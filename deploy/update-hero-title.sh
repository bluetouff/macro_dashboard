#!/bin/bash
# One-time UI text activation. Run personally with sudo from the exact checkout.
set -Eeuo pipefail
umask 077

fail() { echo "$*" >&2; exit 1; }
[[ $(id -u) == 0 ]] || fail 'Activation administrateur requise.'
[[ $# == 1 && $1 =~ ^[0-9a-f]{40}$ ]] || fail 'SHA Git complet requis.'
release_sha=$1
release_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
git_release() { git --no-optional-locks -c safe.directory="$release_dir" -C "$release_dir" "$@"; }
[[ $(git_release rev-parse HEAD) == "$release_sha" ]] || fail 'SHA du checkout incorrect.'
[[ -z $(git_release status --porcelain --untracked-files=all) ]] || fail 'Checkout modifié.'

active=/opt/macro_dashboard
live="$active/ui.py"
service=macro_dashboard.service
old_hash=6fd1233ec082b7454d5a5a88ca8bb97598fab53abf680185745486e4bc39a87a
new_hash=f099c1e666703a4907a0318e77a8815a2f5767d385fd2c650b1ceb91e170fb9b
exec 9>/run/lock/macro-runtime-deployment.lock
flock -n 9 || fail 'Autre activation en cours.'
[[ -f $live && ! -L $live ]] || fail 'Fichier UI actif inattendu.'
[[ $(sha256sum "$live" | cut -d ' ' -f 1) == "$old_hash" ]] || fail 'UI active différente : inspection requise.'
systemctl is-active --quiet "$service" || fail 'Service initialement inactif.'
[[ $(curl --fail --silent --max-time 5 http://127.0.0.1:8501/_stcore/health) == ok ]] \
    || fail 'Healthcheck initial en échec.'

backup=$(mktemp -d /var/backups/macro-ui-title.XXXXXXXX)
cp -a "$live" "$backup/ui.py"
cp -a "$active/DEPLOYED_SHA" "$backup/calculator-sha"
git_release show "$release_sha:ui.py" > "$backup/new-ui.py"
[[ $(sha256sum "$backup/new-ui.py" | cut -d ' ' -f 1) == "$new_hash" ]] || fail 'UI candidate incorrecte.'
python3 - "$backup/new-ui.py" <<'PY'
import sys
from pathlib import Path
path = Path(sys.argv[1])
compile(path.read_bytes(), str(path), 'exec')
PY
candidate="$active/.ui-title-${backup##*/}.py"
[[ ! -e $candidate && ! -L $candidate ]] || fail 'Candidat déjà présent.'
install -o root -g usdashboard -m 0640 "$backup/new-ui.py" "$candidate"

changed=0
recover() {
    local status=$?
    trap - EXIT HUP INT TERM
    set +e
    if (( changed == 1 )); then
        cp -a "$backup/ui.py" "$candidate" && mv -f -- "$candidate" "$live"
        systemctl restart "$service"
        echo "UI_ROLLBACK $backup" >&2
    fi
    exit "$status"
}
trap recover EXIT
trap 'exit 129' HUP
trap 'exit 130' INT
trap 'exit 143' TERM
changed=1
mv -f -- "$candidate" "$live"
systemctl restart "$service"
healthy=0
for attempt in {1..30}; do
    if [[ $(curl --fail --silent --max-time 2 http://127.0.0.1:8501/_stcore/health) == ok ]]; then
        healthy=1
        break
    fi
    sleep 1
done
[[ $healthy == 1 ]] || fail 'Healthcheck après activation en échec.'
(
    cd "$active"
    runuser -u usdashboard -- env PYTHONDONTWRITEBYTECODE=1 "$active/venv/bin/python" - <<'PY'
from unittest.mock import patch
import ui
with patch.object(ui.st, 'markdown') as render:
    ui.render_hero({})
if '<h1><em>Stress macro US</em></h1>' not in render.call_args.args[0]:
    raise SystemExit('Titre actif incorrect')
print('HERO_OK Stress macro US')
PY
)
cmp -- "$backup/calculator-sha" "$active/DEPLOYED_SHA"
[[ $(sha256sum "$live" | cut -d ' ' -f 1) == "$new_hash" ]] || fail 'Empreinte UI active incorrecte.'
printf '%s\n' "$release_sha" > "$backup/ui-source-sha"
trap - EXIT HUP INT TERM
echo "UI_DEPLOYMENT_OK $release_sha"
echo "UI_BACKUP $backup"
