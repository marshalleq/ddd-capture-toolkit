# Planned Features

## 1. Alphabetical Project Sorting

### Problem
The project list in the workflow control centre reorders unpredictably during a session. This causes confusion because:
- Letter/number shortcuts (1, 2, 3...) become unreliable
- User thinks they're acting on project 1 but it's now project 8
- Status indicators may appear to move around

### Root Cause
Projects are returned in filesystem scan order (`os.listdir()`), which is not guaranteed to be stable. Dictionary insertion order is preserved but depends on scan order.

**Current flow:**
1. `project_discovery.py` line 99: `os.listdir()` scans directory
2. Files grouped by base name in dictionary
3. `list(unique_projects.values())` returned (line 83) - no sorting
4. Assigned directly to `self.current_projects` in workflow_control_centre.py

### Solution
Add alphabetical sorting in `project_discovery.py` at line 83-84.

**Current code:**
```python
self.projects = list(unique_projects.values())
return self.projects
```

**New code:**
```python
self.projects = sorted(list(unique_projects.values()), key=lambda p: p.name.lower())
return self.projects
```

### Files to Modify
- `project_discovery.py` (line 83-84) - single change

### Testing
1. Add projects with names starting A, Z, M
2. Verify they always appear in order A, M, Z
3. Refresh the view multiple times - order should be stable
4. Add new project - should slot into correct alphabetical position

---

## 2. Per-Disk Concurrency Limits

### Problem
With a global `max_concurrent_jobs` setting, all jobs compete equally regardless of which disk they use. This leads to:
- Spinning HDDs getting saturated (e.g., 88% utilization) while NVMe sits idle
- I/O contention slowing all jobs on the same disk
- Inability to maximize throughput across heterogeneous storage

### Current State
- Global limit: `max_concurrent_jobs` in `config/job_queue.json` (default: 2, max: 8)
- Job selection: First QUEUED job in priority order (`job_queue_manager.py` lines 346-349)
- Location tracking: None - jobs only store full file paths, not which disk/location

### Solution
Implement per-location job limits that work alongside the global limit.

**Desired behavior:**
- Global limit: 8 concurrent jobs total
- Per-location limits: e.g., `hdd1bpool: 3`, `nvme2tb: 4`, `intel1tb: 2`
- Job scheduler respects BOTH limits when selecting next job

### Implementation Steps

#### Step 1: Add location tracking to QueuedJob

**File:** `job_queue_manager.py` (lines 49-95)

Add new fields to the QueuedJob dataclass:
```python
@dataclass
class QueuedJob:
    # ... existing fields ...
    source_location: str = ""   # Pool/disk name for input file
    output_location: str = ""   # Pool/disk name for output file
```

#### Step 2: Create helper to determine location from path

**File:** `job_queue_manager.py` or new `location_utils.py`

```python
def get_location_for_path(file_path: str) -> str:
    """
    Determine which location/pool a file path belongs to.

    Parses mount points to map paths like:
    - /mnt/hdd1bpool/captures/... -> "hdd1bpool"
    - /mnt/nvme2tb/captures/... -> "nvme2tb"
    - /mnt/intel1tb/captures/... -> "intel1tb"

    Returns "unknown" if path doesn't match known locations.
    """
    # Option 1: Parse from path directly
    # /mnt/LOCATION_NAME/... -> extract LOCATION_NAME

    # Option 2: Use directory_manager to match against configured locations
    pass
```

#### Step 3: Add per-location config

**File:** `config/job_queue.json`

```json
{
  "max_concurrent_jobs": 8,
  "per_location_limits": {
    "hdd1bpool": 3,
    "nvme2tb": 4,
    "intel1tb": 2,
    "_default": 2
  },
  "jobs": [...]
}
```

**File:** `job_queue_manager.py`

Add to `__init__`:
```python
self.per_location_limits = {}  # Loaded from config
```

Add getter/setter:
```python
def set_location_limit(self, location: str, limit: int):
    """Set max concurrent jobs for a specific location"""
    self.per_location_limits[location] = max(1, limit)
    self.save_queue()

def get_location_limit(self, location: str) -> int:
    """Get max concurrent jobs for a location (default: 2)"""
    return self.per_location_limits.get(location,
           self.per_location_limits.get("_default", 2))
```

#### Step 4: Populate location when adding jobs

**File:** `job_queue_manager.py` - `add_job()` method

```python
def add_job(self, job_type, input_file, output_file, ...):
    # ... existing code ...

    # Determine locations
    source_location = get_location_for_path(input_file)
    output_location = get_location_for_path(output_file)

    job = QueuedJob(
        # ... existing fields ...
        source_location=source_location,
        output_location=output_location,
    )
```

#### Step 5: Modify job selection to respect per-location limits

**File:** `job_queue_manager.py` - `_process_jobs()` method (lines 334-366)

