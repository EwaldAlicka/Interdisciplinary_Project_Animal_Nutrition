# ============================================================
# Animal Supplement Optimierer (Streamlit App)
#
# Update (this turn):
# - "⚠️ Fehler" Spalte NICHT mehr dauerhaft in der Haupt-Tabelle anzeigen.
# - Validierung bleibt aktiv (Min > Max, Grundnahrung > Max).
# - Detail-Ansicht zeigt weiterhin alle Spalten inkl. "⚠️ Fehler".
# - Fixieren ist NICHT möglich, solange Fehler vorhanden sind.
#
# Hinweis:
# Streamlit data_editor kann Rows nicht zuverlässig "rot einfärben" (conditional row styling).
# ============================================================

import numpy as np
import pandas as pd
import pulp
import streamlit as st
import streamlit.components.v1 as components
import io
import matplotlib.pyplot as plt
import re

# ------------------------------------------------------------
# 0) PAGE CONFIG
# ------------------------------------------------------------
st.set_page_config(page_title="Animal Nutrition Optimierer", layout="wide")

# ------------------------------------------------------------
# 0b) GLOBAL CSS (Design Controls)
# ------------------------------------------------------------
st.markdown(
    """
    <style>
    :root{
      --btn_primary_font: 1.50rem;
      --btn_primary_weight: 600;
      --btn_primary_py: 0.55rem;
      --btn_primary_px: 0.90rem;
      --btn_primary_radius: 10px;

      --btn_secondary_font: 1.15rem;
      --btn_secondary_weight: 450;
      --btn_secondary_py: 0.25rem;
      --btn_secondary_px: 0.65rem;
      --btn_secondary_radius: 10px;

      --chk_font: 1.25rem;
      --chk_weight: 500;
      --chk_scale: 1.45;
      --chk_gap: 12px;

      --caption_font: 1.15rem;
      --caption_weight: 450;
      --caption_opacity: 0.85;
      --caption_line: 1.35;
    }

    /* CHECKBOXES */
    div[data-testid="stCheckbox"] label,
    div[data-testid="stCheckbox"] label p,
    div[data-testid="stCheckbox"] label span{
      font-size: var(--chk_font) !important;
      font-weight: var(--chk_weight) !important;
      line-height: 1.35 !important;
    }
    div[data-testid="stCheckbox"] input{
      transform: scale(var(--chk_scale)) !important;
      margin-right: var(--chk_gap) !important;
    }

    /* CAPTION */
    div[data-testid="stCaption"],
    div[data-testid="stCaption"] *{
      font-size: var(--caption_font) !important;
      font-weight: var(--caption_weight) !important;
      line-height: var(--caption_line) !important;
      opacity: var(--caption_opacity) !important;
    }
    div[data-testid="stMarkdownContainer"] small,
    div[data-testid="stMarkdownContainer"] small *{
      font-size: var(--caption_font) !important;
      font-weight: var(--caption_weight) !important;
      line-height: var(--caption_line) !important;
      opacity: var(--caption_opacity) !important;
    }
    div[data-testid="stMarkdownContainer"] p small,
    div[data-testid="stMarkdownContainer"] p small *{
      font-size: var(--caption_font) !important;
      font-weight: var(--caption_weight) !important;
      line-height: var(--caption_line) !important;
      opacity: var(--caption_opacity) !important;
    }

    .caption-note{
      font-size: var(--caption_font);
      font-weight: var(--caption_weight);
      line-height: var(--caption_line);
      opacity: var(--caption_opacity);
      margin-top: 0.15rem;
      margin-bottom: 0.40rem;
    }

    /* BUTTONS */
    button[kind="primary"],
    button[data-testid="baseButton-primary"]{
      padding: var(--btn_primary_py) var(--btn_primary_px) !important;
      border-radius: var(--btn_primary_radius) !important;
    }
    button[kind="primary"] *,
    button[data-testid="baseButton-primary"] *{
      font-size: var(--btn_primary_font) !important;
      font-weight: var(--btn_primary_weight) !important;
      line-height: 1.1 !important;
    }

    button[kind="secondary"],
    button[data-testid="baseButton-secondary"]{
      padding: var(--btn_secondary_py) var(--btn_secondary_px) !important;
      border-radius: var(--btn_secondary_radius) !important;
    }
    button[kind="secondary"] *,
    button[data-testid="baseButton-secondary"] *{
      font-size: var(--btn_secondary_font) !important;
      font-weight: var(--btn_secondary_weight) !important;
      line-height: 1.2 !important;
    }

    /* Upload titles */
    .upload-title { font-size: 1.10rem; font-weight: 750; margin-bottom: 0.1rem; }
    .muted-hint { color: rgba(49, 51, 63, 0.7); font-size: 1.05rem; margin-top: -0.1rem; margin-bottom: 0.6rem; }

    /* Status line */
    .statusline { font-size: 1.05rem; font-weight: 650; margin: 0.15rem 0 0.65rem 0; }

    /* Compact rows */
    .okrow, .warnrow, .errorrow{
        border-radius: 10px;
        padding: 0.55rem 0.7rem;
        margin: 0.25rem 0 0.25rem 0;
        font-weight: 650;
    }
    .okrow{
        background: rgba(46, 184, 92, 0.12);
        border: 1px solid rgba(46, 184, 92, 0.30);
    }
    .warnrow{
        background: rgba(255, 165, 0, 0.12);
        border: 1px solid rgba(255, 165, 0, 0.30);
    }
    .errorrow{
        background: rgba(255, 0, 0, 0.08);
        border: 1px solid rgba(255, 0, 0, 0.18);
    }

    .warnrow-after { margin-bottom: 0.95rem !important; }
    .nutrient-actions { margin-top: 0rem; }

    /* reduce gap under data_editor */
    div[data-testid="stDataEditor"],
    div[data-testid="stDataFrame"]{
        margin-bottom: 0.10rem !important;
        padding-bottom: 0rem !important;
    }

    /* thin separator without adding big spacing */
    .thin-sep{
      border: 0;
      border-top: 1px solid rgba(49,51,63,0.22);
      margin: 0.20rem 0 0.20rem 0;
      padding: 0;
    }

    /* KPI cards */
    .kpi-card {
        border-radius: 12px;
        padding: 16px 18px;
        border: 1px solid rgba(49,51,63,0.12);
        background: rgba(49,51,63,0.05);
    }
    .kpi-title {
        font-size: 1.05rem;
        font-weight: 700;
        opacity: 0.85;
    }
    .kpi-value {
        font-size: 2.2rem;
        font-weight: 900;
        margin-top: 4px;
        line-height: 1.05;
    }
    </style>
    """,
    unsafe_allow_html=True
)

