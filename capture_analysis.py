#!/usr/bin/env python3
"""
DdD Sync Capture - Capture analysis tool

Extracts a slice of a .lds (10-bit packed) or .ldf (FLAC-compressed) RF capture,
unpacks it to a raw signed-16-bit PCM file suitable for inspection in Audacity,
and prints a numeric summary (clipping %, min/max, mean, RMS).

The DdD ADC is 10-bit unsigned (0..1023) sampled at 40 MHz. The unpacker
applies (raw - 512) * 64 to centre and scale into signed 16-bit, so:
  - raw 0    (clip low)  -> int16 -32768
  - raw 1023 (clip high) -> int16  32704
  - DdD-style normalised RMS = rms_int16 / 32768
"""

import os
import shutil
import subprocess
import sys

DDD_SAMPLE_RATE = 40_000_000          # 40 MHz
LDS_BYTES_PER_SECOND = 50_000_000     # 4 samples per 5 bytes * 40 Msps
RAW_BYTES_PER_SECOND = 80_000_000     # 16-bit (2 bytes) * 40 Msps

CLIP_HIGH_INT16 = 32704               # raw 10-bit 1023 after (-512)*64
CLIP_LOW_INT16 = -32768               # raw 10-bit 0    after (-512)*64


def _format_size(bytes_count):
    for unit in ('B', 'KB', 'MB', 'GB', 'TB'):
        if bytes_count < 1024 or unit == 'TB':
            return f"{bytes_count:.1f} {unit}"
        bytes_count /= 1024


def _which_or_die(tool):
    path = shutil.which(tool)
    if not path:
        raise FileNotFoundError(
            f"{tool} not found on PATH. Install ld-decode tools (ld-lds-converter, ld-ldf-reader)."
        )
    return path


def _slice_lds(input_path, skip_seconds, duration_seconds, slice_path):
    """Slice an .lds file using dd, writing aligned packed bytes to slice_path."""
    # 1 MB (decimal) = 1_000_000 bytes, which is divisible by 5 — keeps quartet alignment.
    bs = 1_000_000
    blocks_per_second = LDS_BYTES_PER_SECOND // bs   # = 50
    skip_blocks = skip_seconds * blocks_per_second
    count_blocks = duration_seconds * blocks_per_second

    cmd = [
        'dd',
        f'if={input_path}',
        f'of={slice_path}',
        f'bs={bs}',
        f'skip={skip_blocks}',
        f'count={count_blocks}',
        'status=none',
    ]
    subprocess.run(cmd, check=True)


def _unpack_lds_to_raw(slice_path, raw_path):
    """Run ld-lds-converter --unpack to produce signed 16-bit LE PCM."""
    tool = _which_or_die('ld-lds-converter')
    subprocess.run(
        [tool, '-q', '-u', '-i', slice_path, '-o', raw_path],
        check=True,
    )


def _extract_ldf_to_raw(input_path, skip_seconds, duration_seconds, raw_path):
    """For .ldf: seek to the right sample, stream into raw_path, truncate to duration."""
    tool = _which_or_die('ld-ldf-reader')
    skip_samples = skip_seconds * DDD_SAMPLE_RATE
    out_bytes = duration_seconds * RAW_BYTES_PER_SECOND

    with open(raw_path, 'wb') as fout:
        reader = subprocess.Popen(
            [tool, input_path, str(skip_samples)],
            stdout=subprocess.PIPE,
        )
        try:
            remaining = out_bytes
            while remaining > 0:
                chunk = reader.stdout.read(min(remaining, 16 * 1024 * 1024))
                if not chunk:
                    break
                fout.write(chunk)
                remaining -= len(chunk)
        finally:
            try:
                reader.stdout.close()
            except Exception:
                pass
            reader.terminate()
            try:
                reader.wait(timeout=5)
            except subprocess.TimeoutExpired:
                reader.kill()


