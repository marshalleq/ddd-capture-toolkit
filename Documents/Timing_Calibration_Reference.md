# Audio/Video Timing Calibration Reference

## Overview
This document provides a comprehensive understanding of the audio/video synchronization system used in the DdD Sync Capture project, including calibration and validation processes.

## System Architecture

### Capture Process Flow
1. **Video-First Architecture**: Video recording starts first via GUI automation
2. **Audio Delay**: Audio recording starts after a configurable delay (`audio_delay` from config.json)
3. **Hardware Components**: 
   - Domesday Duplicator (RF video capture)
   - SOX (audio capture via ALSA)
   - Clockgen Lite (sync timing reference)

### Key Timing Components

#### 1. SOX Startup Delay
- **What it is**: Time between `subprocess.Popen()` call and actual audio recording start
- **Cause**: ALSA hardware initialization, driver loading, buffer setup
- **Characteristics**: 
  - **THEORY TO TEST**: May be variable (0.3s to 0.6s range observed)
  - **THEORY TO TEST**: May depend on system load, hardware state, driver caching
  - **UNKNOWN**: Whether it's actually constant or variable
  - **NEEDS TESTING**: Multiple calibration runs from zero baseline required

#### 2. GUI Automation Delay
- **What it is**: Time between pyautogui.click() and actual video recording start
- **Cause**: GUI response time, application processing
- **Characteristics**: 
  - Generally small (10-50ms)
  - More consistent than SOX delay
  - Included in overall timing measurements

#### 3. Pipeline Processing Delays
- **What it is**: Internal delays in capture hardware/software
- **Components**: Video capture buffers, audio pipeline latency
- **Characteristics**: Generally consistent for given hardware

## Calibration Process Analysis

### Calibration Workflow
1. **Baseline Capture**: 
   - Start audio recording (SOX) immediately
   - Start video recording immediately after (zero configured delay)
   - Record test pattern for specified duration
2. **Processing**:
   - Decode RF to TBC/video
   - Mechanically align audio
   - Analyze test pattern timing in both streams
3. **Measurement**:
   - Calculate offset: `audio_start_time - video_start_time`
   - Positive offset = audio starts after video
   - Negative offset = audio starts before video

### Critical Insight: What the Calibration Measures
The calibration measurement includes ALL system delays:
- SOX startup delay
- GUI response delay  
- Hardware pipeline delays
- Any other systematic timing offsets

**Key Point**: The measured offset represents the TOTAL delay needed to synchronize the streams, not just the "pure" sync offset.

### Why SOX Delay Correction Was Added
The SOX startup delay varies between runs due to:
- System load variations
- Hardware state changes
- Driver caching effects
- ALSA subsystem state

**Problem**: If calibration runs when SOX delay is 0.6s, it measures +0.6s offset and sets delay to 0.6s. But if validation runs when SOX delay is 0.4s, the effective delay becomes 0.6s + 0.4s = 1.0s, causing overcorrection.

### Current Approach: Fixed SOX Delay Subtraction
```python
SOX_STARTUP_DELAY = 0.56  # seconds - hardcoded
true_sync_offset = measured_offset - SOX_STARTUP_DELAY
required_delay = true_sync_offset  # (if positive)
```

**Issues with Current Approach**:
1. SOX delay is not actually constant (varies 0.3-0.6s)
2. Hardcoded value may not match actual delay at calibration time
3. Creates systematic error when actual delay differs from hardcoded value

## Validation Process Analysis

### Validation Workflow
1. **Configured Capture**:
   - Start video recording first
   - Wait configured `audio_delay` seconds
   - Start audio recording (SOX)
   - Record test pattern
2. **Processing**: Same as calibration
3. **Analysis**: 
   - Measure offset with configured delay applied
   - Should be near zero if calibration is accurate

### Expected Validation Results
If calibration is perfect:
- Measured offset should be ~0.000s ± measurement noise
- Any significant offset indicates calibration error

