"""Application locale du US Macro Risk Monitor.

Cette variante collecte FRED directement. La production publique utilise
``app_server.py`` et ne possède aucune clé FRED.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime

import streamlit as st

from catalog import METHODOLOGY_VERSION, SERIES_CATALOG
from dashboard_view import render_dashboard, render_method_faq
from data import (
    apply_weights,
    calibration_to_weight,
    compute_dashboard,
    compute_empirical_calibration,
    fetch_all_series,
    reconstruct_historical_score,
)
from ui import configure_page, inject_theme, query_view

configure_page()
inject_theme()

expected_count = sum(len(series) for series in SERIES_CATALOG.values())

with st.spinner('Collecte FRED et vérification du catalogue…'):
    all_data, errors = fetch_all_series()

if errors or len(all_data) != expected_count:
    st.error(
        f'Collecte incomplète : {len(all_data)}/{expected_count} séries. '
        'Le score est volontairement indisponible tant que la couverture n’est pas complète.'
    )
    if errors:
        st.caption('Séries en erreur : ' + ', '.join(series_id for series_id, _ in errors))
    st.stop()

keys = tuple(sorted(all_data))
with st.spinner('Calcul du backtest et de la pénalité de faux positifs…'):
    backtest = compute_empirical_calibration(all_data, keys)
    current = apply_weights(compute_dashboard(all_data), backtest)
    weights = {
        series_id: calibration_to_weight(calibration)
        for series_id, calibration in zip(
            backtest['series_id'], backtest['calibration_net'], strict=False
        )
    }

with st.spinner('Reconstruction mensuelle sans look-ahead…'):
    historical = reconstruct_historical_score(all_data, keys, weights)

now = datetime.now(UTC)
metadata = {
    'methodology_version': METHODOLOGY_VERSION,
    'calculator_revision': os.environ.get('MACRO_DASHBOARD_SOURCE_SHA', 'local-unversioned'),
    'generated_at': now.isoformat().replace('+00:00', 'Z'),
    'source': 'FRED · Federal Reserve Bank of St. Louis',
    'n_series_loaded': len(current),
    'n_series_expected': expected_count,
    'quality_status': 'local-live',
    'delivery_mode': 'local-live',
}

if query_view() == 'faq':
    render_method_faq(metadata)
else:
    render_dashboard(current, backtest, historical, metadata)
