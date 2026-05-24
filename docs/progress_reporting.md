# Progress Reporting System Documentation

This document describes how progress reporting works for each workflow step in the VHS Workflow Control Centre, including progress bars, FPS calculation, and ETA estimation.

## Overview

The progress reporting system is distributed across multiple files:
- `job_queue_manager.py` - Core job execution and progress tracking
- `job_queue_display.py` - Job queue status display
- `shared/progress_display_utils.py` - Shared progress display formatting and calculations
- `parallel_vhs_decode.py` - Parallel VHS decode with frame counting
- `project_status_display.py` - Enhanced project status with progress bars

## Summary Table

| Job Type | Total Frames Source | Progress Method | FPS / Rate | ETA Method |
|----------|---------------------|-----------------|-----------------|------------|
| vhs-decode | Capture `.json` (duration × fps) | Frame regex from stdout | frames / runtime | remaining_frames / fps |
| tbc-export | `.tbc.json` (fields / 2) | FFmpeg `frame=` from stderr | FFmpeg `fps=` from stderr | remaining_frames / fps |
| lds-compress | `.lds` size (exact) | **Exact input bytes consumed** via `/proc` (Linux) / `libproc` (macOS); falls back to output-bytes-vs-estimated-ratio elsewhere | input bytes/sec (rendered as MB/s) | remaining_input / rate |
| compress-validate | `.lds` size × 4/5 × 2 (exact, lossless decode size) | Bytes streamed through `ld-ldf-reader` | decode bytes/sec (rendered as MB/s) | remaining / rate |
| audio-align | Input `.flac` file size | Output file size / input size | N/A | progress rate based |
| final-mux | N/A | Incremental (2% steps) | N/A | N/A |
| `Nmv` (ldf validation) | `.lds` size × 4/5 × 2 (exact) | Bytes streamed through `ld-ldf-reader` | decode bytes/sec (status bar) | remaining / rate |

---

## Job Type Details

### 1. VHS-DECODE (`vhs-decode`)

#### Total Frames Calculation

**Source:** `parallel_vhs_decode.py` lines 87-114 (`get_frame_count_from_json`)

**Input File Required:** `{basename}.json` (capture metadata from Domesday Duplicator, NOT `.tbc.json`)

**Calculation Method:**
```python
duration_ms = data['captureInfo']['durationInMilliseconds']
duration_seconds = duration_ms / 1000.0

if video_standard.lower() == 'pal':
    frames = int(duration_seconds * 25.0)  # PAL: 25fps
else:  # NTSC
    frames = int(duration_seconds * 29.97)  # NTSC: 29.97fps
```

#### Progress Parsing

**Source:** `job_queue_manager.py` lines 509-531

**Regex Pattern:**
```python
frame_match = re.search(r'File Frame (\d+):', line)
```

**Example Match:** `"File Frame 1000: VHS"`

**Progress Calculation:**
```python
if total_frames > 0:
    progress = (current_frame / total_frames) * 100
    job.progress = min(progress, 99.9)  # Cap at 99.9% until completion
else:
    job.progress = min(current_frame / 1000.0, 50.0)  # Rough estimate when total unknown
```

#### FPS Calculation

**Source:** `shared/progress_display_utils.py` lines 261-274

**Method:** Calculated from progress percentage and runtime:
```python
if total_frames > 0:
    current_frame = int((progress_percentage / 100.0) * total_frames)
    if current_frame > 0 and runtime_seconds > 0:
        fps = current_frame / runtime_seconds
```

**Alternative (from vhs-decode completion output):** `parallel_vhs_decode.py` lines 129-139
```python
# Pattern 1: "(9.36 FPS post-setup)"
fps_match = re.search(r'\(([0-9.]+)\s*fps\s*post-setup\)', line, re.IGNORECASE)

# Pattern 2: "Took X seconds to decode Y frames (Z.Z FPS"
fps_alt_match = re.search(r'decode\s+\d+\s+frames\s*\(([0-9.]+)\s*fps', line, re.IGNORECASE)
```

#### ETA Calculation

