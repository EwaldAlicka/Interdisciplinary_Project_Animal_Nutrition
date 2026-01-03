import time
from pathlib import Path

import numpy as np
import pandas as pd
import pulp
import streamlit as st

# ---------------------------
# Page
# ---------------------------
st.set_page_config(page_title="Animal Nutrition Optimizer", layout="wide")
st.title("🐾 Supplement Optimizer V1")
st.write(
    "Lade die beiden Excel-Dateien hoch, starte die Optimierung und erhalte die günstigste Supplement-Strategie "
    "unter Einhaltung der Nährstoff-Min/Max-Intervalle."
)

# ---------------------------
# Loaders (work with uploaded files OR paths)
# ---------------------------
@st.cache_data
def load_constraints_excel(path_or_file) -> pd.DataFrame:
    # Expected format from your VetMed sheet (kept close to your notebook logic)
    df = pd.read_excel(path_or_file, header=[0, 1], nrows=6)

    df = df.iloc[:, 3:-1]
    df = df.drop(df.index[-3:-1])
    df = df.dropna(axis=1, how="any")
    df = df.set_index(df.columns[0])

    df.index = ["Tagesbedarf", "Maximaler_Wert", "Bedarfsdeck", "Grundnahrung"]

    # MultiIndex columns -> strings
    df.columns = [
        f"{str(col[0]).strip()} {str(col[1]).strip()}" if pd.notna(col[1]) else str(col[0]).strip()
        for col in df.columns
    ]

    # small harmonization
    df = df.rename(columns={"Ca:P Verhältnis": "Ca/P-Verhältnis"})
    return df


@st.cache_data
def load_supplements_excel(path_or_file) -> pd.DataFrame:
    df_efm = pd.read_excel(path_or_file, sheet_name="EFM", header=2)
    df_einzel = pd.read_excel(path_or_file, sheet_name="Einzelfuttermittel", header=2)

    df_einzel = df_einzel.rename(columns={"Taurin [mg]/[100 g]": "Taurin [mg]/[100g]"})

    df_efm = df_efm.dropna(axis=1, how="all").dropna(subset=["Identifier"])
    df_einzel = df_einzel.dropna(axis=1, how="all").dropna(subset=["Identifier"])

    df_efm_slim = df_efm.iloc[:, 4:-13]
    df_einzel_slim = df_einzel.iloc[:, 5:-12]

    # align columns
    d3_new = list(set(df_efm_slim.columns) - set(df_einzel_slim.columns))
    d2_new = list(set(df_einzel_slim.columns) - set(df_efm_slim.columns))
    df_einzel_slim[d3_new] = 0
    df_efm_slim[d2_new] = 0

    df = pd.concat([df_efm_slim, df_einzel_slim], ignore_index=True)

    # normalize column names: keep up to first ']'
    cleaned_cols = [s.split("]", 1)[0] + "]" if "]" in s else s for s in list(df.columns)]
    df.columns = cleaned_cols
    return df


