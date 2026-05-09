# Output Integrity Validation — Implementation Plan

Companion to feature #5 in `planned-features.md`. This document is the *how*, not the *what*.

## Goals

A single source of truth for "did step X finish correctly" that:

1. Distinguishes *finished* from *in-progress*.
2. Distinguishes *cleanly written* from *truncated / interrupted*.
3. Is cheap enough to run on the analyzer's hot path (~4 Hz UI refresh).
4. Returns enough context that the UI can eventually surface the reason a step is not complete (feeds feature #4).
5. Is reusable as the gate for destructive actions like "delete `.lds` after compress" (feeds feature #3).

Non-goal: catching every possible form of corruption. Round-trip cryptographic verification is out of scope here; that belongs to the deletion gate in feature #3.

## Architecture

### Single validator entry point

```python
# workflow_analyzer.py

class ValidationState(Enum):
    VALID = "valid"            # Output exists and looks complete
    IN_PROGRESS = "in_progress"  # A job is currently producing it
    TRUNCATED = "truncated"    # File exists but fails format / size checks
    MISSING = "missing"        # No output yet
    UNKNOWN = "unknown"        # Validator could not run (e.g. ffprobe missing)

@dataclass
class ValidationResult:
    state: ValidationState
    reason: str                # Human-readable, suitable for UI display
    details: Dict[str, Any]    # e.g. {"expected_frames": N, "actual_frames": M}

def validate_step_output(step: WorkflowStep, project: Project) -> ValidationResult: ...
```

`_is_*_complete` becomes a thin wrapper: `state == VALID`. Existing callers continue to work; new callers (UI error panel, deletion gate) read the structured result.

### Cross-cutting work, done once per call

Inside `validate_step_output`, before dispatching to step-specific helpers:

1. **Job-state-first guard.** If a job for this step is currently RUNNING or QUEUED for this project, return `IN_PROGRESS` immediately. Output may exist on disk but it is not safe to call complete. (One-line guard, prevents the EXPORT-goes-READY-immediately class of bug at the architectural layer.)
2. **Cache lookup.** Key = `(step, project.name, output_path, mtime, size)`. On hit return the cached `ValidationResult`. On miss, fall through to the step-specific check, then store. Eviction: simple LRU sized to ~10× project count.
3. **Step dispatch.** One helper per step, easy to test.

### Per-step helpers — what they actually check

Each helper returns a `ValidationResult`. Order of checks within a helper: cheapest first, return early.

| Step | Output(s) | Cheap checks | Format-aware checks |
|---|---|---|---|
| CAPTURE | `.lds` / `.ldf` | exists, size ≥ 1 MB, mtime stable | (none — raw RF has no footer) |
| DECODE | `.tbc` + `.tbc.json` | both exist, sizes ≥ 1 MB | parse JSON; require `videoParameters.numberOfSequentialFields > 0`; cross-check `.tbc` size against `fields × fieldBytes` |
| COMPRESS | `.ldf` | exists, size ≥ 1 MB | size ratio: `.ldf` between 30% and 95% of `.lds` (when source still present) |
| EXPORT | `_ffv1.mkv` | exists, size ≥ 1 MB | ffprobe: parses, has video stream, codec == ffv1; frame count matches `.tbc.json` |
| ALIGN | `_aligned.wav` | exists | ffprobe: valid WAV, duration > 0 |
| FINAL | `_final.mkv` | exists, size ≥ 80% of `_ffv1.mkv` (existing rule, moved here) | ffprobe: video stream + audio stream (when expected), duration ≈ video duration |

### Stable-mtime helper

```python
def is_mtime_stable(path: str, settle_seconds: float = 5.0) -> bool:
    """True if mtime is older than `settle_seconds` ago."""
```

Implemented as a single comparison against `time.time()`. We do **not** sleep or sample twice — the analyzer cannot block. The semantics are "no writer has touched this file in the last N seconds," which combined with the job-state-first guard is enough: if a process is actively writing, either a job is running (caught by guard) or mtime is recent (caught here).

## Phases

Each phase is independently shippable.

### Phase 0 — Foundations (no behavior change)

- Add `ValidationState`, `ValidationResult` dataclass, `validate_step_output` skeleton with the job-state-first guard and cache scaffolding, all dispatching to placeholder helpers that just call the existing `_is_*_complete` and wrap the boolean.
- Add `is_mtime_stable` helper.
- Wire `_is_step_complete` to call `validate_step_output(step).state == VALID`.

**Why first:** establishes the architecture without changing any check logic. Easy to revert if we don't like the shape. Safe to merge.

**Files:**
- `workflow_analyzer.py` (primary)

### Phase 1 — Quick win: DECODE JSON gate

- Update the DECODE helper to require `<tbc>.json` exists (alongside the existing size check).
- Verify by running the control centre during a real decode — EXPORT should no longer flip to READY in the first 30 seconds.

**Why second:** smallest possible change with the largest visible benefit (fixes the user's specific complaint). Validates that the Phase 0 architecture works end-to-end on a real path.

**Files:**
- `workflow_analyzer.py:_is_decode_complete` (or its new helper)

**Risk:** if vhs-decode's behavior diverges from ld-decode's atomic-rename pattern in some edge case (e.g. crash mid-write leaves a `.tbc.json.tmp` but no `.tbc.json`), the check still works correctly — `.tbc.json` won't exist, so step is not VALID. The fail-safe direction is correct.

### Phase 2 — Format-aware checks per step

In dependency order (each step's check helps validate the next step's prereq):

1. **DECODE** — JSON parsing + field-count cross-check against `.tbc` size.
2. **EXPORT** — ffprobe + frame-count cross-check against `.tbc.json`.
3. **FINAL** — move the existing 80% rule from `job_queue_manager.py:1737` into the analyzer; add ffprobe stream-presence check.
4. **ALIGN** — ffprobe duration check.
5. **COMPRESS** — size-ratio check (when `.lds` still present).
6. **CAPTURE** — stable-mtime backstop.

Each step is a separate, testable change.

**Files:**
- `workflow_analyzer.py` — every helper.
- `job_queue_manager.py:1737` — extract the 80% rule into a shared utility, leave a thin call from the job runner.

**External dependency:** ffprobe. Already shipped via FFmpeg in both easy and performance modes (per `docs/easy-performance_status.md`). Validator should fall back to `UNKNOWN` if ffprobe is unavailable rather than failing the step — UI can render "validator unavailable" without blocking the user.

### Phase 3 — Caching

- Add the `(step, name, path, mtime, size)` cache. Initially in-memory, dict-backed.
- Add cache-hit / cache-miss counters logged at debug level so we can confirm hit rate is high during typical use.

**Why after Phase 2:** ffprobe is the expensive call. No point caching cheap checks. Once Phase 2 introduces ffprobe, caching becomes a measurable win.

**Files:**
- `workflow_analyzer.py`

### Phase 4 — UI plumbing for the reason string

- Surface `ValidationResult.reason` somewhere the user can see it on demand, even before the "errors panel" of feature #4 ships.
- Minimum viable: a new command `why <coord>` (e.g. `why 6e`) that prints the most recent `ValidationResult` for that step. No new UI real estate needed — uses the existing message line.

**Why this phase:** lets us *use* the new structured information without committing to a UI redesign. Validates that the `reason` strings we generate are actually useful.

**Files:**
- `workflow_control_centre.py:handle_command` — add `why <coord>` parsing, alongside existing `force` / `clean` / `stop` patterns.

### Phase 5 — Reuse for feature #3 deletion gate

- When the auto-delete-source flag is enabled and a compress job succeeds, before deleting `.lds`, re-run `validate_step_output(COMPRESS, project)`. Require `state == VALID` AND a stronger round-trip integrity check (per feature #3 plan). Only delete on both passing.
- This phase intentionally leaves the round-trip check out of scope — that's feature #3's domain. We just expose the validator as the necessary-but-not-sufficient gate.

**Files:**
- `job_queue_manager.py:_execute_lds_compress_job`

### Phase 6 — Tests

- Unit tests per helper, with synthetic fixtures: a 100-byte `.tbc`, a 0-frame `.tbc.json`, a truncated `_ffv1.mkv`, etc.
- One integration test against a real project directory (manual, on the user's capture disk) to confirm the validator agrees with reality across all six steps.

Tests can be written in parallel with Phases 1–5; calling them out as a separate phase only because they aren't blocking the user-facing behavior.

## Open questions to resolve during Phase 2

1. **TBC field-byte constants.** Need exact `fieldBytes` for PAL vs NTSC, with and without colour decoding. Either pull from `.tbc.json.videoParameters` directly (preferred — avoids hardcoding) or hardcode after confirming via a sample TBC. *Resolve before writing the DECODE size cross-check.*
2. **ffprobe invocation overhead.** Need to measure: how long does `ffprobe -v error -show_streams -show_format` take on a 5 GB FFV1 MKV? If > 200 ms, caching is mandatory; if < 50 ms, cache is nice-to-have. Affects whether Phase 3 can be deferred. *Resolve before Phase 3.*
3. **Frame-count vs field-count terminology.** TBC uses fields, MKV uses frames. The 2:1 relationship needs to be confirmed (interlaced sources). *Resolve before EXPORT cross-check.*
4. **Stable-mtime settle window.** 5 seconds is a guess. Capture writes can have natural pauses. Want a value short enough that "really finished" cases aren't held up, long enough that mid-capture pauses don't trigger false-VALID. *Resolve empirically on the user's typical capture rhythm.*

## Risks and mitigations

| Risk | Likelihood | Mitigation |
|---|---|---|
| ffprobe not on PATH in some setup | low | Fall back to `UNKNOWN`, never block. |
| Cache holds stale result after external file edit | low | Key includes mtime + size; any edit invalidates. |
| Per-step helper raises an unexpected exception | medium | Wrap dispatch in try/except, return `UNKNOWN` with exception message in `reason`. |
| 4 Hz refresh × 6 steps × 10 projects = 240 ffprobe calls/sec | high without cache | Phase 3 (cache) is required, not optional, before enabling ffprobe in Phase 2. Order phases accordingly: implement cache scaffolding in Phase 0, populate it in Phase 3, but flip ffprobe on only after the cache is live. |
| Behavior regression: a step that *was* showing complete now shows in-progress | medium | Phase 0 wraps existing logic identically. Each Phase 2 helper is a separate change with a clear rollback. The user should be able to selectively disable a stricter check via a settings flag if it turns out to be wrong. |

## Estimated effort

Rough order of magnitude, not a commitment:

- Phase 0: half a day.
- Phase 1: 30 minutes plus a real-decode validation run.
- Phase 2: 1–2 days, mostly ffprobe wrangling and getting the field/frame math right.
- Phase 3: half a day.
- Phase 4: 1 hour.
- Phase 5: 1 hour (the heavy lifting is in feature #3, not here).
- Phase 6: 1 day, can run in parallel.

Total: 3–4 days of focused work, shippable in increments.

## What this plan deliberately does *not* do

- **No `.validated` sidecar markers on disk.** Considered briefly; the in-memory cache is enough and avoids a new file convention. If we later want persistence across restarts, that's an additive change.
- **No background/async validation thread.** Tempting for ffprobe, but it adds concurrency hazards. Cache + cheap-checks-first should be enough; revisit only if profiling shows otherwise.
- **No reorganization of `workflow_analyzer.py`.** The file is large but well-structured. The new code drops in alongside existing helpers; refactor only if it becomes hard to read.
- **No changes to `project_discovery.py`.** Discovery should stay cheap and dumb (just file presence). All validation lives in the analyzer.
