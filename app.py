# ============================================================
# Animal Supplement Optimierer (Streamlit App)
#
# WICHTIG:
# - Streamlit "Wrapper-DIVs" via st.markdown(<div>...) um Widgets herum
#   funktionieren oft NICHT zuverlässig, weil Widgets in eigenen DOM-Blöcken
#   gerendert werden.
# - Daher stylen wir:
#     (1) Checkboxen & Captions GLOBAL (robust)
#     (2) Buttons robust über :has() (Button-Text), mit Fallbacks
#
# Design-Controls:
# - Ändere Größen/Weights nur im :root Block im CSS (0b)
# ============================================================

import numpy as np
import numpy as np
import numpy as np
import pandas as pd
import pulp
import streamlit as stimport 
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
#    -> HIER stellst du Button/Checkbox/Caption-Größen ein
# ------------------------------------------------------------
st.markdown(
    """
    <style>
    /* =========================
       DESIGN CONTROLS
       ========================= */
    :root{
      /* Primary button (Optimierung starten) */
      --btn_primary_font: 1.90rem;
      --btn_primary_weight: 800;
      --btn_primary_py: 0.55rem;
      --btn_primary_px: 0.90rem;
      --btn_primary_radius: 10px;

      /* Small button (Reset) */
      --btn_small_font: 1.90rem;
      --btn_small_weight: 400;
      --btn_small_py: 0.20rem;
      --btn_small_px: 0.55rem;
      --btn_small_radius: 10px;

      /* Checkbox */
      --chk_font: 1.3rem;
      --chk_weight: 500;
      --chk_scale: 1.45;
      --chk_gap: 12px;

      /* Caption */
      --caption_font: 1.30rem;
      --caption_weight: 450;
      --caption_opacity: 0.85;
      --caption_line: 1.35;
    }

    /* =========================
       CHECKBOXES (global)  ✅ works
       ========================= */
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

    /* =========================
       CAPTION (robust) ✅ fixed
       - Covers multiple Streamlit render variants
       ========================= */

    /* If Streamlit exposes stCaption */
    div[data-testid="stCaption"],
    div[data-testid="stCaption"] *{
      font-size: var(--caption_font) !important;
      font-weight: var(--caption_weight) !important;
      line-height: var(--caption_line) !important;
      opacity: var(--caption_opacity) !important;
    }

    /* Common: caption as <small> inside markdown container */
    div[data-testid="stMarkdownContainer"] small,
    div[data-testid="stMarkdownContainer"] small *{
      font-size: var(--caption_font) !important;
      font-weight: var(--caption_weight) !important;
      line-height: var(--caption_line) !important;
      opacity: var(--caption_opacity) !important;
    }

    /* Extra robust: markdown paragraphs that *contain* small (only affects captions) */
    div[data-testid="stMarkdownContainer"] p:has(small),
    div[data-testid="stMarkdownContainer"] p:has(small) *{
      font-size: var(--caption_font) !important;
      font-weight: var(--caption_weight) !important;
      line-height: var(--caption_line) !important;
      opacity: var(--caption_opacity) !important;
    }

    /* =========================
       BUTTONS (robust) ✅ fixed
       - DO NOT rely on aria-label
       - Target by visible text using :has()
       ========================= */

    /* Primary: match button whose inner text contains "Optimierung starten"
       (emoji may be stripped by Streamlit, so we match both) */
    div[data-testid="stButton"]:has(button:has(span:contains("Optimierung starten"))) > button,
    div[data-testid="stButton"]:has(button:has(p:contains("Optimierung starten"))) > button{
      padding: var(--btn_primary_py) var(--btn_primary_px) !important;
      border-radius: var(--btn_primary_radius) !important;
    }

    /* Also match via :has on the button itself (more reliable) */
    div[data-testid="stButton"] button:has(*:contains("Optimierung starten")){
      padding: var(--btn_primary_py) var(--btn_primary_px) !important;
      border-radius: var(--btn_primary_radius) !important;
    }
    div[data-testid="stButton"] button:has(*:contains("Optimierung starten")) *{
      font-size: var(--btn_primary_font) !important;
      font-weight: var(--btn_primary_weight) !important;
      line-height: 1.1 !important;
    }

    /* Small: match reset button by text */
    div[data-testid="stButton"] button:has(*:contains("Änderungen zurücksetzen")){
      padding: var(--btn_small_py) var(--btn_small_px) !important;
      border-radius: var(--btn_small_radius) !important;
    }
    div[data-testid="stButton"] button:has(*:contains("Änderungen zurücksetzen")) *{
      font-size: var(--btn_small_font) !important;
      font-weight: var(--btn_small_weight) !important;
      line-height: 1.2 !important;
    }

    /* Fallback for old engines: if :has() is unsupported, at least style all buttons a bit */
    @supports not selector(:has(*)) {
      div[data-testid="stButton"] > button {
        border-radius: 10px !important;
      }
    }

    /* Download buttons (keep nice) */
    div[data-testid="stDownloadButton"] > button {
        padding: 0.55rem 0.9rem !important;
        border-radius: 10px !important;
        font-weight: 800 !important;
    }

    /* Upload titles */
    .upload-title { font-size: 1.10rem; font-weight: 750; margin-bottom: 0.1rem; }
    .muted-hint { color: rgba(49, 51, 63, 0.7); font-size: 0.95rem; margin-top: -0.1rem; margin-bottom: 0.6rem; }

    /* Status line */
    .statusline { font-size: 1.05rem; font-weight: 650; margin: 0.15rem 0 0.65rem 0; }

    /* Compact “success row” etc. */
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
    .errorrow {
        background: rgba(255, 0, 0, 0.08);
        border: 1px solid rgba(255, 0, 0, 0.18);
        border-radius: 10px;
        padding: 0.55rem 0.7rem;
        margin: 0.45rem 0 0.55rem 0;
        font-weight: 650;
    }

    /* Spacing under nutrient table */
    .nutrient-actions { margin-top: 0.35rem; }
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
# 5) RATION TABLE -> EDITABLE TABLE (session-state)
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
    return edit

def edit_df_to_constraints(edit_df: pd.DataFrame, original_constraints: pd.DataFrame) -> pd.DataFrame:
    nutrients = edit_df["Nährstoff"].tolist()
    out = original_constraints.copy()
    out = out.reindex(columns=nutrients)
    out.loc["Tagesbedarf"] = pd.to_numeric(edit_df["Tagesbedarf (Min)"].values, errors="coerce")
    out.loc["Maximaler_Wert"] = pd.to_numeric(edit_df["Maximalwert (Max)"].values, errors="coerce")
    out.loc["Grundnahrung"] = pd.to_numeric(edit_df["Grundnahrung"].values, errors="coerce")
    return out

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
                        st.warning("⚠️ **Warnung! Das Format scheint nicht zu passen:**\n\n" + "\n".join(f"- {msg}" for msg in issues))
                        ration_ok = False
                    else:
                        ration_ok = True
                        st.markdown("<div class='okrow'>✅ Format passt!</div>", unsafe_allow_html=True)

                        st.markdown("#### 🧾 Nährstoff-Intervalle (Ration) – Anzeige & Edit")
                        st.caption(
                            "Min/Max/Grundnahrung sind editierbar. "
                            "Erst wenn du **fixierst**, werden die Werte für die Optimierung übernommen."
                        )

                        edit_df_default = constraints_to_edit_df(constraints_raw)
                        signature = tuple(edit_df_default["Nährstoff"].tolist())

                        if st.session_state.get("constraints_signature") != signature:
                            st.session_state["constraints_signature"] = signature
                            st.session_state["constraints_edit_df"] = edit_df_default.copy()
                            st.session_state["constraints_locked"] = False
                            st.session_state["constraints_effective_df"] = None

                        locked = st.session_state.get("constraints_locked", False)

                        edited = st.data_editor(
                            st.session_state["constraints_edit_df"].copy(),
                            key="constraints_editor",
                            use_container_width=True,
                            num_rows="fixed",
                            hide_index=True,
                            disabled=locked,
                            column_config={
                                "Nährstoff": st.column_config.TextColumn(disabled=True),
                                "Tagesbedarf (Min)": st.column_config.NumberColumn(format="%.1f"),
                                "Maximalwert (Max)": st.column_config.NumberColumn(format="%.1f"),
                                "Grundnahrung": st.column_config.NumberColumn(format="%.1f"),
                                "Bedarf nach Grundnahrung (Min-Base)": st.column_config.NumberColumn(disabled=True, format="%.1f"),
                            },
                        )

                        edited = edited.copy()
                        edited["Tagesbedarf (Min)"] = pd.to_numeric(edited["Tagesbedarf (Min)"], errors="coerce").fillna(0.0)
                        edited["Grundnahrung"] = pd.to_numeric(edited["Grundnahrung"], errors="coerce").fillna(0.0)
                        edited["Maximalwert (Max)"] = pd.to_numeric(edited["Maximalwert (Max)"], errors="coerce")
                        edited["Bedarf nach Grundnahrung (Min-Base)"] = (edited["Tagesbedarf (Min)"] - edited["Grundnahrung"]).clip(lower=0.0)
                        st.session_state["constraints_edit_df"] = edited

                        st.markdown("<div class='nutrient-actions'>", unsafe_allow_html=True)

                        # Reset button (styled via aria-label selector)
                        if st.button("↩️ Änderungen zurücksetzen", key="reset_constraints_btn"):
                            st.session_state["constraints_edit_df"] = edit_df_default.copy()
                            st.session_state["constraints_locked"] = False
                            st.session_state["constraints_effective_df"] = None
                            st.success("Änderungen zurückgesetzt. Fixierung aufgehoben.")

                        # Lock checkbox (global checkbox style applies)
                        locked_now = st.checkbox(
                            "🔏 Nährstoff Intervalle fixieren",
                            value=st.session_state.get("constraints_locked", False),
                            key="constraints_locked_ui"
                        )
                        st.session_state["constraints_locked"] = locked_now

                        st.markdown("</div>", unsafe_allow_html=True)

                        if st.session_state.get("constraints_locked", False):
                            st.session_state["constraints_effective_df"] = edit_df_to_constraints(edited, constraints_raw)
                            constraints_effective = st.session_state["constraints_effective_df"]
                            st.markdown("<div class='okrow'>✅ Intervalle fixiert – Werte werden für die Optimierung verwendet.</div>", unsafe_allow_html=True)
                        else:
                            constraints_effective = None
                            st.markdown("<div class='warnrow'>⏳ Noch nicht fixiert – Optimierung bleibt deaktiviert.</div>", unsafe_allow_html=True)

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
                        st.warning("⚠️ **Warnung! Das Format scheint nicht zu passen:**\n\n" + "\n".join(f"- {msg}" for msg in issues))

                    if not excluded_supps_table.empty:
                        st.info(
                            f"{len(excluded_supps_table)} Supplements haben keinen gültigen Preis "
                            "und werden automatisch ausgeschlossen."
                        )

                        with st.expander(f"Details anzeigen ({len(excluded_supps_table)} Zeilen)"):
                            st.dataframe(excluded_supps_table, use_container_width=True)

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

# ------------------------------------------------------------
# 7) OPTIMIERUNG (Placeholder)
# ------------------------------------------------------------
can_run = status_ok and constraints_effective is not None and supplements is not None

st.markdown("### 📈 Optimierung")
with st.expander("Optimierung (aufklappen)", expanded=True):
    # Optimierung button (styled via aria-label selector)
    if st.button("🚀 Optimierung starten", disabled=not can_run):
        st.success("Start (Rest deiner Optimierungs-UI bleibt wie gehabt)")
        st.image("static/pikachu.jpg", width=220)