## Testing SOX Delay Consistency Theory

### Current Evidence (Limited Data)
From recent test logs (testoffsetlog.txt) - **SINGLE DATA POINT**:
- **Calibration**: Measured +0.0733s → After SOX correction (0.56 - 0.0733) → Set delay to 0.4867s
- **Validation**: Applied 0.4867s delay → Measured -0.4176s → Suggests SOX delay was different

### Theory to Test: SOX Delay Variability
**Hypothesis**: SOX startup delay varies between calibration runs due to system conditions
**Alternative Hypothesis**: SOX startup delay is consistent and the offset differences have another cause

### Systematic Testing Approach

#### Test Protocol: Multiple Zero-Baseline Calibrations
1. **No Config Changes Needed**: Calibration always uses zero delay (ignores audio_delay setting)
2. **Run Calibration**: Execute calibration - it automatically uses zero baseline delay
3. **Record Raw Results**: Document the raw measured offset before any SOX correction
4. **Document Conditions**: Note system state, time of day, recent activity
5. **Repeat**: Perform multiple calibrations under similar conditions

#### Expected Results Analysis

**If SOX delay is CONSISTENT**:
- Raw measured offsets should be nearly identical (±10ms variance)
- Pattern: +0.073s, +0.075s, +0.071s, +0.074s (small variance around same value)
- This would suggest the hardcoded 0.56s correction is wrong but could be adjusted

**If SOX delay is VARIABLE**:
- Raw measured offsets will vary significantly (>50ms variance)
- Pattern: +0.073s, +0.156s, +0.024s, +0.187s (large variance)
- This would confirm SOX delay varies and hardcoded correction won't work

**If there's systematic drift**:
- Raw measured offsets show consistent trend (increasing or decreasing)
- Pattern: +0.073s, +0.083s, +0.093s, +0.103s (progressive change)
- This would suggest hardware warming up or system state changes

#### Recommended Test Parameters
- **Number of tests**: 5-7 calibration runs
- **Timing**: Space tests 2-3 minutes apart to allow system settling
- **Conditions**: Keep system load consistent, same VCR tape position
- **Duration**: Use same capture duration for all tests (20-30 seconds)
- **Documentation**: Create detailed log for each test with raw measurements

### Detailed Analysis of Current Results

**Calibration Phase**:
- Raw measurement: +0.0733s (audio after video)
- SOX correction applied: 0.56 - 0.0733 = 0.4867s
- Configured delay set to: 0.4867s

**Validation Phase**:
- Configured delay applied: 0.4867s (video starts first, then audio after delay)
- Measured result: -0.4176s (audio behind video)
- **This means the actual SOX delay during validation was DIFFERENT**

**Mathematical Proof of SOX Delay Variability**:
If SOX delay were constant at 0.56s:
- Calibration: `audio_time = sox_start + 0.56`, `video_time = video_start`
- Measured offset = `(sox_start + 0.56) - video_start = +0.0733s`
- This gives: `sox_start - video_start = 0.0733 - 0.56 = -0.4867s`

Validation with 0.4867s delay:
- `audio_time = sox_start + 0.56`, `video_time = video_start - 0.4867`
- Expected offset = `(sox_start + 0.56) - (video_start - 0.4867) = sox_start - video_start + 0.56 + 0.4867`
- Expected offset = `-0.4867 + 0.56 + 0.4867 = 0.56s`

But we measured -0.4176s, not +0.56s!

**This proves the SOX delay was NOT 0.56s during validation.**

Actual SOX delay during validation can be calculated:
- `-0.4176 = sox_delay - 0.4867`
- `sox_delay = -0.4176 + 0.4867 = 0.0691s`

**Conclusion**: SOX delay varied from ~0.49s (calibration) to ~0.07s (validation)

