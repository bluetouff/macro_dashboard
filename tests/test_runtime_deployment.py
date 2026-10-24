from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / 'deploy/update-runtime-dependencies.sh'


class RuntimeDeploymentTests(unittest.TestCase):
    def check_active_venv(self, active: Path) -> subprocess.CompletedProcess:
        source = SCRIPT.read_text()
        guard = source.split('validate_active_venv() {', 1)[1].split('\nvalidate_active_venv\n', 1)[0]
        return subprocess.run(  # noqa: S603
            ['/bin/bash', '-c', 'set -eu; fail() { exit 1; }; active=$1; '
             + 'validate_active_venv() {' + guard + '\nvalidate_active_venv', 'guard', str(active)],
            capture_output=True, text=True, check=False,
        )

    def test_existing_directory_and_versioned_runtime_are_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            active = Path(temporary)
            (active / 'venv').mkdir()
            self.assertEqual(self.check_active_venv(active).returncode, 0)
            (active / 'venv').rmdir()
            target = active / ('runtime-' + 'a' * 40)
            target.mkdir()
            (target / 'DEPENDENCIES_SOURCE_SHA').write_text('a' * 40 + '\n')
            (active / 'venv').symlink_to(target.name, target_is_directory=True)
            self.assertEqual(self.check_active_venv(active).returncode, 0)
            (target / 'DEPENDENCIES_SOURCE_SHA').write_text('b' * 40 + '\n')
            self.assertNotEqual(self.check_active_venv(active).returncode, 0)
            (target / 'DEPENDENCIES_SOURCE_SHA').unlink()
            (active / 'revision').write_text('a' * 40 + '\n')
            (target / 'DEPENDENCIES_SOURCE_SHA').symlink_to(active / 'revision')
            self.assertNotEqual(self.check_active_venv(active).returncode, 0)

    def test_unexpected_runtime_links_are_rejected(self) -> None:
        for link in ('../outside', '/', 'runtime-invalid', 'runtime-' + 'a' * 40):
            with self.subTest(link=link), tempfile.TemporaryDirectory() as temporary:
                active = Path(temporary)
                # Even a correctly named intermediate symlink must not escape.
                (active / ('runtime-' + 'a' * 40)).symlink_to('/', target_is_directory=True)
                (active / 'venv').symlink_to(link, target_is_directory=True)
                self.assertNotEqual(self.check_active_venv(active).returncode, 0)

    def test_rollback_restores_an_existing_versioned_runtime_link(self) -> None:
        source = SCRIPT.read_text()
        recover = source.split('recover() {', 1)[1].split('\ntrap recover EXIT', 1)[0]
        with tempfile.TemporaryDirectory() as temporary:
            active = Path(temporary)
            previous = active / ('runtime-' + 'a' * 40)
            candidate = active / ('runtime-' + 'b' * 40)
            previous.mkdir()
            candidate.mkdir()
            (active / 'backup').mkdir()
            (active / 'venv.rollback-test').symlink_to(previous.name, target_is_directory=True)
            (active / 'venv').symlink_to(candidate.name, target_is_directory=True)
            result = subprocess.run(  # noqa: S603
                ['/bin/bash', '-c', 'active=$1; backup="$active/backup"; '
                 'rollback_venv="$active/venv.rollback-test"; service=web; timer=timer; '
                 'old_moved=1; committed=0; web_stopped=1; timer_stopped=1; '
                 'systemctl() { return 0; }; healthcheck() { return 0; }; '
                 'recover() {' + recover + '\nfalse; recover', 'rollback', str(active)],
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(result.returncode, 1, result.stderr)
            self.assertEqual((active / 'venv').resolve(), previous.resolve())
            self.assertEqual((active / 'backup/failed-venv-link').readlink(), Path(candidate.name))

    def test_pip_bootstrap_is_hash_checked_and_offline_before_downloads(self) -> None:
        source = SCRIPT.read_text()
        self.assertLess(source.index("== fd7f4dfa8190e014013b9f08f3e973f4e4c26ffd179a204895533a7254813a70"),
                        source.index('--no-index --no-deps "$pip_wheel"'))
        self.assertLess(source.index('--no-index --no-deps "$pip_wheel"'),
                        source.index('-r "$payload/requirements.txt"'))
        self.assertIn('pip_bootstrap=$(mktemp -d /var/tmp/macro-pip.XXXXXXXX)', source)
        self.assertIn('chown root:usdashboard "$pip_bootstrap"', source)
        self.assertIn('chmod 0750 "$pip_bootstrap"', source)
        self.assertIn('pip_wheel="$pip_bootstrap/pip-26.2.2-py3-none-any.whl"', source)
        self.assertNotIn('pip_wheel="$runtime/', source)
        workflow = (SCRIPT.parents[1] / '.github/workflows/quality.yml').read_text()
        self.assertIn('fd7f4dfa8190e014013b9f08f3e973f4e4c26ffd179a204895533a7254813a70', workflow)
        self.assertIn('--no-index --no-deps "$pip_wheel"', workflow)
        self.assertNotIn('--trusted-host', source)
        self.assertNotIn('--insecure', source)

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
