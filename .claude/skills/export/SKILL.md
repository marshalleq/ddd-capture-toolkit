---
name: export
description: Guidance for the tbc-video-export step (.tbc → _ffv1.mkv). Use when dealing with export flags, segment-mode time-range plumbing, field-order issues, or the 1-indexed start-frame quirk.
---

# Export step (tbc-video-export)

Takes the decoded TBC files and produces a viewable FFV1-encoded MKV (`<name>_ffv1.mkv`). Video only — audio is handled separately by align + final-mux.

This is ffmpeg-driven under the hood, so it reports frame=N fps=NN on stderr that the job manager parses for progress.

## The hard-won lessons

### Segment start is 1-indexed, not 0-indexed

`tbc-video-export` rejects `-s 0`. The recent fix:

> "Convert segment start to 1-indexed for tbc-video-export (rejects -s 0)"

If you're plumbing through segment configs from `segment_config.py` (which uses 0-indexed frame numbers in PAL/NTSC `start_frame_pal/_ntsc`), you have to `+1` before passing to tbc-video-export. The decode step (vhs-decode) accepts 0-indexed natively, so the offset only applies on the export side.

### Field order: bottom-field-first by default

The recent commit "drop oftest, add field-order bff" added explicit `--field-order bff` to the export command. This is correct for typical VHS captures. Without it, you get interleaved fields in wrong order and the resulting video judders. If you ever process a TBC from an unusual source that needs `tff`, this would need to be made configurable.

### Time range plumbing

The same commit mentioned applying segments to the export command. When segment_config is active, the export step needs to receive matching time range arguments so the export covers exactly the decoded frames, no more no less. Without this, you'd get an export that tries to read frames the decode didn't produce.

### Per-project export flags

Like decode, export reads per-project flag overrides via `ProjectFlagsManager.get_cli_flags(project_name, 'export')`. Set via the workflow control centre's flags menu (X column).

### Output is video-only, no audio

`<name>_ffv1.mkv` contains the video stream and (optionally) timecode metadata, but no audio track. That gets added in the final-mux step. This is intentional — keeping audio separate until final-mux means you can re-run align without re-encoding the video.

### Progress

`tbc-video-export` proxies ffmpeg's stderr. The job manager parses `frame=N fps=NN.N` to compute progress. Lives in `job_queue_manager.py` around line 1229 (the `_execute_tbc_export_job` and helper). For TBC export and final-mux, the FPS field on the job object is real ffmpeg fps; for lds-compress and audio-align, it's bytes/sec (formatted as MB/s in the UI).

### Decoder output codec

FFV1 lossless, in MKV container. Suitable for archival but big (~50% of LDS size typically). Different from `lds-compress` which compresses the RF capture itself for archival.

## Files of interest

- `job_queue_manager.py` — `_execute_tbc_export_job` and progress parsing for tbc-video-export
- `project_flags.py:ProjectFlagsManager` — per-project export flag overrides
- `segment_config.py` — 0-indexed segment definitions (remember to +1 for tbc-video-export)
- `external/vhs-decode/` and pip-installed `tbc-video-export` — the actual tool
- `docs/per-project-export-flags-design.md` — design notes
