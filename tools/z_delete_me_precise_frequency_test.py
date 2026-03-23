#!/usr/bin/env python3
"""
Precise frequency analysis to verify exact generation
"""

import numpy as np
import scipy.io.wavfile as wavfile
import sys

def analyze_precise_frequency(audio, sample_rate, window_start_sample, window_samples):
    """Analyze frequency with higher precision using zero-padding"""
    
    # Extract the window
    segment = audio[window_start_sample:window_start_sample + window_samples]
    
    # Zero-pad to increase FFT resolution (factor of 8)
    padded_length = len(segment) * 8
    padded_segment = np.zeros(padded_length)
    padded_segment[:len(segment)] = segment * np.hanning(len(segment))
    
    # FFT with high resolution
    fft_result = np.fft.fft(padded_segment)
    freqs = np.fft.fftfreq(padded_length, d=1/sample_rate)
    
    # Only positive frequencies
    positive_freqs = freqs[:len(freqs)//2]
    positive_fft = np.abs(fft_result[:len(fft_result)//2])
    
    # Find peak
    peak_idx = np.argmax(positive_fft)
    peak_freq = positive_freqs[peak_idx]
    
    return abs(peak_freq)

if __name__ == "__main__":
    # Import the generator
    import os
    timecode_gen_path = os.path.join(os.path.dirname(__file__), 'timecode-generator')
    if os.path.exists(timecode_gen_path):
        sys.path.append(timecode_gen_path)
    else:
        # Try relative to project root
        project_root = os.path.dirname(os.path.dirname(__file__))
        timecode_gen_path = os.path.join(project_root, 'tools', 'timecode-generator')
        if os.path.exists(timecode_gen_path):
            sys.path.append(timecode_gen_path)
    from vhs_timecode_base import VHSTimecodeBase
    
    # Create generator instance
    generator = VHSTimecodeBase("PAL")
    
    print("Testing fixed FSK generation with high-precision analysis:")
    
    # Test frame 0 (should be all '0' bits = 1000Hz)
    frame_0_audio = generator._generate_fsk_timecode(0, 48000)
    bit_samples = len(frame_0_audio) // 32
    
    # Analyze first bit
    first_bit_start = 0
    freq_0 = analyze_precise_frequency(frame_0_audio, 48000, first_bit_start, bit_samples)
    print(f"Frame 0, bit 1 frequency: {freq_0:.2f}Hz (expected 1000.00Hz)")
    
    # Test frame with mixed bits
    # Frame 255 = 0b11111111 in last 8 bits, so bit 25-32 should be '1' = 1200Hz
    frame_255_audio = generator._generate_fsk_timecode(255, 48000)
    
    # Analyze bit 17 (should be '1' = 1200Hz for frame 255)
    bit_17_start = 16 * bit_samples  # Bit 17 is index 16
    freq_1 = analyze_precise_frequency(frame_255_audio, 48000, bit_17_start, bit_samples)
    print(f"Frame 255, bit 17 frequency: {freq_1:.2f}Hz (expected 1200.00Hz)")
    
    # Calculate theoretical frequency for verification
    bit_duration = bit_samples / 48000
    cycles_1000 = 1000 * bit_duration
    cycles_1200 = 1200 * bit_duration
    
    print(f"\nTheoretical verification:")
    print(f"Bit duration: {bit_duration:.6f}s")
    print(f"Cycles in bit @ 1000Hz: {cycles_1000:.3f}")
    print(f"Cycles in bit @ 1200Hz: {cycles_1200:.3f}")
    
    # Check if we get exact integer cycles
    print(f"1000Hz cycles - integer part: {int(cycles_1000)}, fractional: {cycles_1000 - int(cycles_1000):.6f}")
    print(f"1200Hz cycles - integer part: {int(cycles_1200)}, fractional: {cycles_1200 - int(cycles_1200):.6f}")
    
    # Save test audio
    wavfile.write('precise_test_frame_0.wav', 48000, (frame_0_audio * 32767).astype(np.int16))
    wavfile.write('precise_test_frame_255.wav', 48000, (frame_255_audio * 32767).astype(np.int16))
    print(f"\nSaved test audio files for manual inspection.")
