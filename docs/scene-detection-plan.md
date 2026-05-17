# Scene-detection plan

## Goal

Auto-detect VHS pause/resume splices in a decoded recording and embed them as
chapter markers in the final MKV, so the archive is navigable without a
post-processing pass in DaVinci Resolve or similar. Detection runs against the
output of the existing pipeline (`_ffv1.mkv`, `*.tbc.json`, aligned audio) and
produces a per-tape, human-vettable CSV that becomes both the chapter source
and a permanent record of the splice points alongside the archive.

Long-form motivation: VHS tapes recorded with pause/resume have splice points
that aren't reliably visible in any single signal channel. MiniDV's
content-independent splice detection isn't possible here (DV had timecode
discontinuities in the stream; VHS does not). Generic AI scene detection
(e.g. DaVinci's) over-triggers on VHS noise. We need something tuned to the
characteristics of decoded VHS captures.

## Status

- Prototype complete and validated against one hand-labelled tape
  (`/mnt/nvme2tb/Captures/USA*`).
- Scratch code lives in `/tmp/scene_*.py`, `/tmp/audio_*.py`,
  `/tmp/combine_signals.py`, `/tmp/apply_chapters.py`. **Not yet integrated**
  into the main pipeline.
- Ground-truth labels live in
  `/mnt/nvme2tb/Captures/USA_chapters_groundtruth.csv` and should stay with the
  capture as a regression-test corpus.

## Empirical findings (from the USA tape, 16.6 min PAL, 51 real splices)

### Signal predictive power

Measured against the user-vetted ground truth (51 Yes / 50 No):

| Signal | AUC | Best single-signal F1 | Verdict |
|---|---|---|---|
| **Pixel-diff (ffmpeg `scene` filter score)** | **0.949** | **0.95** at `pd ≥ 0.108` | **Use as primary** |
| Combined-confidence (weighted sum of all signals) | 0.904 | 0.86 | Worse than `pd` alone |
| bPSNR (lower = more splice-like) | 0.748 | — | Mostly collinear with `pd`; keep as informational |
| Audio level change | 0.519 | — | No useful signal |
| Dropout span | 0.512 | — | No useful signal |
| Audio click ratio | **0.423** | — | **Actively misleading — do not weight** |

Conclusion: **pixel-diff is the only signal that meaningfully predicts splices
in decoded VHS**, and the optimal classifier on this tape is the threshold
`pd ≥ 0.108` (F1 = 0.95, 5 FP, 0 FN out of 51 real splices).

### Why the other signals failed

- **Audio click ratio** (peak high-frequency RMS / surrounding background) is
  fooled by loud content — people speaking, laughter, music transients. These
  produce strong click signatures with no splice present, so it's a *negative*
  correlate of splice on this tape (AUC < 0.5).
- **Audio level change** (pre/post 1-second RMS ratio) catches some splices
  but fires equally often on real audio environment changes within a single
  recording.
- **bPSNR drops to ~5.0** look like a strong splice signature in a few cases,
  but most real splices have bPSNR ≈ 36 (totally normal). The bPSNR=5
  pattern, where it occurs, marks tape damage that *coincides* with a small
  number of splices, not splices themselves.
- **Dropouts** are routinely concealed by vhs-decode's interpolation. By the
  time signal reaches `.tbc.json`, the dropout span describes how much was
  damaged, not how much survived — and most surviving footage is visually
  fine even when dropouts are present.

### Tag combinations (precision by signal mix)

| Evidence tag fired | Yes | No | Yes % |
|---|---|---|---|
| `pixeldiff` (alone) | 35 | 3 | 92% |
| `pixeldiff+*` (any combination) | 44 | 5 | 90% |
| `weak` (no signal cleared its threshold) | 1 | 22 | 4% |
| `audio-click` (alone) | 1 | 15 | 6% |
| `dropout-spike` (alone) | 0 | 3 | 0% |
| `audio-click+audio-level` | 1 | 2 | 33% |

**Anything without `pixeldiff` is essentially noise**, and `pixeldiff` alone
is sufficient.

### Failure modes still present in the prototype

1. **Camera-motion false positives** — pans, fast zooms, sudden gestures push
   `pd` above threshold without a real splice. Worst examples on this tape:
   15:01.76 (`pd=0.44`) and 15:13.72 (`pd=0.50`). Plausible fix: optical-flow
   or motion-compensated pixel-diff, which generic scene detectors do not.
2. **Clean punch-in splices with near-zero signal** — splices where pause/
   resume kept the framing similar enough that pixel-diff barely registers.
   Two cases barely cleared threshold (06:28: `pd=0.11`, 05:49: `pd=0.13`).
   These are the cases the **head-switch capture** would fix cheaply — see
   "Future improvements" below.
3. **Loud audio events** firing weighted-confidence detector even when pd is
   near zero (e.g. 03:01.56: `pd=0.06`, `click=12.3`, `level=7.19`). Fixed
   by dropping audio from the score.

### Tape characteristics that matter for tuning

This tape: 51 splices in 16.6 min ⇒ 3.07/min, median gap 14.9 s, range
2.3–75 s. The 80s home-video pause/resume habit (start/stop/punch-in over the
tail) produces dense, short scenes. Detector thresholds and minimum-spacing
rules should be set with this kind of density in mind, not assume movie-style
~minutes-between-cuts.

## Detector design (v1, what to implement)

```
.tbc + .tbc.json   →   tbc_signals.npz        ┐
_ffv1.mkv          →   ffmpeg scene filter    ├──→  candidates.csv  →  (vet)  →  chapters.ffmetadata  →  remux
_aligned.wav       →   audio envelopes        ┘                                                                  →  *_final.mkv
```

### Stage 1 — pixel-diff scan (primary signal)

```
ffmpeg -i <file>_ffv1.mkv -an \
       -vf "select='gt(scene,0.05)',metadata=print:file=<out>.txt" \
       -f null -
```

- Threshold 0.05 is intentionally **permissive** — we'd rather review and
  prune than miss.
- Parse the showinfo output into `(time_s, score)` pairs.
- Cluster candidates within 1.5 s of each other; keep the highest-scoring
  frame in each cluster.

### Stage 2 — annotate with informational signals

For each candidate, look up:

- `bPSNR_min`, `dropout_span_peak` (in a ±5 frame window) from `.tbc.json`
- `click_ratio` (peak high-frequency RMS / ±3 s baseline median) and
  `level_ratio` (median RMS of 1 s before vs 1 s after) from the aligned WAV

These are **annotations only** — they appear in the EVIDENCE column for the
human reviewer to read, they do **not** weight the candidate's confidence.

### Stage 3 — threshold

- **Per-file relative threshold preferred over absolute.** On this tape
  `pd ≥ 0.108` is optimal, but that's a constant fitted to one tape. For
  cross-tape robustness, use either:
  - "keep all `pd ≥ p95(file)`" — adapts to each tape's noise floor, or
  - "keep top-N per minute" — adapts to content density.
- Either approach is much more robust to RF-gain variation than an absolute
  number (see "Gain and signal-chain sensitivity" below).

### Stage 4 — write the vettable CSV

Format (header row recognised by column name, not position):

```
Correct?,TIME,CONF,NAME,EVIDENCE
,00:00:44.96,0.39,Scene N,pixeldiff | pd=0.390 bpsnr=31.2 do=4.1 click=2.5 level=2.77
```

- `Correct?` is blank by default; the user fills in `Yes` / `No` during review.
- `TIME` is `HH:MM:SS.ss` (matches what player UIs show; avoids manual
  seconds-to-minutes translation during vetting).
- LibreOffice Calc opens this as CSV cleanly; commas chosen over tabs after a
  user-reported viewer issue.
- The file is saved alongside the capture as
  `<basename>_chapters_review.csv` initially, and renamed to
  `<basename>_chapters_groundtruth.csv` once vetted.

### Stage 5 — apply (mux into MKV)

Read the (edited) CSV, skip rows where `Correct? == No`, sort by time, dedupe
within 0.5 s, generate an FFmetadata chapter file, and remux without
re-encoding:

```
ffmpeg -i <basename>_ffv1.mkv \
       -i <basename>_aligned.wav \
       -i <basename>_chapters.ffmetadata \
       -map 0:v -map 1:a -map_metadata 2 -map_chapters 2 \
       -c:v copy -c:a flac -compression_level 5 \
       <basename>_final.mkv
```

(Identical to the existing final-mux step, just with an extra `-map_chapters`
input.)

## Where this fits in the pipeline

Existing pipeline stages (already in `.claude/skills/`):

```
capture → decode → export → align → final-mux
```

Proposed insertion point: **between `align` and `final-mux`**, as an optional
stage. Logical flow:

```
align → scene-detect → vet (manual) → final-mux
```

- `scene-detect` produces `<basename>_chapters_review.csv` from
  `_ffv1.mkv` + `.tbc.json` + `_aligned.wav`.
- Vetting is manual — open in LibreOffice / spreadsheet, fill in `Correct?`.
- `final-mux` learns to ingest the chapters CSV when one is present (and
  works without it for backward compat).

Suggested new project artefacts:

- `.claude/skills/scene-detect/` — guidance skill for this step
- `tools/scene-detect/` (or similar location matching other tool conventions)
  — the actual scripts:
  - `extract_signals.py` — produces tbc-signals NPZ and audio-envelope NPZ
  - `pixeldiff_scan.py` — runs ffmpeg scene filter and parses output
  - `build_candidates.py` — combines into the review CSV
  - `apply_chapters.py` — reads vetted CSV, produces FFmetadata
- `project_flags.py` — add a `chapters_reviewed: bool` flag so the workflow
  browser knows whether `final-mux` can pick up chapters automatically

## Gain and signal-chain sensitivity

DdD capture gain (700-800 typical, varies tape-to-tape) affects RF
amplitude but should have minimal impact on the primary signal:

| Signal | Affected by RF gain? | Why |
|---|---|---|
| **pixel-diff** | Minimal | Operates on decoded 8-bit video; vhs-decode normalises black/white from the actual signal. |
| bPSNR | Marginal | SNR ratio against detected black level — gain amplifies signal and noise proportionally. |
| Dropout span | Possibly slightly | Depends on whether vhs-decode's dropout threshold is absolute or relative to signal. |
| Audio click / level | Zero | Audio comes from a separate channel (clockgen-Lite line in), not RF. |

Since the conclusion is **pixel-diff only**, gain variation should not break
the detector. **Per-file relative thresholds (Stage 3) remove what little
sensitivity remains** and are the recommended path even before we worry about
cross-tape generalisation.

## Future improvements (in priority order)

### 1. Head-switch signal capture
The vhs-decode pipeline supports a 3rd audio channel carrying the VCR's head-
switch / servo signal — effectively a tachometer on the head drum. A
pause/resume causes the capstan/drum servo to lose lock and re-acquire,
producing a clean, content-independent timing glitch. This would resolve both
remaining failure modes:
- Camera-motion false positives (no servo glitch → not a splice)
- Clean punch-in misses (servo glitch → splice even without pixel change)

Current capture pipeline captures 2 channels only — adding the 3rd requires
hardware/electronics work. User has flagged this as a worthwhile future
project.

### 2. Per-file relative threshold
See Stage 3 above. Easy code change once we have a second labelled tape to
sanity-check the percentile cutoff against.

### 3. Motion-compensated pixel-diff
Would address camera-motion false positives without head-switch capture.
PySceneDetect's `ContentDetector` does something similar but heavier. Could
also use ffmpeg's `vidstabdetect` motion vectors as a "this is just panning"
mask. Probably not worth implementing until #1 (head-switch) is ruled out as
an alternative.

### 4. Multi-tape regression corpus
Each newly captured tape should produce a `*_chapters_groundtruth.csv` once
vetted. The collection becomes:
- A regression test set for detector changes ("does the new threshold still
  catch all known splices?")
- A training set if we ever want to fit thresholds rather than hand-tune them.

### 5. Chapter naming
Currently auto-named `Scene N`. Future: extract a thumbnail per chapter and
let the user rename in the same vetting pass (or post-vet). Out of scope for
the initial implementation.

## Open questions

- **Where does the scene-detect step actually run?** Inside the
  `project_workflow` orchestration like other steps, or as a standalone
  script the user invokes? Probably orchestrated, mirroring `align`.
- **What's the policy when no vetted CSV exists at final-mux time?**
  Options: (a) skip chapters, (b) use the unvetted review CSV with all
  candidates as-is, (c) error and require explicit opt-in. Lean towards (a)
  with a notice.
- **Naming convention.** Stick with `<basename>_chapters_review.csv` (raw
  candidates) and `<basename>_chapters_groundtruth.csv` (vetted)? Or one
  file with status tracked in `project_flags`? The two-file approach is
  cleaner for backup/diff and matches the "permanent record alongside
  archive" intent.

## Files / artefacts

Existing (do not move yet — they're experimental):

- `/tmp/scene_explore.py`, `/tmp/scene_detect{,2,3,4,5}.py` — iterations of
  the tbc-only detector (kept for reference; superseded by combine_signals)
- `/tmp/audio_inspect.py`, `/tmp/audio_compare.py`, `/tmp/lf_thump.py` —
  audio characterisation passes (negative results, but informative)
- `/tmp/combine_signals.py` — current best detector (pixel-diff + annotations)
- `/tmp/apply_chapters.py` — CSV → FFmetadata converter
- `/tmp/reformat_time.py` — seconds → HH:MM:SS.ss in-place editor
- `/tmp/analyse_groundtruth.py` — signal-vs-label AUC and F1 analysis

Permanent:

- `/mnt/nvme2tb/Captures/USA_chapters_groundtruth.csv` — vetted ground truth
  for the USA tape. Stays with the capture; regression-test target.
- `/mnt/nvme2tb/Captures/USA_chapters_review_by_time.csv.bak` — pre-time-
  reformat backup; can be deleted once the workflow stabilises.

Trial output (can be regenerated):

- `/mnt/nvme2tb/Captures/USA_scenetest_v6.mkv` — last muxed trial with all
  101 unvetted candidates as chapters.
