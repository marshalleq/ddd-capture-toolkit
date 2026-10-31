#!/usr/bin/env python3
"""
Health of the ld-* helper programs the decode and export stages depend on.

Two things have gone wrong in practice and neither was visible:

  - An unmanaged copy of a tool (for example one installed into /usr/bin years
    ago) sits ahead of the one the toolkit builds into its own environment.
  - That copy can no longer start. ld-ldf-reader, linked against one generation
    of FFmpeg libraries, stops loading when the operating system moves to the
    next. vhs-decode then does not fail: it reports "completed without handling
    any frames" and leaves an empty .tbc.

This module finds the tool the toolkit would actually run, says whether it
belongs to the environment, and whether it can start. check_dependencies.py
prints it; the decode job uses it to refuse to start when the reader is broken.
"""

import os
import shutil
import subprocess
import sys

# The helpers the toolkit runs. ld-ldf-reader reads .ldf and .flac captures
# (including native .ddd.flac); the others build and process the exported video.
LD_TOOLS = (
    'ld-ldf-reader',
    'ld-chroma-decoder',
    'ld-dropout-correct',
    'ld-process-vbi',
    'ld-lds-converter',
)

# What the dynamic loader says when a program cannot start for lack of a library.
_LOAD_ERRORS = (
    'error while loading shared libraries',
    'cannot open shared object file',
    'Library not loaded',
    'dyld:',
)


def env_prefix():
    """The directory of the active environment (conda prefix, or the Python prefix)."""
    return os.environ.get('CONDA_PREFIX') or sys.prefix


def _path_hits(name):
    """Every executable called `name` on PATH, in the order the shell would find them."""
    hits = []
    for folder in os.environ.get('PATH', '').split(os.pathsep):
        candidate = os.path.join(folder, name)
        if folder and os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            if candidate not in hits:
                hits.append(candidate)
    return hits


def _is_inside(path, prefix):
    try:
        return os.path.commonpath([os.path.realpath(path), os.path.realpath(prefix)]) == os.path.realpath(prefix)
    except ValueError:
        return False


def _startup_problem(path):
    """Return a one-line reason if the program cannot start, else None."""
    try:
        proc = subprocess.run([path, '--help'], capture_output=True, text=True, timeout=10,
                              stdin=subprocess.DEVNULL)
    except subprocess.TimeoutExpired:
        return None        # it started and is waiting: it can run
    except OSError as e:
        return f"cannot be run: {e}"
    text = (proc.stderr or '') + (proc.stdout or '')
    for marker in _LOAD_ERRORS:
        if marker in text:
            first = next((line.strip() for line in text.splitlines() if marker in line), marker)
            return first
    return None


def check_tool(name, prefix=None):
    """
    Report on one tool: {'name', 'path', 'managed', 'problem', 'shadows', 'notes'}.

    path     the copy that would run (first on PATH), or None if not found
    managed  True if it lives inside the environment the toolkit built
    problem  why it cannot start, or None
    shadows  a managed copy that exists but is hidden behind `path`, or None
    """
    prefix = prefix or env_prefix()
    hits = _path_hits(name)
    report = {'name': name, 'path': None, 'managed': False, 'problem': None, 'shadows': None, 'notes': []}
    if not hits:
        return report
    report['path'] = hits[0]
    report['managed'] = _is_inside(hits[0], prefix)
    report['problem'] = _startup_problem(hits[0])
    if not report['managed']:
        managed_copy = next((h for h in hits[1:] if _is_inside(h, prefix)), None)
        report['shadows'] = managed_copy
        if not managed_copy:
            inside = os.path.join(prefix, 'bin', name)
            if os.path.isfile(inside):
                report['shadows'] = inside
    return report


def check_ld_tools(prefix=None):
    """Reports for every tool in LD_TOOLS."""
    return [check_tool(name, prefix) for name in LD_TOOLS]


def reader_problem(prefix=None):
    """
    Why ld-ldf-reader cannot be used, or None if it is fine or absent.

    Used before a decode of a .ldf / .flac capture: a reader that cannot start
    makes vhs-decode finish with no frames and no error.
    """
    report = check_tool('ld-ldf-reader', prefix)
    if report['path'] and report['problem']:
        return (f"ld-ldf-reader at {report['path']} cannot start ({report['problem']}). "
                f"Run check_dependencies.py, then rebuild the environment (setup.sh) "
                f"or remove the stale copy.")
    return None


def format_report(report):
    """Lines for a console report. Returns (lines, severity) with severity 'ok' | 'warn' | 'fail'."""
    name = report['name']
    if not report['path']:
        return [f"    {name} - not found"], 'warn'
    lines = []
    severity = 'ok'
    where = 'in the environment' if report['managed'] else 'OUTSIDE the environment'
    if report['problem']:
        severity = 'fail'
        lines.append(f"    {name} - CANNOT START ({where}): {report['path']}")
        lines.append(f"      {report['problem']}")
    elif report['managed']:
        lines.append(f"    {name} - OK ({report['path']})")
    else:
        severity = 'warn'
        lines.append(f"    {name} - unmanaged copy ahead of the environment's: {report['path']}")
    if report['shadows']:
        lines.append(f"      hides the environment's own copy: {report['shadows']}")
    if severity != 'ok':
        lines.append("      Setup builds its own copy into the environment; retire this one or put the "
                     "environment's bin first on PATH.")
    return lines, severity
