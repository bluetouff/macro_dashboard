from __future__ import annotations

import base64
import hashlib
import re
import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch

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

    def test_activation_pins_match_release_files(self) -> None:
        script = SCRIPT.read_text()
        for variable, file in (
            ('new_hash', ROOT / 'ui.py'),
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
        self.assertIn('"$old_hash"|"$title_hash")', script)
        self.assertLess(script.index('trap recover EXIT'), script.index('assets_changed=1'))
        self.assertLess(
            script.index('install -o root -g usdashboard -m 0640 "$backup/new-font.woff2"'),
            script.index('changed=1\nmv -f'),
        )
        self.assertNotIn('snapshot_builder.py', script)
        self.assertNotIn('pip install', script)
