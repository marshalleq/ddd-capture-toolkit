---
name: final-mux
description: Guidance for the final-mux step (combine _ffv1.mkv + _aligned.wav → _final.mkv). Use when working on the final muxing stage, choosing audio codecs, or tuning ffmpeg thread counts.
---

# Final-mux step

Combines the video-only `<name>_ffv1.mkv` with the time-aligned `<name>_aligned.wav` to produce `<name>_final.mkv` — the deliverable. Pure ffmpeg, no special tooling.

This is also where the project's audio codec choice gets applied (typically encoding the WAV down to a smaller compressed format).

## The hard-won lessons

### ffmpeg thread count is configurable

Stored in `config.json` under `performance_settings.ffmpeg_threads` (default 4). The comment in the default config explains why:

> "Number of threads FFmpeg uses (0=auto, 1-16=specific). Lower values reduce CPU load during final muxing to keep UI responsive. Recommended: 4-6 threads for most systems."

Higher values speed up final-mux but can starve the menu/UI of CPU during long muxes. On a 16-thread system, 4 leaves plenty for other work. Adjusted via the Performance Settings menu (now reachable at `Main menu → VHS-Decode → Performance Settings`).

### Output structure

`<name>_final.mkv` ends up with:
- Video stream copied from `_ffv1.mkv` as-is (FFV1 lossless, no re-encode)
- Audio stream re-encoded from `_aligned.wav` (24-bit PCM → chosen output codec)

Re-encoding the audio is cheap compared to touching the video.

### Duration should match video exactly

In a clean pipeline:
- `_aligned.wav` duration ≈ video duration (aligner resampled to fit)
- `_final.mkv` duration = video duration

If the final shows the wrong audio duration, look at the aligner's output — the mux step itself rarely introduces issues.

### Progress

Like tbc-export, ffmpeg emits `frame=N fps=NN` on stderr which the job manager parses. Job type `"final-mux"`. In `shared/progress_display_utils.py`, this is one of the "fps means real fps" job types (vs `"lds-compress"` and `"audio-align"` where the same field carries bytes/sec).

### Real-world sanity check

After a final-mux, the duration comparison is:

```bash
ffprobe -v error -show_entries format=duration -of csv=p=0 "name_ffv1.mkv"
ffprobe -v error -show_entries format=duration -of csv=p=0 "name_final.mkv"
```

These two should match within ~1 ms. If they differ noticeably, either:
- The aligner produced an unusually short/long WAV (rare; investigate align step)
- ffmpeg trimmed the muxed output to the shorter stream (audio cut to video duration, or vice versa)

## Files of interest

- `job_queue_manager.py` — `_execute_final_mux_job` (or equivalent) handles the ffmpeg invocation
- `ddd_main_menu.py:display_performance_settings_menu` and `configure_ffmpeg_threads` — thread count tuning
- `config.py` defaults — `performance_settings.ffmpeg_threads`
