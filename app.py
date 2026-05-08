# ============================================================
# Animal Supplement Optimierer (Streamlit App)
#
# Features:
# - Upload + Parsing + Validation (Ration + Supplement-DB)
# - Editierbare Nährstoff-Intervalle + Fixieren (Lock)
# - Nährstoff-Matching (Auto/Fuzzy/Manual) + Skip fehlender Nährstoffe
# - Optimierung (PuLP CBC) mit 1g Mindestmenge pro gewähltem Supplement
# - Diagnose bei Infeasible + Slack-Debug
# - Ergebnis: g/Tag + Haltbarkeit/Nachbestellen + Nährstoff-Check
# - Beiträge je Supplement × Nährstoff (Wide + Long + Totals)
# - Ergebnis bleibt erhalten bei UI-Änderungen (kein erneutes Optimieren nötig)
# ============================================================

import numpy as np
import pandas as pd
import pulp
import streamlit as st
import re
import difflib
import unicodedata

# ------------------------------------------------------------
# 0) PAGE CONFIG
# ------------------------------------------------------------
st.set_page_config(page_title="Animal Nutrition Optimizer", layout="wide")

# ------------------------------------------------------------
# 0b) GLOBAL CSS
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
    st.title("🐾💊 Animal Supplement Optimizer")
with col_right:
    try:
        st.image("static/Vetmedlogo.png", width="stretch")
    except Exception:
        pass
    st.markdown("<div style='text-align: right;'>Univ.-Prof. Dr. Qendrim Zebeli</div>", unsafe_allow_html=True)

