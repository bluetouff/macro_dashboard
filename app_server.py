"""
US Macro Risk Dashboard — Version SERVEUR (snapshots-only).
Lance : streamlit run app_server.py

Cette version ne fait AUCUN appel à FRED. Elle lit uniquement les fichiers parquet
générés par snapshot_builder.py (lancé par cron une fois par jour).
La clé FRED n'est jamais accessible au processus Streamlit.
"""

import os
import json
from pathlib import Path
from datetime import datetime

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go

from catalog import (
    FAMILY_LABELS, FAMILY_ICONS,
    ZSCORE_WARNING, ZSCORE_DANGER, NBER_RECESSION_PERIODS,
)


# ============================================================
# CONFIG
# ============================================================

SNAPSHOTS_DIR = Path(os.environ.get('SNAPSHOTS_DIR', '/var/lib/macro_dashboard/snapshots'))

st.set_page_config(
page_title="US Macro Risk Dashboard",
    page_icon="🇺🇸",
    layout="wide",
    initial_sidebar_state="collapsed",
)

VIEW_PARAM = "view"


def query_value(name: str, default: str = "") -> str:
    value = st.query_params.get(name, default)
    if isinstance(value, list):
        return str(value[0]) if value else default
    return str(value)


def current_view() -> str:
    view = query_value(VIEW_PARAM, "radar").lower()
    return "faq" if view in {"faq", "help", "aide"} else "radar"


