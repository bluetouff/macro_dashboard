from __future__ import annotations

import subprocess
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / 'deploy/update-runtime-dependencies.sh'


class RuntimeDeploymentTests(unittest.TestCase):
    def test_shell_syntax(self) -> None:
        result = subprocess.run(  # noqa: S603
            ['/bin/bash', '-n', str(SCRIPT)], capture_output=True, text=True, check=False
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_publication_is_not_interrupted(self) -> None:
        source = SCRIPT.read_text()
        self.assertNotIn('systemctl stop macro-snapshot.service', source)
        self.assertNotIn('systemctl kill', source)
        self.assertNotIn('rm -', source)
        self.assertLess(source.index('systemctl stop "$timer"'), source.index('process_status=0'))
        self.assertLess(source.index('[[ $process_status == 1 ]]'), source.index('web_stopped=1'))
        self.assertIn('systemctl start "$timer" || result=1', source)

    def test_validation_precedes_reversible_switch(self) -> None:
        source = SCRIPT.read_text()
        for check in ('assert_same_code', '-m unittest discover', 'check_runtime "$runtime/bin/python"'):
            self.assertLess(source.index(check), source.index('mv -- "$active/venv" "$rollback_venv"'))
        self.assertLess(source.index('trap recover EXIT'), source.index('systemctl stop "$timer"'))
        self.assertIn('mv -- "$rollback_venv" "$active/venv"', source)
        self.assertIn("trap 'exit 129' HUP", source)
        self.assertIn('cmp -- "$backup/calculator-sha" "$active/DEPLOYED_SHA"', source)
        self.assertNotIn('snapshot_builder.py" --', source)

    def test_candidate_is_installed_as_service_user_and_then_frozen(self) -> None:
        source = SCRIPT.read_text()
        self.assertIn('runuser -u usdashboard -- "$runtime/bin/python" -m pip --isolated install', source)
        self.assertLess(source.index('chown -hR root:usdashboard "$runtime"'), source.index('web_stopped=1'))
        self.assertIn('git_release archive "$release_sha"', source)
        self.assertIn('DEPENDENCIES_SOURCE_SHA', source)