# ------------------------------------------------------------
# 1) HEADER
# ------------------------------------------------------------
col_left, col_right = st.columns([6, 1])
with col_left:
    st.title("🐾💊 Animal Supplement Optimierer")
with col_right:
    st.image("static/Vetmedlogo.png", width='stretch')
    st.markdown("<div style='text-align: right;'>Univ.-Prof. Dr. Qendrim Zebeli</div>", unsafe_allow_html=True)

st.write(
    "Lade die beiden Excel-Dateien hoch. Die Dateien werden zuerst in ein Standardformat gebracht "
    "und anschließend fachlich geprüft."
)

# ------------------------------------------------------------
# 2) PARSING
# ------------------------------------------------------------
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
    df.columns = [str(c).strip().replace("100 g", "100g") for c in df.columns]
    return df

# ------------------------------------------------------------
# 3) VALIDATION
# ------------------------------------------------------------
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

# ------------------------------------------------------------
# 4) EXCLUDED SUPPLEMENTS REPORT
# ------------------------------------------------------------
def get_excluded_supplements(supplements: pd.DataFrame) -> pd.DataFrame:
    if "Preis (€) pro kg" not in supplements.columns or "Futtermittel" not in supplements.columns:
        return pd.DataFrame(columns=["Excel-Zeile", "Futtermittel", "Preis (€) pro kg", "Ausschlussgrund"])
    df = supplements.copy()
    df["_Excel_Zeile"] = df.index + 2
    prices = pd.to_numeric(df["Preis (€) pro kg"], errors="coerce")
    mask_no_price = prices.isna()
    excluded = df.loc[mask_no_price, ["_Excel_Zeile", "Futtermittel", "Preis (€) pro kg"]].copy()
    excluded["Ausschlussgrund"] = "Kein gültiger Preis angegeben"
    excluded = excluded.rename(columns={"_Excel_Zeile": "Excel-Zeile"})
    excluded = excluded.sort_values(by=["Excel-Zeile", "Futtermittel"], ascending=True)
    return excluded

