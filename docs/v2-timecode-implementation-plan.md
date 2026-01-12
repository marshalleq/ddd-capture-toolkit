# Implementation Plan: Robust Timecode System Improvements

## Overview

Implement the improvements documented in `docs/robust-timecode-analysis.md` to make the VHS timecode calibration system actually work with real VHS captures.

## Files to Modify

### Primary Files
1. `tools/timecode-generator/shared_timecode_robust.py` - Base class (encoding/decoding)
2. `tools/timecode-generator/vhs_timecode_generator.py` - Video/audio generation
3. `tools/timecode-generator/vhs_timecode_analyzer.py` - Analysis/decoding
4. `tools/timecode-generator/vhs_pattern_generator.py` - Pattern structure

### Secondary Files
5. `tools/validate_mp4_timecode.py` - Update for new encoding
6. `ddd_main_menu.py` - Update menu descriptions if needed

---

## Phase 1: Encoding Changes (Generator)

### 1.1 Update Encoding Parameters in `shared_timecode_robust.py`

**Location:** Lines 23-73

**Changes:**
```python
# OLD
self.freq_0 = 800
self.freq_1 = 1600
self.bits_per_frame = 32
self.samples_per_bit = self.samples_per_frame // 32  # ~60

# NEW
self.freq_0 = 400   # Lower for better VHS linear audio compatibility
self.freq_1 = 800   # 2:1 ratio maintained
self.bits_per_frame = 16
self.samples_per_bit = self.samples_per_frame // 16  # ~120
self.freq_0_range = (300, 500)   # Updated detection ranges
self.freq_1_range = (650, 950)
```

### 1.2 Update 16-bit Frame Encoding in `shared_timecode_robust.py`

**Location:** `generate_robust_fsk_audio()` ~line 144

**Changes:**
- Encode frame number as 12 bits (not 24)
- Add "10" prefix and "01" suffix
- Remove separate checksum (markers provide validation)

```python
def generate_robust_fsk_audio(self, frame_number, frame_type='timecode'):
    """
    frame_type: 'leader', 'countdown', 'timecode', 'leadout', 'separator'
    """
    if frame_type == 'leader':
        bits = '1111111111111111'  # 0xFFFF
    elif frame_type == 'separator':
        bits = '0000000000000000'  # 0x0000
    elif frame_type == 'countdown':
        # "11" + 4-bit countdown + 10-bit frames-until-start
        countdown_val = frame_number  # 5,4,3,2,1
        frames_remaining = ...
        bits = f'11{countdown_val:04b}{frames_remaining:010b}'
    elif frame_type == 'leadout':
        # "00" + 4-bit count-up + 10-bit frames-since-end
        bits = f'00{count_up:04b}{frames_since:010b}'
    else:  # timecode
        # "10" + 12-bit frame number + "01"
        bits = f'10{frame_number:012b}01'
    # ... generate FSK tones
```

### 1.3 Update Visual Binary Strip in `vhs_timecode_generator.py`

**Location:** `_add_sync_patterns()` ~line 87

**Changes:**
- 16 blocks instead of 32 (40 pixels each)
- 3 vertical rows (60 pixels total height)
- Color encoding: Red for '1', Blue for '0'
- Mid-gray background (128) instead of black (0)

```python
def _add_sync_patterns(self, frame, frame_number, frame_type='timecode'):
    # Get 16-bit pattern based on frame_type
    bits = self._get_bit_pattern(frame_number, frame_type)

    # Visual parameters
    strip_height = 60  # 3 rows of 20 pixels
    block_width = (self.width - 80) // 16  # ~40 pixels

    # Fill background with mid-gray (128)
    frame[0:strip_height, 40:self.width-40] = (128, 128, 128)

    # Draw each bit as colored block (3 vertical rows)
    for i, bit in enumerate(bits):
        x_start = 40 + (i * block_width)
        x_end = x_start + block_width

        # Red (BGR: 0,0,255) for '1', Blue (BGR: 255,0,0) for '0'
        color = (0, 0, 255) if bit == '1' else (255, 0, 0)

        # Draw in all 3 rows
        for row in range(3):
            y_start = row * 20
            y_end = y_start + 20
            cv2.rectangle(frame, (x_start, y_start), (x_end, y_end), color, -1)
```

