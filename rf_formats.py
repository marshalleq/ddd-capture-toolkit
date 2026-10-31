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


def _read_flac_header(path, limit=262144):
    """The metadata blocks of a FLAC file: ({'streaminfo': (rate_label, total_samples), 'tags': {...}})
    or None if it is not a FLAC file. Reads only the start of the file."""
    try:
        with open(path, 'rb') as f:
            data = f.read(limit)
    except OSError:
        return None
    if len(data) < 8 or data[:4] != b'fLaC':
        return None
    result = {'streaminfo': None, 'tags': {}}
    pos = 4
    while pos + 4 <= len(data):
        is_last = bool(data[pos] & 0x80)
        block_type = data[pos] & 0x7F
        length = int.from_bytes(data[pos + 1:pos + 4], 'big')
        body = data[pos + 4:pos + 4 + length]
        pos += 4 + length
        if len(body) < length:
            break
        if block_type == 0 and length >= 34:
            # sample rate = top 20 bits, total samples = low 36 bits of bytes 10..17
            packed = struct.unpack('>Q', body[10:18])[0]
            result['streaminfo'] = ((packed >> 44) & 0xFFFFF, packed & 0xFFFFFFFFF)
        elif block_type == 4:
            try:
                vendor_len = struct.unpack('<I', body[:4])[0]
                off = 4 + vendor_len
                count = struct.unpack('<I', body[off:off + 4])[0]
                off += 4
                for _ in range(count):
                    clen = struct.unpack('<I', body[off:off + 4])[0]
                    comment = body[off + 4:off + 4 + clen].decode('utf-8', errors='replace')
                    off += 4 + clen
                    if '=' in comment:
                        key, value = comment.split('=', 1)
                        result['tags'][key.upper()] = value
            except (struct.error, IndexError):
                pass
        if is_last:
            break
    return result


def _duration_from_flac(path):
    """
    Duration of a FLAC capture from the file's own header and tags.

    The FLAC sample-rate field cannot hold 40 MHz, so captures carry a label
    (40000) and the real rate in a tag. This reads, in order of preference:
      - a duration/total-and-rate pair written by the capture program
        (DURATION_SECONDS, or RF_TOTAL_SAMPLES with RF_SAMPLE_RATE);
      - the header's sample count over the real rate (DDD_SAMPLE_RATE_HZ tag, or
        the label x 1000 if the tag is absent).
    Returns None if the file does not say.
    """
    header = _read_flac_header(path)
    if not header:
        return None
    tags = header['tags']
    try:
        if tags.get('DURATION_SECONDS'):
            return float(tags['DURATION_SECONDS'])
        if tags.get('RF_TOTAL_SAMPLES') and tags.get('RF_SAMPLE_RATE'):
            return int(tags['RF_TOTAL_SAMPLES']) / int(tags['RF_SAMPLE_RATE'])
        info = header['streaminfo']
        if not info or info[1] <= 0:
            return None
        label, total_samples = info
        if tags.get('DDD_SAMPLE_RATE_HZ'):
            real_rate = int(tags['DDD_SAMPLE_RATE_HZ'])
        else:
            real_rate = label * 1000
        return total_samples / real_rate if real_rate > 0 else None
    except (ValueError, ZeroDivisionError):
        return None


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
    .ddd.flac: the file's own FLAC header and tags first (they travel with the
               file and cannot be separated from it), then the <name>.ddd.yaml
               beside it. This keeps frame-count based progress and ETAs working
               for native captures.
    .ddd.s16:  no header, so the .ddd.yaml only.
    """
    if is_native(rf_path):
        if is_native_flac(rf_path):
            duration = _duration_from_flac(rf_path)
            if duration:
                return duration
        return _duration_from_yaml(rf_base_path(rf_path) + '.ddd.yaml')
    return _duration_from_legacy_json(rf_base_path(rf_path) + '.json')
