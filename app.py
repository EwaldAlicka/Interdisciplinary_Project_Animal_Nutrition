import numpy as np
import pandas as pd
import pulp
import streamlit as st

# ---------------------------
# Page
# ---------------------------
st.set_page_config(page_title="Animal Nutrition Optimierer", layout="wide")

st.markdown(
    """
    <style>
    /* Größe/Shape des Buttons */
    div[data-testid="stButton"] > button {
        padding: 0.5rem 0.8rem !important;
        border-radius: 10px !important;
    }

    /* ALLES im Button groß machen (Text sitzt je nach Streamlit-Version in unterschiedlichen Nodes) */
    div[data-testid="stButton"] > button * {
        font-size: 1.5rem !important;
        font-weight: 800 !important;
        line-height: 1.1 !important;
    }
    </style>
    """,
    unsafe_allow_html=True
)



col_left, col_right = st.columns([6, 1])
with col_left:
    st.title("🐾💊 Animal Supplement Optimierer")

with col_right:
    st.image("static/Vetmedlogo.png", width='stretch')
    st.markdown(
        "<div style='text-align: right;'>Univ.-Prof. Dr. Qendrim Zebeli</div>",
        unsafe_allow_html=True
    )

st.write(
    "Lade die beiden Excel-Dateien hoch. Die Dateien werden zuerst in ein Standardformat gebracht "
    "und anschließend fachlich geprüft."
)

# ---------------------------
# UI styling (checkbox + titles + inline status)
# ---------------------------
st.markdown(
    """
    <style>
    /* Bigger / clearer checkbox */
    div[data-testid="stCheckbox"] label {
        font-size: 1.08rem;
        font-weight: 650;
        line-height: 1.35;
    }
    div[data-testid="stCheckbox"] input {
        transform: scale(1.45);
        margin-right: 10px;
    }

    /* Upload titles */
    .upload-title {
        font-size: 1.10rem;
        font-weight: 750;
        margin-bottom: 0.1rem;
    }
    .muted-hint {
        color: rgba(49, 51, 63, 0.7);
        font-size: 0.95rem;
        margin-top: -0.1rem;
        margin-bottom: 0.6rem;
    }

    /* Status line */
    .statusline {
        font-size: 1.05rem;
        font-weight: 650;
        margin: 0.15rem 0 0.65rem 0;
    }
    .statusicon {
        float: right;
        font-size: 1.2rem;
    }

    /* Compact “success row” (green but single line) */
    .okrow {
        background: rgba(46, 184, 92, 0.12);
        border: 1px solid rgba(46, 184, 92, 0.30);
        border-radius: 10px;
        padding: 0.55rem 0.7rem;
        margin: 0.45rem 0 0.55rem 0;
        font-weight: 650;
    }
    .warnrow {
        background: rgba(255, 165, 0, 0.12);
        border: 1px solid rgba(255, 165, 0, 0.30);
        border-radius: 10px;
        padding: 0.55rem 0.7rem;
        margin: 0.45rem 0 0.55rem 0;
        font-weight: 650;
    }
    </style>
    """,
    unsafe_allow_html=True
)

# ---------------------------
# 1) Parsing (raw Excel -> canonical DataFrame)
# ---------------------------
@st.cache_data
def parse_constraints_excel(file) -> pd.DataFrame:
    df = pd.read_excel(file, header=[0, 1], nrows=6)

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
def parse_supplements_excel(file) -> pd.DataFrame:
    df_efm = pd.read_excel(file, sheet_name="EFM", header=2)
    df_einzel = pd.read_excel(file, sheet_name="Einzelfuttermittel", header=2)

    df_einzel = df_einzel.rename(columns={"Taurin [mg]/[100 g]": "Taurin [mg]/[100g]"})

    df_efm = df_efm.dropna(axis=1, how="all").dropna(subset=["Identifier"])
    df_einzel = df_einzel.dropna(axis=1, how="all").dropna(subset=["Identifier"])

    df_efm_slim = df_efm.iloc[:, 4:-13]
    df_einzel_slim = df_einzel.iloc[:, 5:-12]

    for c in set(df_efm_slim.columns) - set(df_einzel_slim.columns):
        df_einzel_slim[c] = 0
    for c in set(df_einzel_slim.columns) - set(df_efm_slim.columns):
        df_efm_slim[c] = 0

    df = pd.concat([df_efm_slim, df_einzel_slim], ignore_index=True)
    df.columns = [c.split("]", 1)[0] + "]" if "]" in c else c for c in df.columns]
    return df


