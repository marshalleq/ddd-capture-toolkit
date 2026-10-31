#!/bin/bash
# retire-stray-tools.sh - move unmanaged copies of the decode/export tools aside
# Part of DDD Capture Toolkit build system
#
# Usage: retire-stray-tools.sh PATH [PATH ...]
#
# Each PATH is a program found outside the toolkit's conda environment (for
# example /usr/bin/ld-ldf-reader left by a manual install). They are MOVED, never
# deleted, into a 'retired-ld-tools' folder beside the directory they came from
# (/usr/local/retired-ld-tools for /usr/bin and /usr/local/bin, ~/.local/retired-ld-tools
# for ~/.local/bin), so they can be put back with mv.
#
# A program owned by a system package (rpm or dpkg) is left alone and reported:
# moving it would break the package.
#
# sudo is used only when the program's folder is not writable by the current user.

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/common/conda-setup.sh"

owned_by_package() {
    local p="$1"
    if command -v rpm >/dev/null 2>&1 && rpm -qf "$p" >/dev/null 2>&1; then
        return 0
    fi
    if command -v dpkg >/dev/null 2>&1 && dpkg -S "$p" >/dev/null 2>&1; then
        return 0
    fi
    return 1
}

retire_dir_for() {
    case "$1" in
        "$HOME"/*)  echo "$HOME/.local/retired-ld-tools" ;;
        *)          echo "/usr/local/retired-ld-tools" ;;
    esac
}

moved=0
skipped=0
failed=0

for p in "$@"; do
    [[ -e "$p" ]] || continue
    if owned_by_package "$p"; then
        log_warning "Left alone (owned by a system package): $p"
        skipped=$((skipped + 1))
        continue
    fi

    dest_dir="$(retire_dir_for "$p")"
    dest="$dest_dir/$(basename "$p")"
    [[ -e "$dest" ]] && dest="$dest.$(date +%Y%m%d%H%M%S)"

    parent="$(dirname "$p")"
    runner=""
    if [[ ! -w "$parent" || ! -w "$(dirname "$dest_dir")" ]]; then
        runner="sudo"
    fi

    if $runner mkdir -p "$dest_dir" && $runner mv "$p" "$dest"; then
        log_success "Moved aside: $p -> $dest"
        moved=$((moved + 1))
    else
        log_error "Could not move: $p"
        failed=$((failed + 1))
    fi
done

log_info "Retired $moved, left alone $skipped, failed $failed"
[[ $failed -eq 0 ]]
