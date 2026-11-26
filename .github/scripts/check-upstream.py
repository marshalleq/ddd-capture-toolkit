#!/usr/bin/env python3
"""Daily checks of the upstream tools the toolkit installs or compiles.

Dependabot only sees pinned conda/pip packages and GitHub Actions. The decoders
and FFmpeg come from elsewhere, so this checks, for each:
  1. Security advisories the upstream project publishes in its own GitHub
     repository that are not yet listed in .github/advisories-reviewed.txt.
  2. FFmpeg (compiled in performance mode): a newer point release of the
     pinned FFMPEG_VERSION in build-scripts/build-ffmpeg.sh.
  3. The tbc-video-export AppImage pinned in setup.sh: a newer release.
  4. Each git submodule (compiled in performance mode): how far it is behind
     its upstream's newest release (or default branch, if it has no releases).
  5. Upstream licences differing from EXPECTED_LICENCES below.

Writes Markdown findings to OUTPUT_FILE (empty when nothing applies) and
prints them. Exits non-zero if a source cannot be read: a gap must not look
like "all clear". Needs GH_TOKEN for the GitHub API (read-only use).
"""
import json
import os
import re
import subprocess
import sys
import urllib.request

# Upstream repositories whose code the toolkit runs, and their licence when
# this list was written. A change is reported so the owner can check it still
# allows free use and redistribution.
EXPECTED_LICENCES = {
    "oyvindln/vhs-decode": "GPL-3.0",
    "happycube/ld-decode": "GPL-3.0",
    "JuniorIsAJitterbug/tbc-video-export": "GPL-3.0",
    "namazso/tape-decode-rs": "GPL-3.0",
    "marshalleq/domesday-duplicator-cmdline": "GPL-3.0",
}


def gh(path):
    """GitHub API GET through the gh CLI (authenticated, read-only)."""
    r = subprocess.run(["gh", "api", "-H", "Accept: application/vnd.github+json", path],
                       capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"ERROR: gh api {path} failed: {r.stderr.strip()}")
    return json.loads(r.stdout)


def gh_optional(path):
    """Like gh(), but returns None for 404 (e.g. a repo with no releases)."""
    r = subprocess.run(["gh", "api", path], capture_output=True, text=True)
    if r.returncode != 0:
        if "HTTP 404" in r.stderr:
            return None
        sys.exit(f"ERROR: gh api {path} failed: {r.stderr.strip()}")
    return json.loads(r.stdout)


def read_value(path, pattern, what):
    with open(path) as f:
        m = re.search(pattern, f.read(), re.M)
    if not m:
        sys.exit(f"ERROR: could not find {what} in {path}")
    return m.group(1)


def vtuple(v):
    return tuple(int(x) for x in v.split("."))


def submodules():
    """Yield (path, upstream owner/repo, recorded commit) for each submodule."""
    cfg = subprocess.run(["git", "config", "-f", ".gitmodules", "--get-regexp", r"submodule\..*\.(path|url)"],
                         capture_output=True, text=True, check=True).stdout
    paths, urls = {}, {}
    for line in cfg.splitlines():
        key, value = line.split(" ", 1)
        name = key[len("submodule."):].rsplit(".", 1)[0]
        (paths if key.endswith(".path") else urls)[name] = value
    for name, path in paths.items():
        m = re.match(r"https://github\.com/([^/]+/[^/]+?)(?:\.git)?$", urls[name])
        if not m:
            sys.exit(f"ERROR: submodule {name} URL {urls[name]} is not a GitHub repository")
        tree = subprocess.run(["git", "ls-tree", "HEAD", path], capture_output=True, text=True, check=True).stdout.split()
        if len(tree) < 3 or tree[1] != "commit":
            sys.exit(f"ERROR: {path} is not recorded as a submodule commit")
        yield path, m.group(1), tree[2]