**Source:** `shared/progress_display_utils.py` lines 272-281

**Method:** Frame-based ETA (requires 30+ seconds of runtime for stability):
```python
if runtime_seconds > 30 and fps > 0:
    remaining_frames = total_frames - current_frame
    eta_seconds = int(remaining_frames / fps)
```

**Fallback:** Progress-rate based ETA:
```python
if runtime_seconds > 30 and progress_percentage > 0:
    progress_rate = progress_percentage / runtime_seconds
    remaining_progress = 100 - progress_percentage
    eta_seconds = int(remaining_progress / progress_rate)
```

#### Dependencies

- **Required:** `{basename}.json` - capture metadata with `captureInfo.durationInMilliseconds`
- **Required:** `{basename}.lds` or `{basename}.ldf` - RF capture file

---

### 2. TBC-EXPORT (`tbc-export`)

#### Total Frames Calculation

**Source:** `job_queue_manager.py` (`_get_total_frames_from_tbc_json`)

**Input File Required:** `{basename}.tbc.json` (produced by vhs-decode, NOT capture metadata)

**Calculation Method:**
```python
with open(tbc_json_file, 'r') as f:
    data = json.load(f)

if 'fields' in data:
    field_count = len(data['fields'])
    frame_count = int(field_count / 2)  # Interlaced: 2 fields per frame
```

**Critical Note:** The `.tbc.json` file contains a `videoParameters` section required by `tbc-video-export`. This is NOT the same as the capture metadata `.json` file.

#### Progress Parsing (from FFmpeg output)

**Source:** `job_queue_manager.py` (monitor_progress function)

**Total frames from tbc-video-export stderr:**
```python
# Parse "Total Fields:  284578 Total Frames: 142289"
match = re.search(r'Total Frames:\s*(\d+)', clean_line)
```

**Frame progress from FFmpeg stderr:**
```python
# Parse "frame=  123 fps= 45 q=28.0 size=    1234kB time=00:00:05.12"
frame_match = re.search(r'frame=\s*(\d+)', clean_line)
if frame_match:
    current_frame = int(frame_match.group(1))
```

**Progress calculation:**
```python
progress = (current_frame / total_frames) * 100
job.progress = min(progress, 99.9)  # Cap at 99.9% until completion
```

#### FPS Calculation

**Method:** Parsed directly from FFmpeg's reported FPS, with fallback to calculated FPS:
```python
# Try to parse FFmpeg's reported FPS
fps_match = re.search(r'fps=\s*([0-9.]+)', clean_line)
if fps_match:
    current_fps = float(fps_match.group(1))
else:
    # Fallback: calculate from elapsed time
    current_fps = current_frame / elapsed_time
```

#### ETA Calculation

**Source:** `shared/progress_display_utils.py`

```python
if fps > 0 and total_frames > 0 and current_frame > 0:
    remaining_frames = total_frames - current_frame
    eta_seconds = int(remaining_frames / fps)
```

#### Dependencies

- **Required:** `{basename}.tbc` - decoded TBC file
- **Required:** `{basename}.tbc.json` - TBC metadata with `fields` array and `videoParameters`

---

### 3. LDS-COMPRESS (`lds-compress`)

`lds-compress` represents only the **write phase** of `.lds` → `.ldf` conversion. The post-write Tier 2 FLAC integrity test is a **separate** `compress-validate` job (see §6). The two jobs are auto-chained: a successful `lds-compress` auto-enqueues a `compress-validate`. The matrix shows them as distinct cell states (PROCESSING → VERIFYING).

#### Total "frames" Calculation

Compression is byte-based, not frame-based. The `total_frames` field on the job is repurposed to hold the **expected input byte count** (the `.lds` size), so the matrix renderer's existing progress-bar machinery works without special-casing this job.

```python
total_frames = input_size   # bytes of the source .lds
```

#### Progress Source (preferred): EXACT input-offset

**Source:** `job_queue_manager.py::_read_lds_consumed_bytes` (dispatcher)