# ---------------------------
# 2) Validation (canonical DF -> issues)
# ---------------------------
def validate_constraints_df(constraints: pd.DataFrame):
    issues = []

    required_rows = {"Tagesbedarf", "Maximaler_Wert", "Grundnahrung"}
    if not required_rows.issubset(set(constraints.index)):
        issues.append("Pflichtzeilen fehlen nach Parsing (Tagesbedarf/Maximaler_Wert/Grundnahrung).")

    if constraints.shape[1] == 0:
        issues.append("Keine Nährstoffspalten erkannt (nach Parsing).")

    if constraints.isna().any().any():
        issues.append("NaN-Werte nach Parsing vorhanden.")

    try:
        min_vals = pd.to_numeric(constraints.loc["Tagesbedarf"], errors="coerce")
        max_vals = pd.to_numeric(constraints.loc["Maximaler_Wert"], errors="coerce")
        base_vals = pd.to_numeric(constraints.loc["Grundnahrung"], errors="coerce")

        if min_vals.isna().any() or max_vals.isna().any() or base_vals.isna().any():
            issues.append("Nicht-numerische Werte in Tagesbedarf/Maximaler_Wert/Grundnahrung.")

        if (min_vals < 0).any():
            issues.append("Negative Bedarfswerte gefunden.")

        if (min_vals > max_vals).any():
            issues.append("Tagesbedarf > Maximalwert bei mindestens einem Nährstoff.")
    except Exception:
        issues.append("Werte konnten nicht numerisch interpretiert werden.")

    return issues


def validate_supplements_df(supplements: pd.DataFrame):
    issues = []

    required_cols = {"Futtermittel", "Preis (€) pro kg"}
    missing = required_cols - set(supplements.columns)
    if missing:
        issues.append(f"Pflichtspalten fehlen nach Parsing: {', '.join(sorted(missing))}.")

    if supplements.shape[0] == 0:
        issues.append("Keine Zeilen erkannt (nach Parsing).")

    if "Preis (€) pro kg" in supplements.columns:
        prices = pd.to_numeric(supplements["Preis (€) pro kg"], errors="coerce")
        if prices.isna().any():
            issues.append("Nicht-numerische/fehlende Preise gefunden (diese Zeilen können ignoriert werden).")
        if (prices < 0).any():
            issues.append("Negative Preise gefunden.")

    return issues


# ---------------------------
# 2b) Excluded supplements report
# ---------------------------
def get_excluded_supplements(supplements: pd.DataFrame) -> pd.DataFrame:
    if "Preis (€) pro kg" not in supplements.columns or "Futtermittel" not in supplements.columns:
        return pd.DataFrame(columns=["Excel-Zeile", "Futtermittel", "Preis (€) pro kg", "Ausschlussgrund"])

    df = supplements.copy()
    df["_Excel_Zeile"] = df.index + 2  # approximate row hint

    prices = pd.to_numeric(df["Preis (€) pro kg"], errors="coerce")
    mask_no_price = prices.isna()

    excluded = df.loc[mask_no_price, ["_Excel_Zeile", "Futtermittel", "Preis (€) pro kg"]].copy()
    excluded["Ausschlussgrund"] = "Kein gültiger Preis angegeben"
    excluded = excluded.rename(columns={"_Excel_Zeile": "Excel-Zeile"})
    excluded = excluded.sort_values(by=["Excel-Zeile", "Futtermittel"], ascending=True)
    return excluded