def _compute_stats(raw_path):
    """Compute clipping/level statistics from a signed 16-bit LE raw PCM file."""
    try:
        import numpy as np
    except ImportError:
        raise RuntimeError(
            "numpy is required for capture analysis. Install with: pip install numpy"
        )

    samples = np.fromfile(raw_path, dtype='<i2')   # signed 16-bit little-endian
    total = int(samples.size)
    if total == 0:
        raise RuntimeError(f"Slice is empty — {raw_path} has zero samples.")

    clipped_high = int(np.sum(samples == CLIP_HIGH_INT16))
    clipped_low = int(np.sum(samples == CLIP_LOW_INT16))
    clipped_total = clipped_high + clipped_low

    s_min = int(samples.min())
    s_max = int(samples.max())
    mean = float(samples.mean())
    rms = float(np.sqrt(np.mean(samples.astype('f8') ** 2)))

    # Recover original 10-bit values for display
    raw_min = (s_min // 64) + 512
    raw_max = (s_max // 64) + 512
    raw_mean = (mean / 64.0) + 512.0

    return {
        'samples': total,
        'duration_seconds': total / DDD_SAMPLE_RATE,
        'clipped_high': clipped_high,
        'clipped_low': clipped_low,
        'clipped_total': clipped_total,
        'clipped_pct': (clipped_total / total) * 100.0,
        'int16_min': s_min,
        'int16_max': s_max,
        'int16_mean': mean,
        'int16_rms': rms,
        'rms_normalised': rms / 32768.0,
        'raw_min': raw_min,
        'raw_max': raw_max,
        'raw_mean': raw_mean,
    }


def analyse_capture(input_path, skip_seconds=30, duration_seconds=60, output_path=None,
                    keep_slice=False):
    """
    Extract and analyse a slice of a .lds or .ldf RF capture.

    Returns a stats dict (see _compute_stats) augmented with 'raw_path' and 'input_path'.
    """
    if not os.path.isfile(input_path):
        raise FileNotFoundError(f"Capture file not found: {input_path}")

    ext = os.path.splitext(input_path)[1].lower()
    if ext not in ('.lds', '.ldf'):
        raise ValueError(f"Unsupported extension {ext}; expected .lds or .ldf")

    file_size = os.path.getsize(input_path)

    if ext == '.lds':
        skip_bytes = skip_seconds * LDS_BYTES_PER_SECOND
        need_bytes = duration_seconds * LDS_BYTES_PER_SECOND
        if skip_bytes + need_bytes > file_size:
            available = max(0, (file_size - skip_bytes)) // LDS_BYTES_PER_SECOND
            raise ValueError(
                f"Requested slice (skip {skip_seconds}s + {duration_seconds}s) extends past "
                f"end of file. Only ~{available}s available after skip."
            )

    if output_path is None:
        base = os.path.splitext(input_path)[0]
        output_path = f"{base}_slice_{skip_seconds}s_{duration_seconds}s.raw"

    if ext == '.lds':
        slice_path = output_path + '.lds.tmp'
        try:
            _slice_lds(input_path, skip_seconds, duration_seconds, slice_path)
            _unpack_lds_to_raw(slice_path, output_path)
        finally:
            if not keep_slice and os.path.exists(slice_path):
                os.remove(slice_path)
    else:  # .ldf
        _extract_ldf_to_raw(input_path, skip_seconds, duration_seconds, output_path)

    stats = _compute_stats(output_path)
    stats['raw_path'] = output_path
    stats['input_path'] = input_path
    stats['skip_seconds'] = skip_seconds
    stats['requested_duration_seconds'] = duration_seconds
    return stats


def print_report(stats):
    """Pretty-print the analysis result."""
    print()
    print("=" * 60)
    print("CAPTURE ANALYSIS RESULT")
    print("=" * 60)
    print(f"Source       : {stats['input_path']}")
    print(f"Slice offset : {stats['skip_seconds']} s")
    print(f"Slice length : {stats['duration_seconds']:.2f} s "
          f"({stats['samples']:,} samples)")
    print(f"Raw output   : {stats['raw_path']}")
    print(f"               ({_format_size(os.path.getsize(stats['raw_path']))})")
    print()
    print("--- LEVELS (10-bit ADC, 0..1023, centre 512) ---")
    print(f"min sample   : {stats['raw_min']}")
    print(f"max sample   : {stats['raw_max']}")
    print(f"mean sample  : {stats['raw_mean']:.1f}    (ideal centre: 512)")
    print(f"AC RMS       : {stats['rms_normalised']:.3f}    "
          f"(DdD-style 0..1 normalised; aim ~0.30-0.45)")
    print()
    print("--- CLIPPING ---")
    print(f"low rail  (raw=0)    : {stats['clipped_low']:,}")
    print(f"high rail (raw=1023) : {stats['clipped_high']:,}")
    print(f"total clipped        : {stats['clipped_total']:,} "
          f"({stats['clipped_pct']:.4f}%)")
    print()
    verdict = _verdict(stats)
    print(f"--- VERDICT: {verdict} ---")
    print()
    print("--- AUDACITY IMPORT ---")
    print("File -> Import -> Raw Data, then set:")
    print("  Encoding   : Signed 16-bit PCM")
    print("  Byte order : Little-endian")
    print("  Channels   : 1 (mono)")
    print("  Start      : 0 bytes")
    print("  Sample rate: 48000   (label only; actual rate is 40 MHz, but Audacity")
    print("                       won't play that — waveform shape is unaffected)")
    print()
    print("Spectrum analysis: Analyze -> Plot Spectrum (shows FM carrier + noise floor)")
    print("=" * 60)


def _verdict(stats):
    """Heuristic verdict combining clipping rate and AC RMS."""
    clip = stats['clipped_pct']
    rms = stats['rms_normalised']
    if clip > 0.5:
        return f"HEAVY CLIPPING ({clip:.2f}%) — reduce gain"
    if clip > 0.1:
        return f"MILD CLIPPING ({clip:.3f}%) — consider reducing gain"
    if rms < 0.20:
        return f"SIGNAL LOW (RMS {rms:.3f}) — consider raising gain"
    if rms > 0.55:
        return f"SIGNAL HOT (RMS {rms:.3f}) — likely clipping nearby, reduce gain"
    return f"OK (clipping {clip:.4f}%, RMS {rms:.3f})"


def interactive_analyse(default_dir=None):
    """Menu-driven entry point. Prompts for file, offset, duration; runs analysis."""
    print()
    print("CAPTURE ANALYSIS")
    print("=" * 40)
    print("Extracts a slice of a .lds/.ldf RF capture, unpacks to 16-bit PCM")
    print("for Audacity inspection, and reports clipping/level statistics.")
    print()

    # File prompt
    if default_dir and os.path.isdir(default_dir):
        captures = _list_captures(default_dir)
        if captures:
            print(f"Recent captures in {default_dir}:")
            for i, name in enumerate(captures[:10], 1):
                size = _format_size(os.path.getsize(os.path.join(default_dir, name)))
                print(f"  {i}. {name}  ({size})")
            print()
            sel = input("Select a number, or enter a full path: ").strip()
            if sel.isdigit() and 1 <= int(sel) <= len(captures[:10]):
                input_path = os.path.join(default_dir, captures[int(sel) - 1])
            else:
                input_path = os.path.expanduser(sel)
        else:
            input_path = os.path.expanduser(input("Path to .lds/.ldf file: ").strip())
    else:
        input_path = os.path.expanduser(input("Path to .lds/.ldf file: ").strip())

    if not input_path or not os.path.isfile(input_path):
        print(f"File not found: {input_path}")
        return

    # Offset / duration
    skip = _prompt_int("Skip seconds from start", default=30, minimum=0)
    duration = _prompt_int("Duration to extract (seconds)", default=60, minimum=1)

    # Size warning
    expected_raw_bytes = duration * RAW_BYTES_PER_SECOND
    print(f"\nWill produce ~{_format_size(expected_raw_bytes)} raw 16-bit output.")
    if expected_raw_bytes > 2 * 1024 ** 3:
        confirm = input("That's a large file. Continue? (y/N): ").strip().lower()
        if confirm not in ('y', 'yes'):
            print("Cancelled.")
            return

    print(f"\nSlicing {os.path.basename(input_path)} "
          f"(skip {skip}s, length {duration}s) and unpacking...")
    try:
        stats = analyse_capture(input_path, skip_seconds=skip, duration_seconds=duration)
    except (FileNotFoundError, ValueError, RuntimeError) as e:
        print(f"\nError: {e}")
        return
    except subprocess.CalledProcessError as e:
        print(f"\nExternal tool failed: {e}")
        return

    print_report(stats)


def _list_captures(directory):
    """Return capture files in the directory, newest first."""
    try:
        entries = []
        for name in os.listdir(directory):
            if name.lower().endswith(('.lds', '.ldf')):
                full = os.path.join(directory, name)
                if os.path.isfile(full):
                    entries.append((os.path.getmtime(full), name))
        entries.sort(reverse=True)
        return [name for _, name in entries]
    except OSError:
        return []


def _prompt_int(label, default, minimum=None, maximum=None):
    while True:
        raw = input(f"{label} [{default}]: ").strip()
        if not raw:
            return default
        try:
            value = int(raw)
        except ValueError:
            print("Please enter a whole number.")
            continue
        if minimum is not None and value < minimum:
            print(f"Must be >= {minimum}.")
            continue
        if maximum is not None and value > maximum:
            print(f"Must be <= {maximum}.")
            continue
        return value


def main():
    """CLI entry: capture_analysis.py <file> [skip_seconds] [duration_seconds]"""
    if len(sys.argv) < 2:
        print("Usage: capture_analysis.py <file.lds|file.ldf> [skip_seconds=30] [duration_seconds=60]")
        sys.exit(1)
    path = sys.argv[1]
    skip = int(sys.argv[2]) if len(sys.argv) > 2 else 30
    dur = int(sys.argv[3]) if len(sys.argv) > 3 else 60
    stats = analyse_capture(path, skip_seconds=skip, duration_seconds=dur)
    print_report(stats)


if __name__ == '__main__':
    main()
