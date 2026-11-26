#!/usr/bin/env python3
"""Summarise pip-audit JSON output as Markdown for the CI job summary.

Usage: pip-audit-report.py pip-audit.json

Exits non-zero if the file is missing or not pip-audit output (pip-audit
failed for a reason other than finding vulnerabilities), or if it audited
no packages at all: neither may look like "all clear". With the environment
variable FAIL_ON_FIXED=true, also exits non-zero when a vulnerability has a
fixed version available (the weekly scheduled run uses this).
"""
import json
import os
import sys


def main(path):
    try:
        with open(path) as f:
            data = json.load(f)
    except (OSError, ValueError) as e:
        sys.exit(f"ERROR: no usable pip-audit output at {path} ({e}). pip-audit itself failed; see its log above.")
    deps = data.get("dependencies")
    if not isinstance(deps, list):
        sys.exit(f"ERROR: {path} is not pip-audit JSON (no 'dependencies' list)")
    audited = [d for d in deps if "skip_reason" not in d]
    if not audited:
        sys.exit("ERROR: pip-audit audited no packages; check the site-packages path")

    rows = []
    for d in audited:
        for v in d.get("vulns", []):
            rows.append((d["name"], d["version"], v["id"], ", ".join(v.get("fix_versions") or []) or "none yet"))
    fixed = [r for r in rows if r[3] != "none yet"]

    out = ["## Python packages in the installed environment", "",
           f"Audited {len(audited)} packages ({len(deps) - len(audited)} skipped: not on PyPI, e.g. conda-only).", ""]
    if rows:
        out += ["| Package | Installed | Vulnerability | Fixed in |", "|---|---|---|---|"]
        out += [f"| {n} | {ver} | {i} | {fx} |" for n, ver, i, fx in sorted(rows)]
    else:
        out.append("No known vulnerabilities.")
    print("\n".join(out))

    if fixed and os.environ.get("FAIL_ON_FIXED") == "true":
        print(f"\n{len(fixed)} vulnerabilities have a fixed version that a fresh install did not get. "
              "conda-forge may lag PyPI; if it persists, raise the floor in environment.yml.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    sys.exit(main(sys.argv[1]))