### 1.4 Create Lead-In/Lead-Out Structure in `vhs_pattern_generator.py`

**Location:** Complete rewrite of cycle structure

**New structure (62 seconds per cycle):**
```
Section 1: Leader (0xFFFF)      - 10 seconds (250 frames PAL)
Section 2: Countdown ("11")     - 5 seconds (125 frames)
Section 3: Separator (0x0000)   - 1 second (25 frames)
Section 4: Timecode ("10")      - 30 seconds (750 frames)
Section 5: Separator (0x0000)   - 1 second (25 frames)
Section 6: Count-up ("00")      - 5 seconds (125 frames)
Section 7: Tail (0xFFFF)        - 10 seconds (250 frames)
```

---

## Phase 2: Decoding Changes (Analyzer)

### 2.1 Update Decoding Parameters in `shared_timecode_robust.py`

**Location:** Class attributes and detection ranges

**Changes:**
- Update frequency detection ranges for 400Hz/800Hz
- Update bits_per_frame to 16
- Update samples_per_bit to 120

### 2.2 Implement Center Sampling with Confidence Reporting in `read_binary_strip()`

**Location:** `shared_timecode_robust.py` ~line 1338

**Design Principle:** One robust algorithm with confidence reporting - NO silent fallbacks. If detection confidence is low, report it explicitly rather than silently degrading to a different algorithm.

**Changes:**
```python
def read_binary_strip(self, frame):
    """
    Returns: (bits: str, confidences: list[float], overall_confidence: float)
    """
    # Extract 60-pixel strip (3 rows)
    strip = frame[0:60, :]

    bits = []
    confidences = []
    block_width = (width - 80) // 16

    for i in range(16):
        x_start = 40 + (i * block_width)
        x_end = x_start + block_width

        # CENTER SAMPLING: Skip 25% on each side horizontally
        margin_x = block_width // 4
        center_x_start = x_start + margin_x
        center_x_end = x_end - margin_x

        # Sample all 3 rows and vote (with confidence per row)
        row_results = []
        for row in range(3):
            # Skip 5 pixels top/bottom of each 20-pixel row
            y_start = row * 20 + 5
            y_end = y_start + 10
            center_block = frame[y_start:y_end, center_x_start:center_x_end]

            # Color-based detection: compare red vs blue channels
            red_avg = np.mean(center_block[:, :, 2])
            blue_avg = np.mean(center_block[:, :, 0])

            # Calculate confidence based on separation
            separation = abs(red_avg - blue_avg)
            max_possible = 255  # Maximum possible separation
            row_confidence = separation / max_possible

            row_bit = '1' if red_avg > blue_avg else '0'
            row_results.append((row_bit, row_confidence))

        # Majority vote across 3 rows
        ones = sum(1 for b, c in row_results if b == '1')
        bit = '1' if ones >= 2 else '0'

        # Bit confidence = average of agreeing rows' confidences
        agreeing_confidences = [c for b, c in row_results if b == bit]
        bit_confidence = np.mean(agreeing_confidences)

        bits.append(bit)
        confidences.append(bit_confidence)

    # Overall frame confidence
    overall_confidence = np.mean(confidences)

    return ''.join(bits), confidences, overall_confidence

def decode_frame_with_validation(self, frame):
    """
    Decode frame and validate - fail explicitly if confidence too low.
    """
    bits, confidences, overall_confidence = self.read_binary_strip(frame)

    # Minimum confidence threshold
    MIN_CONFIDENCE = 0.15  # 15% color separation required

    if overall_confidence < MIN_CONFIDENCE:
        # FAIL EXPLICITLY - don't silently degrade
        return None, overall_confidence, "LOW_CONFIDENCE"

    # Check for low-confidence individual bits
    low_conf_bits = sum(1 for c in confidences if c < MIN_CONFIDENCE)
    if low_conf_bits > 2:  # Allow up to 2 uncertain bits
        return None, overall_confidence, f"TOO_MANY_UNCERTAIN_BITS:{low_conf_bits}"

    # Validate markers
    if bits[:2] != '10' or bits[14:16] != '01':
        return None, overall_confidence, "INVALID_MARKERS"

    # Extract frame number
    frame_number = int(bits[2:14], 2)
    return frame_number, overall_confidence, "OK"
```

