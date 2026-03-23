#!/usr/bin/env python3

import subprocess
import numpy as np
import os
import tempfile
import sys

def extract_audio_segment(video_or_audio_file, start_seconds=0, duration_seconds=60, output_sample_rate=48000):
    """
    Extract a segment of audio from video or audio file for analysis
    """
    temp_wav = tempfile.mktemp(suffix='.wav')
    
    ffmpeg_cmd = [
        'ffmpeg', '-y', '-v', 'quiet',
        '-i', video_or_audio_file,
        '-ss', str(start_seconds),
        '-t', str(duration_seconds),
        '-vn',  # No video
        '-acodec', 'pcm_s16le',
        '-ar', str(output_sample_rate),
        '-ac', '1',  # Mono
        temp_wav
    ]
    
    result = subprocess.run(ffmpeg_cmd, capture_output=True)
    if result.returncode != 0:
        print(f"Error extracting audio: {result.stderr.decode()}")
        return None
    
    return temp_wav

def detect_tone_bursts(wav_file, expected_frequency=1000, burst_duration=1.0, silence_duration=1.0):
    """
    Detect 1kHz tone bursts in audio and calculate timing
    """
    try:
        from scipy.io import wavfile
        from scipy import signal
        
        # Read audio file
        sample_rate, audio_data = wavfile.read(wav_file)
        
        # Convert to mono if stereo
        if len(audio_data.shape) > 1:
            audio_data = audio_data[:, 0]
        
        print(f"Analyzing {len(audio_data)/sample_rate:.1f}s of audio at {sample_rate}Hz")
        
        # Calculate window size for analysis
        window_size = int(0.1 * sample_rate)  # 100ms windows
        hop_size = int(0.05 * sample_rate)    # 50ms overlap
        
        # Detect energy levels in each window
        energy_levels = []
        times = []
        
        for i in range(0, len(audio_data) - window_size, hop_size):
            window = audio_data[i:i + window_size]
            
            # Calculate FFT to find 1kHz component
            fft = np.fft.rfft(window)
            freqs = np.fft.rfftfreq(len(window), 1/sample_rate)
            
            # Find energy around 1kHz (±50Hz tolerance)
            freq_mask = (freqs >= expected_frequency - 50) & (freqs <= expected_frequency + 50)
            tone_energy = np.sum(np.abs(fft[freq_mask])**2)
            
            energy_levels.append(tone_energy)
            times.append(i / sample_rate)
        
        energy_levels = np.array(energy_levels)
        times = np.array(times)
        
        # Normalize energy levels
        if len(energy_levels) > 0:
            energy_levels = energy_levels / np.max(energy_levels)
        
        # Detect tone bursts (energy above threshold)
        threshold = 0.3
        tone_detected = energy_levels > threshold
        
        # Find tone burst start times
        burst_starts = []
        in_burst = False
        
        for i, is_tone in enumerate(tone_detected):
            if is_tone and not in_burst:
                burst_starts.append(times[i])
                in_burst = True
            elif not is_tone and in_burst:
                in_burst = False
        
        print(f"Detected {len(burst_starts)} tone bursts")
        
        if len(burst_starts) >= 2:
            # Calculate intervals between bursts
            intervals = np.diff(burst_starts)
            expected_interval = burst_duration + silence_duration  # Should be 2.0 seconds
            
            print(f"Expected interval: {expected_interval:.1f}s")
            print(f"Average detected interval: {np.mean(intervals):.3f}s")
            print(f"First burst at: {burst_starts[0]:.3f}s")
            
            # Calculate offset (how far off is the first burst from expected timing)
            # Assuming the pattern should start at t=0
            offset = burst_starts[0] % expected_interval
            if offset > expected_interval / 2:
                offset -= expected_interval
            
            return offset, burst_starts, intervals
        
        return None, [], []
        
    except ImportError:
        print("ERROR: This function requires scipy. Install with: pip install scipy")
        return None, [], []
    except Exception as e:
        print(f"ERROR analyzing audio: {e}")
        return None, [], []

def analyze_capture_timing(capture_file):
    """
    Analyze captured audio file to determine A/V sync offset
    """
    print(f"Analyzing capture file: {capture_file}")
    
    if not os.path.exists(capture_file):
        print(f"ERROR: File not found: {capture_file}")
        return None
    
    # Extract first 60 seconds for analysis
    temp_wav = extract_audio_segment(capture_file, start_seconds=10, duration_seconds=60)
    if not temp_wav:
        return None
    
    try:
        # Detect tone patterns
        offset, burst_starts, intervals = detect_tone_bursts(temp_wav)
        
        if offset is not None:
            print(f"\n=== TIMING ANALYSIS RESULTS ===")
            print(f"Detected timing offset: {offset:.3f}s ({offset*1000:.0f}ms)")
            
            if abs(offset) < 0.01:  # Less than 10ms
                print(" Timing is very good (< 10ms offset)")
            elif abs(offset) < 0.05:  # Less than 50ms
                print(" Timing is acceptable (< 50ms offset)")
            else:
                print(" Significant timing offset detected")
            
            return offset
        else:
            print(" Could not detect tone pattern in captured audio")
            print("Make sure the test pattern was recorded properly")
            return None
            
    finally:
        if temp_wav and os.path.exists(temp_wav):
            os.remove(temp_wav)

def main():
    if len(sys.argv) != 2:
        print(f"Usage: {sys.executable} audio_alignment_analyzer.py <capture_file>")
        print(f"Example: {sys.executable} audio_alignment_analyzer.py av_alignment_capture.flac")
        sys.exit(1)
    
    capture_file = sys.argv[1]
    offset = analyze_capture_timing(capture_file)
    
    if offset is not None:
        print(f"\nRecommended delay adjustment: {-offset:.3f}s")
        if offset > 0:
            print("Audio is ahead of video - increase delay")
        else:
            print("Audio is behind video - decrease delay")
    else:
        print("\nCould not determine timing offset")

if __name__ == "__main__":
    main()
