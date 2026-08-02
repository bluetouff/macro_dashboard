"""Vue commune du dashboard, utilisée en local comme en production."""

from __future__ import annotations

from html import escape
from typing import Any

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from catalog import (
    FAMILY_LABELS,
    NBER_RECESSION_PERIODS,
    STRESS_COMPONENT_WEIGHTS,
    ZSCORE_DANGER,
    ZSCORE_WARNING,
)
from scoring import family_scores, global_score, status_level
from ui import METHOD_URL, render_footer, render_header, render_hero, render_quality_banner, section_heading

PLOT_CONFIG = {
    'displayModeBar': False,
    'displaylogo': False,
    'responsive': True,
    'scrollZoom': False,
}
COLORS = {
    'bg': 'rgba(0,0,0,0)',
    'grid': 'rgba(255,255,255,.075)',
    'paper': '#e7e9ee',
    'muted': '#8b909b',
    'signal': '#5eead4',
    'accent': '#ff4d87',
    'amber': '#f5b13d',
    'surface': '#121419',
}


def _finite(value: object) -> bool:
    try:
        return bool(pd.notna(value) and np.isfinite(float(value)))
    except (TypeError, ValueError):
        return False


def _format_score(value: object, *, signed: bool = True) -> str:
    if not _finite(value):
        return 'n/d'
    return f'{float(value):+.2f}' if signed else f'{float(value):.2f}'


def _history_value(history: pd.Series, *, months: int) -> float:
    clean = history.dropna().sort_index()
    if clean.empty:
        return np.nan
    target = pd.Timestamp(clean.index.max()) - pd.DateOffset(months=months)
    try:
        value = clean.asof(target)
    except (TypeError, ValueError):
        return np.nan
    return float(value) if _finite(value) else np.nan


def _delta(current: float, prior: float) -> float:
    return current - prior if _finite(current) and _finite(prior) else np.nan


def _chart_layout(*, height: int = 410) -> dict[str, Any]:
    return {
        'height': height,
        'margin': {'l': 12, 'r': 12, 't': 24, 'b': 18},
        'paper_bgcolor': COLORS['bg'],
        'plot_bgcolor': COLORS['bg'],
        'font': {
            'family': 'Inter, -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif',
            'color': COLORS['muted'],
            'size': 11,
        },
        'hoverlabel': {
            'bgcolor': COLORS['surface'],
            'bordercolor': 'rgba(255,255,255,.18)',
            'font': {'color': COLORS['paper'], 'family': 'SFMono-Regular, Menlo, monospace'},
        },
        'xaxis': {
            'showgrid': False,
            'zeroline': False,
            'linecolor': COLORS['grid'],
            'tickfont': {'color': COLORS['muted']},
        },
        'yaxis': {
            'gridcolor': COLORS['grid'],
            'zerolinecolor': 'rgba(255,255,255,.22)',
            'tickfont': {'color': COLORS['muted']},
        },
        'legend': {
            'orientation': 'h',
            'yanchor': 'bottom',
            'y': 1.02,
            'xanchor': 'left',
            'x': 0,
            'font': {'size': 10},
        },
    }


def _risk_tag(score: float) -> str:
    level = status_level(score)
    return f'<span class="risk-tag {escape(level)}">{escape(level)}</span>'


def _render_kpis(current: pd.DataFrame, historical: pd.DataFrame) -> None:
    current_score = global_score(current)
    family = family_scores(current)
    history = historical['global'].dropna().sort_index()
    historical_latest = float(history.iloc[-1]) if not history.empty else np.nan
    delta_3m = _delta(historical_latest, _history_value(history, months=3))
    delta_12m = _delta(historical_latest, _history_value(history, months=12))
    top_family = family.index[0] if not family.empty else ''
    top_family_label = FAMILY_LABELS.get(top_family, top_family) if top_family else 'n/d'
    top_family_score = float(family.iloc[0]['score']) if not family.empty else np.nan
    max_source_date = pd.to_datetime(current['date']).max()
    source_date = max_source_date.strftime('%d/%m/%Y') if pd.notna(max_source_date) else 'n/d'
    html = f"""
<div class="kpi-grid">
  <div class="kpi-card primary"><div class="kpi-label">Score global courant</div><div class="kpi-value">{_format_score(current_score)}</div><div class="kpi-detail">{_risk_tag(current_score)}</div></div>
  <div class="kpi-card"><div class="kpi-label">Historique reconstruit</div><div class="kpi-value">{_format_score(historical_latest)}</div><div class="kpi-detail">Méthode actuelle · fin de mois</div></div>
  <div class="kpi-card"><div class="kpi-label">Variation 3 mois</div><div class="kpi-value">{_format_score(delta_3m)}</div><div class="kpi-detail">Sur la reconstruction mensuelle</div></div>
  <div class="kpi-card"><div class="kpi-label">Variation 12 mois</div><div class="kpi-value">{_format_score(delta_12m)}</div><div class="kpi-detail">Sur la reconstruction mensuelle</div></div>
  <div class="kpi-card"><div class="kpi-label">Famille la plus tendue</div><div class="kpi-value" style="font-size:1.05rem;letter-spacing:-.02em">{escape(top_family_label)}</div><div class="kpi-detail">score {_format_score(top_family_score)}</div></div>
  <div class="kpi-card"><div class="kpi-label">Dernière observation</div><div class="kpi-value" style="font-size:1.15rem;letter-spacing:-.03em">{escape(source_date)}</div><div class="kpi-detail">{len(current)} séries validées</div></div>
</div>
"""
    st.markdown(html, unsafe_allow_html=True)


