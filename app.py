import time
import streamlit as st
import pandas as pd
import numpy as np
import pulp
from pathlib import Path


# ---------------------------
# Helpers
# ---------------------------
@st.cache_data
def load_constraints_excel(path: str) -> pd.DataFrame:
    df = pd.read_excel(path, header=[0, 1], nrows=6)
    df = df.iloc[:, 3:-1]
    df = df.drop(df.index[-3:-1])
    df = df.dropna(axis=1, how="any")
    df = df.set_index(df.columns[0])

    df.index = ["Tagesbedarf", "Maximaler_Wert", "Bedarfsdeck", "Grundnahrung"]
    df.columns = [
        f"{str(col[0]).strip()} {str(col[1]).strip()}" if pd.notna(col[1]) else str(col[0]).strip()
        for col in df.columns
    ]
    df = df.rename(columns={"Ca:P Verhältnis": "Ca/P-Verhältnis"})
    return df


@st.cache_data
def load_supplements_excel(path: str) -> pd.DataFrame:
    df_efm = pd.read_excel(path, sheet_name="EFM", header=2)
    df_einzel = pd.read_excel(path, sheet_name="Einzelfuttermittel", header=2)

    df_einzel = df_einzel.rename(columns={"Taurin [mg]/[100 g]": "Taurin [mg]/[100g]"})
    df_efm = df_efm.dropna(axis=1, how="all").dropna(subset=["Identifier"])
    df_einzel = df_einzel.dropna(axis=1, how="all").dropna(subset=["Identifier"])

    df_efm_slim = df_efm.iloc[:, 4:-13]
    df_einzel_slim = df_einzel.iloc[:, 5:-12]

    d3_new = list(set(df_efm_slim.columns) - set(df_einzel_slim.columns))
    d2_new = list(set(df_einzel_slim.columns) - set(df_efm_slim.columns))
    df_einzel_slim[d3_new] = 0
    df_efm_slim[d2_new] = 0

    df = pd.concat([df_efm_slim, df_einzel_slim], ignore_index=True)

    cleaned_cols = [s.split("]", 1)[0] + "]" if "]" in s else s for s in list(df.columns)]
    df.columns = cleaned_cols
    return df


def optimize_fast(constraint_df: pd.DataFrame, supp_df: pd.DataFrame, debug=False, time_limit=None):
    t0 = time.perf_counter()

    # Schnittmenge der Nährstoffe
    relevant = list(set(constraint_df.columns).intersection(set(supp_df.columns)))
    # Verhältnis-Spalten erstmal raus (wie zuvor)
    nutrient_cols = [c for c in relevant if "Verhältnis" not in c]

    # Constraints extrahieren
    fc = constraint_df[nutrient_cols]
    base = pd.to_numeric(fc.loc["Grundnahrung"], errors="coerce").fillna(0.0)
    min_req = pd.to_numeric(fc.loc["Tagesbedarf"], errors="coerce").fillna(0.0)
    max_req = pd.to_numeric(fc.loc["Maximaler_Wert"], errors="coerce")

    min_supp = (min_req - base).clip(lower=0.0)
    max_supp = (max_req - base)

    infeasible = max_supp[max_supp < 0]
    infeasible_msg = infeasible.to_dict() if len(infeasible) else None

    t1 = time.perf_counter()

    # Supplements vorbereiten
    if "Preis (€) pro kg" not in supp_df.columns:
        raise ValueError("In der Supplement-Datei fehlt: 'Preis (€) pro kg'")
    if "Futtermittel" not in supp_df.columns:
        raise ValueError("In der Supplement-Datei fehlt: 'Futtermittel'")

    supp = supp_df.dropna(subset=["Preis (€) pro kg", "Futtermittel"]).copy()
    supp["Preis (€) pro kg"] = pd.to_numeric(supp["Preis (€) pro kg"], errors="coerce")
    supp = supp.dropna(subset=["Preis (€) pro kg"])

    # Nährstoffspalten in numeric (fehlende = 0)
    supp[nutrient_cols] = (
        supp[nutrient_cols]
        .apply(pd.to_numeric, errors="coerce")
        .replace([np.inf, -np.inf], np.nan)
        .fillna(0.0)
    )

    # Index: Futtermittel
    supp = supp.set_index("Futtermittel")

    # 🔥 SPEED-UP: Supplements entfernen, die für alle relevanten Nährstoffe 0 liefern
    nonzero_mask = (supp[nutrient_cols].abs().sum(axis=1) > 0)
    supp = supp.loc[nonzero_mask]

    costs = supp["Preis (€) pro kg"].copy()
    comp = supp[nutrient_cols].copy()

    # nochmal check
    if comp.shape[0] == 0:
        raise ValueError("Nach Filterung hat kein Supplement relevante Nährstoffe (alles 0).")

    t2 = time.perf_counter()

    # LP Modell
    model = pulp.LpProblem("Supplement_Optimierung", pulp.LpMinimize)
    names = list(comp.index)

    x = {s: pulp.LpVariable(f"x_{i}", lowBound=0) for i, s in enumerate(names)}
    model += pulp.lpSum(costs[s] * x[s] for s in names)

    # Constraints effizienter: pro Nutrient einmal bauen
    # (comp als numpy: schneller als viele DataFrame lookups)
    comp_np = comp.to_numpy(dtype=float)   # rows = supplements, cols = nutrients
    min_np = min_supp.to_numpy(dtype=float)
    max_np = max_supp.to_numpy(dtype=float)

    # Wir bauen constraints spaltenweise über numpy + pulp
    # pulp braucht trotzdem lpSum, aber wir vermeiden df.loc in loops
    for j, nutr in enumerate(nutrient_cols):
        # Intake = sum_i comp[i,j] * x_i
        intake = pulp.lpSum(comp_np[i, j] * x[names[i]] for i in range(len(names)))

        if min_np[j] > 0:
            model += intake >= float(min_np[j]), f"{nutr}_min"
        if pd.notna(max_np[j]):
            model += intake <= float(max_np[j]), f"{nutr}_max"

    t3 = time.perf_counter()

    # Solve
    solver = pulp.PULP_CBC_CMD(
        msg=debug,
        threads=0,  # 0 = CBC entscheidet; auf manchen Systemen auch threads=2/4 gut
        timeLimit=time_limit
    )
    model.solve(solver)

    t4 = time.perf_counter()

    status = pulp.LpStatus[model.status]
    if status != "Optimal":
        timings = {
            "prep_constraints_s": round(t1 - t0, 4),
            "prep_supplements_s": round(t2 - t1, 4),
            "build_model_s": round(t3 - t2, 4),
            "solve_s": round(t4 - t3, 4),
            "total_s": round(t4 - t0, 4),
            "n_supplements": int(len(names)),
            "n_nutrients": int(len(nutrient_cols)),
        }
        return status, None, None, None, infeasible_msg, timings

    sol = pd.Series({s: x[s].varValue for s in names}, name="Menge").fillna(0.0)
    sol = sol[sol > 1e-9].sort_values(ascending=False)
    total_cost = float(pulp.value(model.objective))

    # Report (vectorisiert)
    x_vec = np.array([x[s].varValue or 0.0 for s in names], dtype=float)
    supp_intake = pd.Series(comp_np.T @ x_vec, index=nutrient_cols)  # (nutrients x supplements) @ x
    total_intake = base + supp_intake

    report = pd.DataFrame({
        "Grundnahrung": base,
        "Supplemente": supp_intake,
        "Gesamt": total_intake,
        "Min_Bedarf": min_req,
        "Max_Wert": max_req,
    })

    timings = {
        "prep_constraints_s": round(t1 - t0, 4),
        "prep_supplements_s": round(t2 - t1, 4),
        "build_model_s": round(t3 - t2, 4),
        "solve_s": round(t4 - t3, 4),
        "total_s": round(t4 - t0, 4),
        "n_supplements": int(len(names)),
        "n_nutrients": int(len(nutrient_cols)),
    }

    return status, sol, total_cost, report, infeasible_msg, timings


