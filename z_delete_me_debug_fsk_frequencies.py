#!/usr/bin/env python3
"""
Debug FSK frequencies in captured timecode audio

This tool analyzes the captured audio to find the actual FSK frequencies
and test different frequency pairs for timecode decoding.
"""

import numpy as np
import subprocess
import sys
import matplotlib.pyplot as plt
from collections import Counter

def load_audio_data(audio_file, sample_rate=48000):
    """Load audio data using sox"""
    try:
        cmd = ['sox', audio_file, '-t', 'f32', '-r', str(sample_rate), '-']
        result = subprocess.run(cmd, capture_output=True, check=True)
        audio_raw = np.frombuffer(result.stdout, dtype=np.float32)
        
        if len(audio_raw) % 2 == 0:
            return audio_raw.reshape(-1, 2)  # Stereo
        else:
            return audio_raw.reshape(-1, 1)  # Mono
    except Exception as e:
        print(f"Error loading audio: {e}")
        return None

def analyze_fsk_frequencies(audio_channel, sample_rate=48000, expected_fps=25):
    """Analyze audio to find the actual FSK frequencies being used"""
    print("Analyzing FSK frequencies in captured audio...")
    
    # Expected parameters
    frame_duration = sample_rate / expected_fps  # samples per frame
    bits_per_frame = 32
    samples_per_bit = int(frame_duration / bits_per_frame)
    
    print(f"Expected: {frame_duration:.0f} samples/frame, {samples_per_bit:.0f} samples/bit")
    
    # Analyze multiple segments to find frequency patterns
    frequencies_found = []
    
    # Take samples from first 10 frames to get good statistics
    max_frames = min(10, len(audio_channel) // int(frame_duration))
    
    for frame_idx in range(max_frames):
        frame_start = int(frame_idx * frame_duration)
        frame_end = int(frame_start + frame_duration)
        
        if frame_end > len(audio_channel):
            break
            
        frame_audio = audio_channel[frame_start:frame_end]
        
        # Analyze each bit in this frame
        for bit_idx in range(bits_per_frame):
            bit_start = bit_idx * samples_per_bit
            bit_end = bit_start + samples_per_bit
            
            if bit_end > len(frame_audio):
                break
                
            bit_audio = frame_audio[bit_start:bit_end]
            
            if len(bit_audio) < 10:
                continue
                
            # Find peak frequency using FFT
            windowed = bit_audio * np.hanning(len(bit_audio))
            fft_result = np.fft.fft(windowed)
            freqs = np.fft.fftfreq(len(bit_audio), d=1/sample_rate)
            
            positive_freqs = freqs[:len(freqs)//2]
            positive_fft = np.abs(fft_result[:len(fft_result)//2])
            
            if len(positive_fft) > 0:
                peak_idx = np.argmax(positive_fft)
                peak_freq = abs(positive_freqs[peak_idx])
                
                # Only consider reasonable FSK frequencies
                if 500 < peak_freq < 2000:
                    frequencies_found.append(peak_freq)
    
    # Analyze frequency distribution
    if len(frequencies_found) < 10:
        print("Not enough frequency data found!")
        return None, None
    
    freq_array = np.array(frequencies_found)
    
    # Create histogram to find the two main frequency clusters
    hist, bin_edges = np.histogram(freq_array, bins=100, range=(500, 2000))
    bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2
    
    # Find peaks in histogram
    peak_indices = []
    for i in range(1, len(hist)-1):
        if hist[i] > hist[i-1] and hist[i] > hist[i+1] and hist[i] > 5:  # Local maximum with min count
            peak_indices.append(i)
    
    # Sort peaks by height and take top 2
    peak_indices = sorted(peak_indices, key=lambda i: hist[i], reverse=True)[:2]
    
    if len(peak_indices) < 2:
        print("Could not find two distinct frequency peaks!")
        print("Frequency distribution:")
        freq_counter = Counter(np.round(freq_array, 0).astype(int))
        for freq, count in freq_counter.most_common(10):
            print(f"  {freq}Hz: {count} occurrences")
        return None, None
    
    # Get the two main frequencies
    freq_0 = bin_centers[peak_indices[0]]
    freq_1 = bin_centers[peak_indices[1]]
    
    # Ensure freq_0 < freq_1 (0 should be lower frequency)
    if freq_0 > freq_1:
        freq_0, freq_1 = freq_1, freq_0
    
    print(f"\nFrequency analysis results:")
    print(f"  Lower frequency (for '0'): {freq_0:.1f}Hz ({hist[peak_indices[1 if freq_0 == bin_centers[peak_indices[1]] else 0]]} occurrences)")
    print(f"  Higher frequency (for '1'): {freq_1:.1f}Hz ({hist[peak_indices[0 if freq_0 == bin_centers[peak_indices[0]] else 1]]} occurrences)")
    print(f"  Frequency ratio: {freq_1/freq_0:.3f}")
    print(f"  Expected ratio (1200/1000): 1.200")
    
    return freq_0, freq_1

def test_fsk_decoding(audio_channel, freq_0, freq_1, sample_rate=48000, expected_fps=25):
    """Test FSK decoding with specific frequencies"""
    print(f"\nTesting FSK decoding with {freq_0:.1f}Hz/'0' and {freq_1:.1f}Hz/'1'...")
    
    frame_duration = int(sample_rate / expected_fps)
    bits_per_frame = 32
    samples_per_bit = frame_duration // bits_per_frame
    
    # Test first few frames
    decoded_frames = []
    
    for frame_idx in range(min(5, len(audio_channel) // frame_duration)):
        frame_start = frame_idx * frame_duration
        frame_end = frame_start + frame_duration
        
        if frame_end > len(audio_channel):
            break
            
        frame_audio = audio_channel[frame_start:frame_end]
        
        # Decode this frame
        bits = []
        for bit_idx in range(bits_per_frame):
            bit_start = bit_idx * samples_per_bit
            bit_end = bit_start + samples_per_bit
            
            if bit_end > len(frame_audio):
                break
                
            bit_audio = frame_audio[bit_start:bit_end]
            
            # FFT analysis
            windowed = bit_audio * np.hanning(len(bit_audio))
            fft_result = np.fft.fft(windowed)
            freqs = np.fft.fftfreq(len(bit_audio), d=1/sample_rate)
            
            positive_freqs = freqs[:len(freqs)//2]
            positive_fft = np.abs(fft_result[:len(fft_result)//2])
            
            # Check amplitudes at our two frequencies
            freq_0_range = (freq_0 - 50, freq_0 + 50)
            freq_1_range = (freq_1 - 50, freq_1 + 50)
            
            mask_0 = (positive_freqs >= freq_0_range[0]) & (positive_freqs <= freq_0_range[1])
            mask_1 = (positive_freqs >= freq_1_range[0]) & (positive_freqs <= freq_1_range[1])
            
            amp_0 = np.max(positive_fft[mask_0]) if np.any(mask_0) else 0
            amp_1 = np.max(positive_fft[mask_1]) if np.any(mask_1) else 0
            
            # Decode bit
            if amp_0 > amp_1 and amp_0 > 0.1:
                bits.append('0')
            elif amp_1 > amp_0 and amp_1 > 0.1:
                bits.append('1')
            else:
                bits.append('?')  # Unclear
        
        if len(bits) == 32:
            # Try to decode frame number
            frame_bits = bits[:24]
            checksum_bits = bits[24:]
            
            # Check if we have valid bits
            if '?' not in frame_bits and '?' not in checksum_bits:
                try:
                    frame_number = int(''.join(frame_bits), 2)
                    checksum = int(''.join(checksum_bits), 2)
                    
                    # Verify checksum
                    calc_checksum = 0
                    for bit in frame_bits:
                        calc_checksum ^= int(bit)
                    
                    if calc_checksum == checksum:
                        decoded_frames.append((frame_idx, frame_number, "VALID"))
                        print(f"  Frame {frame_idx}: decoded frame_id {frame_number} (checksum valid)")
                    else:
                        decoded_frames.append((frame_idx, frame_number, "BAD_CHECKSUM"))
                        print(f"  Frame {frame_idx}: decoded frame_id {frame_number} (checksum failed: got {checksum}, expected {calc_checksum})")
                except ValueError:
                    decoded_frames.append((frame_idx, None, "DECODE_ERROR"))
                    print(f"  Frame {frame_idx}: could not decode binary data")
            else:
                unclear_count = bits.count('?')
                decoded_frames.append((frame_idx, None, f"UNCLEAR_{unclear_count}"))
                print(f"  Frame {frame_idx}: {unclear_count} unclear bits out of 32")
        else:
            print(f"  Frame {frame_idx}: only decoded {len(bits)} bits")
    
    return decoded_frames

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python3 debug_fsk_frequencies.py <audio_file>")
        sys.exit(1)
    
    audio_file = sys.argv[1]
    print(f"Analyzing FSK frequencies in: {audio_file}")
    
    # Load audio
    audio_data = load_audio_data(audio_file)
    if audio_data is None:
        print("Failed to load audio data!")
        sys.exit(1)
    
    print(f"Loaded audio: {audio_data.shape}")
    
    # Use left channel for FSK analysis
    left_channel = audio_data[:, 0] if audio_data.ndim > 1 else audio_data
    
    # Analyze frequencies
    freq_0, freq_1 = analyze_fsk_frequencies(left_channel)
    
    if freq_0 and freq_1:
        # Test decoding with found frequencies
        results = test_fsk_decoding(left_channel, freq_0, freq_1)
        
        print(f"\nDecoding test summary:")
        valid_count = sum(1 for _, _, status in results if status == "VALID")
        print(f"  Successfully decoded frames: {valid_count}/{len(results)}")
        
        if valid_count > 0:
            print(f"\nRecommendation: Use frequencies {freq_0:.1f}Hz and {freq_1:.1f}Hz for FSK decoding")
        else:
            print("\nFSK decoding failed - timecode may not be properly recorded")
    else:
        print("Could not determine FSK frequencies from audio data")