### Mathematical Analysis
Let's define:
- `S_cal` = actual SOX delay during calibration
- `S_val` = actual SOX delay during validation  
- `M_cal` = measured offset during calibration = `S_cal + other_delays`
- `M_val` = measured offset during validation

Current logic:
1. Calibration: `required_delay = M_cal - 0.56`
2. Validation applies: `required_delay`
3. Validation measures: `M_val = S_val + other_delays - required_delay`

If `S_cal ≠ S_val`, we get systematic error:
`M_val = S_val - (M_cal - 0.56) = S_val - S_cal + 0.56`

**This explains the systematic offset increase!**

## Proposed Solutions

### Option 1: Dynamic SOX Delay Measurement
- Measure actual SOX startup delay during each calibration
- Use measured value instead of hardcoded 0.56s
- Requires method to detect actual audio recording start

### Option 2: Total Offset Approach
- Use measured offset directly as required delay
- Accept that this includes SOX variability
- Rely on alignment post-processing to handle remaining sync issues

### Option 3: Multiple Calibration Averaging
- Run multiple calibration cycles
- Average the results to reduce SOX delay variance impact
- More robust but slower

### Option 4: Real-time SOX Delay Compensation
- Measure SOX delay during each capture
- Adjust timing in real-time
- Most accurate but complex to implement

## Recommended Immediate Fix

Based on the analysis, the systematic offset increase is caused by SOX delay variability combined with the hardcoded correction value.

**Recommendation**: Remove the hardcoded SOX delay correction and use the total measured offset as the required delay. This approach:

1. **Includes all system delays** in the calibration
2. **Eliminates systematic errors** from incorrect SOX delay assumptions
3. **Provides consistent results** between calibration and validation
4. **Relies on mechanical alignment** to handle remaining fine-tuning

## Implementation Notes

### Configuration Management
- `audio_delay` in config.json stores the delay for video-first capture
- This value should be the direct result of calibration measurement
- No corrections or adjustments should be applied to this value

### Validation Interpretation
- Validation offset should be near zero if calibration is accurate
- Significant validation offset indicates need for recalibration
- Validation should use the same capture architecture as normal captures

## Historical Context

This analysis resolves the confusion around SOX delay handling that has caused multiple calibration logic revisions. The key insight is that SOX startup delay variability is the root cause of systematic timing errors, not inadequate delay correction logic.

## Recent Analysis: Calibration Variance Issue (January 2025)

### Problem Identified
After running 7 calibration tests, we discovered that the mechanical audio alignment step in calibration may be introducing measurement variance and errors.

### Key Findings from 7-Test Calibration Series
- **Raw measured offsets** (before SOX correction): +0.049s to +0.092s
- **Variance**: Approximately ±20-25ms between calibration runs
- **Consistency**: Individual runs show "Good" internal consistency
- **Issue**: The variance suggests systematic measurement problems

### Root Cause Analysis
The calibration process includes a mechanical audio alignment step that:
1. Takes the raw captured audio file  
2. Applies TBC JSON timing data to "align" it with video timing
3. Measures offset between this aligned audio and the video

**Critical Problem**: The TBC JSON timing alignment assumes audio and video started synchronously. However, since they start at different times (due to GUI automation delays), this alignment step may be incorrectly shifting audio timing relative to video, introducing artificial offsets.

### Test Results Analysis
From 7 calibration runs:
- Raw offsets varied from +0.049s to +0.092s (43ms range)
- All runs concluded with "Good" measurement quality
- Recommended delays clustered around 0.468-0.503s
- **Variance too high** for a system that should be mechanically consistent

### Identified Issues with Current Calibration
1. **Mechanical Alignment Dependency**: Uses TBC JSON timing that assumes synchronized start times
2. **Start Time Assumptions**: Audio and video don't actually start simultaneously due to GUI automation
3. **Circular Logic**: Aligning audio to video timing, then measuring their offset
4. **Measurement Contamination**: The alignment step may introduce the very offsets we're trying to measure

