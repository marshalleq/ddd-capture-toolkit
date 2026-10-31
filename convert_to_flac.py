#!/usr/bin/env python3
"""
Convert old RF captures (.lds / .ldf) to the native FLAC format (.ddd.flac).

    python3 convert_to_flac.py CAPTURE.lds [MORE.ldf ...] [options]

The result is what the current capture application writes: a mono 16-bit FLAC whose
header carries the label 40000 and, in the DDD_SAMPLE_RATE_HZ tag, the real 40 MHz
rate, with a <name>.ddd.yaml beside it. The toolkit and tape-decode read it directly.

  .lds   packed 10-bit samples, unpacked here
  .ldf   FLAC-compressed .lds, read through ld-ldf-reader

Each conversion is checked: a hash of the samples as they were read is compared with a hash
of the samples decoded back out of the new file, and the file is only kept (renamed from
.part) if they match. The source file is never changed or deleted.
"""

import argparse
import hashlib
import os
import shutil
import subprocess
import sys
import threading
import time

import numpy as np

import rf_formats

SAMPLE_RATE_HZ = 40_000_000       # the Domesday Duplicator records at 40 MHz
CHUNK_GROUPS = 1_000_000          # 5-byte groups (4 samples) read at a time for .lds
FLAC_LABEL_RATE = 40000           # FLAC headers cannot hold 40 MHz; the real rate is in a tag


def unpack_lds(packed):
    """Packed 10-bit bytes (a multiple of 5 long) -> int16 samples, the same arithmetic
    vhs-decode uses: (value - 512) << 6."""
    p = packed.reshape(-1, 5).astype(np.uint16)
    out = np.empty((len(p), 4), dtype=np.uint16)
    out[:, 0] = (p[:, 0] << 2) | ((p[:, 1] >> 6) & 3)
    out[:, 1] = ((p[:, 1] & 0x3F) << 4) | ((p[:, 2] >> 4) & 0x0F)
    out[:, 2] = ((p[:, 2] & 0x0F) << 6) | ((p[:, 3] >> 2) & 0x3F)
    out[:, 3] = ((p[:, 3] & 3) << 8) | p[:, 4]
    return np.left_shift(out.astype(np.int32) - 512, 6).astype('<i2').reshape(-1)