st.write(
    "Upload the two Excel files. The files are first converted into a standard format and then validated for correctness."
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
        issues.append("Required rows are missing after parsing (Tagesbedarf/Maximaler_Wert/Grundnahrung).")
    if constraints.shape[1] == 0:
        issues.append("No nutrient columns detected after parsing.")
    if constraints.isna().any().any():
        issues.append("NaN values detected after parsing.")
    try:
        min_vals = pd.to_numeric(constraints.loc["Tagesbedarf"], errors="coerce")
        max_vals = pd.to_numeric(constraints.loc["Maximaler_Wert"], errors="coerce")
        base_vals = pd.to_numeric(constraints.loc["Grundnahrung"], errors="coerce")
        if min_vals.isna().any() or max_vals.isna().any() or base_vals.isna().any():
            issues.append("Non-numeric values found in Tagesbedarf/Maximaler_Wert/Grundnahrung.")
        if (min_vals < 0).any():
            issues.append("Negative requirement values detected.")
        if (min_vals > max_vals).any():
            issues.append("Daily requirement exceeds maximum value for at least one nutrient.")
    except Exception:
        issues.append("Values could not be interpreted as numeric.")
    return issues



def validate_supplements_df(supplements: pd.DataFrame):
    issues = []
    required_cols = {"Futtermittel", "Preis (€) pro kg"}
    missing = required_cols - set(supplements.columns)
    if missing:
        issues.append(f"Required columns are missing after parsing: {', '.join(sorted(missing))}.")
    if supplements.shape[0] == 0:
        issues.append("No rows detected after parsing.")
    if "Preis (€) pro kg" in supplements.columns:
        prices = pd.to_numeric(supplements["Preis (€) pro kg"], errors="coerce")
        if prices.isna().any():
            issues.append("Non-numeric or missing prices detected (these rows may be ignored).")
        if (prices < 0).any():
            issues.append("Negative prices detected.")
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
    excluded["Ausschlussgrund"] = "No valid price provided"
    excluded = excluded.rename(columns={"_Excel_Zeile": "Excel row","Futtermittel": "Supplement","Preis (€) pro kg":"Price (€) per kg","Ausschlussgrund":"Exclusion reason"})
    excluded = excluded.sort_values(by=["Excel row", "Supplement"], ascending=True)
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
# 6) Supplement Table -> EDITABLE TABLE
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
    min_all  = pd.to_numeric(constraints_effective.loc["Tagesbedarf", nutrients_from_constraints], errors="coerce").fillna(0.0)
    max_all  = pd.to_numeric(constraints_effective.loc["Maximaler_Wert", nutrients_from_constraints], errors="coerce")
    min_supp_all = (min_all - base_all).clip(lower=0.0)

    missing_required = [n for n in nutrients_from_constraints if (min_supp_all.get(n, 0.0) > 0) and (n not in available)]
    if missing_required:
        infeasible_msg = {
            "Missing nutritions in Supplement database": missing_required,
            "Note": "For these nutrients, there is still a remaining requirement after the base-diet (>0), but no corresponding column exists in the supplement database."
        }
        return "Infeasible", None, None, infeasible_msg, {"reason": "missing_required_cols"}

    nutrient_cols = [n for n in nutrients_from_constraints if n in available]

    base    = base_all.reindex(nutrient_cols).fillna(0.0)
    min_req = min_all.reindex(nutrient_cols).fillna(0.0)
    max_req = max_all.reindex(nutrient_cols)

    min_supp = (min_req - base).clip(lower=0.0)
    max_supp = (max_req - base)

    infeasible_base_over_max = max_supp[max_supp < 0]
    infeasible_msg = infeasible_base_over_max.to_dict() if len(infeasible_base_over_max) else None

    supp_clean = build_supp_clean(supplements, nutrient_cols)
    if supp_clean.shape[0] == 0:
        return "Infeasible", None, None, {"Note": "After cleaning, no supplements with nutrient content remain."}, {"reason": "empty_supp_clean"}

    MIN_KG = 1.0 / 1000.0
    BIG_M_KG = 10.0

    def _diagnose():
        diag_rows = []
        for n in nutrient_cols:
            coeff = supp_clean[n].astype(float)
            pos_sum = float(np.maximum(coeff.values, 0.0).sum())
            max_possible = BIG_M_KG * pos_sum
            min_needed = float(min_supp.get(n, 0.0))

            max_allowed = max_supp.get(n, np.nan)
            max_allowed = float(max_allowed) if pd.notna(max_allowed) else np.nan

            has_positive_source = bool((coeff > 0).any())

            top_sources = coeff.sort_values(ascending=False).head(8)
            top_sources_dict = {k: float(v) for k, v in top_sources.items() if float(v) != 0.0}

            one_g_effect = (top_sources * MIN_KG).head(8)
            one_g_effect_dict = {k: float(v) for k, v in one_g_effect.items() if float(v) != 0.0}

            reason_flags = []
            if min_needed > 0 and (not has_positive_source):
                reason_flags.append("Min > 0 but no positive source available (all coefficients ≤ 0)")
            if min_needed > max_possible + 1e-12:
                reason_flags.append("Min exceeds the maximum achievable value (BIG_M limit)")
            if pd.notna(max_allowed) and max_allowed < 0:
                reason_flags.append("Base-diet exceeds Max (Max-Base < 0)")

            diag_rows.append({
                "Nutrient": n,
                "Min_After_Base_Diet": min_needed,
                "Max_After_Base_Diet": (max_allowed if pd.notna(max_allowed) else np.nan),
                "Max_Achievable_Rough": max_possible,
                "Has_Positive_Source": has_positive_source,
                "Flags": " | ".join(reason_flags),
                "Top_Sources_coeff_per_kg": top_sources_dict,
                "1g_Effect_TopSources": one_g_effect_dict,
            })

        diag_df = pd.DataFrame(diag_rows)
        likely = diag_df[
            (diag_df["Flags"].astype(str).str.len() > 0)
            | (diag_df["Min_After_Base_Diet"] > diag_df["Max_Achievable_Rough"] + 1e-12)
        ].copy()

        return {
            "diag_df": diag_df,
            "likely_problem_nutrients": likely.sort_values(
                by=["Min_After_Base_Diet"], ascending=False
            ).reset_index(drop=True),
            "MIN_KG": MIN_KG,
            "BIG_M_KG": BIG_M_KG,
            "nutrient_cols": nutrient_cols,
            "supp_clean_shape": tuple(supp_clean.shape),
        }

    if infeasible_msg:
        dbg = {
            "nutrient_cols": nutrient_cols,
            "supp_clean": supp_clean,
            "base": base,
            "min_req": min_req,
            "max_req": max_req,
            "diagnose": _diagnose(),
        }
        return "Infeasible", None, None, {"Base-Diet over Max": infeasible_msg}, dbg

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
        dbg = {
            "nutrient_cols": nutrient_cols,
            "supp_clean": supp_clean,
            "base": base,
            "min_req": min_req,
            "max_req": max_req,
            "diagnose": _diagnose(),
            "solver_status": status,
        }
        return status, None, None, infeasible_msg, dbg

    solution = pd.Series({s: x[s].value() for s in x if (x[s].value() or 0) > 1e-9}).sort_values(ascending=False)
    cost = float(pulp.value(model.objective))

    debug = {
        "nutrient_cols": nutrient_cols,
        "supp_clean": supp_clean,
        "base": base,
        "min_req": min_req,
        "max_req": max_req,
        "diagnose": _diagnose(),
    }
    return status, solution, cost, infeasible_msg, debug


def optimize_with_slacks(constraints_effective: pd.DataFrame, supplements: pd.DataFrame, penalty=1e6):
    nutrients = [c for c in constraints_effective.columns if "Verhältnis" not in str(c)]
    available = infer_available_nutrients_from_supplements(supplements)

    base = pd.to_numeric(constraints_effective.loc["Grundnahrung", nutrients], errors="coerce").fillna(0.0)
    minv = pd.to_numeric(constraints_effective.loc["Tagesbedarf", nutrients], errors="coerce").fillna(0.0)
    maxv = pd.to_numeric(constraints_effective.loc["Maximaler_Wert", nutrients], errors="coerce")

    min_supp = (minv - base).clip(lower=0.0)
    max_supp = (maxv - base)

    nutrient_cols = [n for n in nutrients if n in available]
    supp_clean = build_supp_clean(supplements, nutrient_cols)

    MIN_KG = 1.0 / 1000.0
    BIG_M_KG = 10.0

    model = pulp.LpProblem("Debug_Slack_Model", pulp.LpMinimize)

    x = {s: pulp.LpVariable(f"x_{i}", lowBound=0) for i, s in enumerate(supp_clean.index)}
    y = {s: pulp.LpVariable(f"y_{i}", cat="Binary") for i, s in enumerate(supp_clean.index)}

    s_min = {n: pulp.LpVariable(f"smin_{i}", lowBound=0) for i, n in enumerate(nutrient_cols)}
    s_max = {n: pulp.LpVariable(f"smax_{i}", lowBound=0) for i, n in enumerate(nutrient_cols)}

    cost_expr = pulp.lpSum(supp_clean.loc[s, "Preis (€) pro kg"] * x[s] for s in supp_clean.index)
    slack_expr = pulp.lpSum(s_min[n] + s_max[n] for n in nutrient_cols)
    model += penalty * slack_expr + cost_expr

    for s in supp_clean.index:
        model += x[s] <= BIG_M_KG * y[s]
        model += x[s] >= MIN_KG * y[s]

    for n in nutrient_cols:
        intake = pulp.lpSum(supp_clean.loc[s, n] * x[s] for s in supp_clean.index)
        model += intake + s_min[n] >= float(min_supp.get(n, 0.0))
        if pd.notna(max_supp.get(n)):
            model += intake - s_max[n] <= float(max_supp[n])

    model.solve(pulp.PULP_CBC_CMD(msg=False))

    rows = []
    for n in nutrient_cols:
        rows.append({
            "Nutrient": n,
            "Slack_Min": float(s_min[n].value() or 0),
            "Slack_Max": float(s_max[n].value() or 0),
        })

    slack_df = pd.DataFrame(rows).sort_values(["Slack_Min", "Slack_Max"], ascending=False)
    return slack_df

# ------------------------------------------------------------
# 5c) Matching helpers
# ------------------------------------------------------------
def normalize_name(s: str) -> str:
    s = str(s or "").strip().lower()
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = s.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"[^\w\s\[\]\(\)\-\/\+\.]", "", s)
    return s.strip()

def build_initial_mapping_and_status(ration_nutrients: list[str], supp_names: list[str]):
    supp_norm_map = {normalize_name(s): s for s in supp_names}
    mapping, status, mode = {}, {}, {}

    for r in ration_nutrients:
        rn = normalize_name(r)
        if rn in supp_norm_map:
            mapping[r] = supp_norm_map[rn]
            status[r] = "exact"
            mode[r] = "auto"
        else:
            norm_list = list(supp_norm_map.keys())
            close = difflib.get_close_matches(rn, norm_list, n=1, cutoff=0.78)
            if close:
                mapping[r] = supp_norm_map[close[0]]
                status[r] = "fuzzy"
                mode[r] = "auto"
            else:
                mapping[r] = None
                status[r] = "missing"
                mode[r] = "auto"
    return mapping, status, mode

