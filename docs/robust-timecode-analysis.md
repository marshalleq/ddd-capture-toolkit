# Robust Timecode System Analysis

## Executive Summary

This document analyzes the robust timecode system used in the DDD Capture Toolkit for VHS audio/video synchronization. The system encodes frame numbers into both video (binary visual strip) and audio (FSK encoding) to enable frame-accurate timing measurement. However, VHS playback degradation has prevented reliable timecode recovery. This analysis identifies the technical challenges and proposes optimizations.

## Current System Architecture

### 1. Visual Timecode Encoding

**Location:** Top 20 pixels of each video frame

**Binary Strip Implementation:**
- 32-bit binary representation of frame number (24-bit frame + 8-bit checksum)
- Each bit occupies `(width - 80) / 32` pixels horizontally (~20 pixels at 720px width)
- Bit encoding: White (255, 255, 255) = '1', Dark gray (64, 64, 64) = '0'
- Strip positioned between corner markers: starts at x=40, ends at x=width-40

**Corner Markers:**
- Top-left and bottom-right: Red squares (BGR: 0, 0, 255), 40x40 pixels
- Top-right and bottom-left: Blue squares (BGR: 255, 0, 0), 40x40 pixels
- Purpose: Frame alignment reference for distorted VHS captures

**Central Display:**
- Human-readable timecode: `HH:MM:SS:FF` format
- Large white text (font scale 3.0, thickness 8) on black background
- Frame number in top-left corner: `Frame: XXXXXX`

### 2. Audio Timecode Encoding (FSK)

**Frequency Shift Keying Parameters:**
- Frequency for '0': 800 Hz
- Frequency for '1': 1600 Hz (exactly 2:1 ratio)
- Sample rate: 48000 Hz
- Audio channels: 1 (MONO)

**Detection Ranges with Guard Bands:**
- '0' detection range: 650-950 Hz (300 Hz bandwidth around 800 Hz)
- '1' detection range: 1350-1850 Hz (500 Hz bandwidth around 1600 Hz)
- Guard band between ranges: 400 Hz (950 Hz to 1350 Hz)

**Frame Encoding Structure:**
- PAL: 1920 samples per frame (48000 / 25 fps)
- NTSC: ~1602 samples per frame (48000 / 29.97 fps)
- 32 bits per frame = ~60 samples per bit (PAL)
- Structure: 24-bit frame number + 8-bit enhanced XOR checksum

**Tone Generation:**
- Clean sine wave generation with exact phase calculation
- 5% fade-in/fade-out envelope on each bit to reduce transients
- 60% amplitude to prevent clipping

### 3. Checksum Algorithm

```
checksum = 0
for each bit position i in 24-bit frame number:
    if bit is '1':
        checksum XOR= ((i + 1) mod 256)
checksum XOR= (frame_number mod 256)
return checksum mod 256
```

### 4. Decoding Methods

**FFT-Based Frequency Detection (Weight: 2.0):**
- Apply Hanning window to bit audio segment
- Compute FFT and measure amplitude in each detection range
- Require >60% of total amplitude in one range for confident detection

**Zero-Crossing Rate Analysis (Weight: 1.0):**
- Count zero crossings in bit segment
- Estimate frequency: crossings / (2 * duration)
- Compare distance to expected 800 Hz vs 1600 Hz

**Autocorrelation Period Detection (Weight: 1.0):**
- Calculate autocorrelation of bit segment
- Look for peaks at expected periods (60 samples for 800 Hz, 30 samples for 1600 Hz)
- Require normalized correlation > 0.3 for confident detection

**Voting System:**
- Weight-based voting across all three methods
- FFT has double weight due to higher reliability
- Confidence = average confidence of winning votes

## How Binary Strip Decoding Currently Works

### Current Decoding Algorithm

The `read_binary_strip()` function in `shared_timecode_robust.py` (line 1338) works as follows:

```python
# 1. Extract the top 20 pixels of the frame
strip = frame[0:20, :]

# 2. Convert to grayscale
strip_gray = cv2.cvtColor(strip, cv2.COLOR_BGR2GRAY)

# 3. Calculate adaptive threshold
if strip_mean < 100 and strip_std > 20:
    threshold = strip_mean + (strip_std * 0.5)
else:
    threshold = 128

# 4. Divide width evenly into 32 blocks
block_width = width // 32  # = 22 pixels at 720 width

# 5. For each block, average ALL pixels in that region
for i in range(32):
    x_start = i * block_width
    x_end = x_start + block_width
    block = strip_gray[:, x_start:x_end]
    avg_intensity = np.mean(block)  # Average of entire 20x22 pixel region
    bit = '1' if avg_intensity > threshold else '0'
```

### Critical Problems with Current Decoding

**Problem 1: Assumes Blocks Are Exactly Where Expected**

The decoder divides the frame width evenly by 32 and assumes each block is exactly at position `i * block_width`. But VHS can introduce:
- Horizontal shift (entire image displaced left or right)
- Non-linear distortion (different shift at different vertical positions)
- Slight scaling changes

If the image shifts by even 10 pixels, bit boundaries are completely wrong.

**Problem 2: Averages Entire Block Area**

The code averages ALL pixels in the expected block region:
```python
avg_intensity = np.mean(block)  # Averages 20 × 22 = 440 pixels
```

This is problematic because:
- Block edges are blurry after VHS (gradients, not sharp transitions)
- Adjacent blocks bleed into each other
- The average includes transition zones which are ambiguous

