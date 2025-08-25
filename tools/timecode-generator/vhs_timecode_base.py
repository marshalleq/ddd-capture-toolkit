#!/usr/bin/env python3
"""
VHS Timecode Base Class - Shared Frame Generation Logic

This module contains the shared frame generation logic used by both
the standard and efficient VHS timecode generators.
"""

import cv2
import numpy as np
import json
from datetime import datetime


class VHSTimecodeBase:
    def __init__(self, format_type="PAL", width=720, height=576):
        """
        Initialize VHS timecode base class
        
        Args:
            format_type: "PAL" (25fps) or "NTSC" (29.97fps)
            width: Video width (720 for VHS standard)
            height: Video height (576 for PAL, 480 for NTSC)
        """
        self.format_type = format_type.upper()
        
        if self.format_type == "PAL":
            self.fps = 25.0
            self.width = width
            self.height = height if height else 576
        elif self.format_type == "NTSC":
            self.fps = 29.97
            self.width = width
            self.height = height if height else 480
        else:
            raise ValueError("Format must be PAL or NTSC")
        
        # Audio parameters optimized for VHS
        self.sample_rate = 48000  # High quality for encoding
        self.audio_channels = 2   # Stereo: Left=timecode, Right=sync pulse
        
        # Timecode encoding parameters
        self.base_frequency = 1000  # 1kHz base tone
        self.bit_duration = 0.001   # 1ms per bit (1000 bits/second)
        self.sync_frequency = 2000  # 2kHz sync tone
        
        # Visual parameters optimized for VHS quality
        self.font_scale = 3.0
        self.font_thickness = 8
        self.text_color = (255, 255, 255)  # White text
        self.bg_color = (0, 0, 0)          # Black background
        
        # Corner marker colors for robust frame detection (BGR format)
        self.corner_color_primary = (0, 0, 255)    # Red corners for fixed reference
        self.corner_color_secondary = (255, 0, 0)  # Blue corners for frame pattern

    def generate_frame_image(self, frame_number, timecode_str):
        """
        Generate a single frame with visual timecode
        
        Args:
            frame_number: Current frame number
            timecode_str: Formatted timecode string (HH:MM:SS:FF)
            
        Returns:
            numpy array: BGR image for the frame
        """
        # Create black background
        frame = np.zeros((self.height, self.width, 3), dtype=np.uint8)
        frame[:] = self.bg_color
        
        # Add main timecode display (large, centered)
        font = cv2.FONT_HERSHEY_SIMPLEX
        
        # Calculate text size for centering
        (text_width, text_height), baseline = cv2.getTextSize(
            timecode_str, font, self.font_scale, self.font_thickness
        )
        
        # Center the timecode
        x = (self.width - text_width) // 2
        y = (self.height + text_height) // 2
        
        cv2.putText(frame, timecode_str, (x, y), font, 
                   self.font_scale, self.text_color, self.font_thickness)
        
        # Add frame number in top-left corner (below binary blocks)
        frame_text = f"Frame: {frame_number:06d}"
        cv2.putText(frame, frame_text, (20, 70), font, 
                   1.0, self.text_color, 2)
        
        # Add format info in top-right corner (below binary blocks)
        format_text = f"{self.format_type} {self.fps}fps"
        (fw, fh), _ = cv2.getTextSize(format_text, font, 0.7, 2)
        cv2.putText(frame, format_text, (self.width - fw - 20, 70), font, 
                   0.7, self.text_color, 2)
        
        # Add machine-readable patterns for extra reliability
        self._add_sync_patterns(frame, frame_number)
        
        return frame
    
    def _add_sync_patterns(self, frame, frame_number):
        """
        Add machine-readable sync patterns to frame
        
        Args:
            frame: Frame image to modify
            frame_number: Current frame number
        """
        # Add binary representation as visual blocks (top edge, between corner markers)
        # This provides a backup machine-readable timecode
        binary = format(frame_number, '032b')  # 32-bit binary
        
        # Position binary blocks between corner squares (40px margins)
        available_width = self.width - 80  # Total width minus 40px corners
        block_width = available_width // 32
        start_offset = 40  # Start after left corner
        
        for i, bit in enumerate(binary):
            x_start = start_offset + (i * block_width)
            x_end = min(x_start + block_width, self.width - 40)  # Stop before right corner
            
            # White for 1, dark gray for 0 (still visible)
            color = (255, 255, 255) if bit == '1' else (64, 64, 64)
            cv2.rectangle(frame, (x_start, 0), (x_end, 20), color, -1)
        
        # Add sync markers in corners for frame detection
        marker_size = 40
        
        # Top-left and bottom-right: red squares for primary corner markers
        cv2.rectangle(frame, (0, 0), (marker_size, marker_size), self.corner_color_primary, -1)
        cv2.rectangle(frame, (self.width - marker_size, self.height - marker_size), 
                     (self.width, self.height), self.corner_color_primary, -1)
        
        # Top-right and bottom-left: blue squares for secondary corner markers
        cv2.rectangle(frame, (self.width - marker_size, 0), 
                     (self.width, marker_size), self.corner_color_secondary, -1)
        cv2.rectangle(frame, (0, self.height - marker_size), 
                     (marker_size, self.height), self.corner_color_secondary, -1)
    
    def generate_audio_timecode(self, frame_number, duration_seconds):
        """
        Generate audio timecode for a frame
        
        Args:
            frame_number: Current frame number
            duration_seconds: Duration of this frame in seconds
            
        Returns:
            tuple: (left_channel, right_channel) audio arrays
        """
        samples_per_frame = int(self.sample_rate * duration_seconds)
        
        # Left channel: Encoded frame number using FSK (Frequency Shift Keying)
        left_channel = self._generate_fsk_timecode(frame_number, samples_per_frame)
        
        # Right channel: Simple sync pulse at frame boundary
        right_channel = self._generate_sync_pulse(samples_per_frame)
        
        return left_channel, right_channel
    
    def _generate_fsk_timecode(self, frame_number, samples):
        """
        Generate FSK-encoded timecode in audio
        
        Args:
            frame_number: Frame number to encode
            samples: Number of audio samples to generate
            
        Returns:
            numpy array: Audio samples for left channel
        """
        # Encode frame number as binary
        binary = format(frame_number, '024b')  # 24-bit frame number
        
        # Add 8-bit checksum (simple XOR of all bits)
        checksum = 0
        for bit in binary:
            checksum ^= int(bit)
        checksum_bin = format(checksum, '08b')
        
        # Complete data: 24-bit frame + 8-bit checksum = 32 bits
        data_bits = binary + checksum_bin
        
        # Generate FSK audio
        audio = np.zeros(samples)
        bit_samples = samples // len(data_bits)
        
        for i, bit in enumerate(data_bits):
            start_sample = i * bit_samples
            end_sample = min(start_sample + bit_samples, samples)
            
            # Frequency shift keying: 1000Hz for '0', 1200Hz for '1'
            frequency = self.base_frequency if bit == '0' else self.base_frequency + 200
            
            # Calculate exact number of cycles to fit in the bit duration
            bit_duration_seconds = (end_sample - start_sample) / self.sample_rate
            cycles_in_bit = frequency * bit_duration_seconds
            
            # Generate time array that ensures exact frequency
            n_samples = end_sample - start_sample
            # Create phase values that complete exact cycles
            phase = np.linspace(0, 2 * np.pi * cycles_in_bit, n_samples, False)
            
            # Generate sine wave with exact frequency
            tone = np.sin(phase)
            
            # Apply soft envelope (first/last 10% of bit duration)
            envelope_samples = len(tone) // 10
            if envelope_samples > 0:
                # Fade in
                tone[:envelope_samples] *= np.linspace(0, 1, envelope_samples)
                # Fade out
                tone[-envelope_samples:] *= np.linspace(1, 0, envelope_samples)
            
            audio[start_sample:end_sample] = tone * 0.5  # 50% amplitude
        
        return audio
    
    def _generate_sync_pulse(self, samples):
        """
        Generate sync pulse for right channel
        
        Args:
            samples: Number of audio samples to generate
            
        Returns:
            numpy array: Audio samples for right channel
        """
        # Generate a short 2kHz pulse at the beginning of each frame
        pulse_duration = 0.01  # 10ms pulse
        pulse_samples = int(self.sample_rate * pulse_duration)
        
        audio = np.zeros(samples)
        
        if pulse_samples < samples:
            t = np.linspace(0, pulse_duration, pulse_samples, False)
            pulse = np.sin(2 * np.pi * self.sync_frequency * t) * 0.7
            
            # Apply envelope to pulse
            envelope = np.exp(-t * 50)  # Exponential decay
            pulse *= envelope
            
            audio[:pulse_samples] = pulse
        
        return audio
    
    def frame_to_timecode(self, frame_number):
        """
        Convert frame number to timecode string
        
        Args:
            frame_number: Frame number
            
        Returns:
            str: Formatted timecode (HH:MM:SS:FF)
        """
        if self.format_type == "PAL":
            fps = 25
        else:  # NTSC
            fps = 30  # Use 30 for display, even though actual is 29.97
        
        total_seconds = frame_number // fps
        frame_remainder = frame_number % fps
        
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60
        
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}:{frame_remainder:02d}"
    
    def generate_metadata(self, total_frames, duration_seconds, generator_version="1.0"):
        """
        Generate metadata dictionary with timing information
        
        Args:
            total_frames: Total number of frames
            duration_seconds: Duration in seconds
            generator_version: Version string for the generator
            
        Returns:
            dict: Metadata dictionary
        """
        return {
            "timecode_metadata": {
                "generator": f"VHS Timecode Generator v{generator_version}",
                "method_version": "1.0",  # For tracking encoding method compatibility
                "timestamp": datetime.now().isoformat(),
                "format": self.format_type,
                "fps": self.fps,
                "resolution": f"{self.width}x{self.height}",
                "duration_seconds": duration_seconds,
                "total_frames": total_frames
            },
            "encoding_parameters": {
                "audio_sample_rate": self.sample_rate,
                "base_frequency": self.base_frequency,
                "sync_frequency": self.sync_frequency,
                "bit_duration": self.bit_duration,
                "bits_per_frame": 32  # 24-bit frame + 8-bit checksum
            },
            "corner_markers": {
                "primary_color_bgr": list(self.corner_color_primary),
                "secondary_color_bgr": list(self.corner_color_secondary),
                "marker_size_pixels": 40,
                "positions": {
                    "primary": ["top-left", "bottom-right"],
                    "secondary": ["top-right", "bottom-left"]
                }
            },
            "usage_instructions": {
                "left_channel": "FSK-encoded frame numbers (1000Hz='0', 1200Hz='1')",
                "right_channel": "Sync pulses at frame boundaries (2000Hz)",
                "visual_timecode": "Human-readable HH:MM:SS:FF format",
                "binary_strip": "Machine-readable frame number (top edge)",
                "sync_markers": "Colored corner markers for frame detection and alignment correction"
            }
        }
    
    def save_metadata(self, metadata, metadata_path):
        """
        Save metadata to JSON file
        
        Args:
            metadata: Metadata dictionary
            metadata_path: Path to save metadata file
        """
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)
