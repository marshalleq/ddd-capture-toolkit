# VHS Processing Pipeline - Tool Audit

This document describes how each tool in the VHS processing pipeline is sourced and configured for Easy Mode vs Performance Mode.

## Step 1: CAPTURE
| Aspect | Details |
|--------|---------|
| **Tool** | Domesday Duplicator software |
| **Source** | `external/DomesdayDuplicator` |
| **Easy Mode** | Requires separate installation (system-level) |
| **Performance Mode** | Same |
| **Status** | ✅ Working (not managed by this toolkit) |

---

## Step 2: DECODE (.lds → .tbc)
| Aspect | Details |
|--------|---------|
| **Tool** | `vhs-decode` (Python + Cython + Rust) |
| **Lookup Order** | 1) PATH, 2) `external/vhs-decode/vhs-decode` |
| **Easy Mode** | `pip install vhs-decode` from PyPI (pre-compiled wheels) |
| **Performance Mode** | Compiled from `external/vhs-decode` with `-march=native` |
| **Status** | ✅ Working correctly |

---

## Step 3: COMPRESS (.tbc → .tbc.lz4)
| Aspect | Details |
|--------|---------|
| **Tool** | `ld-compress` (shell script wrapping lz4/flac) |
| **Lookup Order** | 1) `external/vhs-decode/scripts/ld-compress`, 2) `external/ld-decode/scripts/ld-compress`, 3) PATH |
| **Easy Mode** | Uses script from submodule (no compilation) |
| **Performance Mode** | Same |
| **Status** | ✅ Working (it's a shell script) |

---

## Step 4: EXPORT (.tbc → .mkv)

| Aspect | Details |
|--------|---------|
| **Wrapper Tool** | `tbc-video-export` (Python wrapper that calls C++ ld-tools) |
| **Lookup Order** | 1) `tools/tbc-video-export.AppImage`, 2) `$CONDA_PREFIX/bin/`, 3) `~/.local/bin/`, 4) PATH |
| **Easy Mode** | AppImage downloaded to `tools/tbc-video-export.AppImage` (bundles all ld-tools) |
| **Performance Mode** | pip-installed wrapper uses compiled ld-tools from conda bin |
| **Status** | ✅ Working |

### Internal C++ Tools Called by tbc-video-export

tbc-video-export internally calls these C++ tools which require `--input-json` support (from vhs-decode fork, NOT mainline ld-decode):

| Internal Tool | Required Option | Easy Mode Source | Performance Mode Source | Status |
|--------------|-----------------|------------------|------------------------|--------|
| `ld-chroma-decoder` | `--input-json` | Bundled in AppImage | Compiled from `external/vhs-decode` | ✅ Fixed |
| `ld-dropout-correct` | `--input-json` | Bundled in AppImage | Compiled from `external/vhs-decode` | ✅ Fixed |
| `ld-process-vbi` | `--input-json` | Bundled in AppImage | Compiled from `external/vhs-decode` | ✅ Fixed |
| `ffmpeg` | N/A | Bundled in AppImage | Compiled with `-march=native` | ✅ Fixed |

### Historical Note

- **vhs-decode** (oyvindln/vhs-decode) ld-tools use `--input-json` - this is what tbc-video-export expects
- **ld-decode** (happycube/ld-decode) ld-tools use `--input-metadata` - this was the WRONG version
- The `build-ld-decode.sh` script was fixed to build from vhs-decode instead of ld-decode

---

## Step 5: ALIGN (audio sync)
| Aspect | Details |
|--------|---------|
| **Tool** | `tools/audio-sync/vhs_audio_align.py` |
| **Source** | Local Python script |
| **Easy Mode** | Python script (no compilation) |
| **Performance Mode** | Same |
| **Status** | ✅ Working |

---

## Step 6: FINAL (mux video + audio)
| Aspect | Details |
|--------|---------|
| **Tool** | `ffmpeg` |
| **Lookup** | PATH (conda or compiled version) |
| **Easy Mode** | conda-forge package (pre-compiled, generic) |
| **Performance Mode** | Compiled from source with `-march=native` |
| **Status** | ✅ Working |

---

## Summary

| Component | Easy Mode | Performance Mode |
|-----------|-----------|------------------|
| **vhs-decode** | PyPI wheel (pre-compiled) | Compiled with `-march=native` |
| **tbc-video-export** | AppImage (bundles everything) | pip package (uses compiled ld-tools) |
| **ld-tools** | Bundled in AppImage | Compiled from `external/vhs-decode` |
| **ffmpeg** | conda-forge package | Compiled with `-march=native` |

---

## Setup Behavior

### Easy Mode (`setup.sh` or `setup.sh --easy`)
1. Creates conda environment from `environment-linux.yml`
2. Installs `vhs-decode` from PyPI
3. Downloads `tbc-video-export.AppImage` to `tools/` directory
4. AppImage bundles tbc-video-export + ld-tools + ffmpeg

### Performance Mode (`setup.sh --performance`)
1. Creates conda environment from `environment-linux.yml`
2. **Removes AppImage** if it exists (to ensure compiled tools are used)
3. Compiles ld-tools from `external/vhs-decode` with native optimizations
4. Compiles vhs-decode from `external/vhs-decode` with native optimizations
5. Compiles ffmpeg from source with native optimizations
6. All compiled tools installed to conda environment bin

---

## Files Involved

### Build Scripts
- `build-scripts/build-ld-decode.sh` - Builds ld-tools from vhs-decode source
- `build-scripts/build-vhs-decode.sh` - Builds vhs-decode Python package
- `build-scripts/build-ffmpeg.sh` - Builds ffmpeg from source

### Tool Lookup (job_queue_manager.py)
The `_execute_tbc_export_job()` function looks for tbc-video-export in this order:
1. `tools/tbc-video-export.AppImage` (easy mode)
2. `$CONDA_PREFIX/bin/tbc-video-export` (performance mode)
3. `~/.local/bin/tbc-video-export`
4. System PATH

### Ignored Files (.gitignore)
- `tools/*.AppImage` - Downloaded AppImages
- `build/` - Compilation artifacts (ffmpeg source, build directories)
