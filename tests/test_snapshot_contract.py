from __future__ import annotations

import json
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from catalog import METHODOLOGY_VERSION, NON_STATIONARY, SERIES_CATALOG, SNAPSHOT_SCHEMA_VERSION
from snapshot_builder import publish_bundle
from snapshot_contract import (
    CURRENT_FILENAME,
    METADATA_FILENAME,
    SnapshotValidationError,
    catalog_sha256,
    expected_series_ids,
    load_snapshot_bundle,
    validate_current_snapshot,
)

REVISION = 'a' * 40


def fixture_frames() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    rows = []
    for family, series in SERIES_CATALOG.items():
        for sid, meta in series.items():
            rows.append(
                {
                    'series_id': sid,
                    'name': meta['name'],
                    'famille': family,
                    'freq': meta['freq'],
                    'unit': meta['unit'],
                    'direction': meta['direction'],
                    'date': pd.Timestamp.now().normalize(),
                    'current': 100.0,
                    'signed_zscore': 0.4,
                    'drift_zscore_equiv': 0.2,
                    'momentum_zscore_equiv': 0.1,
                    'stress_final': 0.3,
                    'calibration_net': 0.5,
                    'weight': 2.0,
                    'stress_weighted': 0.6,
                }
            )
    current = pd.DataFrame(rows)
    backtest = pd.DataFrame(
        {
            'series_id': current['series_id'],
            'mode': [
                'score composite · z YoY' if sid in NON_STATIONARY else 'score composite · z niveau'
                for sid in current['series_id']
            ],
            'false_positive_rate': [0.1] * len(current),
            'n_nonrec_obs': [100] * len(current),
            'avg_score_3m': [0.6] * len(current),
            'n_obs_3m': [4] * len(current),
            'avg_score_6m': [0.6] * len(current),
            'n_obs_6m': [4] * len(current),
            'avg_score_12m': [0.6] * len(current),
            'n_obs_12m': [4] * len(current),
            'calibration_raw': [0.6] * len(current),
            'false_positive_penalty': [0.1] * len(current),
            'calibration_net': [0.5] * len(current),
            'n_min': [4] * len(current),
        }
    )
    historical = pd.DataFrame(
        {
            'global': [0.2, 0.3],
            'coverage': [len(current), len(current)],
            **{f'fam_{family}': [0.1, 0.2] for family in SERIES_CATALOG},
        },
        index=pd.to_datetime(['2025-01-01', '2025-02-01']),
    )
    historical.index.name = 'date'
    return current, backtest, historical


def fixture_metadata(current: pd.DataFrame, historical: pd.DataFrame) -> dict[str, object]:
    dates = pd.to_datetime(current['date'])
    return {
        'schema_version': SNAPSHOT_SCHEMA_VERSION,
        'methodology_version': METHODOLOGY_VERSION,
        'calculator_revision': REVISION,
        'generated_at': datetime.now(UTC).isoformat().replace('+00:00', 'Z'),
        'source': 'FRED · Federal Reserve Bank of St. Louis',
        'source_url': 'https://fred.stlouisfed.org/',
        'catalog_sha256': catalog_sha256(),
        'n_series_expected': len(expected_series_ids()),
        'n_series_loaded': len(current),
        'n_errors': 0,
        'quality_status': 'nominal',
        'historical_mode': 'current-methodology-reconstruction',
        'historical_points': len(historical),
        'source_observation_oldest': dates.min().isoformat(),
        'source_observation_newest': dates.max().isoformat(),
        'files': {},
    }


class SnapshotContractTests(unittest.TestCase):
    def test_valid_bundle_round_trip(self) -> None:
        current, backtest, historical = fixture_frames()
        metadata = fixture_metadata(current, historical)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            publish_bundle(root, current, backtest, historical, metadata)
            bundle = load_snapshot_bundle(root)
            self.assertEqual(set(bundle.current['series_id']), expected_series_ids())
            self.assertEqual(bundle.metadata['calculator_revision'], REVISION)

    def test_hash_tampering_is_rejected_before_read(self) -> None:
        current, backtest, historical = fixture_frames()
        metadata = fixture_metadata(current, historical)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            publish_bundle(root, current, backtest, historical, metadata)
            with (root / CURRENT_FILENAME).open('ab') as handle:
                handle.write(b'tampered')
            with self.assertRaisesRegex(SnapshotValidationError, 'taille invalide|hash invalide'):
                load_snapshot_bundle(root)

    def test_missing_series_is_rejected(self) -> None:
        current, _, _ = fixture_frames()
        with self.assertRaisesRegex(SnapshotValidationError, 'couverture FRED incomplète'):
            validate_current_snapshot(current.iloc[:-1])

    def test_catalog_metadata_mismatch_is_rejected(self) -> None:
        current, _, _ = fixture_frames()
        current.loc[0, 'unit'] = 'inventée'
        with self.assertRaisesRegex(SnapshotValidationError, 'catalogue incohérent'):
            validate_current_snapshot(current)

    def test_metadata_rejects_unversioned_calculator(self) -> None:
        current, backtest, historical = fixture_frames()
        metadata = fixture_metadata(current, historical)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            publish_bundle(root, current, backtest, historical, metadata)
            metadata_path = root / METADATA_FILENAME
            manifest = json.loads(metadata_path.read_text(encoding='utf-8'))
            manifest['calculator_revision'] = 'main'
            metadata_path.write_text(json.dumps(manifest), encoding='utf-8')
            with self.assertRaisesRegex(SnapshotValidationError, 'SHA calculateur invalide'):
                load_snapshot_bundle(root)


if __name__ == '__main__':
    unittest.main()