def main():
    findings = []

    # 1. Advisories published upstream.
    with open(".github/advisories-reviewed.txt") as f:
        reviewed = {l.split()[0] for l in f if l.strip() and not l.startswith("#")}
    repos = set(EXPECTED_LICENCES)
    new_advisories = []
    for repo in sorted(repos):
        for a in gh(f"repos/{repo}/security-advisories?state=published&per_page=100"):
            if a["ghsa_id"] not in reviewed:
                new_advisories.append(f"| {repo} | [{a['ghsa_id']}]({a['html_url']}) | {a['severity']} | {a['summary']} |")
    if new_advisories:
        findings.append(
            "### Upstream security advisories not yet reviewed\n\n"
            "Check whether the toolkit installs an affected version (easy mode installs each tool's newest "
            "release; performance mode compiles the submodule commits). Then add the advisory ID to "
            "`.github/advisories-reviewed.txt` with a one-line note.\n\n"
            "| Project | Advisory | Severity | Summary |\n|---|---|---|---|\n" + "\n".join(new_advisories))

    # 2. FFmpeg point release.
    ffmpeg = read_value("build-scripts/build-ffmpeg.sh", r'^FFMPEG_VERSION="([0-9.]+)"$', "FFMPEG_VERSION")
    series = ".".join(ffmpeg.split(".")[:2])
    req = urllib.request.Request("https://ffmpeg.org/releases/", headers={"User-Agent": "ddd-capture-toolkit-advisory-watch"})
    with urllib.request.urlopen(req, timeout=60) as r:
        listing = r.read().decode()
    available = {m for m in re.findall(r"ffmpeg-([0-9]+\.[0-9]+(?:\.[0-9]+)?)\.tar\.xz", listing)}
    if not available:
        sys.exit("ERROR: no FFmpeg releases found at https://ffmpeg.org/releases/")
    same_series = sorted((v for v in available if ".".join(v.split(".")[:2]) == series), key=vtuple)
    if same_series and vtuple(same_series[-1]) > vtuple(ffmpeg):
        findings.append(
            f"### FFmpeg {same_series[-1]} is out; performance mode compiles {ffmpeg}\n\n"
            f"Point releases in the {series} series carry security fixes. Set `FFMPEG_VERSION=\"{same_series[-1]}\"` "
            f"in `build-scripts/build-ffmpeg.sh`.")

    # 3. tbc-video-export AppImage.
    pinned = read_value("setup.sh", r"tbc-video-export/releases/download/(v[0-9][^/]*)/", "the tbc-video-export AppImage URL")
    latest = gh("repos/JuniorIsAJitterbug/tbc-video-export/releases/latest")["tag_name"]
    if latest != pinned:
        findings.append(
            f"### tbc-video-export {latest} is out; setup.sh downloads {pinned}\n\n"
            f"Update the AppImage URL in `setup.sh` (and the `tbc-video-export>=` floor in requirements.txt and the "
            f"environment files if needed).")

    # 4. Submodules behind upstream.
    rows = []
    for path, repo, commit in submodules():
        release = gh_optional(f"repos/{repo}/releases/latest")
        target = release["tag_name"] if release else gh(f"repos/{repo}")["default_branch"]
        cmp = gh_optional(f"repos/{repo}/compare/{commit}...{target}")
        if cmp is None:
            sys.exit(f"ERROR: {repo} cannot compare {commit[:9]} with {target} (commit not in that repository?)")
        if cmp["ahead_by"] > 0:
            rows.append(f"| `{path}` | {commit[:9]} | {target} | {cmp['ahead_by']} commits |")
    if rows:
        findings.append(
            "### Submodules behind their upstream\n\n"
            "Performance mode compiles these commits (vhs-decode is then moved to its newest release tag by "
            "build-vhs-decode.sh). A submodule far behind misses upstream fixes; moving it needs a performance-mode "
            "build and test.\n\n| Submodule | Recorded | Upstream | Behind by |\n|---|---|---|---|\n" + "\n".join(rows))

    # 5. Licences.
    changed = []
    for repo, expected in sorted(EXPECTED_LICENCES.items()):
        lic = (gh(f"repos/{repo}").get("license") or {}).get("spdx_id") or "none"
        if lic != expected:
            changed.append(f"| {repo} | {expected} | {lic} |")
    if changed:
        findings.append(
            "### Upstream licence changed\n\nCheck the new licence still allows free use and redistribution, then "
            "update `EXPECTED_LICENCES` in `.github/scripts/check-upstream.py`.\n\n"
            "| Project | Was | Now |\n|---|---|---|\n" + "\n".join(changed))

    body = ""
    if findings:
        body = ("The daily advisory watch found the items below. This issue is updated each day and closed "
                "automatically when nothing applies.\n\n" + "\n\n".join(findings) + "\n")
    with open(os.environ["OUTPUT_FILE"], "w") as f:
        f.write(body)
    print(body or "No findings: the checks ran and nothing applies.")


if __name__ == "__main__":
    main()