## Proposed Testing Options

### Option 1: Skip Mechanical Alignment in Calibration
**Approach**: Modify calibration to measure timing offset directly from raw (unaligned) audio
**Pros**:
- Eliminates alignment-induced measurement errors
- Direct measurement of actual capture timing relationship
- Simpler, more transparent process
- Removes circular dependency

**Cons**:
- May be less precise due to lack of frame-accurate timing reference
- Requires different analysis algorithms
- Unknown if raw audio analysis will be accurate enough

**Implementation**: Remove `analyze_alignment_with_tbc()` call from calibration workflow

### Option 2: Cross-Correlation Based Calibration
**Approach**: Use signal processing to directly correlate audio and video test patterns
**Pros**:
- Algorithmic matching independent of start time assumptions
- High precision through signal correlation
- Robust to GUI automation timing variations
- No dependency on TBC JSON timing accuracy

**Cons**:
- More complex implementation
- Requires development of correlation algorithms
- May need different test pattern designs
- Computationally intensive

**Implementation**: Develop cross-correlation analysis between audio tones and video brightness patterns

### Option 3: Hardware Timing Reference Integration
**Approach**: Use Clockgen Lite shared timing signal for synchronization reference
**Pros**:
- Hardware-level timing accuracy
- Consistent reference across audio and video capture
- Eliminates software timing dependencies
- Most accurate theoretical approach

**Cons**:
- Requires hardware integration development
- More complex setup
- May need additional hardware connections
- Higher implementation complexity

**Implementation**: Integrate Clockgen Lite timing signal into both audio and video capture paths

### Option 4: Multiple Raw Measurements with Statistical Analysis
**Approach**: Run multiple calibrations without alignment, use statistical analysis to find true offset
**Pros**:
- Reduces impact of measurement variance
- Uses existing hardware setup
- Statistical robustness
- Identifies and compensates for systematic errors

**Cons**:
- Slower calibration process
- Still depends on raw audio analysis accuracy
- May not eliminate root cause of variance
- Requires more user time

**Implementation**: Automated multi-run calibration with statistical analysis

## Recommended Immediate Actions

### 1. Remove Mechanical Alignment from Calibration Menu
The current calibration menu includes mechanical audio alignment which is counterproductive for calibration purposes. This should be removed immediately.

### 2. Test Option 1: Direct Raw Audio Analysis
As the simplest test, modify calibration to skip mechanical alignment and measure offset directly from raw audio vs. video patterns.

### 3. Validate with Known Good Tape Segment
Use the same VCR tape position for all calibration tests to eliminate content-based variables.

## Risk Assessment

### Low Risk Solutions
- **Option 1** (Skip alignment): Easy to implement, easy to revert
- **Option 4** (Statistical): Uses existing methods, just more measurements

### Medium Risk Solutions  
- **Option 2** (Cross-correlation): New algorithms, but well-understood signal processing

### High Risk Solutions
- **Option 3** (Hardware integration): Requires hardware changes, complex implementation

## Next Steps

1. **Immediate**: Remove mechanical alignment from calibration menu
2. **Short-term**: Implement and test Option 1 (direct raw audio analysis)
3. **Medium-term**: If Option 1 shows promise, refine the analysis algorithms
4. **Long-term**: Consider Option 2 or 3 if higher precision is needed

## Future Improvements

1. **SOX Delay Measurement**: Implement dynamic SOX startup delay detection
2. **Calibration Robustness**: Add multiple-run averaging
3. **Real-time Monitoring**: Add timing validation to capture workflow
4. **Hardware Optimization**: Investigate more consistent audio capture methods
5. **Advanced Algorithms**: Develop cross-correlation based timing analysis
6. **Hardware Integration**: Explore Clockgen Lite timing reference usage

---

**Document Version**: 1.1  
**Last Updated**: 2025-01-25  
**Status**: Active Reference - Updated with Calibration Variance Analysis