**Problem 3: Black Background Contaminates Shifted Blocks**

The current encoding uses:
- **Black background** (0, 0, 0)
- **White blocks** for '1' (255, 255, 255)
- **Dark gray blocks** for '0' (64, 64, 64)

If the entire strip shifts horizontally:
```
Expected:   [BLACK][WHITE BLOCK][GRAY BLOCK][WHITE BLOCK]...
Actual:     [BLACK + partial WHITE][shifted WHITE + partial GRAY][shifted GRAY + partial WHITE]...
```

When averaging a region that's supposed to be "white block":
- If shifted left: includes some black background → average drops
- If shifted right: includes some of next block → average contaminated

**Black background is the worst choice** because it maximally contaminates white blocks (pulls average from 255 toward 0).

**Problem 4: No Sub-Block Sampling**

The code doesn't sample the CENTER of each block where the signal is cleanest. It averages the entire block including:
- Left edge (transition from previous block)
- Right edge (transition to next block)
- Top edge (possible head switching noise)
- Bottom edge (possible contamination from frame content below)

**Problem 5: Corner-Based Alignment Still Has Issues**

The `read_binary_strip_with_corners()` function (line 1466) attempts to use corner markers for alignment:

```python
# Find corners
top_left_red = min(red_corners, key=lambda p: p[0] + p[1])
top_right_blue = min(blue_corners, key=lambda p: -p[0] + p[1])

# Calculate strip boundaries from corners
strip_left = max(40, top_left_red[0] + 40)  # Hardcoded +40 offset!
strip_right = min(width - 40, top_right_blue[0] - 40)
```

Problems:
- **Hardcoded 40-pixel offset** from corner centroid - assumes corner detection is pixel-perfect
- Still divides resulting width evenly by 32
- Still averages entire block regions
- Corner detection itself may be inaccurate after VHS color bleeding
- No edge detection within the strip to find actual block boundaries

### Proposed Decoding Improvements

**Improvement 1: Neutral Background Color (Mid-Gray)**

Instead of black background, use **mid-gray (128, 128, 128)**:

```
Current encoding:
- Background: Black (0)
- '0' bit: Dark gray (64)
- '1' bit: White (255)

Problem: If white block shifts, black (0) gets averaged in → big drop in average

Proposed encoding:
- Background: Mid-gray (128)
- '0' bit: Dark (32) or Black (0)
- '1' bit: White (255)

Benefit: If white block shifts, gray (128) gets averaged in → smaller impact
         The background is "neutral" - between the two bit values
```

With mid-gray background:
- Shifted '1' blocks: average drops from 255 toward 128 (still well above threshold)
- Shifted '0' blocks: average rises from 32 toward 128 (less catastrophic)
- The background "splits the difference" rather than maximally contaminating one bit value

**Improvement 2: Center Sampling (Avoid Edges)**

Instead of averaging the entire block, sample only the CENTER:

```python
# Current: Average entire block (20 × 22 pixels)
avg_intensity = np.mean(block)

# Proposed: Sample center 50% of block
margin_x = block_width // 4  # Skip 25% on each side
margin_y = 5  # Skip 5 pixels top and bottom (of 20)
center_block = block[margin_y:-margin_y, margin_x:-margin_x]
avg_intensity = np.mean(center_block)
```

Benefits:
- Avoids transition zones at left/right edges
- Avoids head switching artifacts at top
- Samples where the bit signal is cleanest
- More tolerant of slight misalignment

**Improvement 3: Edge Detection for Block Boundary Discovery**

Instead of assuming blocks are at fixed positions, FIND the actual boundaries:

```python
# 1. Compute horizontal intensity profile (average each column)
profile = np.mean(strip_gray, axis=0)  # Shape: (width,)

# 2. Find transitions (where intensity changes significantly)
diff = np.abs(np.diff(profile))
transition_indices = np.where(diff > threshold)[0]

# 3. Use detected transitions as actual block boundaries
# (rather than assumed i * block_width positions)
```

Benefits:
- Discovers where blocks actually are after VHS shift
- Handles non-uniform distortion
- Can detect if strip is missing or corrupted (no clear transitions)

**Improvement 4: Correlation-Based Alignment**

Use the known pattern structure to find optimal alignment:

```python
# Generate expected pattern for frame N
expected_pattern = generate_expected_binary_pattern(candidate_frame_n)

# Slide expected pattern across actual strip and find best match
correlations = []
for offset in range(-max_offset, max_offset):
    correlation = compute_correlation(expected_pattern, actual_strip, offset)
    correlations.append((offset, correlation))

best_offset = max(correlations, key=lambda x: x[1])[0]
```

This is computationally expensive but very robust - it finds where the pattern actually is.

**Improvement 5: Use Corner Markers for Perspective Correction**

The corner markers (red top-left/bottom-right, blue top-right/bottom-left) can define a perspective transform:

```python
# Detect all four corners
src_points = [top_left, top_right, bottom_left, bottom_right]

# Define where they SHOULD be
dst_points = [(0, 0), (width, 0), (0, height), (width, height)]

# Compute and apply perspective transform
M = cv2.getPerspectiveTransform(src_points, dst_points)
corrected_frame = cv2.warpPerspective(frame, M, (width, height))

# Now decode from corrected frame (blocks are where expected)
```

Benefits:
- Corrects for rotation, scaling, and perspective distortion
- Aligns entire frame, not just the strip
- Block positions are now reliable