def _render_historical_chart(historical: pd.DataFrame) -> None:
    figure = go.Figure()
    figure.add_trace(
        go.Scatter(
            x=historical.index,
            y=historical['global'],
            name='Score composite',
            mode='lines',
            line={'color': COLORS['signal'], 'width': 2.2},
            fill='tozeroy',
            fillcolor='rgba(94,234,212,.045)',
            hovertemplate='%{x|%b %Y}<br>score %{y:+.2f}<extra></extra>',
        )
    )
    figure.add_hline(
        y=ZSCORE_WARNING,
        line={'color': COLORS['amber'], 'width': 1, 'dash': 'dot'},
        annotation_text='vigilance',
        annotation_font={'color': COLORS['amber'], 'size': 10},
        annotation_position='top left',
    )
    figure.add_hline(
        y=ZSCORE_DANGER,
        line={'color': COLORS['accent'], 'width': 1, 'dash': 'dot'},
        annotation_text='danger',
        annotation_font={'color': COLORS['accent'], 'size': 10},
        annotation_position='top left',
    )
    for start, end in NBER_RECESSION_PERIODS:
        figure.add_vrect(
            x0=start,
            x1=end,
            fillcolor='rgba(255,255,255,.055)',
            line_width=0,
            layer='below',
        )
    layout = _chart_layout(height=440)
    layout['yaxis']['title'] = 'z-score signé agrégé'
    layout['hovermode'] = 'x unified'
    figure.update_layout(**layout)
    st.plotly_chart(figure, width='stretch', config=PLOT_CONFIG)


def _render_family_cards(current: pd.DataFrame) -> None:
    scores = family_scores(current)
    cards: list[str] = []
    for family, row in scores.iterrows():
        score = float(row['score'])
        intensity = min(abs(score) / max(ZSCORE_DANGER, 0.01), 1.0)
        cards.append(
            '<div class="family-card" style="--intensity:'
            f'{intensity:.3f}"><div class="family-name">{escape(FAMILY_LABELS.get(family, family))}</div>'
            f'<div class="family-value">{_format_score(score)}</div>'
            f'<div class="family-meta">{int(row["n"])} séries · pic {_format_score(row["max"])}</div>'
            f'<div style="margin-top:18px">{_risk_tag(score)}</div></div>'
        )
    st.markdown(f'<div class="family-grid">{"".join(cards)}</div>', unsafe_allow_html=True)


def _render_family_chart(current: pd.DataFrame) -> None:
    scores = family_scores(current).sort_values('score')
    labels = [FAMILY_LABELS.get(value, value) for value in scores.index]
    colors = [
        COLORS['accent'] if value >= ZSCORE_DANGER else COLORS['amber'] if value >= ZSCORE_WARNING else COLORS['signal']
        for value in scores['score']
    ]
    figure = go.Figure(
        go.Bar(
            x=scores['score'],
            y=labels,
            orientation='h',
            marker={'color': colors, 'line': {'width': 0}},
            text=[_format_score(value) for value in scores['score']],
            textposition='outside',
            textfont={'family': 'SFMono-Regular, Menlo, monospace', 'color': COLORS['paper'], 'size': 10},
            hovertemplate='%{y}<br>score %{x:+.2f}<extra></extra>',
        )
    )
    layout = _chart_layout(height=350)
    layout['xaxis']['title'] = 'stress relatif'
    layout['xaxis']['range'] = [min(-0.2, float(scores['score'].min()) - 0.25), max(0.4, float(scores['score'].max()) + 0.45)]
    layout['yaxis']['gridcolor'] = 'rgba(0,0,0,0)'
    figure.update_layout(**layout)
    st.plotly_chart(figure, width='stretch', config=PLOT_CONFIG)


