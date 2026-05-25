#!/usr/bin/env python3
"""
Post-capture inline hashing with countdown and progress display.

After capture exits cleanly (sox + DomesdayDuplicator both confirmed exited and
files flushed), the capture flow can invoke ``prompt_and_hash_originals(...)``
to:

  1. Show a 5-second countdown with cancel-on-keypress.
  2. If not cancelled, hash the .lds, .flac, .json sequentially with a linear
     progress bar (one file at a time).
  3. Record the results to the project's ``_validation.log`` so later runs
     can detect TOUCHED/CHANGED vs VALIDATED via mtime+size comparison.
     Also writes a portable ``<file>.sha256`` sidecar next to each hashed
     file in standard ``sha256sum -c`` format.

This is the only inline hashing in the toolkit — every other hash flows
through the job queue. We do it inline here because (a) the user is sitting
at the terminal and wants confirmation that hashing actually started, (b) it
makes the cancel-window UX simple, and (c) capture is a foreground operation
anyway so the user isn't waiting for it to free the terminal.
"""

import os
import select
import sys
import time

try:
    import validation_log
except ImportError:
    validation_log = None


COUNTDOWN_SECONDS = 5
PROGRESS_BAR_WIDTH = 30


def _read_keypress_nonblocking(timeout_seconds):
    """Wait up to `timeout_seconds` for a keypress. Returns True if one
    arrived. Uses select on stdin so it works in the terminal without
    altering terminal modes."""
    try:
        readable, _, _ = select.select([sys.stdin], [], [], timeout_seconds)
        if readable:
            # Drain whatever the user typed
            sys.stdin.read(1)
            return True
    except (OSError, ValueError):
        pass
    return False


def _human_bytes(n):
    """Format bytes as a short human-readable string."""
    for unit, threshold in (('TB', 1024 ** 4), ('GB', 1024 ** 3), ('MB', 1024 ** 2), ('KB', 1024)):
        if n >= threshold:
            return f"{n / threshold:.1f} {unit}"
    return f"{n} B"


def _show_progress(label, bytes_done, bytes_total, start_time):
    """Render a one-line progress bar that updates in place via \\r."""
    if bytes_total == 0:
        return
    pct = bytes_done / bytes_total
    filled = int(pct * PROGRESS_BAR_WIDTH)
    bar = "█" * filled + "░" * (PROGRESS_BAR_WIDTH - filled)
    elapsed = time.time() - start_time
    rate = bytes_done / elapsed if elapsed > 0 else 0
    rate_str = f"{_human_bytes(int(rate))}/s" if rate > 0 else "—"
    eta = (bytes_total - bytes_done) / rate if rate > 0 else 0
    eta_str = f"ETA {int(eta)}s" if eta > 0 else ""
    line = (f"  {label:<8} |{bar}| {pct * 100:5.1f}%  "
            f"{_human_bytes(bytes_done):>9} / {_human_bytes(bytes_total):>9}  "
            f"{rate_str:>11}  {eta_str:>9}")
    sys.stdout.write("\r" + line)
    sys.stdout.flush()


def _countdown_with_cancel(seconds=COUNTDOWN_SECONDS):
    """Print a countdown and return True if user pressed a key to cancel.
    Uses 1-second ticks; aborts as soon as a key is detected."""
    print()
    for remaining in range(seconds, 0, -1):
        sys.stdout.write(
            f"\r\033[96mStarting hash compute in {remaining}…\033[0m "
            f"(press any key to cancel) "
        )
        sys.stdout.flush()
        if _read_keypress_nonblocking(1.0):
            print()
            print("\033[93mCancelled. Hash compute skipped.\033[0m")
            return True
    print()  # newline after countdown
    return False