**Improvement 6: Per-Frame Calibration Using Known Bits**

If we reduce to 16-bit encoding, some bits could be KNOWN (calibration bits):

```
Proposed 16-bit structure:
- Bits 0-1: Always "10" (start marker / calibration)
- Bits 2-13: 12-bit frame number
- Bits 14-15: Always "01" (end marker / calibration)
```

The decoder first finds where bits 0-1 appear as "10" and where bits 14-15 appear as "01". This calibrates the threshold and alignment for THIS specific frame, then decodes the data bits.

## Identified Problems with VHS Playback

### 1. Visual Binary Strip Degradation

**Problem: Low Contrast After VHS Recording/Playback**
- VHS chroma bandwidth: ~400-500 kHz (significantly reduced from source)
- VHS luma bandwidth: ~3 MHz (acceptable but with noise)
- White pixels (255) compress to approximately 200-220
- Dark gray pixels (64) can shift to 80-100
- Result: Reduced contrast ratio from 4:1 to approximately 2:1

**Problem: Edge Blurring (PAL vs NTSC)**
- **NTSC:** ~240 horizontal lines effective resolution
- **PAL:** ~288 horizontal lines effective resolution (better, but still limited)
- At 720 source pixels, this means:
  - NTSC: 720/240 = 3:1 reduction, 20-pixel blocks become ~6-7 effective pixels
  - PAL: 720/288 = 2.5:1 reduction, 20-pixel blocks become ~8 effective pixels
- Block boundaries become gradients instead of sharp transitions
- Adjacent bits can "bleed" into each other
- **Note:** System must work reliably for both PAL and NTSC regions

**Problem: Noise and Interference**
- VHS SNR: approximately 42-46 dB
- Dropout artifacts create random white/black speckles
- Head switching noise can corrupt bottom of frame
- Tracking errors cause horizontal displacement

**Problem: Threshold Selection**
- Fixed threshold of 128 assumes clean white/black distinction
- After VHS degradation, optimal threshold varies per frame
- Current adaptive threshold (`mean + std * 0.5`) may not track variations

### 2. Audio FSK Degradation

**Problem: Frequency Response Limitations**
- VHS Hi-Fi audio: 20 Hz - 20 kHz (acceptable for FSK frequencies)
- VHS Linear audio: 100 Hz - 10 kHz with severe high-frequency rolloff
- If linear audio used, 1600 Hz signal significantly attenuated relative to 800 Hz

**Problem: Wow and Flutter**
- VHS wow/flutter: 0.005% to 0.02% (weighted)
- At 1600 Hz, flutter can shift frequency by 0.32 Hz (minimal impact)
- More concerning: instantaneous speed variations cause frequency modulation

**Problem: Tape Noise**
- VHS audio noise floor: approximately -50 to -60 dB
- At 60% signal amplitude, weak transitions may approach noise floor
- Bit boundaries (with fade envelopes) are most vulnerable

**Problem: Head Switching Noise**
- Occurs every ~16.7ms (60 Hz field rate for NTSC, 50 Hz for PAL)
- Can corrupt 1-2 audio bits per frame
- Current system has no mechanism to detect/correct this

### 3. Temporal Alignment Issues

**Problem: Frame Boundary Drift**
- VHS playback speed varies with temperature, tape tension
- Frame-accurate boundaries in source may drift over time
- Current deterministic decoder assumes exact frame boundaries

**Problem: Audio/Video Desynchronization**
- VHS audio and video recorded on different tape tracks
- Different head drums and path lengths
- Inherent timing offset varies by VCR and tape condition

### 4. Sync Direction Ambiguity

**Problem: Which Device Needs Adjustment?**

Previous sync methods using simple pulse detection (1 second on/off patterns) suffered from a fundamental ambiguity: the system could detect *that* audio and video were offset, but couldn't reliably determine *which direction* the offset was in - i.e., whether audio was ahead of video or video was ahead of audio.

This occurred because:
- A sync pulse looks the same whether you're measuring from the start or end
- Without absolute timing reference, the system might "snap" to the wrong edge
- Result: Sometimes applied correction in the wrong direction, making sync worse

**Why Absolute Timecode Solves This:**
- Each frame has a unique, sequential identifier (frame 0, 1, 2, 3...)
- If video shows frame 100 when audio encodes frame 102, we know definitively:
  - Audio is 2 frames ahead of video
  - Audio needs to be delayed (or video advanced)
- No ambiguity about direction - the frame numbers tell the complete story
- This is the core reason the absolute timecode approach was developed

### 5. Capture System Startup Delay

**Problem: Missing Beginning of Home Videos**

The current Domesday Duplicator capture system has approximately 1 second of startup delay before recording begins. This means:
- The first second of any VHS playback is not captured
- For home videos, this often contains important content (titles, first moments)
- The delay is a combination of USB initialization, buffer allocation, and file setup

**Implications for Calibration:**
- If startup delay improves in future code versions, recalibration is needed
- The timecode system provides a robust way to measure new delay values
- Workflow: burn calibration DVD → record to VHS → capture → measure offset
- Can be repeated whenever capture code changes to verify timing

### 6. Pre-Processing Requirements: TBC and Clock Sync

**Critical Workflow Consideration:**

Before comparing video and audio timecodes to calculate offset, the captured data must be processed through the standard VHS decode pipeline:

