---
name: capture
description: Guidance for the VHS capture step (DomesdayDuplicator RF + sox audio via clockgen-Lite). Use when setting up captures, hitting FX3 sequence drops ("Sequence number mismatch"), seeing sox alsa over-runs, audio/video drift in long captures, or planning USB topology for the rig.
---

# Capture step (DDD + sox via clockgen-Lite)

The capture step produces two files per session:
- `<name>.lds` — raw 10-bit RF samples from the FX3, ~50 MB/s sustained (40 MHz × 10/8 bytes)
- `<name>.flac` — linear audio from the clockgen-Lite ADC at 78125 Hz, 24-bit, 3 channels native (sox `remix 1 2` extracts L+R)

`audio_delay` in `config.json` is a `time.sleep()` between starting DDD and starting sox to compensate for their asymmetric startup latencies. It is NOT used by the align step — only at capture time.

## The hard-won lessons

### USB topology matters a lot

The clockgen-Lite (USB audio) and the FX3 (DDD's RF capture) **must be on different xHCI controllers**. If they share a controller, sustained DDD bulk traffic causes the controller to occasionally be late servicing the clockgen's isochronous audio packets, which the kernel then silently drops. Symptoms:

- "Sequence number mismatch! Expecting N but got M" from DDD (FX3 hardware FIFO overflowed because host wasn't draining)
- Accumulating audio drift of ~200 PPM (sox's FLAC ends up several hundred ms shorter than the video over ~1 hour)

Diagnose with `lsusb -t`. Each xHCI controller registers two USB bus numbers (one USB2, one USB3). Identify the PCI device behind each bus from `dmesg | grep xhci`. If clockgen and DDD share a controller, move one of them physically to a port on a different controller (front panel ports often go through a different controller than back panel).

The external capture SSD (if used) should ideally be on a third controller. With three independent controllers, sustained captures run cleanly.

### Persistent kernel params (already applied on this system)

- `usbcore.usbfs_memory_mb=1000` (via grubby kernel cmdline, NOT modprobe.d — usbcore is built into the kernel) — gives libusb ~25 s of URB headroom for the FX3 stream instead of the default 16 MB / ~400 ms.
- `vm.swappiness=10` (via `/etc/sysctl.d/99-swappiness.conf`) — keeps cold pages in RAM instead of zram, reducing decompression-induced scheduler latency.

Verify with `cat /sys/module/usbcore/parameters/usbfs_memory_mb` and `sysctl vm.swappiness`. The Capture menu options 5 and 6 re-apply these if they ever revert.

### Realtime audio priority

`ddd_clockgen_sync.py` wraps sox in `chrt -r 50` if the capability is available. Granted persistently via Capture menu option 11 (`sudo setcap cap_sys_nice+ep $(which chrt)`). Without realtime, occasional ALSA over-runs accumulate to audible drift on multi-hour captures.

### Sox `--buffer` is 524288

Was 8192 (~17 ms) originally, now 524288 (~1 s) to absorb scheduler stalls. Defined in `build_sox_command_with_device()` and `get_sox_command()` in `ddd_clockgen_sync.py`.

### Sox often shows over-runs that aren't there

Sox can print `sox WARN alsa: over-run` for transient stalls that didn't actually lose samples. ALSA can also drop samples in the kernel ring buffer *before* sox sees them (no warning emitted). So presence of warnings is not equal to data loss, and absence is not equal to no data loss.

The only ground-truth check is the duration math (see below).

### DdD level meter is RMS, not peak — target 0.30–0.45

The level reading shown in the DomesdayDuplicator capture app is **AC RMS** normalised 0..1 (NOT peak or peak-to-peak). The widely-shared community advice "aim for 0.7" is stated in *peak* terms — applying it to an RMS display drives the signal well past the ADC rails. Verified empirically: a capture at RMS ~0.7 produced 1.7 % clipped samples; the same chain at RMS ~0.3 produced 0.04 %. The crest factor of FM RF off a tape head is ~1.5–1.8×, so RMS 0.7 implies peaks of 1.05–1.26 (clipping by definition).

**Use this target:**
- RMS 0.30–0.45 is the safe band (peaks land in the 0.45–0.80 range, well clear of the rails)
- RMS ~0.40 is the sweet spot
- Below 0.20 starts losing demod SNR margin
- Above 0.55 will clip transients even if the steady RMS looks fine

If a tape forces you to crank DdD gain to maximum to hit 0.40, that tape's RF output is genuinely lower than usual — drop the target to 0.30 rather than amplifying further. Better a low clean signal than a hot clipped one. Clipping destroys FM information; quiet does not.

### Start the capture before the tape audibly starts

The decoder (lddecode/vhs-decode) builds its sync-tip and blanking reference levels from the **start of the .lds file** and tracks from there. If the first chunk is degraded or noisy it never gets a foothold and either skips many frames at the start or fails entirely with "Level detection failed - sync or blank is None" / "Unable to determine start of field". Once locked, it can ride through later rough patches; it just can't cold-start on bad signal.

In practice: hit record on the DdD a half-second to a second *before* you hear the tape transport engage. Pre-roll noise, broadcast lead-in, or even snowy junk content is fine — even a marginal broadcast recording has properly-formed sync pulses, and that's all the decoder needs to calibrate. Avoid starting capture exactly on the recorded camera content, especially on weaker consumer-camera recordings.

Symptom of getting this wrong: decoder produces a large log but the .tbc files stay 0 bytes for many minutes before any frames appear (or it gives up entirely on short captures).

### Verifying gain on past captures

`capture_analysis.py` (VHS-Decode menu → option 4 "Analyse Capture Levels") slices a .lds/.ldf at a configurable offset (default 30 s, 60 s long), unpacks via `ld-lds-converter -u` to signed-16-bit LE PCM, computes clipping %, raw min/max, mean, and AC RMS — and writes the .raw alongside for Audacity inspection.

Format details for ad-hoc analysis: ld-lds-converter applies `(raw_10bit - 512) * 64` to produce signed 16-bit LE, so clip-high lands on int16 32704 (not 32767) and clip-low on -32768. DdD-style normalised RMS = `rms_int16 / 32768`.

Audacity raw-PCM import settings: Signed 16-bit, little-endian, mono, sample rate label any value (40 MHz is the real rate but Audacity caps playback — waveform/spectrum shape is unaffected by the label).

## Diagnostic: drift detection without full processing

For any capture, you can confirm audio sync without decoding/aligning/muxing:

```bash
LDS_SIZE=$(stat -c '%s' "name.lds")
LDS_DUR=$(awk "BEGIN { printf \"%.3f\", $LDS_SIZE / 50001303 }")
FLAC_DUR=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "name.flac")
AUDIO_DELAY=$(grep audio_delay config.json | grep -oP '[0-9.]+')
DRIFT=$(awk "BEGIN { printf \"%.3f\", ($LDS_DUR - $AUDIO_DELAY) - $FLAC_DUR }")
echo "Drift: $DRIFT s"
```

- DDD samples at exactly 40 MHz × 10/8 = 50,000,000 bytes/sec nominal, empirically 50,001,303 from cross-checking against decoded video duration.
- `Drift` under ~100 ms over an hour = sync is fine. The align step will absorb it.
- `Drift` > 300 ms over an hour = something is dropping samples (USB topology, scheduling, etc.).

## When things still go wrong

After verifying topology + kernel params + realtime priority, if you still see drift:
- Check `dmesg | grep -iE 'xhci|usb.*error|urb status'` immediately after the failed capture. Transport-level errors point at cable/bridge issues.
- Capture menu has options to drain swap (3, 4), drop caches (9), compact memory (10) — useful before long captures on a system that's been up for a while.

## Files of interest

- `ddd_clockgen_sync.py` — the main capture orchestrator (`start_capture_and_record`, `shared_capture_process`, sox command builders)
- `config.py` — `audio_delay`, `capture_directory`, audio device detection by name match on "CXADC"
- `ddd_main_menu.py:capture_new_video` — the capture menu (options 1-12 covering capture + system tuning)
- `capture_analysis.py` — slice-and-analyse a .lds/.ldf for clipping/RMS (VHS-Decode menu option 4); also callable as `python3 capture_analysis.py <file> [skip_seconds] [duration_seconds]`