**Key Design Points:**
- Single algorithm - no fallbacks
- Confidence reported for every bit and overall frame
- Explicit failure with reason when confidence is too low
- Multi-point averaging in the calibration workflow handles occasional failures

### 2.4 Implement Perspective Correction Using Corners

**Location:** New method in `shared_timecode_robust.py`

```python
def correct_frame_perspective(self, frame):
    """Use corner markers to correct perspective distortion"""
    corner_info = self.detect_corner_markers(frame)
    if not corner_info['detected']:
        return frame  # Can't correct without corners

    # Get detected corners
    red_corners = corner_info['red_corners']
    blue_corners = corner_info['blue_corners']

    # Identify corner positions
    src_points = np.float32([top_left, top_right, bottom_left, bottom_right])
    dst_points = np.float32([
        [0, 0], [self.width, 0],
        [0, self.height], [self.width, self.height]
    ])

    # Compute and apply perspective transform
    M = cv2.getPerspectiveTransform(src_points, dst_points)
    corrected = cv2.warpPerspective(frame, M, (self.width, self.height))
    return corrected
```

### 2.5 Implement Spectrogram-Based Audio Decoding

**Location:** New method in `shared_timecode_robust.py`

```python
def decode_fsk_spectrogram(self, audio_channel):
    """Spectrogram-based FSK decoding for better timing tolerance"""
    from scipy.signal import spectrogram

    # Compute spectrogram with overlapping windows
    f, t, Sxx = spectrogram(audio_channel, fs=self.sample_rate,
                            nperseg=256, noverlap=128)

    # Track power at target frequencies
    f0_idx = np.argmin(np.abs(f - self.freq_0))
    f1_idx = np.argmin(np.abs(f - self.freq_1))

    f0_power = Sxx[f0_idx, :]
    f1_power = Sxx[f1_idx, :]

    # Find transitions based on power ratio changes
    ratio = f1_power / (f0_power + 1e-10)

    # Detect bit boundaries from ratio transitions
    transitions = self._find_transitions(ratio, t)

    # Decode bits from transition timings
    return self._decode_from_transitions(transitions)
```

### 2.6 Implement State Machine Decoder

**Location:** New method in `vhs_timecode_analyzer.py`

```python
class DecoderState(Enum):
    SEARCHING = 1
    IN_LEADER = 2
    IN_COUNTDOWN = 3
    READY_FOR_TIMECODE = 4
    READING_TIMECODE = 5
    TIMECODE_COMPLETE = 6
    IN_LEADOUT = 7
    CYCLE_COMPLETE = 8

def decode_with_state_machine(self, video_frames, audio_data):
    """State machine decoder for structured calibration video"""
    state = DecoderState.SEARCHING
    timecode_frames = []

    for frame_num, frame in enumerate(video_frames):
        bits = self.read_binary_strip(frame)
        prefix = bits[:2]

        if bits == '1111111111111111':  # Leader/Tail
            if state == DecoderState.SEARCHING:
                state = DecoderState.IN_LEADER
            elif state == DecoderState.IN_LEADOUT:
                state = DecoderState.CYCLE_COMPLETE

        elif prefix == '11':  # Countdown
            state = DecoderState.IN_COUNTDOWN
            countdown_val = int(bits[2:6], 2)

        elif bits == '0000000000000000':  # Separator
            if state == DecoderState.IN_COUNTDOWN:
                state = DecoderState.READY_FOR_TIMECODE
            elif state == DecoderState.READING_TIMECODE:
                state = DecoderState.TIMECODE_COMPLETE

        elif prefix == '10':  # Timecode
            state = DecoderState.READING_TIMECODE
            frame_id = int(bits[2:14], 2)
            if bits[14:16] == '01':  # Valid end marker
                timecode_frames.append((frame_num, frame_id))

        elif prefix == '00':  # Lead-out
            state = DecoderState.IN_LEADOUT

    return timecode_frames
```

---

## Phase 3: Audio Improvements

### 3.1 Add Per-Frame Pilot Tone

**Location:** `generate_robust_fsk_audio()` in `shared_timecode_robust.py`

