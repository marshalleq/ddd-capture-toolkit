#!/usr/bin/env python3
"""
FSK Audio Diagnostic Tool

This script analyzes the generated FSK audio to determine the distribution of
frame boundary detections and the alignment of expected frames.
"""

import numpy as np
import matplotlib.pyplot as plt
from scipy.io import wavfile
import os
import sys

# Add the timecode generator directory to path
sys.path.append(os.path.join(os.path.dirname(os.path.dirname(__file__)), 'tools', 'timecode-generator'))

# Define the FSK decoder from the robust timecode library
from vhs_timecode_robust import VHSTimecodeRobust

# Load the extracted timecode audio file
audio_path = '/tmp/cycle_validation_lvyr7jz0/timecode_only.wav'

# Initialize FSK decoder
decoder = VHSTimecodeRobust(format_type='PAL')

# Function to plot timing analysis
def plot_fsk_analysis(audio_samples, fsk_frames):
    plt.figure(figsize=(12, 6))

    # Visualize the detected frame starts
    positions = [pos / 48000 for pos, _, _ in fsk_frames]
    plt.hist(positions, bins=100, color='cyan', label='Detected Frame Positions')

    # Expected frame starts
    expected_positions = np.arange(0, len(audio_samples) / 48000, decoder.samples_per_frame / 48000)
    plt.vlines(expected_positions, ymin=0, ymax=plt.ylim()[1], color='magenta', linewidth=0.5, label='Expected Frames')

    plt.title('FSK Frame Timing Analysis')
    plt.xlabel('Time (seconds)')
    plt.ylabel('Detected Counts')
    plt.legend()
    plt.grid(True)
    plt.show()

# Load the audio samples
try:
    sample_rate, audio_data = wavfile.read(audio_path)
except Exception as e:
    raise RuntimeError(f"Failed to read audio file {audio_path}: {e}")

print(f"Loaded {len(audio_data)} audio samples at {sample_rate}Hz")

# Decode the FSK audio
decoded_fsk_frames = decoder.decode_fsk_audio(audio_data, strict=False)

print(f"Decoded {len(decoded_fsk_frames)} FSK frames")

# Plot the analysis
plot_fsk_analysis(audio_data, decoded_fsk_frames)

# Output detected frames for inspection
for i, (sample_pos, frame_id, confidence) in enumerate(decoded_fsk_frames[:10]):
    time_pos = sample_pos / sample_rate
    print(f"Frame {i+1}: Start @ {sample_pos} ({time_pos:.3f}s), Frame ID: {frame_id}, Confidence: {confidence:.2f}")