**Video: Time Base Correction (TBC)**
- Raw VHS RF capture has timing instability (jitter, speed variation)
- vhs-decode applies TBC to stabilize frame timing
- Output video has consistent, predictable frame boundaries
- **Timecode comparison must use TBC-corrected video, not raw capture**

**Audio: Clock Synchronization**
- VHS audio capture may have clock drift relative to video
- The toolkit's clock sync process adjusts audio timing
- Aligns audio sample rate to match video timing reference
- **Timecode comparison must use clock-synced audio, not raw capture**

**Correct Processing Order:**
```
1. Raw RF capture (video + audio)
2. vhs-decode → TBC-corrected video (.tbc)
3. Audio clock sync adjustment
4. Export TBC to viewable video
5. THEN compare video/audio timecodes for offset measurement
```

**Why This Matters:**
- Without TBC, video frame boundaries are inconsistent
- Without clock sync, audio timing drifts over the capture duration
- Measuring offset from raw capture would include these instabilities
- After TBC and clock sync, remaining offset is the true A/V delay to correct

This step may have been overlooked in previous calibration attempts - the timecode comparison should happen on the *processed* output, not the raw capture.

### 7. Multi-Point Sampling Strategy

**Problem: Single-Point Measurement Unreliability**

Measuring offset at only one point in the capture is unreliable because:
- Local corruption might affect that specific frame
- Transient timing variations exist even after TBC
- A single bad measurement gives wrong calibration

**Proposed Approach: Multi-Point Averaging**

```
1. Decode timecodes at multiple points throughout the capture
   - Beginning (after initial stabilization, ~5 seconds in)
   - Middle (~15 seconds)
   - End (~25 seconds)
   - Or sample every N frames throughout

2. Calculate offset at each sample point:
   offset[i] = video_frame_time[i] - audio_frame_time[i]

3. Validate consistency:
   - After TBC and clock sync, offsets should be very similar
   - Large variation between sample points indicates a problem
   - Standard deviation should be < 1 frame (40ms for PAL)

4. Average the offsets:
   final_offset = mean(offset[])

5. Report confidence based on consistency:
   - Low std dev = high confidence
   - High std dev = flag for manual review
```

**Expected Behavior After TBC/Clock Sync:**
- All sample points should show nearly identical offset
- If they don't, something is wrong with:
  - The TBC processing
  - The clock sync
  - The timecode decoding
  - Or the source material itself

## Proposed Optimizations

### Priority 1: Visual Binary Strip Improvements

**1.1 Larger Binary Blocks**

**Visual Layout Math:**
```
Screen width:       720 pixels
Corner markers:     40 pixels each side = 80 pixels total
Available width:    640 pixels

Current (32 bits):  640 ÷ 32 = 20 pixels per block  ← Too small after VHS blur
Proposed (16 bits): 640 ÷ 16 = 40 pixels per block  ← Double width, much better
Alternative (20):   640 ÷ 20 = 32 pixels per block  ← Still reasonable
```

**Recommended 16-bit structure (Option C from analysis):**
```
- Bits 0-1:   "10" (start marker + validation)
- Bits 2-13:  12-bit frame number
- Bits 14-15: "01" (end marker + validation)
```

- 12-bit frame number = 4096 frames
- At 25fps (PAL) = 164 seconds = **2 minutes 44 seconds**
- At 29.97fps (NTSC) = 137 seconds = **2 minutes 17 seconds**
- More than sufficient for 30-second calibration windows

The start/end markers ("10" and "01") provide error detection without a separate checksum - if either marker is wrong, the frame is rejected. For calibration with multi-point averaging, this is adequate.

**With Vertical Triplication:**
- 3 rows of the SAME 16 bits stacked vertically
- Each bit becomes a 40-pixel wide × 60-pixel tall block (20 pixels × 3 rows)
- Total strip height: 60 pixels (vs current 20 pixels)
- Majority voting across rows handles single-row dropouts

**1.2 Color-Based Bit Encoding**

Instead of grayscale intensity (white vs gray), use color channels (red vs blue):
- '1': Pure red (0, 0, 255 BGR)
- '0': Pure blue (255, 0, 0 BGR)

**Why Color is More Robust Than Grayscale (Counterintuitively):**

VHS records video as separate luma (brightness) and chroma (color) signals:
- **Luma** is recorded directly with ~3 MHz bandwidth
- **Chroma** is downconverted to ~629 kHz carrier and recorded separately

**The problem with white/gray encoding:**
- White (255,255,255) and gray (64,64,64) differ ONLY in brightness (luma)
- Both have zero color saturation - they're on the same point of the color spectrum
- VHS luma signal is subject to: noise, level drift, head switching artifacts, AGC variations
- A noise spike can easily push gray intensity toward white range or vice versa
- The discrimination relies entirely on one signal (luma)

**Why red/blue is more robust:**
- Red and blue are on OPPOSITE ends of the chroma spectrum
- They are maximally different in color space
- Even with VHS chroma bandwidth limitations (~400 kHz), red vs blue is a large, distinguishable difference
- To misread a bit, the COLOR would have to flip entirely - not just brightness shifting
- You decode by comparing `pixel[2]` (red channel) vs `pixel[0]` (blue channel)
- Whichever channel is higher determines the bit value

**Potential Combined Approach:**
Since VHS records luma and chroma separately, we could use BOTH as independent channels:
- Encode bit in color (red vs blue) AND in brightness (white vs black)
- Decode both independently
- Vote between them - if they agree, high confidence; if they disagree, flag for review
- This provides redundancy across the two signal paths

