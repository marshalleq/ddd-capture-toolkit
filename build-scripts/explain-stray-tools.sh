#!/bin/bash
# explain-stray-tools.sh - say how each unmanaged tool got onto the system
# Part of DDD Capture Toolkit build system
#
# Usage: explain-stray-tools.sh PATH [PATH ...]
#
# Changes nothing. For each program found outside the toolkit's conda environment
# it reports what installed it and the command that removes it the proper way:
# the system package manager (dnf/yum/zypper, apt, pacman, brew), pip, or, for a
# manual install (e.g. 'make install'), plain removal.

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/common/conda-setup.sh"

# Name of the system package manager's remove command, for the hint
remove_cmd() {
    local pkg="$1" manager="$2"
    case "$manager" in
        rpm)
            if command -v dnf >/dev/null 2>&1; then echo "sudo dnf remove $pkg"
            elif command -v zypper >/dev/null 2>&1; then echo "sudo zypper remove $pkg"
            else echo "sudo yum remove $pkg"; fi ;;
        dpkg)   echo "sudo apt remove $pkg" ;;
        pacman) echo "sudo pacman -R $pkg" ;;
    esac
}

# Which pip-installed distribution put this console script here, if any
pip_owner() {
    local p="$1" py
    py="$(command -v python3 || command -v python)" || return 1
    "$py" - "$p" <<'PY' 2>/dev/null
import sys, os
from importlib import metadata
target = os.path.basename(sys.argv[1])
for dist in metadata.distributions():
    for f in (dist.files or []):
        if f.name == target and ('bin' in f.parts or 'Scripts' in f.parts):
            print(dist.metadata['Name']); sys.exit(0)
sys.exit(1)
PY
}

explain() {
    local p="$1" real pkg
    real="$(readlink -f "$p" 2>/dev/null || echo "$p")"
    echo "  $p"

    if command -v rpm >/dev/null 2>&1 && pkg="$(rpm -qf --qf '%{NAME}' "$p" 2>/dev/null)" && [[ -n "$pkg" ]]; then
        echo "      installed by the system package $pkg"
        echo "      remove with:  $(remove_cmd "$pkg" rpm)"
    elif command -v dpkg >/dev/null 2>&1 && pkg="$(dpkg -S "$p" 2>/dev/null | head -n1 | cut -d: -f1)" && [[ -n "$pkg" ]]; then
        echo "      installed by the system package $pkg"
        echo "      remove with:  $(remove_cmd "$pkg" dpkg)"
    elif command -v pacman >/dev/null 2>&1 && pkg="$(pacman -Qoq "$p" 2>/dev/null)" && [[ -n "$pkg" ]]; then
        echo "      installed by the system package $pkg"
        echo "      remove with:  $(remove_cmd "$pkg" pacman)"
    elif [[ "$real" == */Cellar/* ]]; then
        pkg="$(echo "$real" | sed -E 's|.*/Cellar/([^/]+)/.*|\1|')"
        echo "      installed by Homebrew (formula $pkg)"
        echo "      remove with:  brew uninstall $pkg"
    elif pkg="$(pip_owner "$p")" && [[ -n "$pkg" ]]; then
        echo "      installed by pip (package $pkg)"
        echo "      remove with:  python3 -m pip uninstall $pkg"
    else
        echo "      not installed by any package manager I can find (a manual install, for example 'make install')"
        case "$p" in
            "$HOME"/*) echo "      remove with:  rm $p" ;;
            *)         echo "      remove with:  sudo rm $p     (or move it aside: sudo mv $p ~/)" ;;
        esac
    fi
}

for p in "$@"; do
    [[ -e "$p" ]] && explain "$p"
done