The progress bar is driven by the **kernel's record of how many bytes the reader process has consumed from the `.lds`**. This is byte-accurate; there is no compression-ratio estimate anywhere on the preferred path.

| Platform | Mechanism | Helper |
|---|---|---|
| Linux | `/proc/<pid>/fdinfo/<fd>` parses `pos:` line. Matches the reader by walking descendants of the `ld-compress` bash subprocess and comparing fd inode/dev to the `.lds`. | `_linux_read_lds_consumed_bytes` |
| macOS | `libproc.dylib` via `ctypes`. Uses `proc_listpids(PROC_PPID_ONLY)`, `proc_pidinfo(PROC_PIDLISTFDS)`, `proc_pidfdinfo(PROC_PIDFDVNODEPATHINFO)` for inode/dev and `proc_pidfdinfo(PROC_PIDFDFILEINFO)` for the offset. | `_macos_read_lds_consumed_bytes` |
| Windows | No native mechanism is used. (Equivalent path would need `NtQuerySystemInformation` + handle duplication + `NtQueryInformationFile`, which is fragile and requires a debug privilege grant.) | n/a |

The helper caches the discovered `(pid, fd)` tuple between ticks so subsequent reads skip the descendant walk.

Once the offset is read each tick:

```python
real_progress = (input_offset / input_size) * 100.0
# Capped at 99.5% until the subprocess actually exits, so we don't
# snap to 100 while flac is still finalising the last frames.
if real_progress > 99.5:
    real_progress = 99.5
bytes_per_sec = (input_offset - last_input_offset) / dt
```

#### Progress Source (fallback): output bytes + estimated ratio

When the preferred path returns `None` (the reader hasn't spawned yet, has exited, or we're on Windows / a system without `/proc` and `libproc`), the executor falls back to the original behaviour:

```python
EXPECTED_RATIO = 0.70   # median observed compression ratio for FLAC L11 on RF
expected_output_bytes = int(input_size * EXPECTED_RATIO)

# Dynamic-expand if the file is compressing worse than expected
if current_output_bytes > expected_output_bytes:
    expected_output_bytes = int(current_output_bytes * 1.10)

real_progress = (current_output_bytes / expected_output_bytes) * 100.0
```

Both paths use the same 99.5% cap until the subprocess exits.

#### Rate Display

`job.current_fps` holds bytes-per-second. `shared/progress_display_utils.py` flags `lds-compress` as a `MB/s`-unit job, so the matrix cell renders the rate as `NNN MB/s`. The exact path reports **input** bytes/sec (directly related to ETA); the fallback path reports **output** bytes/sec.

#### Tier 1 structural check (still inline)

Once the subprocess exits successfully, `lds-compress` still runs a cheap (~seconds) Tier 1 structural seek check inline before completing. If Tier 1 fails, the compress job itself fails. Tier 1 result is appended to `_validation.log`.

#### ETA

The matrix cell renderer computes ETA from `(100 - percent) / percent * runtime_seconds` (see `project_status_display.py`). On the exact-input path this is honest: percent updates with real input consumption.

#### Dependencies

- **Required:** `{basename}.lds` — RF capture file.
- **Required (Linux):** `/proc` filesystem (always present on Linux). No additional tools.
- **Required (macOS):** `/usr/lib/libproc.dylib` (always present on macOS). No additional tools.
- **No external dependencies on Windows; falls back to output-bytes estimate.**

---

### 3.1. COMPRESS-VALIDATE (`compress-validate`)

Auto-queued after a successful `lds-compress` (gated by the per-project `flac_integrity_check` flag). This is the slow Tier 2 FLAC integrity check moved out of the compress job into its own queue entry so it has visible progress.

#### Total Bytes Calculation

Exact, derived from the source `.lds` size:

```python
expected_bytes = os.path.getsize(lds_path) * 4 // 5 * 2
```

This is the byte count `ld-ldf-reader` will produce when streaming the `.ldf` end-to-end as 16-bit samples. Lossless compression guarantees the decoded count equals this value (±1 MB FLAC frame alignment).

#### Progress Source

