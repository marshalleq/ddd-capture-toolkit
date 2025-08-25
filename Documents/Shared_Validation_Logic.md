# Shared Validation Logic for VHS and MP4 Timecode Analysis

## Overview

This document provides a detailed explanation of the shared logic for FSK decoding and timecode correlation used in both VHS and MP4 timecode analysis. This logic is implemented in the `shared_timecode_robust.py` module (formerly `vhs_timecode_robust.py`) and is invoked by both the VHS timecode analyzer and the MP4 validator.

## Core Logic

The shared FSK decoder uses two modes:
1. **Strict Mode** (for MP4): This mode expects perfect timing, decoding FSK only at exact frame boundaries.
2. **Tolerant Mode** (for VHS): This mode is more flexible, using sliding window techniques to handle timing variations typical in VHS captures.

### Flexible Decoder Function

```python
def decode_fsk_audio(self, audio_channel, strict=True):
    """
    Flexible FSK decoder with strict and tolerant modes

    Args:
        audio_channel: Mono audio samples
        strict: If True, uses deterministic frame boundaries (MP4 mode)
               If False, uses sliding window tolerance (VHS mode)

    Returns:
        list: List of (sample_position, frame_id, confidence) tuples
    """
    if strict:
        return self._decode_deterministic_frames(audio_channel)
    else:
        return self._decode_tolerant_frames(audio_channel)
```

### Mode-Specific Methods

#### Deterministic Mode
- **Usage**: Called with `strict=True` for MP4 validation.
- **Implementation**:
  - Checks exact frame boundaries for decoding.
  - No overlapping or probabilistic methods.

#### Tolerant Mode
- **Usage**: Called with `strict=False` for VHS captures.
- **Implementation**:
  - Uses sliding window approach with robust multi-method bit analysis.
  - Incorporates overlapping windows to accommodate timing variations.
  - Merges results using confidence-based filtering.

### Tolerant Mode Logic

#### Sliding Window and Multi-Method Analysis

```python
def _decode_tolerant_frames(self, audio_channel):
    decoded_frames = []
    frame_samples = self.samples_per_frame

    # Exact frame boundaries (robust bit analysis)
    exact_results = self._decode_exact_boundaries_robust(audio_channel)
    decoded_frames.extend(exact_results)
    
    # Sliding window (small offsets)
    slide_step = frame_samples // 8
    sliding_results = self._decode_sliding_windows(audio_channel, slide_step)

    # Merge results, avoiding duplicates
    merged_results = self._merge_decoded_frames(decoded_frames, sliding_results)
    return merged_results
```

#### Robust Bit Analysis
- **Methods Used**:
  - FFT-based frequency detection.
  - Zero-crossing rate analysis.
  - Autocorrelation-based period detection.
- **Weighted Voting**:
  - Combines results from multiple detection methods, with FFT having the highest weight.

#### Example Code

```python
def _analyze_bit_robust(self, bit_audio):
    # Analyze using FFT, Zero-Crossing, Autocorrelation
    fft_result = self._analyze_bit_fft(bit_audio)
    zcr_result = self._analyze_bit_zero_crossings(bit_audio)
    autocorr_result = self._analyze_bit_autocorrelation(bit_audio)

    # Combine using weights
    methods = []
    if fft_result is not None:
        methods.append((fft_result[0], fft_result[1], 2.0))
    if zcr_result is not None:
        methods.append((zcr_result[0], zcr_result[1], 1.0))
    if autocorr_result is not None:
        methods.append((autocorr_result[0], autocorr_result[1], 1.0))

    if len(methods) == 0:
        return None  # No methods worked

    # Weighted voting based on methods
    total_weight_0 = sum(weight for bit, conf, weight in methods if bit == '0')
    total_weight_1 = sum(weight for bit, conf, weight in methods if bit == '1')

    if total_weight_0 > total_weight_1:
        avg_conf = np.mean([conf for bit, conf, weight in methods if bit == '0'])
        return '0', avg_conf
    elif total_weight_1 > total_weight_0:
        avg_conf = np.mean([conf for bit, conf, weight in methods if bit == '1'])
        return '1', avg_conf
    else:
        best_method = max(methods, key=lambda x: x[1])
        return best_method[0], best_method[1]
```

## Sequential Timecode Correlation Algorithm

### Problem Statement

The original correlation algorithm had a fundamental flaw: it performed exhaustive matching between ALL video timecodes and ALL audio timecodes. With 1156 video frames and 925 audio frames, this created over 1 million potential matches, leading to:

- **False Matches**: Frame ID "100" from video at 4 seconds matching with frame ID "100" from audio at 42 seconds
- **Massive Offset Variations**: Standard deviations of 22+ seconds with ranges up to 38 seconds
- **Unrealistic Results**: Offset measurements that were physically impossible for VHS timing variations

### Sequential Matching Solution

The new algorithm implements **sequential matching** that pairs timecodes in their natural temporal order:

```python
def correlate_timecodes(self, video_timecodes, audio_timecodes):
    # Sort timecodes by frame/sample position
    video_timecodes.sort(key=lambda x: x[0])
    audio_timecodes.sort(key=lambda x: x[0])

    matches = []
    
    # Use sequential matching - match first occurrence with first occurrence
    v_idx, a_idx = 0, 0
    while v_idx < len(video_timecodes) and a_idx < len(audio_timecodes):
        video_frame, video_id, video_conf = video_timecodes[v_idx]
        audio_sample, audio_id, audio_conf = audio_timecodes[a_idx]
        
        if video_id == audio_id:
            # Found a match - calculate offset
            video_time = video_frame / self.fps
            audio_time = audio_sample / self.sample_rate
            offset = audio_time - video_time
            combined_confidence = min(video_conf, audio_conf)
            
            matches.append({
                'frame_id': video_id,
                'offset_seconds': offset,
                'confidence': combined_confidence
            })
            v_idx += 1
            a_idx += 1
        elif video_id < audio_id:
            v_idx += 1  # Video is behind - advance video index
        else:
            a_idx += 1  # Audio is behind - advance audio index
```

### Algorithm Benefits

1. **Temporal Consistency**: Matches frames in their natural sequence order
2. **Eliminates False Positives**: First occurrence of frame ID X in video only matches with first occurrence of frame ID X in audio
3. **Realistic Results**: Produces offset measurements within tenths of seconds (realistic for VHS timing variations)
4. **Computational Efficiency**: O(n + m) complexity instead of O(n × m)
5. **Robust to Missing Frames**: If a frame is missing in either stream, the algorithm gracefully skips it

### Shared Implementation

The correlation logic is implemented in the `SharedTimecodeRobust` class as the `correlate_timecodes()` method, ensuring consistency across:

- **Menu 5.3**: VHS capture validation
- **Menu 5.4**: MP4 timecode validation  
- **Menu 3.2**: MP4 timecode creation validation

This shared approach follows the project's architecture principle of maintaining consistent logic across validation workflows while allowing mode-specific decoding (strict vs. tolerant).

### Expected Results

With sequential correlation, typical results show:
- **Standard Deviation**: < 1.0 seconds (down from 22+ seconds)
- **Offset Range**: Within ±2.0 seconds (down from ±38 seconds)
- **Realistic Measurements**: Offsets that reflect actual VHS mechanical timing variations
- **Consistent Results**: Multiple runs produce similar offset measurements

## Conclusion

This shared logic ensures FSK decoding has robustness for MP4 and flexibility for VHS analysis, which creates an accurate source upon which to calculate capture start time adjustments.  The sliding window and multi-method approach specifically enhances the decoder's ability to handle the imperfections of VHS captures while maintaining strict validation standards for MP4 files.
