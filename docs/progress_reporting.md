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

| Job Type | Total Frames Source | Progress Method | FPS Calculation | ETA Method |
|----------|---------------------|-----------------|-----------------|------------|
| vhs-decode | Capture `.json` (duration × fps) | Frame regex from stdout | frames / runtime | remaining_frames / fps |
| tbc-export | `.tbc.json` (fields / 2) | FFmpeg `frame=` from stderr | FFmpeg `fps=` from stderr | remaining_frames / fps |
| lds-compress | N/A | Time-based estimation | N/A | N/A |
| audio-align | N/A | Stage-based (fixed %) | N/A | N/A |
| final-mux | N/A | Incremental (2% steps) | N/A | N/A |

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

#### Total Frames Calculation

**N/A** - LDS/TBC compression does not track frame count.

#### Progress Estimation (time-based)

**Source:** `job_queue_manager.py` lines 1429-1472

**Method:** Estimate compression duration based on input file size:
```python
input_size = os.path.getsize(job.input_file)
input_size_gb = input_size / (1024 ** 3)

# Estimate ~60 seconds per GB for compression
estimated_duration = max(60.0, (input_size / (1024**3)) * 60.0)

# Progress based on elapsed time (5% to 90%)
elapsed = current_time - start_time
time_progress = 5.0 + (elapsed / estimated_duration) * 85.0
job.progress = min(max(5.0, time_progress), 90.0)
```

#### FPS / ETA

**Not tracked** - compression jobs do not have frame-based progress.

#### Dependencies

- **Required:** `{basename}.tbc` - decoded TBC file to compress

---

### 4. AUDIO-ALIGN (`audio-align`)

#### Progress Tracking

**Source:** `job_queue_manager.py` lines 940-1118

**Method:** Stage-based progress updates (not frame-based):
```python
# Fixed progress stages:
job.progress = 10.0   # Initial
job.progress = 20.0   # Before subprocess start
job.progress = 30.0   # "Starting VHS audio alignment" detected in output
job.progress = 50.0   # "Running alignment pipeline" detected in output
job.progress = 90.0   # "Audio alignment completed successfully" detected
job.progress = 95.0   # After process completes
job.progress = 100.0  # Output file verified
```

#### FPS / ETA

**Not tracked** - audio alignment uses stage-based progress, not frame-based.

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

3. **lds-compress:** Progress is purely time-based estimation. The `60 seconds per GB` estimate may vary significantly based on CPU speed and compression settings.

4. **audio-align / final-mux:** Progress jumps between fixed stages rather than showing smooth continuous progress.

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

### 2025-12-15
- **Fixed:** vhs-decode jobs now properly set `job.total_frames`, `job.current_frame`, and `job.current_fps` on the job object, enabling FPS and ETA display in the workflow control centre
- **Fixed:** tbc-export jobs now use frame-based progress tracking by parsing FFmpeg's `frame=` output instead of file size estimation
- **Fixed:** tbc-export FPS is now parsed directly from FFmpeg's `fps=` output for accurate real-time display
- **Fixed:** Cancelled jobs now correctly show as CANCELLED instead of being overwritten to COMPLETED or FAILED