# ------------------------------------------------------------
# 5) RATION TABLE -> EDITABLE TABLE
# ------------------------------------------------------------
def constraints_to_edit_df(constraints: pd.DataFrame) -> pd.DataFrame:
    nutrients = list(constraints.columns)
    edit = pd.DataFrame({
        "Nährstoff": nutrients,
        "Tagesbedarf (Min)": pd.to_numeric(constraints.loc["Tagesbedarf", nutrients], errors="coerce"),
        "Maximalwert (Max)": pd.to_numeric(constraints.loc["Maximaler_Wert", nutrients], errors="coerce"),
        "Grundnahrung": pd.to_numeric(constraints.loc["Grundnahrung", nutrients], errors="coerce"),
    })
    edit["Bedarf nach Grundnahrung (Min-Base)"] = (edit["Tagesbedarf (Min)"] - edit["Grundnahrung"]).clip(lower=0.0)
    edit["🗑 Löschen"] = False
    return edit


def edit_df_to_constraints(edit_df: pd.DataFrame, original_constraints: pd.DataFrame) -> pd.DataFrame:
    nutrients = edit_df["Nährstoff"].tolist()
    out = original_constraints.copy()
    for n in nutrients:
        if n not in out.columns:
            out[n] = np.nan
    out = out.reindex(columns=nutrients)
    out.loc["Tagesbedarf"] = pd.to_numeric(edit_df["Tagesbedarf (Min)"].values, errors="coerce")
    out.loc["Maximaler_Wert"] = pd.to_numeric(edit_df["Maximalwert (Max)"].values, errors="coerce")
    out.loc["Grundnahrung"] = pd.to_numeric(edit_df["Grundnahrung"].values, errors="coerce")
    return out

# ------------------------------------------------------------
# 5b) Helpers + Optimization (minimal needed)
# ------------------------------------------------------------
def canonical_name(col: str) -> str:
    return str(col).split("/", 1)[0].strip()

def is_100g_col(col: str) -> bool:
    return re.search(r"100\s*g", str(col), flags=re.IGNORECASE) is not None

def infer_available_nutrients_from_supplements(supplements: pd.DataFrame) -> set:
    ignore = {"Futtermittel", "Preis (€) pro kg", "Identifier"}
    cols = [c for c in supplements.columns if c not in ignore]
    return {canonical_name(c) for c in cols}

def build_supp_clean(supplements: pd.DataFrame, nutrient_cols: list) -> pd.DataFrame:
    df = supplements.copy()
    df = df.dropna(subset=["Futtermittel", "Preis (€) pro kg"]).copy()
    df["Preis (€) pro kg"] = pd.to_numeric(df["Preis (€) pro kg"], errors="coerce")
    df = df.dropna(subset=["Preis (€) pro kg"])

    all_cols = [c for c in df.columns if c not in ["Futtermittel", "Preis (€) pro kg"]]
    canon_map = {}
    for c in all_cols:
        canon = canonical_name(c)
        canon_map.setdefault(canon, []).append(c)

    out = pd.DataFrame({"Futtermittel": df["Futtermittel"], "Preis (€) pro kg": df["Preis (€) pro kg"]})

    for n in nutrient_cols:
        cols_for_n = canon_map.get(n, [])
        if not cols_for_n:
            out[n] = 0.0
            continue

        vals = []
        for c in cols_for_n:
            s = pd.to_numeric(df[c], errors="coerce").replace([np.inf, -np.inf], np.nan).fillna(0.0)
            if is_100g_col(c):
                s = s * 10.0
            vals.append(s)

        out[n] = pd.concat(vals, axis=1).mean(axis=1)

    agg = {n: "mean" for n in nutrient_cols}
    agg["Preis (€) pro kg"] = "min"
    out = out.groupby("Futtermittel", as_index=True).agg(agg)
    out = out[out[nutrient_cols].abs().sum(axis=1) > 0]
    return out