```python
def generate_robust_fsk_audio(self, frame_number, frame_type='timecode'):
    """Generate audio with pilot tone for frame sync"""
    samples = np.zeros(self.samples_per_frame)

    # 10% pilot tone at 1200Hz (not 400 or 800)
    pilot_samples = int(self.samples_per_frame * 0.10)
    pilot_tone = self._generate_tone(1200, pilot_samples)
    samples[:pilot_samples] = pilot_tone

    # 5% silence separator
    silence_samples = int(self.samples_per_frame * 0.05)

    # 80% FSK data
    data_start = pilot_samples + silence_samples
    data_samples = int(self.samples_per_frame * 0.80)
    # ... generate FSK bits in remaining space

    # 5% trailing silence
    return samples
```

### 3.2 Update Audio Detection Ranges

**Location:** Class attributes in `shared_timecode_robust.py`

```python
# Lower frequencies for VHS linear audio compatibility
self.freq_0 = 400
self.freq_1 = 800
self.freq_pilot = 1200  # For frame sync

# Detection ranges with guard bands
self.freq_0_range = (300, 500)    # 200Hz bandwidth
self.freq_1_range = (650, 950)    # 300Hz bandwidth
self.freq_pilot_range = (1050, 1350)  # For pilot detection
# Guard band: 500-650Hz (150Hz), 950-1050Hz (100Hz)
```

---

## Phase 4: Integration & Testing

### 4.1 Update Pattern Generator Entry Point

**Location:** `vhs_pattern_generator.py` `main()`

- Update default duration to 62 seconds
- Update structure documentation
- Add `--cycles` parameter for multiple loops

### 4.2 Update MP4 Validation Tool

**Location:** `tools/validate_mp4_timecode.py`

- Update for 16-bit encoding
- Add state machine validation
- Update expected frame ranges

### 4.3 Update Menu Descriptions

**Location:** `ddd_main_menu.py`

- Update any hardcoded durations (35s → 62s)
- Update descriptions to reflect new structure

---

## Implementation Order

1. **Phase 1.1-1.2**: Update encoding parameters (breaks existing videos)
2. **Phase 1.3**: Update visual binary strip (16 blocks, 3 rows, red/blue, gray background)
3. **Phase 1.4**: Create new lead-in/lead-out structure (62 second cycle)
4. **Phase 2.1-2.2**: Update decoding with center sampling and confidence reporting
5. **Phase 2.4**: Add perspective correction using corners
6. **Phase 3.1-3.2**: Add pilot tone and update frequencies (400/800 Hz)
7. **Phase 2.5-2.6**: Add spectrogram and state machine decoding
8. **Phase 4**: Integration and testing

---

## Verification Steps

### Test 1: Generate New Calibration Video
```bash
cd tools/timecode-generator
python vhs_timecode_generator.py --duration 62 --format PAL --output test_new.mp4
```

Verify:
- 62-second duration with correct structure
- 16 blocks visible (40 pixels each)
- Red/blue color blocks on gray background
- 3 vertical rows visible
- Leader → Countdown → Timecode → Count-up → Tail structure

### Test 2: Validate MP4 Detection
```bash
python validate_mp4_timecode.py test_new.mp4
```

Verify:
- State machine transitions correctly detected
- Frame numbers decoded accurately
- 750 timecode frames identified (30s × 25fps)

### Test 3: Test with Simulated VHS Degradation
- Apply blur, noise, and contrast reduction to test MP4
- Run validation and check decode rate

### Test 4: Full VHS Round-Trip (Manual)
1. Burn test video to DVD
2. Record DVD to VHS
3. Capture VHS with DomesdayDuplicator
4. Run vhs-decode (TBC + clock sync)
5. Run timecode analysis on processed output
6. Verify offset measurements are consistent

---

## Phase 5: Calibration Workflow Integration

### 5.1 Update `precision_timecode_capture()` in `ddd_main_menu.py`

**Location:** Line ~3408

**Changes:**
- Update capture duration from 45s to 130s (124s video + 6s buffer)
- Use fixed calibration filename: `calibration_v2` (not timestamped)
- Output to `temp/` directory with known filenames
- Remove old alignment analysis, replace with V2 timecode decoder