st.markdown("""
<style>
    :root {
        --bg: #1a1a1a;
        --panel: #202020;
        --line: rgba(0, 240, 208, 0.16);
        --line-soft: rgba(255, 255, 255, 0.10);
        --text: #b8fff5;
        --paper: #e7e9ee;
        --bright: #f5f6f8;
        --dim: #6f9b94;
        --faint: #456b65;
        --usd: #00f0d0;
        --teal: #5eead4;
        --yen: #ff6b9d;
        --rose: #ff4d87;
        --gold: #f5b13d;
        --mono: ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, monospace;
    }
    .main { background-color: var(--bg); }
    .stApp {
        background: var(--bg);
        color: var(--text);
        font-family: var(--mono);
    }
    .stApp::after {
        content: "";
        position: fixed;
        inset: 0;
        pointer-events: none;
        z-index: 9999;
        background: repeating-linear-gradient(0deg, rgba(0,0,0,0) 0, rgba(0,0,0,0) 2px, rgba(0,0,0,.08) 3px);
        mix-blend-mode: multiply;
        opacity: .42;
    }
    .block-container { padding-top: 1.2rem; max-width: 1220px; }
    h1, h2, h3 { color: var(--bright); letter-spacing: 0; font-family: var(--mono); }
    h1 { border-bottom: 1px solid var(--line); padding-bottom: 0.45rem; }
    h2 { color: var(--dim); font-size: 0.92rem; letter-spacing: 0.08em; text-transform: uppercase; }
    h2::before {
        content: "";
        display: inline-block;
        width: 18px;
        height: 2px;
        margin-right: 10px;
        vertical-align: middle;
        background: var(--yen);
    }
    h3 { color: var(--paper); font-size: 1rem; }
    .tape {
        display: flex;
        flex-wrap: wrap;
        align-items: baseline;
        gap: 12px 22px;
        border-bottom: 1px solid var(--line);
        padding-bottom: 14px;
        margin-bottom: 20px;
    }
    .brand { color: var(--bright); font-size: 1.15rem; font-weight: 800; }
    .brand b { color: var(--yen); }
    .tagline { color: var(--dim); font-size: 0.72rem; letter-spacing: 0.03em; }
    .status-pill {
        margin-left: auto;
        color: var(--dim);
        border: 1px solid var(--line);
        border-radius: 999px;
        padding: 4px 10px;
        font-size: 0.7rem;
        display: flex;
        gap: 8px;
        align-items: center;
    }
    .status-dot { width: 7px; height: 7px; border-radius: 50%; background: var(--usd); }
    .top-nav { display: flex; flex-wrap: wrap; gap: 8px; margin-left: auto; align-items: center; }
    .nav-link {
        color: var(--dim) !important;
        border: 1px solid var(--line);
        border-radius: 999px;
        padding: 4px 10px;
        font-size: 0.7rem;
        text-decoration: none !important;
    }
    .nav-link:hover, .nav-link.active {
        color: var(--bright) !important;
        border-color: rgba(94, 234, 212, 0.65);
        background: rgba(94, 234, 212, 0.06);
    }
    .help-card, .stale-warning {
        background: rgba(255, 255, 255, 0.018);
        border: 1px solid var(--line);
        border-left: 2px solid var(--teal);
        border-radius: 10px;
        padding: 13px 15px;
        color: var(--dim);
        font-size: 0.82rem;
        line-height: 1.55;
        margin: 8px 0 14px;
    }
    .stale-warning { border-left-color: var(--rose); }
    .help-card strong, .stale-warning strong { color: var(--paper); }
    .faq-grid {
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 12px;
        margin: 10px 0 18px;
    }
    .faq-card {
        background: rgba(255, 255, 255, 0.018);
        border: 1px solid var(--line);
        border-radius: 10px;
        padding: 14px 15px;
        min-height: 128px;
        color: var(--dim);
        font-size: 0.82rem;
        line-height: 1.52;
    }
    .faq-card strong { color: var(--paper); display: block; margin-bottom: 6px; }
    .kpi-grid {
        display: grid;
        grid-template-columns: repeat(5, minmax(0, 1fr));
        gap: 1px;
        background: var(--line);
        border: 1px solid var(--line);
        border-radius: 10px;
        overflow: hidden;
        margin: 18px 0 16px;
    }
    .kpi-card {
        background: var(--panel);
        border: 0;
        border-left: 3px solid var(--usd);
        border-radius: 0;
        padding: 15px 15px 13px;
        min-height: 112px;
    }
    .kpi-label {
        text-transform: uppercase;
        color: var(--dim);
        font-size: 0.66rem;
        letter-spacing: 0.07em;
        margin-bottom: 4px;
    }
    .kpi-value {
        font-family: var(--mono);
        font-weight: 700;
        font-size: 1.85rem;
        line-height: 1.15;
        font-variant-numeric: tabular-nums;
    }
    .kpi-delta { color: var(--dim); font-size: 0.76rem; margin-top: 8px; line-height: 1.35; }
    div[data-testid="stDataFrame"] {
        border: 1px solid var(--line);
        border-radius: 10px;
        overflow: hidden;
    }
    div[data-testid="stDataFrame"] * { font-family: var(--mono) !important; }
    .site-footer {
        display: flex;
        flex-wrap: wrap;
        align-items: center;
        justify-content: space-between;
        gap: 12px;
        margin-top: 34px;
        padding: 18px 0 6px;
        border-top: 1px solid var(--line);
        color: var(--faint);
        font-size: 0.72rem;
    }
    .l0g-logo {
        display: inline-flex;
        align-items: baseline;
        gap: 2px;
        color: var(--bright) !important;
        font-weight: 800;
        text-decoration: none !important;
        letter-spacing: 0;
    }
    .l0g-logo .slash { color: var(--teal); }
    .l0g-logo:hover { color: var(--teal) !important; }
    footer { visibility: hidden; }
    #MainMenu { visibility: hidden; }
    header[data-testid="stHeader"] { display: none; }
    div[data-testid="stToolbar"] { display: none; }

    div[data-testid="stMarkdownContainer"] h2 {
        font-size: 1.55rem !important;
        line-height: 1.2 !important;
        font-weight: 700 !important;
        letter-spacing: 0 !important;
        text-transform: none !important;
        margin-top: 1.2rem !important;
        margin-bottom: 0.9rem !important;
    }
    div[data-testid="stMarkdownContainer"] h3 {
        font-size: 1.35rem !important;
        line-height: 1.25 !important;
        font-weight: 650 !important;
        letter-spacing: 0 !important;
        margin-top: 1.1rem !important;
        margin-bottom: 0.75rem !important;
    }
    .brand {
        font-size: 1rem !important;
        font-weight: 750 !important;
    }
    .tagline {
        font-size: 0.66rem !important;
    }
    .help-card, .stale-warning {
        font-size: 0.76rem !important;
        padding: 10px 14px !important;
    }
    .kpi-card {
        min-height: 96px !important;
        padding: 13px 14px 12px !important;
    }
    .kpi-label {
        font-size: 0.58rem !important;
        letter-spacing: 0.06em !important;
    }
    .kpi-value {
        font-size: 1.38rem !important;
        line-height: 1.18 !important;
        font-weight: 650 !important;
        overflow-wrap: anywhere;
    }
    .kpi-delta {
        font-size: 0.68rem !important;
        margin-top: 7px !important;
    }
    @media (max-width: 1180px) {
        .kpi-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
        .faq-grid { grid-template-columns: 1fr; }
    }
    @media (max-width: 720px) {
        .kpi-grid { grid-template-columns: 1fr; }
        .status-pill { margin-left: 0; }
    }
</style>
""", unsafe_allow_html=True)


