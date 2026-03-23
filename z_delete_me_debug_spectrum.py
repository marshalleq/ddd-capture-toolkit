#!/usr/bin/env python3
"""
Detailed spectrum analysis of captured timecode audio

This tool provides a comprehensive frequency analysis to understand
what frequencies are actually present in the captured audio.
"""

import numpy as np
import subprocess
import sys
import matplotlib.pyplot as plt

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

def analyze_frequency_spectrum(audio_channel, sample_rate=48000, duration_to_analyze=5.0):
    """Analyze the frequency spectrum of audio"""
    print(f"Analyzing frequency spectrum of first {duration_to_analyze} seconds...")
    
    # Take first few seconds for analysis
    samples_to_analyze = int(duration_to_analyze * sample_rate)
    if len(audio_channel) > samples_to_analyze:
        audio_segment = audio_channel[:samples_to_analyze]
    else:
        audio_segment = audio_channel
    
    print(f"Analyzing {len(audio_segment)} samples ({len(audio_segment)/sample_rate:.1f} seconds)")
    
    # Apply window and compute FFT
    windowed = audio_segment * np.hanning(len(audio_segment))
    fft_result = np.fft.fft(windowed)
    freqs = np.fft.fftfreq(len(audio_segment), d=1/sample_rate)
    
    # Only positive frequencies
    positive_freqs = freqs[:len(freqs)//2]
    positive_fft = np.abs(fft_result[:len(fft_result)//2])
    
    # Find peaks in the 500-2000Hz range (where FSK should be)
    fsk_range_mask = (positive_freqs >= 500) & (positive_freqs <= 2000)
    fsk_freqs = positive_freqs[fsk_range_mask]
    fsk_amps = positive_fft[fsk_range_mask]
    
    if len(fsk_amps) == 0:
        print("No frequencies found in FSK range!")
        return
    
    # Find prominent peaks
    # Look for local maxima that are significantly above background
    threshold = np.max(fsk_amps) * 0.1  # 10% of max amplitude
    
    peaks = []
    for i in range(1, len(fsk_amps)-1):
        if (fsk_amps[i] > fsk_amps[i-1] and 
            fsk_amps[i] > fsk_amps[i+1] and 
            fsk_amps[i] > threshold):
            peaks.append((fsk_freqs[i], fsk_amps[i]))
    
    # Sort by amplitude
    peaks.sort(key=lambda x: x[1], reverse=True)
    
    print(f"\nFrequency spectrum analysis:")
    print(f"  Max amplitude in FSK range: {np.max(fsk_amps):.2f}")
    print(f"  Threshold for peak detection: {threshold:.2f}")
    print(f"  Number of peaks found: {len(peaks)}")
    
    print(f"\nTop 10 frequency peaks (500-2000Hz range):")
    for i, (freq, amp) in enumerate(peaks[:10]):
        print(f"  {i+1:2d}. {freq:7.1f}Hz - amplitude {amp:8.2f}")
    
    # Check for expected FSK frequencies
    expected_low = 800  # What we think should be there for '0'
    expected_high = 1600  # What we think should be there for '1'
    
    print(f"\nLooking for expected FSK frequencies:")
    
    # Check for frequency near 800Hz
    low_candidates = [(f, a) for f, a in peaks if 750 <= f <= 850]
    if low_candidates:
        best_low = max(low_candidates, key=lambda x: x[1])
        print(f"  Near 800Hz: Found {best_low[0]:.1f}Hz (amplitude {best_low[1]:.2f})")
    else:
        print(f"  Near 800Hz: No significant peak found")
    
    # Check for frequency near 1600Hz
    high_candidates = [(f, a) for f, a in peaks if 1500 <= f <= 1700]
    if high_candidates:
        best_high = max(high_candidates, key=lambda x: x[1])
        print(f"  Near 1600Hz: Found {best_high[0]:.1f}Hz (amplitude {best_high[1]:.2f})")
    else:
        print(f"  Near 1600Hz: No significant peak found")
    
    return peaks

def analyze_bit_by_bit(audio_channel, sample_rate=48000, expected_fps=25):
    """Analyze individual bits to see frequency content"""
    print(f"\nAnalyzing individual bits for first few frames...")
    
    frame_duration = int(sample_rate / expected_fps)
    bits_per_frame = 32
    samples_per_bit = frame_duration // bits_per_frame
    
    print(f"Frame duration: {frame_duration} samples")
    print(f"Samples per bit: {samples_per_bit}")
    
    # Analyze first 2 frames, first 10 bits each
    for frame_idx in range(2):
        frame_start = frame_idx * frame_duration
        frame_end = frame_start + frame_duration
        
        if frame_end > len(audio_channel):
            break
            
        print(f"\n--- Frame {frame_idx} ---")
        frame_audio = audio_channel[frame_start:frame_end]
        
        for bit_idx in range(min(10, bits_per_frame)):  # First 10 bits
            bit_start = bit_idx * samples_per_bit
            bit_end = bit_start + samples_per_bit
            
            if bit_end > len(frame_audio):
                break
                
            bit_audio = frame_audio[bit_start:bit_end]
            
            if len(bit_audio) < 10:
                continue
            
            # FFT for this bit
            windowed = bit_audio * np.hanning(len(bit_audio))
            fft_result = np.fft.fft(windowed)
            freqs = np.fft.fftfreq(len(bit_audio), d=1/sample_rate)
            
            positive_freqs = freqs[:len(freqs)//2]
            positive_fft = np.abs(fft_result[:len(fft_result)//2])
            
            # Find peak frequency
            if len(positive_fft) > 0:
                peak_idx = np.argmax(positive_fft)
                peak_freq = abs(positive_freqs[peak_idx])
                peak_amp = positive_fft[peak_idx]
                
                # Also check specific frequency ranges
                range_800 = (positive_freqs >= 750) & (positive_freqs <= 850)
                range_1600 = (positive_freqs >= 1500) & (positive_freqs <= 1700)
                
                amp_800 = np.max(positive_fft[range_800]) if np.any(range_800) else 0
                amp_1600 = np.max(positive_fft[range_1600]) if np.any(range_1600) else 0
                
                print(f"  Bit {bit_idx:2d}: peak={peak_freq:6.1f}Hz (amp={peak_amp:6.2f}), 800Hz={amp_800:6.2f}, 1600Hz={amp_1600:6.2f}")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python3 debug_spectrum.py <audio_file>")
        sys.exit(1)
    
    audio_file = sys.argv[1]
    print(f"Detailed spectrum analysis of: {audio_file}")
    
    # Load audio
    audio_data = load_audio_data(audio_file)
    if audio_data is None:
        print("Failed to load audio data!")
        sys.exit(1)
    
    print(f"Loaded audio: {audio_data.shape}")
    
    # Use left channel for analysis
    left_channel = audio_data[:, 0] if audio_data.ndim > 1 else audio_data
    
    # Overall spectrum analysis
    peaks = analyze_frequency_spectrum(left_channel)
    
    # Bit-by-bit analysis
    analyze_bit_by_bit(left_channel)