def prompt_and_hash_originals(lds_path, flac_path, json_path,
                              countdown_seconds=COUNTDOWN_SECONDS,
                              algorithm='sha256'):
    """Top-level entry point for post-capture inline hashing.

    Args:
        lds_path, flac_path, json_path: full paths to the 3 capture files
        countdown_seconds: how long the cancel window stays open
        algorithm: hashlib name to use

    Returns:
        dict {role: file_info} if hashes were computed (possibly partial if
        cancelled mid-way), or None if cancelled before starting.

    The function also writes a ``_validation.log`` entry recording what was
    computed and whether the user cancelled.
    """
    if validation_log is None:
        print("\033[91mvalidation_log module not available — skipping hash\033[0m")
        return None

    # Sanity: make sure each target file exists. If a file is missing we don't
    # block the whole flow — just skip it and note in the log.
    targets = []
    for role, path in (('lds', lds_path), ('flac', flac_path), ('json', json_path)):
        if path and os.path.isfile(path):
            targets.append((role, path))
        elif path:
            print(f"  \033[93m{role:<4} missing: {path}\033[0m")
    if not targets:
        print("\033[91mNo capture files to hash.\033[0m")
        return None

    total_bytes = sum(os.path.getsize(p) for _, p in targets)
    print()
    print(f"\033[96mCapture complete — {len(targets)} file(s), "
          f"total {_human_bytes(total_bytes)} ready for hash.\033[0m")

    # Countdown with cancel
    if _countdown_with_cancel(countdown_seconds):
        try:
            validation_log.log_capture_hashes(
                lds_path or flac_path or json_path,
                file_hashes={},
                elapsed_seconds=0,
                cancelled=True,
            )
        except Exception:
            pass
        return None

    # Hash each file with progress
    print(f"\033[96mHashing {len(targets)} file(s) sequentially…\033[0m")
    print()
    results = {}
    overall_start = time.time()
    user_aborted = False

    for role, path in targets:
        if user_aborted:
            break
        size = os.path.getsize(path)
        if size == 0:
            results[role] = {'path': path, 'size': 0, 'mtime': '', 'hash': '(empty)', 'elapsed': 0}
            print(f"  {role:<4} skipped (zero bytes)")
            continue

        start = time.time()
        try:
            def progress_cb(done, total, _label=role, _start=start):
                _show_progress(f".{_label}", done, total, _start)

            digest, elapsed = validation_log.compute_file_hash(
                path, algorithm=algorithm, progress_callback=progress_cb,
            )
            _, mtime = validation_log.file_identity(path)
            results[role] = {
                'path': path, 'size': size, 'mtime': mtime,
                'hash': digest, 'elapsed': elapsed,
            }
            print()  # finish the progress line
        except KeyboardInterrupt:
            print()
            print("\033[93mInterrupted by user — partial hash recorded.\033[0m")
            user_aborted = True
        except OSError as e:
            print()
            print(f"  \033[91m{role} hash failed: {e}\033[0m")
            results[role] = {'path': path, 'size': size, 'mtime': '',
                             'hash': f'(error: {e})', 'elapsed': None}

    overall_elapsed = time.time() - overall_start

    # Write to validation log
    try:
        validation_log.log_capture_hashes(
            lds_path or flac_path or json_path,
            file_hashes=results,
            elapsed_seconds=overall_elapsed,
            cancelled=user_aborted,
        )
        log_path = validation_log.get_log_path(lds_path or flac_path or json_path)
        print()
        if user_aborted:
            print(f"\033[93mHash run cancelled. Partial results saved to:\033[0m {log_path}")
        else:
            print(f"\033[92m✓ Hashes recorded in:\033[0m {log_path}")
    except Exception as e:
        print(f"\033[91mCould not write validation log: {e}\033[0m")

    return results


if __name__ == '__main__':
    # Quick CLI test: python3 post_capture_hash.py <lds> <flac> <json>
    if len(sys.argv) != 4:
        print("Usage: post_capture_hash.py <lds_path> <flac_path> <json_path>")
        sys.exit(1)
    prompt_and_hash_originals(sys.argv[1], sys.argv[2], sys.argv[3])
