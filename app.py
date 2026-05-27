"""
US Macro Risk Dashboard — Tableau de bord style Bloomberg.
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
    status_emoji, status_color, reconstruct_historical_score, power_to_weight,
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

# CSS Bloomberg-style : noir, dense, monospace pour les chiffres
st.markdown("""
<style>
    /* Background */
    .main {background-color: #0a0a0a;}
    .stApp {background-color: #0a0a0a; color: #e8e8e8;}
    
    /* Titres */
    h1, h2, h3 {color: #ffaa00; font-family: 'Helvetica Neue', sans-serif;}
    h1 {border-bottom: 2px solid #ffaa00; padding-bottom: 8px;}
    
    /* KPI Cards */
    .kpi-card {
        background: linear-gradient(135deg, #1a1a1a 0%, #0f0f0f 100%);
        border-left: 4px solid #ffaa00;
        padding: 16px;
        border-radius: 4px;
        margin-bottom: 8px;
    }
    .kpi-label {
        font-size: 11px;
        color: #888;
        text-transform: uppercase;
        letter-spacing: 1px;
        margin-bottom: 4px;
    }
    .kpi-value {
        font-size: 28px;
        font-weight: 700;
        font-family: 'Courier New', monospace;
    }
    .kpi-delta {
        font-size: 12px;
        color: #888;
        margin-top: 4px;
        font-family: 'Courier New', monospace;
    }
    
    /* Family scores */
    .family-row {
        display: flex;
        justify-content: space-between;
        padding: 6px 12px;
        border-bottom: 1px solid #222;
        font-family: 'Courier New', monospace;
    }
    .family-name {color: #ccc;}
    .family-score {font-weight: bold;}
    
    /* Dataframes */
    .stDataFrame {background-color: #0f0f0f;}
    
    /* Sidebar */
    .css-1d391kg {background-color: #0a0a0a;}
    
    /* Hide footer */
    footer {visibility: hidden;}
    #MainMenu {visibility: hidden;}
</style>
""", unsafe_allow_html=True)


# ============================================================
# HEADER
# ============================================================

col_h1, col_h2, col_h3 = st.columns([3, 1, 1])
with col_h1:
    st.markdown("# 🇺🇸 US MACRO RISK DASHBOARD")
    st.caption(f"Tableau de bord macro — surveillance des signaux faibles et systémiques | {datetime.now().strftime('%A %d %B %Y, %H:%M')}")
with col_h3:
    if st.button("🔄 Refresh data", use_container_width=True):
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
# SECTION 1 — TOP KPIs (style Bloomberg)
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
    color = color or '#ffaa00'
    delta_html = f'<div class="kpi-delta">{delta}</div>' if delta else ''
    return f"""
    <div class="kpi-card" style="border-left-color: {color};">
        <div class="kpi-label">{label}</div>
        <div class="kpi-value" style="color: {color};">{value}</div>
        {delta_html}
    </div>
    """


k1, k2, k3, k4, k5 = st.columns(5)

with k1:
    st.markdown(kpi_card(
        "Score global (live)",
        f"{gscore:+.2f}",
        f"Pondéré empirique • {len(df)} séries",
        status_color(gscore),
    ), unsafe_allow_html=True)

with k2:
    st.markdown(kpi_card(
        "Score historique (recalc.)",
        f"{current_hist:+.2f}",
        f"Percentile {percentile:.0f}% (1990-now)",
        status_color(current_hist),
    ), unsafe_allow_html=True)

with k3:
    delta3 = current_hist - m3 if pd.notna(m3) else 0
    arrow = "📈" if delta3 > 0.05 else "📉" if delta3 < -0.05 else "➡️"
    st.markdown(kpi_card(
        "Tendance 3 mois",
        f"{delta3:+.2f} {arrow}",
        f"Il y a 3M : {m3:+.2f}" if pd.notna(m3) else "",
        '#c03028' if delta3 > 0.2 else '#5a8a3a' if delta3 < -0.2 else '#888',
    ), unsafe_allow_html=True)

with k4:
    delta12 = current_hist - m12 if pd.notna(m12) else 0
    arrow = "📈" if delta12 > 0.05 else "📉" if delta12 < -0.05 else "➡️"
    st.markdown(kpi_card(
        "Tendance 1 an",
        f"{delta12:+.2f} {arrow}",
        f"Il y a 1Y : {m12:+.2f}" if pd.notna(m12) else "",
        '#c03028' if delta12 > 0.2 else '#5a8a3a' if delta12 < -0.2 else '#888',
    ), unsafe_allow_html=True)

with k5:
    # Famille la plus stressée
    top_fam = fam_scores_df.iloc[0]
    fam_name = top_fam.name
    st.markdown(kpi_card(
        "Famille #1 stress",
        f"{FAMILY_ICONS[fam_name]} {top_fam['score']:+.2f}",
        FAMILY_LABELS[fam_name],
        status_color(top_fam['score']),
    ), unsafe_allow_html=True)


st.markdown("---")


# ============================================================
# SECTION 2 — GRILLE 2x2 PRINCIPALE
# ============================================================

row1_col1, row1_col2 = st.columns([1, 1])


# ─── BLOC HISTORIQUE ───
with row1_col1:
    st.markdown("### 📈 Score composite historique (1990 → now)")
    
    fig_hist = go.Figure()
    fig_hist.add_trace(go.Scatter(
        x=g_series.index, y=g_series.values,
        mode='lines',
        line=dict(color='#ffaa00', width=1.5),
        fill='tozeroy',
        fillcolor='rgba(255, 170, 0, 0.15)',
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
    fig_hist.add_hline(y=0, line_dash='dot', line_color='#666', line_width=1)
    fig_hist.add_hline(y=ZSCORE_WARNING, line_dash='dash', line_color='#e0a020', line_width=1,
                       annotation_text='Vigilance', annotation_position='right',
                       annotation_font_color='#e0a020')
    fig_hist.add_hline(y=ZSCORE_DANGER, line_dash='dash', line_color='#c03028', line_width=1,
                       annotation_text='Danger', annotation_position='right',
                       annotation_font_color='#c03028')
    # Marker aujourd'hui
    fig_hist.add_trace(go.Scatter(
        x=[g_series.index[-1]], y=[current_hist],
        mode='markers',
        marker=dict(size=12, color='#fff', line=dict(color='#ffaa00', width=2)),
        showlegend=False,
        hovertemplate=f'<b>Maintenant</b><br>Score: {current_hist:+.2f}<extra></extra>',
    ))
    fig_hist.update_layout(
        template='plotly_dark',
        plot_bgcolor='#0a0a0a',
        paper_bgcolor='#0a0a0a',
        height=350,
        margin=dict(l=10, r=10, t=10, b=10),
        showlegend=False,
        xaxis=dict(gridcolor='#222', showgrid=True),
        yaxis=dict(gridcolor='#222', showgrid=True, title='Score'),
    )
    st.plotly_chart(fig_hist, use_container_width=True)


# ─── BLOC FAMILLES ───
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
        textfont=dict(color='#fff', size=11),
        hovertemplate='<b>%{y}</b><br>Score: %{x:+.2f}<extra></extra>',
    ))
    fig_fam.add_vline(x=0, line_color='#666', line_width=1)
    fig_fam.add_vline(x=ZSCORE_WARNING, line_dash='dash', line_color='#e0a020', line_width=1)
    fig_fam.add_vline(x=ZSCORE_DANGER, line_dash='dash', line_color='#c03028', line_width=1)
    fig_fam.update_layout(
        template='plotly_dark',
        plot_bgcolor='#0a0a0a',
        paper_bgcolor='#0a0a0a',
        height=350,
        margin=dict(l=10, r=40, t=10, b=10),
        showlegend=False,
        xaxis=dict(gridcolor='#222', range=[-1.5, max(3, fam_data['score'].max() + 0.5)]),
        yaxis=dict(gridcolor='#222'),
    )
    st.plotly_chart(fig_fam, use_container_width=True)


# Deuxième ligne
row2_col1, row2_col2 = st.columns([1, 1])


# ─── TOP 10 STRESSÉS ───
with row2_col1:
    st.markdown("### 🚨 Top 10 indicateurs stressés (live)")
    
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


# ─── ALARMES & TENDANCES ───
with row2_col2:
    st.markdown("### ⚡ Mouvements par famille (3 mois)")
    
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
    colors = ['#c03028' if d > 0.1 else '#5a8a3a' if d < -0.1 else '#888' for d in mov_df['delta']]
    labels = [f"{FAMILY_ICONS[f]} {FAMILY_LABELS[f]}" for f in mov_df['famille']]
    fig_mov.add_trace(go.Bar(
        y=labels[::-1],
        x=mov_df['delta'].values[::-1],
        orientation='h',
        marker_color=colors[::-1],
        text=[f"{d:+.2f}" for d in mov_df['delta'].values[::-1]],
        textposition='outside',
        textfont=dict(color='#fff', size=11),
        hovertemplate='<b>%{y}</b><br>Δ 3M: %{x:+.2f}<extra></extra>',
    ))
    fig_mov.add_vline(x=0, line_color='#666', line_width=1)
    fig_mov.update_layout(
        template='plotly_dark',
        plot_bgcolor='#0a0a0a',
        paper_bgcolor='#0a0a0a',
        height=400,
        margin=dict(l=10, r=40, t=10, b=10),
        showlegend=False,
        xaxis=dict(gridcolor='#222', title='Δ score sur 3 mois'),
        yaxis=dict(gridcolor='#222'),
    )
    st.plotly_chart(fig_mov, use_container_width=True)


st.markdown("---")


# ============================================================
# SECTION 3 — DÉTAIL PAR FAMILLE (expander)
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
            st.caption(f"{int(fam_scores_df.loc[famille, 'n'])} séries — max: {fam_scores_df.loc[famille, 'max']:+.2f}")
        
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

st.markdown("---")
col_f1, col_f2, col_f3 = st.columns([2, 1, 1])
with col_f1:
    st.caption("📊 Données : FRED (St. Louis Fed) | Méthodologie : z-score 5Y + drift pré-COVID + momentum + pondération empirique calibrée backtest")
with col_f2:
    st.caption(f"🔄 Cache 6h | Dernier calcul : {datetime.now().strftime('%H:%M')}")
with col_f3:
    st.caption(f"Périmètre : {len(df)} séries / 8 familles")
