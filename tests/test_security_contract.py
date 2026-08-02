from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from snapshot_builder import load_environment_file

ROOT = Path(__file__).resolve().parents[1]


class SecurityContractTests(unittest.TestCase):
    def test_public_server_contains_no_fred_credential_or_client(self) -> None:
        source = (ROOT / 'app_server.py').read_text(encoding='utf-8')
        self.assertNotIn('FRED_API_KEY', source)
        self.assertNotIn('from fredapi', source)
        self.assertNotIn('import Fred', source)

    def test_ui_loads_no_automatic_third_party_assets(self) -> None:
        source = (ROOT / 'ui.py').read_text(encoding='utf-8').lower()
        self.assertNotIn('@import url', source)
        self.assertNotIn('<script src=', source)
        self.assertNotIn('<iframe', source)
        self.assertNotIn('<img src="http', source)

    def test_streamlit_defensive_options_are_enabled(self) -> None:
        config = (ROOT / '.streamlit' / 'config.toml').read_text(encoding='utf-8')
        self.assertIn('enableCORS = true', config)
        self.assertIn('enableXsrfProtection = true', config)
        self.assertIn('gatherUsageStats = false', config)
        self.assertIn('showErrorDetails = "none"', config)

    def test_world_readable_environment_file_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'env'
            path.write_text('FRED_API_KEY=not-a-real-key\n', encoding='utf-8')
            path.chmod(0o644)
            with self.assertRaisesRegex(RuntimeError, 'lisible par tous'):
                load_environment_file(path)

    def test_environment_file_is_not_evaluated_as_shell(self) -> None:
        variable = 'MACRO_DASHBOARD_TEST_LITERAL'
        os.environ.pop(variable, None)
        try:
            with tempfile.TemporaryDirectory() as temporary:
                path = Path(temporary) / 'env'
                path.write_text(f'{variable}=$(id)\n', encoding='utf-8')
                path.chmod(0o640)
                load_environment_file(path)
                self.assertEqual(os.environ[variable], '$(id)')
        finally:
            os.environ.pop(variable, None)


if __name__ == '__main__':
    unittest.main()
