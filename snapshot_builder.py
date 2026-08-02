#!/usr/bin/env python3
"""Génère le bundle FRED validé lu par ``app_server.py``."""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
from fredapi import Fred

from catalog import METHODOLOGY_VERSION, SERIES_CATALOG, SNAPSHOT_SCHEMA_VERSION
from scoring import (
    apply_weights,
    calibration_to_weight,
    compute_dashboard,
    compute_empirical_calibration,
    reconstruct_historical_score,
)
from snapshot_contract import (
    BACKTEST_FILENAME,
    CURRENT_FILENAME,
    HISTORICAL_FILENAME,
    METADATA_FILENAME,
    catalog_sha256,
    file_sha256,
    validate_backtest,
    validate_current_snapshot,
    validate_historical,
    validate_metadata,
)

LOG = logging.getLogger('macro-snapshot-builder')
SHA_PATTERN = re.compile(r'^[0-9a-f]{40}$')


def load_environment_file(path: Path) -> None:
    """Charge un fichier KEY=VALUE minimal sans évaluer de syntaxe shell."""
    if not path.exists():
        return
    mode = path.stat().st_mode & 0o777
    if mode & 0o007:
        raise RuntimeError(f'{path} est lisible par tous ; permissions refusées')
    for raw_line in path.read_text(encoding='utf-8').splitlines():
        line = raw_line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, value = line.split('=', 1)
        key = key.strip()
        if key and key not in os.environ:
            os.environ[key] = value.strip()


def require_revision(value: str | None) -> str:
    revision = (value or '').strip().lower()
    if not SHA_PATTERN.fullmatch(revision):
        raise RuntimeError('MACRO_DASHBOARD_SOURCE_SHA doit contenir le SHA Git complet déployé')
    return revision


def fetch_all_series(fred: Fred, start: str = '1985-01-01') -> tuple[dict[str, pd.Series], list[str]]:
    """Collecte FRED avec retries bornés et échec explicite par série."""
    collected: dict[str, pd.Series] = {}
    errors: list[str] = []
    expected = sum(len(series) for series in SERIES_CATALOG.values())
    LOG.info('Collecte FRED de %s séries depuis %s', expected, start)

    for series_dict in SERIES_CATALOG.values():
        for sid in series_dict:
            last_error = 'inconnue'
            for attempt in range(3):
                try:
                    series = fred.get_series(sid, observation_start=start).dropna().sort_index()
                    if series.empty:
                        raise ValueError('série vide')
                    collected[sid] = series
                    break
                except Exception as exc:  # Le journal ne contient jamais la clé FRED.
                    last_error = type(exc).__name__
                    if attempt < 2:
                        time.sleep(2**attempt)
            else:
                errors.append(f'{sid}:{last_error}')

    LOG.info('Collecte terminée : %s/%s séries', len(collected), expected)
    return collected, errors


def _temporary_path(destination: Path) -> Path:
    return destination.with_name(f'.{destination.name}.{uuid.uuid4().hex}.tmp')


def _write_parquet(frame: pd.DataFrame, destination: Path, *, index: bool) -> Path:
    temporary = _temporary_path(destination)
    frame.to_parquet(temporary, index=index, engine='pyarrow')
    os.chmod(temporary, 0o640)
    return temporary


def _archive_current(output_dir: Path, current: pd.DataFrame, metadata: dict[str, object]) -> None:
    """Archive le courant sans pouvoir invalider un bundle déjà publié."""
    archive_dir = output_dir / 'archive'
    archive_dir.mkdir(exist_ok=True, mode=0o750)
    archive_name = str(metadata['generated_at']).replace(':', '').replace('-', '')
    archive_path = archive_dir / f'snapshot-{archive_name}-{str(metadata["calculator_revision"])[:12]}.parquet'
    archive_temporary = _temporary_path(archive_path)
    try:
        current.to_parquet(archive_temporary, index=False, engine='pyarrow')
        os.chmod(archive_temporary, 0o640)
        os.replace(archive_temporary, archive_path)
    finally:
        archive_temporary.unlink(missing_ok=True)


