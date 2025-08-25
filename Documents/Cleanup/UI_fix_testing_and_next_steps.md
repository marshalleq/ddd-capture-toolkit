# UI Fix Testing and Next Steps

## Problem Summary
The VHS Workflow Control Centre freezes consistently during job submission, specifically when FFmpeg is involved. The freeze happens **every time** when FFmpeg is present, not just sometimes.

## What We've Tested and Eliminated

### ✅ **Things That Are NOT Causing the Freeze:**

1. **Threading Issues** - Background job submission works fine in isolation
2. **Complex Subprocess Handling** - Simplified FFmpeg execution back to basic `subprocess.Popen()`
3. **Missing FFmpeg** - When FFmpeg is missing, it fails immediately with `FileNotFoundError`
4. **Lock Contention** - Extensive testing shows no lock contention between UI and job manager
5. **Rich Terminal Output** - Rich tables render fine during rapid UI updates
6. **Non-blocking Methods** - Job manager non-blocking methods work correctly
7. **Select-based Input** - The `select()` input handling works without issues
8. **Adaptive Refresh Intervals** - Implemented but didn't resolve the freeze

### ✅ **Components That Work Correctly:**

1. **Job Queue Manager** - Processes jobs correctly, handles failures properly
2. **Individual Job Submission** - `add_job_nonblocking()` works fine in isolation
3. **Status Queries** - `get_queue_status_nonblocking()` and `get_jobs_nonblocking()` work
4. **Background Job Processing** - Job processor thread runs without hanging
5. **Terminal Operations** - Screen clearing, Rich tables, input handling all work

## Key Insight: The FFmpeg Connection

**Critical Discovery:** The freeze happens **every time** with FFmpeg, not sporadically. This suggests:

- The freeze is specifically related to FFmpeg execution within the job processor
- When FFmpeg is missing, jobs fail quickly and no freeze occurs
- When FFmpeg is present, something about its execution causes the UI to hang

## Current Test Files Created

1. `test_freeze.py` - Initial isolation test
2. `test_minimal_ui_freeze.py` - Minimal UI reproduction
3. `test_job_submission_freeze.py` - Direct job submission test
4. `test_subprocess_hang.py` - FFmpeg subprocess behavior test
5. `test_job_processor.py` - Job processor investigation
6. `test_exact_ui_freeze.py` - Exact workflow centre reproduction
7. `test_lock_contention.py` - Lock contention stress test

## Current System State

- **FFmpeg Status:** Not installed (`/usr/bin/which: no ffmpeg`)
- **Job Queue:** 6+ failed jobs (all fail due to missing FFmpeg)
- **Job Processor:** Running correctly, processes jobs that fail immediately
- **No Active Freeze:** System currently behaves normally because FFmpeg is missing

## Next Steps to Investigate

### 🎯 **Priority 1: Install FFmpeg and Test**

The most critical next step is to **install FFmpeg** and reproduce the freeze:

```bash
# Install FFmpeg on Fedora
sudo dnf install ffmpeg

# Or install from RPM Fusion
sudo dnf install https://mirrors.rpmfusion.org/free/fedora/rpmfusion-free-release-$(rpm -E %fedora).noarch.rpm
sudo dnf install ffmpeg
```

### 🎯 **Priority 2: Create Real File Test**

Once FFmpeg is installed, create a test with actual video/audio files:

1. Create small test video file: `ffmpeg -f lavfi -i testsrc=duration=5:size=320x240:rate=1 -c:v libx264 test_video.mkv`
2. Create small test audio file: `ffmpeg -f lavfi -i sine=frequency=440:duration=5 test_audio.wav`
3. Submit final-mux job using these real files
4. Observe if freeze occurs during actual FFmpeg processing

### 🎯 **Priority 3: FFmpeg Execution Monitoring**

If freeze occurs with FFmpeg installed, investigate:

1. **FFmpeg Process Monitoring:**
   - Does FFmpeg process start correctly?
   - Does it hang during execution?
   - Is the output reading loop causing issues?

2. **Subprocess I/O Investigation:**
   - Test `stderr.readline()` behavior during long FFmpeg operations
   - Check if `process.poll()` calls are blocking
   - Monitor for deadlocks in the FFmpeg output monitoring loop

3. **Threading Analysis:**
   - Check if FFmpeg subprocess blocks the job processor thread
   - Verify if this blocking affects the main UI thread

### 🎯 **Priority 4: Create FFmpeg-Specific Test**

Create a test that specifically reproduces the FFmpeg execution scenario:

```python
# test_ffmpeg_freeze.py - Test with actual FFmpeg execution
def test_real_ffmpeg_execution():
    # Submit job with real video/audio files
    # Monitor UI responsiveness during FFmpeg processing
    # Check for exact freeze point
```

## Theories to Test

### **Theory A: FFmpeg Output Reading Deadlock**
The `stderr.readline()` calls in the FFmpeg monitoring loop might deadlock when FFmpeg produces certain types of output, blocking the job processor thread and causing UI freeze.

### **Theory B: FFmpeg Subprocess Blocking**
FFmpeg execution might block in a way that affects the threading model, even though subprocess calls should be non-blocking.

### **Theory C: Resource Contention During FFmpeg**
FFmpeg might consume resources (CPU/memory) in a way that interferes with the UI refresh cycle, causing apparent "freezing."

## Diagnostic Commands Ready

```bash
# Check FFmpeg installation
which ffmpeg
ffmpeg -version

# Test FFmpeg with small files
ffmpeg -f lavfi -i testsrc=duration=2:size=160x120:rate=1 -t 2 test_short.mp4

# Monitor processes during job execution
ps aux | grep ffmpeg
ps aux | grep python | grep job
```

## Code Changes Made

1. **Simplified FFmpeg execution** in `job_queue_manager.py` (removed complex threading)
2. **Added non-blocking methods** for job queue access
3. **Implemented adaptive refresh** in `workflow_control_centre.py`
4. **Added async queue saving** to reduce blocking operations

## Status: Ready for FFmpeg Testing

The system is now in a good state for testing the actual freeze condition. The key is to install FFmpeg and test with real files to reproduce the exact freeze scenario. All testing infrastructure is in place to immediately identify where in the FFmpeg execution chain the freeze occurs.

**Next Session Action Items:**
1. Install FFmpeg
2. Run `test_job_submission_freeze.py` with FFmpeg available
3. Create real test files and submit actual final-mux job
4. Identify exact freeze point in FFmpeg execution
5. Implement targeted fix based on findings
