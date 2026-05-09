# GPU Compression (`ld-compress -a` / `flaldf`)

The compress step (`.lds` → `.ldf`) can run on the CPU (default) or on the GPU. GPU mode uses `flaldf`, an OpenCL/CUDA-accelerated FLAC encoder, and is typically 5–10× faster than CPU FLAC at level 11. The output is a drop-in replacement for the CPU-produced `.ldf` and is decoded identically by the rest of the toolkit.

## Enabling GPU mode

GPU compression is a **global setting** — flipping it on affects every subsequent compress run, regardless of project. (GPU availability is system-wide, so it doesn't make sense to vary per-project.)

From the main menu: **Settings → Performance Settings → Toggle Compress GPU Acceleration**.

Or programmatically:
```python
from config import set_compress_use_gpu
set_compress_use_gpu(True)
```

The setting persists in `config.json` under `performance_settings.compress_use_gpu`. Default is `False` so existing setups are unaffected.

## Prerequisites

GPU mode requires three things on the host. The toolkit currently does **not** install or check for these — it just calls `ld-compress -a`, which fails fast if any are missing.

### 1. `flaldf` binary on `PATH`

`flaldf` is the OpenCL FLAC encoder upstream `ld-compress` invokes when `-a` is passed. It is **not** part of vhs-decode or this toolkit and must be installed separately.

Verify:
```bash
which flaldf
flaldf --help | head -5
```

Expected: a path under `/usr/local/bin/` (or similar) and the `FlaLDF 0.1.0` banner.

Source: see the upstream wiki linked from `external/vhs-decode/scripts/ld-compress` (`https://github.com/happycube/ld-decode/wiki/ld-compress`).

### 2. OpenCL runtime

`flaldf` reaches the GPU through OpenCL. The runtime is vendor-specific:

| GPU vendor | Runtime package |
|---|---|
| NVIDIA | NVIDIA driver (CUDA toolkit ships an OpenCL ICD) |
| AMD | ROCm OpenCL (`rocm-opencl`) or AMDGPU-PRO OpenCL |
| Intel | `intel-opencl-icd` / `intel-compute-runtime` |

Verify with `clinfo -l`:
```bash
clinfo -l
```

Expected: at least one platform listing your GPU as a device. Example:
```
Platform #0: NVIDIA CUDA
 `-- Device #0: NVIDIA GeForce RTX 4090
```

If `clinfo` itself is missing, install the `clinfo` package — it's a useful diagnostic tool and is small.

### 3. GPU driver loaded

Vendor-specific:
- NVIDIA: `nvidia-smi -L` should list the GPU.
- AMD: `rocminfo` should list the GPU as an agent.
- Intel: integrated/discrete Intel GPUs are usually fine if the kernel driver is loaded.

## What the toolkit does on enable

When a project's compress flag has GPU enabled, the job runner (`job_queue_manager.py:_execute_lds_compress_job`):

1. Invokes `ld-compress -a -l 11 [-p] <input.lds>` instead of `ld-compress -c …`.
2. Detects the resulting `<base>.flac.ldf` and renames it to `<base>.ldf` so the rest of the toolkit (discovery, analyzer, decode) is unaware GPU mode was used.
3. Logs `Running ld-compress (GPU mode): …` for traceability.

Compression level is clamped to 11 in GPU mode (upstream cap; CPU mode permits up to 12). The toolkit currently always passes `-l 11`, so this clamp is a guard against future changes.

## Troubleshooting

- **`flaldf: command not found`** — install `flaldf`.
- **`clCreateContext failed: CL_DEVICE_NOT_FOUND`** — OpenCL platform sees no usable device. Check `clinfo -l`. On NVIDIA, ensure the NVIDIA driver is loaded (not just the open-source `nouveau`). On AMD, ensure ROCm OpenCL is installed *and* your card is supported by the installed ROCm version.
- **Compression succeeds but output is wrong size or fails decode** — verify by uncompressing back to `.lds` and comparing MD5 against the original (`ld-compress -v <file>.ldf`). Disable GPU mode for that project if the round-trip fails. (We have no automated round-trip check today; this is on the planned-features list — see `docs/planned-features.md` feature #3.)
- **No speed improvement vs CPU** — check that the GPU is actually busy during compression (`nvidia-smi -l 1` for NVIDIA; `radeontop` for AMD). If the GPU is idle, OpenCL likely fell back to the CPU device. Force GPU explicitly with `flaldf --opencl-type GPU --opencl-platform "NVIDIA CUDA"` (or appropriate platform name) — this would require a small change to the upstream `ld-compress` script, since the toolkit currently does not pass extra flaldf options through.

## Future work

- A startup health check that verifies `flaldf` and `clinfo -l` before the toolkit offers the GPU flag, plus a clear message when prerequisites are missing.
- Optional `setup.sh --with-gpu` that installs `flaldf` and the appropriate OpenCL runtime (vendor-detected). Today GPU prereqs are entirely manual.
- Tracked alongside feature #3 (auto-delete `.lds` after compress): GPU compression makes the disk-space win larger, so the deletion gate is more valuable when GPU is the default.