**Caveat:** VHS chroma has its own artifacts (color bleeding, rainbow fringing at edges). Testing with actual VHS captures is essential to validate this approach.

**1.3 Vertical Redundancy**
```
Current:  20 pixel tall strip (single row)
Proposed: 60 pixel tall strip (3 redundant rows)
```
- Each bit repeated 3 times vertically
- Majority voting across rows
- Tolerates dropout lines affecting 1-2 rows

**1.4 Adaptive Thresholding**
```python
# Current approach
threshold = strip_mean + (strip_std * 0.5) if strip_mean < 100 else 128

# Proposed approach
# Use Otsu's method for optimal threshold selection
_, binary_strip = cv2.threshold(strip_gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

# Or use local adaptive thresholding
binary_strip = cv2.adaptiveThreshold(strip_gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                      cv2.THRESH_BINARY, 11, 2)
```

### Priority 2: Audio FSK Improvements

**2.1 Lower Frequencies for Better VHS Compatibility**
```
Current:  800 Hz / 1600 Hz (2:1 ratio)
Proposed: 400 Hz / 800 Hz  (2:1 ratio, both well within linear audio range)
```
- Both frequencies well within VHS linear audio passband
- Greater amplitude consistency between tones
- Less affected by tape speed variations

**2.2 Stronger Error Correction**
```
Current:  8-bit XOR checksum (detects errors but cannot correct)
Proposed: Hamming(7,4) encoding for each nibble
```
- Every 4 data bits encoded as 7 bits
- Can correct 1-bit errors per block
- 32 data bits becomes 56 encoded bits
- Reduces effective data rate but increases reliability

**2.3 Pilot Tone Synchronization**
```
Proposed structure per frame:
- 10% of frame: 1200 Hz pilot tone (sync signal)
- 5% of frame: silence (separator)
- 80% of frame: FSK data
- 5% of frame: silence (separator)
```
- Pilot tone allows decoder to find exact frame start
- Known frequency enables timing drift compensation
- Silence separators improve bit detection at boundaries

**2.4 Video Sync Frame Equivalent (Visual Pilot)**

Just as audio benefits from a pilot tone, video benefits from periodic sync frames:

```
Proposed video structure:
- Every 25 frames (1 second for PAL): Insert distinctive sync frame
- Sync frame pattern: Alternating vertical bars (high contrast, survives VHS blur)
- Or: Specific color sequence that's easily machine-detectable
```

**Benefits of Video Sync Frames:**
- Decoder first scans entire video for sync frames to establish timing grid
- If frame boundaries drift, next sync frame re-establishes alignment
- Can detect dropped frames (gap between expected sync frame positions)
- Provides sanity check: if sync frames aren't at expected ~1 second intervals, capture has problems
- Works as "chapter markers" for the timecode data between them

**Implementation:**
- Sync frame should be visually distinct from timecode frames
- Could use full-screen alternating bars (high frequency = survives blur poorly but detectable)
- Or use specific corner marker colors different from normal frames
- Sync frames don't encode data - they just mark "this is frame N*25"

**2.5 Machine-Readable Lead-In Structure**

VHS tapes have issues at the start (tracking settling, head alignment, tape stretch). The calibration video needs a substantial lead-in that is **machine-readable** so the decoder knows what's happening.

**Proposed Calibration Video Structure:**

```
SECTION 1: LEADER TONE (10 seconds) - Machine detectable
┌─────────────────────────────────────────────────────────────────┐
│  Video: Distinctive pattern (e.g., diagonal stripes or specific │
│         color that's NOT used elsewhere in the calibration)     │
│  Audio: Continuous 1kHz tone (or specific FSK pattern)          │
│  Binary strip: All bits = "1" (0xFFFF) - easily detectable      │
│                                                                 │
│  Purpose: Decoder detects this pattern and knows:               │
│           "This is calibration content, leader section"         │
│           Allows VCR tracking/AGC to settle                     │
└─────────────────────────────────────────────────────────────────┘

SECTION 2: BINARY COUNTDOWN (5 seconds) - Machine readable countdown
┌─────────────────────────────────────────────────────────────────┐
│  Video: Large countdown number displayed (5, 4, 3, 2, 1)        │
│  Audio: Beep each second (different tone from leader)           │
│  Binary strip: Encodes countdown value in machine-readable form │
│                                                                 │
│  Frame encoding during countdown:                               │
│    Bits 0-1:   "11" (countdown marker - different from "10")    │
│    Bits 2-5:   Countdown value (5, 4, 3, 2, 1, 0)               │
│    Bits 6-15:  Frames until timecode starts (e.g., 125, 124...) │
│                                                                 │
│  Purpose: Decoder reads countdown and knows exactly when        │
│           timecode section will begin. Can prepare/synchronize. │
└─────────────────────────────────────────────────────────────────┘

SECTION 3: SEPARATOR (1 second)
┌─────────────────────────────────────────────────────────────────┐
│  Video: Black screen                                            │
│  Audio: Silence                                                 │
│  Binary strip: All bits = "0" (0x0000)                          │
│                                                                 │
│  Purpose: Clear transition marker between countdown and         │
│           timecode. Decoder sees all-zeros = "timecode next"    │
└─────────────────────────────────────────────────────────────────┘

SECTION 4: TIMECODE (30 seconds) - The actual calibration data
┌─────────────────────────────────────────────────────────────────┐
│  Video: Frame number display + binary strip                     │
│  Audio: FSK-encoded frame numbers                               │
│  Binary strip: "10" + 12-bit frame + "01" structure             │
│                                                                 │
│  Purpose: Frame-accurate timecode for A/V offset measurement    │
└─────────────────────────────────────────────────────────────────┘

SECTION 5: SEPARATOR (1 second)
┌─────────────────────────────────────────────────────────────────┐
│  Video: Black screen                                            │
│  Audio: Silence                                                 │
│  Binary strip: All bits = "0" (0x0000)                          │
└─────────────────────────────────────────────────────────────────┘

SECTION 6: BINARY COUNT-UP / LEAD-OUT WARNING (5 seconds)
┌─────────────────────────────────────────────────────────────────┐
│  Video: "END IN 5, 4, 3, 2, 1" countdown display                │
│  Audio: Beep each second (same as lead-in countdown)            │
│  Binary strip: Encodes count-up in machine-readable form        │
│                                                                 │
│  Frame encoding during lead-out:                                │
│    Bits 0-1:   "00" (lead-out marker - different from others)   │
│    Bits 2-5:   Count-up value (1, 2, 3, 4, 5)                   │
│    Bits 6-15:  Frames since timecode ended (1, 2, 3...)         │
│                                                                 │
│  Purpose: Decoder knows timecode section is complete.           │
│           Can finalize calculations before tape issues occur.   │
└─────────────────────────────────────────────────────────────────┘

SECTION 7: TAIL TONE (10 seconds)
┌─────────────────────────────────────────────────────────────────┐
│  Video: Distinctive pattern (same as leader, or inverse)        │
│  Audio: Continuous 1kHz tone (same as leader)                   │
│  Binary strip: All bits = "1" (0xFFFF) - same as leader         │
│                                                                 │
│  Purpose: Buffer before tape end or next loop iteration.        │
│           Decoder knows calibration cycle is complete.          │
└─────────────────────────────────────────────────────────────────┘

SECTION 8: REPEAT (Loop back to Section 2 for continuous calibration)
```

