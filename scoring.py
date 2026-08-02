"""Moteur de calcul unique du US Macro Risk Dashboard.

Ce module ne dépend ni de Streamlit ni du mode de livraison. L'application
locale et le générateur de snapshots de production utilisent donc exactement
les mêmes fonctions et les mêmes constantes.
"""

from __future__ import annotations

from collections.abc import Mapping

import numpy as np
import pandas as pd

from catalog import (
    COMPONENT_SCORE_CAP,
    DRIFT_WARNING,
    FALSE_POSITIVE_BUFFER_MONTHS,
    FALSE_POSITIVE_PENALTY,
    FALSE_POSITIVE_WARNING_LEVEL,
    MIN_RECESSION_OBS_PER_HORIZON,
    MOMENTUM_WARNING,
    NBER_RECESSION_PERIODS,
    NBER_RECESSIONS,
    NO_MOMENTUM_SERIES,
    NON_STATIONARY,
    PRE_COVID_REF_END,
    PRE_COVID_REF_START,
    REGIME_CHANGE_SERIES,
    SERIES_CATALOG,
    STRESS_COMPONENT_WEIGHTS,
    ZSCORE_DANGER,
    ZSCORE_WARNING,
    ZSCORE_WINDOW_YEARS,
)


def _finite(value: object) -> bool:
    """Retourne True pour une valeur numérique finie."""
    try:
        return bool(pd.notna(value) and np.isfinite(float(value)))
    except (TypeError, ValueError):
        return False


def weighted_stress_component_score(components: Mapping[str, float]) -> float:
    """Combine les composantes disponibles après saturation symétrique."""
    weighted_sum = 0.0
    weight_sum = 0.0
    for name, value in components.items():
        if not _finite(value):
            continue
        weight = float(STRESS_COMPONENT_WEIGHTS.get(name, 0.0))
        if weight <= 0:
            continue
        bounded_value = float(np.clip(float(value), -COMPONENT_SCORE_CAP, COMPONENT_SCORE_CAP))
        weighted_sum += bounded_value * weight
        weight_sum += weight
    return weighted_sum / weight_sum if weight_sum > 0 else np.nan


def value_asof_offset(
    series: pd.Series,
    date: pd.Timestamp,
    *,
    months: int = 0,
    years: int = 0,
) -> float:
    """Valeur disponible au plus tard à une distance calendaire donnée."""
    target = pd.Timestamp(date) - pd.DateOffset(months=months, years=years)
    try:
        value = series.asof(target)
    except (TypeError, ValueError):
        return np.nan
    return float(value) if _finite(value) else np.nan


def pct_change_from(value: float, previous: float) -> float:
    """Variation en pourcentage, avec garde sur les valeurs indisponibles."""
    if not _finite(value) or not _finite(previous) or float(previous) == 0:
        return np.nan
    return (float(value) - float(previous)) / float(previous) * 100.0


def time_based_year_over_year(series: pd.Series) -> pd.Series:
    """Calcule un vrai glissement annuel, quelle que soit la fréquence FRED.

    ``pct_change(periods=12)`` signifie douze observations. Pour une série
    hebdomadaire, cela représente environ douze semaines. Cette fonction prend
    au contraire la dernière observation réellement disponible un an plus tôt.
    """
    clean = series.dropna().sort_index()
    clean = clean.loc[~clean.index.duplicated(keep='last')]
    if clean.empty:
        return pd.Series(dtype=float)
    targets = pd.DatetimeIndex([pd.Timestamp(date) - pd.DateOffset(years=1) for date in clean.index])
    expanded_index = clean.index.union(targets.unique()).unique()
    expanded = clean.reindex(expanded_index).sort_index().ffill()
    previous = expanded.reindex(targets).to_numpy(dtype=float)
    current = clean.to_numpy(dtype=float)
    changes = np.divide(
        current - previous,
        previous,
        out=np.full_like(current, np.nan, dtype=float),
        where=np.isfinite(previous) & (previous != 0),
    )
    return pd.Series(changes, index=clean.index, dtype=float).dropna()


def zscore_input_series(data: pd.Series, sid: str) -> pd.Series:
    """Série effectivement normalisée pour le z-score."""
    clean = data.dropna().sort_index()
    return time_based_year_over_year(clean) if sid in NON_STATIONARY else clean


