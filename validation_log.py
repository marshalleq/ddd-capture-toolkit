#!/usr/bin/env python3
"""
Validation log writer for the lds-compress pipeline.

Writes a human-readable history of every validation pass alongside the capture
files. Used by all three compress-validation tiers:

  Tier 1 (always-on structural seek check)  → one-line entry per run
  Tier 2 (FLAC integrity test, default on)  → entry with optional .ldf hash
  Tier 3 (manual 1mv full validation)       → full entry with checksums of
                                              the 3 capture originals (.lds,
                                              .flac, .json) plus the .ldf

The log file lives next to the captures as ``<basename>_validation.log`` and
is **append-only** so the user gets a complete history of every validation
event for this capture. A future "delete the .lds" decision can be made by
reading the log and confirming the last Tier 3 entry was a PASS.
"""

import hashlib
import os
import time
from datetime import datetime


# ----- Hashing ------------------------------------------------------------

def compute_file_hash(path, algorithm='sha256', chunk_size=64 * 1024 * 1024,
                      progress_callback=None):
    """Compute the hash of a file.

    Reads in large chunks for throughput. Returns (hex_digest, elapsed_seconds).
    Raises OSError if the file can't be read.

    progress_callback: optional callable(bytes_read, total_bytes) invoked
    after each chunk — used by the post-capture progress bar.
    """
    h = hashlib.new(algorithm)
    start = time.time()
    total = os.path.getsize(path)
    read_so_far = 0
    with open(path, 'rb') as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            h.update(chunk)
            read_so_far += len(chunk)
            if progress_callback:
                progress_callback(read_so_far, total)
    return h.hexdigest(), time.time() - start


def file_identity(path):
    """Return (size, mtime_iso) for a file — used to detect later changes
    cheaply without re-hashing. mtime is rounded to whole seconds since
    sub-second precision varies across filesystems."""
    st = os.stat(path)
    return st.st_size, datetime.fromtimestamp(int(st.st_mtime)).isoformat(timespec='seconds')


def find_capture_originals(base_path):
    """Find the originals for a project, given any related file path.

    Returns a dict mapping {'lds': path, 'ldf': path, 'flac': path, 'json': path}
    with only the entries whose files actually exist on disk.
    """
    base, _ = os.path.splitext(base_path)
    while True:
        for suffix in ('.tbc', '_aligned', '_ffv1', '_final', '_chroma'):
            if base.endswith(suffix):
                base = base[:-len(suffix)]
                break
        else:
            break
    candidates = {
        'lds': base + '.lds',
        'ldf': base + '.ldf',
        'flac': base + '.flac',
        'json': base + '.json',
    }
    return {role: path for role, path in candidates.items() if os.path.isfile(path)}


# ----- Log path & header --------------------------------------------------

def get_log_path(any_capture_file_path):
    """Return the validation log path for a project. Pass any related file
    (.lds, .ldf, .flac, .json, _aligned.flac, _ffv1.mkv, _final.mkv, .tbc, .tbc.json)
    and the log path is derived from the project's base name."""
    base, _ = os.path.splitext(any_capture_file_path)
    # Strip composite extensions / known downstream suffixes so the log path is
    # always anchored to the project's base name (no duplicate logs per output).
    while True:
        for suffix in ('.tbc', '_aligned', '_ffv1', '_final', '_chroma'):
            if base.endswith(suffix):
                base = base[:-len(suffix)]
                break
        else:
            break
    return base + '_validation.log'


def _append(log_path, text):
    """Append `text` to the log file. Creates a header on first write."""
    first_write = not os.path.exists(log_path) or os.path.getsize(log_path) == 0
    with open(log_path, 'a') as f:
        if first_write:
            f.write("VHS Capture Validation Log\n")
            f.write("=" * 70 + "\n")
            f.write(f"Project basename: {os.path.basename(log_path).replace('_validation.log', '')}\n")
            f.write(f"Created:          {datetime.now().isoformat(timespec='seconds')}\n")
            f.write("\n")
            f.write("Each entry below records one validation pass. Tier 3 entries\n")
            f.write("include SHA-256 checksums of the capture originals — use these to\n")
            f.write("confirm files have not changed between runs.\n")
            f.write("\n")
            f.write("─" * 70 + "\n")
        f.write(text)
        if not text.endswith("\n"):
            f.write("\n")
        f.write("─" * 70 + "\n")


