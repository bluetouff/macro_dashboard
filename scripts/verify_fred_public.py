#!/usr/bin/env python3
"""Vérifie le catalogue et le moteur via l'export public officiel FRED.

Ce diagnostic en lecture seule ne remplace pas le builder de production et ne
requiert aucune clé. Il sert à contrôler ponctuellement la couverture, les
fréquences déclarées, la fraîcheur et la cohérence du calcul complet.
"""

from __future__ import annotations

import io
import json
import time
import zipfile

import numpy as np
import pandas as pd
import requests

from catalog import SERIES_CATALOG
from scoring import (
    apply_weights,
    calibration_to_weight,
    compute_dashboard,
    compute_empirical_calibration,
    compute_metrics_for_series,
    family_scores,
    global_score,
    reconstruct_historical_score,
    zscore_input_series,
)
from snapshot_contract import validate_backtest, validate_current_snapshot, validate_historical

FRED_EXPORT_URL = 'https://fred.stlouisfed.org/graph/fredgraph.csv'
FREQUENCY_PREFIX = {'D': 'daily', 'W': 'weekly', 'M': 'monthly', 'Q': 'quarterly'}


def fetch_export(series_ids: list[str]) -> bytes:
    """Télécharge un lot FRED avec des reprises bornées et une erreur neutre."""
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            response = requests.get(
                FRED_EXPORT_URL,
                params={'id': ','.join(series_ids)},
                timeout=90,
            )
            response.raise_for_status()
            return response.content
        except requests.RequestException as exc:
            last_error = exc
            if attempt < 2:
                time.sleep(2**attempt)
    raise RuntimeError(
        f'export FRED indisponible après 3 tentatives ({type(last_error).__name__})'
    ) from last_error


def download_catalog() -> tuple[dict[str, pd.Series], dict[str, str]]:
    expected = {sid for family in SERIES_CATALOG.values() for sid in family}
    all_data: dict[str, pd.Series] = {}
    source_files: dict[str, str] = {}
    # L'export graphique tronque silencieusement les requêtes trop larges. Un
    # appel borné par famille garde la réponse vérifiable sans marteler FRED.
    for family in SERIES_CATALOG.values():
        requested = sorted(family)
        payload = io.BytesIO(fetch_export(requested))
        frames: list[tuple[str, pd.DataFrame]] = []
        if zipfile.is_zipfile(payload):
            with zipfile.ZipFile(payload) as archive:
                for name in archive.namelist():
                    if name.endswith('.csv'):
                        frames.append((name, pd.read_csv(archive.open(name), parse_dates=['observation_date'])))
        else:
            declared = {meta['freq'] for meta in family.values()}
            if len(declared) != 1:
                raise RuntimeError('export FRED non-ZIP inattendu pour des fréquences mixtes')
            name = f'{FREQUENCY_PREFIX[declared.pop()]}.csv'
            payload.seek(0)
            frames.append((name, pd.read_csv(payload, parse_dates=['observation_date'])))

        for name, frame in frames:
            frame = frame.set_index('observation_date').sort_index()
            for sid in frame.columns:
                series = pd.to_numeric(frame[sid], errors='coerce').dropna()
                if not series.empty:
                    all_data[sid] = series
                    source_files[sid] = name

    missing = expected - set(all_data)
    extra = set(all_data) - expected
    if missing or extra:
        raise RuntimeError(f'export FRED incohérent : missing={sorted(missing)}, extra={sorted(extra)}')

    frequency_mismatches: list[str] = []
    for family in SERIES_CATALOG.values():
        for sid, meta in family.items():
            prefix = FREQUENCY_PREFIX[meta['freq']]
            if not source_files[sid].startswith(prefix):
                frequency_mismatches.append(
                    f'{sid}:catalogue={meta["freq"]},export={source_files[sid]}'
                )
    if frequency_mismatches:
        raise RuntimeError(f'fréquences incohérentes : {frequency_mismatches}')
    return all_data, source_files