def _series_table(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy().sort_values('stress_final', ascending=False)
    result['Niveau'] = result['stress_final'].apply(status_level).str.upper()
    result['Observation'] = pd.to_datetime(result['date']).dt.strftime('%Y-%m-%d')
    if 'false_positive_rate' in result:
        result['false_positive_rate'] = pd.to_numeric(result['false_positive_rate'], errors='coerce') * 100
    result = result.rename(
        columns={
            'series_id': 'FRED',
            'name': 'Série',
            'current': 'Valeur',
            'unit': 'Unité',
            'signed_zscore': 'Z signé',
            'drift_zscore_equiv': 'Drift eq.',
            'momentum_zscore_equiv': 'Momentum eq.',
            'stress_final': 'Score',
            'calibration_net': 'Calibration nette',
            'false_positive_rate': 'Faux positifs',
            'weight': 'Poids',
        }
    )
    columns = [
        'Niveau',
        'FRED',
        'Série',
        'Valeur',
        'Unité',
        'Score',
        'Z signé',
        'Drift eq.',
        'Momentum eq.',
        'Poids',
        'Calibration nette',
        'Faux positifs',
        'Observation',
    ]
    return result[[column for column in columns if column in result.columns]]


def _render_detail(current: pd.DataFrame, backtest: pd.DataFrame) -> None:
    merged = current.merge(
        backtest[['series_id', 'false_positive_rate', 'n_nonrec_obs']],
        on='series_id',
        how='left',
        validate='one_to_one',
    )
    labels = [FAMILY_LABELS.get(family, family) for family in FAMILY_LABELS]
    tabs = st.tabs(labels)
    for tab, family in zip(tabs, FAMILY_LABELS, strict=False):
        with tab:
            subset = merged.loc[merged['famille'] == family]
            st.dataframe(
                _series_table(subset),
                hide_index=True,
                width='stretch',
                column_config={
                    'Valeur': st.column_config.NumberColumn(format='%.2f'),
                    'Score': st.column_config.NumberColumn(format='%+.2f'),
                    'Z signé': st.column_config.NumberColumn(format='%+.2f'),
                    'Drift eq.': st.column_config.NumberColumn(format='%+.2f'),
                    'Momentum eq.': st.column_config.NumberColumn(format='%+.2f'),
                    'Poids': st.column_config.NumberColumn(format='%.1f'),
                    'Calibration nette': st.column_config.NumberColumn(format='%+.2f'),
                    'Faux positifs': st.column_config.NumberColumn(format='%.1f%%'),
                },
            )


def _render_top_tensions(current: pd.DataFrame) -> None:
    top = current.nlargest(8, 'stress_final')
    cards = []
    for rank, row in enumerate(top.itertuples(index=False), start=1):
        cards.append(
            f'<strong>{rank:02d} · {escape(str(row.series_id))}</strong> '
            f'{escape(str(row.name))} · score {_format_score(row.stress_final)} · poids {float(row.weight):.1f}'
        )
    st.markdown(
        '<div class="insight-card">' + '<br>'.join(cards) + '</div>',
        unsafe_allow_html=True,
    )


def render_method_faq(metadata: dict[str, Any]) -> None:
    render_header('faq')
    render_hero(metadata)
    section_heading(
        'Une méthode lisible, versionnée, réfutable',
        'Le score organise les signaux. Il ne produit ni probabilité de récession, ni date cible, ni conseil d’investissement.',
        'book',
    )
    z_weight = STRESS_COMPONENT_WEIGHTS['zscore']
    drift_weight = STRESS_COMPONENT_WEIGHTS['drift']
    momentum_weight = STRESS_COMPONENT_WEIGHTS['momentum']
    st.markdown(
        f"""
<div class="method-grid">
  <div class="method-step"><div class="step-no">01 · ORIENTER</div><h3>Sens du risque</h3><p>Chaque série FRED est signée. Une valeur positive représente toujours davantage de stress relatif, même lorsque la baisse de la donnée brute constitue le signal.</p></div>
  <div class="method-step"><div class="step-no">02 · NORMALISER</div><h3>Trois composantes</h3><p>Z-score glissant sur cinq ans, drift face au régime 2015–2019 lorsque pertinent, momentum calendaire à trois et douze mois.</p></div>
  <div class="method-step"><div class="step-no">03 · AGRÉGER</div><h3>Moyenne disponible</h3><p>{z_weight:.0%} z-score, {drift_weight:.0%} drift, {momentum_weight:.0%} momentum. Chaque composante est bornée à ±5, puis les poids sont renormalisés lorsqu’une composante est absente.</p></div>
</div>
<div class="method-card"><strong>Calibrage interne, pas validation prédictive.</strong> Le score est observé à 3, 6 et 12 mois avant les quatre récessions NBER codées. Une pénalité réduit ensuite le poids des séries qui franchissent trop souvent le seuil de vigilance hors récession. Ce calibrage est in-sample et quatre épisodes restent un échantillon très limité.</div>
<div class="method-card" style="margin-top:10px"><strong>Historique affiché.</strong> Il s’agit d’une reconstruction rétrospective avec la méthodologie, les poids et les vintages FRED actuels. Les observations datées après chaque point sont exclues, mais les délais de publication et les révisions historiques ne sont pas rejoués comme dans une base point-in-time ALFRED.</div>
""",
        unsafe_allow_html=True,
    )
    section_heading('Questions fréquentes', 'Les limites importantes font partie du produit, pas des notes de bas de page.', 'shield')
    st.markdown(
        f"""
<div class="faq-grid">
  <div class="faq-card"><strong>Le score est-il une probabilité de récession ?</strong>Non. C’est un z-score signé et agrégé. Il mesure un écart relatif à l’historique des séries incluses.</div>
  <div class="faq-card"><strong>Pourquoi le score courant peut-il différer du dernier point historique ?</strong>Le courant utilise la dernière observation disponible de chaque série. La reconstruction est mensuelle et s’arrête au premier jour de chaque mois.</div>
  <div class="faq-card"><strong>Les données sont-elles définitives ?</strong>Non. FRED republie des séries provenant de producteurs multiples et certaines observations sont révisées. Cette reconstruction utilise les vintages actuels, pas les publications connues à chaque date passée.</div>
  <div class="faq-card"><strong>Peut-on comparer ce chiffre aux autres dashboards l0g ?</strong>Pas directement. Les normalisations et périmètres diffèrent. Il faut comparer les méthodologies avant les niveaux affichés.</div>
  <div class="faq-card"><strong>Que signifie une composante absente ?</strong>Le drift ou le momentum est désactivé lorsqu’il serait économiquement trompeur. La moyenne est alors renormalisée sur les composantes valides, sans remplacer l’absence par zéro.</div>
  <div class="faq-card"><strong>Où auditer la méthode complète ?</strong>La <a href="{METHOD_URL}" target="_blank" rel="noopener noreferrer">méthodologie canonique l0g</a> documente le périmètre, les transformations, les seuils et les limites.</div>
</div>
""",
        unsafe_allow_html=True,
    )
    render_footer(metadata)


def render_dashboard(
    current: pd.DataFrame,
    backtest: pd.DataFrame,
    historical: pd.DataFrame,
    metadata: dict[str, Any],
) -> None:
    """Rend le radar public depuis un bundle déjà validé."""
    render_header('radar')
    render_hero(metadata)
    render_quality_banner(metadata)
    _render_kpis(current, historical)

    section_heading(
        'Trajectoire du stress composite',
        'Reconstruction mensuelle avec les vintages FRED actuels, tronquée par date d’observation. Bandes grises : récessions NBER. Il ne s’agit pas d’un backtest point-in-time.',
        'trend',
    )
    _render_historical_chart(historical)

    section_heading(
        'Lecture par famille',
        'Moyenne pondérée des séries valides de chaque bloc. Le pic signale la série la plus tendue, sans se substituer à la moyenne.',
        'layers',
    )
    _render_family_cards(current)
    _render_family_chart(current)

    section_heading(
        'Tensions dominantes',
        'Classement par score composite de série. Le poids empirique intervient ensuite dans l’agrégation globale.',
        'pulse',
    )
    _render_top_tensions(current)

    section_heading(
        'Registre des indicateurs',
        'Valeur source, composantes, score, poids et taux de faux positifs sont exposés pour audit. Les cases vides correspondent à des composantes volontairement non applicables.',
        'table',
    )
    _render_detail(current, backtest)
    render_footer(metadata)
