---
name: decode
description: Guidance for the vhs-decode step (.lds → .tbc + .tbc.json). Use when configuring decode parameters, hitting decode errors, debugging segment-mode partial decodes, or wiring up project flags.
---

# Decode step (vhs-decode)

Takes the raw RF capture (`.lds`) and produces time-base-corrected output (`.tbc`, `.tbc.chroma`, `.tbc.json`). This is the most CPU-intensive part of the pipeline — typically ~real-time on a modern CPU (so 1 hour of tape = ~1 hour of decode time per core, parallelisable).

Command lives at `job_queue_manager.py:_execute_vhs_decode_job` (around line 624). The tool is found via:
1. `shutil.which('vhs-decode')` (pip-installed version preferred)
2. `external/vhs-decode/vhs-decode` (submodule fallback)

## The hard-won lessons

### Segment mode for testing

For testing decode/export changes without redoing a full-tape decode, use segment mode via `segment_config.py`. The job manager reads `segment_config` for the project at decode time:

```python
segment_start_frame = segment_config.get('start_frame_pal', 0)
frame_count = segment_config.get('frame_count_pal', 0)
# passes -s <start_frame> -l <frame_count> to vhs-decode
```

The PAL and NTSC start/length are stored separately so the same segment_config can apply to either format.

Important: when segment mode is active, `total_frames` on the job object is updated to the segment length (`frame_count`), and `current_frame` in progress callbacks is *relative to the segment start*. So progress percentage shows segment progress, not absolute file position.

### Project flags

`ProjectFlagsManager` (in `project_flags.py`) stores per-project vhs-decode flag overrides. Read via `flags_manager.get_cli_flags(project_name, 'decode')`. If flags aren't set for a project, the decoder uses the hardcoded defaults: `--no_resample --recheck_phase --ire0_adjust`.

Tape speed (`SP`, `LP`, `EP`) and video standard (PAL/NTSC) are also job parameters, set via the menu or workflow control centre.

### Total frame count

`ParallelVHSDecoder.get_frame_count_from_json` reads the capture's `.json` metadata to determine total frames for progress calculation. If that's missing, progress shows as 0% throughout. The `_get_total_frames_for_job` helper in `shared/progress_display_utils.py` caches this per project to avoid repeated JSON parsing.

### Progress parsing

vhs-decode emits `File Frame N: VHS` lines on stdout. The job manager parses these with regex `r'File Frame (\d+):'` and updates job progress. FPS is computed from frame count delta over runtime, not from a separate vhs-decode FPS field.

### What decode does NOT do

- Doesn't touch the audio file (`.flac` is independent)
- Doesn't deinterlace or scale
- Doesn't produce a viewable video — that's the export step

### Output files

After successful decode:
- `<name>.tbc` — luma TBC
- `<name>.tbc.chroma` — chroma TBC  
- `<name>.tbc.json` — frame timing, field metadata, sample positions
- `<name>.log` — lddecode debug log (very large, useful for diagnosing video-level issues)

Success check in `job_queue_manager.py:789-796`: both `.tbc` and `.tbc.json` must exist and be non-zero size.

## Files of interest

- `job_queue_manager.py:_execute_vhs_decode_job` — execution and progress parsing
- `parallel_vhs_decode.py` — older interface used for standalone parallel decode + frame counting
- `external/vhs-decode/` — submodule with the actual decoder
- `project_flags.py:ProjectFlagsManager` — per-project flag overrides
- `segment_config.py:load_segment_config` — partial-decode configuration