**Total Duration Per Cycle:**
```
Section 1: Leader tone        10 seconds
Section 2: Countdown           5 seconds
Section 3: Separator           1 second
Section 4: Timecode           30 seconds
Section 5: Separator           1 second
Section 6: Count-up            5 seconds
Section 7: Tail tone          10 seconds
─────────────────────────────────────────
TOTAL:                        62 seconds per cycle

At 25fps (PAL):  62 × 25 = 1,550 frames per cycle
At 29.97fps:     62 × 29.97 = 1,858 frames per cycle

With 12-bit frame numbers (4,096 max), we can encode:
- 2.6 complete cycles at PAL
- 2.2 complete cycles at NTSC

For looping, frame numbers can reset at each cycle start,
or continue incrementing across cycles (both work within range).
```

**Decoder State Machine:**

```
State: SEARCHING
  → Detect all-ones (0xFFFF) pattern → State: IN_LEADER

State: IN_LEADER
  → Detect "11" prefix (countdown marker) → State: IN_COUNTDOWN
  → (Can also enter from CYCLE_COMPLETE when looping)

State: IN_COUNTDOWN
  → Read countdown value, prepare for timecode
  → Detect all-zeros (0x0000) → State: READY_FOR_TIMECODE

State: READY_FOR_TIMECODE
  → Detect "10" prefix (timecode marker) → State: READING_TIMECODE

State: READING_TIMECODE
  → Decode frame numbers, correlate audio/video
  → Detect all-zeros (0x0000) → State: TIMECODE_COMPLETE

State: TIMECODE_COMPLETE
  → Detect "00" prefix (lead-out marker) → State: IN_LEADOUT
  → Finalize offset calculations for this cycle

State: IN_LEADOUT
  → Read count-up value, prepare for cycle end
  → Detect all-ones (0xFFFF) → State: CYCLE_COMPLETE

State: CYCLE_COMPLETE
  → Report results for this cycle
  → Detect "11" prefix → State: IN_COUNTDOWN (next cycle)
  → Or exit if sufficient data collected
```

**Why This Matters:**

1. **No guessing** - Decoder knows exactly what section it's in
2. **Handles tape start issues** - 15+ seconds of lead-in before critical data
3. **Handles tape end issues** - 15+ seconds of lead-out after critical data
4. **Synchronization** - Countdown tells decoder precisely when timecode begins
5. **Clean completion** - Lead-out confirms timecode section ended normally
6. **Error recovery** - If decoder loses track, it can wait for next all-zeros separator
7. **Human readable too** - Visual countdown/count-up helps manual verification
8. **Multiple cycles** - Can average results across multiple 62-second cycles

**Marker Summary:**
```
Binary strip first two bits determine frame type:

  Prefix "11" + data    = Countdown frame (lead-in)
  Prefix "10" + data    = Timecode frame (calibration data)
  Prefix "00" + data    = Count-up frame (lead-out)

Special patterns (all 16 bits):
  0xFFFF (all ones)     = Leader/tail tone section
  0x0000 (all zeros)    = Separator / transition marker
```

**Symmetrical Structure:**
```
LEAD-IN:                          LEAD-OUT:
  Leader (0xFFFF)     10s           Count-up ("00")    5s
  Countdown ("11")     5s           Tail (0xFFFF)     10s
  Separator (0x0000)   1s
                    ↓
              TIMECODE ("10")
                 30 seconds
                    ↓
              Separator (0x0000)
                    ↓
                 LEAD-OUT
```

