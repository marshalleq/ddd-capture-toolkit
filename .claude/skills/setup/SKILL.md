---
name: setup
description: Guidance for setup.sh, environment files, and dependency management. Use when adding external tool/library dependencies, modifying setup.sh, debugging install failures, or when a pipeline step fails due to a missing system feature (e.g. ffmpeg compiled without a needed library).
---

# Setup, install modes, and dependencies

`setup.sh` is the project's installer. Always consider both install modes when adding a dependency — they have different paths to "ffmpeg is on PATH" and other tools.

## The two install modes

### Easy mode (`./setup.sh` or `./setup.sh --easy`) — default

- Uses pre-built conda-forge packages
- Reads `environment-linux.yml` / `environment-macos.yml` / `environment-windows.yml` to create the conda env
- For tools not on conda: downloads pre-built (vhs-decode from PyPI, tbc-video-export AppImage)
- Fast (~5 min); no compilation
- **Dependency point**: anything ffmpeg needs at runtime must be installed via the conda env (conda-forge ffmpeg is feature-rich and includes most things, but ensure the *library* package is also in the env yml so it's present on disk)

### Performance mode (`./setup.sh --performance`)

- Compiles ffmpeg, ld-decode, vhs-decode from source via `build-scripts/build-*.sh`
- Uses `--march=native` for CPU-specific optimisation by default
- Requires git submodules (`git submodule update --init --recursive`)
- Slower (~30 min); produces faster binaries
- **Dependency point**: any optional ffmpeg library must be both:
  1. Available in the build environment (add to `environment-linux.yml`)
  2. Explicitly enabled in `build-scripts/build-ffmpeg.sh` via `--enable-lib<name>`

## When adding a new ffmpeg / external-tool dependency

Always update **all three** of:

1. **The relevant `environment-*.yml`** (linux/macos/windows) to install the library
2. **`build-scripts/build-ffmpeg.sh`** to add `--enable-lib<name>` in both the main and fallback configure calls
3. **`check_dependencies.py`** to verify the feature is actually present (loud failure, no fallback). Use the pattern of inspecting `ffmpeg -hide_banner -version` output for `--enable-libxxx` strings.

The `check_dependencies.py` check is critical: the toolkit's philosophy is no silent fallbacks. A missing feature should fail loudly with a clear remediation message, not silently produce broken output.

## Historical example: libsoxr (audio resampler)

When final-mux added `aresample=resampler=soxr` for high-quality 78125 → 96000 Hz conversion, all three files needed updating:

- `environment-{linux,macos,windows}.yml`: added `- soxr`
- `build-scripts/build-ffmpeg.sh`: added `--enable-libsoxr` to both configure calls
- `check_dependencies.py`: added `check_ffmpeg_features()` that inspects `ffmpeg -hide_banner -version` for `--enable-libsoxr` and fails loudly with install instructions if missing

A failing machine had been built with `build-ffmpeg.sh` before `--enable-libsoxr` was added — the binary lacked the library entirely. The check now catches this at dependency-validation time rather than at final-mux time.

## Per-step tool sources

| Tool | Easy mode | Performance mode |
|------|-----------|------------------|
| ffmpeg | conda-forge `ffmpeg` package | source via `build-ffmpeg.sh` |
| ld-decode / vhs-decode | PyPI `vhs-decode` package | source via `build-vhs-decode.sh` / `build-ld-decode.sh` |
| tbc-video-export | AppImage download | source compile |
| sox | conda-forge `sox` package | conda (not rebuilt) |
| Mono (for align tool) | conda or system package | conda or system package |
| VhsDecodeAutoAudioAlign.exe | bundled at `tools/VhsDecodeAutoAudioAlign.exe` | same |

## clean-setup.sh

Removes the conda env, compiled artefacts, AppImages — full reset. Use when troubleshooting install issues or upgrading between modes. After running, re-run `./setup.sh [--mode]`.

## Detection: is libxxx in this ffmpeg?

```bash
ffmpeg -hide_banner -version | grep -oE '\-\-enable-lib[a-z0-9]+' | sort -u
```

Lists every `--enable-libN` flag baked into the build. Useful for checking what features are available on a given machine without diving into the toolkit's check logic.

## Files of interest

- `setup.sh` — main installer with mode selection
- `clean-setup.sh` — full uninstall
- `environment-linux.yml` / `environment-macos.yml` / `environment-windows.yml` — per-platform conda envs
- `environment.yml` — generic env (used as fallback when platform-specific isn't present)
- `build-scripts/build-ffmpeg.sh` — source build of ffmpeg with CPU-specific optimisations
- `build-scripts/build-vhs-decode.sh` — source build of vhs-decode
- `build-scripts/build-ld-decode.sh` — source build of ld-decode
- `check_dependencies.py` — runtime dependency / feature validator