def apply_mapping_to_constraints(constraints_effective: pd.DataFrame, mapping: dict) -> pd.DataFrame:
    cols = list(constraints_effective.columns)
    rename_map = {}
    keep_cols = []
    for c in cols:
        if c in mapping:
            target = mapping.get(c)
            if target is None:
                continue
            rename_map[c] = target
            keep_cols.append(c)
        else:
            keep_cols.append(c)

    out = constraints_effective[keep_cols].copy()
    out = out.rename(columns=rename_map)

    if out.columns.duplicated().any():
        out = out.groupby(level=0, axis=1).max()
    return out

# ------------------------------------------------------------
# 6) UI – UPLOAD SECTION
# ------------------------------------------------------------
st.markdown("### 📥 Upload and Customize Data")

constraints_raw = None
constraints_effective = None
supplements = None

ration_ok = False
supp_ok = False
excluded_supps_table = pd.DataFrame()
status_ok = False

with st.expander("📥 Upload and Customize Data (expand)", expanded=True):
    left, right = st.columns(2)

    # ----------------------------
    # LEFT: Rationsdatei
    # ----------------------------
    with left:
        with st.expander("Nutrient Requirement", expanded=True):
            st.markdown("<div class='upload-title'>Nutrient Requirement file</div>", unsafe_allow_html=True)
            st.markdown("<div class='muted-hint'>(e.g. Ration Katze.xlsx)</div>", unsafe_allow_html=True)

            ration_file = st.file_uploader("Rationsdatei Upload", type="xlsx", label_visibility="collapsed")

            if ration_file:
                try:
                    constraints_raw = parse_constraints_excel(ration_file)
                    issues = validate_constraints_df(constraints_raw)

                    if issues:
                        st.warning(
                            "⚠️ **Warning! The format does not appear to be correct:**\n\n"
                            + "\n".join(f"- {msg}" for msg in issues)
                        )
                        ration_ok = False
                    else:
                        ration_ok = True
                        st.markdown("<div class='okrow'>✅ Format looks good!</div>", unsafe_allow_html=True)

                        st.markdown("#### 🧾 Nutrient Intervals – View & Edit")
                        st.markdown(
                            "<div class='caption-note'>"
                            "Min/Max/Base are editable. "
                            "The values will only be used for optimization once you <b>fix</b> them. \n\n All requirements are expressed as daily doses "
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

                            st.session_state["nutrient_mapping"] = None
                            st.session_state["nutrient_mapping_status"] = None
                            st.session_state["nutrient_mapping_mode"] = None
                            st.session_state["nutrient_mapping_signature"] = None
                            st.session_state["skip_missing_nutrients"] = False

                        locked = bool(st.session_state.get("constraints_locked", False))
                        editor_key = f"constraints_editor_{st.session_state['constraints_editor_nonce']}"

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
                                "Nährstoff": st.column_config.TextColumn("Nutrition",disabled=False),
                                "Tagesbedarf (Min)": st.column_config.NumberColumn("Requirement (Min)",format="%.1f"),
                                "Maximalwert (Max)": st.column_config.NumberColumn("Requirement (Max)",format="%.1f"),
                                "Grundnahrung": st.column_config.NumberColumn("Base-Diet",format="%.1f"),
                                "Bedarf nach Grundnahrung (Min-Base)": st.column_config.NumberColumn("Requirement after Base-Diet",disabled=True, format="%.1f"),
                                "🗑 Löschen": st.column_config.CheckboxColumn("🗑 Delete"),
                            },
                        )

                        edited = st.session_state["constraints_edit_df"].copy()
                        for c in display_cols:
                            edited[c] = edited_display[c]

                        edited["Nährstoff"] = edited["Nährstoff"].astype(str).str.strip()
                        edited["Tagesbedarf (Min)"] = pd.to_numeric(edited["Tagesbedarf (Min)"], errors="coerce").fillna(0.0)
                        edited["Grundnahrung"] = pd.to_numeric(edited["Grundnahrung"], errors="coerce").fillna(0.0)
                        edited["Maximalwert (Max)"] = pd.to_numeric(edited["Maximalwert (Max)"], errors="coerce")
                        edited["Bedarf nach Grundnahrung (Min-Base)"] = (edited["Tagesbedarf (Min)"] - edited["Grundnahrung"]).clip(lower=0.0)
                        edited["🗑 Löschen"] = edited.get("🗑 Löschen", False).fillna(False).astype(bool)

                        max_present = edited["Maximalwert (Max)"].notna()
                        err_min_gt_max = max_present & (edited["Tagesbedarf (Min)"] > edited["Maximalwert (Max)"])
                        err_base_gt_max = max_present & (edited["Grundnahrung"] > edited["Maximalwert (Max)"])

                        def _build_err_msg(i: int) -> str:
                            parts = []
                            if bool(err_min_gt_max.iloc[i]):
                                parts.append("Min > Max")
                            if bool(err_base_gt_max.iloc[i]):
                                parts.append("Base Diet > Max")
                            return " | ".join(parts)

                        edited["⚠️ Fehler"] = [_build_err_msg(i) for i in range(len(edited))]
                        st.session_state["constraints_edit_df"] = edited

                        has_interval_errors = bool((err_min_gt_max | err_base_gt_max).any())
                        if has_interval_errors:
                            bad_rows = edited.loc[
                                (err_min_gt_max | err_base_gt_max),
                                ["Nährstoff", "Tagesbedarf (Min)", "Grundnahrung", "Maximalwert (Max)", "⚠️ Fehler"]
                            ]
                            st.error("❌ There are invalid intervals in the table (Min and/or Base Diet > Max). Fixing is only possible once this has been corrected.")
                            with st.expander(f"Show details ({len(bad_rows)} rows)"):
                                st.dataframe(bad_rows, use_container_width=True, hide_index=True)

                        st.markdown("<div class='nutrient-actions'>", unsafe_allow_html=True)

                        a1, a2 = st.columns([1, 1])

                        with a1:
                            if st.button("🗑 Delete selected rows", type="secondary", key="delete_rows_btn", disabled=locked):
                                df_now = st.session_state["constraints_edit_df"].copy()
                                to_delete = df_now["🗑 Löschen"].fillna(False).astype(bool)
                                if to_delete.any():
                                    df_now = df_now.loc[~to_delete].copy()
                                    df_now["🗑 Löschen"] = False
                                    df_now["⚠️ Fehler"] = df_now.get("⚠️ Fehler", "").fillna("")
                                    st.session_state["constraints_edit_df"] = df_now.reset_index(drop=True)
                                    st.session_state["constraints_editor_nonce"] += 1

                                    st.session_state["nutrient_mapping"] = None
                                    st.session_state["nutrient_mapping_status"] = None
                                    st.session_state["nutrient_mapping_mode"] = None
                                    st.session_state["nutrient_mapping_signature"] = None
                                    st.session_state["skip_missing_nutrients"] = False

                                    st.success(f"{int(to_delete.sum())} row(s) deleted.")
                                    st.rerun()
                                else:
                                    st.info("No rows selected for deletion.")

                        with a2:
                            if st.button("↩️ Reset changes", key="reset_constraints_btn", type="secondary", disabled=locked):
                                st.session_state["constraints_edit_df"] = edit_df_default.copy()
                                st.session_state["constraints_locked"] = False
                                st.session_state["constraints_effective_df"] = None
                                st.session_state["constraints_editor_nonce"] += 1

                                st.session_state["nutrient_mapping"] = None
                                st.session_state["nutrient_mapping_status"] = None
                                st.session_state["nutrient_mapping_mode"] = None
                                st.session_state["nutrient_mapping_signature"] = None
                                st.session_state["skip_missing_nutrients"] = False

                                st.success("Everything has been reset: deleted/added rows and all changes have been reverted.")
                                st.rerun()

                        with st.expander("➕ Add new nutrient", expanded=False):
                            add_c1, add_c2, add_c3 = st.columns([2.2, 1.2, 1.2])
                            with add_c1:
                                new_nutrient_name = st.text_input(
                                    "Nutrient name",
                                    value="",
                                    placeholder="z.B. Vit. E [mg]",
                                    disabled=locked,
                                    key="new_nutrient_name_input"
                                )
                            with add_c2:
                                new_min = st.number_input(
                                    "Daily Requirement (Min)",
                                    value=0.0,
                                    step=0.1,
                                    format="%.1f",
                                    disabled=locked,
                                    key="new_nutrient_min_input"
                                )
                            with add_c3:
                                new_max = st.number_input(
                                    "Daily Requirement (Max)",
                                    value=0.0,
                                    step=0.1,
                                    format="%.1f",
                                    disabled=locked,
                                    key="new_nutrient_max_input"
                                )

                            new_base = st.number_input(
                                "Base Diet",
                                value=0.0,
                                step=0.1,
                                format="%.1f",
                                disabled=locked,
                                key="new_nutrient_base_input"
                            )

                            if st.button("➕ Add", type="secondary", key="add_nutrient_btn", disabled=locked):
                                name_clean = (new_nutrient_name or "").strip()
                                if not name_clean:
                                    st.error("Please enter a nutrient name.")
                                else:
                                    existing = set(st.session_state["constraints_edit_df"]["Nährstoff"].astype(str).str.strip())
                                    if name_clean in existing:
                                        st.warning("This nutrient already exists in the table.")
                                    elif (float(new_max) > 0) and (float(new_min) > float(new_max)):
                                        st.error("Min must not be greater than Max.")
                                    elif (float(new_max) > 0) and (float(new_base) > float(new_max)):
                                        st.error("Base diet must not exceed Max.")
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

                                        st.session_state["nutrient_mapping"] = None
                                        st.session_state["nutrient_mapping_status"] = None
                                        st.session_state["nutrient_mapping_mode"] = None
                                        st.session_state["nutrient_mapping_signature"] = None
                                        st.session_state["skip_missing_nutrients"] = False

                                        st.success(f"Nutrition '{name_clean}' added.")
                                        st.rerun()

                        st.markdown("<hr class='thin-sep'/>", unsafe_allow_html=True)

                        st.checkbox(
                            "🔏 Fix nutrient intervals",
                            value=st.session_state.get("constraints_locked", False),
                            key="constraints_locked"
                        )

                        st.markdown("</div>", unsafe_allow_html=True)

                        if st.session_state.get("constraints_locked", False):
                            if has_interval_errors:
                                st.session_state["constraints_locked"] = False
                                st.session_state["constraints_effective_df"] = None
                                st.error("❌ Cannot fix: invalid intervals detected (Min and/or Base Diet > Max). Please correct it/them")
                                st.rerun()

                            names = st.session_state["constraints_edit_df"]["Nährstoff"].astype(str).str.strip()
                            if (names == "").any():
                                st.session_state["constraints_locked"] = False
                                st.session_state["constraints_effective_df"] = None
                                st.error("❌ Cannot fix: there are empty nutrient names. Please fill them in.")
                                st.rerun()

                            dup_mask = names.duplicated(keep=False)
                            if dup_mask.any():
                                dups = sorted(set(names[dup_mask].tolist()))
                                st.session_state["constraints_locked"] = False
                                st.session_state["constraints_effective_df"] = None
                                st.error(f"❌ Fixing not possible: duplicate nutrient names detected: {', '.join(dups)}")
                                st.rerun()

                            st.session_state["constraints_effective_df"] = edit_df_to_constraints(
                                st.session_state["constraints_edit_df"].drop(columns=["🗑 Löschen", "⚠️ Fehler"], errors="ignore"),
                                constraints_raw
                            )
                            constraints_effective = st.session_state["constraints_effective_df"]
                            st.markdown("<div class='okrow'>✅ Intervals fixed – values are used for optimization.</div>", unsafe_allow_html=True)
                        else:
                            constraints_effective = None
                            st.markdown("<div class='warnrow warnrow-after'>⏳ Not fixed yet – optimization remains disabled.</div>", unsafe_allow_html=True)

                except Exception as e:
                    st.error("❌ The Excel format could not be parsed.")
                    st.caption(f"Technical notice: {e}")
                    ration_ok = False

    # ----------------------------
    # RIGHT: Supplementdatenbank
    # ----------------------------
    with right:
        with st.expander("Supplement database", expanded=True):
            st.markdown("<div class='upload-title'>Supplement database</div>", unsafe_allow_html=True)
            st.markdown("<div class='muted-hint'>(e.g. Database Supplemente.xlsx)</div>", unsafe_allow_html=True)

            supp_file = st.file_uploader("Supplementdatenbank Upload", type="xlsx", label_visibility="collapsed")
            proceed_without_incomplete = False

            if supp_file:
                try:
                    supplements = parse_supplements_excel(supp_file)
                    issues = validate_supplements_df(supplements)
                    excluded_supps_table = get_excluded_supplements(supplements)

                    if issues:
                        st.warning("⚠️ **Warning! The format does not appear to be correct:**\n\n" + "\n".join(f"- {msg}" for msg in issues))

                    if not excluded_supps_table.empty:
                        st.info(f"{len(excluded_supps_table)} supplements supplements have no valid price and will be automatically excluded.")
                        with st.expander(f"Show details ({len(excluded_supps_table)} rows)"):
                            st.dataframe(excluded_supps_table, use_container_width=True, hide_index=True)

                        proceed_without_incomplete = st.checkbox(
                            "⏭️ I want to continue without the incomplete supplements.",
                            value=False,
                            key="proceed_checkbox"
                        )

                    supp_ok = (supplements is not None) and (proceed_without_incomplete or excluded_supps_table.empty)

                    if supp_ok and supplements is not None:
                        st.markdown("<div class='okrow'>✅ Format looks good!</div>", unsafe_allow_html=True)
                    else:
                        st.markdown("<div class='warnrow'>⏳ Note: Select the checkbox to ignore incomplete supplements</div>", unsafe_allow_html=True)

                except Exception as e:
                    st.error("❌ The Excel format could not be read.")
                    st.caption(f"Technical notice: {e}")
                    supp_ok = False

    status_ok = ration_ok and supp_ok
    status_icon = "✅" if status_ok else "⏳"
    st.markdown(
        f"""
        <div class='statusline' style='font-size:1.8rem;'>
            Data Format <span style='font-size:1.8rem; margin-left:0.2rem;'>{status_icon}</span>
        </div>
        """,
        unsafe_allow_html=True
    )