```python
def _process_jobs(self):
    while not self.stop_processing:
        with self.lock:
            # Count running jobs globally
            running_jobs = [j for j in self.jobs if j.status == JobStatus.RUNNING]
            running_count = len(running_jobs)

            # Count running jobs per location
            jobs_per_location = {}
            for job in running_jobs:
                loc = job.source_location or "unknown"
                jobs_per_location[loc] = jobs_per_location.get(loc, 0) + 1

            # Check global limit
            if running_count >= self.max_concurrent_jobs:
                continue  # or sleep

            # Find next eligible job
            next_job = None
            for job in self.jobs:
                if job.status != JobStatus.QUEUED:
                    continue

                # Check per-location limit
                loc = job.source_location or "unknown"
                loc_limit = self.get_location_limit(loc)
                loc_running = jobs_per_location.get(loc, 0)

                if loc_running < loc_limit:
                    next_job = job
                    break
                # else: skip this job, try next one

            if next_job:
                # Start the job...
```

#### Step 6: Add UI for managing per-location limits

**File:** `ddd_main_menu.py` or `job_queue_display.py`

Add menu option to view/edit per-location limits:
```
Job Queue Settings:
1. Change max concurrent jobs (global): 8
2. Per-location limits:
   - hdd1bpool: 3 jobs max
   - nvme2tb: 4 jobs max
   - intel1tb: 2 jobs max
3. Add/edit location limit
```

#### Step 7: Update save/load to persist per-location config

**File:** `job_queue_manager.py` - `save_queue()` and `load_queue()`

Ensure `per_location_limits` is saved to and loaded from `job_queue.json`.

### Files to Modify
1. `job_queue_manager.py` - QueuedJob dataclass, add_job(), _process_jobs(), save/load
2. `config/job_queue.json` - add per_location_limits structure
3. `ddd_main_menu.py` or `job_queue_display.py` - UI for config
4. Possibly new `location_utils.py` for path-to-location mapping

### Migration
Existing jobs in the queue won't have `source_location`/`output_location` set. Handle gracefully:
```python
loc = job.source_location or get_location_for_path(job.input_file) or "unknown"
```

### Testing
1. Set global limit to 8, hdd1bpool limit to 2
2. Queue 4 jobs all from hdd1bpool
3. Verify only 2 run concurrently (not 4)
4. Queue 2 jobs from nvme2tb
5. Verify they start immediately (different location, under global limit)
6. Verify total never exceeds 8

---

## Implementation Order

Recommended order:
1. **Alphabetical sorting** - trivial one-line fix, immediate benefit
2. **Per-disk limits** - more complex, implement when time allows

---

## Notes

- These features are independent and can be implemented separately
- Per-disk limits require more testing due to job queue persistence
- Consider adding location info to job queue display for visibility

---

## 3. Auto-delete Source `.lds` After Successful Compression

### Problem
After the compress step produces an `.ldf`, the original `.lds` is left on disk. The two together can be 14+GB per project, which has filled the capture disk and caused downstream FFmpeg mux jobs to fail with `No space left on device` (the failure was previously visible only in `logs/job_queue.log`, not in the control-centre UI). Without automatic cleanup the user has to remember to delete `.lds` files manually, which defeats the disk-space benefit of compression.

### Proposed solution
Add a per-project flag in the `Nx` flags dialog (under a new "compress" section, or alongside existing audio/decode/export sections) named something like `delete_source_after_compress`. Default off. When the compress job succeeds, the job runner checks this flag and, only after passing strict validation, deletes the source `.lds`.

### Validation before deletion
The bar for deletion has to be high — the `.lds` is the original capture and is unrecoverable. Suggested checks, all of which must pass:

1. `.ldf` exists, file size is plausible (e.g. ≥ 50% of `.lds` size and ≥ 1 MB).
2. The compress job exited with return code 0 and no error message.
3. **Round-trip integrity check**: decompress the `.ldf` back to a temp file (or stream) and verify it matches the source. The cleanest form would be a checksum comparison: hash the `.lds` before/at compress time, hash the round-tripped output, require equality. Whether the underlying tool (`ld-compress` / lz4 / flac) provides this natively needs to be checked — if it does, prefer the native verify; if not, do a streaming SHA-256 comparison via decompression.
4. Optionally, decode a small range of the `.ldf` and confirm it yields a non-empty, valid `.tbc` (catches the rare case where the compressor wrote a syntactically-valid but semantically-wrong file). This may be too expensive for large captures — opt-in only.

Without (3) we are trusting the compressor's exit code; that is OK for an opt-in flag but not safe enough for a default-on behaviour. (3) should be the bar before considering making this default.