def compute_metrics_for_series(
    data: pd.Series,
    sid: str,
    meta: Mapping[str, str],
    *,
    as_of: pd.Timestamp | str | None = None,
    zscore_data: pd.Series | None = None,
) -> dict[str, object] | None:
    """Calcule les métriques en excluant les observations datées après ``as_of``.

    FRED fournit ici la dernière version révisée des séries, pas leur vintage
    réellement disponible à ``as_of``. La fonction garantit une troncature par
    date d'observation, pas un jeu de données point-in-time de type ALFRED.
    """
    if data is None:
        return None
    clean = data.dropna().sort_index()
    clean = clean.loc[~clean.index.duplicated(keep='last')]
    requested_as_of = pd.Timestamp(as_of) if as_of is not None else None
    available = clean.loc[:requested_as_of] if requested_as_of is not None else clean
    if len(available) < 10:
        return None

    current = float(available.iloc[-1])
    current_date = pd.Timestamp(available.index[-1])
    direction = meta['direction']
    sign = 1 if direction == 'up' else -1

    # Le drift pré-COVID n'est utilisable qu'une fois la période de référence
    # entièrement observée. Cela évite une fuite de données dans l'historique.
    baseline = np.nan
    if current_date > pd.Timestamp(PRE_COVID_REF_END):
        precovid = available.loc[PRE_COVID_REF_START:PRE_COVID_REF_END]
        if len(precovid) > 0:
            baseline = float(precovid.mean())

    prepared_zscore = zscore_data if zscore_data is not None else zscore_input_series(clean, sid)
    available_zscore = prepared_zscore.loc[:current_date]
    cutoff = current_date - pd.DateOffset(years=ZSCORE_WINDOW_YEARS)
    window = available_zscore.loc[cutoff:current_date]
    if len(window) > 5 and _finite(window.std()) and float(window.std()) > 0:
        zscore_value = available_zscore.asof(current_date)
        zscore = (float(zscore_value) - float(window.mean())) / float(window.std())
        signed_z = sign * zscore
    else:
        zscore = np.nan
        signed_z = np.nan

    if _finite(baseline) and float(baseline) != 0:
        raw_drift = (current - float(baseline)) / abs(float(baseline)) * 100.0
        drift_pct = sign * raw_drift
        drift_zscore_equiv = drift_pct / (DRIFT_WARNING / ZSCORE_WARNING)
    else:
        drift_pct = np.nan
        drift_zscore_equiv = np.nan

    previous_1y = value_asof_offset(available, current_date, years=1)
    previous_3m = value_asof_offset(available, current_date, months=3)
    pct_1y = pct_change_from(current, previous_1y)
    pct_3m = pct_change_from(current, previous_3m)

    momentum_signals: list[float] = []
    if _finite(pct_3m):
        momentum_signals.append(sign * float(pct_3m) * 4.0)
    if _finite(pct_1y):
        momentum_signals.append(sign * float(pct_1y))
    if momentum_signals:
        momentum = float(np.mean(momentum_signals))
        momentum_zscore_equiv = momentum / (MOMENTUM_WARNING / ZSCORE_WARNING)
    else:
        momentum_zscore_equiv = np.nan

    components: dict[str, float] = {'zscore': signed_z}
    if sid not in REGIME_CHANGE_SERIES:
        components['drift'] = drift_zscore_equiv
    if sid not in NO_MOMENTUM_SERIES:
        components['momentum'] = momentum_zscore_equiv
    stress_final = weighted_stress_component_score(components)

    return {
        'series_id': sid,
        'name': meta['name'],
        'freq': meta['freq'],
        'unit': meta['unit'],
        'direction': direction,
        'date': current_date,
        'as_of': requested_as_of if requested_as_of is not None else current_date,
        'current': current,
        'baseline_precovid': baseline,
        'zscore_5y': zscore,
        'signed_zscore': signed_z,
        'drift_vs_precovid_pct': drift_pct,
        'drift_zscore_equiv': drift_zscore_equiv,
        'pct_change_3m': pct_3m,
        'pct_change_1y': pct_1y,
        'momentum_zscore_equiv': momentum_zscore_equiv,
        'stress_final': stress_final,
    }


def compute_dashboard(all_data: Mapping[str, pd.Series]) -> pd.DataFrame:
    """Construit le snapshot courant à partir des séries disponibles."""
    rows: list[dict[str, object]] = []
    for family, series_dict in SERIES_CATALOG.items():
        for sid, meta in series_dict.items():
            if sid not in all_data:
                continue
            metrics = compute_metrics_for_series(
                all_data[sid],
                sid,
                meta,
                zscore_data=zscore_input_series(all_data[sid], sid),
            )
            if metrics:
                metrics['famille'] = family
                rows.append(metrics)
    return pd.DataFrame(rows)