**2.6 Differential Encoding**
Instead of absolute frequencies:
```
'0': Same frequency as previous bit
'1': Different frequency from previous bit
```
- Eliminates sensitivity to absolute frequency shifts
- Wow/flutter affects both frequencies equally
- Only transitions matter, not absolute values

### Priority 3: Decoding Algorithm Improvements

**3.1 Spectrogram-Based Decoding**

The current system decodes each bit in isolation by splitting the audio into fixed segments and analyzing each separately. This has fundamental limitations that spectrogram-based decoding addresses.

**Current Per-Bit FFT Approach:**
```
Frame audio → Split into 32 fixed segments → FFT each segment → Decide each bit independently
```

**Problems with Per-Bit FFT:**
1. **Assumes exact bit boundaries** - If VHS speed varies even slightly, bit boundaries shift
2. **Short analysis window** - 60 samples gives poor frequency resolution (~800Hz resolution)
3. **No context** - Each bit decoded without knowledge of neighbors
4. **Binary decision** - Must choose 0 or 1 with no uncertainty tracking

**Spectrogram Approach:**
```python
# Instead of per-bit FFT, use sliding spectrogram
from scipy.signal import spectrogram
f, t, Sxx = spectrogram(frame_audio, fs=48000, nperseg=256, noverlap=128)

# Track 800 Hz and 1600 Hz bins over time
f0_power = Sxx[np.argmin(np.abs(f - 800)), :]
f1_power = Sxx[np.argmin(np.abs(f - 1600)), :]

# Find bit transitions from power ratio changes
bit_transitions = find_transitions(f0_power, f1_power)
```

**Key Benefits of Spectrogram Decoding:**

1. **Continuous frequency tracking** - Instead of asking "is this segment 800Hz or 1600Hz?", you track "when does the dominant frequency change?" This naturally handles timing uncertainty.

2. **Better frequency resolution** - Uses 256-sample FFT windows (vs 60), giving ~187Hz resolution instead of ~800Hz. The 800Hz and 1600Hz tones become clearly separated peaks.

3. **Overlapping windows** - 50% overlap means each moment in time is analyzed multiple times from different perspectives, reducing noise impact.

4. **Transition-based decoding** - You're looking for *changes* in the frequency content, not absolute values at fixed positions. This is inherently more robust to timing drift.

5. **Visual debugging** - A spectrogram is literally a picture of frequency vs time. You can visually inspect:
   - Where each tone appears
   - How clean the transitions are
   - Where corruption or dropouts occur
   - Whether the bit rate is consistent

**Conceptual Difference:**
```
Per-bit FFT asks:  "Samples 0-60 = ?, samples 60-120 = ?, samples 120-180 = ?, ..."
Spectrogram asks:  "800Hz dominant from sample 0-58, then 1600Hz from 58-125, then 800Hz..."
```

The spectrogram naturally discovers where the transitions actually are, rather than assuming they're at predetermined positions.

**3.2 Phase-Locked Loop Tracking**
- Track instantaneous frequency using PLL
- Adapts to wow/flutter automatically
- Provides continuous frequency estimate

**3.3 Viterbi Decoding**
- Model FSK as finite state machine
- Use Viterbi algorithm for optimal bit sequence
- Naturally handles uncertainty and noise
- Can incorporate frame number constraints (sequential, limited range)

### Priority 4: Structural Changes

**4.1 Longer Bit Durations and 16-Bit Encoding**

```
Current 32-bit encoding:
- 24-bit frame number (supports 16.7 million frames = 186 hours at 25fps)
- 8-bit checksum
- 32 bits × 60 samples = 1920 samples per frame (exactly one PAL frame)
- 60 samples per bit = 1.25 ms per bit

Proposed 16-bit encoding:
- 12-bit frame number (supports 4096 frames = 164 seconds at 25fps)
- 4-bit CRC checksum
- 16 bits × 120 samples = 1920 samples per frame (same total)
- 120 samples per bit = 2.5 ms per bit
```

**Benefits of 16-Bit Encoding:**

1. **Double bit duration in audio (120 samples vs 60)**
   - More cycles of the FSK tone fit within each bit
   - At 800Hz with 60 samples: only ~1 cycle per bit (hard to identify frequency)
   - At 800Hz with 120 samples: ~2 cycles per bit (much clearer frequency detection)
   - Better frequency resolution in FFT: 400Hz resolution vs 800Hz resolution

2. **Double visual block width (40 pixels vs 20)**
   - Current 20-pixel blocks blur to ~6-8 effective pixels after VHS
   - Proposed 40-pixel blocks blur to ~12-16 effective pixels
   - Still blurry, but much more distinguishable
   - Gradient transitions at block edges have less relative impact

3. **Sufficient range for calibration use case**
   - The timecode test window is 30 seconds
   - 12 bits supports 4096 frames = 164 seconds at 25fps
   - This is more than 5× the required range
   - We don't need to encode hours of content for calibration

4. **Better signal-to-noise ratio per bit**
   - Twice as many audio samples per bit
   - Averaging over more samples improves SNR by √2 ≈ 1.4× (3 dB)
   - Twice as many video pixels per bit
   - Spatial averaging over larger blocks reduces impact of individual noise pixels

5. **Simpler checksum validation**
   - 4-bit CRC is faster to compute and verify
   - With only 12 data bits, error detection is statistically adequate
   - Could use CRC-4 polynomial for single-bit error detection