# ------------------------------------------------------------
# 6b) DATEN KONTROLLE 🛂
# ------------------------------------------------------------
st.markdown("### 🛂 Data Check")

with st.expander("🛂 Data Check (expand)", expanded=True):
    if status_ok and ("constraints_edit_df" in st.session_state) and (supplements is not None):
        st.markdown("#### 🔁 Nutrition-Matching (Nutrient Requirement ↔ Supplement database)")
        st.markdown(
            "<div class='caption-note'>"
            "You only need to manually assign nutrients that could not be clearly identified automatically. "
            "Nutrients can also be ignored."
            "</div>",
            unsafe_allow_html=True
        )

        ration_nutrients_now = st.session_state["constraints_edit_df"]["Nährstoff"].astype(str).str.strip().tolist()
        ration_sig_now = tuple(ration_nutrients_now)
        supp_names_sorted = sorted(list(infer_available_nutrients_from_supplements(supplements)))

        if ("nutrient_mapping" not in st.session_state) or (st.session_state.get("nutrient_mapping") is None) \
           or (st.session_state.get("nutrient_mapping_signature") != ration_sig_now):
            m, s, mode = build_initial_mapping_and_status(ration_nutrients_now, supp_names_sorted)
            st.session_state["nutrient_mapping"] = m
            st.session_state["nutrient_mapping_status"] = s
            st.session_state["nutrient_mapping_mode"] = mode
            st.session_state["nutrient_mapping_signature"] = ration_sig_now

        mapping = st.session_state["nutrient_mapping"] or {}
        mapping_status = st.session_state.get("nutrient_mapping_status", {}) or {}
        mapping_mode = st.session_state.get("nutrient_mapping_mode", {}) or {}

        needs_manual = [
            r for r in ration_nutrients_now
            if (mapping_mode.get(r) == "manual") or (mapping_status.get(r) in {"missing", "fuzzy"})
        ]

        used = set(v for v in mapping.values() if v is not None)

        def _safe_key(s: str) -> str:
            return re.sub(r"[^a-zA-Z0-9_]", "_", s)[:80]

        if len(needs_manual) == 0:
            st.markdown("<div class='okrow'>✅ All nutrients were matched automatically and unambiguously.</div>", unsafe_allow_html=True)
        else:
            st.markdown("<div class='warnrow'>⚠️ The following nutrients were not matched clearly and require manual selection:</div>", unsafe_allow_html=True)

            m_left, m_right = st.columns([1, 1])
            mid = int(np.ceil(len(needs_manual) / 2))
            left_list = needs_manual[:mid]
            right_list = needs_manual[mid:]

            def render_match_column(names: list[str], col_container):
                with col_container:
                    for r in names:
                        current = mapping.get(r, None)

                        opts = ["(ignore)"]
                        for sname in supp_names_sorted:
                            if (sname not in used) or (current == sname):
                                opts.append(sname)

                        sugg = difflib.get_close_matches(
                            normalize_name(r),
                            [normalize_name(x) for x in supp_names_sorted],
                            n=5,
                            cutoff=0.75
                        )
                        norm_to_real = {normalize_name(x): x for x in supp_names_sorted}
                        sugg_real = []
                        for sn in sugg:
                            real = norm_to_real.get(sn)
                            if real and real in opts and real not in sugg_real:
                                sugg_real.append(real)

                        rest = [x for x in opts[1:] if x not in sugg_real]
                        opts_final = ["(ignore)"] + sugg_real + rest

                        if current is None:
                            idx = 0
                        else:
                            try:
                                idx = opts_final.index(current)
                            except ValueError:
                                idx = 0

                        label_hint = " (no match)" if mapping_status.get(r) == "missing" else " (unclear match)"
                        choice = st.selectbox(
                            f"**{r}** →{label_hint}",
                            options=opts_final,
                            index=idx,
                            key=f"map_{_safe_key(r)}",
                        )

                        if current is not None:
                            used.discard(current)

                        if choice == "(ignore)":
                            mapping[r] = None
                            mapping_mode[r] = "manual"
                            mapping_status[r] = "missing"
                        else:
                            mapping[r] = choice
                            used.add(choice)
                            mapping_mode[r] = "manual"
                            mapping_status[r] = "manual"

            render_match_column(left_list, m_left)
            render_match_column(right_list, m_right)

            st.session_state["nutrient_mapping"] = mapping
            st.session_state["nutrient_mapping_mode"] = mapping_mode
            st.session_state["nutrient_mapping_status"] = mapping_status

        rows = []
        for r in ration_nutrients_now:
            v = mapping.get(r, None)
            if st.session_state.get("skip_missing_nutrients", False) and (v is None):
                st_val = "skipped"
            else:
                if v is None:
                    st_val = "missing"
                else:
                    if mapping_mode.get(r) == "manual":
                        st_val = "manual"
                    else:
                        st_val = mapping_status.get(r, "missing")

            rows.append({"Ration Nutrient": r, "Supplement Column": (v or ""), "Status": st_val})
        mapping_df = pd.DataFrame(rows)

        def compute_needed_and_status(_constraints_effective: pd.DataFrame, _mapping: dict, _skip_missing: bool):
            mapping_ok_local = True
            missing_needed_local, skipped_missing_local = [], []

            if _constraints_effective is None:
                return None, mapping_ok_local, missing_needed_local, skipped_missing_local

            eff_cols_local = list(_constraints_effective.columns)
            base_eff_local = pd.to_numeric(_constraints_effective.loc["Grundnahrung", eff_cols_local], errors="coerce").fillna(0.0)
            min_eff_local = pd.to_numeric(_constraints_effective.loc["Tagesbedarf", eff_cols_local], errors="coerce").fillna(0.0)
            needed_local = (min_eff_local - base_eff_local).clip(lower=0.0)
            needed_cols_local = [c for c in eff_cols_local if float(needed_local.get(c, 0.0)) > 0.0]

            for n in needed_cols_local:
                mapped_to = _mapping.get(n, None)
                if mapped_to is None:
                    if _skip_missing:
                        skipped_missing_local.append(n)
                    else:
                        mapping_ok_local = False
                        missing_needed_local.append(n)

            return needed_cols_local, mapping_ok_local, missing_needed_local, skipped_missing_local

        if constraints_effective is None:
            st.markdown("<div class='warnrow'>⏳ Matching for optimization is only checked once you have fixed the intervals.</div>", unsafe_allow_html=True)
        else:
            skip_missing_default = bool(st.session_state.get("skip_missing_nutrients", False))
            st.session_state["skip_missing_nutrients"] = st.checkbox(
                "⏭️ I want to skip missing (unassigned) nutrients and optimize without them.",
                value=skip_missing_default,
                key="skip_missing_nutrients_checkbox"
            )

            skip_missing_now = bool(st.session_state.get("skip_missing_nutrients", False))
            _, mapping_ok, missing_needed, skipped_missing = compute_needed_and_status(constraints_effective, mapping, skip_missing_now)

            if skip_missing_now:
                if skipped_missing:
                    st.markdown("<div class='warnrow'>⚠️ These nutrients will be removed from the optimization (skipped):</div>", unsafe_allow_html=True)
                    st.json(sorted(skipped_missing))
                else:
                    st.markdown("<div class='okrow'>✅ There are no missing required nutrients — skipping has no effect at the moment.</div>", unsafe_allow_html=True)
                st.markdown("<br><br><br>", unsafe_allow_html=True)

            if mapping_ok or skip_missing_now:
                st.markdown("<div class='okrow'>✅ Matching OK — optimization can start.</div>", unsafe_allow_html=True)
            else:
                st.markdown("<div class='errorrow'>❌ \"Matching incomplete \u2014 at least one required nutrient is set to ignore.</div>", unsafe_allow_html=True)
                st.info("These nutrients still have a remaining requirement (>0) but are currently ignored or not matched:")
                st.json(missing_needed)

        with st.expander("Show overview (mapping)"):
            st.dataframe(mapping_df, use_container_width=True, hide_index=True)

    else:
        st.markdown("<div class='warnrow'>⏳ Please upload both files correctly first (data format ✅). Data check will be available afterwards.</div>", unsafe_allow_html=True)

