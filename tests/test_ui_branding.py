from __future__ import annotations

import base64
import hashlib
import re
import subprocess
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import pandas as pd
from streamlit.testing.v1 import AppTest

import dashboard_view
import ui

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'deploy/update-hero-title.sh'


class BrandingTests(unittest.TestCase):
    def test_hero_only_emphasizes_stress(self) -> None:
        with patch.object(ui.st, 'markdown') as render:
            ui.render_hero({})
        self.assertIn('<h1><em>Stress</em> <span>macro US</span></h1>', render.call_args.args[0])

    def test_logo_has_l0g_colors_and_decorative_cursor(self) -> None:
        with patch.object(ui.st, 'markdown') as render:
            ui.render_header('radar')
        self.assertIn(
            '<span>l</span><span class="brand-0">0</span><span>g</span>'
            '<span class="brand-cursor" aria-hidden="true">_</span>',
            render.call_args.args[0],
        )
        self.assertIn('aria-label="l0g.fr"', render.call_args.args[0])

    def test_brand_font_is_embedded_and_reduced_motion_is_respected(self) -> None:
        with patch.object(ui.st, 'markdown') as render:
            ui.inject_theme()
        css = render.call_args.args[0]
        encoded = css.split('data:font/woff2;base64,', 1)[1].split('"', 1)[0]
        font = ROOT / 'assets/fonts/jetbrains-mono-latin-wght-normal.woff2'
        self.assertEqual(base64.b64decode(encoded, validate=True), font.read_bytes())
        self.assertIn('font-family: "JetBrains Mono Variable"', css)
        self.assertIn('@media (prefers-reduced-motion: reduce)', css)
        self.assertIn('.brand-logo .brand-cursor { animation: none; }', css)

    def test_sections_use_semantic_headings_and_escape_external_text(self) -> None:
        with patch.object(ui.st, 'markdown') as render:
            ui.section_heading('<script>titre</script>', '<img src=x>', 'trend')
        markup = render.call_args.args[0]
        self.assertIn('<h2 class="section-heading">', markup)
        self.assertIn('aria-hidden="true">//</span>', markup)
        self.assertIn('&lt;script&gt;titre&lt;/script&gt;', markup)
        self.assertIn('&lt;img src=x&gt;', markup)
        self.assertNotIn('<script>', markup)

    def test_navigation_identifies_current_view_and_stays_in_same_tab(self) -> None:
        for view in ('radar', 'faq'):
            with self.subTest(view=view), patch.object(ui.st, 'markdown') as render:
                ui.render_header(view)
            markup = render.call_args.args[0]
            self.assertEqual(markup.count('aria-current="page"'), 1)
            self.assertIn(f'href="?view={view}" target="_self" aria-current="page"', markup)

    def test_stale_warning_and_provenance_are_preserved(self) -> None:
        metadata = {
            'generated_at': (datetime.now(UTC) - timedelta(hours=48)).isoformat(),
            'calculator_revision': 'b' * 40,
            'methodology_version': '2.0.0',
        }
        with patch.object(ui.st, 'markdown') as render:
            self.assertTrue(ui.render_quality_banner(metadata))
        self.assertIn('À ACTUALISER', render.call_args.args[0])
        self.assertIn('fenêtre de fraîcheur', render.call_args.args[0])
        with patch.object(ui.st, 'markdown') as render:
            ui.render_footer(metadata)
        self.assertIn('calculateur bbbbbbbbbbbb', render.call_args.args[0])
        self.assertIn(ui.FRED_URL, render.call_args.args[0])
        with patch.object(ui.st, 'markdown') as render:
            ui.inject_theme()
        self.assertIn('footer:not(.site-footer)', render.call_args.args[0])

    def test_tensions_keep_signed_order_and_values_and_escape_names(self) -> None:
        current = pd.DataFrame([
            {'series_id': 'LOW', 'name': 'low', 'stress_final': -2.0, 'weight': 3.0},
            {'series_id': 'HIGH', 'name': '<script>alert(1)</script>', 'stress_final': 1.25, 'weight': 2.0},
        ])
        original = current.copy(deep=True)
        with patch.object(dashboard_view.st, 'markdown') as render:
            dashboard_view._render_top_tensions(current)
        markup = render.call_args.args[0]
        self.assertLess(markup.index('HIGH'), markup.index('LOW'))
        self.assertIn('+1.25', markup)
        self.assertIn('-2.00', markup)
        self.assertIn('poids 2.0', markup)
        self.assertIn('&lt;script&gt;', markup)
        self.assertNotIn('<script>', markup)
        pd.testing.assert_frame_equal(current, original)

    def test_history_chart_preserves_observations_and_risk_thresholds(self) -> None:
        history = pd.DataFrame({'global': [-0.4, 1.2]}, index=pd.to_datetime(['2025-01-01', '2025-02-01']))
        with patch.object(dashboard_view.st, 'plotly_chart') as render:
            dashboard_view._render_historical_chart(history)
        figure = render.call_args.args[0]
        self.assertEqual(list(figure.data[0].y), [-0.4, 1.2])
        self.assertEqual(list(figure.data[0].x), list(history.index))
        self.assertEqual(figure.layout.shapes[0].y0, dashboard_view.ZSCORE_WARNING)
        self.assertEqual(figure.layout.shapes[1].y0, dashboard_view.ZSCORE_DANGER)

    def test_complete_streamlit_dashboard_and_faq_render_without_exception(self) -> None:
        # Isolated test fixtures, never source or preview market data.
        script = f'''
import sys
sys.path.insert(0, {str(ROOT)!r})
sys.path.insert(0, {str(ROOT / 'tests')!r})
from test_snapshot_contract import fixture_frames, fixture_metadata
from dashboard_view import render_dashboard, render_method_faq
from ui import configure_page, inject_theme
configure_page()
inject_theme()
current, backtest, historical = fixture_frames()
metadata = fixture_metadata(current, historical)
render_dashboard(current, backtest, historical, metadata)
render_method_faq(metadata)
'''
        app = AppTest.from_string(script, default_timeout=15).run()
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(len(app.dataframe), 8)
        markup = '\n'.join(element.value for element in app.markdown)
        self.assertIn('Stress</em> <span>macro US', markup)
        self.assertIn('Tensions dominantes', markup)
        self.assertIn('point-in-time', markup)
        self.assertIn('calculateur aaaaaaaaaaaa', markup)

    def test_activation_pins_match_release_files(self) -> None:
        script = SCRIPT.read_text()
        for variable, file in (
            ('new_hash', ROOT / 'ui.py'),
            ('view_new_hash', ROOT / 'dashboard_view.py'),
            ('font_hash', ROOT / 'assets/fonts/jetbrains-mono-latin-wght-normal.woff2'),
            ('license_hash', ROOT / 'assets/fonts/OFL.txt'),
        ):
            pinned = re.search(rf'^{variable}=([0-9a-f]{{64}})$', script, re.MULTILINE)
            self.assertIsNotNone(pinned)
            self.assertEqual(pinned.group(1), hashlib.sha256(file.read_bytes()).hexdigest())

    def test_activation_syntax_and_preserves_calculator_provenance(self) -> None:
        result = subprocess.run(  # noqa: S603
            ['/bin/bash', '-n', str(SCRIPT)], capture_output=True, text=True, check=False
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        script = SCRIPT.read_text()
        self.assertIn('cmp -- "$backup/calculator-sha" "$active/DEPLOYED_SHA"', script)
        self.assertIn('"$old_hash"|"$title_hash"|"$brand_hash")', script)
        self.assertLess(script.index('trap recover EXIT'), script.index('assets_changed=1'))
        self.assertLess(
            script.index('install -o root -g usdashboard -m 0640 "$backup/new-font.woff2"'),
            script.index('changed=1\nsystemctl stop'),
        )
        self.assertNotIn('snapshot_builder.py', script)
        self.assertNotIn('pip install', script)
        self.assertIn('cp -a "$backup/dashboard_view.py" "$view_candidate"', script)
        self.assertIn('if (( assets_present == 0 )); then', script)
        self.assertLess(
            script.index('systemctl stop "$service"\nmv -f'),
            script.index('mv -f -- "$candidate" "$live"\nmv -f'),
        )
