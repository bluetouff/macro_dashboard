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
brand_hash=7a500bfc387b12f4a0aaaadafce35e6bfd61beb8bea0f62bf8435652df7ccb90
design_hash=b5f265839fc88a66794d6b25d5a2c640466db36c49dd3b8978cf5e7d696a75df
new_hash=81bd7cbf13fb12beb8fdf27990801e4de9bbe4d1f128671627973a8cb5d3ef39
view_old_hash=e193635155e0b7fbda0f750791be029f1e0c8f69d06d3cf1f3e6d3f4df517878
view_new_hash=7e4dce1e64680f1ec1bf6ddeccc60ae2140878049d3a646c8f2ea2d55a8d121a
font_path=assets/fonts/jetbrains-mono-latin-wght-normal.woff2
license_path=assets/fonts/OFL.txt
font_hash=18be452724bfdc236c074ca94a249a7f41a86752c7d04ab258ce9ed5651f6a7e
license_hash=403581b69dac5cff4079205e01c6b467e56af449ecbd7247693ddb1baafa005b
favicon_path=assets/favicon.svg
favicon_hash=73ff2df7e3dcc29516c8fc89cfe50c54bfaa95861930027b862d742740a32fb5
exec 9>/run/lock/macro-runtime-deployment.lock
flock -n 9 || fail 'Autre activation en cours.'
[[ -d $active && ! -L $active ]] || fail 'Arborescence active inattendue.'
[[ -f $live && ! -L $live ]] || fail 'Fichier UI actif inattendu.'
case $(sha256sum "$live" | cut -d ' ' -f 1) in
    "$old_hash"|"$title_hash"|"$brand_hash"|"$design_hash"|"$new_hash") ;;
    *) fail 'UI active différente : inspection requise.' ;;
esac
[[ -f $active/dashboard_view.py && ! -L $active/dashboard_view.py ]] || fail 'Vue active inattendue.'
case $(sha256sum "$active/dashboard_view.py" | cut -d ' ' -f 1) in
    "$view_old_hash"|"$view_new_hash") ;;
    *) fail 'Vue active différente : inspection requise.' ;;
esac
for directory in "$active/assets" "$active/assets/fonts"; do
    [[ ! -L $directory && ( ! -e $directory || -d $directory ) ]] || fail 'Répertoire de police inattendu.'
done
assets_present=0
if [[ -f $active/$font_path && ! -L $active/$font_path && -f $active/$license_path && ! -L $active/$license_path ]]; then
    [[ $(sha256sum "$active/$font_path" | cut -d ' ' -f 1) == "$font_hash" ]] || fail 'Police active différente.'
    [[ $(sha256sum "$active/$license_path" | cut -d ' ' -f 1) == "$license_hash" ]] || fail 'Licence active différente.'
    assets_present=1
else
    for asset in "$font_path" "$license_path"; do
        [[ ! -e $active/$asset && ! -L $active/$asset ]] || fail 'Police partiellement présente : inspection requise.'
    done
fi
favicon_present=0
if [[ -f $active/$favicon_path && ! -L $active/$favicon_path ]]; then
    [[ $(sha256sum "$active/$favicon_path" | cut -d ' ' -f 1) == "$favicon_hash" ]] || fail 'Favicon actif différent.'
    favicon_present=1
else
    [[ ! -e $active/$favicon_path && ! -L $active/$favicon_path ]] || fail 'Favicon actif inattendu.'
