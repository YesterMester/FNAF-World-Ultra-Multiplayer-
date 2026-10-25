"""A desktop launcher that uses Steam's installed Proton and matching runtime."""
import os
from pathlib import Path


SCRIPT = r'''#!/usr/bin/env bash
set -euo pipefail
game_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
fail() {
    printf '%s\n' "$1" >&2
    if command -v kdialog >/dev/null; then kdialog --error "$1"; fi
    exit 1
}
[[ -f "$game_dir/Fnaf World Ultra.exe" ]] || fail 'The game executable is missing. Run the multiplayer patcher again.'
steam_root=''
for candidate in "$HOME/.local/share/Steam" "$HOME/.steam/steam" "$HOME/.steam/root"; do
    if [[ -d "$candidate/steamapps" ]]; then steam_root=$(readlink -f -- "$candidate"); break; fi
done
[[ -n "$steam_root" ]] || fail 'Install Steam and a Proton compatibility tool, then try again.'
libraries=("$steam_root")
while IFS= read -r library; do
    if [[ -d "$library/steamapps" && "$library" != "$steam_root" ]]; then libraries+=("$library"); fi
done < <(sed -n 's/^[[:space:]]*"path"[[:space:]]*"\([^"]*\)".*/\1/p' "$steam_root/steamapps/libraryfolders.vdf")
proton=${FWUM_PROTON_PATH:-}
if [[ -z "$proton" ]]; then
    candidates=() stable=()
    shopt -s nullglob
    for library in "${libraries[@]}"; do
        for candidate in "$library"/steamapps/common/Proton*/proton; do
            if [[ -x "$candidate" ]]; then
                candidates+=("$candidate")
                if [[ "$(basename -- "$(dirname -- "$candidate")")" =~ ^Proton\ [0-9] ]]; then stable+=("$candidate"); fi
            fi
        done
    done
    for candidate in "$steam_root"/compatibilitytools.d/*/proton; do
        if [[ -x "$candidate" ]]; then candidates+=("$candidate"); fi
    done
    if ((${#stable[@]})); then candidates=("${stable[@]}"); fi
    if ((${#candidates[@]})); then
        proton=$(printf '%s\n' "${candidates[@]}" | sort -Vr | head -n 1)
    fi
fi
[[ -x "$proton" ]] || fail 'No installed Proton was found. Install Proton from Steam, then try again.'
[[ -f "$(dirname -- "$proton")/toolmanifest.vdf" ]] || fail 'The selected Proton installation has no tool manifest. Verify it in Steam.'
tool_id=$(sed -n 's/.*"require_tool_appid"[[:space:]]*"\([0-9]*\)".*/\1/p' "$(dirname -- "$proton")/toolmanifest.vdf")
runtime=''
for library in "${libraries[@]}"; do
    manifest="$library/steamapps/appmanifest_${tool_id}.acf"
    if [[ -n "$tool_id" && -f "$manifest" ]]; then
        install_dir=$(sed -n 's/.*"installdir"[[:space:]]*"\([^"]*\)".*/\1/p' "$manifest")
        [[ -x "$library/steamapps/common/$install_dir/run" ]] && runtime="$library/steamapps/common/$install_dir/run"
    fi
done
[[ -n "$runtime" ]] || fail 'The Steam Linux Runtime required by Proton is missing. Install or verify Proton in Steam.'
export STEAM_COMPAT_DATA_PATH=${FWUM_COMPAT_DATA_PATH:-"$game_dir/.proton"}
export STEAM_COMPAT_CLIENT_INSTALL_PATH="$steam_root"
export STEAM_COMPAT_INSTALL_PATH="$game_dir"
export SteamAppId=0 SteamGameId=0 WINEDEBUG=-all
mkdir -p -- "$STEAM_COMPAT_DATA_PATH"
cd -- "$game_dir"
exec "$runtime" -- "$proton" run "$game_dir/Fnaf World Ultra.exe"
'''


def write_launcher(out_dir):
    if not os.sys.platform.startswith("linux"):
        return
    out = Path(out_dir).resolve()
    script = out / "Play Multiplayer.sh"
    script.write_text(SCRIPT, encoding="utf-8")
    script.chmod(script.stat().st_mode | 0o111)
    # Desktop Entry Exec fields are parsed directly, without a shell.
    target = str(script).replace("\\", "\\\\").replace('"', '\\"').replace("`", "\\`").replace("$", "\\$").replace("%", "%%")
    desktop = out / "FNaF World Ultra Multiplayer.desktop"
    desktop.write_text('[Desktop Entry]\nType=Application\nName=FNaF World Ultra Multiplayer\n'
                       'Comment=Play local or online co-op\nExec="%s"\nIcon=applications-games\nTerminal=false\n'
                       'Categories=Game;\n' % target, encoding="utf-8")
    desktop.chmod(desktop.stat().st_mode | 0o111)