def render_header(view: str) -> None:
    radar_active = "active" if view == "radar" else ""
    faq_active = "active" if view == "faq" else ""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    st.markdown(
        f"""
        <header class="tape">
            <div class="brand"><b>US</b> Macro <b>Risk</b></div>
            <div class="tagline">FRED snapshots · credit · liquidite · travail · consommation · recession watch</div>
            <nav class="top-nav" aria-label="Navigation">
                <a class="nav-link {radar_active}" href="?">Radar</a>
                <a class="nav-link {faq_active}" href="?view=faq">Aide / FAQ</a>
            </nav>
            <div class="status-pill"><span class="status-dot"></span>{timestamp}</div>
        </header>
        """,
        unsafe_allow_html=True,
    )


def render_site_footer() -> None:
    st.markdown(
        """
        <div class="site-footer">
          <a class="l0g-logo" href="https://l0g.fr" target="_blank" rel="noopener" aria-label="l0g.fr">
            <span class="slash">//</span><span>l0g.fr</span>
          </a>
          <span>US Macro Risk Dashboard · Donnees FRED / St. Louis Fed · MIT License</span>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_faq_page() -> None:
    st.markdown("## Aide / FAQ")
    st.markdown(
        """
        <div class="help-card">
          <strong>Objectif.</strong> US Macro Risk Dashboard surveille les signaux de stress macro
          americains depuis des snapshots serveur. Il ne predit pas une recession et ne donne pas de
          signal d'investissement : il aide a prioriser les familles de donnees a lire.
        </div>
        <div class="faq-grid">
          <div class="faq-card"><strong>Perimetre</strong> Credit menages, banques, liquidite, corporate, immobilier, travail, consommation et SLOOS.</div>
          <div class="faq-card"><strong>Score</strong> Les series sont transformees en z-scores signes. Une hausse du score indique davantage de stress relatif.</div>
          <div class="faq-card"><strong>Snapshots</strong> La version publique ne contacte pas FRED directement : elle lit les fichiers parquet generes cote serveur.</div>
          <div class="faq-card"><strong>Lecture</strong> Le score global est un raccourci. La composition par famille et les indicateurs les plus tendus comptent davantage.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.expander("Que mesure le dashboard ?", expanded=True):
        st.markdown("""
        Il suit des indicateurs macro et financiers americains qui peuvent se degrader avant ou
        pendant un ralentissement : defauts de paiement, reserves bancaires, conditions financieres,
        courbe des taux, spreads credit, immobilier, marche du travail, consommation et enquete SLOOS.
        """)

    with st.expander("Pourquoi une version snapshots-only ?"):
        st.markdown("""
        Le processus Streamlit public ne possede pas la cle FRED. Les donnees sont preparees en amont
        par `snapshot_builder.py`, puis l'interface lit seulement des fichiers parquet locaux.
        Cela reduit la surface d'exposition et evite les appels API au chargement public.
        """)

    with st.expander("Comment lire les seuils ?"):
        st.markdown(f"""
        Le seuil vigilance est fixe a `{ZSCORE_WARNING}` et le seuil danger a `{ZSCORE_DANGER}`.
        Ces seuils expriment un stress relatif a l'historique de chaque serie, pas une probabilite
        officielle de recession.
        """)

    with st.expander("Quelles sont les limites ?"):
        st.markdown("""
        Les series peuvent etre revisees, certaines sont trimestrielles, et les regimes economiques
        changent. Le moteur US calibre ses poids sur quatre recessions NBER seulement et ne mesure pas
        explicitement les faux positifs hors recession. Enfin, le score retient le maximum entre z-score,
        drift et momentum, ce qui favorise mecaniquement les alertes precoces au detriment de la parcimonie.

        Le tableau de bord sert a orienter la lecture, pas a remplacer une analyse macro complete.
        """)


# ============================================================
# CACHE LECTURE PARQUET (5 minutes — les fichiers ne changent qu'1x/jour)
# ============================================================

@st.cache_data(ttl=300, show_spinner=False)
def load_snapshot():
    """Charge le snapshot live (situation actuelle)."""
    path = SNAPSHOTS_DIR / 'current_snapshot.parquet'
    if not path.exists():
        return None
    return pd.read_parquet(path)

@st.cache_data(ttl=300, show_spinner=False)
def load_historical():
    """Charge la reconstruction historique mensuelle."""
    path = SNAPSHOTS_DIR / 'historical.parquet'
    if not path.exists():
        return None
    return pd.read_parquet(path)

@st.cache_data(ttl=300, show_spinner=False)
def load_metadata():
    """Charge les métadonnées (date de dernier refresh, etc.)."""
    path = SNAPSHOTS_DIR / 'metadata.json'
    if not path.exists():
        return None
    return json.loads(path.read_text())


# ============================================================
# HELPERS
# ============================================================

def status_color(score):
    if pd.isna(score): return '#6f9b94'
    if score >= ZSCORE_DANGER: return '#ff4d87'
    if score >= ZSCORE_WARNING: return '#f5b13d'
    if score > 0: return '#5eead4'
    return '#00f0d0'

def status_emoji(score):
    if pd.isna(score): return '⚪'
    if score >= ZSCORE_DANGER: return '🔴'
    if score >= ZSCORE_WARNING: return '🟡'
    return '🟢'

def kpi_card(label, value, delta=None, color=None):
    color = color or '#00f0d0'
    delta_html = f'<div class="kpi-delta">{delta}</div>' if delta else ''
    return f"""
    <div class="kpi-card" style="border-left-color: {color};">
        <div class="kpi-label">{label}</div>
        <div class="kpi-value" style="color: {color};">{value}</div>
        {delta_html}
    </div>"""



view = current_view()
render_header(view)

if view == "faq":
    render_faq_page()
    render_site_footer()
    st.stop()

st.markdown(
    """
    <div class="help-card">
      <strong>Perimetre.</strong> Radar macro US base sur des snapshots FRED : credit menages,
      stress bancaire, liquidite, corporate, immobilier, travail, consommation et SLOOS.
    </div>
    """,
    unsafe_allow_html=True,
)

# ============================================================
# CHARGEMENT DONNÉES
# ============================================================

df = load_snapshot()
hist_df = load_historical()
metadata = load_metadata()

if df is None or hist_df is None:
    st.error("⚠️ Aucune donnée disponible.")
    st.info("Le snapshot builder n'a pas encore été exécuté ou les fichiers parquet sont manquants.")
    st.stop()


# ============================================================
# SNAPSHOT STATUS
# ============================================================

if metadata:
    last_update = pd.to_datetime(metadata['last_update'])
    age_hours = (datetime.now() - last_update.replace(tzinfo=None)).total_seconds() / 3600
    if age_hours > 30:
        st.markdown(f"""<div class="stale-warning">
            <strong>Donnees anciennes</strong><br>
            Dernier refresh : {last_update.strftime('%d %b %Y, %H:%M')}<br>
            ({age_hours:.0f}h, le cron a peut-etre plante)
        </div>""", unsafe_allow_html=True)
    else:
        st.markdown(f"""<div class="help-card">
            <strong>Snapshot.</strong> Donnees du {last_update.strftime('%d %b %Y, %H:%M')}.
        </div>""", unsafe_allow_html=True)


# ============================================================
# SCORES AGRÉGÉS
# ============================================================

def family_scores_df(df):
    def wfam(g):
        w, s = g['weight'], g['stress_final']
        return (s * w).sum() / w.sum() if w.sum() > 0 else np.nan
    fam = df.groupby('famille').apply(wfam).rename('score')
    maxes = df.groupby('famille')['stress_final'].max().rename('max')
    counts = df.groupby('famille').size().rename('n')
    return pd.concat([fam, maxes, counts], axis=1).sort_values('score', ascending=False)

fam_scores_df = family_scores_df(df)
gscore = (df['stress_final'] * df['weight']).sum() / df['weight'].sum()


# ============================================================
# KPI BAR
# ============================================================

st.markdown("## 📊 INDICATEURS PRINCIPAUX")

g_series = hist_df['global']
current_hist = g_series.iloc[-1]
m1 = g_series.asof(g_series.index[-1] - pd.DateOffset(months=1))
m3 = g_series.asof(g_series.index[-1] - pd.DateOffset(months=3))
m12 = g_series.asof(g_series.index[-1] - pd.DateOffset(years=1))
percentile = (g_series <= current_hist).mean() * 100

delta3 = current_hist - m3 if pd.notna(m3) else 0
delta12 = current_hist - m12 if pd.notna(m12) else 0
top_fam = fam_scores_df.iloc[0]
fam_name = top_fam.name

st.markdown(
    f"""
    <div class="kpi-grid">
        {kpi_card("Score global live", f"{gscore:+.2f}", f"Pondere empirique · {len(df)} series", status_color(gscore))}
        {kpi_card("Score historique", f"{current_hist:+.2f}", f"Percentile {percentile:.0f}% depuis 1990", status_color(current_hist))}
        {kpi_card("Tendance 3 mois", f"{delta3:+.2f}", f"Il y a 3M : {m3:+.2f}" if pd.notna(m3) else "", "#ff4d87" if delta3 > 0.2 else "#5eead4" if delta3 < -0.2 else "#6f9b94")}
        {kpi_card("Tendance 1 an", f"{delta12:+.2f}", f"Il y a 1Y : {m12:+.2f}" if pd.notna(m12) else "", "#ff4d87" if delta12 > 0.2 else "#5eead4" if delta12 < -0.2 else "#6f9b94")}
        {kpi_card("Famille #1 stress", f"{FAMILY_LABELS.get(fam_name, fam_name)} {top_fam['score']:+.2f}", "Canal le plus tendu", status_color(top_fam["score"]))}
    </div>
    """,
    unsafe_allow_html=True,
)

st.markdown("---")


# ============================================================
# GRILLE PRINCIPALE
# ============================================================

st.markdown("### 📈 Score composite historique (1990 → now)")
fig = go.Figure()
fig.add_trace(go.Scatter(
    x=g_series.index,
    y=g_series.values,
    mode='lines',
    line=dict(color='#5eead4', width=1.8),
    fill='tozeroy',
    fillcolor='rgba(94, 234, 212, 0.10)',
    hovertemplate='<b>%{x|%b %Y}</b><br>Score: %{y:+.2f}<extra></extra>',
))
for start_rec, end_rec in NBER_RECESSION_PERIODS:
    fig.add_vrect(
        x0=start_rec,
        x1=end_rec,
        fillcolor='rgba(192, 48, 40, 0.2)',
        line_width=0,
        layer='below',
    )
fig.add_hline(y=0, line_dash='dot', line_color='rgba(255,255,255,0.25)', line_width=1)
fig.add_hline(
    y=ZSCORE_WARNING,
    line_dash='dash',
    line_color='#f5b13d',
    line_width=1,
    annotation_text='Vigilance',
    annotation_position='right',
    annotation_font_color='#f5b13d',
)
fig.add_hline(
    y=ZSCORE_DANGER,
    line_dash='dash',
    line_color='#ff4d87',
    line_width=1,
    annotation_text='Danger',
    annotation_position='right',
    annotation_font_color='#ff4d87',
)
fig.add_trace(go.Scatter(
    x=[g_series.index[-1]],
    y=[current_hist],
    mode='markers',
    marker=dict(size=12, color='#f5f6f8', line=dict(color='#5eead4', width=2)),
    showlegend=False,
))
fig.update_layout(
    template='plotly_dark',
    plot_bgcolor='#1a1a1a',
    paper_bgcolor='#1a1a1a',
    height=460,
    margin=dict(l=10, r=10, t=10, b=10),
    showlegend=False,
    xaxis=dict(gridcolor='rgba(0,240,208,0.08)'),
    yaxis=dict(gridcolor='rgba(0,240,208,0.08)', title='Score'),
)
st.plotly_chart(fig, use_container_width=True)

st.markdown("---")
st.markdown("### 🌡️ Scores par famille")
fd = fam_scores_df.copy()
fd['label'] = fd.index.map(lambda x: f"{FAMILY_ICONS.get(x, '')} {FAMILY_LABELS.get(x, x)}")
fd['color'] = fd['score'].apply(status_color)
fd = fd.sort_values('score', ascending=True)
fig = go.Figure()
fig.add_trace(go.Bar(
    y=fd['label'],
    x=fd['score'],
    orientation='h',
    marker_color=fd['color'],
    text=[f"{s:+.2f}" for s in fd['score']],
    textposition='outside',
    textfont=dict(color='#f5f6f8', size=11),
))
fig.add_vline(x=0, line_color='rgba(255,255,255,0.25)', line_width=1)
fig.add_vline(x=ZSCORE_WARNING, line_dash='dash', line_color='#f5b13d', line_width=1)
fig.add_vline(x=ZSCORE_DANGER, line_dash='dash', line_color='#ff4d87', line_width=1)
fig.update_layout(
    template='plotly_dark',
    plot_bgcolor='#1a1a1a',
    paper_bgcolor='#1a1a1a',
    height=420,
    margin=dict(l=10, r=70, t=10, b=10),
    showlegend=False,
    font=dict(color='#b8fff5'),
    xaxis=dict(gridcolor='rgba(0,240,208,0.08)', range=[-1.5, max(3, fd['score'].max() + 0.5)]),
    yaxis=dict(gridcolor='rgba(0,240,208,0.08)'),
)
st.plotly_chart(fig, use_container_width=True)

st.markdown("---")
st.markdown("### Top 10 indicateurs stresses")
top10 = df.nlargest(10, 'stress_weighted')[
    ['famille', 'series_id', 'name', 'current', 'stress_final', 'weight', 'stress_weighted']
].copy()
top10.insert(0, 'Statut', top10['stress_weighted'].apply(status_emoji))
top10['Tier'] = top10['weight'].apply(lambda w: 'T1' if w >= 2.5 else 'T2' if w >= 1.5 else 'T3')
top10['Famille'] = top10['famille'].map(FAMILY_LABELS)
top10['Z brut'] = top10['stress_final'].round(2)
top10['Score'] = top10['stress_weighted'].round(2)
top10['Valeur'] = top10['current'].apply(lambda v: f"{v:,.2f}" if abs(v) < 10000 else f"{v:,.0f}")
display = top10[['Statut', 'Tier', 'Famille', 'series_id', 'name', 'Valeur', 'Z brut', 'Score']].rename(
    columns={'series_id': 'Code', 'name': 'Indicateur'}
)
st.dataframe(display, hide_index=True, use_container_width=True, height=420)

st.markdown("---")
st.markdown("### Mouvements par famille (3 mois)")
movements = []
for fc in [c for c in hist_df.columns if c.startswith('fam_')]:
    fname = fc.replace('fam_', '')
    cur_v = hist_df[fc].iloc[-1]
    prev_v = hist_df[fc].asof(hist_df.index[-1] - pd.DateOffset(months=3))
    if pd.notna(prev_v):
        movements.append({'famille': fname, 'delta': cur_v - prev_v})

mov_df = pd.DataFrame(movements).sort_values('delta', ascending=False)
fig = go.Figure()
colors = ['#ff4d87' if d > 0.1 else '#5eead4' if d < -0.1 else '#6f9b94' for d in mov_df['delta']]
labels = [f"{FAMILY_ICONS.get(f, '')} {FAMILY_LABELS.get(f, f)}" for f in mov_df['famille']]
fig.add_trace(go.Bar(
    y=labels[::-1],
    x=mov_df['delta'].values[::-1],
    orientation='h',
    marker_color=colors[::-1],
    text=[f"{d:+.2f}" for d in mov_df['delta'].values[::-1]],
    textposition='outside',
    textfont=dict(color='#f5f6f8', size=11),
))
fig.add_vline(x=0, line_color='rgba(255,255,255,0.25)', line_width=1)
fig.update_layout(
    template='plotly_dark',
    plot_bgcolor='#1a1a1a',
    paper_bgcolor='#1a1a1a',
    height=420,
    margin=dict(l=10, r=70, t=10, b=10),
    showlegend=False,
    font=dict(color='#b8fff5'),
    xaxis=dict(gridcolor='rgba(0,240,208,0.08)', title='Δ score sur 3 mois'),
    yaxis=dict(gridcolor='rgba(0,240,208,0.08)'),
)
st.plotly_chart(fig, use_container_width=True)

st.markdown("---")
st.markdown("## 🔬 Détail par famille")

tabs = st.tabs([f"{FAMILY_ICONS.get(f, '')} {FAMILY_LABELS.get(f, f)}" for f in fam_scores_df.index])
for tab, famille in zip(tabs, fam_scores_df.index):
    with tab:
        sub = df[df['famille'] == famille].sort_values('stress_weighted', ascending=False).copy()
        col_a, col_b = st.columns([1, 5])
        with col_a:
            score = fam_scores_df.loc[famille, 'score']
            st.metric(label="Score famille", value=f"{score:+.2f}")
            st.caption(f"{int(fam_scores_df.loc[famille, 'n'])} séries — "
                       f"max: {fam_scores_df.loc[famille, 'max']:+.2f}")
        with col_b:
            sub['Statut'] = sub['stress_weighted'].apply(status_emoji)
            sub['Tier'] = sub['weight'].apply(lambda w: 'T1' if w >= 2.5 else 'T2' if w >= 1.5 else 'T3')
            sub['Score'] = sub['stress_weighted'].round(2)
            sub['Z brut'] = sub['stress_final'].round(2)
            sub['Valeur'] = sub['current'].apply(lambda v: f"{v:,.2f}" if abs(v) < 10000 else f"{v:,.0f}")
            display = sub[['Statut', 'Tier', 'series_id', 'name', 'Valeur', 'Z brut', 'Score']].rename(
                columns={'series_id': 'Code', 'name': 'Indicateur'})
            st.dataframe(
                display,
                hide_index=True,
                use_container_width=True,
                column_config={
                    "Code": st.column_config.TextColumn("Code", width="small"),
                    "Indicateur": st.column_config.TextColumn("Indicateur", width="large"),
                    "Valeur": st.column_config.TextColumn("Valeur", width="small"),
                    "Z brut": st.column_config.NumberColumn("Z brut", width="small"),
                    "Score": st.column_config.NumberColumn("Score", width="small"),
                },
            )


# ============================================================
# FOOTER
# ============================================================

st.markdown(
    f"""
    <div class="help-card">
      <strong>Sources et methode.</strong> Donnees FRED (St. Louis Fed) via snapshots serveur.
      Methodologie : z-score 5Y, drift pre-COVID, momentum et ponderation empirique calibree par backtest.
      Perimetre : {len(df)} series / {df['famille'].nunique()} familles.
    </div>
    """,
    unsafe_allow_html=True,
)
render_site_footer()