### Files likely to change
- `project_flags.py` — add a `COMPRESS_FLAGS` definition (or extend an existing one) with the new flag.
- `workflow_control_centre.py` — extend the `Nx` flags dialog to render the new section.
- `job_queue_manager.py` `_execute_lds_compress_job` — after successful compress, read the flag, run validation, delete `.lds` only if all checks pass. Log the deletion (and any validation failure) prominently.

### Open questions
- Is there an existing "lds-compress" job log/status field we can reuse for surfacing the validation result, or do we need a new field?
- Should there be a global toggle (default for all projects) in addition to the per-project flag?
- For the round-trip check, can we avoid reading the entire `.lds` twice (once to compress, once to verify)? A streaming compressor that hashes input and verified-decompressed-output simultaneously would be ideal.

---

## 4. Surface Job Errors in the Control Centre UI

### Problem
When a job fails (e.g. FFmpeg `No space left on device`, missing tool, malformed input), the control-centre shows only "queued → failed" with no visible reason. The actual error is in `logs/job_queue.log` and in the job's `error_message` field, but neither is rendered in the UI. This made the disk-full failure described in feature #3 hard to diagnose — the user assumed a control-centre bug rather than a real OS error.

### Constraints
- Terminal real estate is limited; we already have a project table, jobs panel, command input panel, and status bar.
- Job IDs change between runs, so persisting "show error for job X" across sessions is not useful.
- Error messages can be long (full FFmpeg stderr) and are not always meaningful in isolation.

### Possible directions (deferred — needs design)
- A short rolling "errors" panel at the bottom of the layout, showing the most recent N failures with project name + step + truncated error. Job ID is not the right key — use `project_name` + `step_letter` so the user can still recognise which row it relates to even after restart.
- Inline error indicator next to a failed step in the project table (e.g. red `F` with hover/expand to reveal the error). Hover doesn't translate to terminals well, but a follow-up command like `err 6f` could open the most recent error for that step.
- Click-through to log: a command like `log 6f` that pages the relevant log entries for project 6's FINAL step. Cheaper to build than a full panel.

The right shape probably depends on whether we expect users to need *one* error at a time (then a command-driven view is enough) or to glance at many *simultaneously* (then a panel is needed).

### Why deferred
This is a UX problem at least as much as a code problem; the user has flagged that doing it well in a TUI is non-trivial. Worth scoping as a separate exercise rather than rushing in alongside a one-line bug fix.

---

## 5. Stronger Per-Step Output Validation

### Problem
Every step's "complete" check today is essentially `file exists && size > 1 MB`. That is far too weak to mean *the step actually finished correctly*. Two concrete failure modes that have already bitten:

1. **EXPORT shows READY the moment DECODE starts.** vhs-decode writes the `.tbc` incrementally; it crosses 1 MB within seconds. `_is_decode_complete` then returns True on the partial file, and EXPORT (whose prereq is `_is_decode_complete`) flips to READY even though decode is still running. Users could trigger an export against a half-written TBC.
2. **Disk-full mid-write leaves files that look valid.** When the capture disk filled up during the FINAL mux, FFmpeg failed with `No space left on device` but partial outputs from earlier steps may still pass the 1 MB check. The user has no way to distinguish "step ran cleanly" from "step started, wrote >1 MB, then aborted." After a disk-full incident the entire output set has to be inspected by hand.

This is the same root cause as feature #3's deletion-validation question: we lack format-aware completeness checks. Whatever heuristics we pick for "is X complete" should be reusable as the validator for "is X safe to delete the source for."

### Goals
- Distinguish *finished* from *in-progress*.
- Distinguish *cleanly written* from *truncated* / *interrupted*.
- Avoid expensive checks on the hot path (the analyzer runs on every refresh of the control centre, ~4 Hz). Cache where possible — `(path, mtime, size) → validation result`.

### Per-step validation proposals

#### CAPTURE (`.lds` or `.ldf`)
- **Today**: file exists, size > 1 MB.
- **Better**:
  - File mtime stable for ≥ 5 s (no active writer).
  - No `domesday-duplicator` / capture process holds the file open (`fuser` / `lsof`, but those are slow — prefer the mtime check).
  - If a capture metadata sidecar (`.json`) exists, prefer its presence as the completion marker, since it's typically written at end of capture.
- **Why it's hard**: there's no in-band footer in the raw RF format. Stable-mtime is probably the strongest signal we can get cheaply.

