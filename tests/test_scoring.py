from __future__ import annotations

import unittest

import numpy as np
import pandas as pd

from catalog import COMPONENT_SCORE_CAP, NO_MOMENTUM_SERIES, REGIME_CHANGE_SERIES, SERIES_CATALOG
from scoring import (
    calibration_to_weight,
    compute_dashboard,
    compute_empirical_calibration,
    compute_metrics_for_series,
    family_scores,
    global_score,
    reconstruct_historical_score,
    time_based_year_over_year,
    weighted_stress_component_score,
    zscore_input_series,
)


class ScoringTests(unittest.TestCase):
    def test_catalog_uses_active_discount_window_series_and_correct_units(self) -> None:
        banking = SERIES_CATALOG['stress_bancaire']
        labour = SERIES_CATALOG['travail']
        self.assertIn('WLCFLPCL', banking)
        self.assertNotIn('H41RESPPALDKNWW', banking)
        self.assertIn('WLCFLPCL', REGIME_CHANGE_SERIES)
        self.assertIn('WLCFLPCL', NO_MOMENTUM_SERIES)
        self.assertEqual(SERIES_CATALOG['corporate']['BUSLOANS']['freq'], 'M')
        self.assertEqual(labour['ICSA']['unit'], 'count')
        self.assertEqual(labour['CCSA']['unit'], 'count')

    def test_component_aggregation_is_weighted_mean_not_maximum(self) -> None:
        score = weighted_stress_component_score({'zscore': 0.2, 'drift': 3.0, 'momentum': 0.2})
        self.assertAlmostEqual(score, 0.9)
        self.assertNotEqual(score, 3.0)

    def test_missing_component_is_renormalized_not_replaced_by_zero(self) -> None:
        score = weighted_stress_component_score({'zscore': 2.0, 'drift': np.nan})
        self.assertAlmostEqual(score, 2.0)

    def test_extreme_component_is_saturated_before_aggregation(self) -> None:
        score = weighted_stress_component_score(
            {'zscore': 2.0, 'drift': np.nan, 'momentum': 200.0}
        )
        expected = (2.0 * 0.5 + COMPONENT_SCORE_CAP * 0.25) / 0.75
        self.assertAlmostEqual(score, expected)
        self.assertLessEqual(abs(score), COMPONENT_SCORE_CAP)

    def test_weekly_year_over_year_uses_calendar_year_not_twelve_rows(self) -> None:
        index = pd.date_range('2023-01-01', '2025-01-05', freq='W-SUN')
        series = pd.Series(np.arange(100.0, 100.0 + len(index)), index=index)
        result = time_based_year_over_year(series)
        current_date = result.index[-1]
        previous = series.asof(current_date - pd.DateOffset(years=1))
        expected = series.loc[current_date] / previous - 1
        twelve_rows = series.pct_change(periods=12).loc[current_date]
        self.assertAlmostEqual(result.loc[current_date], expected)
        self.assertNotAlmostEqual(result.loc[current_date], twelve_rows)

    def test_daily_year_over_year_handles_leap_day_target_collision(self) -> None:
        index = pd.date_range('2019-02-20', '2020-03-02', freq='D')
        series = pd.Series(np.linspace(100, 120, len(index)), index=index)
        result = time_based_year_over_year(series)
        self.assertIn(pd.Timestamp('2020-02-28'), result.index)
        self.assertIn(pd.Timestamp('2020-02-29'), result.index)
        self.assertTrue(np.isfinite(result.loc['2020-02-29']))

    def test_nonstationary_zscore_uses_calendar_yoy(self) -> None:
        index = pd.date_range('2015-01-01', '2025-01-01', freq='MS')
        values = pd.Series(100 + np.arange(len(index)) ** 1.35, index=index)
        metrics = compute_metrics_for_series(values, 'TOTALSL', SERIES_CATALOG['credit_menages']['TOTALSL'])
        transformed = zscore_input_series(values, 'TOTALSL')
        window = transformed.loc['2020-01-01':'2025-01-01']
        expected = (transformed.iloc[-1] - window.mean()) / window.std()
        self.assertIsNotNone(metrics)
        self.assertAlmostEqual(float(metrics['zscore_5y']), float(expected))

    def test_precovid_baseline_excludes_later_observations(self) -> None:
        index = pd.date_range('2014-01-01', '2021-01-01', freq='MS')
        values = pd.Series(np.linspace(80, 120, len(index)), index=index)
        meta = SERIES_CATALOG['credit_menages']['PSAVERT']
        before = compute_metrics_for_series(values, 'PSAVERT', meta, as_of='2018-06-01')
        after = compute_metrics_for_series(values, 'PSAVERT', meta, as_of='2021-01-01')
        self.assertTrue(np.isnan(before['baseline_precovid']))
        self.assertTrue(np.isfinite(after['baseline_precovid']))

    def test_aggregation_does_not_dilute_missing_values(self) -> None:
        frame = pd.DataFrame(
            [
                {'famille': 'a', 'stress_final': 2.0, 'weight': 2.0},
                {'famille': 'a', 'stress_final': np.nan, 'weight': 3.0},
                {'famille': 'b', 'stress_final': -1.0, 'weight': 1.0},
            ]
        )
        scores = family_scores(frame)
        self.assertAlmostEqual(float(scores.loc['a', 'score']), 2.0)
        self.assertAlmostEqual(global_score(frame), 1.0)

    def test_short_recession_history_keeps_neutral_weight(self) -> None:
        index = pd.date_range('2015-01-01', '2026-01-01', freq='MS')
        values = pd.Series(100 + np.sin(np.arange(len(index)) / 5), index=index)
        calibration = compute_empirical_calibration({'PSAVERT': values}).iloc[0]
        self.assertLess(int(calibration['n_min']), 2)
        self.assertTrue(np.isnan(calibration['calibration_net']))
        self.assertEqual(calibration_to_weight(calibration['calibration_net']), 1.0)

    def test_historical_last_point_reconciles_with_current_engine(self) -> None:
        index = pd.date_range('1985-01-01', '2024-01-01', freq='MS')
        all_data: dict[str, pd.Series] = {}
        for position, family in enumerate(SERIES_CATALOG.values(), start=1):
            for sid in family:
                trend = np.arange(len(index), dtype=float) * (0.015 + position / 10_000)
                cycle = np.sin(np.arange(len(index)) / (8 + position % 5)) * (1 + position / 20)
                all_data[sid] = pd.Series(100 + position + trend + cycle, index=index)
        current = compute_dashboard(all_data)
        current['weight'] = 1.0
        current['stress_weighted'] = current['stress_final']
        weights = {sid: 1.0 for sid in all_data}
        historical = reconstruct_historical_score(all_data, weights, start='2023-01-01', end='2024-01-01')
        self.assertEqual(int(historical.iloc[-1]['coverage']), len(all_data))
        self.assertAlmostEqual(float(historical.iloc[-1]['global']), global_score(current), places=10)


if __name__ == '__main__':
    unittest.main()