def is_near_recession(
    date: pd.Timestamp | str,
    buffer_months: int = FALSE_POSITIVE_BUFFER_MONTHS,
) -> bool:
    """Vrai pendant une récession NBER ou sa fenêtre tampon."""
    point = pd.Timestamp(date)
    for start, end in NBER_RECESSION_PERIODS:
        lower = pd.Timestamp(start) - pd.DateOffset(months=buffer_months)
        upper = pd.Timestamp(end) + pd.DateOffset(months=buffer_months)
        if lower <= point <= upper:
            return True
    return False


def historical_zscore(
    series: pd.Series,
    target_date: pd.Timestamp | str,
    sid: str,
    window_years: int = ZSCORE_WINDOW_YEARS,
) -> float:
    """Z-score tronqué à la date d'observation, en niveau ou glissement annuel."""
    if series is None or len(series) < 50:
        return np.nan
    target = pd.Timestamp(target_date)
    available = series.dropna().sort_index()
    available = available.loc[~available.index.duplicated(keep='last')].loc[:target]
    if len(available) < 24:
        return np.nan

    transformed = zscore_input_series(available, sid)
    if len(transformed) < 24:
        return np.nan
    try:
        current_value = transformed.asof(target)
    except (TypeError, ValueError):
        return np.nan
    if not _finite(current_value):
        return np.nan

    cutoff = target - pd.DateOffset(years=window_years)
    window = transformed.loc[cutoff:target]
    std = window.std()
    if len(window) < 5 or not _finite(std) or float(std) == 0:
        return np.nan
    return (float(current_value) - float(window.mean())) / float(std)


def compute_empirical_calibration(all_data: Mapping[str, pd.Series]) -> pd.DataFrame:
    """Calibre le même score composite sur récessions et faux positifs."""
    horizons = (3, 6, 12)
    results: list[dict[str, object]] = []
    for family, series_dict in SERIES_CATALOG.items():
        for sid, meta in series_dict.items():
            if sid not in all_data:
                continue
            series = all_data[sid].dropna().sort_index()
            prepared_zscore = zscore_input_series(series, sid)
            scores_by_horizon: dict[int, list[float]] = {h: [] for h in horizons}
            for recession_date in NBER_RECESSIONS:
                for horizon in horizons:
                    target = recession_date - pd.DateOffset(months=horizon)
                    metrics = compute_metrics_for_series(
                        series,
                        sid,
                        meta,
                        as_of=target,
                        zscore_data=prepared_zscore,
                    )
                    if metrics is not None and _finite(metrics['stress_final']):
                        scores_by_horizon[horizon].append(float(metrics['stress_final']))

            non_recession_scores: list[float] = []
            start = max(pd.Timestamp('1990-01-01'), pd.Timestamp(series.index.min()))
            end = pd.Timestamp(series.index.max())
            for target in pd.date_range(start, end, freq='QS'):
                if is_near_recession(target):
                    continue
                metrics = compute_metrics_for_series(
                    series,
                    sid,
                    meta,
                    as_of=target,
                    zscore_data=prepared_zscore,
                )
                if metrics is not None and _finite(metrics['stress_final']):
                    non_recession_scores.append(float(metrics['stress_final']))
            false_positive_rate = (
                float(np.mean([score >= FALSE_POSITIVE_WARNING_LEVEL for score in non_recession_scores]))
                if non_recession_scores
                else np.nan
            )

            row: dict[str, object] = {
                'series_id': sid,
                'name': meta['name'],
                'famille': family,
                'mode': 'score composite · z YoY' if sid in NON_STATIONARY else 'score composite · z niveau',
                'false_positive_rate': false_positive_rate,
                'n_nonrec_obs': len(non_recession_scores),
            }
            for horizon in horizons:
                values = scores_by_horizon[horizon]
                row[f'avg_score_{horizon}m'] = float(np.mean(values)) if values else np.nan
                row[f'n_obs_{horizon}m'] = len(values)
            results.append(row)

    backtest = pd.DataFrame(results)
    average_columns = ['avg_score_3m', 'avg_score_6m', 'avg_score_12m']
    backtest['calibration_raw'] = backtest[average_columns].mean(axis=1)
    backtest['false_positive_penalty'] = (
        backtest['false_positive_rate'].fillna(0) * FALSE_POSITIVE_PENALTY
    )
    backtest['calibration_net'] = backtest['calibration_raw'] - backtest['false_positive_penalty']
    backtest['n_min'] = backtest[['n_obs_3m', 'n_obs_6m', 'n_obs_12m']].min(axis=1)
    backtest.loc[backtest['n_min'] < MIN_RECESSION_OBS_PER_HORIZON, 'calibration_net'] = np.nan
    return backtest