`_validate_ldf_flac_integrity` is called with a progress callback. The function streams `ld-ldf-reader`'s stdout in 1 MB chunks; the callback fires every ~2 s with `(bytes_streamed, expected_bytes, mbps)`. The job executor uses these to update `job.progress`, `job.current_frame` (bytes), and `job.current_fps` (bytes/sec, rendered as MB/s).

Progress is byte-accurate from start to finish. There is no estimation step.

#### Matrix Cell State

While the `compress-validate` job is `RUNNING`, the analyzer's `_is_compress_validate_running` returns true and the COMPRESS cell shows `VERIFYING` (bright yellow). The cell's progress bar / percent / MB/s / ETA all come from the running `compress-validate` job entry. When the job completes the cell falls through to the auto-checksum (`HASHING`) and eventually `VALIDATED`.

#### Failure

A FAILED `compress-validate` writes the failure reason to the project's `_validation.log` (Tier 2 entry). The matrix's failed-job machinery surfaces it on the COMPRESS cell — the cell shows `FAILED` red and the error message is available in the job-detail view.

#### Dependencies

- **Required:** `{basename}.ldf` — the freshly-compressed file.
- **Optional:** `{basename}.lds` — used only to derive `expected_bytes`. If absent the job still runs (FLAC stream integrity) but reports progress as bytes-streamed rather than percent.
- **Required tool:** `ld-ldf-reader` (from ld-decode/vhs-decode).

---

### 4. AUDIO-ALIGN (`audio-align`)

#### Progress Tracking

**Source:** `job_queue_manager.py` (`_execute_audio_align_job`)

**Method:** Output file size monitoring - since audio alignment doesn't change the duration, the output file size should be approximately equal to the input file size.

```python
# Get input file size
input_file_size = os.path.getsize(audio_file)

# Monitor output file growth
output_size = os.path.getsize(aligned_output)
progress = min((output_size / input_file_size) * 100, 95.0)
```

**Progress stages:**
- 5% - Job started, input file size captured
- 5-95% - Output file growing (progress = output_size / input_size)
- 100% - Output file verified

#### FPS / ETA

**FPS:** Not tracked - audio alignment isn't frame-based, displays "--fps"

**ETA:** Can be estimated from progress rate over time

#### Dependencies

- **Required:** `{basename}.flac` - original audio capture
- **Required:** `{basename}.tbc.json` - TBC metadata for timing information

---

### 5. FINAL-MUX (`final-mux`)

#### Progress Tracking

**Source:** `job_queue_manager.py` lines 1125-1338

**Method:** Incremental progress during FFmpeg muxing:
```python
job.progress = 10.0   # Initial
job.progress = 20.0   # FFmpeg command built

# During FFmpeg output parsing:
if 'time=' in stderr_line or 'frame=' in stderr_line:
    job.progress = min(job.progress + 2.0, 85.0)  # Increment by 2%

job.progress = 95.0   # After process completes
job.progress = 100.0  # Output verified
```

#### FPS / ETA

**Not tracked** - final muxing uses incremental progress, not frame-based.

#### Dependencies

- **Required:** `{basename}_ffv1.mkv` - exported video from tbc-export
- **Optional:** `{basename}_aligned.wav` - aligned audio (if audio exists)

---

### 6. NMV LDF VALIDATION (`Nmv` command)

Triggered manually by typing `Nmv` (where N is the project number) in the WCC. Not a queued job — runs in a WCC background thread. Same Tier 3 sample-count comparison `compress-validate` performs at Tier 2 (FLAC stream integrity), **plus** a comparison of the decoded byte count against what the source `.lds` would have produced. On PASS, writes a `<basename>.ldf.verified` sidecar — the operator's "safe to delete `.lds`" gate.

#### Refusal Condition

`handle_compress_validate` refuses to start if the source `.lds` is missing: without it there is no comparison to perform, only the lighter FLAC integrity check the compress pipeline already runs. The user sees a clear "Tier 3 requires the .lds" message and no decode work is wasted.

#### Total Bytes / Progress

Same math as `compress-validate`:

```python
expected_bytes = lds_size * 4 // 5 * 2
```

`_run_compress_validate_background` streams `ld-ldf-reader` and updates two surfaces every ~2 s:

1. **Status bar** — `Validating {ldf}: NN.N%  X.X/Y.Y GB  NNN MB/s  ETA Nm SSs`.
2. **Matrix cell** — by writing the same shape of dict the queue progress extractor would produce into `WorkflowAnalyzer.ldf_validation_in_progress[project.name]`:
   ```python
   {'percentage': float, 'fps': bytes_per_sec, 'rate_unit_label': 'MB/s',
    'runtime_seconds': float}
   ```
   The cell renderer reads this dict when the step is `VERIFYING` and produces the same bar / percent / rate / ETA Group used by queued jobs.

#### Matrix Cell State

The analyzer flips the COMPRESS cell to `VERIFYING` (bright yellow) for the duration. The detection is `project.name in analyzer.ldf_validation_in_progress`. The worker `add`s on entry and `pop`s in a `finally` so a crash mid-run can't leave the cell stuck.

#### Result Handling

| Outcome | Status bar | `.ldf.verified` sidecar |
|---|---|---|
| Sample counts match (within 1 MB FLAC alignment) | `✓ Validate PASS … Safe to delete .lds. Sidecar: …` | **Written** with the comparison numbers (sizes, decoded vs expected, tolerance, ratio, elapsed, source `.lds` and `.ldf` hashes). |
| Sample counts disagree | `✗ Validate FAIL … DO NOT DELETE .lds.` | Removed if a stale one was present. |

The `.ldf.verified` file is also the gate for the `stage N` archive-prep command (which refuses to run without it).

#### Dependencies

- **Required:** `{basename}.lds` — uncompressed source.
- **Required:** `{basename}.ldf` — compressed file to validate.
- **Required tool:** `ld-ldf-reader`.

---

## Platform-specific exact-progress paths

The exact (kernel-offset-based) compress progress only works where the OS exposes a remote process's file-descriptor position:

| Platform | Path | Notes |
|---|---|---|
| Linux | `/proc/<pid>/fdinfo/<fd>` — `pos:` line. Descendant walk via `/proc/<pid>/task/<pid>/children`. fd identification via `os.stat()` on the symlink, inode/dev compared. | Always-present. No external tools, no extra privileges. |
| macOS | `libproc.dylib` via `ctypes`. `proc_listpids(PROC_PPID_ONLY)` → children; `proc_pidinfo(PROC_PIDLISTFDS)` → fd list; `proc_pidfdinfo(PROC_PIDFDVNODEPATHINFO)` → vnode inode+dev; `proc_pidfdinfo(PROC_PIDFDFILEINFO)` → byte offset. Struct offsets derived from `<sys/proc_info.h>`. Output buffers oversized to absorb per-arch padding; the only fields read are `vst_dev` (offset +8), `vst_ino` (offset +16), `fi_offset` (offset +8). | The macOS path was structurally verified against Apple's public headers but not yet runtime-tested. Every libproc call is wrapped in `try/except`; on any layout mismatch the helper returns `(None, cached)` and the executor falls back to the output-bytes estimate. macOS users get no worse behaviour than before. |
| Windows | No native path. Equivalent would need `NtQuerySystemInformation` + `DuplicateHandle` + `NtQueryInformationFile` — hundreds of lines, fragile, needs SeDebugPrivilege. Not implemented. | Falls back to output-bytes-vs-estimated-ratio. |

Dispatcher lives at `JobQueueManager._read_lds_consumed_bytes`. Per-platform helpers (`_linux_read_lds_consumed_bytes`, `_macos_read_lds_consumed_bytes`) are independent — each is selected via `sys.platform` and returns `(offset, cache_token)` or `(None, cache_token)`.

---

## UI Display Components

### Progress Bar Rendering

**Source:** `shared/progress_display_utils.py` lines 69-90