# ----- Entry formatters ---------------------------------------------------

def _ts():
    return datetime.now().isoformat(timespec='seconds')


def log_hash(any_capture_file_path, file_hashes, step='hash',
             missing_files=None, elapsed_seconds=None):
    """Generic hash-recording log entry. Used by the checksum job for any
    workflow step (compress, align, export, final-mux) and for retrospective
    hashing of existing files. The `step` label tells the user (and any later
    workflow analyzer) which step's outputs were hashed.

    file_hashes: {role: {'path', 'size', 'mtime', 'hash', 'elapsed'}}.
    missing_files: list of paths requested but not present on disk.
    """
    log_path = get_log_path(any_capture_file_path)
    lines = [
        f"[{_ts()}] {step.title()}: hash recorded  →  DONE",
    ]
    if elapsed_seconds is not None:
        lines.append(f"  total elapsed:  {elapsed_seconds:.0f}s")
    if missing_files:
        for p in missing_files:
            lines.append(f"  missing (skipped): {p}")
    if file_hashes:
        lines.append("")
        lines.append("  File identity + checksums (SHA-256):")
        for role, info in file_hashes.items():
            size = info.get('size', 0)
            mtime = info.get('mtime', '')
            h = info.get('hash', '(skipped)')
            path = info.get('path', '')
            elapsed = info.get('elapsed')
            elapsed_str = f"  ({elapsed:.0f}s)" if elapsed is not None else ""
            lines.append(f"    .{role:<8} {size:>18,} bytes  mtime {mtime}  {h}{elapsed_str}")
            if path:
                lines.append(f"          {path}")
    _append(log_path, "\n".join(lines) + "\n")


def log_verify(any_capture_file_path, new_hashes, missing_files=None,
               elapsed_seconds=None):
    """Verify-mode entry: compare freshly-computed hashes to the most-recent
    recorded hashes in the log, record PASS/FAIL per file.

    new_hashes: {role: file_info} from a fresh re-hash.

    The comparison reads back our own log (which is a small text file) to
    find the most recent hash for each role.
    """
    log_path = get_log_path(any_capture_file_path)
    expected = _parse_latest_hashes(log_path)

    all_pass = True
    detail_lines = []
    for role, info in new_hashes.items():
        new_hash = info.get('hash', '')
        exp = expected.get(role)
        if exp is None:
            detail_lines.append(f"    .{role:<8} NO PRIOR HASH (recording new)  {new_hash}")
            all_pass = False
            continue
        if exp['hash'] == new_hash:
            detail_lines.append(f"    .{role:<8} MATCH    {new_hash}")
        else:
            all_pass = False
            detail_lines.append(
                f"    .{role:<8} MISMATCH  expected {exp['hash']}  got {new_hash}"
            )

    verdict = "PASS — all hashes match prior record" if all_pass else "FAIL — hash mismatch(es) found"
    lines = [
        f"[{_ts()}] Verify: re-hash + compare to log  →  {verdict}",
    ]
    if elapsed_seconds is not None:
        lines.append(f"  total elapsed:  {elapsed_seconds:.0f}s")
    if missing_files:
        for p in missing_files:
            lines.append(f"  missing: {p}")
    lines.append("")
    lines.extend(detail_lines)
    _append(log_path, "\n".join(lines) + "\n")


