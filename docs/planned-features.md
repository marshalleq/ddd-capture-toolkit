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