# ---------------------------
# Optimization (faster + timings)
# ---------------------------
def optimize_fast(constraint_df: pd.DataFrame, supp_df: pd.DataFrame, debug=False, time_limit=None):
    t0 = time.perf_counter()

    # shared nutrients
    relevant = list(set(constraint_df.columns).intersection(set(supp_df.columns)))
    nutrient_cols = [c for c in relevant if "Verhältnis" not in c]

    # constraints
    fc = constraint_df[nutrient_cols]
    base = pd.to_numeric(fc.loc["Grundnahrung"], errors="coerce").fillna(0.0)
    min_req = pd.to_numeric(fc.loc["Tagesbedarf"], errors="coerce").fillna(0.0)
    max_req = pd.to_numeric(fc.loc["Maximaler_Wert"], errors="coerce")

    min_supp = (min_req - base).clip(lower=0.0)
    max_supp = (max_req - base)

    infeasible = max_supp[max_supp < 0]
    infeasible_msg = infeasible.to_dict() if len(infeasible) else None

    t1 = time.perf_counter()

    # supplements prep
    if "Preis (€) pro kg" not in supp_df.columns:
        raise ValueError("In der Supplement-Datei fehlt: 'Preis (€) pro kg'")
    if "Futtermittel" not in supp_df.columns:
        raise ValueError("In der Supplement-Datei fehlt: 'Futtermittel'")

    supp = supp_df.dropna(subset=["Preis (€) pro kg", "Futtermittel"]).copy()
    supp["Preis (€) pro kg"] = pd.to_numeric(supp["Preis (€) pro kg"], errors="coerce")
    supp = supp.dropna(subset=["Preis (€) pro kg"])

    supp[nutrient_cols] = (
        supp[nutrient_cols]
        .apply(pd.to_numeric, errors="coerce")
        .replace([np.inf, -np.inf], np.nan)
        .fillna(0.0)
    )

    supp = supp.set_index("Futtermittel")

    # SPEED-UP: remove supplements that contribute nothing to any nutrient
    nonzero_mask = (supp[nutrient_cols].abs().sum(axis=1) > 0)
    supp = supp.loc[nonzero_mask]

    costs = supp["Preis (€) pro kg"].copy()
    comp = supp[nutrient_cols].copy()

    if comp.shape[0] == 0:
        raise ValueError("Nach Filterung hat kein Supplement relevante Nährstoffe (alles 0).")

    t2 = time.perf_counter()

    # LP model
    model = pulp.LpProblem("Supplement_Optimierung", pulp.LpMinimize)
    names = list(comp.index)

    x = {s: pulp.LpVariable(f"x_{i}", lowBound=0) for i, s in enumerate(names)}
    model += pulp.lpSum(costs[s] * x[s] for s in names)

    comp_np = comp.to_numpy(dtype=float)
    min_np = min_supp.to_numpy(dtype=float)
    max_np = max_supp.to_numpy(dtype=float)

    for j, nutr in enumerate(nutrient_cols):
        intake = pulp.lpSum(comp_np[i, j] * x[names[i]] for i in range(len(names)))
        if min_np[j] > 0:
            model += intake >= float(min_np[j]), f"{nutr}_min"
        if pd.notna(max_np[j]):
            model += intake <= float(max_np[j]), f"{nutr}_max"

    t3 = time.perf_counter()

    solver = pulp.PULP_CBC_CMD(
        msg=debug,
        threads=0,
        timeLimit=time_limit
    )
    model.solve(solver)

    t4 = time.perf_counter()

    status = pulp.LpStatus[model.status]
    timings = {
        "prep_constraints_s": round(t1 - t0, 4),
        "prep_supplements_s": round(t2 - t1, 4),
        "build_model_s": round(t3 - t2, 4),
        "solve_s": round(t4 - t3, 4),
        "total_s": round(t4 - t0, 4),
        "n_supplements": int(len(names)),
        "n_nutrients": int(len(nutrient_cols)),
    }

    if status != "Optimal":
        return status, None, None, None, infeasible_msg, timings

    sol = pd.Series({s: x[s].varValue for s in names}, name="Menge").fillna(0.0)
    sol = sol[sol > 1e-9].sort_values(ascending=False)
    total_cost = float(pulp.value(model.objective))

    # Report (vectorized)
    x_vec = np.array([x[s].varValue or 0.0 for s in names], dtype=float)
    supp_intake = pd.Series(comp_np.T @ x_vec, index=nutrient_cols)
    total_intake = base + supp_intake

    report = pd.DataFrame({
        "Grundnahrung": base,
        "Supplemente": supp_intake,
        "Gesamt": total_intake,
        "Min_Bedarf": min_req,
        "Max_Wert": max_req,
    })

    return status, sol, total_cost, report, infeasible_msg, timings


# ---------------------------
# UI: Upload (drag & drop)
# ---------------------------
st.subheader("📥 Dateien hochladen")

col1, col2 = st.columns(2)
with col1:
    ration_file = st.file_uploader(
        "Ration-Datei (z.B. Ration Katze.xlsx)",
        type=["xlsx"],
        accept_multiple_files=False
    )

with col2:
    supp_file = st.file_uploader(
        "Supplement-Datenbank (Database Supplemente.xlsx)",
        type=["xlsx"],
        accept_multiple_files=False
    )

# if ration_file:
#     st.caption(f"Ration geladen: **{ration_file.name}**")
# if supp_file:
#     st.caption(f"Supplements geladen: **{supp_file.name}**")

# with st.expander("⚙️ Debug / Performance", expanded=False):
#     debug = st.checkbox("Debug-Ausgaben vom Solver (CBC msg)", value=False)
#     show_timings = st.checkbox("Zeige Timings", value=True)
#     time_limit = st.number_input(
#         "Optional: Solver Time Limit (Sekunden, 0 = unbegrenzt)",
#         min_value=0, value=0, step=5
#     )

st.divider()

# ---------------------------
# Run optimization
# ---------------------------
run_disabled = (ration_file is None) or (supp_file is None)
if st.button("✅ OK, let's go", disabled=run_disabled):
    tl = None if time_limit == 0 else int(time_limit)

    status_box = st.status("Starte...", expanded=True)
    try:
        status_box.update(label="1/3 Lade Ration-Excel…")
        constraints = load_constraints_excel(ration_file)

        status_box.update(label="2/3 Lade Supplements-Excel…")
        supplements = load_supplements_excel(supp_file)

        status_box.update(label="3/3 Optimiere… (Solver läuft)")
        status, sol, cost, report, infeasible_msg, timings = optimize_fast(
            constraints, supplements, debug=debug, time_limit=tl
        )

        status_box.update(label="Fertig.", state="complete")

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
        st.error("Keine optimale Lösung gefunden. Prüfe Datenformat / Constraints / Einheiten.")
        st.stop()

    st.success(f"**Minimale Kosten:** {cost:.4f} €")

    st.subheader("Optimale Supplement-Mengen")
    st.dataframe(sol.to_frame(), use_container_width=True)

    st.subheader("Nährstoff-Bilanz")
    st.dataframe(report.round(4), use_container_width=True)

# st.caption("Basic v1 – nächste Schritte: Auswahl Tier/Weight-Group, Einheiten/Skalierung, Penalty für Anzahl Supplements.")
