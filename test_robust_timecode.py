#!/usr/bin/env python3
"""
Test script for the robust VHS timecode system

This script demonstrates the improvements in the robust FSK encoding
compared to the original system.
"""

import numpy as np
import sys
import os

# Add the timecode generator path
timecode_gen_path = os.path.join(os.path.dirname(__file__), 'tools', 'timecode-generator')
if os.path.exists(timecode_gen_path):
    sys.path.append(timecode_gen_path)
else:
    # Fallback to current directory for imports
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from shared_timecode_robust import SharedTimecodeRobust

def test_robust_encoding():
    """Test the robust FSK encoding system"""
    print("Testing Robust VHS Timecode System")
    print("=" * 50)
    
    # Create robust timecode generator
    generator = SharedTimecodeRobust("PAL")
    
    print(f"Frequency configuration:")
    print(f"  '0' bit frequency: {generator.freq_0}Hz")
    print(f"  '1' bit frequency: {generator.freq_1}Hz")
    print(f"  Frequency separation: {generator.freq_1 - generator.freq_0}Hz")
    print(f"  Frequency ratio: {generator.freq_1 / generator.freq_0:.1f}:1")
    print()
    
    print(f"Detection ranges:")
    print(f"  '0' detection range: {generator.freq_0_range[0]}-{generator.freq_0_range[1]}Hz")
    print(f"  '1' detection range: {generator.freq_1_range[0]}-{generator.freq_1_range[1]}Hz")
    print(f"  Guard band separation: {generator.freq_1_range[0] - generator.freq_0_range[1]}Hz")
    print()
    
    print(f"Audio parameters:")
    print(f"  Sample rate: {generator.sample_rate}Hz")
    print(f"  Audio channels: {generator.audio_channels} (MONO)")
    print(f"  Samples per frame: {generator.samples_per_frame}")
    print(f"  Samples per bit: {generator.samples_per_bit}")
    print(f"  Bit duration: {generator.samples_per_bit / generator.sample_rate * 1000:.1f}ms")
    print()
    
    # Test frame encoding/decoding
    test_frames = [0, 1, 7, 15, 255, 1000, 4095]
    
    print("Testing frame encoding and decoding:")
    print("Frame | Binary (24-bit)          | Checksum | Decode Result | Confidence")
    print("------|--------------------------|----------|---------------|------------")
    
    for frame_num in test_frames:
        # Generate audio for this frame
        audio = generator.generate_robust_fsk_audio(frame_num)
        
        # Decode the audio back
        results = generator.decode_robust_fsk_audio(audio)
        
        # Get the binary representation and checksum
        binary = format(frame_num, '024b')
        checksum = generator._calculate_robust_checksum(frame_num)
        
        if results and len(results) > 0:
            # Get the best result (highest confidence)
            best_result = max(results, key=lambda x: x[2])
            sample_pos, decoded_frame, confidence = best_result
            
            status = "✓ PASS" if decoded_frame == frame_num else "✗ FAIL"
            print(f"{frame_num:5d} | {binary} | {checksum:8d} | {status:13s} | {confidence:.3f}")
        else:
            print(f"{frame_num:5d} | {binary} | {checksum:8d} | ✗ NO DECODE  | 0.000")
    
    print()
    
    # Test bit-level analysis
    print("Testing individual bit detection methods:")
    test_frame = 7  # Has both '0' and '1' bits
    audio = generator.generate_robust_fsk_audio(test_frame)
    
    print(f"Frame {test_frame} binary: {format(test_frame, '032b')}")
    print()
    print("Bit | Expected | FFT    | ZCR    | AutoCorr | Voting Result")
    print("----|----------|--------|--------|----------|-------------")
    
    expected_bits = format(test_frame, '024b') + format(generator._calculate_robust_checksum(test_frame), '08b')
    
    for bit_idx in range(min(10, generator.bits_per_frame)):  # Test first 10 bits
        start_bit = bit_idx * generator.samples_per_bit
        end_bit = start_bit + generator.samples_per_bit
        bit_audio = audio[start_bit:end_bit]
        
        # Test individual methods
        fft_result = generator._analyze_bit_fft(bit_audio)
        zcr_result = generator._analyze_bit_zero_crossings(bit_audio)
        autocorr_result = generator._analyze_bit_autocorrelation(bit_audio)
        
        # Get voting result
        voting_result = generator._analyze_bit_robust(bit_audio)
        
        expected = expected_bits[bit_idx]
        
        fft_bit = fft_result[0] if fft_result else '?'
        zcr_bit = zcr_result[0] if zcr_result else '?'
        autocorr_bit = autocorr_result[0] if autocorr_result else '?'
        voting_bit = voting_result[0] if voting_result else '?'
        
        status = "✓" if voting_bit == expected else "✗"
        
        print(f"{bit_idx:3d} | {expected:8s} | {fft_bit:6s} | {zcr_bit:6s} | {autocorr_bit:8s} | {voting_bit:8s} {status}")
    
    print()
    
    # Test frequency robustness
    print("Testing frequency detection robustness:")
    
    # Generate pure tones at the expected frequencies
    bit_duration = generator.samples_per_bit / generator.sample_rate
    
    # Generate test tones
    test_freqs = [generator.freq_0, generator.freq_1]
    for freq in test_freqs:
        print(f"\nTesting {freq}Hz tone:")
        
        # Generate pure sine wave
        t = np.linspace(0, bit_duration, generator.samples_per_bit, False)
        tone = np.sin(2 * np.pi * freq * t) * 0.6
        
        # Test detection methods
        fft_result = generator._analyze_bit_fft(tone)
        zcr_result = generator._analyze_bit_zero_crossings(tone)
        autocorr_result = generator._analyze_bit_autocorrelation(tone)
        voting_result = generator._analyze_bit_robust(tone)
        
        expected_bit = '0' if freq == generator.freq_0 else '1'
        
        print(f"  Expected bit: '{expected_bit}'")
        if fft_result:
            print(f"  FFT method: '{fft_result[0]}' (confidence: {fft_result[1]:.3f})")
        if zcr_result:
            print(f"  ZCR method: '{zcr_result[0]}' (confidence: {zcr_result[1]:.3f})")
        if autocorr_result:
            print(f"  AutoCorr method: '{autocorr_result[0]}' (confidence: {autocorr_result[1]:.3f})")
        if voting_result:
            print(f"  Voting result: '{voting_result[0]}' (confidence: {voting_result[1]:.3f})")
        
        success = voting_result and voting_result[0] == expected_bit
        print(f"  Status: {'✓ PASS' if success else '✗ FAIL'}")
    
    print()
    print("Robust timecode system test completed!")
    
    # Save test metadata
    metadata = generator.generate_metadata(100, 4.0)
    
    print("System configuration summary:")
    features = metadata['robustness_features']
    for key, value in features.items():
        print(f"  {key.replace('_', ' ').title()}: {value}")

if __name__ == "__main__":
    test_robust_encoding()