**The Trade-off:**
- Maximum encodable duration: ~2.7 minutes of unique frame numbers
- For 30-second calibration tests repeated in a loop, this is perfectly adequate
- If longer encoding needed in future, could switch between modes based on use case

**4.2 Repeated Transmission**
```
Proposed: Transmit frame number 3 times per frame
- First transmission: normal
- Second transmission: bit-inverted
- Third transmission: normal
```
- Majority voting across transmissions
- Bit inversion catches systematic errors
- Increases reliability at cost of data rate

**4.3 Known Sequence Markers**
```
Proposed frame structure:
- 4 bits: Start marker (1010)
- 12 bits: Frame number
- 4 bits: Checksum
- 4 bits: End marker (0101)
```
- Start/end markers enable frame synchronization
- Alternating patterns survive most corruption
- Can detect frame boundary with marker correlation

## Recommended Implementation Priority

### Phase 1: Quick Wins (Low Effort, High Impact)

1. **Implement Otsu's thresholding** for binary strip reading
2. **Add vertical redundancy** (3 rows instead of 1)
3. **Lower FSK frequencies** to 400/800 Hz
4. **Increase bit duration** to 120 samples

### Phase 2: Medium Effort Improvements

5. **Color-based bit encoding** (red/blue instead of white/gray)
6. **Pilot tone synchronization** for audio
7. **Spectrogram-based decoding** instead of per-bit FFT
8. **Reduce to 16-bit encoding** with CRC

### Phase 3: Advanced Solutions

9. **Viterbi decoding** for optimal bit sequence recovery
10. **Differential encoding** for frequency independence
11. **Hamming error correction** for bit error recovery
12. **Repeated transmission** with voting

## Testing Recommendations

### Test Material Preparation

1. **Generate test videos at multiple quality levels:**
   - Original MP4 (baseline - validates decoder works correctly)
   - Simulated VHS degradation (blur, noise, contrast reduction)
   - Actual VHS recording and playback (the real test)

2. **Calibration DVD Workflow:**
   - Burn timecode test pattern to DVD
   - Record DVD to VHS tape
   - Can re-record same DVD when testing code changes
   - Provides consistent, repeatable test source

### Processing Before Analysis

**Critical: Apply TBC and Clock Sync Before Timecode Comparison**

```
1. Capture raw RF from VHS playback
2. Run vhs-decode to produce TBC-corrected video
3. Apply clock sync to audio
4. Export video to viewable format
5. THEN run timecode analysis on processed output
```

This ensures you're measuring the true A/V offset, not timing instabilities that TBC/clock sync would correct anyway.

### Metrics to Measure

1. **Per-component success rate:**
   - Binary strip readability percentage (frames successfully decoded / total frames)
   - FSK audio decode success rate
   - Checksum validation rate
   - Corner marker detection rate

2. **Multi-point offset consistency:**
   - Sample offsets at 5+ points throughout capture
   - Calculate standard deviation of offsets
   - After TBC/clock sync, std dev should be < 1 frame (40ms PAL)
   - High std dev indicates processing problem

3. **Confidence metrics:**
   - Average bit confidence from voting system
   - Percentage of bits decoded by multiple methods agreeing
   - Distribution of confidence scores

### Parameter Variations

1. **Vary encoding parameters systematically:**
   - Block size (16, 24, 32 bits)
   - FSK frequencies (400/800, 600/1200, 800/1600)
   - Bit duration (60, 90, 120 samples)
   - Color encoding (white/gray vs red/blue)

2. **Test with different VCRs:**
   - Consumer-grade VHS
   - S-VHS (higher bandwidth)
   - Hi-Fi vs Linear audio
   - Different head conditions/ages

3. **Test edge cases:**
   - Beginning of tape (head alignment settling)
   - End of tape (tension variations)
   - After pause/resume
   - Different tape brands/ages

## Conclusion

The current robust timecode system uses sound engineering principles (wide frequency separation, multiple detection methods, checksum validation) but may be optimized for conditions that don't match real VHS degradation. The primary issues are:

1. **Visual encoding assumes higher resolution** than VHS can reliably reproduce (both PAL and NTSC)
2. **Audio frequencies may be affected** by VHS linear audio rolloff
3. **Bit durations are short** relative to VHS timing variations
4. **No redundancy mechanism** to survive localized corruption
5. **Previous testing may have skipped TBC/clock sync** - comparing raw capture instead of processed output

The proposed optimizations prioritize:
- Larger visual blocks with color encoding (red/blue using chroma separation)
- Lower audio frequencies with longer bit durations (16-bit encoding)
- Pilot tones and sync frames for timing recovery
- Spectrogram-based decoding that tracks frequency transitions rather than assuming fixed boundaries
- Multi-point sampling with averaging for robust offset measurement
- Redundancy through repetition and error correction

**Critical Workflow Insight:**

The timecode comparison must happen on **processed** output (after TBC and clock sync), not raw capture. This may explain previous calibration failures - the measured offset included timing instabilities that the decode pipeline would correct anyway. The remaining offset after TBC/clock sync is the true A/V delay that needs correction.

**Calibration Sustainability:**

Once working, the system enables:
- Repeatable calibration using DVD→VHS→Capture workflow
- Re-calibration when capture code changes (e.g., startup delay improvements)
- Confidence validation through multi-point offset consistency
- Objective measurement replacing subjective "does it look synced?" evaluation

Implementation should proceed incrementally, measuring improvement at each step against actual VHS capture data processed through the complete decode pipeline.