def sample_chunks(path, progress):
    """Yield the capture's samples as little-endian int16 bytes."""
    suffix = rf_formats.rf_suffix(path)
    if suffix == '.lds':
        size = os.path.getsize(path)
        done = 0
        with open(path, 'rb') as f:
            while True:
                data = f.read(CHUNK_GROUPS * 5)
                if not data:
                    break
                usable = len(data) // 5 * 5
                if usable:
                    yield unpack_lds(np.frombuffer(data[:usable], dtype=np.uint8)).tobytes()
                done += len(data)
                progress(done / size)
        return
    if suffix == '.ldf':
        import tool_health
        reader = shutil.which('ld-ldf-reader')
        if not reader:
            raise RuntimeError("ld-ldf-reader not found; run ./setup.sh")
        problem = tool_health.reader_problem()
        if problem:
            raise RuntimeError(problem)
        proc = subprocess.Popen(tool_health.ldf_reader_argv(reader, path),
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        size = max(os.path.getsize(path), 1)
        # no frame position is reported, so progress is estimated from the output size
        # against an assumed 8:3 compression of 16-bit samples
        expected = size * 2.7
        done = 0
        while True:
            data = proc.stdout.read(1 << 22)
            if not data:
                break
            done += len(data)
            progress(min(done / expected, 0.99))
            yield data
        if proc.wait() != 0:
            raise RuntimeError("ld-ldf-reader failed: " + proc.stderr.read().decode(errors='replace')[-300:])
        return
    raise RuntimeError(f"{os.path.basename(path)} is not a .lds or .ldf capture")


def decode_hash(ffmpeg, flac_path):
    """sha256 and byte count of the samples decoded back out of a FLAC file."""
    proc = subprocess.Popen([ffmpeg, '-v', 'error', '-i', flac_path, '-f', 's16le', '-'],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    digest, count = hashlib.sha256(), 0
    while True:
        data = proc.stdout.read(1 << 22)
        if not data:
            break
        digest.update(data)
        count += len(data)
    if proc.wait() != 0:
        raise RuntimeError("could not decode the new file back: " + proc.stderr.read().decode(errors='replace')[-300:])
    return digest.hexdigest(), count


def write_yaml(path, flac_name, source, samples, flac_bytes):
    duration = samples / SAMPLE_RATE_HZ
    lines = [
        '# Domesday Duplicator capture metadata, written by convert_to_flac.py.',
        '#',
        '# This file describes the capture of the same name beside it. The capture was',
        '# converted from an older recording, so only what the conversion knows is here.',
        '',
        '"schema_version": 1',
        '',
        '"capture":',
        f'  "file": "{flac_name}"',
        '  "format": "FLAC"',
        f'  "sample_rate_hz": {SAMPLE_RATE_HZ}',
        f'  "duration_seconds": {duration:.3f}',
        f'  "samples": {samples}',
        f'  "bytes": {flac_bytes}',
        '',
        '"converted":',
        f'  "from": "{os.path.basename(source)}"',
        f'  "on": "{time.strftime("%Y-%m-%dT%H:%M:%S%z")}"',
        '',
    ]
    with open(path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))


def convert(source, output_dir=None, level=8, verify=True, overwrite=False, out=print):
    ffmpeg = shutil.which('ffmpeg')
    if not ffmpeg:
        raise RuntimeError("ffmpeg not found; run ./setup.sh")
    base = os.path.basename(rf_formats.rf_base_path(source))
    directory = output_dir or os.path.dirname(os.path.abspath(source))
    os.makedirs(directory, exist_ok=True)
    target = os.path.join(directory, base + '.ddd.flac')
    partial = target + '.part'
    if os.path.abspath(target) == os.path.abspath(source):
        raise RuntimeError("the input is already a .ddd.flac")
    if os.path.exists(target) and not overwrite:
        raise RuntimeError(f"{target} already exists (use --overwrite to replace it)")

    started = time.time()
    last_print = [0.0]

    def progress(fraction):
        if time.time() - last_print[0] > 2:
            last_print[0] = time.time()
            out(f"  {fraction * 100:5.1f}%  {time.time() - started:6.0f}s", end='\r', flush=True)

    cmd = [ffmpeg, '-v', 'error', '-y', '-f', 's16le', '-ar', str(FLAC_LABEL_RATE), '-ac', '1', '-i', '-',
           '-c:a', 'flac', '-compression_level', str(level),
           '-metadata', f'TITLE={base}.ddd.flac',
           '-metadata', f'DDD_SAMPLE_RATE_HZ={SAMPLE_RATE_HZ}',
           '-metadata', f'CONVERTED_FROM={os.path.basename(source)}',
           '-f', 'flac', partial]
    encoder = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    errors = []
    threading.Thread(target=lambda: errors.append(encoder.stderr.read()), daemon=True).start()
    digest, total = hashlib.sha256(), 0
    try:
        for chunk in sample_chunks(source, progress):
            digest.update(chunk)
            total += len(chunk)
            encoder.stdin.write(chunk)
        encoder.stdin.close()
        if encoder.wait() != 0:
            raise RuntimeError("ffmpeg failed: " + b''.join(errors).decode(errors='replace')[-300:])
        if total == 0:
            raise RuntimeError("the capture contains no samples")
        samples = total // 2
        if verify:
            out("  verifying the new file...                    ")
            back_hash, back_bytes = decode_hash(ffmpeg, partial)
            if back_bytes != total or back_hash != digest.hexdigest():
                raise RuntimeError(f"verification failed: the new file does not decode to the same samples "
                                   f"({back_bytes} bytes back, {total} read)")
        os.replace(partial, target)
    except BaseException:
        if encoder.poll() is None:
            encoder.kill()
        if os.path.exists(partial):
            os.remove(partial)
        raise
    write_yaml(os.path.join(directory, base + '.ddd.yaml'), base + '.ddd.flac', source, samples,
               os.path.getsize(target))
    out(f"  done: {target}")
    out(f"        {samples} samples, {samples / SAMPLE_RATE_HZ:.2f} s, {os.path.getsize(target) / 1e6:.0f} MB"
        + (", verified" if verify else ", NOT verified"))
    return target


def main(argv=None):
    parser = argparse.ArgumentParser(description="Convert .lds / .ldf RF captures to .ddd.flac")
    parser.add_argument('inputs', nargs='+', help="capture files (.lds or .ldf)")
    parser.add_argument('-o', '--output-dir', help="where to write (default: beside each input)")
    parser.add_argument('--level', type=int, default=8, choices=range(0, 13),
                        help="FLAC compression level 0-12 (default 8)")
    parser.add_argument('--no-verify', action='store_true',
                        help="skip decoding the new file back to compare samples (faster, not recommended)")
    parser.add_argument('--overwrite', action='store_true', help="replace an existing .ddd.flac")
    args = parser.parse_args(argv)

    failed = 0
    for source in args.inputs:
        print(f"{source}")
        try:
            convert(source, args.output_dir, args.level, not args.no_verify, args.overwrite)
        except (RuntimeError, OSError) as e:
            print(f"  FAILED: {e}")
            failed += 1
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