def calibration_to_weight(calibration: float) -> float:
    """Convertit la calibration historique en poids empirique borné."""
    if not _finite(calibration):
        return 1.0
    if calibration >= 1.5:
        return 3.0
    if calibration >= 0.8:
        return 2.5
    if calibration >= 0.4:
        return 2.0
    if calibration >= 0.0:
        return 1.5
    if calibration >= -0.5:
        return 1.0
    return 0.5


def apply_weights(frame: pd.DataFrame, backtest: pd.DataFrame) -> pd.DataFrame:
    """Ajoute les poids et le score pondéré au snapshot courant."""
    calibration_map = dict(zip(backtest['series_id'], backtest['calibration_net'], strict=False))
    result = frame.copy()
    result['calibration_net'] = result['series_id'].map(calibration_map)
    result['weight'] = result['calibration_net'].apply(calibration_to_weight)
    result['stress_weighted'] = result['stress_final'] * result['weight']
    return result


def _valid_weighted_rows(frame: pd.DataFrame) -> pd.DataFrame:
    required = frame[['stress_final', 'weight']].apply(pd.to_numeric, errors='coerce')
    mask = (
        np.isfinite(required['stress_final'])
        & np.isfinite(required['weight'])
        & (required['weight'] > 0)
    )
    return frame.loc[mask]


def family_scores(frame: pd.DataFrame) -> pd.DataFrame:
    """Calcule les scores par famille sans diluer les valeurs manquantes."""
    valid = _valid_weighted_rows(frame)

    def weighted_family(group: pd.DataFrame) -> float:
        return float(np.average(group['stress_final'], weights=group['weight']))

    scores = valid.groupby('famille').apply(weighted_family, include_groups=False).rename('score')
    maximums = valid.groupby('famille')['stress_final'].max().rename('max')
    counts = valid.groupby('famille').size().rename('n')
    return pd.concat([scores, maximums, counts], axis=1).sort_values('score', ascending=False)


def global_score(frame: pd.DataFrame) -> float:
    """Calcule le score global sur les seules lignes valides."""
    valid = _valid_weighted_rows(frame)
    if valid.empty:
        return np.nan
    return float(np.average(valid['stress_final'], weights=valid['weight']))


def reconstruct_historical_score(
    all_data: Mapping[str, pd.Series],
    weights_map: Mapping[str, float],
    *,
    start: str = '1990-01-01',
    end: pd.Timestamp | str | None = None,
) -> pd.DataFrame:
    """Reconstruit le score composite avec la méthodologie courante.

    Les observations datées après chaque point sont exclues. Les poids et les
    vintages FRED sont ceux du modèle courant : il s'agit donc d'une
    reconstruction rétrospective et non d'une série de décisions historiques
    prises en temps réel.
    """
    end_date = pd.Timestamp(end) if end is not None else pd.Timestamp.now().normalize()
    dates = pd.date_range(pd.Timestamp(start), end_date.replace(day=1), freq='MS')
    history: list[dict[str, object]] = []
    prepared_zscores = {
        sid: zscore_input_series(series, sid)
        for sid, series in all_data.items()
    }

    for date in dates:
        rows: list[dict[str, object]] = []
        for family, series_dict in SERIES_CATALOG.items():
            for sid, meta in series_dict.items():
                if sid not in all_data:
                    continue
                metrics = compute_metrics_for_series(
                    all_data[sid],
                    sid,
                    meta,
                    as_of=date,
                    zscore_data=prepared_zscores[sid],
                )
                if metrics is None or not _finite(metrics['stress_final']):
                    continue
                rows.append(
                    {
                        'famille': family,
                        'stress_final': float(metrics['stress_final']),
                        'weight': float(weights_map.get(sid, 1.0)),
                    }
                )
        if not rows:
            continue
        frame = pd.DataFrame(rows)
        families = family_scores(frame)
        history.append(
            {
                'date': date,
                'global': global_score(frame),
                'coverage': len(frame),
                **{f'fam_{family}': value for family, value in families['score'].items()},
            }
        )

    if not history:
        return pd.DataFrame(columns=['global', 'coverage']).rename_axis('date')
    return pd.DataFrame(history).set_index('date').sort_index()


def status_level(score: float) -> str:
    """Libellé public fondé sur les seuils natifs du moteur."""
    if not _finite(score):
        return 'indisponible'
    if score >= ZSCORE_DANGER:
        return 'critique'
    if score >= ZSCORE_WARNING:
        return 'vigilance'
    if score > 0:
        return 'modéré'
    return 'calme'
