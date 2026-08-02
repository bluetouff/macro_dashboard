"""Accès FRED et wrappers de cache pour l'application locale."""

from __future__ import annotations

import os
from collections.abc import Mapping

import pandas as pd
import streamlit as st
from fredapi import Fred

from catalog import SERIES_CATALOG
from scoring import (
    apply_weights,
    calibration_to_weight,
    compute_dashboard,
    family_scores,
    global_score,
)
from scoring import (
    compute_empirical_calibration as _compute_empirical_calibration,
)
from scoring import (
    reconstruct_historical_score as _reconstruct_historical_score,
)


def get_fred() -> Fred:
    """Construit le client FRED depuis l'environnement, sans exposer la clé."""
    key = os.environ.get('FRED_API_KEY')
    if not key:
        st.error("Clé FRED absente. Configurez `FRED_API_KEY` dans l'environnement local.")
        st.stop()
    return Fred(api_key=key)


@st.cache_data(ttl=6 * 3600, show_spinner=False)
def fetch_all_series(start: str = '1985-01-01') -> tuple[dict[str, pd.Series], list[tuple[str, str]]]:
    """Télécharge le catalogue FRED avec progression et cache de six heures."""
    fred = get_fred()
    all_data: dict[str, pd.Series] = {}
    errors: list[tuple[str, str]] = []
    expected = sum(len(series) for series in SERIES_CATALOG.values())
    progress = st.progress(0.0)
    status = st.empty()
    count = 0

    for family, series_dict in SERIES_CATALOG.items():
        for sid in series_dict:
            count += 1
            status.text(f"FRED · {family} · {sid} · {count}/{expected}")
            progress.progress(count / expected)
            try:
                series = fred.get_series(sid, observation_start=start).dropna().sort_index()
                if len(series) > 0:
                    all_data[sid] = series
                else:
                    errors.append((sid, 'série vide'))
            except Exception as exc:  # L'erreur est affichée sans secret ni traceback.
                errors.append((sid, type(exc).__name__))

    progress.empty()
    status.empty()
    return all_data, errors


@st.cache_data(ttl=24 * 3600, show_spinner=False)
def compute_empirical_calibration(
    _all_data: Mapping[str, pd.Series],
    all_data_keys: tuple[str, ...],
) -> pd.DataFrame:
    """Wrapper Streamlit du backtest pur."""
    del all_data_keys
    return _compute_empirical_calibration(_all_data)


@st.cache_data(ttl=24 * 3600, show_spinner=False)
def reconstruct_historical_score(
    _all_data: Mapping[str, pd.Series],
    all_data_keys: tuple[str, ...],
    weights_map: Mapping[str, float],
) -> pd.DataFrame:
    """Wrapper Streamlit de la reconstruction historique pure."""
    del all_data_keys
    return _reconstruct_historical_score(_all_data, weights_map)


__all__ = [
    'apply_weights',
    'compute_dashboard',
    'compute_empirical_calibration',
    'family_scores',
    'fetch_all_series',
    'global_score',
    'calibration_to_weight',
    'reconstruct_historical_score',
]
