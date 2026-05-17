---
name: align
description: Guidance for the audio-align step (VhsDecodeAutoAudioAlign via Mono). Use when working on audio alignment, debugging sync drift in the final output, or understanding what alignment can and cannot fix.
---

# Align step (VhsDecodeAutoAudioAlign)

Resamples the captured audio (`.flac`) to match the TBC's actual field timing, producing `<name>_aligned.wav`. Uses `tools/VhsDecodeAutoAudioAlign.exe` invoked through Mono (it's a .NET app from <https://gitlab.com/wolfre/vhs-decode-auto-audio-align>).

Pipeline: `sox flac → raw stream | mono VhsDecodeAutoAudioAlign.exe stream-align | sox raw → wav` — orchestrated in `tools/audio-sync/vhs_audio_align.py:align_audio`.

## The hard-won lessons

### What it does and doesn't do

The README is explicit:

> "For this to work all 3 streams need to be captured with a synchronous clock source."

The tool:
- **Assumes** all input streams (audio + video RF) started recording at the same wall-clock moment, with sample-clock synchronisation. This is the entire reason clockgen-Lite exists.
- **Corrects** time-varying VCR playback speed variations (wow, flutter, capstan irregularities) by using per-field timing from the TBC JSON to stretch/compress audio segments so each audio sample maps to its correct field.
- **Does NOT** find or correct any startup offset. If `audio_delay` was wrong at capture time, the resulting `_aligned.wav` will have a constant lip-sync offset throughout.
- **Does NOT** receive `audio_delay` as a parameter — it's not part of the command line.

So responsibility splits cleanly:

```
audio_delay (capture time)  →  ensures both streams START at same VHS moment
align tool (post-capture)   →  corrects time-varying VCR speed wobble
```

If you see drift in the final output that's not present in the original FLAC (compare durations), that's a sign the aligner did something unexpected. If you see drift in the FLAC itself (`FLAC duration < (LDS_duration - audio_delay)`), the capture step lost samples and alignment can't recover them.

### What about clock drift between independent oscillators?

Without clockgen-Lite, the audio ADC and the RF sampler run on independent crystals. Typical consumer crystals are ±20-50 PPM, so they can drift apart by ~100 ms per hour. The aligner cannot fix this — it assumes the streams share a clock. With clockgen-Lite (which is required for this toolkit), they do share, and rate drift is near-zero.

### Subcommand and parameters

```
mono VhsDecodeAutoAudioAlign.exe stream-align \
    --sample-size-bytes 6 \
    --stream-sample-rate-hz 78125 \
    --json <tbc.json> \
    < raw_audio_bytes \
    > aligned_raw_audio_bytes
```

`--sample-size-bytes 6` = 24-bit stereo (3 bytes × 2 channels). `--rf-video-sample-rate-hz` defaults to 40000000 (the FX3 sample rate); should match what DDD actually captured at.

### The aligner needs Mono installed

On Linux/macOS only, via `mono` command. Linux package manager: `dnf install mono-core` (Fedora). The check at `tools/audio-sync/vhs_audio_align.py:find_align_tool` looks for the .exe in several known locations.

### What gets trimmed

The aligner trims the start of the audio so its first sample aligns with the first decoded video field. In practice this means the aligned WAV is shorter than the input FLAC by some milliseconds (you saw ~84 ms in the Shaun capture). This is expected behaviour, not data loss.

### Diagnosis tips

If the aligned WAV duration much shorter than the original FLAC:
- Original FLAC and video durations near-equal → alignment trimmed normally
- Original FLAC much shorter than video → capture step lost samples (audio over-runs)

Duration math:
```bash
ffprobe -v error -show_entries format=duration -of csv=p=0 "name.flac"
ffprobe -v error -show_entries format=duration -of csv=p=0 "name_aligned.wav"
ffprobe -v error -show_entries format=duration -of csv=p=0 "name_ffv1.mkv"
```

`gen-drift-csv` subcommand of VhsDecodeAutoAudioAlign generates a CSV of per-field timing drift inside the video — useful for diagnosing whether the VCR's playback was unusually wobbly.

## Upgrading old captures to a standard audio sample rate

The clockgen-Lite native rate (78125 Hz) isn't accepted by some NLEs.
Final-mux can resample the audio to a standard rate (default 96 kHz FLAC)
via `config.json` defaults or per-project audio flags. To retroactively
get that on a capture that was already muxed at 78125 Hz:

1. Delete the existing `_aligned.wav` and `_final.mkv`
2. Re-run **align** (uses the existing `.flac` and `.tbc.json` — fast)
3. Re-run **final-mux** (applies the new resample at the boundary — also fast)

The original `.flac` is the master and is never modified. The align step
continues to operate at 78125 Hz natively. Only final-mux does the
resample, using `aresample=resampler=soxr:precision=33:osf=s32`. So the
upgrade requires no slow decode/export re-runs and produces a fully
alignment-corrected output at the new sample rate.

Do not resample the `.flac` directly before align — it would break
alignment math (which is built around the 78125 Hz native rate).

## Files of interest

- `tools/audio-sync/vhs_audio_align.py` — the wrapper that pipes sox|mono|sox
- `tools/VhsDecodeAutoAudioAlign.exe` — the actual aligner binary
- `job_queue_manager.py:_execute_audio_align_job` — job queue integration
- Upstream: <https://gitlab.com/wolfre/vhs-decode-auto-audio-align>