# ---------------------------
# 3) Optimization
# ---------------------------
def optimize_fast(constraints: pd.DataFrame, supplements: pd.DataFrame):
    relevant = list(set(constraints.columns).intersection(set(supplements.columns)))
    nutrient_cols = [c for c in relevant if "Verhältnis" not in c]

    base = pd.to_numeric(constraints.loc["Grundnahrung", nutrient_cols], errors="coerce").fillna(0.0)
    min_req = pd.to_numeric(constraints.loc["Tagesbedarf", nutrient_cols], errors="coerce").fillna(0.0)
    max_req = pd.to_numeric(constraints.loc["Maximaler_Wert", nutrient_cols], errors="coerce")

    min_supp = (min_req - base).clip(lower=0.0)
    max_supp = (max_req - base)

    infeasible = max_supp[max_supp < 0]
    infeasible_msg = infeasible.to_dict() if len(infeasible) else None

    # Exclude missing/non-numeric prices + missing names
    supp = supplements.dropna(subset=["Preis (€) pro kg", "Futtermittel"]).copy()
    supp["Preis (€) pro kg"] = pd.to_numeric(supp["Preis (€) pro kg"], errors="coerce")
    supp = supp.dropna(subset=["Preis (€) pro kg"])

    for c in nutrient_cols:
        supp[c] = pd.to_numeric(supp.get(c, 0), errors="coerce").replace([np.inf, -np.inf], np.nan).fillna(0.0)

    supp = supp.set_index("Futtermittel")
    supp = supp[supp[nutrient_cols].abs().sum(axis=1) > 0]

    if supp.shape[0] == 0:
        return "Infeasible", None, None, infeasible_msg

    model = pulp.LpProblem("Supplement_Optimierung", pulp.LpMinimize)
    x = {s: pulp.LpVariable(s, lowBound=0) for s in supp.index}

    model += pulp.lpSum(supp.loc[s, "Preis (€) pro kg"] * x[s] for s in supp.index)

    for n in nutrient_cols:
        intake = pulp.lpSum(supp.loc[s, n] * x[s] for s in supp.index)
        if min_supp[n] > 0:
            model += intake >= float(min_supp[n])
        if pd.notna(max_supp[n]):
            model += intake <= float(max_supp[n])

    model.solve(pulp.PULP_CBC_CMD(msg=False))

    status = pulp.LpStatus[model.status]
    if status != "Optimal":
        return status, None, None, infeasible_msg

    solution = pd.Series({s: x[s].value() for s in x if (x[s].value() or 0) > 1e-9}).sort_values(ascending=False)
    cost = float(pulp.value(model.objective))

    return status, solution, cost, infeasible_msg


# ---------------------------
# UI – Upload section with dropdowns + status inside dropdown
# ---------------------------
st.markdown("### 📥 Dateien hochladen")

constraints = None
supplements = None

ration_ok = False
supp_ok = False
excluded_supps_table = pd.DataFrame()