def optimize_fast(constraints_effective: pd.DataFrame, supplements: pd.DataFrame):
    nutrients_from_constraints = [c for c in constraints_effective.columns if "Verhältnis" not in str(c)]
    available = infer_available_nutrients_from_supplements(supplements)

    base_all = pd.to_numeric(constraints_effective.loc["Grundnahrung", nutrients_from_constraints], errors="coerce").fillna(0.0)
    min_all = pd.to_numeric(constraints_effective.loc["Tagesbedarf", nutrients_from_constraints], errors="coerce").fillna(0.0)
    max_all = pd.to_numeric(constraints_effective.loc["Maximaler_Wert", nutrients_from_constraints], errors="coerce")

    min_supp_all = (min_all - base_all).clip(lower=0.0)

    missing_required = [n for n in nutrients_from_constraints if (min_supp_all.get(n, 0.0) > 0) and (n not in available)]
    if missing_required:
        infeasible_msg = {
            "Fehlende_Naehrstoffe_in_SupplementDB": missing_required,
            "Hinweis": "Für diese Nährstoffe ist nach Grundnahrung noch Bedarf (>0), aber in der Supplementdatenbank gibt es keine passende Spalte. "
                      "Du kannst Min/Base links anpassen oder später ein Mapping hinzufügen."
        }
        return "Infeasible", None, None, infeasible_msg, None

    nutrient_cols = [n for n in nutrients_from_constraints if n in available]

    base = base_all.reindex(nutrient_cols).fillna(0.0)
    min_req = min_all.reindex(nutrient_cols).fillna(0.0)
    max_req = max_all.reindex(nutrient_cols)

    min_supp = (min_req - base).clip(lower=0.0)
    max_supp = (max_req - base)

    infeasible = max_supp[max_supp < 0]
    infeasible_msg = infeasible.to_dict() if len(infeasible) else None

    supp_clean = build_supp_clean(supplements, nutrient_cols)
    if supp_clean.shape[0] == 0:
        return "Infeasible", None, None, infeasible_msg, None

    MIN_KG = 1.0 / 1000.0
    BIG_M_KG = 10.0

    model = pulp.LpProblem("Supplement_Optimierung", pulp.LpMinimize)

    x = {s: pulp.LpVariable(f"x_{i}", lowBound=0) for i, s in enumerate(supp_clean.index)}
    y = {s: pulp.LpVariable(f"y_{i}", cat="Binary") for i, s in enumerate(supp_clean.index)}

    model += pulp.lpSum(supp_clean.loc[s, "Preis (€) pro kg"] * x[s] for s in supp_clean.index)

    for s in supp_clean.index:
        model += x[s] <= BIG_M_KG * y[s]
        model += x[s] >= MIN_KG * y[s]

    for n in nutrient_cols:
        intake = pulp.lpSum(supp_clean.loc[s, n] * x[s] for s in supp_clean.index)
        if float(min_supp.get(n, 0)) > 0:
            model += intake >= float(min_supp[n])
        if pd.notna(max_supp.get(n, np.nan)):
            model += intake <= float(max_supp[n])

    model.solve(pulp.PULP_CBC_CMD(msg=False))

    status = pulp.LpStatus[model.status]
    if status != "Optimal":
        return status, None, None, infeasible_msg, None

    solution = pd.Series({s: x[s].value() for s in x if (x[s].value() or 0) > 1e-9}).sort_values(ascending=False)
    cost = float(pulp.value(model.objective))

    debug = {
        "nutrient_cols": nutrient_cols,
        "supp_clean": supp_clean,
        "base": base,
        "min_req": min_req,
        "max_req": max_req,
    }
    return status, solution, cost, infeasible_msg, debug

# ------------------------------------------------------------
# 6) UI – UPLOAD SECTION
# ------------------------------------------------------------
st.markdown("### 📥 Dateien hochladen")

constraints_raw = None
constraints_effective = None
supplements = None

ration_ok = False
supp_ok = False
excluded_supps_table = pd.DataFrame()

