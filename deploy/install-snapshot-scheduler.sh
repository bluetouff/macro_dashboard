#!/bin/bash
# One-time migration of the verified legacy Zen cron. Run personally with sudo.
set -euo pipefail
umask 077

fail() { echo "$*" >&2; exit 1; }
[[ $(id -u) == 0 ]] || fail 'Cette installation doit être lancée par un administrateur.'
[[ $# == 1 && $1 =~ ^[0-9a-f]{40}$ ]] || fail 'SHA Git complet requis.'
release_sha=$1
release_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
[[ $(git -c safe.directory="$release_dir" -C "$release_dir" rev-parse HEAD) == "$release_sha" ]] || fail 'SHA du checkout incorrect.'
[[ -z $(git -c safe.directory="$release_dir" -C "$release_dir" status --porcelain --untracked-files=all -- deploy) ]] || fail 'Fichiers de déploiement modifiés.'

legacy_cron=/etc/cron.d/macro_dashboard
unit_dir=/etc/systemd/system
legacy_sha=f5e9678b61402d6958ded4287c813ec2283fc49e362581febde78a1710d843df
[[ -f $legacy_cron && ! -L $legacy_cron ]] || fail 'Cron historique absent ou lien symbolique : arrêt sans modification.'
[[ $(sha256sum "$legacy_cron" | cut -d ' ' -f 1) == "$legacy_sha" ]] || fail 'Le cron a changé depuis le diagnostic : arrêt sans modification.'
for unit in macro-snapshot.service macro-snapshot.timer; do
    [[ ! -e $unit_dir/$unit && ! -L $unit_dir/$unit ]] || fail "Unité déjà présente : $unit"
    [[ $(systemctl show "$unit" -p LoadState --value) == not-found ]] || fail "Unité déjà chargée : $unit"
done
[[ -x /opt/macro_dashboard/venv/bin/python ]] || fail 'Python du producteur absent.'
[[ -f /opt/macro_dashboard/snapshot_builder.py ]] || fail 'Builder du producteur absent.'
[[ -d /var/lib/macro_dashboard/snapshots ]] || fail 'Répertoire des snapshots absent.'
[[ -f /etc/macro_dashboard/env ]] || fail 'Configuration du producteur absente.'
systemd-analyze verify "$release_dir/deploy/macro-snapshot.service" "$release_dir/deploy/macro-snapshot.timer"

# Do not overlap a running legacy collection. pgrep exit 2 is also blocking.
assert_no_builder() {
    local result=0
    pgrep -u usdashboard -f '[/]opt/macro_dashboard/snapshot_builder[.]py' >/dev/null || result=$?
    [[ $result == 1 ]] || fail 'Collecte déjà active ou contrôle des processus impossible.'
}
assert_no_builder

backup_dir=$(mktemp -d /var/backups/macro-snapshot-scheduler.XXXXXXXX)
cp -a -- "$legacy_cron" "$backup_dir/macro_dashboard.cron"
install -m 0700 "$release_dir/deploy/rollback-snapshot-scheduler.sh" "$backup_dir/rollback.sh"
printf '%s\n' "$release_sha" > "$backup_dir/source-sha"

# Roll back installation errors before any new collection can be started.
# The prior cron and snapshot files remain recoverable; data is never rewritten here.
rollback_install() {
    local result=$?
    trap - EXIT
    if (( result != 0 )); then
        systemctl disable macro-snapshot.timer >/dev/null 2>&1 || true
        rm -f -- "$unit_dir/macro-snapshot.timer" "$unit_dir/macro-snapshot.service"
        cp -a -- "$backup_dir/macro_dashboard.cron" "$legacy_cron"
        systemctl daemon-reload || true
        echo "Installation annulée ; cron restauré. Sauvegarde : $backup_dir" >&2
    fi
    exit "$result"
}
trap rollback_install EXIT
install -m 0644 "$release_dir/deploy/macro-snapshot.service" "$unit_dir/macro-snapshot.service"
install -m 0644 "$release_dir/deploy/macro-snapshot.timer" "$unit_dir/macro-snapshot.timer"
mv -- "$legacy_cron" "$backup_dir/macro_dashboard.cron.disabled"
assert_no_builder
systemctl daemon-reload
systemctl enable macro-snapshot.timer

# No automatic rollback beyond this point: a collector may already be publishing.
# A collection failure is retained in the journal and retried by the service.
trap - EXIT
systemctl start macro-snapshot.timer
systemctl start --no-block macro-snapshot.service
echo "SCHEDULER_INSTALLED $release_sha"
echo "SNAPSHOT_REFRESH_PENDING : vérifier le journal et le snapshot public avant de conclure."
echo "ROLLBACK_COMMAND sudo $backup_dir/rollback.sh"
systemctl show macro-snapshot.timer -p ActiveState -p UnitFileState -p NextElapseUSecRealtime