with st.expander("Dateien hochladen (aufklappen)", expanded=True):
    # Status line INSIDE the upload dropdown (as requested)
    overall_status_ok = ration_ok and supp_ok
    overall_icon = "✅" if overall_status_ok else "⏳"

    left, right = st.columns(2)

    # -------- LEFT: Rationsdatei --------
    with left:
        with st.expander("Rationsdatei", expanded=True):
            #ration_icon = "✅" if ration_ok else "⏳"

            st.markdown(f"""<div class='upload-title'>Rationsdatei<span style="float:right; font-size:1.2rem;"></span></div>""",unsafe_allow_html=True)           
        
            st.markdown("<div class='muted-hint'>(z.B. Ration Katze.xlsx)</div>", unsafe_allow_html=True)

            ration_file = st.file_uploader(
                "Rationsdatei Upload",
                type="xlsx",
                label_visibility="collapsed"
            )

            if ration_file:
                #st.markdown("**Rationsdatei prüfen…**")
                try:
                    constraints = parse_constraints_excel(ration_file)
                    issues = validate_constraints_df(constraints)
                    if issues:
                        warning_text = (
                            "⚠️ **Warnung! Das Format scheint nicht zu passen:**\n\n"
                            + "\n".join(f"- {msg}" for msg in issues)
                        )
                        st.warning(warning_text)
                        ration_ok = False
                    else:
                        ration_ok = True
                        st.markdown(
                            "<div class='okrow'>✅ Format passt! </div>",
                            unsafe_allow_html=True
                        )

                except Exception as e:
                    st.error("❌ Excel-Format konnte nicht geparst werden.")
                    st.caption(f"Technischer Hinweis: {e}")
                    ration_ok = False


    # -------- RIGHT: Supplementdatenbank --------
    with right:
        with st.expander("Supplementdatenbank", expanded=True):
            st.markdown("<div class='upload-title'>Supplementdatenbank</div>", unsafe_allow_html=True)
            st.markdown("<div class='muted-hint'>(z.B. Database Supplemente.xlsx)</div>", unsafe_allow_html=True)

            supp_file = st.file_uploader(
                "Supplementdatenbank Upload",
                type="xlsx",
                label_visibility="collapsed"
            )

            proceed_without_incomplete = False

            if supp_file:
                try:
                    supplements = parse_supplements_excel(supp_file)
                    issues = validate_supplements_df(supplements)

                    excluded_supps_table = get_excluded_supplements(supplements)

                    if issues:
                        warning_text = (
                            "⚠️ **Warnung! Das Format scheint nicht zu passen:**\n\n"
                            + "\n".join(f"- {msg}" for msg in issues)
                        )
                        st.warning(warning_text)

                    if not excluded_supps_table.empty:
                        st.info(
                            f"{len(excluded_supps_table)} Supplements haben keinen gültigen Preis "
                            "und werden automatisch ausgeschlossen."
                        )
                        st.dataframe(excluded_supps_table, use_container_width=True)

                        proceed_without_incomplete = st.checkbox(
                            "Ich möchte ohne den unvollständigen Supplements fortfahren.",
                            value=False
                        )

                    supp_ok = (supplements is not None) and (proceed_without_incomplete or excluded_supps_table.empty)

                    if supp_ok and supplements is not None:
                        st.markdown(
                            "<div class='okrow'>✅ Format passt!</div>",
                            unsafe_allow_html=True
                        )
                    else:
                        st.markdown(
                            "<div class='warnrow'>⏳ Hinweis: Kästchen drüber anklicken um unvollständige Supplemente zu ignorieren</div>",
                            unsafe_allow_html=True
                        )

                except Exception as e:
                    st.error("❌ Excel-Format konnte nicht gelesen werden.")
                    st.caption(f"Technischer Hinweis: {e}")
                    supp_ok = False

# ---------------------------
# Overall status (single line, outside dropdown too)
# ---------------------------
    status_ok = ration_ok and supp_ok
    status_icon = "✅" if status_ok else "⏳"
    st.markdown(
        f"""
        <div class='statusline' style='font-size:1.8rem;'>
            Datenformat
            <span style='font-size:1.8rem; margin-left:0.2rem;'>{status_icon}</span>
        </div>
        """,
        unsafe_allow_html=True
)

st.divider()

# ---------------------------
# Run optimization (only if both OK)
# ---------------------------
can_run = status_ok and constraints is not None and supplements is not None

st.markdown("### 📈 Optimierung")

with st.expander("Dateien hochladen (aufklappen)", expanded=True):

    if st.button("🚀 Optimierung starten", disabled=not can_run):
        status_box = st.status("Starte Optimierung…", expanded=True)
        try:
            status_box.update(label="Optimiere… (Solver läuft)")
            status, solution, cost, infeasible_msg = optimize_fast(constraints, supplements)
            status_box.update(label="Fertig.", state="complete")
        except Exception as e:
            status_box.update(label="Fehler", state="error")
            st.exception(e)
            st.stop()

        st.subheader("Ergebnis")
        st.write(f"**Solver-Status:** {status}")

        if infeasible_msg:
            st.warning("Achtung: Grundnahrung überschreitet bereits den Maximalwert bei einigen Nährstoffen.")
            st.json(infeasible_msg)

        if status != "Optimal" or solution is None:
            st.error("Keine optimale Lösung gefunden. Prüfe Datenformat / Constraints / Einheiten.")
            st.stop()

        st.success(f"💰 **Minimale Kosten:** {cost:.4f} €")
        st.subheader("Optimale Supplement-Mengen")
        st.dataframe(solution.to_frame("Menge"), use_container_width=True)