```python
@staticmethod
def create_progress_bar(percentage: float, width: int = 20) -> str:
    if percentage < 0:
        percentage = 0
    elif percentage > 100:
        percentage = 100

    progress_chars = int(percentage / 5)  # 20 chars for 100%
    if width != 20:
        progress_chars = int((percentage / 100.0) * width)

    return "█" * progress_chars + "░" * (width - progress_chars)
```

### Time Formatting

**Source:** `shared/progress_display_utils.py` lines 93-122

```python
@staticmethod
def format_time(seconds: int) -> str:
    if seconds <= 0:
        return "Unknown"
    elif seconds < 60:
        return f"{seconds}s"
    elif seconds < 3600:
        return f"{seconds//60}m {seconds%60}s"
    else:
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        return f"{hours}h {minutes}m"
```

### Enhanced Progress Cell Display

**Source:** `project_status_display.py` lines 147-256 (`create_enhanced_status_cell`)

For PROCESSING or QUEUED status, the UI displays a 4-line cell:
1. **Line 1:** Progress bar (11 chars wide)
2. **Line 2:** Percentage (e.g., "45.3%")
3. **Line 3:** FPS (e.g., "9.2fps" or "--fps")
4. **Line 4:** ETA (e.g., "ETA 1h 23m" or "ETA: --:--")

```python
line1 = Text(progress_bar, style="green")
line2 = Text(f"{progress_info['percentage']:.1f}%", style="cyan")
line3 = Text(f"{fps:.1f}fps", style="bright_green") if fps > 0 else Text("--fps", style="dim")
line4 = Text(eta_text, style="yellow") if eta_text else Text("ETA: --:--", style="dim")
```

---

## Key Data Structures

### QueuedJob

**Source:** `job_queue_manager.py` lines 48-94

```python
@dataclass
class QueuedJob:
    # Core fields
    job_id: str
    job_type: str  # "vhs-decode", "tbc-export", "audio-align", "final-mux", "lds-compress"
    status: JobStatus  # QUEUED, RUNNING, COMPLETED, FAILED, CANCELLED

    # Progress tracking
    progress: float = 0.0  # 0-100
    total_frames: int = 0
    current_frame: int = 0
    current_fps: float = 0.0

    # Timing
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
```

### Job Type to Workflow Step Mapping

**Source:** `workflow_analyzer.py` lines 397-406

```python
job_type_mapping = {
    WorkflowStep.DECODE: "vhs-decode",
    WorkflowStep.COMPRESS: "lds-compress",
    WorkflowStep.EXPORT: "tbc-export",
    WorkflowStep.ALIGN: "audio-align",
    WorkflowStep.FINAL: "final-mux",
}
```

---

## File Dependencies Chain

```
CAPTURE produces:
├── {name}.lds or {name}.ldf  (RF capture)
├── {name}.flac               (audio)
└── {name}.json               (capture metadata with captureInfo.durationInMilliseconds)
        │
        ▼
DECODE requires {name}.json for frame count, produces:
├── {name}.tbc                (decoded video)
└── {name}.tbc.json           (TBC metadata with fields array and videoParameters)
        │
        ├─────────────────────────┐
        ▼                         ▼
EXPORT requires {name}.tbc.json   ALIGN requires {name}.flac + {name}.tbc.json
produces:                         produces:
└── {name}_ffv1.mkv               └── {name}_aligned.wav
        │                                 │
        └────────────┬────────────────────┘
                     ▼
FINAL requires {name}_ffv1.mkv + optionally {name}_aligned.wav
produces:
└── {name}_final.mkv
```

---

## Known Limitations and Issues

### Progress Accuracy

1. **vhs-decode:** Progress is accurate when `.json` capture metadata exists. Falls back to rough estimate (frame/1000) when total frames unknown.

2. **tbc-export:** Progress is estimated from file size growth, which can be inaccurate due to variable compression ratios. The `40000 bytes per frame` estimate is a rough approximation.

3. **lds-compress:**
   - On Linux and macOS: **exact** byte-based progress via the kernel-side file offset of the reader process. No estimation step.
   - On other platforms (including Windows): falls back to output-bytes-vs-estimated-compression-ratio (default 0.70 with dynamic expansion).

