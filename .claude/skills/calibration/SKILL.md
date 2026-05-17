---
name: calibration
description: Guidance for the V2 timecode A/V calibration workflow that measures audio_delay. Use when working on the calibration capture/analyse loop, when ffmpeg/OpenCV/swscaler errors appear in calibration analysis, or when deciding whether to recalibrate after a hardware/topology change.
---

# Calibration step (V2 timecode → audio_delay)

Calibration measures the constant startup offset between when DDD and sox actually begin recording, and stores it as `audio_delay` in `config.json`. The capture step uses this value as a `time.sleep()` to delay whichever process is faster, so both files begin recording the same content moment.

The full workflow:
1. Generate a V2 calibration video (62 s cycle × N cycles, default 2 = 124 s tape segment)
2. Burn to DVD, record DVD → VHS
3. Play VHS and capture with calibration mode ON
4. Decode + export (NOT align or final — just D and E)
5. Run the analyzer to compute `audio_delay`

The V2 pattern embeds frame numbers in two ways simultaneously:
- **Visual**: red/blue colour-coded binary strip at the top of each frame
- **Audio**: FSK tones (400 Hz / 800 Hz) encoding the same frame number

The analyzer decodes both, finds matching timecodes, computes audio-vs-video offset from their positions.

## The hard-won lessons

### Calibration captures go to project temp/, NOT the user's capture_directory

Fixed in `ddd_clockgen_sync.py:2535-2541` and explained in the menu at `ddd_main_menu.py:2742`. When `calibration_mode = True` in config:

```python
if calibration_mode:
    capture_folder = get_temp_folder()      # <project>/temp/
else:
    capture_folder = get_capture_folder()   # user-configured
```

Reason: `analyze_v2_calibration()` in `ddd_main_menu.py:4214` reads `calibration_ffv1.mkv` and `calibration.flac` from the project temp folder. If captures were saved to the user's capture directory, the analyzer wouldn't find them.

### The analyzer uses ffmpeg+yadif, not cv2.VideoCapture

`analyze_v2_calibration_video()` in `ddd_main_menu.py:3824` reads video frames via an ffmpeg subprocess piping deinterlaced BGR24 raw video, NOT via `cv2.VideoCapture.read()`. Why:

OpenCV's swscaler refuses 10-bit interlaced YUV → progressive BGR conversion (which is exactly what tbc-video-export FFV1 captures produce). The error you'd see is:

```
[swscaler @ ...] Cannot convert interlaced to progressive frames or vice versa.
(Invalid argument): fmt:yuv422p10le csp:bt470bg ... -> fmt:bgr24 csp:gbr ...
```

The fix is the pipe at `ddd_main_menu.py:3953-3987`:

```python
ffmpeg_cmd = [
    'ffmpeg', '-hide_banner', '-loglevel', 'error',
    '-i', video_file,
    '-vf', 'yadif=0:-1:0',           # deinterlace, 1 output frame per input
    '-frames:v', str(frames_to_read),
    '-pix_fmt', 'bgr24',
    '-f', 'rawvideo', '-',
]
```

cv2.VideoCapture is still used briefly to get metadata (fps, width, height, total_frames) since metadata reads don't trigger swscaler. Then `cap.release()` and ffmpeg takes over for actual frame data.

### What calibration does and doesn't fix

- **Fixes**: the constant startup-time offset between DDD and sox.
- **Doesn't fix**: rate-based drift between audio and video clocks. That's the job of the align step.

If captured streams are clock-synced (clockgen-Lite), there should be no rate drift to fix. If you see drift, calibration won't help — investigate the capture step instead (USB topology, sample drops).

### When to recalibrate

- After any change to USB topology (different port, different controller)
- After enabling `chrt -r 50` or `tuned latency-performance` (changes process startup latency by a few ms)
- After OS upgrades that touch the audio stack (alsa-lib, pipewire)
- NOT after a missed capture or a sox over-run — `audio_delay` is for startup offset only

Recalibration takes ~3 minutes (capture, decode, export, analyse). Don't conflate it with the painful hour-long content verification.

### Tolerance

Lip-sync threshold is ~40 ms (audio late) or ~100 ms (audio early). The aligner does NOT refine the calibration — whatever `audio_delay` is stored is what gets applied at the next capture. So calibration accuracy directly determines final output sync accuracy.

That said, calibration uses V2 timecodes which decode at sub-frame accuracy (~5 ms tolerance), so the stored value is much tighter than the human-perceptible threshold.

## Files of interest

- `ddd_main_menu.py:analyze_v2_calibration` (line ~4214) — runs the analyser, writes `audio_delay`
- `ddd_main_menu.py:analyze_v2_calibration_video` (line ~3824) — does the visual+audio decode loop
- `tools/timecode-generator/shared_timecode_robust.py` — `SharedTimecodeRobust` decoder for V2 visual timecodes
- `ddd_main_menu.py:display_robust_timecode_menu` — V2 timecode workflow menu (option 3 → calibration menu → V2)
- `ddd_clockgen_sync.py:start_capture_and_record` — branches on `calibration_mode` for path / name / audio_delay handling