with st.expander("Dateien hochladen (aufklappen)", expanded=True):
    left, right = st.columns(2)

    # ----------------------------
    # LEFT: Rationsdatei
    # ----------------------------
    with left:
        with st.expander("Rationsdatei", expanded=True):
            st.markdown("<div class='upload-title'>Rationsdatei</div>", unsafe_allow_html=True)
            st.markdown("<div class='muted-hint'>(z.B. Ration Katze.xlsx)</div>", unsafe_allow_html=True)

            ration_file = st.file_uploader("Rationsdatei Upload", type="xlsx", label_visibility="collapsed")

            if ration_file:
                try:
                    constraints_raw = parse_constraints_excel(ration_file)
                    issues = validate_constraints_df(constraints_raw)

                    if issues:
                        st.warning(
                            "⚠️ **Warnung! Das Format scheint nicht zu passen:**\n\n"
                            + "\n".join(f"- {msg}" for msg in issues)
                        )
                        ration_ok = False
                    else:
                        ration_ok = True
                        st.markdown("<div class='okrow'>✅ Format passt!</div>", unsafe_allow_html=True)

                        st.markdown("#### 🧾 Nährstoff-Intervalle (Ration) – Anzeige & Bearbeitung")
                        st.markdown(
                            "<div class='caption-note'>"
                            "Min/Max/Grundnahrung sind editierbar. "
                            "Erst wenn du <b>fixierst</b>, werden die Werte für die Optimierung übernommen."
                            "</div>",
                            unsafe_allow_html=True
                        )

                        edit_df_default = constraints_to_edit_df(constraints_raw)
                        excel_signature = tuple(edit_df_default["Nährstoff"].tolist())

                        if "constraints_editor_nonce" not in st.session_state:
                            st.session_state["constraints_editor_nonce"] = 0

                        if "constraints_locked" not in st.session_state:
                            st.session_state["constraints_locked"] = False

                        if st.session_state.get("constraints_signature") != excel_signature:
                            st.session_state["constraints_signature"] = excel_signature
                            st.session_state["constraints_edit_df"] = edit_df_default.copy()
                            st.session_state["constraints_locked"] = False
                            st.session_state["constraints_effective_df"] = None
                            st.session_state["constraints_editor_nonce"] += 1

                        locked = bool(st.session_state.get("constraints_locked", False))
                        editor_key = f"constraints_editor_{st.session_state['constraints_editor_nonce']}"

                        # show editor WITHOUT the error column
                        display_cols = [
                            "Nährstoff",
                            "Tagesbedarf (Min)",
                            "Maximalwert (Max)",
                            "Grundnahrung",
                            "Bedarf nach Grundnahrung (Min-Base)",
                            "🗑 Löschen",
                        ]
                        edited_display = st.data_editor(
                            st.session_state["constraints_edit_df"][display_cols].copy(),
                            key=editor_key,
                            use_container_width=True,
                            num_rows="fixed",
                            hide_index=True,
                            disabled=locked,
                            column_config={
                                "Nährstoff": st.column_config.TextColumn(disabled=False),
                                "Tagesbedarf (Min)": st.column_config.NumberColumn(format="%.1f"),
                                "Maximalwert (Max)": st.column_config.NumberColumn(format="%.1f"),
                                "Grundnahrung": st.column_config.NumberColumn(format="%.1f"),
                                "Bedarf nach Grundnahrung (Min-Base)": st.column_config.NumberColumn(disabled=True, format="%.1f"),
                                "🗑 Löschen": st.column_config.CheckboxColumn("🗑 Löschen"),
                            },
                        )

                        # merge edits back into full df (keeps potential internal columns if later needed)
                        edited = st.session_state["constraints_edit_df"].copy()
                        for c in display_cols:
                            edited[c] = edited_display[c]

                        # --- sanitize
                        edited["Nährstoff"] = edited["Nährstoff"].astype(str).str.strip()
                        edited["Tagesbedarf (Min)"] = pd.to_numeric(edited["Tagesbedarf (Min)"], errors="coerce").fillna(0.0)
                        edited["Grundnahrung"] = pd.to_numeric(edited["Grundnahrung"], errors="coerce").fillna(0.0)
                        edited["Maximalwert (Max)"] = pd.to_numeric(edited["Maximalwert (Max)"], errors="coerce")
                        edited["Bedarf nach Grundnahrung (Min-Base)"] = (edited["Tagesbedarf (Min)"] - edited["Grundnahrung"]).clip(lower=0.0)
                        edited["🗑 Löschen"] = edited.get("🗑 Löschen", False).fillna(False).astype(bool)

                        # --- validation
                        max_present = edited["Maximalwert (Max)"].notna()
                        err_min_gt_max = max_present & (edited["Tagesbedarf (Min)"] > edited["Maximalwert (Max)"])
                        err_base_gt_max = max_present & (edited["Grundnahrung"] > edited["Maximalwert (Max)"])

                        def _build_err_msg(i: int) -> str:
                            parts = []
                            if bool(err_min_gt_max.iloc[i]):
                                parts.append("Min > Max")
                            if bool(err_base_gt_max.iloc[i]):
                                parts.append("Grundnahrung > Max")
                            return " | ".join(parts)

                        # keep error info internally (not shown in main table)
                        edited["⚠️ Fehler"] = [_build_err_msg(i) for i in range(len(edited))]

                        st.session_state["constraints_edit_df"] = edited

                        has_interval_errors = bool((err_min_gt_max | err_base_gt_max).any())
                        if has_interval_errors:
                            bad_rows = edited.loc[
                                (err_min_gt_max | err_base_gt_max),
                                ["Nährstoff", "Tagesbedarf (Min)", "Grundnahrung", "Maximalwert (Max)", "⚠️ Fehler"]
                            ]
                            st.error("❌ In der Tabelle gibt es ungültige Intervalle (Min/Grundnahrung > Max). Fixieren ist erst möglich, wenn das korrigiert ist.")
                            with st.expander(f"Details anzeigen ({len(bad_rows)} Zeile(n))"):
                                st.dataframe(bad_rows, use_container_width=True, hide_index=True)

                        st.markdown("<div class='nutrient-actions'>", unsafe_allow_html=True)

                        a1, a2 = st.columns([1, 1])

                        with a1:
                            if st.button(
                                "🗑 Ausgewählte Zeilen löschen",
                                type="secondary",
                                key="delete_rows_btn",
                                disabled=locked
                            ):
                                df_now = st.session_state["constraints_edit_df"].copy()
                                to_delete = df_now["🗑 Löschen"].fillna(False).astype(bool)
                                if to_delete.any():
                                    df_now = df_now.loc[~to_delete].copy()
                                    df_now["🗑 Löschen"] = False
                                    df_now["⚠️ Fehler"] = df_now.get("⚠️ Fehler", "").fillna("")
                                    st.session_state["constraints_edit_df"] = df_now.reset_index(drop=True)
                                    st.session_state["constraints_editor_nonce"] += 1
                                    st.success(f"{int(to_delete.sum())} Zeile(n) gelöscht.")
                                    st.rerun()
                                else:
                                    st.info("Keine Zeilen zum Löschen markiert.")

                        with a2:
                            if st.button(
                                "↩️ Alle Änderungen zurücksetzen",
                                key="reset_constraints_btn",
                                type="secondary",
                                disabled=locked
                            ):
                                st.session_state["constraints_edit_df"] = edit_df_default.copy()
                                st.session_state["constraints_locked"] = False
                                st.session_state["constraints_effective_df"] = None
                                st.session_state["constraints_editor_nonce"] += 1
                                st.success("Alles zurückgesetzt: gelöschte/hinzugefügte Zeilen + Änderungen wurden rückgängig gemacht.")
                                st.rerun()

                        with st.expander("➕ Nährstoff hinzufügen", expanded=False):
                            add_c1, add_c2, add_c3 = st.columns([2.2, 1.2, 1.2])
                            with add_c1:
                                new_nutrient_name = st.text_input(
                                    "Nährstoffname",
                                    value="",
                                    placeholder="z.B. Vit. E [mg]",
                                    disabled=locked,
                                    key="new_nutrient_name_input"
                                )
                            with add_c2:
                                new_min = st.number_input(
                                    "Tagesbedarf (Min)",
                                    value=0.0,
                                    step=0.1,
                                    format="%.1f",
                                    disabled=locked,
                                    key="new_nutrient_min_input"
                                )
                            with add_c3:
                                new_max = st.number_input(
                                    "Maximalwert (Max)",
                                    value=0.0,
                                    step=0.1,
                                    format="%.1f",
                                    disabled=locked,
                                    key="new_nutrient_max_input"
                                )

                            new_base = st.number_input(
                                "Grundnahrung",
                                value=0.0,
                                step=0.1,
                                format="%.1f",
                                disabled=locked,
                                key="new_nutrient_base_input"
                            )

                            if st.button(
                                "➕ Hinzufügen",
                                type="secondary",
                                key="add_nutrient_btn",
                                disabled=locked
                            ):
                                name_clean = (new_nutrient_name or "").strip()
                                if not name_clean:
                                    st.error("Bitte einen Nährstoffnamen eingeben.")
                                else:
                                    existing = set(st.session_state["constraints_edit_df"]["Nährstoff"].astype(str).str.strip())
                                    if name_clean in existing:
                                        st.warning("Diesen Nährstoff gibt es bereits in der Tabelle.")
                                    elif (float(new_max) > 0) and (float(new_min) > float(new_max)):
                                        st.error("Min darf nicht größer als Max sein.")
                                    elif (float(new_max) > 0) and (float(new_base) > float(new_max)):
                                        st.error("Grundnahrung darf nicht größer als Max sein.")
                                    else:
                                        new_row = pd.DataFrame([{
                                            "Nährstoff": name_clean,
                                            "Tagesbedarf (Min)": float(new_min),
                                            "Maximalwert (Max)": float(new_max) if new_max is not None else np.nan,
                                            "Grundnahrung": float(new_base),
                                            "Bedarf nach Grundnahrung (Min-Base)": max(0.0, float(new_min) - float(new_base)),
                                            "🗑 Löschen": False,
                                            "⚠️ Fehler": "",
                                        }])

                                        st.session_state["constraints_edit_df"] = pd.concat(
                                            [st.session_state["constraints_edit_df"], new_row],
                                            ignore_index=True
                                        )
                                        st.session_state["constraints_editor_nonce"] += 1
                                        st.success(f"Nährstoff '{name_clean}' hinzugefügt.")
                                        st.rerun()

                        st.markdown("<hr class='thin-sep'/>", unsafe_allow_html=True)

                        st.checkbox(
                            "🔏 Nährstoff Intervalle fixieren",
                            value=st.session_state.get("constraints_locked", False),
                            key="constraints_locked"
                        )

                        st.markdown("</div>", unsafe_allow_html=True)

                        if st.session_state.get("constraints_locked", False):
                            if has_interval_errors:
                                st.session_state["constraints_locked"] = False
                                st.session_state["constraints_effective_df"] = None
                                st.error("❌ Fixieren nicht möglich: Es gibt ungültige Intervalle (Min/Grundnahrung > Max). Bitte korrigieren.")
                                st.rerun()

                            names = st.session_state["constraints_edit_df"]["Nährstoff"].astype(str).str.strip()

                            if (names == "").any():
                                st.session_state["constraints_locked"] = False
                                st.session_state["constraints_effective_df"] = None
                                st.error("❌ Fixieren nicht möglich: Es gibt leere Nährstoffnamen. Bitte ausfüllen.")
                                st.rerun()

                            dup_mask = names.duplicated(keep=False)
                            if dup_mask.any():
                                dups = sorted(set(names[dup_mask].tolist()))
                                st.session_state["constraints_locked"] = False
                                st.session_state["constraints_effective_df"] = None
                                st.error(f"❌ Fixieren nicht möglich: Doppelte Nährstoffnamen: {', '.join(dups)}")
                                st.rerun()

                            st.session_state["constraints_effective_df"] = edit_df_to_constraints(
                                st.session_state["constraints_edit_df"].drop(columns=["🗑 Löschen", "⚠️ Fehler"], errors="ignore"),
                                constraints_raw
                            )
                            constraints_effective = st.session_state["constraints_effective_df"]
                            st.markdown(
                                "<div class='okrow'>✅ Intervalle fixiert – Werte werden für die Optimierung verwendet.</div>",
                                unsafe_allow_html=True
                            )
                        else:
                            constraints_effective = None
                            st.markdown(
                                "<div class='warnrow warnrow-after'>⏳ Noch nicht fixiert – Optimierung bleibt deaktiviert.</div>",
                                unsafe_allow_html=True
                            )

                except Exception as e:
                    st.error("❌ Excel-Format konnte nicht geparst werden.")
                    st.caption(f"Technischer Hinweis: {e}")
                    ration_ok = False

    # ----------------------------
    # RIGHT: Supplementdatenbank
    # ----------------------------
    with right:
        with st.expander("Supplementdatenbank", expanded=True):
            st.markdown("<div class='upload-title'>Supplementdatenbank</div>", unsafe_allow_html=True)
            st.markdown("<div class='muted-hint'>(z.B. Database Supplemente.xlsx)</div>", unsafe_allow_html=True)

            supp_file = st.file_uploader("Supplementdatenbank Upload", type="xlsx", label_visibility="collapsed")
            proceed_without_incomplete = False

            if supp_file:
                try:
                    supplements = parse_supplements_excel(supp_file)
                    issues = validate_supplements_df(supplements)
                    excluded_supps_table = get_excluded_supplements(supplements)

                    if issues:
                        st.warning(
                            "⚠️ **Warnung! Das Format scheint nicht zu passen:**\n\n"
                            + "\n".join(f"- {msg}" for msg in issues)
                        )

                    if not excluded_supps_table.empty:
                        st.info(
                            f"{len(excluded_supps_table)} Supplements haben keinen gültigen Preis "
                            "und werden automatisch ausgeschlossen."
                        )
                        with st.expander(f"Details anzeigen ({len(excluded_supps_table)} Zeilen)"):
                            st.dataframe(excluded_supps_table, use_container_width=True, hide_index=True)

                        proceed_without_incomplete = st.checkbox(
                            "⏭️ Ich möchte ohne den unvollständigen Supplements fortfahren.",
                            value=False,
                            key="proceed_checkbox"
                        )

                    supp_ok = (supplements is not None) and (proceed_without_incomplete or excluded_supps_table.empty)

                    if supp_ok and supplements is not None:
                        st.markdown("<div class='okrow'>✅ Format passt!</div>", unsafe_allow_html=True)
                    else:
                        st.markdown(
                            "<div class='warnrow'>⏳ Hinweis: Kästchen anklicken um unvollständige Supplemente zu ignorieren</div>",
                            unsafe_allow_html=True
                        )

                except Exception as e:
                    st.error("❌ Excel-Format konnte nicht gelesen werden.")
                    st.caption(f"Technischer Hinweis: {e}")
                    supp_ok = False

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
# Run optimization
# ---------------------------
can_run = status_ok and constraints_effective is not None and supplements is not None

