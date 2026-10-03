from __future__ import annotations

import configparser
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def unit(name: str) -> configparser.ConfigParser:
    config = configparser.ConfigParser(interpolation=None)
    config.read(ROOT / 'deploy' / name)
    return config


class SnapshotSchedulerTests(unittest.TestCase):
    def test_daily_schedule_catches_up_after_shutdown(self) -> None:
        timer = unit('macro-snapshot.timer')
        self.assertEqual(timer['Timer']['OnCalendar'], '*-*-* 06:00:00')
        self.assertEqual(timer['Timer']['Persistent'], 'true')
        self.assertEqual(timer['Timer']['Unit'], 'macro-snapshot.service')
        self.assertEqual(timer['Install']['WantedBy'], 'timers.target')

    def test_failed_or_hung_collections_are_bounded_and_retried(self) -> None:
        service = unit('macro-snapshot.service')
        self.assertEqual(service['Service']['Type'], 'oneshot')
        self.assertEqual(service['Service']['Restart'], 'on-failure')
        self.assertEqual(service['Service']['RestartSec'], '15min')
        self.assertEqual(service['Service']['TimeoutStartSec'], '15min')
        self.assertEqual(service['Service']['TimeoutStopSec'], '30s')
        self.assertEqual(service['Service']['KillMode'], 'control-group')
        self.assertEqual(service['Unit']['StartLimitIntervalSec'], '0')

    def test_existing_validated_builder_and_identity_are_preserved(self) -> None:
        service = unit('macro-snapshot.service')['Service']
        self.assertEqual(service['User'], 'usdashboard')
        self.assertEqual(service['Group'], 'usdashboard')
        self.assertEqual(
            service['ExecStart'],
            '/opt/macro_dashboard/venv/bin/python /opt/macro_dashboard/snapshot_builder.py',
        )
        self.assertNotIn('EnvironmentFile', service)
        self.assertNotIn('FRED_API_KEY', (ROOT / 'deploy/macro-snapshot.service').read_text())

    def test_aggregation_only_follows_success(self) -> None:
        service = unit('macro-snapshot.service')
        self.assertEqual(service['Unit']['OnSuccess'], 'l0g-risk.service')
        self.assertNotIn('ExecStopPost', service['Service'])
        self.assertNotIn('RemainAfterExit', service['Service'])

    def test_write_scope_and_logs_are_explicit(self) -> None:
        service = unit('macro-snapshot.service')['Service']
        self.assertEqual(service['ProtectSystem'], 'strict')
        self.assertEqual(service['ReadWritePaths'], '/var/lib/macro_dashboard/snapshots')
        self.assertEqual(service['NoNewPrivileges'], 'true')
        self.assertEqual(service['StandardError'], 'journal')
        self.assertEqual(service['StandardOutput'], 'journal')

    def test_installer_and_rollback_shell_syntax(self) -> None:
        for name in ['install-snapshot-scheduler.sh', 'rollback-snapshot-scheduler.sh']:
            result = subprocess.run(  # noqa: S603
                ['/bin/bash', '-n', str(ROOT / 'deploy' / name)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_rollback_does_not_kill_an_in_flight_publication(self) -> None:
        script = (ROOT / 'deploy/rollback-snapshot-scheduler.sh').read_text()
        self.assertNotIn('systemctl stop macro-snapshot.service', script)
        self.assertNotIn('systemctl kill', script)
        self.assertNotIn('dead|failed|auto-restart', script)
        self.assertLess(script.index('systemctl disable --now'), script.index('state=$(systemctl show'))
        self.assertLess(script.index('esac'), script.index('cp -a'))


if __name__ == '__main__':
    unittest.main()
