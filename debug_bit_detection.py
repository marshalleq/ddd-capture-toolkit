#!/usr/bin/env python3
"""
Debug FSK bit detection logic

This script tests the same frequency analysis logic used by the timecode analyzer
to understand why bits are not being detected correctly.
"""

import numpy as np
import subprocess
import sys

def load_audio_data(audio_file, sample_rate=48000):
    """Load audio data using sox"""
    try:
        cmd = ['sox', audio_file, '-t', 'f32', '-r', str(sample_rate), '-']
        result = subprocess.run(cmd, capture_output=True, check=True)
        audio_raw = np.frombuffer(result.stdout, dtype=np.float32)
        
        if len(audio_raw) % 2 == 0:
            return audio_raw.reshape(-1, 2)
        else:
            return audio_raw.reshape(-1, 1)
    except Exception as e:
        print(f"Error loading audio: {e}")
        return None

def analyze_bit_frequency_original(bit_audio, base_frequency=800, sample_rate=48000):
    """Original analyzer logic"""
    if len(bit_audio) < 10:
        return None, {}, {}

    # Apply window function
    windowed_audio = bit_audio * np.hanning(len(bit_audio))
    
    # Perform FFT
    fft_result = np.fft.fft(windowed_audio)
    freqs = np.fft.fftfreq(len(bit_audio), d=1/sample_rate)
    
    # Only positive frequencies
    positive_freqs = freqs[:len(freqs)//2]
    positive_fft = np.abs(fft_result[:len(fft_result)//2])
    
    # Expected frequencies
    freq_0 = base_frequency  # 800Hz for '0'
    freq_1 = base_frequency + 800  # 1600Hz for '1' (corrected from original)
    
    # Find peaks in expected frequency ranges
    freq_0_range = (freq_0 - 150, freq_0 + 150)  # 650-950Hz
    freq_1_range = (freq_1 - 150, freq_1 + 150)  # 1450-1750Hz
    
    # Get amplitude in each frequency range
    mask_0 = (positive_freqs >= freq_0_range[0]) & (positive_freqs <= freq_0_range[1])
    mask_1 = (positive_freqs >= freq_1_range[0]) & (positive_freqs <= freq_1_range[1])
    
    amp_0 = np.max(positive_fft[mask_0]) if np.any(mask_0) else 0
    amp_1 = np.max(positive_fft[mask_1]) if np.any(mask_1) else 0
    
    # Find overall peak frequency
    peak_idx = np.argmax(positive_fft)
    peak_freq = positive_freqs[peak_idx]
    
    debug_info = {
        'peak_freq': peak_freq,
        'amp_0': amp_0,
        'amp_1': amp_1,
        'freq_0_range': freq_0_range,
        'freq_1_range': freq_1_range,
        'threshold': 0.1
    }
    
    spectrum_info = {
        'freqs': positive_freqs,
        'fft': positive_fft,
        'mask_0': mask_0,
        'mask_1': mask_1
    }
    
    # Classify based on amplitude
    if amp_0 > amp_1 and amp_0 > 0.1:
        return '0', debug_info, spectrum_info
    elif amp_1 > amp_0 and amp_1 > 0.1:
        return '1', debug_info, spectrum_info
    
    return None, debug_info, spectrum_info

def test_frame_detection(audio_file, frame_id):
    """Test bit detection for a specific frame"""
    # Load audio
    audio_data = load_audio_data(audio_file)
    if audio_data is None:
        return None
    
    left_channel = audio_data[:, 0] if audio_data.ndim > 1 else audio_data
    
    # Parameters matching the analyzer
    sample_rate = 48000
    expected_fps = 25
    expected_frame_duration = sample_rate / expected_fps
    bits_per_frame = 32
    samples_per_bit = int(expected_frame_duration / bits_per_frame)
    
    # Calculate frame position
    frame_samples = int(expected_frame_duration)
    frame_start = frame_id * frame_samples
    frame_end = frame_start + frame_samples
    
    if frame_end > len(left_channel):
        return None
        
    frame_audio = left_channel[frame_start:frame_end]
    
    detected_bits = []
    failed_bits = 0
    
    for bit_idx in range(bits_per_frame):
        start_bit = bit_idx * samples_per_bit
        end_bit = start_bit + samples_per_bit
        
        if end_bit > len(frame_audio):
            break
            
        bit_audio = frame_audio[start_bit:end_bit]
        bit_value, debug_info, spectrum_info = analyze_bit_frequency_original(bit_audio)
        
        if bit_value is not None:
            detected_bits.append(bit_value)
        else:
            failed_bits += 1
            detected_bits.append('?')
    
    return {
        'frame_id': frame_id,
        'detected_bits': ''.join(detected_bits),
        'failed_bits': failed_bits,
        'total_bits': bits_per_frame
    }

def test_bit_detection(audio_file):
    """Test bit detection on actual captured audio - multiple frames"""
    print(f"Testing bit detection on: {audio_file}")
    
    # Load audio
    audio_data = load_audio_data(audio_file)
    if audio_data is None:
        print("Failed to load audio!")
        return
    
    left_channel = audio_data[:, 0] if audio_data.ndim > 1 else audio_data
    
    # Parameters matching the analyzer
    sample_rate = 48000
    expected_fps = 25
    expected_frame_duration = sample_rate / expected_fps
    bits_per_frame = 32
    samples_per_bit = int(expected_frame_duration / bits_per_frame)
    
    print(f"Frame duration: {expected_frame_duration} samples")
    print(f"Samples per bit: {samples_per_bit}")
    
    # Test first several frames
    max_frames = min(10, int(len(left_channel) / expected_frame_duration))
    
    print(f"\nTesting first {max_frames} frames:")
    print("Frame | Expected                         | Detected                         | Match | Failed")
    print("------|----------------------------------|----------------------------------|---------")
    
    total_matches = 0
    total_bits = 0
    
    for frame_id in range(max_frames):
        result = test_frame_detection(audio_file, frame_id)
        if result is None:
            break
            
        expected_bits = format(frame_id, '032b')
        detected_bits = result['detected_bits']
        failed_bits = result['failed_bits']
        
        # Count matches
        matches = sum(1 for i, (exp, det) in enumerate(zip(expected_bits, detected_bits)) if exp == det and det != '?')
        valid_detected = len([b for b in detected_bits if b != '?'])
        
        total_matches += matches
        total_bits += len(expected_bits)
        
        print(f"{frame_id:5d} | {expected_bits} | {detected_bits} | {matches:2d}/{valid_detected:2d} | {failed_bits:2d}")
        
        # Try to decode frame number
        if '?' not in detected_bits:
            decoded_frame = int(detected_bits[:24], 2)
            if decoded_frame != frame_id:
                print(f"      WARNING: Expected frame {frame_id}, decoded {decoded_frame}")
    
    print(f"\nOverall Results:")
    print(f"  Total correct bits: {total_matches}/{total_bits} ({100*total_matches/total_bits:.1f}%)")
    
    # Also test specific frame with detailed output
    print(f"\n=== Detailed analysis of Frame 7 (should have some '1' bits) ===")
    frame_id = 7
    result = test_frame_detection(audio_file, frame_id)
    if result:
        expected_bits = format(frame_id, '032b')
        print(f"Expected: {expected_bits}")
        print(f"Detected: {result['detected_bits']}")
        
        # Show bit-by-bit for this frame
        frame_samples = int(expected_frame_duration)
        frame_start = frame_id * frame_samples
        frame_end = frame_start + frame_samples
        frame_audio = left_channel[frame_start:frame_end]
        
        print("\nBit-by-bit analysis:")
        print("Bit | Exp | Det | Peak  | Amp_0  | Amp_1  | Decision")
        print("----|-----|-----|-------|--------|--------|----------")
        
        for bit_idx in range(min(32, bits_per_frame)):
            start_bit = bit_idx * samples_per_bit
            end_bit = start_bit + samples_per_bit
            
            if end_bit > len(frame_audio):
                break
                
            bit_audio = frame_audio[start_bit:end_bit]
            bit_value, debug_info, spectrum_info = analyze_bit_frequency_original(bit_audio)
            
            expected_bit = expected_bits[bit_idx]
            peak_freq = debug_info.get('peak_freq', 0)
            amp_0 = debug_info.get('amp_0', 0)
            amp_1 = debug_info.get('amp_1', 0)
            
            decision = "WRONG" if bit_value != expected_bit else "OK"
            if bit_value is None:
                decision = "FAIL"
                
            print(f"{bit_idx:3d} | {expected_bit:3s} | {bit_value or '?':3s} | {peak_freq:5.0f} | {amp_0:6.2f} | {amp_1:6.2f} | {decision}")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python3 debug_bit_detection.py <audio_file>")
        sys.exit(1)
    
    test_bit_detection(sys.argv[1])