#### DECODE (`.tbc` + `.tbc.json` + `_chroma.tbc`)
- **Today**: `.tbc` exists, size > 1 MB. `_chroma.tbc` and `.tbc.json` ignored for completion.
- **Better**:
  - **Require `.tbc.json` to exist** — vhs-decode writes it at end-of-decode (need to verify this is true for all versions; if not, the JSON's `videoParameters.numberOfSequentialFields` field reaching the expected total is the real signal).
  - Parse `.tbc.json`, require `videoParameters.numberOfSequentialFields` (or equivalent) > 0 and consistent with `.tbc` size: each field is a fixed byte count, so `.tbc` size should equal `numberOfSequentialFields × fieldBytes` (with maybe a small tolerance).
  - For colour decodes, also require `_chroma.tbc` if expected (depends on decode flags).
  - No `vhs-decode` process holds the file open / no DECODE job currently running for this project (we already track this in `_is_step_running` — wire it into `_is_decode_complete`).
- **Smallest immediate win**: in `workflow_analyzer.py:_is_decode_complete`, also require `os.path.exists(tbc_file + '.json')`. That alone fixes the "EXPORT goes READY immediately" symptom, because vhs-decode doesn't produce the JSON until late in the run.

#### COMPRESS (`.ldf`)
- **Today**: `.ldf` exists, size > 1 MB.
- **Better**:
  - Size ratio sanity: `.ldf` should be roughly 50–90% of `.lds` (typical ld-compress ratios). Outside that range → likely truncated or wrong file.
  - No COMPRESS job running for this project.
  - Round-trip integrity check (same as feature #3 deletion validation) — preferred for high-confidence "complete," but expensive enough that it should be opt-in or done once and cached.

#### EXPORT (`_ffv1.mkv`)
- **Today**: `.mkv` exists, size > 1 MB.
- **Better**:
  - `ffprobe -v error -show_streams` — must parse, must have at least one video stream, codec_name == `ffv1`.
  - Frame count from ffprobe must match `videoParameters.numberOfSequentialFields / 2` (or whatever the field-to-frame relation is) from `.tbc.json`. This catches the truncated-mkv case.
  - No `tbc-video-export` process running.
- **Cheap alternative if ffprobe is too heavy**: estimate expected size from frame count × per-frame bytes for FFV1 at this resolution and require actual ≥ 80% of estimate (similar to the existing FINAL-mux 80% rule at `job_queue_manager.py:1737`).

#### ALIGN (`_aligned.wav`)
- **Today**: `output_files['align']` populated.
- **Better**: ffprobe → must be a valid WAV, duration ≈ source video duration (within e.g. 1 s tolerance).

#### FINAL (`_final.mkv`)
- **Today**: `output_files['final']` populated, plus the existing 80%-of-video-size check inside `_execute_final_mux_job` at line 1737. This is the *only* step with a non-trivial check today, and only at job-completion time.
- **Better**:
  - ffprobe → must have video stream and (if audio was expected) audio stream; duration ≈ source.
  - Move the 80% check (or a stronger ffprobe-based check) into `_is_final_complete` so the analyzer doesn't accept a half-written file as complete on subsequent runs.

### Cross-cutting suggestions
- **Single `validate_step_output(step, project)` function** in `workflow_analyzer.py` that returns a structured result (`Valid`, `Truncated`, `InProgress`, `Missing`, plus a reason string). Today's status logic can keep its enum but the reason string can feed the future "errors panel" from feature #4.
- **Stable-mtime helper**: a small utility `is_mtime_stable(path, seconds=5)` reused by every step.
- **Cache validation results** keyed on `(path, mtime, size)`. Re-validate only when one of those changes. Avoids re-running ffprobe on every UI refresh.
- **Always check job-state first**: if a job for this step is currently RUNNING or QUEUED for this project, the step is by definition not complete, regardless of what's on disk. This is a one-line guard at the top of every `_is_*_complete`.

### Files likely to change
- `workflow_analyzer.py` — primary: every `_is_*_complete` plus `check_prerequisites`.
- `job_queue_manager.py` — secondary: move the existing FINAL 80% check into the analyzer; possibly add an output-validation step at job-completion that writes a sidecar `.validated` marker for cheap reuse.
- `project_discovery.py` — tertiary: only if we decide to populate `output_files['decode']` only when the JSON-and-TBC pair is consistent (probably not — better to do the consistency check in the analyzer so discovery stays cheap).

### Open questions
- Does vhs-decode always write `.tbc.json` only at end-of-decode, or does it stream it? (Affects whether JSON-presence is a sufficient completion marker.)
- What's the actual byte-per-field constant for the TBC format, and does it vary between PAL/NTSC/decode flags? Needed for the size-vs-frame-count cross-check.
- Is there a project-wide `.validated` marker pattern we'd want, or is per-step in-memory cache enough? Markers survive restarts but become stale if files change outside the toolkit.

### Why this is feature #5 and not a bugfix
The "EXPORT goes READY immediately" symptom *is* a bug and could be patched with a one-line `os.path.exists(tbc_file + '.json')` check. But doing only that leaves five other steps with the same weakness. The systematic pass — single validator, mtime helper, cache, ffprobe where it matters, job-state-first — is the lasting fix. Worth bundling.