def _parse_latest_hashes(log_path):
    """Scan the validation log and return the most-recent recorded hash for
    each role: {role: {'hash', 'size', 'mtime'}}. Best-effort parsing — the
    log format is intended for humans, but the hash lines have a stable shape
    that we can recognise.

    Returns empty dict if the log doesn't exist or has no parseable entries.
    """
    if not os.path.isfile(log_path):
        return {}
    latest = {}
    try:
        with open(log_path) as f:
            for line in f:
                # Match lines like: "    .lds     <SIZE> bytes  mtime <ISO>  <HASH>"
                stripped = line.strip()
                if not stripped.startswith('.'):
                    continue
                parts = stripped.split()
                # Expect: .role  N,N,N bytes  mtime ISO hash
                if len(parts) < 6 or parts[2] != 'bytes' or parts[3] != 'mtime':
                    continue
                role = parts[0][1:].rstrip(':').strip()  # strip leading '.'
                if not role:
                    continue
                try:
                    size = int(parts[1].replace(',', '').replace('_', ''))
                except ValueError:
                    continue
                mtime = parts[4]
                # Hash is parts[5]; ignore trailing "(Xs)" if present
                hash_val = parts[5]
                # Heuristic: hex digest is 64 chars for SHA-256
                if not (len(hash_val) == 64 and all(c in '0123456789abcdefABCDEF' for c in hash_val)):
                    continue
                latest[role] = {'hash': hash_val, 'size': size, 'mtime': mtime}
    except OSError:
        return {}
    return latest


def file_state(path, log_path=None):
    """Cheap status check for a file: returns one of
    {'missing', 'no-hash', 'validated', 'stale'} based on log entries and
    the current filesystem state. Never re-hashes — that's what verify is for.

    'missing'   — file doesn't exist
    'no-hash'   — file exists, no hash recorded yet
    'validated' — hash recorded, file's size+mtime still match what was recorded
    'stale'     — hash recorded, but size or mtime differs from the recorded value
    """
    if not os.path.isfile(path):
        return 'missing'
    if log_path is None:
        log_path = get_log_path(path)
    latest = _parse_latest_hashes(log_path)

    ext = os.path.splitext(path)[1].lower().lstrip('.')
    if ext == 'mkv' and '_final' in path:
        role = 'final'
    elif ext == 'mkv' and '_ffv1' in path:
        role = 'ffv1'
    elif ext == 'flac' and '_aligned' in path:
        role = 'aligned'
    else:
        role = ext

    rec = latest.get(role)
    if rec is None:
        return 'no-hash'
    current_size, current_mtime = file_identity(path)
    if current_size != rec['size'] or current_mtime != rec['mtime']:
        return 'stale'
    return 'validated'


def log_capture_hashes(any_capture_file_path, file_hashes, elapsed_seconds=None,
                       cancelled=False):
    """Record the post-capture hashes of the 3 originals (.lds, .flac, .json).

    These files have no validation oracle — they ARE the source of truth — so
    we just record their checksums + identity (size, mtime) at the moment of
    capture. Later runs use the recorded identity to cheaply detect whether
    the file has been modified (STALE state in the WCC).

    file_hashes: dict {role: {'path', 'size', 'mtime', 'hash', 'elapsed'}}.
    cancelled: if True, the user cancelled the hash mid-way; record what was
    computed so far and note the cancellation.
    """
    log_path = get_log_path(any_capture_file_path)
    verdict = "CANCELLED" if cancelled else "DONE"
    lines = [
        f"[{_ts()}] Capture: post-capture hash of originals  →  {verdict}",
    ]
    if elapsed_seconds is not None:
        lines.append(f"  total elapsed:  {elapsed_seconds:.0f}s")

    if file_hashes:
        lines.append("")
        lines.append("  File identity + checksums (SHA-256):")
        for role, info in file_hashes.items():
            size = info.get('size', 0)
            mtime = info.get('mtime', '')
            h = info.get('hash', '(skipped)')
            path = info.get('path', '')
            elapsed = info.get('elapsed')
            elapsed_str = f"  ({elapsed:.0f}s)" if elapsed is not None else ""
            lines.append(f"    .{role:<4} {size:>18,} bytes  mtime {mtime}  {h}{elapsed_str}")
            if path:
                lines.append(f"          {path}")
    _append(log_path, "\n".join(lines) + "\n")