st.markdown("### 📈 Optimierung")

with st.expander("Optimierung (aufklappen)", expanded=True):
    if st.button("🚀 Optimierung starten", disabled=not can_run):
        status_placeholder = st.empty()
        status_placeholder.markdown("<div class='warnrow'>⏳ Optimiere...</div>", unsafe_allow_html=True)

        try:
            status, solution, cost, infeasible_msg, debug = optimize_fast(constraints_effective, supplements)
        except Exception as e:
            status_placeholder.markdown(f"<div class='errorrow'>❌ Fehler: {e}</div>", unsafe_allow_html=True)
            st.exception(e)
            st.stop()

        if status != "Optimal" or solution is None or debug is None:
            status_placeholder.markdown("<div class='errorrow'>❌ Keine optimale Lösung gefunden.</div>", unsafe_allow_html=True)
            if infeasible_msg:
                st.info("Diagnose / Hinweis:")
                st.json(infeasible_msg)
            st.stop()

        status_placeholder.markdown("<div class='okrow'>✅ Fertig.</div>", unsafe_allow_html=True)

        st.subheader("Ergebnis")

        n_supp = int(len(solution))

        k1, k2 = st.columns(2)
        with k1:
            st.markdown(
                f"""
                <div class="kpi-card" style="background: rgba(46,184,92,0.12); border: 1px solid rgba(46,184,92,0.30);">
                    <div class="kpi-title">💰 Minimale Kosten</div>
                    <div class="kpi-value">{cost:.4f} €</div>
                </div>
                """,
                unsafe_allow_html=True
            )
        with k2:
            st.markdown(
                f"""
                <div class="kpi-card">
                    <div class="kpi-title">💊 Anzahl Supplements</div>
                    <div class="kpi-value">{n_supp}</div>
                </div>
                """,
                unsafe_allow_html=True
            )

        st.image("static/pikachu.jpg", width=220)