fi
systemctl is-active --quiet "$service" || fail 'Service initialement inactif.'
[[ $(curl --fail --silent --max-time 5 http://127.0.0.1:8501/_stcore/health) == ok ]] \
    || fail 'Healthcheck initial en échec.'

backup=$(mktemp -d /var/backups/macro-ui-title.XXXXXXXX)
cp -a "$live" "$backup/ui.py"
cp -a "$active/dashboard_view.py" "$backup/dashboard_view.py"
cp -a "$active/DEPLOYED_SHA" "$backup/calculator-sha"
git_release show "$release_sha:ui.py" > "$backup/new-ui.py"
git_release show "$release_sha:dashboard_view.py" > "$backup/new-view.py"
[[ $(sha256sum "$backup/new-ui.py" | cut -d ' ' -f 1) == "$new_hash" ]] || fail 'UI candidate incorrecte.'
[[ $(sha256sum "$backup/new-view.py" | cut -d ' ' -f 1) == "$view_new_hash" ]] || fail 'Vue candidate incorrecte.'
git_release show "$release_sha:$font_path" > "$backup/new-font.woff2"
git_release show "$release_sha:$license_path" > "$backup/new-OFL.txt"
[[ $(sha256sum "$backup/new-font.woff2" | cut -d ' ' -f 1) == "$font_hash" ]] || fail 'Police candidate incorrecte.'
[[ $(sha256sum "$backup/new-OFL.txt" | cut -d ' ' -f 1) == "$license_hash" ]] || fail 'Licence candidate incorrecte.'
git_release show "$release_sha:$favicon_path" > "$backup/new-favicon.svg"
[[ $(sha256sum "$backup/new-favicon.svg" | cut -d ' ' -f 1) == "$favicon_hash" ]] || fail 'Favicon candidat incorrect.'
python3 - "$backup/new-ui.py" "$backup/new-view.py" <<'PY'
import sys
from pathlib import Path
for filename in sys.argv[1:]:
    path = Path(filename)
    compile(path.read_bytes(), str(path), 'exec')
PY
candidate="$active/.ui-title-${backup##*/}.py"
view_candidate="$active/.view-design-${backup##*/}.py"
[[ ! -e $candidate && ! -L $candidate ]] || fail 'Candidat déjà présent.'
[[ ! -e $view_candidate && ! -L $view_candidate ]] || fail 'Vue candidate déjà présente.'
install -o root -g usdashboard -m 0640 "$backup/new-ui.py" "$candidate"
install -o root -g usdashboard -m 0640 "$backup/new-view.py" "$view_candidate"

changed=0
assets_changed=0
favicon_changed=0
recover() {
    local status=$?
    local ui_restored=1
    trap - EXIT HUP INT TERM
    set +e
    if (( changed == 1 )); then
        systemctl stop "$service"
        if cp -a "$backup/ui.py" "$candidate" && cp -a "$backup/dashboard_view.py" "$view_candidate" \
            && mv -f -- "$candidate" "$live" && mv -f -- "$view_candidate" "$active/dashboard_view.py"; then
            if systemctl start "$service"; then
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
    if (( favicon_changed == 1 && ui_restored == 1 )); then
        [[ ! -f $active/$favicon_path ]] || mv -- "$active/$favicon_path" "$backup/failed-favicon.svg"
    fi
    exit "$status"
}
trap recover EXIT
trap 'exit 129' HUP
trap 'exit 130' INT
trap 'exit 143' TERM
if (( assets_present == 0 )); then
    for directory in "$active/assets" "$active/assets/fonts"; do
        [[ -d $directory ]] || install -d -o root -g usdashboard -m 0750 "$directory"
    done
    assets_changed=1
    install -o root -g usdashboard -m 0640 "$backup/new-font.woff2" "$active/$font_path"
    install -o root -g usdashboard -m 0640 "$backup/new-OFL.txt" "$active/$license_path"
fi
if (( favicon_present == 0 )); then
    favicon_changed=1
    install -o root -g usdashboard -m 0640 "$backup/new-favicon.svg" "$active/$favicon_path"
fi
changed=1
systemctl stop "$service"
mv -f -- "$candidate" "$live"
mv -f -- "$view_candidate" "$active/dashboard_view.py"
systemctl start "$service"
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
from base64 import b64decode
from pathlib import Path
from streamlit.commands.page_config import _get_favicon_string
import dashboard_view
import ui
with patch.object(ui.st, 'set_page_config') as configure:
    ui.configure_page()
favicon = _get_favicon_string(configure.call_args.kwargs['page_icon'])
prefix = 'data:image/svg+xml;base64,'
if not favicon.startswith(prefix) or b64decode(favicon[len(prefix):], validate=True) != Path('assets/favicon.svg').read_bytes():
    raise SystemExit('Favicon actif incorrect ou non embarqué')
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
with patch.object(ui.st, 'markdown') as render:
    ui.section_heading('Test', 'Note', 'trend')
if '<h2 class="section-heading">' not in render.call_args.args[0]:
    raise SystemExit('Titres de section incorrects')
if 'JetBrains Mono Variable' not in dashboard_view._chart_layout()['font']['family']:
    raise SystemExit('Police des graphiques incorrecte')
print('HERO_OK Stress macro US')
print('LOGO_OK JetBrains Mono, zero turquoise, curseur rose')
print('DESIGN_OK YCT-aligned')
print('FAVICON_OK l0g.fr, SVG embarque')
PY
)
cmp -- "$backup/calculator-sha" "$active/DEPLOYED_SHA"
[[ $(sha256sum "$live" | cut -d ' ' -f 1) == "$new_hash" ]] || fail 'Empreinte UI active incorrecte.'
[[ $(sha256sum "$active/dashboard_view.py" | cut -d ' ' -f 1) == "$view_new_hash" ]] || fail 'Empreinte vue active incorrecte.'
[[ $(sha256sum "$active/$font_path" | cut -d ' ' -f 1) == "$font_hash" ]] || fail 'Empreinte police active incorrecte.'
[[ $(sha256sum "$active/$license_path" | cut -d ' ' -f 1) == "$license_hash" ]] || fail 'Empreinte licence active incorrecte.'
[[ $(sha256sum "$active/$favicon_path" | cut -d ' ' -f 1) == "$favicon_hash" ]] || fail 'Empreinte favicon active incorrecte.'
printf '%s\n' "$release_sha" > "$backup/ui-source-sha"
trap - EXIT HUP INT TERM
echo "UI_DEPLOYMENT_OK $release_sha"
echo "UI_BACKUP $backup"
