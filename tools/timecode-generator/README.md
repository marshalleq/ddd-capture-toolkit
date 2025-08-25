# VHS Timecode System for Precise Audio/Video Alignment

This system creates and analyzes professional-grade timecode patterns optimized for VHS tape recording and capture, enabling microsecond-accurate audio/video synchronization measurements.

## Overview

The VHS timecode system works by encoding unique frame identifiers into both the video and audio streams of a test pattern. After recording to VHS tape and capturing back, the system can correlate the video and audio timecodes to determine precise timing offsets.

### Key Features

- **Frame-accurate encoding**: Each video frame has a unique identifier
- **Dual-channel audio timecode**: FSK encoding + sync pulses
- **Multiple detection methods**: Binary strips, visual timecode, corner patterns
- **Error correction**: Checksums and confidence scoring
- **VHS-optimized**: High contrast, robust encoding for tape quality
- **Microsecond precision**: Sub-millisecond alignment measurements

## How It Works

### 1. Timecode Generation

Each frame contains:
- **Visual timecode**: Large HH:MM:SS:FF display
- **Binary strip**: Machine-readable frame number (top edge)
- **Corner markers**: Sync patterns and frame validation
- **Audio encoding**:
  - Left channel: FSK-encoded frame number (1000Hz='0', 1200Hz='1')
  - Right channel: 2kHz sync pulse at frame boundaries

### 2. VHS Recording Process

1. Generate timecode test video (60+ seconds recommended)
2. Record to VHS tape using your normal VCR setup
3. Capture back using Domesday Duplicator + audio interface

### 3. Analysis Process

1. **Video analysis**: Extract frame IDs from captured video
2. **Audio analysis**: Decode FSK timecode and detect sync pulses
3. **Correlation**: Match video and audio frame IDs
4. **Measurement**: Calculate precise timing offset

## Usage

### Generate Timecode Test Pattern

```bash
# Generate 2-minute PAL test pattern
python3 vhs_timecode_generator.py --duration 120 --format PAL --output calibration_test.mp4

# Generate NTSC version
python3 vhs_timecode_generator.py --duration 120 --format NTSC --output calibration_test_ntsc.mp4
```

**Options:**
- `--duration`: Length in seconds (default: 60)
- `--format`: PAL (25fps) or NTSC (29.97fps)
- `--output`: Output MP4 file path
- `--width`: Video width (default: 720)
- `--height`: Video height (auto: 576 for PAL, 480 for NTSC)

### Analyze Captured Timecode

```bash
# Analyze captured VHS timecode for alignment
python3 vhs_timecode_analyzer.py --video captured_video.mkv --audio captured_audio.wav --metadata calibration_test_metadata.json --output analysis_results.json
```

**Options:**
- `--video`: Captured video file (FFV1, H.264, etc.)
- `--audio`: Captured audio file (WAV, FLAC, etc.)
- `--metadata`: Optional metadata from generation
- `--output`: Optional JSON output file

### Example Output

```
VHS TIMECODE ANALYSIS RESULTS
============================================================
Analysis successful!

TIMING OFFSET MEASUREMENT:
  Average offset: +0.000342 seconds
  Standard deviation: 0.000028 seconds
  Offset range: +0.000298 to +0.000387 seconds
  Measurement precision: ±0.0 milliseconds

ANALYSIS QUALITY:
  Total frame matches: 847
  Average confidence: 89.2%
  Video frames analyzed: 1502
  Audio frames decoded: 1489

INTERPRETATION: EXCELLENT SYNC (within 1ms)
  Audio starts 0.000s AFTER video
  Recommendation: Reduce audio delay by 0.000s
============================================================
```

## Integration with Calibration System

### Option 1: Replace Current Test Pattern

Replace the current 1kHz tone pattern with the timecode system:

```python
# In your calibration workflow:
# 1. Generate timecode test instead of simple tone
generator = VHSTimecodeGenerator(format_type="PAL")
generator.generate_test_video(60, "vhs_calibration_timecode.mp4")

# 2. Record timecode to VHS and capture back
# (Use existing capture workflow)

# 3. Analyze with timecode analyzer instead of current analysis
analyzer = VHSTimecodeAnalyzer(video_file, audio_file)
results = analyzer.analyze_alignment()

offset = results['average_offset_seconds']
confidence = results['average_confidence']
```

### Option 2: Enhanced Calibration Mode

Add as a new high-precision calibration option:

```
A/V CALIBRATION MENU
1. Standard Calibration (1kHz tone)
2. Precision Timecode Calibration (recommended)
3. Manual Calibration Value Entry
4. Validate Results
```

## Technical Details

### Audio Encoding Specifications

- **Sample rate**: 48kHz (configurable)
- **Left channel**: FSK timecode
  - '0' bit: 1000Hz sine wave
  - '1' bit: 1200Hz sine wave
  - Frame format: 24-bit frame ID + 8-bit XOR checksum
  - Bit duration: ~1ms (1000 bits/second)
- **Right channel**: Sync pulses
  - 2kHz tone burst at frame start
  - 10ms duration with exponential decay

### Video Encoding Specifications

- **Resolution**: 720×576 (PAL) or 720×480 (NTSC)
- **Frame rate**: 25fps (PAL) or 29.97fps (NTSC)
- **Binary strip**: 32-bit frame number (top 20 pixels)
- **Visual timecode**: HH:MM:SS:FF format
- **Corner markers**: White sync squares + intensity patterns

### Error Handling

- **Checksum validation**: XOR checksum on audio timecode
- **Confidence scoring**: Based on signal quality and consistency
- **Multiple detection methods**: Fallback from binary to visual to pattern
- **Statistical analysis**: Weighted averaging of multiple measurements

## Advantages Over Simple Tone Method

1. **Frame-level precision**: Each frame individually identified
2. **Error detection**: Checksums catch decode errors
3. **Robust to dropouts**: Multiple encoding methods
4. **Statistical confidence**: Quality metrics for measurements
5. **Professional workflow**: Similar to broadcast timecode systems
6. **Scalable duration**: Works with any length test pattern

## Requirements

### Software Dependencies

```bash
pip install opencv-python numpy
# Also need: ffmpeg, sox (system packages)
```

### Hardware Requirements

- VHS playback device
- Domesday Duplicator (or similar RF capture)
- Audio capture interface (for Clockgen Lite)
- Monitor for viewing test patterns

## Workflow Integration

This system can replace or supplement the existing test pattern analysis in your calibration workflow. The key advantages are:

1. **Eliminates cycle counting errors**: No risk of being "off by one cycle"
2. **Provides confidence metrics**: Know how reliable your measurement is
3. **Works with any duration**: No need to estimate measurement pairs
4. **Professional accuracy**: Approaches broadcast-quality sync measurement

The timecode approach gives you the "SMPTE-like" precision you mentioned, specifically designed for VHS tape constraints while providing the microsecond accuracy needed for perfect audio/video synchronization.
