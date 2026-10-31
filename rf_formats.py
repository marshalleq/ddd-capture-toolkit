#!/usr/bin/env python3
"""
RF capture file formats, in one place.

Two families of RF capture file exist side by side:

  .lds / .ldf       The original Domesday Duplicator formats. A .lds is packed
                    10-bit samples; a .ldf is the same data FLAC-compressed by
                    the COMPRESS step. Capture details are in <name>.json
                    (durationInMilliseconds, ...).

  .ddd.flac         What the current upstream capture application writes
  .ddd.s16          directly: native FLAC (or raw signed 16-bit). Already
                    compressed, so there is nothing for COMPRESS to do. Capture
                    details are in <name>.ddd.yaml, and in the file's own tags.

Everything that has to know "what is this project's RF file called, what is its
base name, where is its metadata, how long is it" goes through this module, so
the rest of the toolkit does not hard-code extensions.

The project base name never changes: Movie_Night_1985.ddd.flac and
Movie_Night_1985.lds are both project "Movie_Night_1985".
"""

import os
import re
import struct

# Longest first, so '.ddd.flac' is matched before '.flac' and '.s16' before nothing.
NATIVE_SUFFIXES = ('.ddd.flac', '.ddd.s16')
LEGACY_SUFFIXES = ('.lds', '.ldf')
RF_SUFFIXES = NATIVE_SUFFIXES + LEGACY_SUFFIXES

# Sample rate the current capture application records (its FLAC header carries
# the label 40000 and the real rate lives in the DDD_SAMPLE_RATE_HZ tag).
NATIVE_SAMPLE_RATE_HZ = 40_000_000


def rf_suffix(path):
    """Return the RF suffix the file name ends with ('.ddd.flac', '.lds', ...) or None."""
    lower = str(path).lower()
    for suffix in RF_SUFFIXES:
        if lower.endswith(suffix):
            return suffix
    return None


def is_rf_capture(path):
    """True if the path is one of the RF capture formats."""
    return rf_suffix(path) is not None


def is_native(path):
    """True for the current application's own formats (.ddd.flac / .ddd.s16)."""
    return rf_suffix(path) in NATIVE_SUFFIXES


def is_primary_capture(path):
    """True for a capture as recorded: .lds or a native .ddd.* (not the compressed .ldf)."""
    return rf_suffix(path) in ('.lds',) + NATIVE_SUFFIXES


def is_native_flac(path):
    return rf_suffix(path) == '.ddd.flac'


def rf_base_path(path):
    """Path with the RF suffix removed: /d/Foo.ddd.flac -> /d/Foo.

    A file that is not an RF capture falls back to os.path.splitext, which is
    what the toolkit did before native formats existed.
    """
    suffix = rf_suffix(path)
    if suffix:
        return str(path)[:-len(suffix)]
    return os.path.splitext(str(path))[0]


def rf_with_suffix(path, new_suffix):
    """Swap the RF suffix: rf_with_suffix('/d/Foo.ddd.flac', '.tbc') -> '/d/Foo.tbc'.

    A path that is not an RF capture gets the suffix appended, which is what the
    toolkit's old if/elif/else blocks did for unrecognised extensions.
    """
    if rf_suffix(path):
        return rf_base_path(path) + new_suffix
    return str(path) + new_suffix


def capture_metadata_path(rf_path):
    """Path of the capture-details file beside an RF capture (may not exist)."""
    if is_native(rf_path):
        return rf_base_path(rf_path) + '.ddd.yaml'
    return rf_base_path(rf_path) + '.json'


def capture_metadata_candidates(rf_path):
    """Metadata files that exist beside an RF capture, native or legacy."""
    base = rf_base_path(rf_path)
    return [p for p in (base + '.ddd.yaml', base + '.json') if os.path.isfile(p)]


# ---------------------------------------------------------------- duration

def _duration_from_yaml(yaml_path):
    """duration_seconds from a .ddd.yaml (read with a regex; no YAML library needed)."""
    try:
        with open(yaml_path, 'r', encoding='utf-8') as f:
            text = f.read()
    except OSError:
        return None
    match = re.search(r'"?duration_seconds"?\s*:\s*([0-9]+(?:\.[0-9]+)?)', text)
    if match:
        return float(match.group(1))
    samples = re.search(r'"?samples"?\s*:\s*([0-9]+)', text)
    rate = re.search(r'"?sample_rate_hz"?\s*:\s*([0-9]+)', text)
    if samples and rate and int(rate.group(1)) > 0:
        return int(samples.group(1)) / int(rate.group(1))
    return None


def _flac_streaminfo(path):
    """(sample_rate_label, total_samples) from a FLAC file's STREAMINFO, or None."""
    try:
        with open(path, 'rb') as f:
            head = f.read(42)
    except OSError:
        return None
    if len(head) < 42 or head[:4] != b'fLaC':
        return None
    # 4 bytes marker + 4 bytes block header, then STREAMINFO: sample rate is the
    # top 20 bits of bytes 10..13 of the block; total samples the low 36 bits of
    # bytes 13..17.
    block = head[8:42]
    packed = struct.unpack('>Q', block[10:18])[0]
    sample_rate = (packed >> 44) & 0xFFFFF
    total_samples = packed & 0xFFFFFFFFF
    return sample_rate, total_samples


def _duration_from_flac_header(path):
    """Duration of a native FLAC capture from its header (real rate assumed 40 MHz)."""
    info = _flac_streaminfo(path)
    if not info:
        return None
    _, total_samples = info
    if total_samples <= 0:
        return None
    return total_samples / NATIVE_SAMPLE_RATE_HZ


def _duration_from_legacy_json(json_path):
    import json
    try:
        with open(json_path, 'r') as f:
            data = json.load(f)
        return data['captureInfo']['durationInMilliseconds'] / 1000.0
    except (OSError, ValueError, KeyError, TypeError):
        return None


def capture_duration_seconds(rf_path):
    """
    How long the capture is, in seconds, or None if it cannot be established.

    .lds/.ldf: durationInMilliseconds from the capture .json (as before).
    .ddd.flac: duration_seconds from the .ddd.yaml; failing that the FLAC header
               (sample count at the real 40 MHz rate). This keeps frame-count
               based progress and ETAs working for native captures.
    """
    if is_native(rf_path):
        duration = _duration_from_yaml(rf_base_path(rf_path) + '.ddd.yaml')
        if duration:
            return duration
        if is_native_flac(rf_path):
            return _duration_from_flac_header(rf_path)
        return None
    return _duration_from_legacy_json(rf_base_path(rf_path) + '.json')