4. **compress-validate / Nmv:** Exact byte-based progress against `lds_size * 4 / 5 * 2`. Lossless compression guarantees this is the decoded byte count; ±1 MB FLAC frame alignment slack at the very end.

5. **audio-align / final-mux:** Progress jumps between fixed stages rather than showing smooth continuous progress.

### FPS Display

- FPS is only meaningful for `vhs-decode` and `tbc-export` jobs
- For other job types, FPS displays as "--fps" in the UI
- FPS is calculated in real-time as `current_frame / elapsed_time`

### ETA Display

- ETA requires both valid FPS and total_frames to calculate
- Shows "ETA: --:--" when insufficient data available
- ETA is calculated as `remaining_frames / fps`
- ETA becomes more accurate as job progresses and FPS stabilizes

### Missing Metadata Handling

- If `.json` capture metadata is missing, vhs-decode falls back to rough progress estimation
- If `.tbc.json` is missing, tbc-export cannot determine total frames accurately
- The system does not currently warn users when metadata files are missing

---

## Changelog

### 2026-05-25

- **Added:** Exact compress progress on Linux via `/proc/<pid>/fdinfo/<fd>` (input-side file offset of the reader process). No more 70% / 85% / etc. compression-ratio guess; percent advances precisely with bytes consumed from the `.lds`.
- **Added:** Exact compress progress on macOS via `libproc.dylib` and `ctypes` (`proc_pidfdinfo` + `proc_pidinfo`). Mirrors the Linux path. Structural correctness verified against Apple's `<sys/proc_info.h>`; runtime correctness pending real-hardware verification (defensive `try/except` falls back to the estimate path on any failure, so no regression for macOS users).
- **Changed:** Compress job (`lds-compress`) now represents only the write phase — progress 0 → 100% based on bytes-consumed-from-`.lds`. Reaches 100% exactly when the last byte of input is consumed. No reserved bands, no internal Tier 2.
- **Added:** New `compress-validate` job type. Auto-queued after a successful `lds-compress` (gated by the per-project `flac_integrity_check` flag). Runs the slow Tier 2 FLAC integrity check with byte-based 0 → 100% progress against `lds_size * 4 / 5 * 2`. Failure marks the job FAILED; result logged to `_validation.log` as Tier 2.
- **Added:** New `VERIFYING` matrix step status (bright yellow). Triggered by either (a) the analyzer's `ldf_validation_in_progress` dict (populated by `Nmv`) or (b) a `RUNNING` `compress-validate` job. The COMPRESS cell flips to VERIFYING for the duration with its own progress bar / percent / MB/s / ETA — same visual shape as a running decode.
- **Added:** `Nmv` (manual `.ldf` vs `.lds` round-trip) writes a `<basename>.ldf.verified` sidecar on PASS containing the actual comparison numbers, sizes, hashes, and tolerance. Sidecar removed on FAIL.
- **Fixed:** Earlier interim "cap at 89% reserved-band" approach for compress progress caused the cell to freeze for many minutes during the trailing input-read window. Removed; progress now runs cleanly to 100% on the write phase, then the cell flips state to VERIFYING for Tier 2.

### 2025-12-18
- **Added:** audio-align jobs now have real progress tracking based on output file size monitoring
- **Fixed:** Progress bar calculation simplified to use consistent formula across all widths

### 2025-12-15
- **Fixed:** vhs-decode jobs now properly set `job.total_frames`, `job.current_frame`, and `job.current_fps` on the job object, enabling FPS and ETA display in the workflow control centre
- **Fixed:** tbc-export jobs now use frame-based progress tracking by parsing `tbc-video-export` output with `--show-process-output` flag
- **Fixed:** tbc-export FPS is now parsed directly from the tool's progress output for accurate real-time display
- **Fixed:** tbc-export progress now only increases (never goes backwards) when different pipeline stages report different frame counts
- **Fixed:** Cancelled jobs now correctly show as CANCELLED instead of being overwritten to COMPLETED or FAILED
