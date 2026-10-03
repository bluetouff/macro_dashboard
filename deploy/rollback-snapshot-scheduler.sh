#!/bin/bash
# Installed next to the exact cron backup by install-snapshot-scheduler.sh.
set -euo pipefail
[[ $(id -u) == 0 ]] || { echo 'Exécution administrateur requise.' >&2; exit 1; }
backup_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
[[ $backup_dir == /var/backups/macro-snapshot-scheduler.* ]] || exit 1
[[ -f $backup_dir/macro_dashboard.cron ]] || exit 1
[[ ! -e /etc/cron.d/macro_dashboard ]] || { echo 'Cron déjà présent : arrêt.' >&2; exit 1; }
# Preserve any in-flight publication; never kill a builder to restore cron.
systemctl disable --now macro-snapshot.timer
state=$(systemctl show macro-snapshot.service -p SubState --value)
case "$state" in
    dead|failed) ;;
    *) echo "Collecte active ou relance prévue ($state) : attendre une réussite avant ce rollback." >&2; exit 1 ;;
esac
# No stop/kill command: do not race a retry against an in-flight publication.
cp -a -- "$backup_dir/macro_dashboard.cron" /etc/cron.d/macro_dashboard
rm -f -- /etc/systemd/system/macro-snapshot.timer /etc/systemd/system/macro-snapshot.service
systemctl daemon-reload
echo "SCHEDULER_ROLLED_BACK $backup_dir"