# ------------------------------------------------------------
# 7) RUN OPTIMIZATION
# ------------------------------------------------------------
mapping_ok_for_run = True
mapped_constraints_effective = constraints_effective

if status_ok and (supplements is not None) and (constraints_effective is not None) and ("nutrient_mapping" in st.session_state):
    try:
        mapping = st.session_state.get("nutrient_mapping") or {}
        skip_missing = bool(st.session_state.get("skip_missing_nutrients", False))

        mapped_constraints_effective = apply_mapping_to_constraints(constraints_effective, mapping)

        eff_cols = list(constraints_effective.columns)
        base_eff = pd.to_numeric(constraints_effective.loc["Grundnahrung", eff_cols], errors="coerce").fillna(0.0)
        min_eff = pd.to_numeric(constraints_effective.loc["Tagesbedarf", eff_cols], errors="coerce").fillna(0.0)
        needed = (min_eff - base_eff).clip(lower=0.0)
        needed_cols = [c for c in eff_cols if float(needed.get(c, 0.0)) > 0.0]

        for n in needed_cols:
            if mapping.get(n, None) is None:
                if skip_missing:
                    continue
                mapping_ok_for_run = False
                break
    except Exception:
        mapping_ok_for_run = False

can_run = status_ok and (mapped_constraints_effective is not None) and (supplements is not None) and mapping_ok_for_run