def publish_bundle(
    output_dir: Path,
    current: pd.DataFrame,
    backtest: pd.DataFrame,
    historical: pd.DataFrame,
    metadata: dict[str, object],
) -> None:
    """Publie les données d'abord et leur manifest d'intégrité en dernier."""
    output_dir.mkdir(parents=True, exist_ok=True, mode=0o750)
    destinations = {
        CURRENT_FILENAME: output_dir / CURRENT_FILENAME,
        BACKTEST_FILENAME: output_dir / BACKTEST_FILENAME,
        HISTORICAL_FILENAME: output_dir / HISTORICAL_FILENAME,
    }
    temporary = {
        CURRENT_FILENAME: _write_parquet(current, destinations[CURRENT_FILENAME], index=False),
        BACKTEST_FILENAME: _write_parquet(backtest, destinations[BACKTEST_FILENAME], index=False),
        HISTORICAL_FILENAME: _write_parquet(historical, destinations[HISTORICAL_FILENAME], index=True),
    }
    metadata_temporary: Path | None = None
    try:
        metadata['files'] = {
            name: {'sha256': file_sha256(path), 'bytes': path.stat().st_size}
            for name, path in temporary.items()
        }
        validate_metadata(metadata)
        metadata_path = output_dir / METADATA_FILENAME
        metadata_temporary = _temporary_path(metadata_path)
        metadata_temporary.write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2, sort_keys=True) + '\n',
            encoding='utf-8',
        )
        os.chmod(metadata_temporary, 0o640)

        for name, path in temporary.items():
            os.replace(path, destinations[name])
        os.replace(metadata_temporary, metadata_path)

        try:
            _archive_current(output_dir, current, metadata)
        except OSError as exc:
            LOG.warning('Archivage non bloquant impossible (%s)', type(exc).__name__)
    finally:
        for path in temporary.values():
            path.unlink(missing_ok=True)
        if metadata_temporary is not None:
            metadata_temporary.unlink(missing_ok=True)


def build_snapshot(
    fred: Fred,
    output_dir: Path,
    calculator_revision: str,
    *,
    now: datetime | None = None,
) -> dict[str, object]:
    """Collecte, calcule, valide et publie un snapshot complet."""
    generated_at = now or datetime.now(UTC)
    all_data, errors = fetch_all_series(fred)
    expected_count = sum(len(series) for series in SERIES_CATALOG.values())
    if errors or len(all_data) != expected_count:
        raise RuntimeError(f'snapshot partiel refusé : {len(all_data)}/{expected_count}, erreurs={errors}')

    current = compute_dashboard(all_data)
    backtest = compute_empirical_calibration(all_data)
    current = apply_weights(current, backtest)
    weights = {
        sid: calibration_to_weight(calibration)
        for sid, calibration in zip(backtest['series_id'], backtest['calibration_net'], strict=False)
    }
    historical = reconstruct_historical_score(all_data, weights, end=generated_at.date())

    validate_current_snapshot(current)
    validate_backtest(backtest)
    validate_historical(historical)

    source_dates = pd.to_datetime(current['date'])
    metadata: dict[str, object] = {
        'schema_version': SNAPSHOT_SCHEMA_VERSION,
        'methodology_version': METHODOLOGY_VERSION,
        'calculator_revision': require_revision(calculator_revision),
        'generated_at': generated_at.astimezone(UTC).isoformat().replace('+00:00', 'Z'),
        'source': 'FRED · Federal Reserve Bank of St. Louis',
        'source_url': 'https://fred.stlouisfed.org/',
        'catalog_sha256': catalog_sha256(),
        'n_series_expected': expected_count,
        'n_series_loaded': len(current),
        'n_errors': 0,
        'quality_status': 'nominal',
        'historical_mode': 'current-methodology-reconstruction',
        'historical_points': len(historical),
        'source_observation_oldest': source_dates.min().isoformat(),
        'source_observation_newest': source_dates.max().isoformat(),
        'files': {},
    }
    publish_bundle(output_dir, current, backtest, historical, metadata)
    return metadata


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        '--output-dir',
        type=Path,
        default=Path(os.environ.get('SNAPSHOTS_DIR', '/var/lib/macro_dashboard/snapshots')),
    )
    parser.add_argument(
        '--env-file',
        type=Path,
        default=Path('/etc/macro_dashboard/env'),
    )
    return parser.parse_args()


def main() -> int:
    logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
    args = parse_args()
    load_environment_file(args.env_file)
    api_key = os.environ.get('FRED_API_KEY')
    if not api_key:
        raise RuntimeError('FRED_API_KEY absente')
    revision = require_revision(os.environ.get('MACRO_DASHBOARD_SOURCE_SHA'))
    metadata = build_snapshot(Fred(api_key=api_key), args.output_dir, revision)
    LOG.info(
        'Snapshot nominal : %s séries, méthode %s, SHA %s',
        metadata['n_series_loaded'],
        metadata['methodology_version'],
        str(metadata['calculator_revision'])[:12],
    )
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
