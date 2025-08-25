#!/usr/bin/env python3
"""
Test script to verify frequency generation and detection
"""

import numpy as np
import scipy.io.wavfile as wavfile
import matplotlib.pyplot as plt

def generate_test_tones():
    """Generate test tones at 1000Hz and 1200Hz"""
    sample_rate = 48000
    duration = 1.0  # 1 second each
    
    # Generate time array
    t = np.linspace(0, duration, int(sample_rate * duration), False)
    
    # Generate 1000Hz tone
    tone_1000 = np.sin(2 * np.pi * 1000 * t)
    
    # Generate 1200Hz tone  
    tone_1200 = np.sin(2 * np.pi * 1200 * t)
    
    # Combine tones (1000Hz first, then 1200Hz)
    combined = np.concatenate([tone_1000, tone_1200])
    
    # Save as WAV file
    wavfile.write('test_tones.wav', sample_rate, (combined * 32767).astype(np.int16))
    
    print(f"Generated test tones: 1000Hz and 1200Hz")
    print(f"Sample rate: {sample_rate}Hz")
    print(f"Duration: {duration}s each")
    
    return combined, sample_rate

def analyze_frequency_with_fft(audio, sample_rate, start_time, duration):
    """Analyze frequency using FFT"""
    start_sample = int(start_time * sample_rate)
    end_sample = int((start_time + duration) * sample_rate)
    
    segment = audio[start_sample:end_sample]
    
    # Apply window
    windowed = segment * np.hanning(len(segment))
    
    # FFT
    fft_result = np.fft.fft(windowed)
    freqs = np.fft.fftfreq(len(segment), d=1/sample_rate)
    
    # Only positive frequencies
    positive_freqs = freqs[:len(freqs)//2]
    positive_fft = np.abs(fft_result[:len(fft_result)//2])
    
    # Find peak
    peak_idx = np.argmax(positive_fft)
    peak_freq = positive_freqs[peak_idx]
    
    return abs(peak_freq)

def analyze_frequency_with_zero_crossings(audio, sample_rate, start_time, duration):
    """Analyze frequency using zero crossings"""
    start_sample = int(start_time * sample_rate)
    end_sample = int((start_time + duration) * sample_rate)
    
    segment = audio[start_sample:end_sample]
    
    # Count zero crossings
    zero_crossings = 0
    for i in range(1, len(segment)):
        if (segment[i-1] >= 0) != (segment[i] >= 0):
            zero_crossings += 1
    
    # Estimate frequency
    estimated_freq = zero_crossings / (2 * duration)
    
    return estimated_freq

if __name__ == "__main__":
    # Generate test tones
    audio, sample_rate = generate_test_tones()
    
    print("\nAnalyzing first tone (expected 1000Hz):")
    fft_freq_1 = analyze_frequency_with_fft(audio, sample_rate, 0.0, 1.0)
    zc_freq_1 = analyze_frequency_with_zero_crossings(audio, sample_rate, 0.0, 1.0)
    print(f"  FFT method: {fft_freq_1:.1f}Hz")
    print(f"  Zero-crossing method: {zc_freq_1:.1f}Hz")
    
    print("\nAnalyzing second tone (expected 1200Hz):")
    fft_freq_2 = analyze_frequency_with_fft(audio, sample_rate, 1.0, 1.0)
    zc_freq_2 = analyze_frequency_with_zero_crossings(audio, sample_rate, 1.0, 1.0)
    print(f"  FFT method: {fft_freq_2:.1f}Hz")
    print(f"  Zero-crossing method: {zc_freq_2:.1f}Hz")
    
    # Test our generator's FSK function
    print("\nTesting generator's FSK function:")
    
    # Import the generator
    import sys
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
    
    # Generate FSK for frame 0 (all zeros in binary)
    frame_0_audio = generator._generate_fsk_timecode(0, 48000)  # 1 second worth
    
    # Analyze first bit (should be 1000Hz for '0')
    bit_duration = len(frame_0_audio) // 32
    first_bit = frame_0_audio[:bit_duration]
    
    # Apply window and FFT
    windowed_bit = first_bit * np.hanning(len(first_bit))
    fft_result = np.fft.fft(windowed_bit)
    freqs = np.fft.fftfreq(len(first_bit), d=1/48000)
    positive_freqs = freqs[:len(freqs)//2]
    positive_fft = np.abs(fft_result[:len(fft_result)//2])
    peak_idx = np.argmax(positive_fft)
    generator_freq = abs(positive_freqs[peak_idx])
    
    print(f"  Generator FSK bit frequency: {generator_freq:.1f}Hz (expected 1000Hz)")
    
    # Let's debug the bit duration calculation
    total_samples = len(frame_0_audio)
    calculated_bit_samples = total_samples // 32
    actual_bit_duration = calculated_bit_samples / 48000
    expected_bit_duration = 1.0 / 32
    
    print(f"  Debug info:")
    print(f"    Total samples: {total_samples}")
    print(f"    Calculated bit samples: {calculated_bit_samples}")
    print(f"    Actual bit duration: {actual_bit_duration:.6f}s")
    print(f"    Expected bit duration: {expected_bit_duration:.6f}s")
    print(f"    Duration error: {(actual_bit_duration - expected_bit_duration)*1000:.3f}ms")
    
    # Test with frame 1 to see a '1' bit
    frame_1_audio = generator._generate_fsk_timecode(1, 48000)  # Frame 1 has '1' in last bit
    last_bit = frame_1_audio[-calculated_bit_samples:]
    
    # Analyze last bit (should be 1200Hz for '1' in frame 1)
    windowed_bit = last_bit * np.hanning(len(last_bit))
    fft_result = np.fft.fft(windowed_bit)
    freqs = np.fft.fftfreq(len(last_bit), d=1/48000)
    positive_freqs = freqs[:len(freqs)//2]
    positive_fft = np.abs(fft_result[:len(fft_result)//2])
    peak_idx = np.argmax(positive_fft)
    generator_freq_1 = abs(positive_freqs[peak_idx])
    
    print(f"  Generator FSK '1' bit frequency: {generator_freq_1:.1f}Hz (expected 1200Hz)")
    
    # Save generator audio for manual inspection
    wavfile.write('generator_fsk_test.wav', 48000, (frame_0_audio * 32767).astype(np.int16))
    print(f"  Saved generator FSK test audio as 'generator_fsk_test.wav'")