def log_tier1(any_capture_file_path, passed, message, lds_path=None, ldf_path=None):
    """Log a Tier 1 (structural seek) result. Cheap and runs every compress."""
    log_path = get_log_path(any_capture_file_path)
    verdict = "PASS" if passed else "FAIL"
    entry = (
        f"[{_ts()}] Tier 1: structural seek check  →  {verdict}\n"
        f"  {message}\n"
    )
    if lds_path:
        entry += f"  source .lds:  {lds_path}\n"
    if ldf_path:
        entry += f"  output .ldf:  {ldf_path}\n"
    _append(log_path, entry)


def log_tier2(any_capture_file_path, passed, message, ldf_path=None,
              ldf_hash=None, elapsed_seconds=None):
    """Log a Tier 2 (FLAC integrity) result. The .ldf hash is optional but
    recommended — it's free to compute during the decode pass."""
    log_path = get_log_path(any_capture_file_path)
    verdict = "PASS" if passed else "FAIL"
    lines = [f"[{_ts()}] Tier 2: FLAC integrity test  →  {verdict}",
             f"  {message}"]
    if elapsed_seconds is not None:
        lines.append(f"  elapsed:      {elapsed_seconds:.0f}s")
    if ldf_path:
        lines.append(f"  .ldf:         {ldf_path}")
    if ldf_hash:
        lines.append(f"  .ldf SHA-256: {ldf_hash}")
    _append(log_path, "\n".join(lines) + "\n")


def log_tier3(any_capture_file_path, passed, message, file_hashes=None,
              elapsed_seconds=None):
    """Log a Tier 3 (full validation) result with checksums of all originals.

    file_hashes: dict {role: {'path', 'size', 'hash', 'elapsed'}} for each of
    the capture originals (.lds/.ldf/.flac/.json). Pass None or empty dict to
    skip the checksum section.
    """
    log_path = get_log_path(any_capture_file_path)
    verdict = "PASS" if passed else "FAIL"
    lines = [
        f"[{_ts()}] Tier 3: full sample-count validation  →  {verdict}",
        f"  {message}",
    ]
    if elapsed_seconds is not None:
        lines.append(f"  total elapsed:    {elapsed_seconds:.0f}s")

    if file_hashes:
        lines.append("")
        lines.append("  File checksums (SHA-256) — record of capture integrity at this point in time:")
        for role, info in file_hashes.items():
            size = info.get('size', 0)
            h = info.get('hash', '(skipped)')
            path = info.get('path', '')
            elapsed = info.get('elapsed')
            elapsed_str = f"  ({elapsed:.0f}s)" if elapsed is not None else ""
            lines.append(f"    .{role:<4} {size:>18,} bytes  {h}{elapsed_str}")
            if path:
                lines.append(f"          {path}")
    _append(log_path, "\n".join(lines) + "\n")


# ----- Convenience: compute all hashes for a project ----------------------

def hash_capture_originals(any_capture_file_path, skip_lds_hash=False,
                          progress_callback=None):
    """Compute SHA-256 of the 3 capture originals (lds, flac, json) plus the
    .ldf if it exists.

    Returns dict {role: {'path', 'size', 'hash', 'elapsed'}}.

    skip_lds_hash: if True, skip hashing the .lds (which can take minutes for
    a long capture). Useful when the .lds is so large that hashing it would
    dominate the validation time and the user just wants the smaller files.

    progress_callback: optional callable(role: str, status: str) for UI updates
    during long hash operations.
    """
    originals = find_capture_originals(any_capture_file_path)
    result = {}
    for role, path in originals.items():
        if role == 'lds' and skip_lds_hash:
            result[role] = {'path': path, 'size': os.path.getsize(path),
                            'hash': '(skipped — pass skip_lds_hash=False to compute)',
                            'elapsed': None}
            continue
        if progress_callback:
            progress_callback(role, f"hashing .{role}…")
        try:
            digest, elapsed = compute_file_hash(path)
            result[role] = {'path': path, 'size': os.path.getsize(path),
                            'hash': digest, 'elapsed': elapsed}
        except OSError as e:
            result[role] = {'path': path, 'size': 0,
                            'hash': f'(error: {e})', 'elapsed': None}
    return result
