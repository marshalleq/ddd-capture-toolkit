#!/usr/bin/env python3
"""Tests for convert_to_flac.py: .lds -> .ddd.flac keeps every sample, and refuses to overwrite."""

import hashlib
import os
import subprocess
import sys
import tempfile

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import convert_to_flac
import rf_formats


def pack(values):
    """10-bit values (multiple of 4) -> packed bytes, 4 samples in 5 bytes."""
    v = values.reshape(-1, 4).astype(np.uint16)
    a, b, c, d = v[:, 0], v[:, 1], v[:, 2], v[:, 3]
    out = np.empty((len(v), 5), dtype=np.uint8)
    out[:, 0] = a >> 2
    out[:, 1] = ((a & 3) << 6) | (b >> 4)
    out[:, 2] = ((b & 15) << 4) | (c >> 6)
    out[:, 3] = ((c & 63) << 2) | (d >> 8)
    out[:, 4] = d & 255
    return out.tobytes()


def test_unpack_matches_vhs_decode_arithmetic():
    values = np.arange(1024, dtype=np.uint16)
    unpacked = convert_to_flac.unpack_lds(np.frombuffer(pack(values), dtype=np.uint8))
    expected = np.left_shift(values.astype(np.int32) - 512, 6).astype('<i2')
    assert np.array_equal(unpacked, expected)


def test_lds_to_flac_round_trip():
    rng = np.random.default_rng(1)
    values = rng.integers(0, 1024, size=400_000, dtype=np.uint16)
    with tempfile.TemporaryDirectory() as tmp:
        lds = os.path.join(tmp, 'Cap.lds')
        with open(lds, 'wb') as f:
            f.write(pack(values))
        target = convert_to_flac.convert(lds, out=lambda *a, **k: None)
        assert target == os.path.join(tmp, 'Cap.ddd.flac')
        assert os.path.isfile(os.path.join(tmp, 'Cap.ddd.yaml'))
        assert not os.path.exists(target + '.part')
        back = subprocess.run(['ffmpeg', '-v', 'error', '-i', target, '-f', 's16le', '-'],
                              capture_output=True, check=True).stdout
        want = np.left_shift(values.astype(np.int32) - 512, 6).astype('<i2').tobytes()
        assert hashlib.sha256(back).digest() == hashlib.sha256(want).digest()
        # the native file reports its own length from the header tag
        assert abs(rf_formats.capture_duration_seconds(target) - 400_000 / 40e6) < 1e-9
        assert rf_formats.capture_sample_rate_hz(target) == 40_000_000
        # an existing result is never replaced without --overwrite
        try:
            convert_to_flac.convert(lds, out=lambda *a, **k: None)
        except RuntimeError as e:
            assert 'already exists' in str(e)
        else:
            raise AssertionError('overwrote an existing .ddd.flac')
        assert os.path.isfile(lds), 'the source must be left alone'


def test_rejects_other_formats():
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, 'Cap.raw')
        open(path, 'wb').write(b'x' * 10)
        try:
            convert_to_flac.convert(path, out=lambda *a, **k: None)
        except RuntimeError as e:
            assert 'not a .lds or .ldf' in str(e)
        else:
            raise AssertionError('converted an unsupported file')


def main():
    tests = [v for k, v in sorted(globals().items()) if k.startswith('test_')]
    for t in tests:
        t()
        print(f"PASS {t.__name__}")
    print(f"{len(tests)} conversion checks passed")


if __name__ == '__main__':
    main()