st.markdown("### 📈 Optimization")

with st.expander("Optimization (expand)", expanded=True):

    if "opt_result" not in st.session_state:
        st.session_state["opt_result"] = None

    if st.button("🚀 Start Optimization", disabled=not can_run):
        status_placeholder = st.empty()
        status_placeholder.markdown("<div class='warnrow'>⏳ Optimizing...</div>", unsafe_allow_html=True)

        try:
            status, solution, cost, infeasible_msg, debug = optimize_fast(mapped_constraints_effective, supplements)
        except Exception as e:
            status_placeholder.markdown(f"<div class='errorrow'>❌ Error message: {e}</div>", unsafe_allow_html=True)
            st.exception(e)
            st.stop()

        if status != "Optimal" or solution is None or debug is None:
            status_placeholder.markdown("<div class='errorrow'>❌ No optimal solution found.</div>", unsafe_allow_html=True)
            st.markdown(f"**Solver-Status:** `{status}`")

            if infeasible_msg:
                st.info("Initial assessment/note:")
                st.json(infeasible_msg)

            diag = debug.get("diagnose", None) if isinstance(debug, dict) else None
            if diag is not None:
                with st.expander("🧩 Diagnosis details (why no solution?)", expanded=True):
                    st.caption("Heuristic: (1) Min exceeds the maximum achievable value (BIG_M), (2) no positive source available, (3) base feed > Max, plus top sources & 1g effect.")
                    likely = diag.get("likely_problem_nutrients", None)
                    if isinstance(likely, pd.DataFrame) and not likely.empty:
                        st.markdown("#### ⚠️ Suspicious nutrients (likely cause)")
                        show = likely[[
                            "Nutrient",
                            "Min_After_Base_Diet",
                            "Max_After_Base_Diet",
                            "Max_Achievable_Rough",
                            "Has_Positive_Source",
                            "Flags"
                        ]].copy()
                        show = show.sort_values(by=["Flags", "Min_After_Base_Diet"], ascending=[False, False]).reset_index(drop=True)
                        st.dataframe(show, use_container_width=True, hide_index=True)

                        st.markdown("#### 🔍 Top sources & 1g effect (for the worst 5)")
                        st.json(likely.head(5).to_dict(orient="records"))
                    else:
                        st.warning("No clear flags found. In this case, it is often a conflict between Min/Max across multiple nutrients or a unit issue (mg vs g).")

                    full = diag.get("diag_df", None)
                    with st.expander("All Nutritions (Full Table)", expanded=False):
                        if isinstance(full, pd.DataFrame):
                            st.dataframe(full[[
                                "Nutrient",
                                "Min_After_Base_Diet",
                                "Max_After_Base_Diet",
                                "Max_Achievable_Rough",
                                "Has_Positive_Source",
                                "Flags"
                            ]], use_container_width=True, hide_index=True)

                    st.caption(
                        f"Parameter: MIN_KG={diag.get('MIN_KG')} kg (={diag.get('MIN_KG',0)*1000:.1f} g), "
                        f"BIG_M_KG={diag.get('BIG_M_KG')} kg. supp_clean shape={diag.get('supp_clean_shape')}"
                    )

            st.markdown("## 🧪 Debug: Which nutrients make the problem unsolvable?")
            slack_df = optimize_with_slacks(mapped_constraints_effective, supplements)
            slack_df = slack_df[(slack_df["Slack_Min"] > 1e-9) | (slack_df["Slack_Max"] > 1e-9)]

            if not slack_df.empty:
                st.dataframe(slack_df, use_container_width=True, hide_index=True)
                st.info("Large slack values → strong indication of a unit issue or an incorrect Excel value.")
            else:
                st.success("Slack ~0 → this is more likely a combination or minimum quantity issue.")
            st.stop()

        # Erfolg: speichern (damit UI-Änderungen nicht alles resetten)
        st.session_state["opt_result"] = {
            "status": status,
            "solution": solution,
            "cost": cost,
            "debug": debug,
            "mapped_constraints_effective": mapped_constraints_effective,
        }
        status_placeholder.markdown("<div class='okrow'>✅ Done.</div>", unsafe_allow_html=True)

    # Immer aus gespeicherten Ergebnissen rendern
    res = st.session_state.get("opt_result")
    if res is None:
        st.info("No results available yet. Please start the optimization")
        st.stop()

    status = res["status"]
    solution = res["solution"]
    cost = res["cost"]
    debug = res["debug"]
    mapped_constraints_effective = res["mapped_constraints_effective"]

    if st.button("♻️ Reset result"):
        st.session_state["opt_result"] = None
        st.rerun()

    st.subheader("Result")

    n_supp = int(len(solution))
    k1, k2 = st.columns(2)
    with k1:
        st.markdown(
            f"""
            <div class="kpi-card" style="background: rgba(46,184,92,0.12); border: 1px solid rgba(46,184,92,0.30);">
                <div class="kpi-title">💰 Minimum Cost</div>
                <div class="kpi-value">{cost:.4f} €</div>
            </div>
            """,
            unsafe_allow_html=True
        )
    with k2:
        st.markdown(
            f"""
            <div class="kpi-card">
                <div class="kpi-title">💊 Number of Supplements</div>
                <div class="kpi-value">{n_supp}</div>
            </div>
            """,
            unsafe_allow_html=True
        )

    st.caption("Note: The optimization currently applies a minimum quantity of 1 g/day per selected supplement (MIN_KG = 1/1000 kg).")

    solution_df = (
        solution.rename("Daily Amount (kg)")
        .to_frame()
        .reset_index()
        .rename(columns={"index": "Supplement"})
    )
    solution_df["Daily Amount (g)"] = solution_df["Daily Amount (kg)"] * 1000.0
    solution_df = solution_df.sort_values("Daily Amount (g)", ascending=False).reset_index(drop=True)

    display_supp_df = solution_df[["Supplement", "Daily Amount (g)"]].copy()
    display_supp_df["Daily Amount (g)"] = display_supp_df["Daily Amount (g)"].round(2)

    st.markdown("#### 💊 Selected supplements & daily amount")
    tcol, _ = st.columns([1.15, 1.85])
    with tcol:
        st.dataframe(
            display_supp_df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Supplement": st.column_config.TextColumn(width="medium"),
                "Daily Amount (g)": st.column_config.NumberColumn(format="%.2f", width="small"),
            },
        )

    # ------------------------------------------------------------
    # Contributions per Supplement × Nutrient
    # ------------------------------------------------------------
    with st.expander("🧾 Contributions per Supplement × Nutrient (expand)", expanded=False):
        nutrient_cols = debug.get("nutrient_cols", [])
        supp_clean = debug.get("supp_clean", None)

        if supp_clean is None or not nutrient_cols:
            st.warning("No nutrient data available.")
        else:
            cdf = mapped_constraints_effective
            base = pd.to_numeric(cdf.loc["Grundnahrung", nutrient_cols], errors="coerce").fillna(0.0)
            minv = pd.to_numeric(cdf.loc["Tagesbedarf", nutrient_cols], errors="coerce").fillna(0.0)
            needed = (minv - base).clip(lower=0.0)
            relevant = [n for n in nutrient_cols if float(needed.get(n, 0.0)) > 0.0]

            show_mode = st.radio(
                "Which nutrients to show?",
                options=["Relevant only (requirement > 0)", "All matched"],
                index=0,
                horizontal=True
            )
            show_cols = relevant if (show_mode == "Relevant only (requirement > 0)") else nutrient_cols

            default_pick = show_cols[: min(12, len(show_cols))]
            picked = st.multiselect("Select nutrients (optional)", options=show_cols, default=default_pick)
            show_cols = picked if picked else show_cols

            x_kg = solution.copy()
            chosen = x_kg.index.tolist()

            contrib = supp_clean.loc[chosen, show_cols].copy()
            for n in show_cols:
                contrib[n] = contrib[n].astype(float) * x_kg  # align by index

            grams = (x_kg * 1000.0).rename("Daily Amount (g)")
            contrib_wide = contrib.copy()
            contrib_wide.insert(0, "Daily Amount (g)", grams.round(3))

            st.markdown("#### Wide View (rows = supplements, columns = nutrients)")
            st.dataframe(contrib_wide.round(6), use_container_width=True)

            tmp = contrib.reset_index()
            idx_col = tmp.columns[0]
            tmp = tmp.rename(columns={idx_col: "Supplement"})
            long_df = tmp.melt(id_vars=["Supplement"], var_name="Nutrient", value_name="Contribution/Day")

            long_df = long_df.merge(
                grams.reset_index().rename(columns={grams.reset_index().columns[0]: "Supplement"}),
                on="Supplement",
                how="left"
            )

            long_df = long_df[long_df["Contribution/Day"].abs() > 0].sort_values(
                ["Nutrient", "Contribution/Day"], ascending=[True, False]
            )

            st.markdown("#### Long View (filterable)")
            st.dataframe(long_df.round(6), use_container_width=True, hide_index=True)

            totals = contrib.sum(axis=0).rename("Total Contribution/Day").to_frame()
            totals["Base Diet"] = base.reindex(show_cols).values
            totals["After Supplementation"] = totals["Base Diet"] + totals["Total Contribution/Day"]
            totals["Minimum"] = minv.reindex(show_cols).values
            totals["Δ to Min"] = totals["After Supplementation"] - totals["Minimum"]
            totals = totals.reset_index().rename(columns={"index": "Nutrient"})

            st.markdown("#### Totals per Nutrient (supplement contribution + base diet)")
            st.dataframe(totals.round(8), use_container_width=True, hide_index=True)

    # ------------------------------------------------------------
    # Shelf Life & Reordering
    # ------------------------------------------------------------
    with st.expander("📦 Shelf Life & Reordering (expand)", expanded=False):
        st.caption("Assumption: you buy a standard quantity per supplement in kg. Adjust as needed.")

        buy_kg = st.number_input(
            "Standard purchase quantity per supplement (kg)",
            min_value=0.1,
            max_value=50.0,
            value=1.0,
            step=0.1,
            format="%.1f",
            key="buy_kg_default"
        )

        reorder_threshold_days = st.number_input(
            "Reorder when remaining supply falls below (days)",
            min_value=1,
            max_value=365,
            value=30,
            step=1,
            key="reorder_threshold_days"
        )

        supply_df = display_supp_df.copy()
        supply_df["Purchase Amount (kg)"] = float(buy_kg)
        supply_df["Lasts (Days)"] = (supply_df["Purchase Amount (kg)"] * 1000.0) / supply_df["Daily Amount (g)"]
        supply_df["Lasts (Days)"] = supply_df["Lasts (Days)"].replace([np.inf, -np.inf], np.nan)

        supply_df["Reorder?"] = np.where(
            supply_df["Lasts (Days)"] < float(reorder_threshold_days),
            "✅ yes",
            "—"
        )

        supply_df = supply_df.sort_values("Lasts (Days)", ascending=True).reset_index(drop=True)

        st.markdown("##### Overview")
        st.dataframe(
            supply_df[["Supplement", "Daily Amount (g)", "Purchase Amount (kg)", "Lasts (Days)", "Reorder?"]],
            use_container_width=True,
            hide_index=True,
            column_config={
                "Supplement": st.column_config.TextColumn(width="medium"),
                "Daily Amount (g)": st.column_config.NumberColumn(format="%.2f", width="small"),
                "Purchase Amount (kg)": st.column_config.NumberColumn(format="%.1f", width="small"),
                "Lasts (Days)": st.column_config.NumberColumn(format="%.1f", width="small"),
                "Reorder?": st.column_config.TextColumn(width="small"),
            },
        )

        need_reorder = supply_df.loc[supply_df["Reorder?"] == "✅ yes", "Supplement"].tolist()
        if need_reorder:
            st.info("These supplements are below the reorder threshold and should be reordered soon:")
            st.json(need_reorder)
        else:
            st.success("No supplements are below the reorder threshold.")

    # ------------------------------------------------------------
    # Nutrient Check
    # ------------------------------------------------------------
    with st.expander("🧪 Nutrient Check (Min/Max/Base + after supplementation)", expanded=False):
        nutrient_cols = debug.get("nutrient_cols", [])
        supp_clean = debug.get("supp_clean", None)

        if (supp_clean is None) or (len(nutrient_cols) == 0):
            st.warning("No nutrient data available for the overview.")
        else:
            x_kg = solution

            supp_intake = {}
            for n in nutrient_cols:
                vals_perkg = supp_clean[n].reindex(x_kg.index).fillna(0.0)
                supp_intake[n] = float((vals_perkg * x_kg).sum())

            cdf = mapped_constraints_effective
            base = pd.to_numeric(cdf.loc["Grundnahrung", nutrient_cols], errors="coerce").fillna(0.0)
            minv = pd.to_numeric(cdf.loc["Tagesbedarf", nutrient_cols], errors="coerce").fillna(0.0)
            maxv = pd.to_numeric(cdf.loc["Maximaler_Wert", nutrient_cols], errors="coerce")

            after = base.copy()
            for n in nutrient_cols:
                after[n] = float(base.get(n, 0.0)) + float(supp_intake.get(n, 0.0))

            nutri_check = pd.DataFrame({
                "Nutrient": nutrient_cols,
                "Minimum (Daily Req.)": [float(minv.get(n, 0.0)) for n in nutrient_cols],
                "Maximum": [float(maxv.get(n)) if pd.notna(maxv.get(n)) else np.nan for n in nutrient_cols],
                "Base Diet": [float(base.get(n, 0.0)) for n in nutrient_cols],
                "After Supplementation": [float(after.get(n, 0.0)) for n in nutrient_cols],
            })

            def _status_row(row):
                tol = 1e-9 + 1e-6 * max(1.0, abs(row["Minimum (Daily Req.)"]))
                ok_min = row["After Supplementation"] + tol >= row["Minimum (Daily Req.)"]
                if pd.isna(row["Maximum"]):
                    ok_max = True
                else:
                    tol2 = 1e-9 + 1e-6 * max(1.0, abs(row["Maximum"]))
                    ok_max = row["After Supplementation"] <= row["Maximum"] + tol2

                if ok_min and ok_max:
                    return "✅ ok"
                if (not ok_min) and ok_max:
                    return "⬇️ below Min"
                if ok_min and (not ok_max):
                    return "⬆️ above Max"
                return "⚠️ out of range"

            nutri_check["Status"] = nutri_check.apply(_status_row, axis=1)

            for c in ["Minimum (Daily Req.)", "Maximum", "Base Diet", "After Supplementation"]:
                nutri_check[c] = nutri_check[c].round(4)

            nutri_check = nutri_check.sort_values(["Status", "Nutrient"]).reset_index(drop=True)

            st.dataframe(
                nutri_check,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Nutrient": st.column_config.TextColumn(width="medium"),
                    "Minimum (Daily Req.)": st.column_config.NumberColumn(width="small"),
                    "Maximum": st.column_config.NumberColumn(width="small"),
                    "Base Diet": st.column_config.NumberColumn(width="small"),
                    "After Supplementation": st.column_config.NumberColumn(width="small"),
                    "Status": st.column_config.TextColumn(width="small"),
                },
            )

    try:
        st.image("static/pikachu.jpg", width=230)
    except Exception:
        pass