**Fixed filenames:**
```
temp/calibration_v2.lds          # RF capture
temp/calibration_v2.flac         # Audio capture
temp/calibration_v2.tbc          # Decoded TBC
temp/calibration_v2.tbc.json     # TBC metadata
temp/calibration_v2_ffv1.mkv     # Exported video (for V2 analysis)
```

### 5.2 Create V2 Calibration Analyzer Function

**Location:** New function in `ddd_main_menu.py` or separate module

```python
def analyze_v2_calibration(video_file, audio_file):
    """
    Analyze V2 calibration video to calculate A/V offset.

    1. Extract frames from video
    2. Decode visual timecodes using V2 decoder
    3. Decode audio FSK timecodes
    4. Compare video frame numbers with audio frame numbers
    5. Calculate offset (video_frame - audio_frame)
    6. Return median offset with confidence
    """
    from tools.timecode_generator.shared_timecode_robust import RobustTimecodeGenerator

    generator = RobustTimecodeGenerator(format_type='PAL')

    # Sample frames throughout the video
    sample_points = []
    for frame_num in sample_frame_numbers:
        frame = extract_frame(video_file, frame_num)

        # Decode visual timecode
        decoded_frame, confidence, status = generator.decode_frame_with_validation(frame)

        if status == "OK":
            # Get corresponding audio timecode
            audio_frame = decode_audio_at_frame(audio_file, frame_num)

            if audio_frame is not None:
                offset = frame_num - decoded_frame  # How many frames offset
                sample_points.append((frame_num, offset, confidence))

    # Calculate median offset (robust to outliers)
    offsets = [o for _, o, _ in sample_points]
    median_offset = np.median(offsets)

    # Convert to seconds
    offset_seconds = median_offset / fps

    return offset_seconds, len(sample_points), np.std(offsets)
```

### 5.3 Update Calibration Workflow Steps

**New workflow in `precision_timecode_capture()`:**

```
STEP 1: CAPTURE (130 seconds)
- Start DomesdayDuplicator capture to temp/calibration_v2.lds
- Start SOX audio recording to temp/calibration_v2.flac
- Wait 130 seconds
- Stop both captures

STEP 2: DECODE
- Run vhs-decode on calibration_v2.lds → calibration_v2.tbc
- Run tbc-video-export → calibration_v2_ffv1.mkv

STEP 3: ANALYZE V2 TIMECODES
- Call analyze_v2_calibration(calibration_v2_ffv1.mkv, calibration_v2.flac)
- Decode visual timecodes from video frames
- Decode audio FSK timecodes
- Calculate offset between them

STEP 4: SAVE CALIBRATION
- Display measured offset with confidence
- Save to config['audio_delay']
- Confirm calibration applied
```

### 5.4 Update Menu Option 3 Instructions

**Location:** `display_robust_timecode_menu()` line ~2443

Update step descriptions to match V2 workflow:
```
STEP 1 - PREPARATION:
  1. Generate VHS Calibration Pattern (62s V2 Cycles)
  2. Create DVD ISOs from MP4s
     (Then burn ISO to DVD with your chosen burning software)

STEP 2 - RECORD:
  3. Record DVD playback to VHS tape (at least 2 minutes)

STEP 3 - CALIBRATE:
  4. Capture & Analyze (auto-captures, decodes, and calculates offset)
```

### 5.5 Handle Existing Calibration Files

Before capture, check if calibration files exist and offer to overwrite:
```python
calibration_files = [
    'temp/calibration_v2.lds',
    'temp/calibration_v2.flac',
    'temp/calibration_v2.tbc',
    'temp/calibration_v2_ffv1.mkv'
]

existing = [f for f in calibration_files if os.path.exists(f)]
if existing:
    print("Existing calibration files found:")
    for f in existing:
        print(f"  {f}")
    overwrite = input("Overwrite? (y/N): ")
    if overwrite.lower() != 'y':
        return
```

---

## Rollback Plan

Keep original files as backups:
- `shared_timecode_robust_v1.py`
- `vhs_timecode_generator_v1.py`

Add version parameter to generator for compatibility:
```python
parser.add_argument('--encoding-version', choices=['v1', 'v2'], default='v2')
```

---

## Notes

- All changes maintain backward compatibility where possible
- New encoding is incompatible with old decoder (by design)
- Test videos must be regenerated after implementation
- Calibration DVDs must be re-burned with new test patterns
