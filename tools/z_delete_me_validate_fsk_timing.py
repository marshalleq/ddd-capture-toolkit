#!/usr/bin/env python3
"""
FSK Timing Parameter Validation

This script validates that the timing parameters used for FSK generation
match those used for FSK detection, and identifies any misalignments.
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'timecode-generator'))

from vhs_timecode_robust import VHSTimecodeRobust
import numpy as np

def validate_timing_parameters():
    """Validate FSK timing parameters"""
    
    print("FSK Timing Parameter Validation")
    print("=" * 50)
    
    # Initialize decoder for PAL
    decoder = VHSTimecodeRobust(format_type='PAL')
    
    print(f"Format: {decoder.format_type}")
    print(f"FPS: {decoder.fps}")
    print(f"Sample Rate: {decoder.sample_rate}Hz")
    print(f"Audio Channels: {decoder.audio_channels}")
    print()
    
    print("FSK Frequencies:")
    print(f"  Freq 0 (bit '0'): {decoder.freq_0}Hz")
    print(f"  Freq 1 (bit '1'): {decoder.freq_1}Hz")
    print(f"  Frequency Ratio: {decoder.freq_1/decoder.freq_0:.2f}:1")
    print(f"  Frequency Separation: {decoder.freq_1 - decoder.freq_0}Hz")
    print()
    
    print("Detection Ranges:")
    print(f"  Freq 0 Range: {decoder.freq_0_range[0]}-{decoder.freq_0_range[1]}Hz")
    print(f"  Freq 1 Range: {decoder.freq_1_range[0]}-{decoder.freq_1_range[1]}Hz")
    print(f"  Guard Band: {decoder.freq_1_range[0] - decoder.freq_0_range[1]}Hz")
    print()
    
    print("Frame Timing:")
    print(f"  Samples per frame: {decoder.samples_per_frame}")
    print(f"  Bits per frame: {decoder.bits_per_frame}")
    print(f"  Samples per bit: {decoder.samples_per_bit}")
    print(f"  Frame duration: {decoder.samples_per_frame/decoder.sample_rate:.4f}s")
    print(f"  Bit duration: {decoder.samples_per_bit/decoder.sample_rate:.6f}s")
    print()
    
    print("FSK Decoder Search Parameters:")
    search_step = decoder.samples_per_frame // 8
    print(f"  Search step: {search_step} samples")
    print(f"  Search interval: {search_step/decoder.sample_rate:.6f}s ({search_step/decoder.sample_rate*1000:.2f}ms)")
    print(f"  Overlap factor: {decoder.samples_per_frame/search_step:.1f}x")
    print()
    
    # Calculate expected detections for 30-second timecode section
    timecode_duration = 30.0  # seconds
    total_samples = int(timecode_duration * decoder.sample_rate)
    expected_frames = int(timecode_duration * decoder.fps)
    search_positions = total_samples // search_step
    
    print("30-Second Timecode Section Analysis:")
    print(f"  Total duration: {timecode_duration}s")
    print(f"  Total samples: {total_samples}")
    print(f"  Expected video frames: {expected_frames}")
    print(f"  Expected FSK frames: {expected_frames}")
    print(f"  Search positions: {search_positions}")
    print(f"  Theoretical max detections: {search_positions}")
    print()
    
    # Check for potential alignment issues
    print("Alignment Analysis:")
    frame_boundary_samples = decoder.samples_per_frame
    print(f"  Frame boundary every: {frame_boundary_samples} samples")
    print(f"  Search step: {search_step} samples")
    
    # Calculate greatest common divisor to find alignment pattern
    import math
    gcd = math.gcd(frame_boundary_samples, search_step)
    print(f"  GCD of frame boundary and search step: {gcd}")
    print(f"  Alignment period: {frame_boundary_samples // gcd} search steps")
    print(f"  Search positions per frame boundary: {frame_boundary_samples // search_step}")
    
    if frame_boundary_samples % search_step == 0:
        print("  ✓ Perfect alignment - search step divides frame boundary evenly")
    else:
        remainder = frame_boundary_samples % search_step
        print(f"  ⚠️  Imperfect alignment - remainder: {remainder} samples")
        print(f"     This could cause some frames to be missed")
    
    print()
    
    # Test a single frame generation and detection
    print("Single Frame Test:")
    test_frame_id = 100
    generated_audio = decoder.generate_robust_fsk_audio(test_frame_id)
    print(f"  Generated audio for frame {test_frame_id}: {len(generated_audio)} samples")
    
    # Try to decode it back
    decoded_frames = decoder.decode_fsk_audio(generated_audio, strict=False)
    print(f"  Decoded frames: {len(decoded_frames)}")
    
    if decoded_frames:
        for i, (sample_pos, frame_id, confidence) in enumerate(decoded_frames):
            print(f"    Frame {i+1}: Position {sample_pos}, ID {frame_id}, Confidence {confidence:.3f}")
            if frame_id == test_frame_id:
                print(f"    ✓ Successfully decoded original frame ID")
            else:
                print(f"    ❌ Frame ID mismatch: expected {test_frame_id}, got {frame_id}")
    else:
        print("    ❌ No frames decoded from generated audio")
    
    return decoder

def test_frame_boundary_detection():
    """Test frame boundary detection with multiple consecutive frames"""
    
    print("\n" + "=" * 50)
    print("Frame Boundary Detection Test")
    print("=" * 50)
    
    decoder = VHSTimecodeRobust(format_type='PAL')
    
    # Generate 5 consecutive frames
    test_frames = [0, 1, 2, 3, 4]
    combined_audio = np.array([])
    
    for frame_id in test_frames:
        frame_audio = decoder.generate_robust_fsk_audio(frame_id)
        combined_audio = np.concatenate([combined_audio, frame_audio])
    
    print(f"Generated {len(test_frames)} consecutive frames")
    print(f"Total audio length: {len(combined_audio)} samples ({len(combined_audio)/decoder.sample_rate:.3f}s)")
    
    # Try to decode the combined audio
    decoded_frames = decoder.decode_fsk_audio(combined_audio, strict=False)
    print(f"Decoded {len(decoded_frames)} frames")
    
    print("\nDetected frames:")
    for i, (sample_pos, frame_id, confidence) in enumerate(decoded_frames):
        expected_pos = frame_id * decoder.samples_per_frame
        time_pos = sample_pos / decoder.sample_rate
        print(f"  Frame {i+1}: Pos {sample_pos} (expected {expected_pos}), ID {frame_id}, Conf {confidence:.3f}, Time {time_pos:.3f}s")
    
    # Check if all expected frames were found
    detected_ids = set(frame_id for _, frame_id, _ in decoded_frames)
    expected_ids = set(test_frames)
    missing_ids = expected_ids - detected_ids
    extra_ids = detected_ids - expected_ids
    
    if missing_ids:
        print(f"\n❌ Missing frame IDs: {missing_ids}")
    if extra_ids:
        print(f"\n⚠️  Extra frame IDs: {extra_ids}")
    if not missing_ids and not extra_ids:
        print(f"\n✓ All expected frames detected correctly")

def analyze_search_coverage():
    """Analyze how well the search algorithm covers the audio space"""
    
    print("\n" + "=" * 50)
    print("Search Coverage Analysis")
    print("=" * 50)
    
    decoder = VHSTimecodeRobust(format_type='PAL')
    
    # Simulate 30-second audio
    duration = 30.0
    total_samples = int(duration * decoder.sample_rate)
    frame_samples = decoder.samples_per_frame
    search_step = frame_samples // 8
    
    print(f"Analyzing {duration}s of audio ({total_samples} samples)")
    print(f"Frame size: {frame_samples} samples")
    print(f"Search step: {search_step} samples")
    
    # Calculate all search positions
    search_positions = []
    for start_sample in range(0, total_samples - frame_samples + 1, search_step):
        search_positions.append(start_sample)
    
    print(f"Total search positions: {len(search_positions)}")
    
    # Calculate expected frame starts (every frame_samples)
    expected_frame_starts = []
    for frame_num in range(int(duration * decoder.fps)):
        frame_start = frame_num * frame_samples
        if frame_start <= total_samples - frame_samples:
            expected_frame_starts.append(frame_start)
    
    print(f"Expected frame starts: {len(expected_frame_starts)}")
    
    # Check coverage - for each expected frame start, find closest search position
    coverage_analysis = []
    for frame_start in expected_frame_starts:
        # Find closest search position
        distances = [abs(search_pos - frame_start) for search_pos in search_positions]
        min_distance = min(distances)
        closest_search_pos = search_positions[distances.index(min_distance)]
        
        coverage_analysis.append({
            'frame_start': frame_start,
            'closest_search': closest_search_pos,
            'distance': min_distance,
            'time_offset': min_distance / decoder.sample_rate
        })
    
    # Analyze coverage statistics
    distances = [item['distance'] for item in coverage_analysis]
    time_offsets = [item['time_offset'] for item in coverage_analysis]
    
    print(f"\nCoverage Statistics:")
    print(f"  Average distance: {np.mean(distances):.1f} samples ({np.mean(time_offsets)*1000:.3f}ms)")
    print(f"  Max distance: {np.max(distances)} samples ({np.max(time_offsets)*1000:.3f}ms)")
    print(f"  Min distance: {np.min(distances)} samples ({np.min(time_offsets)*1000:.3f}ms)")
    
    # Count perfect alignments (distance = 0)
    perfect_alignments = sum(1 for d in distances if d == 0)
    print(f"  Perfect alignments: {perfect_alignments}/{len(expected_frame_starts)} ({perfect_alignments/len(expected_frame_starts)*100:.1f}%)")
    
    # Count frames that might be missed (distance > threshold)
    threshold = frame_samples // 4  # Quarter frame tolerance
    potentially_missed = sum(1 for d in distances if d > threshold)
    print(f"  Potentially missed (distance > {threshold}): {potentially_missed}")

if __name__ == "__main__":
    print("FSK Timing Analysis Suite")
    print("=" * 50)
    
    # Run all tests
    decoder = validate_timing_parameters()
    test_frame_boundary_detection()
    analyze_search_coverage()
    
    print("\n" + "=" * 50)
    print("Analysis Complete")
