#!/bin/bash
# UI-only activation. Run personally with sudo from the exact checkout.
# Calculator, snapshots, dependencies and scheduler remain unchanged.
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
title_hash=f099c1e666703a4907a0318e77a8815a2f5767d385fd2c650b1ceb91e170fb9b
new_hash=7a500bfc387b12f4a0aaaadafce35e6bfd61beb8bea0f62bf8435652df7ccb90
font_path=assets/fonts/jetbrains-mono-latin-wght-normal.woff2
license_path=assets/fonts/OFL.txt
font_hash=18be452724bfdc236c074ca94a249a7f41a86752c7d04ab258ce9ed5651f6a7e
license_hash=403581b69dac5cff4079205e01c6b467e56af449ecbd7247693ddb1baafa005b
exec 9>/run/lock/macro-runtime-deployment.lock
flock -n 9 || fail 'Autre activation en cours.'
[[ -d $active && ! -L $active ]] || fail 'Arborescence active inattendue.'
[[ -f $live && ! -L $live ]] || fail 'Fichier UI actif inattendu.'
case $(sha256sum "$live" | cut -d ' ' -f 1) in
    "$old_hash"|"$title_hash") ;;
    *) fail 'UI active différente : inspection requise.' ;;
esac
for directory in "$active/assets" "$active/assets/fonts"; do
    [[ ! -L $directory && ( ! -e $directory || -d $directory ) ]] || fail 'Répertoire de police inattendu.'
done
for asset in "$font_path" "$license_path"; do
    [[ ! -e $active/$asset && ! -L $active/$asset ]] || fail 'Police déjà présente : inspection requise.'
done
systemctl is-active --quiet "$service" || fail 'Service initialement inactif.'
[[ $(curl --fail --silent --max-time 5 http://127.0.0.1:8501/_stcore/health) == ok ]] \
    || fail 'Healthcheck initial en échec.'

backup=$(mktemp -d /var/backups/macro-ui-title.XXXXXXXX)
cp -a "$live" "$backup/ui.py"
cp -a "$active/DEPLOYED_SHA" "$backup/calculator-sha"
git_release show "$release_sha:ui.py" > "$backup/new-ui.py"
[[ $(sha256sum "$backup/new-ui.py" | cut -d ' ' -f 1) == "$new_hash" ]] || fail 'UI candidate incorrecte.'
git_release show "$release_sha:$font_path" > "$backup/new-font.woff2"
git_release show "$release_sha:$license_path" > "$backup/new-OFL.txt"
[[ $(sha256sum "$backup/new-font.woff2" | cut -d ' ' -f 1) == "$font_hash" ]] || fail 'Police candidate incorrecte.'
[[ $(sha256sum "$backup/new-OFL.txt" | cut -d ' ' -f 1) == "$license_hash" ]] || fail 'Licence candidate incorrecte.'
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
assets_changed=0
recover() {
    local status=$?
    local ui_restored=1
    trap - EXIT HUP INT TERM
    set +e
    if (( changed == 1 )); then
        if cp -a "$backup/ui.py" "$candidate" && mv -f -- "$candidate" "$live"; then
            if systemctl restart "$service"; then
                echo "UI_ROLLBACK $backup" >&2
            else
                echo "UI_RESTORED_RESTART_FAILED $backup" >&2
            fi
        else
            ui_restored=0
            echo "UI_ROLLBACK_FAILED $backup" >&2
        fi
    fi
    if (( assets_changed == 1 && ui_restored == 1 )); then
        [[ ! -f $active/$font_path ]] || mv -- "$active/$font_path" "$backup/failed-font.woff2"
        [[ ! -f $active/$license_path ]] || mv -- "$active/$license_path" "$backup/failed-OFL.txt"
    fi
    exit "$status"
}
trap recover EXIT
trap 'exit 129' HUP
trap 'exit 130' INT
trap 'exit 143' TERM
for directory in "$active/assets" "$active/assets/fonts"; do
    [[ -d $directory ]] || install -d -o root -g usdashboard -m 0750 "$directory"
done
assets_changed=1
install -o root -g usdashboard -m 0640 "$backup/new-font.woff2" "$active/$font_path"
install -o root -g usdashboard -m 0640 "$backup/new-OFL.txt" "$active/$license_path"
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
if '<h1><em>Stress</em> <span>macro US</span></h1>' not in render.call_args.args[0]:
    raise SystemExit('Titre actif incorrect')
with patch.object(ui.st, 'markdown') as render:
    ui.render_header('radar')
if '<span class="brand-0">0</span><span>g</span><span class="brand-cursor" aria-hidden="true">_</span>' not in render.call_args.args[0]:
    raise SystemExit('Logo actif incorrect')
with patch.object(ui.st, 'markdown') as render:
    ui.inject_theme()
if 'data:font/woff2;base64,' not in render.call_args.args[0]:
    raise SystemExit('Police locale indisponible')
print('HERO_OK Stress macro US')
print('LOGO_OK JetBrains Mono, zero turquoise, curseur rose')
PY
)
cmp -- "$backup/calculator-sha" "$active/DEPLOYED_SHA"
[[ $(sha256sum "$live" | cut -d ' ' -f 1) == "$new_hash" ]] || fail 'Empreinte UI active incorrecte.'
[[ $(sha256sum "$active/$font_path" | cut -d ' ' -f 1) == "$font_hash" ]] || fail 'Empreinte police active incorrecte.'
[[ $(sha256sum "$active/$license_path" | cut -d ' ' -f 1) == "$license_hash" ]] || fail 'Empreinte licence active incorrecte.'
printf '%s\n' "$release_sha" > "$backup/ui-source-sha"
trap - EXIT HUP INT TERM
echo "UI_DEPLOYMENT_OK $release_sha"
echo "UI_BACKUP $backup"
