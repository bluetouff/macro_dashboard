#!/bin/bash
# Dependency-only release: run personally with sudo after CI for the exact SHA.
# The calculator, its provenance, snapshots, timer units and secrets stay intact.
set -Eeuo pipefail
umask 027
export PYTHONDONTWRITEBYTECODE=1

fail() { echo "$*" >&2; exit 1; }
[[ $(id -u) == 0 ]] || fail 'Activation réservée à un administrateur.'
[[ $# == 1 && $1 =~ ^[0-9a-f]{40}$ ]] || fail 'SHA Git complet requis.'
release_sha=$1
release_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
git_release() { git --no-optional-locks -c safe.directory="$release_dir" -C "$release_dir" "$@"; }
[[ $(git_release rev-parse HEAD) == "$release_sha" ]] || fail 'SHA du checkout incorrect.'
[[ -z $(git_release status --porcelain --untracked-files=all) ]] || fail 'Checkout modifié.'

active=/opt/macro_dashboard
snapshots=/var/lib/macro_dashboard/snapshots
runtime="$active/runtime-$release_sha"
payload="$runtime/release"
service=macro_dashboard.service
timer=macro-snapshot.timer
exec 9>/run/lock/macro-runtime-deployment.lock
flock -n 9 || fail 'Un autre déploiement est en cours.'
[[ -d $active && ! -L $active ]] || fail 'Arborescence active inattendue.'
[[ -d $active/venv && ! -L $active/venv ]] || fail 'Premier remplacement uniquement : venv actif inattendu.'
[[ ! -e $runtime && ! -L $runtime ]] || fail 'Candidat déjà présent ; inspection requise.'
[[ ! -e /etc/cron.d/macro_dashboard ]] || fail 'Cron historique encore actif.'
systemctl is-active --quiet "$service" || fail 'Serveur initialement inactif.'
systemctl is-active --quiet "$timer" || fail 'Timer initialement inactif.'
systemctl is-enabled --quiet "$timer" || fail 'Timer non activé au démarrage.'

healthcheck() {
    local attempt
    for attempt in {1..30}; do
        if [[ $(curl --fail --silent --max-time 2 http://127.0.0.1:8501/_stcore/health) == ok ]]; then
            return 0
        fi
        sleep 1
    done
    return 1
}
healthcheck || fail 'Healthcheck initial en échec.'

backup=$(mktemp -d /var/backups/macro-runtime.XXXXXXXX)
chmod 0700 "$backup"
stamp=$(date -u +%Y%m%dT%H%M%SZ)
rollback_venv="$active/venv.rollback-$stamp"
[[ ! -e $rollback_venv && ! -L $rollback_venv ]] || fail 'Sauvegarde venv déjà présente.'
"$active/venv/bin/python" -m pip freeze --all > "$backup/requirements-before.txt"
cp -a "$active/DEPLOYED_SHA" "$backup/calculator-sha"
systemctl cat "$service" "$timer" macro-snapshot.service > "$backup/units-before.txt"
cd "$active"

# Build at its permanent path: console-script shebangs will never be relocated.
install -d -o usdashboard -g usdashboard -m 0750 "$runtime"
runuser -u usdashboard -- python3 -m venv "$runtime"
install -d -o root -g usdashboard -m 0750 "$payload"
git_release archive "$release_sha" | tar -xf - -C "$payload"
chown -hR root:usdashboard "$payload"
chmod -R go-w "$payload"

assert_same_code() {
    local file
    for file in app.py app_server.py catalog.py dashboard_view.py data.py scoring.py \
        snapshot_builder.py snapshot_contract.py ui.py .streamlit/config.toml; do
        cmp -- "$payload/$file" "$active/$file" || fail "Code actif différent : $file. Release complète requise."
    done
}
assert_same_code
runuser -u usdashboard -- "$runtime/bin/python" -m pip --isolated install \
    --disable-pip-version-check --no-cache-dir --only-binary=:all: \
    -r "$payload/requirements.txt" -c "$payload/constraints.txt" pip setuptools
runuser -u usdashboard -- "$runtime/bin/python" -m pip check
(
    cd "$payload"
    runuser -u usdashboard -- "$runtime/bin/python" -m unittest discover -s tests -v
)
# Freeze the validated environment before any service can execute it.
chown -hR root:usdashboard "$runtime"
chmod -R go-w "$runtime"

check_runtime() {
    local python=$1
    (
        cd "$active"
        runuser -u usdashboard -- "$python" - "$payload/constraints.txt" "$snapshots" <<'PY'
import sys
from importlib.metadata import distributions, version
from pathlib import Path

from packaging.utils import canonicalize_name
from snapshot_contract import load_snapshot_bundle

pins = {}
for line in Path(sys.argv[1]).read_text().splitlines():
    if line and not line.startswith('#'):
        name, expected = line.split('==')
        pins[canonicalize_name(name)] = expected
for dist in distributions():
    name = dist.metadata['Name']
    if pins.get(canonicalize_name(name)) != dist.version:
        raise SystemExit(f'Unpinned or inconsistent dependency: {name} {dist.version}')
bundle = load_snapshot_bundle(Path(sys.argv[2]))
if bundle.metadata['calculator_revision'] != Path('DEPLOYED_SHA').read_text().strip():
    raise SystemExit('Calculator provenance mismatch')
print('RUNTIME_OK', version('GitPython'), version('urllib3'), version('streamlit'))
print('UNCHANGED_SNAPSHOT_OK', bundle.metadata['calculator_revision'], len(bundle.current))
PY
    )
}
check_runtime "$runtime/bin/python"
printf '%s\n' "$release_sha" > "$runtime/DEPENDENCIES_SOURCE_SHA"

timer_stopped=0
web_stopped=0
old_moved=0
committed=0
recover() {
    local result=$?
    trap - EXIT INT TERM
    set +e
    if (( committed == 0 && old_moved == 1 )); then
        systemctl stop "$service"
        if [[ -L $active/venv ]]; then
            mv -- "$active/venv" "$backup/failed-venv-link"
        fi
        mv -- "$rollback_venv" "$active/venv"
        echo "ROLLBACK_RUNTIME $backup" >&2
    fi
    if (( web_stopped == 1 )); then
        systemctl start "$service" || result=1
        healthcheck || result=1
    fi
    if (( timer_stopped == 1 )); then
        systemctl start "$timer" || result=1
    fi
    exit "$result"
}
trap recover EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

# Do not interrupt publication. Stop scheduling, then fail closed on any run or
# pending automatic retry. The trap restores scheduling on every failure.
timer_stopped=1
systemctl stop "$timer"
[[ $(systemctl show macro-snapshot.service -p ActiveState --value) == inactive && \
   $(systemctl show macro-snapshot.service -p SubState --value) == dead ]] \
    || fail 'Collecte ou retry actif : relancer après sa fin.'
process_status=0
pgrep -u usdashboard -f '[/]opt/macro_dashboard/snapshot_builder[.]py' >/dev/null || process_status=$?
[[ $process_status == 1 ]] || fail 'Collecte active ou contrôle des processus impossible.'
assert_same_code
check_runtime "$runtime/bin/python"
web_stopped=1
systemctl stop "$service"
mv -- "$active/venv" "$rollback_venv"
old_moved=1
ln -s "runtime-$release_sha" "$active/venv"
systemctl start "$service"
healthcheck || fail 'Healthcheck après activation en échec.'
check_runtime "$active/venv/bin/python"
"$active/venv/bin/python" -m pip check
cmp -- "$backup/calculator-sha" "$active/DEPLOYED_SHA"
systemctl is-active --quiet "$service"
# No dependency rollback after scheduling resumes: a new builder may start.
committed=1
systemctl start "$timer"
systemctl is-active --quiet "$timer"
trap - EXIT INT TERM
echo "DEPENDENCIES_DEPLOYMENT_OK $release_sha"
echo "ROLLBACK_VENV $rollback_venv"
echo "CONFIG_BACKUP $backup"
systemctl show "$timer" -p ActiveState -p UnitFileState -p NextElapseUSecRealtime
