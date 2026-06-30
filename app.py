"""
US Macro Risk Dashboard - Tableau de bord style Bloomberg.
Lancement : `streamlit run app.py`
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime

from catalog import (
    SERIES_CATALOG, FAMILY_LABELS, FAMILY_ICONS,
    ZSCORE_WARNING, ZSCORE_DANGER, NBER_RECESSION_PERIODS,
    REGIME_CHANGE_SERIES, NO_MOMENTUM_SERIES,
)
from data import (
    fetch_all_series, compute_dashboard, compute_predictive_power,
    apply_weights, family_scores, global_score,
    status_emoji, reconstruct_historical_score, power_to_weight,
)


# ============================================================
# CONFIG STREAMLIT
# ============================================================

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


# Charte l0g proche de debt.l0g.fr : noir dense, mono, accents teal/rose.
st.markdown("""
<style>
    :root {
        --bg: #1a1a1a;
        --panel: #202020;
        --panel2: #171717;
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
        --orange: #ff8a3d;
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
    .block-container {
        padding-top: 1.2rem;
        max-width: 1220px;
    }
    h1, h2, h3 {
        color: var(--bright);
        letter-spacing: 0;
        font-family: var(--mono);
    }
    h1 {
        border-bottom: 1px solid var(--line);
        padding-bottom: 0.45rem;
        text-shadow: 0 0 30px rgba(94, 234, 212, 0.18);
    }
    h2 {
        color: var(--dim);
        font-size: 0.92rem;
        letter-spacing: 0.08em;
        text-transform: uppercase;
    }
    h2::before {
        content: "";
        display: inline-block;
        width: 18px;
        height: 2px;
        margin-right: 10px;
        vertical-align: middle;
        background: var(--yen);
    }
    h3 {
        color: var(--paper);
        font-size: 1rem;
    }
    div[data-testid="stSidebar"] {
        background: #171717;
        border-right: 1px solid var(--line);
    }
    div[data-testid="stSidebar"] label,
    div[data-testid="stSidebar"] p {
        color: var(--dim);
        font-family: var(--mono);
    }
    .tape {
        display: flex;
        flex-wrap: wrap;
        align-items: baseline;
        gap: 12px 22px;
        border-bottom: 1px solid var(--line);
        padding-bottom: 14px;
        margin-bottom: 20px;
    }
    .brand {
        color: var(--bright);
        font-size: 1.15rem;
        font-weight: 800;
    }
    .brand b { color: var(--yen); }
    .tagline {
        color: var(--dim);
        font-size: 0.72rem;
        letter-spacing: 0.03em;
    }
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
    .status-dot {
        width: 7px;
        height: 7px;
        border-radius: 50%;
        background: var(--usd);
    }
    .top-nav {
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
        margin-left: auto;
        align-items: center;
    }
    .nav-link {
        color: var(--dim) !important;
        border: 1px solid var(--line);
        border-radius: 999px;
        padding: 4px 10px;
        font-size: 0.7rem;
        text-decoration: none !important;
    }
    .nav-link:hover,
    .nav-link.active {
        color: var(--bright) !important;
        border-color: rgba(94, 234, 212, 0.65);
        background: rgba(94, 234, 212, 0.06);
    }
    .help-card {
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
    .help-card strong { color: var(--paper); }
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
    .faq-card strong {
        color: var(--paper);
        display: block;
        margin-bottom: 6px;
    }
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
    .kpi-delta {
        color: var(--dim);
        font-size: 0.76rem;
        margin-top: 8px;
        line-height: 1.35;
    }
    .family-row {
        display: flex;
        justify-content: space-between;
        padding: 6px 12px;
        border-bottom: 1px solid var(--line-soft);
        font-family: var(--mono);
    }
    .family-name { color: var(--paper); }
    .family-score { font-weight: bold; }
    div[data-testid="stDataFrame"] {
        border: 1px solid var(--line);
        border-radius: 10px;
        overflow: hidden;
    }
    div[data-testid="stDataFrame"] * {
        font-family: var(--mono) !important;
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        border-bottom: 1px solid var(--line);
    }
    .stTabs [data-baseweb="tab"] {
        color: var(--dim);
        font-family: var(--mono);
        border: 1px solid var(--line);
        border-radius: 999px;
        padding: 4px 10px;
        height: auto;
    }
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
    footer {visibility: hidden;}
    #MainMenu {visibility: hidden;}
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
            <div class="tagline">FRED · credit · liquidite · travail · consommation · recession watch</div>
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
          americains. Il ne predit pas une recession et ne donne pas de signal d'investissement :
          il aide a prioriser les familles de donnees a lire quand le cycle se tend.
        </div>
        <div class="faq-grid">
          <div class="faq-card"><strong>Perimetre</strong> Le tableau agrège des series FRED sur credit menages, banques, liquidite, corporate, immobilier, travail, consommation et SLOOS.</div>
          <div class="faq-card"><strong>Score</strong> Les series sont transformees en z-scores signes. Une hausse du score indique davantage de stress relatif au regime recent de la serie.</div>
          <div class="faq-card"><strong>Backtest</strong> Les poids empiriques viennent de la reaction observee avant les recessions NBER de 1990, 2001, 2007-2009 et 2020.</div>
          <div class="faq-card"><strong>Lecture</strong> Le score global est un raccourci. La composition par famille et les dix indicateurs les plus tendus comptent davantage que le chiffre seul.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.expander("Que mesure le dashboard ?", expanded=True):
        st.markdown(
            """
            Il suit des indicateurs macro et financiers americains qui peuvent se degrader avant ou
            pendant un ralentissement : defauts de paiement, reserves bancaires, conditions financieres,
            courbe des taux, spreads credit, immobilier, marche du travail, consommation et enquete SLOOS.

            Le dashboard sert a reperer les canaux de transmission du stress, pas a annoncer une date de recession.
            """
        )

    with st.expander("Comment est construit le score ?"):
        st.markdown(
            """
            Chaque serie est comparee a son propre historique recent via un z-score sur cinq ans.
            Quand c'est pertinent, le calcul ajoute aussi un ecart au regime pre-COVID et un signal de momentum.

            Le sens du risque est explicite dans le catalogue : certaines series sont dangereuses quand elles montent,
            d'autres quand elles baissent.
            """
        )

    with st.expander("Pourquoi des poids empiriques ?"):
        st.markdown(
            """
            Tous les signaux ne valent pas la meme chose. Le backtest mesure la reaction de chaque serie
            avant les recessions NBER disponibles dans l'echantillon. Les series historiquement plus parlantes
            recoivent un poids plus eleve dans le score agrege.
            """
        )

    with st.expander("Comment lire les seuils vigilance et danger ?"):
        st.markdown(
            f"""
            Le seuil vigilance est fixe a `{ZSCORE_WARNING}` et le seuil danger a `{ZSCORE_DANGER}`.
            Ils expriment un stress relatif a l'historique de la serie, pas une probabilite officielle de recession.
            """
        )

    with st.expander("Quelles sont les sources ?"):
        st.markdown(
            """
            La source operationnelle est FRED, la base de donnees de la Federal Reserve Bank of St. Louis.
            Les recessions utilisees pour le backtest reprennent les dates NBER codees dans le catalogue.

            Une cle `FRED_API_KEY` doit etre configuree cote serveur pour charger les donnees. Elle n'est jamais
            affichee dans l'interface.
            """
        )

    with st.expander("Quelles sont les limites importantes ?"):
        st.markdown(
            """
            Les donnees peuvent etre revisees, certaines series sont trimestrielles, et les regimes economiques changent.
            Le score ne remplace pas une analyse macro complete, une lecture de la Fed, du fiscal, des profits,
            des conditions de marche ou des valorisations.
            """
        )


def status_color(score, warning=ZSCORE_WARNING, danger=ZSCORE_DANGER):
    if pd.isna(score):
        return "#6f9b94"
    if score >= danger:
        return "#ff4d87"
    if score >= warning:
        return "#f5b13d"
    if score > 0:
        return "#5eead4"
    return "#00f0d0"


# ============================================================
# HEADER + NAVIGATION
# ============================================================

view = current_view()
render_header(view)

if view == "faq":
    render_faq_page()
    render_site_footer()
    st.stop()

st.markdown(
    """
    <div class="help-card">
      <strong>Perimetre.</strong> Radar macro US base sur FRED : credit menages, stress bancaire,
      liquidite, corporate, immobilier, travail, consommation et SLOOS. Les scores sont relatifs
      aux regimes historiques de chaque serie.
    </div>
    """,
    unsafe_allow_html=True,
)

refresh_left, refresh_right = st.columns([5, 1])
with refresh_right:
    if st.button("Refresh data", use_container_width=True):
        st.cache_data.clear()
        st.rerun()


# ============================================================
# CHARGEMENT DES DONNÉES
# ============================================================

with st.spinner("Chargement des données FRED (cache 6h)..."):
    all_data, errors = fetch_all_series(start='1985-01-01')

if errors:
    with st.expander(f"⚠️ {len(errors)} séries n'ont pas pu être téléchargées"):
        for sid, err in errors:
            st.text(f"{sid}: {err}")

df = compute_dashboard(all_data)

with st.spinner("Backtest sur 4 récessions NBER (cache 24h)..."):
    bt = compute_predictive_power(all_data, tuple(sorted(all_data.keys())))

df = apply_weights(df, bt)

# Score global et par famille
gscore = global_score(df)
fam_scores_df = family_scores(df)


# ============================================================
# SECTION 1 - TOP KPIs
# ============================================================

st.markdown("## 📊 INDICATEURS PRINCIPAUX")

# Reconstruction historique pour percentile et tendances
power_map = dict(zip(bt['series_id'], bt['pred_power']))
weights_map = {sid: power_to_weight(p) for sid, p in power_map.items()}

with st.spinner("Reconstruction historique 1990-aujourd'hui (cache 24h)..."):
    hist_df = reconstruct_historical_score(all_data, tuple(sorted(all_data.keys())), weights_map)

# Calculs de tendance
g_series = hist_df['global']
current_hist = g_series.iloc[-1]
m1 = g_series.asof(g_series.index[-1] - pd.DateOffset(months=1))
m3 = g_series.asof(g_series.index[-1] - pd.DateOffset(months=3))
m12 = g_series.asof(g_series.index[-1] - pd.DateOffset(years=1))
percentile = (g_series <= current_hist).mean() * 100


def kpi_card(label, value, delta=None, color=None):
    color = color or '#00f0d0'
    delta_html = f'<div class="kpi-delta">{delta}</div>' if delta else ''
    return f"""
    <div class="kpi-card" style="border-left-color: {color};">
        <div class="kpi-label">{label}</div>
        <div class="kpi-value" style="color: {color};">{value}</div>
        {delta_html}
    </div>
    """


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
        {kpi_card("Famille #1 stress", f"{FAMILY_LABELS[fam_name]} {top_fam['score']:+.2f}", "Canal le plus tendu", status_color(top_fam["score"]))}
    </div>
    """,
    unsafe_allow_html=True,
)


st.markdown("---")


# ============================================================
# SECTION 2 - GRILLE 2x2 PRINCIPALE
# ============================================================

row1_col1, row1_col2 = st.columns([1, 1])


# BLOC HISTORIQUE
with row1_col1:
    st.markdown("### 📈 Score composite historique (1990 → now)")
    
    fig_hist = go.Figure()
    fig_hist.add_trace(go.Scatter(
        x=g_series.index, y=g_series.values,
        mode='lines',
        line=dict(color='#5eead4', width=1.8),
        fill='tozeroy',
        fillcolor='rgba(94, 234, 212, 0.10)',
        hovertemplate='<b>%{x|%b %Y}</b><br>Score: %{y:+.2f}<extra></extra>',
        name='Score',
    ))
    # Récessions NBER
    for start, end in NBER_RECESSION_PERIODS:
        fig_hist.add_vrect(
            x0=start, x1=end,
            fillcolor='rgba(192, 48, 40, 0.2)',
            line_width=0,
            layer='below',
        )
    # Seuils
    fig_hist.add_hline(y=0, line_dash='dot', line_color='rgba(255,255,255,0.25)', line_width=1)
    fig_hist.add_hline(y=ZSCORE_WARNING, line_dash='dash', line_color='#f5b13d', line_width=1,
                       annotation_text='Vigilance', annotation_position='right',
                       annotation_font_color='#f5b13d')
    fig_hist.add_hline(y=ZSCORE_DANGER, line_dash='dash', line_color='#ff4d87', line_width=1,
                       annotation_text='Danger', annotation_position='right',
                       annotation_font_color='#ff4d87')
    # Marker aujourd'hui
    fig_hist.add_trace(go.Scatter(
        x=[g_series.index[-1]], y=[current_hist],
        mode='markers',
        marker=dict(size=12, color='#f5f6f8', line=dict(color='#5eead4', width=2)),
        showlegend=False,
        hovertemplate=f'<b>Maintenant</b><br>Score: {current_hist:+.2f}<extra></extra>',
    ))
    fig_hist.update_layout(
        template='plotly_dark',
        plot_bgcolor='#1a1a1a',
        paper_bgcolor='#1a1a1a',
        height=350,
        margin=dict(l=10, r=10, t=10, b=10),
        showlegend=False,
        font=dict(color='#b8fff5', family='ui-monospace, SFMono-Regular, Menlo, Consolas, monospace'),
        xaxis=dict(gridcolor='rgba(0,240,208,0.08)', showgrid=True),
        yaxis=dict(gridcolor='rgba(0,240,208,0.08)', showgrid=True, title='Score'),
    )
    st.plotly_chart(fig_hist, use_container_width=True)


# BLOC FAMILLES
with row1_col2:
    st.markdown("### 🌡️ Scores par famille")
    
    fam_data = fam_scores_df.copy()
    fam_data['label'] = fam_data.index.map(lambda x: f"{FAMILY_ICONS[x]} {FAMILY_LABELS[x]}")
    fam_data['color'] = fam_data['score'].apply(status_color)
    fam_data = fam_data.sort_values('score', ascending=True)
    
    fig_fam = go.Figure()
    fig_fam.add_trace(go.Bar(
        y=fam_data['label'],
        x=fam_data['score'],
        orientation='h',
        marker_color=fam_data['color'],
        text=[f"{s:+.2f}" for s in fam_data['score']],
        textposition='outside',
        textfont=dict(color='#f5f6f8', size=11),
        hovertemplate='<b>%{y}</b><br>Score: %{x:+.2f}<extra></extra>',
    ))
    fig_fam.add_vline(x=0, line_color='rgba(255,255,255,0.25)', line_width=1)
    fig_fam.add_vline(x=ZSCORE_WARNING, line_dash='dash', line_color='#f5b13d', line_width=1)
    fig_fam.add_vline(x=ZSCORE_DANGER, line_dash='dash', line_color='#ff4d87', line_width=1)
    fig_fam.update_layout(
        template='plotly_dark',
        plot_bgcolor='#1a1a1a',
        paper_bgcolor='#1a1a1a',
        height=350,
        margin=dict(l=10, r=40, t=10, b=10),
        showlegend=False,
        font=dict(color='#b8fff5', family='ui-monospace, SFMono-Regular, Menlo, Consolas, monospace'),
        xaxis=dict(gridcolor='rgba(0,240,208,0.08)', range=[-1.5, max(3, fam_data['score'].max() + 0.5)]),
        yaxis=dict(gridcolor='rgba(0,240,208,0.08)'),
    )
    st.plotly_chart(fig_fam, use_container_width=True)


# Deuxième ligne
row2_col1, row2_col2 = st.columns([1, 1])


# TOP 10 STRESSES
with row2_col1:
    st.markdown("### Top 10 indicateurs stresses (live)")
    
    top10 = df.nlargest(10, 'stress_weighted')[
        ['famille', 'series_id', 'name', 'current', 'stress_final', 'weight', 'stress_weighted']
    ].copy()
    top10.insert(0, 'Statut', top10['stress_weighted'].apply(status_emoji))
    top10['Tier'] = top10['weight'].apply(lambda w: 'T1' if w >= 2.5 else 'T2' if w >= 1.5 else 'T3')
    top10['Famille'] = top10['famille'].map(FAMILY_LABELS)
    top10['Z brut'] = top10['stress_final'].round(2)
    top10['Score'] = top10['stress_weighted'].round(2)
    top10['Valeur'] = top10['current'].apply(lambda v: f"{v:,.2f}" if abs(v) < 10000 else f"{v:,.0f}")
    
    display_cols = ['Statut', 'Tier', 'Famille', 'series_id', 'name', 'Valeur', 'Z brut', 'Score']
    display = top10[display_cols].rename(columns={'series_id': 'Code', 'name': 'Indicateur'})
    
    st.dataframe(
        display,
        hide_index=True,
        use_container_width=True,
        height=400,
    )


# ALARMES & TENDANCES
with row2_col2:
    st.markdown("### Mouvements par famille (3 mois)")
    
    movements = []
    for fc in [c for c in hist_df.columns if c.startswith('fam_')]:
        fname = fc.replace('fam_', '')
        cur_v = hist_df[fc].iloc[-1]
        prev_v = hist_df[fc].asof(hist_df.index[-1] - pd.DateOffset(months=3))
        if pd.notna(prev_v):
            movements.append({
                'famille': fname,
                'actuel': cur_v,
                'il_y_a_3m': prev_v,
                'delta': cur_v - prev_v,
                'percentile': (hist_df[fc] <= cur_v).mean() * 100,
            })
    
    mov_df = pd.DataFrame(movements).sort_values('delta', ascending=False)
    
    fig_mov = go.Figure()
    colors = ['#ff4d87' if d > 0.1 else '#5eead4' if d < -0.1 else '#6f9b94' for d in mov_df['delta']]
    labels = [f"{FAMILY_ICONS[f]} {FAMILY_LABELS[f]}" for f in mov_df['famille']]
    fig_mov.add_trace(go.Bar(
        y=labels[::-1],
        x=mov_df['delta'].values[::-1],
        orientation='h',
        marker_color=colors[::-1],
        text=[f"{d:+.2f}" for d in mov_df['delta'].values[::-1]],
        textposition='outside',
        textfont=dict(color='#f5f6f8', size=11),
        hovertemplate='<b>%{y}</b><br>Δ 3M: %{x:+.2f}<extra></extra>',
    ))
    fig_mov.add_vline(x=0, line_color='rgba(255,255,255,0.25)', line_width=1)
    fig_mov.update_layout(
        template='plotly_dark',
        plot_bgcolor='#1a1a1a',
        paper_bgcolor='#1a1a1a',
        height=400,
        margin=dict(l=10, r=40, t=10, b=10),
        showlegend=False,
        font=dict(color='#b8fff5', family='ui-monospace, SFMono-Regular, Menlo, Consolas, monospace'),
        xaxis=dict(gridcolor='rgba(0,240,208,0.08)', title='Δ score sur 3 mois'),
        yaxis=dict(gridcolor='rgba(0,240,208,0.08)'),
    )
    st.plotly_chart(fig_mov, use_container_width=True)


st.markdown("---")


# ============================================================
# SECTION 3 - DETAIL PAR FAMILLE
# ============================================================

st.markdown("## 🔬 Détail par famille")

tabs = st.tabs([f"{FAMILY_ICONS[f]} {FAMILY_LABELS[f]}" for f in fam_scores_df.index])

for tab, famille in zip(tabs, fam_scores_df.index):
    with tab:
        sub = df[df['famille'] == famille].sort_values('stress_weighted', ascending=False).copy()
        
        col_a, col_b = st.columns([2, 3])
        with col_a:
            score = fam_scores_df.loc[famille, 'score']
            st.metric(
                label=f"Score famille",
                value=f"{score:+.2f}",
                delta=None,
            )
            st.caption(f"{int(fam_scores_df.loc[famille, 'n'])} series - max: {fam_scores_df.loc[famille, 'max']:+.2f}")
        
        with col_b:
            sub['Statut'] = sub['stress_weighted'].apply(status_emoji)
            sub['Tier'] = sub['weight'].apply(lambda w: 'T1' if w >= 2.5 else 'T2' if w >= 1.5 else 'T3')
            sub['Score'] = sub['stress_weighted'].round(2)
            sub['Z brut'] = sub['stress_final'].round(2)
            sub['Valeur'] = sub['current'].apply(lambda v: f"{v:,.2f}" if abs(v) < 10000 else f"{v:,.0f}")
            display = sub[['Statut', 'Tier', 'series_id', 'name', 'Valeur', 'Z brut', 'Score']].rename(
                columns={'series_id': 'Code', 'name': 'Indicateur'}
            )
            st.dataframe(display, hide_index=True, use_container_width=True)


# ============================================================
# FOOTER
# ============================================================

st.markdown(
    f"""
    <div class="help-card">
      <strong>Sources et methode.</strong> Donnees FRED (St. Louis Fed). Methodologie :
      z-score 5Y, drift pre-COVID, momentum et ponderation empirique calibree par backtest.
      Cache 6h. Dernier calcul : {datetime.now().strftime('%H:%M')}. Perimetre : {len(df)} series / 8 familles.
    </div>
    """,
    unsafe_allow_html=True,
)
render_site_footer()