def main() -> int:
    started = time.perf_counter()
    all_data, source_files = download_catalog()
    current = compute_dashboard(all_data)
    backtest = compute_empirical_calibration(all_data)
    current = apply_weights(current, backtest)
    weights = {
        sid: calibration_to_weight(calibration)
        for sid, calibration in zip(backtest['series_id'], backtest['calibration_net'], strict=False)
    }
    historical = reconstruct_historical_score(all_data, weights)

    validate_current_snapshot(current)
    validate_backtest(backtest)
    validate_historical(historical)

    psavert = current.loc[current['series_id'] == 'PSAVERT'].iloc[0]
    ordered = current.sort_values('stress_final', ascending=False)
    families = family_scores(current)
    leave_one_out = {
        sid: global_score(current.loc[current['series_id'] != sid])
        for sid in current['series_id']
    }
    current_global = global_score(current)
    most_influential = max(
        leave_one_out,
        key=lambda sid: abs(leave_one_out[sid] - current_global),
    )
    history_min_date = pd.Timestamp(historical['global'].idxmin()).date().isoformat()
    history_max_timestamp = pd.Timestamp(historical['global'].idxmax())
    history_max_date = history_max_timestamp.date().isoformat()
    peak_rows: list[dict[str, object]] = []
    for family_name, series_dict in SERIES_CATALOG.items():
        for sid, meta in series_dict.items():
            metrics = compute_metrics_for_series(
                all_data[sid],
                sid,
                meta,
                as_of=history_max_timestamp,
                zscore_data=zscore_input_series(all_data[sid], sid),
            )
            if metrics is not None and np.isfinite(float(metrics['stress_final'])):
                peak_rows.append(
                    {
                        **metrics,
                        'famille': family_name,
                        'weight': weights[sid],
                    }
                )
    peak = pd.DataFrame(peak_rows)
    peak_global = global_score(peak)
    peak_leave_one_out = {
        sid: global_score(peak.loc[peak['series_id'] != sid])
        for sid in peak['series_id']
    }
    peak_most_influential = max(
        peak_leave_one_out,
        key=lambda sid: abs(peak_leave_one_out[sid] - peak_global),
    )
    result = {
        'source': FRED_EXPORT_URL,
        'series_loaded': len(all_data),
        'frequency_files': sorted(set(source_files.values())),
        'oldest_latest_observation': pd.to_datetime(current['date']).min().isoformat(),
        'newest_latest_observation': pd.to_datetime(current['date']).max().isoformat(),
        'current_global_score': round(current_global, 8),
        'family_scores': {
            family: round(float(score), 8)
            for family, score in families['score'].sort_index().items()
        },
        'historical_points': len(historical),
        'historical_last_coverage': int(historical.iloc[-1]['coverage']),
        'historical_global_min': {
            'date': history_min_date,
            'score': round(float(historical['global'].min()), 8),
        },
        'historical_global_max': {
            'date': history_max_date,
            'score': round(float(historical['global'].max()), 8),
            'recomputed_score': round(peak_global, 8),
            'coverage': len(peak),
            'highest_series_scores': [
                {'series_id': row.series_id, 'score': round(float(row.stress_final), 6)}
                for row in peak.sort_values('stress_final', ascending=False).head(5).itertuples(index=False)
            ],
            'max_leave_one_out_impact': {
                'series_id': peak_most_influential,
                'absolute_delta': round(
                    abs(float(peak_leave_one_out[peak_most_influential]) - peak_global),
                    8,
                ),
            },
        },
        'historical_global_quantiles': {
            str(quantile): round(float(historical['global'].quantile(quantile)), 8)
            for quantile in (0.01, 0.05, 0.5, 0.95, 0.99)
        },
        'max_leave_one_out_impact': {
            'series_id': most_influential,
            'absolute_delta': round(
                abs(float(leave_one_out[most_influential]) - current_global),
                8,
            ),
        },
        'psavert_signed_zscore': round(float(psavert['signed_zscore']), 8),
        'psavert_composite_score': round(float(psavert['stress_final']), 8),
        'finite_current_scores': int(np.isfinite(current['stress_final']).sum()),
        'neutral_weights': int((current['weight'] == 1.0).sum()),
        'weight_distribution': {
            str(weight): int(count)
            for weight, count in current['weight'].value_counts().sort_index().items()
        },
        'highest_series_scores': [
            {'series_id': row.series_id, 'score': round(float(row.stress_final), 6)}
            for row in ordered.head(5).itertuples(index=False)
        ],
        'lowest_series_scores': [
            {'series_id': row.series_id, 'score': round(float(row.stress_final), 6)}
            for row in ordered.tail(5).itertuples(index=False)
        ],
        'elapsed_seconds': round(time.perf_counter() - started, 3),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