# ---------------------------
# UI
# ---------------------------
st.set_page_config(page_title="Animal Nutrition Optimizer", layout="wide")
st.title("🐾 Supplement Optimizer (Basic)")

constraint_path = st.text_input("Pfad zur Ration-Datei", "Ration Katze.xlsx")
supp_path = st.text_input("Pfad zur Supplement-Datenbank", "Database Supplemente.xlsx")

with st.expander("⚙️ Debug / Performance", expanded=False):
    debug = st.checkbox("Debug-Ausgaben vom Solver (CBC msg)", value=False)
    show_timings = st.checkbox("Zeige Timings", value=True)
    time_limit = st.number_input("Optional: Solver Time Limit (Sekunden, 0 = unbegrenzt)", min_value=0, value=0, step=5)

st.divider()

if st.button("✅ OK, let's go"):
    if not Path(constraint_path).exists():
        st.error(f"Datei nicht gefunden: {constraint_path}")
        st.stop()
    if not Path(supp_path).exists():
        st.error(f"Datei nicht gefunden: {supp_path}")
        st.stop()

    tl = None if time_limit == 0 else int(time_limit)

    status_box = st.status("Starte...", expanded=True)
    try:
        status_box.update(label="1/4 Lade Constraint-Excel…")
        constraints = load_constraints_excel(constraint_path)

        status_box.update(label="2/4 Lade Supplements-Excel…")
        supplements = load_supplements_excel(supp_path)

        status_box.update(label="3/4 Optimiere… (Solver läuft)")
        status, sol, cost, report, infeasible_msg, timings = optimize_fast(
            constraints, supplements, debug=debug, time_limit=tl
        )

        status_box.update(label="4/4 Fertig.", state="complete")

    except Exception as e:
        status_box.update(label="Fehler", state="error")
        st.exception(e)
        st.stop()

    st.subheader("Ergebnis")
    st.write(f"**Solver-Status:** {status}")

    if show_timings:
        st.info(f"Timings: {timings}")

    if infeasible_msg:
        st.warning("Achtung: Grundnahrung überschreitet bereits Max bei einigen Nährstoffen.")
        st.json(infeasible_msg)

    if status != "Optimal":
        st.error("Keine optimale Lösung gefunden.")
        st.stop()

    st.success(f"**Minimale Kosten:** {cost:.4f} €")

    st.subheader("Optimale Supplement-Mengen")
    st.dataframe(sol.to_frame(), use_container_width=True)

    st.subheader("Nährstoff-Bilanz")
    st.dataframe(report.round(4), use_container_width=True)
