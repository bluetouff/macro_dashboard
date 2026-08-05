"""Contrat de données et vérification des snapshots de production."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from catalog import (
    COMPONENT_SCORE_CAP,
    FALSE_POSITIVE_PENALTY,
    METHODOLOGY_VERSION,
    MIN_RECESSION_OBS_PER_HORIZON,
    NON_STATIONARY,
    SERIES_CATALOG,
    SNAPSHOT_SCHEMA_VERSION,
)

CURRENT_FILENAME = 'current_snapshot.parquet'
BACKTEST_FILENAME = 'current_backtest.parquet'
HISTORICAL_FILENAME = 'historical.parquet'
METADATA_FILENAME = 'metadata.json'

CURRENT_REQUIRED_COLUMNS = {
    'series_id',
    'name',
    'famille',
    'freq',
    'unit',
    'direction',
    'date',
    'current',
    'stress_final',
    'calibration_net',
    'weight',
    'stress_weighted',
}
BACKTEST_REQUIRED_COLUMNS = {
    'series_id',
    'mode',
    'false_positive_rate',
    'n_nonrec_obs',
    'avg_score_3m',
    'n_obs_3m',
    'avg_score_6m',
    'n_obs_6m',
    'avg_score_12m',
    'n_obs_12m',
    'calibration_raw',
    'false_positive_penalty',
    'calibration_net',
    'n_min',
}
ALLOWED_WEIGHTS = {0.5, 1.0, 1.5, 2.0, 2.5, 3.0}
SHA_PATTERN = re.compile(r'^[0-9a-f]{40}$')
SHA256_PATTERN = re.compile(r'^[0-9a-f]{64}$')
FRESHNESS_MAX_DAYS = {'D': 14, 'W': 35, 'M': 95, 'Q': 240}
# Certaines publications mensuelles officielles arrivent structurellement plus
# tard que les autres. Le G.19 publie le crédit à la consommation avec environ
# deux mois de décalage et Case-Shiller avec près de trois mois. Ces plafonds
# restent bornés et propres aux séries : ils évitent de relâcher le contrat pour
# l'ensemble du catalogue lorsqu'un calendrier de publication est légitime.
FRESHNESS_MAX_DAYS_BY_SERIES = {
    'TOTALSL': 105,
    'REVOLSL': 105,
    'CSUSHPINSA': 125,
}


class SnapshotValidationError(RuntimeError):
    """Le bundle de production ne respecte pas son contrat public."""


@dataclass(frozen=True)
class SnapshotBundle:
    current: pd.DataFrame
    backtest: pd.DataFrame
    historical: pd.DataFrame
    metadata: dict[str, Any]


def expected_series_ids() -> set[str]:
    return {sid for series in SERIES_CATALOG.values() for sid in series}


def expected_series_contract() -> dict[str, dict[str, str]]:
    return {
        sid: {**meta, 'famille': family}
        for family, series in SERIES_CATALOG.items()
        for sid, meta in series.items()
    }


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def catalog_sha256() -> str:
    payload = json.dumps(SERIES_CATALOG, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(payload.encode('utf-8')).hexdigest()


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise SnapshotValidationError(message)


def _finite_column(frame: pd.DataFrame, column: str) -> pd.Series:
    values = pd.to_numeric(frame[column], errors='coerce')
    return pd.Series(np.isfinite(values), index=frame.index)


def validate_current_snapshot(frame: pd.DataFrame, *, as_of: pd.Timestamp | None = None) -> None:
    expected = expected_series_ids()
    _require(not frame.empty, 'snapshot courant vide')
    _require(CURRENT_REQUIRED_COLUMNS <= set(frame.columns), 'colonnes du snapshot courant incomplètes')
    _require(frame['series_id'].is_unique, 'identifiants FRED dupliqués')
    actual = set(frame['series_id'].astype(str))
    _require(actual == expected, f'couverture FRED incomplète ({len(actual)}/{len(expected)})')
    _require(frame['famille'].isin(SERIES_CATALOG).all(), 'famille inconnue dans le snapshot')
    _require(frame['direction'].isin({'up', 'down'}).all(), 'direction de risque invalide')
    catalog_contract = expected_series_contract()
    for row in frame[['series_id', 'name', 'famille', 'freq', 'unit', 'direction']].itertuples(index=False):
        expected_meta = catalog_contract[str(row.series_id)]
        for field in ('name', 'famille', 'freq', 'unit', 'direction'):
            _require(str(getattr(row, field)) == str(expected_meta[field]), f'catalogue incohérent pour {row.series_id}')
    for column in ('current', 'stress_final', 'weight', 'stress_weighted'):
        _require(_finite_column(frame, column).all(), f'valeur non finie dans {column}')
    _require(
        frame['stress_final'].astype(float).abs().le(COMPONENT_SCORE_CAP + 1e-12).all(),
        'score de série hors saturation méthodologique',
    )
    _require(frame['weight'].isin(ALLOWED_WEIGHTS).all(), 'poids empirique hors contrat')
    expected_weighted = frame['stress_final'].astype(float) * frame['weight'].astype(float)
    _require(
        np.allclose(frame['stress_weighted'].astype(float), expected_weighted, rtol=1e-10, atol=1e-12),
        'stress_weighted ne correspond pas à stress_final × weight',
    )
    reference = pd.Timestamp.now() if as_of is None else pd.Timestamp(as_of)
    if reference.tzinfo is not None:
        reference = reference.tz_convert(None)
    dates = pd.to_datetime(frame['date'], errors='coerce')
    _require(dates.notna().all(), 'date source invalide')
    _require((dates <= reference + pd.Timedelta(days=1)).all(), 'date source située dans le futur')
    ages = (reference.normalize() - dates.dt.tz_localize(None).dt.normalize()).dt.days
    max_ages = frame['freq'].map(FRESHNESS_MAX_DAYS)
    _require(max_ages.notna().all(), 'fréquence sans contrat de fraîcheur')
    series_overrides = frame['series_id'].map(FRESHNESS_MAX_DAYS_BY_SERIES)
    max_ages = series_overrides.fillna(max_ages).astype(int)
    stale = ages > max_ages
    stale_details = ','.join(
        f'{series_id}:{int(age)}j>{int(limit)}j'
        for series_id, age, limit in zip(frame.loc[stale, 'series_id'], ages[stale], max_ages[stale], strict=False)
    )
    _require(not stale.any(), f'séries FRED trop anciennes pour leur fréquence ({stale_details})')


def validate_backtest(frame: pd.DataFrame) -> None:
    expected = expected_series_ids()
    _require(not frame.empty, 'backtest vide')
    _require(BACKTEST_REQUIRED_COLUMNS <= set(frame.columns), 'colonnes du backtest incomplètes')
    _require(frame['series_id'].is_unique, 'identifiants du backtest dupliqués')
    _require(set(frame['series_id'].astype(str)) == expected, 'couverture du backtest incomplète')
    _require(
        frame['mode'].isin({'score composite · z YoY', 'score composite · z niveau'}).all(),
        'transformation de backtest inconnue',
    )
    for row in frame[['series_id', 'mode']].itertuples(index=False):
        expected_mode = 'score composite · z YoY' if row.series_id in NON_STATIONARY else 'score composite · z niveau'
        _require(row.mode == expected_mode, f'transformation de backtest incohérente pour {row.series_id}')
    rate = pd.to_numeric(frame['false_positive_rate'], errors='coerce')
    _require(rate.dropna().between(0, 1).all(), 'taux de faux positifs hors intervalle [0,1]')
    counts = pd.to_numeric(frame['n_nonrec_obs'], errors='coerce')
    _require((counts.fillna(-1) >= 0).all(), 'nombre d’observations hors récession invalide')
    horizon_counts = frame[['n_obs_3m', 'n_obs_6m', 'n_obs_12m']].apply(pd.to_numeric, errors='coerce')
    _require(np.isfinite(horizon_counts).all().all(), 'compte de récessions non fini')
    _require((horizon_counts >= 0).all().all(), 'compte de récessions négatif')
    n_min = pd.to_numeric(frame['n_min'], errors='coerce')
    _require((n_min == horizon_counts.min(axis=1)).all(), 'n_min incohérent avec les horizons')
    penalty = pd.to_numeric(frame['false_positive_penalty'], errors='coerce')
    expected_penalty = rate.fillna(0) * FALSE_POSITIVE_PENALTY
    _require(np.allclose(penalty, expected_penalty), 'pénalité de faux positifs incohérente')
    raw = pd.to_numeric(frame['calibration_raw'], errors='coerce')
    expected_raw = frame[['avg_score_3m', 'avg_score_6m', 'avg_score_12m']].apply(
        pd.to_numeric, errors='coerce'
    ).mean(axis=1)
    _require(np.allclose(raw, expected_raw, equal_nan=True), 'calibration brute incohérente')
    calibration = pd.to_numeric(frame['calibration_net'], errors='coerce')
    sufficient = n_min >= MIN_RECESSION_OBS_PER_HORIZON
    _require(
        calibration[~sufficient].isna().all(),
        'calibrage non neutralisé malgré un historique insuffisant',
    )
    _require(
        np.isfinite(calibration[sufficient]).all(),
        'calibrage absent malgré un historique suffisant',
    )
    _require(
        np.allclose(calibration[sufficient], raw[sufficient] - penalty[sufficient]),
        'calibration nette incohérente',
    )


def validate_historical(frame: pd.DataFrame) -> None:
    _require(not frame.empty, 'historique vide')
    _require('global' in frame.columns and 'coverage' in frame.columns, 'historique sans score ou couverture')
    _require(frame.index.is_unique and frame.index.is_monotonic_increasing, 'index historique invalide')
    _require(pd.to_datetime(frame.index, errors='coerce').notna().all(), 'date historique invalide')
    _require(_finite_column(frame, 'global').all(), 'score historique non fini')
    _require(
        frame['global'].astype(float).abs().le(COMPONENT_SCORE_CAP + 1e-12).all(),
        'score historique hors saturation méthodologique',
    )
    coverage = pd.to_numeric(frame['coverage'], errors='coerce')
    _require(coverage.between(1, len(expected_series_ids())).all(), 'couverture historique hors limites')
    family_columns = {f'fam_{family}' for family in SERIES_CATALOG}
    _require(family_columns <= set(frame.columns), 'historique sans toutes les familles')
    _require(int(coverage.iloc[-1]) == len(expected_series_ids()), 'dernier point historique incomplet')


def validate_metadata(metadata: dict[str, Any]) -> None:
    required = {
        'schema_version',
        'methodology_version',
        'calculator_revision',
        'generated_at',
        'source',
        'source_url',
        'catalog_sha256',
        'n_series_expected',
        'n_series_loaded',
        'n_errors',
        'quality_status',
        'historical_mode',
        'historical_points',
        'source_observation_oldest',
        'source_observation_newest',
        'files',
    }
    _require(required <= set(metadata), 'métadonnées incomplètes')
    _require(metadata['schema_version'] == SNAPSHOT_SCHEMA_VERSION, 'version de schéma incompatible')
    _require(metadata['methodology_version'] == METHODOLOGY_VERSION, 'version méthodologique incompatible')
    _require(bool(SHA_PATTERN.fullmatch(str(metadata['calculator_revision']))), 'SHA calculateur invalide')
    _require(metadata['catalog_sha256'] == catalog_sha256(), 'catalogue différent de celui du calculateur')
    expected_count = len(expected_series_ids())
    _require(metadata['n_series_expected'] == expected_count, 'compte catalogue incohérent')
    _require(metadata['n_series_loaded'] == expected_count, 'snapshot partiel refusé')
    _require(metadata['n_errors'] == 0, 'erreurs de collecte présentes')
    _require(metadata['quality_status'] == 'nominal', 'qualité du snapshot non nominale')
    _require(metadata['historical_mode'] == 'current-methodology-reconstruction', 'mode historique inconnu')
    _require(isinstance(metadata['historical_points'], int) and metadata['historical_points'] > 0, 'taille historique invalide')
    _require(metadata['source'] == 'FRED · Federal Reserve Bank of St. Louis', 'source de données inattendue')
    _require(metadata['source_url'] == 'https://fred.stlouisfed.org/', 'URL source inattendue')
    try:
        generated_at = datetime.fromisoformat(str(metadata['generated_at']).replace('Z', '+00:00'))
    except ValueError as exc:
        raise SnapshotValidationError('generated_at invalide') from exc
    _require(generated_at.tzinfo is not None, 'generated_at doit inclure un fuseau')
    _require(generated_at <= datetime.now(UTC) + timedelta(minutes=5), 'snapshot daté dans le futur')
    files = metadata['files']
    _require(isinstance(files, dict), 'manifest de fichiers invalide')
    _require(
        {CURRENT_FILENAME, BACKTEST_FILENAME, HISTORICAL_FILENAME} <= set(files),
        'manifest de fichiers incomplet',
    )
    for name in (CURRENT_FILENAME, BACKTEST_FILENAME, HISTORICAL_FILENAME):
        entry = files[name]
        _require(isinstance(entry, dict), f'entrée de manifest invalide pour {name}')
        _require(bool(SHA256_PATTERN.fullmatch(str(entry.get('sha256', '')))), f'SHA-256 invalide pour {name}')
        _require(isinstance(entry.get('bytes'), int) and entry['bytes'] > 0, f'taille invalide pour {name}')


def load_snapshot_bundle(root: Path) -> SnapshotBundle:
    """Charge un bundle cohérent et vérifie schéma, couverture et hashes."""
    root = root.resolve()
    metadata_path = root / METADATA_FILENAME
    if not metadata_path.is_file():
        raise SnapshotValidationError('metadata.json absent')

    metadata_bytes_before = metadata_path.read_bytes()
    try:
        metadata = json.loads(metadata_bytes_before)
    except json.JSONDecodeError as exc:
        raise SnapshotValidationError('metadata.json invalide') from exc
    validate_metadata(metadata)

    paths = {
        CURRENT_FILENAME: root / CURRENT_FILENAME,
        BACKTEST_FILENAME: root / BACKTEST_FILENAME,
        HISTORICAL_FILENAME: root / HISTORICAL_FILENAME,
    }
    for name, path in paths.items():
        _require(path.is_file(), f'{name} absent')
        _require(path.stat().st_size == metadata['files'][name]['bytes'], f'taille invalide pour {name}')
        _require(file_sha256(path) == metadata['files'][name]['sha256'], f'hash invalide pour {name}')

    current = pd.read_parquet(paths[CURRENT_FILENAME])
    backtest = pd.read_parquet(paths[BACKTEST_FILENAME])
    historical = pd.read_parquet(paths[HISTORICAL_FILENAME])
    _require(metadata_path.read_bytes() == metadata_bytes_before, 'bundle modifié pendant la lecture')

    validate_current_snapshot(current)
    validate_backtest(backtest)
    validate_historical(historical)
    _require(len(current) == metadata['n_series_loaded'], 'compte courant différent des métadonnées')
    _require(len(historical) == metadata['historical_points'], 'compte historique différent des métadonnées')
    source_dates = pd.to_datetime(current['date'])
    _require(
        pd.Timestamp(metadata['source_observation_oldest']) == source_dates.min(),
        'date source minimale incohérente',
    )
    _require(
        pd.Timestamp(metadata['source_observation_newest']) == source_dates.max(),
        'date source maximale incohérente',
    )
    return SnapshotBundle(current=current, backtest=backtest, historical=historical, metadata=metadata)
