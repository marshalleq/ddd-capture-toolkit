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
