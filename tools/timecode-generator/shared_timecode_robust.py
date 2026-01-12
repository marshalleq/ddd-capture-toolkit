#!/usr/bin/env python3
"""
Shared Robust Timecode System - Improved FSK encoding for VHS and MP4 validation

This shared module provides robust FSK timecode encoding and decoding capabilities
for both VHS capture validation and MP4 timecode validation.

Key improvements:
1. Wider frequency separation (800Hz vs 1600Hz instead of 1000Hz vs 1200Hz)
2. Non-overlapping detection ranges with significant guard bands
3. Enhanced bit detection using multiple analysis methods
4. Improved checksum and error detection
5. Mono audio encoding (eliminates stereo channel confusion)
6. Dual-mode operation: strict (MP4) and tolerant (VHS)
"""

import cv2
import numpy as np
import subprocess
import json
from datetime import datetime

class SharedTimecodeRobust:
    def __init__(self, format_type="PAL", width=720, height=576):
        """
        Initialize robust VHS timecode system
        
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
        
        # Audio parameters optimized for VHS robustness
        self.sample_rate = 48000
        self.audio_channels = 1  # MONO - eliminates stereo confusion

        # V2 ROBUST frequency selection for VHS linear audio compatibility
        # Lower frequencies: 400Hz for '0', 800Hz for '1' (2:1 ratio maintained)
        # Both frequencies well within VHS linear audio passband (100Hz - 10kHz)
        self.freq_0 = 400   # Low frequency for '0' bit
        self.freq_1 = 800   # High frequency for '1' bit (exactly double)
        self.freq_pilot = 1200  # Pilot tone for frame sync (not 400 or 800)

        # Detection ranges with significant guard bands
        self.freq_0_range = (300, 500)    # 200Hz bandwidth around 400Hz
        self.freq_1_range = (650, 950)    # 300Hz bandwidth around 800Hz
        self.freq_pilot_range = (1050, 1350)  # For pilot tone detection
        # Guard bands: 500-650Hz (150Hz), 950-1050Hz (100Hz)

        # V2 Bit timing - 16 bits per frame for larger blocks and longer bit duration
        self.samples_per_frame = int(self.sample_rate / self.fps)
        self.bits_per_frame = 16  # "10" + 12-bit frame + "01" = 16 bits
        self.samples_per_bit = self.samples_per_frame // self.bits_per_frame  # ~120 samples

        # Pilot tone timing (per frame)
        self.pilot_ratio = 0.10      # 10% of frame for pilot tone
        self.silence_ratio = 0.05   # 5% silence separator
        self.data_ratio = 0.80      # 80% for FSK data
        # Remaining 5% trailing silence
        
        # Visual parameters
        self.font_scale = 3.0
        self.font_thickness = 8
        self.text_color = (255, 255, 255)  # White text
        self.bg_color = (0, 0, 0)          # Black background

        # V2 Binary strip parameters
        self.strip_height = 60             # 3 rows of 20 pixels each
        self.strip_row_height = 20         # Height of each row
        self.strip_num_rows = 3            # Number of redundant rows
        self.strip_bg_color = (128, 128, 128)  # Mid-gray background (neutral)

        # V2 Bit colors (BGR format) - Color-based encoding for VHS robustness
        self.bit_1_color = (0, 0, 255)     # Red for '1' bit
        self.bit_0_color = (255, 0, 0)     # Blue for '0' bit

        # Corner marker colors (BGR format) - unchanged
        self.corner_color_primary = (0, 0, 255)    # Red corners (top-left, bottom-right)
        self.corner_color_secondary = (255, 0, 0)  # Blue corners (top-right, bottom-left)
        self.corner_size = 40              # Corner marker size in pixels

    def generate_frame_image(self, frame_number, timecode_str, frame_type='timecode',
                              countdown_value=0, frames_until_timecode=0,
                              countup_value=0, frames_since_timecode=0):
        """
        Generate a single frame with visual timecode and V2 encoding.

        Args:
            frame_number: Frame number within the section
            timecode_str: Display text (timecode or section label)
            frame_type: 'leader', 'countdown', 'timecode', 'leadout', 'separator'
            countdown_value: For countdown, seconds remaining (5,4,3,2,1)
            frames_until_timecode: For countdown, frames until timecode section starts
            countup_value: For leadout, seconds elapsed (1,2,3,4,5)
            frames_since_timecode: For leadout, frames since timecode section ended

        Returns:
            Frame image with V2 visual encoding
        """
        # Create background - use mid-gray for better visibility
        frame = np.zeros((self.height, self.width, 3), dtype=np.uint8)
        frame[:] = self.bg_color

        # Add main display (large, centered)
        font = cv2.FONT_HERSHEY_SIMPLEX

        # Calculate text size for centering
        (text_width, text_height), baseline = cv2.getTextSize(
            timecode_str, font, self.font_scale, self.font_thickness
        )

        # Center the display text
        x = (self.width - text_width) // 2
        y = (self.height + text_height) // 2

        cv2.putText(frame, timecode_str, (x, y), font,
                   self.font_scale, self.text_color, self.font_thickness)

        # Add section type indicator in top-left (below binary strip)
        section_label = frame_type.upper()
        if frame_type == 'countdown':
            section_label = f"COUNTDOWN: {countdown_value} ({frames_until_timecode} frames)"
        elif frame_type == 'leadout':
            section_label = f"LEAD-OUT: {countup_value} ({frames_since_timecode} frames)"
        elif frame_type == 'timecode':
            section_label = f"TIMECODE Frame: {frame_number:06d}"
        elif frame_type == 'leader':
            section_label = "LEADER (0xFFFF)"
        elif frame_type == 'separator':
            section_label = "SEPARATOR (0x0000)"

        cv2.putText(frame, section_label, (20, 90), font,
                   0.8, self.text_color, 2)

        # Add format info in top-right corner (below binary strip)
        format_text = f"{self.format_type} {self.fps}fps - V2 FSK"
        (fw, fh), _ = cv2.getTextSize(format_text, font, 0.7, 2)
        cv2.putText(frame, format_text, (self.width - fw - 20, 90), font,
                   0.7, self.text_color, 2)

        # Determine the correct countdown/countup value and frames count for sync patterns
        if frame_type == 'countdown':
            cv_val = countdown_value
            fc_val = frames_until_timecode
        elif frame_type == 'leadout':
            cv_val = countup_value
            fc_val = frames_since_timecode
        else:
            cv_val = 0
            fc_val = 0

        # Add V2 machine-readable patterns (binary strip + corners)
        self._add_sync_patterns(frame, frame_number, frame_type, cv_val, fc_val)

        return frame
    
    def get_bit_pattern(self, frame_number, frame_type='timecode', countdown_val=0, frames_count=0):
        """
        Get 16-bit pattern based on frame type.

        Args:
            frame_number: Frame number (for timecode type)
            frame_type: 'leader', 'countdown', 'timecode', 'leadout', 'separator'
            countdown_val: Countdown value 5,4,3,2,1 (for countdown type)
            frames_count: Frames until start or since end (for countdown/leadout)

        Returns:
            str: 16-bit binary string
        """
        if frame_type == 'leader' or frame_type == 'tail':
            # All ones - 0xFFFF
            return '1111111111111111'
        elif frame_type == 'separator':
            # All zeros - 0x0000
            return '0000000000000000'
        elif frame_type == 'countdown':
            # "11" prefix + 4-bit countdown value + 10-bit frames remaining
            countdown_bits = format(min(countdown_val, 15), '04b')
            frames_bits = format(min(frames_count, 1023), '010b')
            return f'11{countdown_bits}{frames_bits}'
        elif frame_type == 'leadout':
            # "00" prefix + 4-bit count-up value + 10-bit frames since end
            countup_bits = format(min(countdown_val, 15), '04b')
            frames_bits = format(min(frames_count, 1023), '010b')
            return f'00{countup_bits}{frames_bits}'
        else:  # timecode
            # "10" prefix + 12-bit frame number + "01" suffix
            # 12 bits supports 4096 frames = 164 seconds at 25fps
            frame_bits = format(min(frame_number, 4095), '012b')
            return f'10{frame_bits}01'

    def _add_sync_patterns(self, frame, frame_number, frame_type='timecode', countdown_val=0, frames_count=0):
        """
        Add V2 machine-readable sync patterns to frame.

        Features:
        - 16 bits (40 pixels each) instead of 32 bits (20 pixels each)
        - 3 vertical rows for redundancy
        - Color-based encoding: Red for '1', Blue for '0'
        - Mid-gray background (neutral for VHS degradation)
        """
        # Get 16-bit pattern based on frame type
        bits = self.get_bit_pattern(frame_number, frame_type, countdown_val, frames_count)

        # Calculate block dimensions
        available_width = self.width - (2 * self.corner_size)  # Width minus corners
        block_width = available_width // self.bits_per_frame  # ~40 pixels for 16 bits

        # Fill strip background with mid-gray (neutral color)
        frame[0:self.strip_height, self.corner_size:self.width - self.corner_size] = self.strip_bg_color

        # Draw each bit as colored block in all 3 rows
        for i, bit in enumerate(bits):
            x_start = self.corner_size + (i * block_width)
            x_end = x_start + block_width

            # Color based on bit value: Red for '1', Blue for '0'
            color = self.bit_1_color if bit == '1' else self.bit_0_color

            # Draw in all 3 rows for vertical redundancy
            for row in range(self.strip_num_rows):
                y_start = row * self.strip_row_height
                y_end = y_start + self.strip_row_height
                cv2.rectangle(frame, (x_start, y_start), (x_end, y_end), color, -1)

        # Add corner markers
        # Top-left: red square
        cv2.rectangle(frame, (0, 0),
                     (self.corner_size, self.corner_size),
                     self.corner_color_primary, -1)
        # Bottom-right: red square
        cv2.rectangle(frame, (self.width - self.corner_size, self.height - self.corner_size),
                     (self.width, self.height),
                     self.corner_color_primary, -1)
        # Top-right: blue square
        cv2.rectangle(frame, (self.width - self.corner_size, 0),
                     (self.width, self.corner_size),
                     self.corner_color_secondary, -1)
        # Bottom-left: blue square
        cv2.rectangle(frame, (0, self.height - self.corner_size),
                     (self.corner_size, self.height),
                     self.corner_color_secondary, -1)
    
    def generate_robust_fsk_audio(self, frame_number, frame_type='timecode', countdown_val=0, frames_count=0):
        """
        Generate V2 robust FSK audio for a single frame with pilot tone.

        Args:
            frame_number: Frame number to encode (for timecode type)
            frame_type: 'leader', 'countdown', 'timecode', 'leadout', 'separator'
            countdown_val: Countdown/count-up value (for countdown/leadout types)
            frames_count: Frames until/since timecode section

        Returns:
            numpy array: MONO audio samples for this frame

        V2 Frame structure:
        - 10% pilot tone (1200Hz) for frame sync
        - 5% silence separator
        - 80% FSK data (16 bits)
        - 5% trailing silence
        """
        audio = np.zeros(self.samples_per_frame)

        # Calculate section boundaries
        pilot_samples = int(self.samples_per_frame * self.pilot_ratio)
        silence1_samples = int(self.samples_per_frame * self.silence_ratio)
        data_samples = int(self.samples_per_frame * self.data_ratio)
        # Trailing silence fills remainder

        # Section 1: Pilot tone (1200Hz) for frame synchronization
        pilot_tone = self._generate_robust_tone(self.freq_pilot, pilot_samples)
        audio[0:pilot_samples] = pilot_tone

        # Section 2: Silence separator (already zeros)
        data_start = pilot_samples + silence1_samples

        # Section 3: FSK data (16 bits)
        # Get bit pattern based on frame type
        bits = self.get_bit_pattern(frame_number, frame_type, countdown_val, frames_count)

        # Calculate samples per bit for the data section
        samples_per_data_bit = data_samples // self.bits_per_frame

        for i, bit in enumerate(bits):
            start_sample = data_start + (i * samples_per_data_bit)
            end_sample = start_sample + samples_per_data_bit

            # Ensure we don't exceed frame bounds
            if end_sample > self.samples_per_frame:
                end_sample = self.samples_per_frame

            if start_sample < end_sample:
                # Select frequency based on bit value
                frequency = self.freq_0 if bit == '0' else self.freq_1

                # Generate tone with improved robustness
                tone = self._generate_robust_tone(frequency, end_sample - start_sample)
                audio[start_sample:end_sample] = tone

        # Section 4: Trailing silence (already zeros)

        return audio

    def generate_robust_fsk_audio_legacy(self, frame_number):
        """
        Legacy V1 FSK audio generation (32-bit, no pilot tone).
        Kept for backward compatibility with existing test videos.

        Args:
            frame_number: Frame number to encode

        Returns:
            numpy array: MONO audio samples for this frame
        """
        # Encode frame number as binary (24 bits)
        binary = format(frame_number, '024b')

        # Calculate enhanced checksum (CRC-like)
        checksum = self._calculate_robust_checksum(frame_number)
        checksum_bin = format(checksum, '08b')

        # Complete data: 24-bit frame + 8-bit checksum = 32 bits
        data_bits = binary + checksum_bin

        # Generate audio samples (using old 32-bit timing)
        legacy_samples_per_bit = self.samples_per_frame // 32
        audio = np.zeros(self.samples_per_frame)

        for i, bit in enumerate(data_bits):
            start_sample = i * legacy_samples_per_bit
            end_sample = min(start_sample + legacy_samples_per_bit, self.samples_per_frame)

            # Select frequency based on bit value (using V2 frequencies for compatibility)
            frequency = self.freq_0 if bit == '0' else self.freq_1

            # Generate tone with improved robustness
            tone = self._generate_robust_tone(frequency, end_sample - start_sample)

            audio[start_sample:end_sample] = tone

        return audio
    
    def _generate_robust_tone(self, frequency, n_samples):
        """
        Generate a robust sine wave tone
        
        Args:
            frequency: Frequency in Hz
            n_samples: Number of samples to generate
            
        Returns:
            numpy array: Audio samples for the tone
        """
        # Calculate exact phase for perfect frequency
        duration = n_samples / self.sample_rate
        total_cycles = frequency * duration
        
        # Generate phase array with exact cycles
        phase = np.linspace(0, 2 * np.pi * total_cycles, n_samples, False)
        
        # Generate clean sine wave
        tone = np.sin(phase)
        
        # Apply gentle envelope to reduce transients (5% fade)
        envelope_samples = max(1, n_samples // 20)  # 5% of bit duration
        
        if envelope_samples > 0 and len(tone) > 2 * envelope_samples:
            # Fade in
            fade_in = np.linspace(0, 1, envelope_samples)
            tone[:envelope_samples] *= fade_in
            
            # Fade out
            fade_out = np.linspace(1, 0, envelope_samples)
            tone[-envelope_samples:] *= fade_out
        
        # Use consistent amplitude (60% to avoid clipping)
        return tone * 0.6
    
    def _calculate_robust_checksum(self, frame_number):
        """
        Calculate enhanced checksum for better error detection
        
        Args:
            frame_number: Frame number to checksum
            
        Returns:
            int: 8-bit checksum value
        """
        # Simple but effective checksum: XOR of all bits + rotation
        binary = format(frame_number, '024b')
        
        checksum = 0
        for i, bit in enumerate(binary):
            if bit == '1':
                # XOR with rotated position value
                checksum ^= ((i + 1) % 256)
        
        # Add frame number modulo 256 for additional validation
        checksum ^= (frame_number % 256)
        
        return checksum % 256
    
    def decode_fsk_audio(self, audio_channel, strict=True):
        """
        Flexible FSK decoder with strict and tolerant modes
        
        Args:
            audio_channel: Mono audio samples
            strict: If True, uses deterministic frame boundaries (MP4 mode)
                   If False, uses sliding window tolerance (VHS mode)
            
        Returns:
            list: List of (sample_position, frame_id, confidence) tuples
        """
        if strict:
            # MP4 mode: Strict frame-boundary decoding
            return self._decode_deterministic_frames(audio_channel)
        else:
            # VHS mode: Tolerant sliding window decoding
            return self._decode_tolerant_frames(audio_channel)
    
    def _decode_deterministic_frames(self, audio_channel):
        """
        STRICT frame-accurate FSK decoder for MP4 validation
        
        Decodes FSK audio at exact frame boundaries with binary frequency detection.
        No probabilistic methods, no confidence levels, no overlapping windows.
        Either a frame decodes correctly or it doesn't.
        
        Args:
            audio_channel: Mono audio samples
            
        Returns:
            list: List of (sample_position, frame_id, confidence) tuples where confidence is always 1.0
        """
        decoded_frames = []
        
        # FRAME-ACCURATE decoding - check exact frame boundaries only
        frame_samples = self.samples_per_frame  # 1920 samples
        
        # Make sure we have enough audio to analyze
        if len(audio_channel) < frame_samples:
            return decoded_frames
        
        # Decode at exact frame boundaries - no overlapping
        for frame_idx in range(len(audio_channel) // frame_samples):
            start_sample = frame_idx * frame_samples
            end_sample = start_sample + frame_samples
            
            if end_sample > len(audio_channel):
                break
                
            frame_audio = audio_channel[start_sample:end_sample]
            
            # DETERMINISTIC decode - either it works or it doesn't
            frame_id = self._decode_frame_deterministic(frame_audio)
            
            if frame_id is not None:
                decoded_frames.append((start_sample, frame_id, 1.0))  # Always confidence 1.0
        
        return decoded_frames
    
    def _decode_tolerant_frames(self, audio_channel):
        """
        TOLERANT sliding window FSK decoder for VHS capture validation
        
        Uses sliding window approach with robust multi-method bit analysis
        to handle capture timing variations and VHS mechanical imperfections.
        
        Args:
            audio_channel: Mono audio samples
            
        Returns:
            list: List of (sample_position, frame_id, confidence) tuples
        """
        import time
        import sys
        start_time = time.time()
        
        decoded_frames = []
        frame_samples = self.samples_per_frame  # 1920 samples
        
        # Make sure we have enough audio to analyze
        if len(audio_channel) < frame_samples:
            return decoded_frames
        
        print(f"  Starting tolerant sliding window decoding...")
        print(f"  Audio length: {len(audio_channel)} samples ({len(audio_channel)/self.sample_rate:.1f}s)")
        sys.stdout.flush()
        
        # First try: exact frame boundaries (same as deterministic but with robust bit analysis)
        exact_results = self._decode_exact_boundaries_robust(audio_channel)
        decoded_frames.extend(exact_results)
        elapsed = time.time() - start_time
        print(f"  Exact boundaries: {len(exact_results)} frames decoded in {elapsed:.1f}s")
        sys.stdout.flush()
        
        # Check timeout before sliding window (which is expensive)
        if elapsed > 60:  # 1 minute timeout for exact boundaries
            print(f"  WARNING: Exact boundary decoding took {elapsed:.1f}s, skipping sliding window")
            return decoded_frames
        
        # Second try: sliding window with small offsets for capture timing variations
        # Limit sliding window to reasonable size to prevent hanging
        max_sliding_duration = 120.0  # Don't slide window on audio longer than 2 minutes
        audio_duration = len(audio_channel) / self.sample_rate
        
        if audio_duration > max_sliding_duration:
            print(f"  WARNING: Audio too long ({audio_duration:.1f}s), limiting sliding window analysis")
            # Only analyze first 2 minutes for sliding window
            limited_audio = audio_channel[:int(max_sliding_duration * self.sample_rate)]
        else:
            limited_audio = audio_channel
        
        slide_step = frame_samples // 8  # 1/8 frame steps for fine adjustment
        sliding_results = self._decode_sliding_windows(limited_audio, slide_step)
        
        # Merge results, avoiding duplicates
        merged_results = self._merge_decoded_frames(decoded_frames, sliding_results)
        total_elapsed = time.time() - start_time
        print(f"  Sliding window: {len(sliding_results)} additional frames found")
        print(f"  Total tolerant decode: {len(merged_results)} frames in {total_elapsed:.1f}s")
        sys.stdout.flush()
        
        return merged_results
    
    def _decode_exact_boundaries_robust(self, audio_channel):
        """
        Decode at exact frame boundaries using robust bit analysis
        """
        decoded_frames = []
        frame_samples = self.samples_per_frame
        
        for frame_idx in range(len(audio_channel) // frame_samples):
            start_sample = frame_idx * frame_samples
            end_sample = start_sample + frame_samples
            
            if end_sample > len(audio_channel):
                break
                
            frame_audio = audio_channel[start_sample:end_sample]
            
            # Use robust frame decoder instead of deterministic
            result = self._decode_frame_robust(frame_audio)
            
            if result is not None:
                frame_id, confidence = result
                decoded_frames.append((start_sample, frame_id, confidence))
        
        return decoded_frames
    
    def _decode_sliding_windows(self, audio_channel, slide_step):
        """
        Decode using sliding windows to catch frames at non-standard positions
        """
        decoded_frames = []
        frame_samples = self.samples_per_frame
        
        # Slide in small steps
        for offset in range(0, len(audio_channel) - frame_samples, slide_step):
            frame_audio = audio_channel[offset:offset + frame_samples]
            
            result = self._decode_frame_robust(frame_audio)
            
            if result is not None:
                frame_id, confidence = result
                # Keep reasonable-confidence sliding window detections for VHS
                if confidence > 0.5:
                    decoded_frames.append((offset, frame_id, confidence))
        
        return decoded_frames
    
    def _decode_frame_robust(self, frame_audio):
        """
        Robust frame decoder using multi-method bit analysis
        
        Args:
            frame_audio: Audio samples for one frame
            
        Returns:
            tuple: (frame_id, confidence) if successful, None if failed
        """
        bits = []
        bit_confidences = []
        
        # Decode each bit using robust analysis
        for bit_idx in range(self.bits_per_frame):
            start_bit = bit_idx * self.samples_per_bit
            end_bit = min(start_bit + self.samples_per_bit, len(frame_audio))
            
            if end_bit <= start_bit:
                return None
            
            bit_audio = frame_audio[start_bit:end_bit]
            
            # Use robust bit analysis
            bit_result = self._analyze_bit_robust(bit_audio)
            
            if bit_result is None:
                return None  # Failed to decode this bit
            
            bit_value, bit_confidence = bit_result
            bits.append(bit_value)
            bit_confidences.append(bit_confidence)
        
        if len(bits) != 32:
            return None
        
        # Calculate overall confidence
        overall_confidence = np.mean(bit_confidences)
        
        # Extract frame number and checksum
        frame_bits = bits[:24]
        checksum_bits = bits[24:]
        
        try:
            frame_number = int(''.join(frame_bits), 2)
            received_checksum = int(''.join(checksum_bits), 2)
        except ValueError:
            return None
        
        # Verify checksum
        calculated_checksum = self._calculate_robust_checksum(frame_number)
        
        if calculated_checksum != received_checksum:
            return None  # Checksum mismatch
        
        # Validate frame ID range
        if not self._validate_frame_id_range(frame_number):
            return None
        
        return frame_number, overall_confidence
    
    def _merge_decoded_frames(self, primary_frames, secondary_frames):
        """
        Merge two sets of decoded frames, avoiding duplicates
        
        Args:
            primary_frames: List of primary detections
            secondary_frames: List of secondary detections to merge
            
        Returns:
            list: Merged and filtered frame list
        """
        # Combine all detections
        all_detections = list(primary_frames) + list(secondary_frames)
        
        # Filter overlapping detections
        return self._filter_overlapping_detections(all_detections)
    
    def _decode_frame_deterministic(self, frame_audio):
        """
        Deterministic frame decoder
        
        Args:
            frame_audio: Audio samples for one frame
            
        Returns:
            int: frame_id if successful, None if failed
        """
        bits = []
        
        # Decode each bit by checking frequency peak
        for bit_idx in range(self.bits_per_frame):
            start_bit = bit_idx * self.samples_per_bit
            end_bit = min(start_bit + self.samples_per_bit, len(frame_audio))
            
            if end_bit <= start_bit:
                return None
            
            bit_audio = frame_audio[start_bit:end_bit]
            
            # Analyze frequency
            f0_amplitude = self._analyze_frequency_amplitude(bit_audio, self.freq_0)
            f1_amplitude = self._analyze_frequency_amplitude(bit_audio, self.freq_1)
            
            # Determine bit value
            if f0_amplitude > f1_amplitude:
                bits.append('0')
            else:
                bits.append('1')
        
        if len(bits) != 32:
            return None
        
        # Extract frame number and checksum
        frame_bits = bits[:24]
        checksum_bits = bits[24:]
        
        try:
            frame_number = int(''.join(frame_bits), 2)
            received_checksum = int(''.join(checksum_bits), 2)
        except ValueError:
            return None
        
        # Verify checksum deterministically
        calculated_checksum = self._calculate_robust_checksum(frame_number)
        
        if calculated_checksum != received_checksum:
            return None  # Checksum mismatch
        
        return frame_number

    def _analyze_frequency_amplitude(self, bit_audio, target_freq):
        """
        Analyze the amplitude of a specific frequency in a bit
        
        Args:
            bit_audio: Audio samples for one bit
            target_freq: The frequency to analyze
            
        Returns:
            float: Amplitude of the target frequency
        """
        # Apply window and FFT
        windowed = bit_audio * np.hanning(len(bit_audio))
        fft_result = np.fft.fft(windowed)
        freqs = np.fft.fftfreq(len(bit_audio), d=1/self.sample_rate)
        
        positive_freqs = freqs[:len(freqs)//2]
        positive_fft = np.abs(fft_result[:len(fft_result)//2])
        
        # Find the amplitude of the target frequency
        target_index = np.argmin(np.abs(positive_freqs - target_freq))
        return positive_fft[target_index]
    
    def _analyze_bit_robust(self, bit_audio):
        """
        Robust bit analysis using multiple detection methods
        
        Args:
            bit_audio: Audio samples for one bit
            
        Returns:
            tuple: (bit_value, confidence) or None if unclear
        """
        if len(bit_audio) < 10:
            return None
        
        # Method 1: FFT-based frequency detection (most reliable)
        fft_result = self._analyze_bit_fft(bit_audio)
        
        # Method 2: Zero-crossing rate analysis
        zcr_result = self._analyze_bit_zero_crossings(bit_audio)
        
        # Method 3: Autocorrelation-based period detection
        autocorr_result = self._analyze_bit_autocorrelation(bit_audio)
        
        # Combine results using weighted voting (FFT has higher weight)
        methods = []
        if fft_result is not None:
            methods.append((fft_result[0], fft_result[1], 2.0))  # Weight 2.0 for FFT
        if zcr_result is not None:
            methods.append((zcr_result[0], zcr_result[1], 1.0))   # Weight 1.0 for ZCR
        if autocorr_result is not None:
            methods.append((autocorr_result[0], autocorr_result[1], 1.0))  # Weight 1.0 for AutoCorr
        
        if len(methods) == 0:
            return None  # No methods worked
        
        # If only one method worked, use it if confidence is reasonable
        if len(methods) == 1:
            bit, conf, weight = methods[0]
            if conf > 0.5:  # Lower confidence threshold for single method
                return bit, conf
            else:
                return None
        
        # Weighted voting
        total_weight_0 = sum(weight for bit, conf, weight in methods if bit == '0')
        total_weight_1 = sum(weight for bit, conf, weight in methods if bit == '1')
        
        if total_weight_0 > total_weight_1:
            # Weighted majority for '0'
            confs_0 = [conf for bit, conf, weight in methods if bit == '0']
            avg_conf = np.mean(confs_0) if confs_0 else 0
            return '0', avg_conf
        elif total_weight_1 > total_weight_0:
            # Weighted majority for '1'
            confs_1 = [conf for bit, conf, weight in methods if bit == '1']
            avg_conf = np.mean(confs_1) if confs_1 else 0
            return '1', avg_conf
        else:
            # Tie - use highest confidence result
            best_method = max(methods, key=lambda x: x[1])
            return best_method[0], best_method[1]
    
    def _analyze_bit_fft(self, bit_audio):
        """FFT-based frequency analysis"""
        # Apply window and FFT
        windowed = bit_audio * np.hanning(len(bit_audio))
        fft_result = np.fft.fft(windowed)
        freqs = np.fft.fftfreq(len(bit_audio), d=1/self.sample_rate)
        
        positive_freqs = freqs[:len(freqs)//2]
        positive_fft = np.abs(fft_result[:len(fft_result)//2])
        
        # Get amplitude in each frequency range (with guard bands)
        mask_0 = (positive_freqs >= self.freq_0_range[0]) & (positive_freqs <= self.freq_0_range[1])
        mask_1 = (positive_freqs >= self.freq_1_range[0]) & (positive_freqs <= self.freq_1_range[1])
        
        amp_0 = np.max(positive_fft[mask_0]) if np.any(mask_0) else 0
        amp_1 = np.max(positive_fft[mask_1]) if np.any(mask_1) else 0
        
        # Decision with confidence based on amplitude ratio
        total_amp = amp_0 + amp_1
        if total_amp < 0.01:  # Too weak signal
            return None
        
        ratio_0 = amp_0 / total_amp
        ratio_1 = amp_1 / total_amp
        
        # Require clear winner (>60% of total amplitude)
        if ratio_0 > 0.6:
            return '0', ratio_0
        elif ratio_1 > 0.6:
            return '1', ratio_1
        else:
            return None  # Ambiguous
    
    def _analyze_bit_zero_crossings(self, bit_audio):
        """Zero-crossing rate analysis"""
        # Count zero crossings
        zero_crossings = 0
        for i in range(1, len(bit_audio)):
            if (bit_audio[i-1] >= 0) != (bit_audio[i] >= 0):
                zero_crossings += 1
        
        # Estimate frequency
        duration = len(bit_audio) / self.sample_rate
        estimated_freq = zero_crossings / (2 * duration)
        
        # Calculate distances to expected frequencies
        dist_0 = abs(estimated_freq - self.freq_0)
        dist_1 = abs(estimated_freq - self.freq_1)
        
        # Classify with confidence based on distance
        if dist_0 < dist_1:
            # Closer to freq_0
            confidence = max(0.1, 1.0 - (dist_0 / 200))  # Normalize to confidence
            if confidence > 0.5:
                return '0', confidence
        else:
            # Closer to freq_1
            confidence = max(0.1, 1.0 - (dist_1 / 200))  # Normalize to confidence
            if confidence > 0.5:
                return '1', confidence
        
        return None
    
    def _analyze_bit_autocorrelation(self, bit_audio):
        """Autocorrelation-based period detection"""
        # Calculate autocorrelation
        correlation = np.correlate(bit_audio, bit_audio, mode='full')
        correlation = correlation[len(correlation)//2:]
        
        # Look for peaks corresponding to expected periods
        period_0 = int(self.sample_rate / self.freq_0)  # Samples per cycle at freq_0
        period_1 = int(self.sample_rate / self.freq_1)  # Samples per cycle at freq_1
        
        # Check correlation strength at expected periods (with tolerance)
        tolerance = 3  # ±3 samples tolerance
        
        corr_0 = 0
        for p in range(max(1, period_0 - tolerance), min(len(correlation), period_0 + tolerance + 1)):
            corr_0 = max(corr_0, correlation[p])
        
        corr_1 = 0
        for p in range(max(1, period_1 - tolerance), min(len(correlation), period_1 + tolerance + 1)):
            corr_1 = max(corr_1, correlation[p])
        
        # Normalize correlations
        max_corr = correlation[0]  # Auto-correlation at zero lag
        if max_corr <= 0:
            return None
        
        norm_corr_0 = corr_0 / max_corr
        norm_corr_1 = corr_1 / max_corr
        
        # Decision based on stronger correlation
        if norm_corr_0 > norm_corr_1 and norm_corr_0 > 0.3:
            return '0', norm_corr_0
        elif norm_corr_1 > norm_corr_0 and norm_corr_1 > 0.3:
            return '1', norm_corr_1
        
        return None
    
    def detect_timecode_window_video(self, video_file, strict=True):
        """
        Detect the first complete timecode window in video file
        
        Pattern structure: 4s test pattern + 1s black + 30s timecode + 1s black + repeat
        
        Args:
            video_file: Path to video file
            strict: If True (MP4), requires precise detection. If False (VHS), more tolerant
            
        Returns:
            dict: {
                'success': bool,
                'timecode_start_frame': int,
                'timecode_end_frame': int,
                'timecode_duration_frames': int,
                'pattern_info': dict
            }
        """
        import cv2
        import sys
        
        cap = cv2.VideoCapture(video_file)
        if not cap.isOpened():
            return {'success': False, 'error': f'Could not open video file: {video_file}'}
        
        try:
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            print(f"  Detecting pattern in {total_frames} frames...")
            
            frame_states = []  # Track frame types: 'black', 'pattern', 'timecode'
            frame_count = 0
            
            while True:
                ret, frame = cap.read()
                if not ret:
                    break
                
                frame_type = self._classify_frame_type(frame, strict)
                frame_states.append((frame_count, frame_type))
                frame_count += 1
                
                # Progress reporting
                if frame_count % 250 == 0:
                    print(f"    Analyzed {frame_count}/{total_frames} frames...")
                    sys.stdout.flush()
            
            # Analyze pattern transitions to find first complete timecode window
            result = self._analyze_pattern_transitions(frame_states, strict)
            print(f"  Pattern detection: {result.get('pattern_info', {}).get('description', 'Unknown')}")
            
            return result
            
        finally:
            cap.release()
    
    def _classify_frame_type(self, frame, strict):
        """
        Classify frame as 'black', 'pattern', or 'timecode'
        
        Args:
            frame: Video frame (BGR)
            strict: If True, use stricter thresholds for MP4
            
        Returns:
            str: Frame type classification
        """
        # Convert to grayscale
        if len(frame.shape) == 3:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        else:
            gray = frame
        
        mean_intensity = np.mean(gray)
        std_intensity = np.std(gray)
        
        # Thresholds - stricter for MP4, more tolerant for VHS
        if strict:
            black_threshold = 30
            pattern_std_threshold = 60
            timecode_std_threshold = 40
        else:
            # VHS-specific thresholds based on actual capture analysis
            black_threshold = 15  # Reduced from 40 (actual black ~7.7)
            pattern_std_threshold = 55  # Reduced from 50 (actual pattern ~61.8)
            timecode_std_threshold = 25  # Reduced from 30 (actual timecode ~38.1)
        
        # Classification logic
        if mean_intensity < black_threshold and std_intensity < 15:
            return 'black'
        elif std_intensity > pattern_std_threshold:
            # High contrast suggests test pattern
            return 'pattern'
        elif std_intensity > timecode_std_threshold and mean_intensity > black_threshold:
            # Medium contrast with brightness above black threshold suggests timecode
            return 'timecode'
        else:
            # Ambiguous - default to pattern for safety
            return 'pattern'
    
    def _analyze_pattern_transitions(self, frame_states, strict):
        """
        Analyze frame state transitions to find first complete timecode window
        
        Expected pattern: pattern -> black -> timecode -> black -> pattern
        We want to identify the timecode portion of the first complete cycle.
        
        Args:
            frame_states: List of (frame_number, frame_type) tuples
            strict: Whether to use strict validation
            
        Returns:
            dict: Analysis results with timecode window bounds
        """
        if len(frame_states) < 100:  # Need reasonable amount of data
            return {'success': False, 'error': 'Insufficient frame data for pattern analysis'}
        
        # Find transitions
        transitions = []
        for i in range(1, len(frame_states)):
            prev_frame, prev_type = frame_states[i-1]
            curr_frame, curr_type = frame_states[i]
            
            if prev_type != curr_type:
                transitions.append((curr_frame, prev_type, curr_type))
        
        if len(transitions) < 3:
            return {'success': False, 'error': 'Insufficient pattern transitions found'}
        
        # Look for pattern: pattern/black -> timecode -> black/pattern
        # We're looking for the first substantial timecode section
        timecode_start = None
        timecode_end = None
        
        for i, (frame_num, from_type, to_type) in enumerate(transitions):
            # Look for transition TO timecode
            if to_type == 'timecode' and timecode_start is None:
                # Verify this is likely the start of a substantial timecode section
                timecode_candidate_start = frame_num
                
                # Look ahead to find the end of this timecode section
                timecode_candidate_end = None
                for j in range(i + 1, len(transitions)):
                    end_frame, end_from_type, end_to_type = transitions[j]
                    if end_from_type == 'timecode' and end_to_type != 'timecode':
                        timecode_candidate_end = end_frame
                        break
                
                # If we found an end, check if this timecode section is long enough
                if timecode_candidate_end is not None:
                    duration_frames = timecode_candidate_end - timecode_candidate_start
                    expected_duration = int(30 * self.fps)  # 30 seconds
                    
                    # Accept if duration is reasonable (20-40 seconds worth)
                    if int(20 * self.fps) <= duration_frames <= int(40 * self.fps):
                        timecode_start = timecode_candidate_start
                        timecode_end = timecode_candidate_end
                        break
        
        if timecode_start is None or timecode_end is None:
            # Fallback: look for longest timecode section
            longest_start = None
            longest_end = None
            longest_duration = 0
            
            current_timecode_start = None
            for frame_num, frame_type in frame_states:
                if frame_type == 'timecode' and current_timecode_start is None:
                    current_timecode_start = frame_num
                elif frame_type != 'timecode' and current_timecode_start is not None:
                    duration = frame_num - current_timecode_start
                    if duration > longest_duration:
                        longest_duration = duration
                        longest_start = current_timecode_start
                        longest_end = frame_num
                    current_timecode_start = None
            
            if longest_start is not None and longest_duration >= int(15 * self.fps):  # At least 15 seconds
                timecode_start = longest_start
                timecode_end = longest_end
        
        if timecode_start is None or timecode_end is None:
            return {
                'success': False,
                'error': 'Could not identify timecode window in pattern',
                'transitions_found': len(transitions),
                'pattern_info': {
                    'description': f'Found {len(transitions)} transitions but no clear timecode window'
                }
            }
        
        duration_frames = timecode_end - timecode_start
        duration_seconds = duration_frames / self.fps
        
        return {
            'success': True,
            'timecode_start_frame': timecode_start,
            'timecode_end_frame': timecode_end,
            'timecode_duration_frames': duration_frames,
            'pattern_info': {
                'description': f'Found timecode window: frames {timecode_start}-{timecode_end} ({duration_seconds:.1f}s)',
                'transitions_analyzed': len(transitions),
                'timecode_duration_seconds': duration_seconds
            }
        }
    
    def detect_timecode_window_audio(self, audio_file, strict=True):
        """
        Detect the first complete timecode window in audio file
        
        Pattern structure: 4s test tone (1kHz) + 1s silence + 30s FSK timecode + 1s silence + repeat
        
        Args:
            audio_file: Path to audio file
            strict: If True (MP4), requires precise detection. If False (VHS), more tolerant
            
        Returns:
            dict: {
                'success': bool,
                'timecode_start_sample': int,
                'timecode_end_sample': int,
                'timecode_duration_samples': int,
                'pattern_info': dict
            }
        """
        import subprocess
        import sys
        
        # Load audio data
        try:
            cmd = ['sox', audio_file, '-t', 'f32', '-r', str(self.sample_rate), '-']
            result = subprocess.run(cmd, capture_output=True, check=True)
            audio_raw = np.frombuffer(result.stdout, dtype=np.float32)
            
            # Convert to mono if needed
            try:
                soxi_result = subprocess.run(['soxi', audio_file], capture_output=True, text=True)
                if '1 channel' in soxi_result.stdout or 'Channels       : 1' in soxi_result.stdout:
                    audio_data = audio_raw
                else:
                    # Convert stereo to mono by taking first channel
                    audio_data = audio_raw[::2]  # Take every other sample (first channel)
            except:
                # Assume mono if we can't determine
                audio_data = audio_raw
                
        except Exception as e:
            return {'success': False, 'error': f'Could not load audio file: {e}'}
        
        total_samples = len(audio_data)
        total_duration = total_samples / self.sample_rate
        print(f"  Detecting audio pattern in {total_samples} samples ({total_duration:.1f}s)...")
        
        # Analyze audio in chunks to classify regions
        chunk_duration = 0.5  # 500ms chunks for analysis
        chunk_samples = int(chunk_duration * self.sample_rate)
        
        audio_states = []  # Track audio types: 'silence', 'tone', 'timecode'
        
        for start_sample in range(0, total_samples - chunk_samples, chunk_samples):
            end_sample = min(start_sample + chunk_samples, total_samples)
            chunk = audio_data[start_sample:end_sample]
            
            audio_type = self._classify_audio_type(chunk, strict)
            audio_states.append((start_sample, audio_type))
            
            # Progress reporting
            if len(audio_states) % 50 == 0:
                analyzed_duration = len(audio_states) * chunk_duration
                print(f"    Analyzed {analyzed_duration:.1f}s/{total_duration:.1f}s...")
                sys.stdout.flush()
        
        # Analyze pattern transitions to find first complete timecode window
        result = self._analyze_audio_pattern_transitions(audio_states, chunk_samples, strict)
        print(f"  Audio pattern detection: {result.get('pattern_info', {}).get('description', 'Unknown')}")
        
        return result
    
    def _classify_audio_type(self, audio_chunk, strict):
        """
        Classify audio chunk as 'silence', 'tone', or 'timecode'
        
        Args:
            audio_chunk: Audio samples
            strict: If True, use stricter thresholds for MP4
            
        Returns:
            str: Audio type classification
        """
        if len(audio_chunk) < 100:
            return 'silence'
        
        # Calculate RMS energy
        rms_energy = np.sqrt(np.mean(audio_chunk**2))
        
        # Thresholds - stricter for MP4, more tolerant for VHS
        if strict:
            silence_threshold = 0.01
            tone_energy_threshold = 0.1
        else:
            silence_threshold = 0.02  # More tolerant for VHS noise
            tone_energy_threshold = 0.05
        
        # Check for silence first
        if rms_energy < silence_threshold:
            return 'silence'
        
        # Analyze frequency content for classification
        if len(audio_chunk) > self.sample_rate // 10:  # At least 100ms of audio
            # Apply window and FFT
            windowed = audio_chunk * np.hanning(len(audio_chunk))
            fft_result = np.fft.fft(windowed)
            freqs = np.fft.fftfreq(len(audio_chunk), d=1/self.sample_rate)
            
            positive_freqs = freqs[:len(freqs)//2]
            positive_fft = np.abs(fft_result[:len(fft_result)//2])
            
            if len(positive_fft) > 0:
                # Find peak frequency
                peak_idx = np.argmax(positive_fft)
                peak_freq = abs(positive_freqs[peak_idx])
                
                # Check for 1kHz test tone (around 1000Hz ± 100Hz)
                if 900 <= peak_freq <= 1100 and rms_energy > tone_energy_threshold:
                    return 'tone'
                
                # Check for FSK timecode frequencies (800Hz or 1600Hz)
                fsk_0_energy = np.max(positive_fft[(positive_freqs >= 650) & (positive_freqs <= 950)])
                fsk_1_energy = np.max(positive_fft[(positive_freqs >= 1350) & (positive_freqs <= 1850)])
                
                if (fsk_0_energy > 0 or fsk_1_energy > 0) and rms_energy > silence_threshold * 2:
                    return 'timecode'
        
        # Default classification based on energy
        if rms_energy > tone_energy_threshold:
            return 'tone'  # High energy, assume test tone
        else:
            return 'timecode'  # Medium energy, likely timecode
    
    def _analyze_audio_pattern_transitions(self, audio_states, chunk_samples, strict):
        """
        Analyze audio pattern transitions to find first complete timecode window
        
        Expected pattern: tone -> silence -> timecode -> silence -> tone
        
        Args:
            audio_states: List of (sample_position, audio_type) tuples
            chunk_samples: Samples per analysis chunk
            strict: Whether to use strict validation
            
        Returns:
            dict: Analysis results with timecode window bounds
        """
        if len(audio_states) < 10:  # Need reasonable amount of data
            return {'success': False, 'error': 'Insufficient audio data for pattern analysis'}
        
        # Find transitions
        transitions = []
        for i in range(1, len(audio_states)):
            prev_sample, prev_type = audio_states[i-1]
            curr_sample, curr_type = audio_states[i]
            
            if prev_type != curr_type:
                transitions.append((curr_sample, prev_type, curr_type))
        
        if len(transitions) < 3:
            return {'success': False, 'error': 'Insufficient audio pattern transitions found'}
        
        # Look for pattern: tone/silence -> timecode -> silence/tone
        timecode_start = None
        timecode_end = None
        
        for i, (sample_pos, from_type, to_type) in enumerate(transitions):
            # Look for transition TO timecode
            if to_type == 'timecode' and timecode_start is None:
                timecode_candidate_start = sample_pos
                
                # Look ahead to find the end of this timecode section
                timecode_candidate_end = None
                for j in range(i + 1, len(transitions)):
                    end_sample, end_from_type, end_to_type = transitions[j]
                    if end_from_type == 'timecode' and end_to_type != 'timecode':
                        timecode_candidate_end = end_sample
                        break
                
                # If we found an end, check if this timecode section is long enough
                if timecode_candidate_end is not None:
                    duration_samples = timecode_candidate_end - timecode_candidate_start
                    duration_seconds = duration_samples / self.sample_rate
                    
                    # Accept if duration is reasonable (20-40 seconds)
                    if 20 <= duration_seconds <= 40:
                        timecode_start = timecode_candidate_start
                        timecode_end = timecode_candidate_end
                        break
        
        if timecode_start is None or timecode_end is None:
            # Fallback: look for longest timecode section
            longest_start = None
            longest_end = None
            longest_duration = 0
            
            current_timecode_start = None
            for sample_pos, audio_type in audio_states:
                if audio_type == 'timecode' and current_timecode_start is None:
                    current_timecode_start = sample_pos
                elif audio_type != 'timecode' and current_timecode_start is not None:
                    duration = sample_pos - current_timecode_start
                    if duration > longest_duration:
                        longest_duration = duration
                        longest_start = current_timecode_start
                        longest_end = sample_pos
                    current_timecode_start = None
            
            if longest_start is not None and longest_duration >= 15 * self.sample_rate:  # At least 15 seconds
                timecode_start = longest_start
                timecode_end = longest_end
        
        if timecode_start is None or timecode_end is None:
            return {
                'success': False,
                'error': 'Could not identify timecode window in audio pattern',
                'transitions_found': len(transitions),
                'pattern_info': {
                    'description': f'Found {len(transitions)} audio transitions but no clear timecode window'
                }
            }
        
        duration_samples = timecode_end - timecode_start
        duration_seconds = duration_samples / self.sample_rate
        
        return {
            'success': True,
            'timecode_start_sample': timecode_start,
            'timecode_end_sample': timecode_end,
            'timecode_duration_samples': duration_samples,
            'pattern_info': {
                'description': f'Found audio timecode window: samples {timecode_start}-{timecode_end} ({duration_seconds:.1f}s)',
                'transitions_analyzed': len(transitions),
                'timecode_duration_seconds': duration_seconds
            }
        }
    
    def correlate_timecodes(self, video_timecodes, audio_timecodes):
        """
        Correlate video and audio timecodes to find alignment offset
        Uses sequential matching to ensure correct temporal matching.

        Args:
            video_timecodes: List of (frame_number, timecode_id, confidence)
            audio_timecodes: List of (sample_position, timecode_id, confidence)

        Returns:
            dict: Result of correlation with offset metrics.
        """
        if not video_timecodes or not audio_timecodes:
            return {
                'error': 'Insufficient timecode data for correlation',
                'video_frames': len(video_timecodes),
                'audio_frames': len(audio_timecodes)
            }

        # Sort timecodes by temporal position to find first occurrences
        video_timecodes.sort(key=lambda x: x[0])  # Sort by frame position
        audio_timecodes.sort(key=lambda x: x[0])  # Sort by sample position

        matches = []
        
        # Create dictionaries for first occurrence of each frame ID
        video_first_occurrence = {}
        for video_frame, video_id, video_conf in video_timecodes:
            if video_id not in video_first_occurrence:
                video_first_occurrence[video_id] = (video_frame, video_conf)
        
        audio_first_occurrence = {}
        for audio_sample, audio_id, audio_conf in audio_timecodes:
            if audio_id not in audio_first_occurrence:
                audio_first_occurrence[audio_id] = (audio_sample, audio_conf)
        
        # For each unique frame ID, match first occurrence in video with first occurrence in audio
        common_frame_ids = set(video_first_occurrence.keys()).intersection(set(audio_first_occurrence.keys()))
        
        for frame_id in common_frame_ids:
            video_frame, video_conf = video_first_occurrence[frame_id]
            audio_sample, audio_conf = audio_first_occurrence[frame_id]
            
            # Calculate timing for this match
            video_time = video_frame / self.fps
            audio_time = audio_sample / self.sample_rate
            # Calculate delay needed for audio (positive = audio needs delay)
            offset = video_time - audio_time
            combined_confidence = min(video_conf, audio_conf)
            
            matches.append({
                'frame_id': frame_id,
                'video_frame': video_frame,
                'audio_sample': audio_sample,
                'video_time': video_time,
                'audio_time': audio_time,
                'offset_seconds': offset,
                'confidence': combined_confidence
            })

        if not matches or len(matches) < 50:  # Output debug if fewer than 50 matches
            # Enhanced debugging for correlation issues
            video_id_set = set(vid for _, vid, _ in video_timecodes)
            audio_id_set = set(aid for _, aid, _ in audio_timecodes)
            common_ids = video_id_set.intersection(audio_id_set)
            
            return {
'error': 'No matching frame IDs found between video and audio (expected for VHS source)',
                'video_ids': [vid for _, vid, _ in video_timecodes[:10]],
                'audio_ids': [aid for _, aid, _ in audio_timecodes[:10]],
                'debug_info': {
                    'unique_video_ids': len(video_id_set),
                    'unique_audio_ids': len(audio_id_set),
                    'common_frame_ids': len(common_ids),
                    'video_id_range': f"{min(video_id_set) if video_id_set else 'N/A'} to {max(video_id_set) if video_id_set else 'N/A'}",
                    'audio_id_range': f"{min(audio_id_set) if audio_id_set else 'N/A'} to {max(audio_id_set) if audio_id_set else 'N/A'}",
                    'sample_common_ids': list(common_ids)[:10] if common_ids else []
                }
            }

        # DEBUG: Show first few matches for troubleshooting
        print(f"  DEBUG: First 20 matches for troubleshooting:")
        for i, match in enumerate(matches[:20]):
            print(f"    Match {i+1}: Frame ID {match['frame_id']} - Video at {match['video_time']:.3f}s, Audio at {match['audio_time']:.3f}s, Offset: {match['offset_seconds']:+.3f}s")
        
        # DEBUG: Show extreme outliers
        sorted_matches = sorted(matches, key=lambda x: x['offset_seconds'])
        print(f"  DEBUG: Most negative offsets (audio much later):")
        for i, match in enumerate(sorted_matches[:5]):
            print(f"    Outlier {i+1}: Frame ID {match['frame_id']} - Video at {match['video_time']:.3f}s, Audio at {match['audio_time']:.3f}s, Offset: {match['offset_seconds']:+.3f}s")
        
        print(f"  DEBUG: Most positive offsets (audio much earlier):")
        for i, match in enumerate(sorted_matches[-5:]):
            print(f"    Outlier {i+1}: Frame ID {match['frame_id']} - Video at {match['video_time']:.3f}s, Audio at {match['audio_time']:.3f}s, Offset: {match['offset_seconds']:+.3f}s")
        
        # Analyze the matches to determine overall offset
        offsets = [match['offset_seconds'] for match in matches]
        weights = [match['confidence'] for match in matches]

        # Weighted average offset
        weighted_offset = np.average(offsets, weights=weights)

        # Statistics
        offset_std = np.std(offsets)
        offset_min = min(offsets)
        offset_max = max(offsets)

        results = {
            'success': True,
            'total_matches': len(matches),
            'average_offset_seconds': weighted_offset,
            'offset_std_seconds': offset_std,
            'offset_range_seconds': (offset_min, offset_max),
            'average_confidence': np.mean(weights),
            'matches': matches[:10],  # Include first 10 matches for inspection
            'analysis_summary': {
                'video_frames_analyzed': len(video_timecodes),
                'audio_frames_decoded': len(audio_timecodes)
            }
        }

        return results
    
    def load_audio_data(self, audio_file):
        """
        Load audio data using sox or similar tool (shared utility)
        
        Args:
            audio_file: Path to audio file
            
        Returns:
            numpy array: Audio data (mono or stereo)
        """
        try:
            # Try using sox to convert to raw format
            cmd = [
                'sox', audio_file, '-t', 'f32', '-r', str(self.sample_rate), '-'
            ]
            
            result = subprocess.run(cmd, capture_output=True, check=True)
            
            # Parse raw audio data based on known channel count
            audio_raw = np.frombuffer(result.stdout, dtype=np.float32)
            
            # Determine if stereo or mono from audio properties
            try:
                soxi_result = subprocess.run(['soxi', audio_file], capture_output=True, text=True)
                if '1 channel' in soxi_result.stdout or 'Channels       : 1' in soxi_result.stdout:
                    # Mono audio
                    audio_data = audio_raw.reshape(-1, 1)
                else:
                    # Stereo or multi-channel audio
                    audio_data = audio_raw.reshape(-1, 2)
            except:
                # Fallback: use length heuristic
                if len(audio_raw) % 2 == 0:
                    audio_data = audio_raw.reshape(-1, 2)  # Assume stereo
                else:
                    audio_data = audio_raw.reshape(-1, 1)  # Assume mono
            
            return audio_data
            
        except subprocess.CalledProcessError as e:
            print(f"  Sox error: {e}")
        except Exception as e:
            print(f"  Audio loading error: {e}")
        
        return None
    
    def read_binary_strip(self, frame):
        """
        V2 Read binary timecode from top strip with center sampling and confidence reporting.

        Reads the 60-pixel (3-row) binary strip using color-based detection (red vs blue)
        with center sampling to avoid edge contamination from VHS horizontal shift.

        Args:
            frame: Video frame (BGR format)

        Returns:
            tuple: (bits: str, confidences: list[float], overall_confidence: float)
                - bits: 16-character binary string
                - confidences: Confidence value (0-1) for each bit
                - overall_confidence: Average confidence across all bits
                Returns (None, [], 0.0) if frame format is invalid
        """
        height, width = frame.shape[:2]

        # Ensure we have a color frame for V2 color-based detection
        if len(frame.shape) != 3 or frame.shape[2] != 3:
            return None, [], 0.0

        # Extract the 60-pixel (3-row) strip from top of frame
        strip = frame[0:self.strip_height, :]

        bits = []
        confidences = []

        # V2: 16 blocks (not 32), with margins on sides
        margin_x = 40  # Skip edge pixels (corner markers)
        usable_width = width - (margin_x * 2)
        block_width = usable_width // 16

        for i in range(16):
            x_start = margin_x + (i * block_width)
            x_end = x_start + block_width

            # CENTER SAMPLING: Skip 25% on each side horizontally to avoid edge contamination
            h_margin = block_width // 4
            center_x_start = x_start + h_margin
            center_x_end = x_end - h_margin

            # Sample all 3 vertical rows and vote (with confidence per row)
            row_results = []
            row_height = self.strip_height // 3  # 20 pixels per row

            for row in range(3):
                # Skip 5 pixels top/bottom of each 20-pixel row
                y_start = row * row_height + 5
                y_end = y_start + 10  # Sample middle 10 pixels

                # Ensure we stay within strip bounds
                y_end = min(y_end, self.strip_height)

                if center_x_end > center_x_start and y_end > y_start:
                    center_block = frame[y_start:y_end, center_x_start:center_x_end]

                    # Color-based detection: compare red vs blue channels (BGR format)
                    blue_avg = np.mean(center_block[:, :, 0])
                    red_avg = np.mean(center_block[:, :, 2])

                    # Calculate confidence based on color separation
                    separation = abs(red_avg - blue_avg)
                    max_possible = 255.0  # Maximum possible separation
                    row_confidence = separation / max_possible

                    # '1' = red (higher red channel), '0' = blue (higher blue channel)
                    row_bit = '1' if red_avg > blue_avg else '0'
                    row_results.append((row_bit, row_confidence))

            # Majority vote across 3 rows
            if len(row_results) >= 2:
                ones = sum(1 for b, c in row_results if b == '1')
                bit = '1' if ones >= 2 else '0'

                # Confidence calculation with disagreement penalty
                agreeing_confidences = [c for b, c in row_results if b == bit]
                dissenting_confidences = [c for b, c in row_results if b != bit]

                base_confidence = np.mean(agreeing_confidences) if agreeing_confidences else 0.0

                if dissenting_confidences:
                    # Penalize proportionally to dissenting row's confidence
                    # High-confidence dissent = bigger penalty
                    dissent_penalty = np.mean(dissenting_confidences) * 0.5
                    bit_confidence = base_confidence * (1 - dissent_penalty)
                else:
                    # All rows agree - full confidence
                    bit_confidence = base_confidence
            else:
                # Not enough valid rows
                bit = '0'
                bit_confidence = 0.0

            bits.append(bit)
            confidences.append(bit_confidence)

        # Overall frame confidence
        overall_confidence = np.mean(confidences) if confidences else 0.0

        return ''.join(bits), confidences, overall_confidence

    def read_binary_strip_legacy(self, frame):
        """
        Legacy V1 binary strip reader (32-bit grayscale) for backward compatibility.

        Args:
            frame: Video frame (BGR or grayscale)

        Returns:
            int: Frame number if successful, None if failed
        """
        height, width = frame.shape[:2]

        # Extract the top 20 pixels
        strip = frame[0:20, :]

        # Convert to grayscale
        if len(strip.shape) == 3:
            strip_gray = cv2.cvtColor(strip, cv2.COLOR_BGR2GRAY)
        else:
            strip_gray = strip

        # Adaptive threshold based on strip characteristics
        strip_mean = np.mean(strip_gray)
        strip_std = np.std(strip_gray)

        # For VHS captures with low intensity, use adaptive threshold
        if strip_mean < 100 and strip_std > 20:
            threshold = strip_mean + (strip_std * 0.5)
        else:
            threshold = 128

        # Read 32 bits (legacy encoding)
        bits = []
        block_width = width // 32

        for i in range(32):
            x_start = i * block_width
            x_end = min(x_start + block_width, width)

            if x_end > x_start:
                block = strip_gray[:, x_start:x_end]
                avg_intensity = np.mean(block)
                bit = '1' if avg_intensity > threshold else '0'
                bits.append(bit)

        if len(bits) == 32:
            binary_str = ''.join(bits)
            try:
                frame_number = int(binary_str, 2)
                if self._validate_frame_id_range(frame_number):
                    return frame_number
            except ValueError:
                pass

        return None

    def decode_frame_with_validation(self, frame):
        """
        Decode V2 frame with confidence validation - fail explicitly if confidence too low.

        This is the primary decoding method that should be used for V2 encoded frames.
        It does NOT fall back to other algorithms - instead it reports failures explicitly.

        Args:
            frame: Video frame (BGR format)

        Returns:
            tuple: (frame_number, overall_confidence, status)
                - frame_number: Decoded frame number or None if failed
                - overall_confidence: Confidence level (0-1)
                - status: 'OK', 'LOW_CONFIDENCE', 'TOO_MANY_UNCERTAIN_BITS:N',
                          'INVALID_MARKERS', or 'INVALID_FRAME'
        """
        MIN_CONFIDENCE = 0.15  # 15% minimum color separation required
        MAX_UNCERTAIN_BITS = 2  # Allow at most 2 uncertain bits

        # Read binary strip with confidence
        bits, confidences, overall_confidence = self.read_binary_strip(frame)

        if bits is None or len(bits) != 16:
            return None, 0.0, "INVALID_FRAME"

        # Check overall confidence threshold
        if overall_confidence < MIN_CONFIDENCE:
            return None, overall_confidence, "LOW_CONFIDENCE"

        # Count low-confidence individual bits
        low_conf_bits = sum(1 for c in confidences if c < MIN_CONFIDENCE)
        if low_conf_bits > MAX_UNCERTAIN_BITS:
            return None, overall_confidence, f"TOO_MANY_UNCERTAIN_BITS:{low_conf_bits}"

        # Detect frame type from prefix bits
        prefix = bits[:2]
        suffix = bits[14:16]

        if bits == '1111111111111111':
            # Leader or Tail (0xFFFF)
            return ('leader', overall_confidence, "OK")
        elif bits == '0000000000000000':
            # Separator (0x0000)
            return ('separator', overall_confidence, "OK")
        elif prefix == '11':
            # Countdown: "11" + 4-bit countdown + 10-bit frames_until
            countdown_val = int(bits[2:6], 2)
            frames_until = int(bits[6:16], 2)
            return (('countdown', countdown_val, frames_until), overall_confidence, "OK")
        elif prefix == '00':
            # Lead-out: "00" + 4-bit count-up + 10-bit frames_since
            countup_val = int(bits[2:6], 2)
            frames_since = int(bits[6:16], 2)
            return (('leadout', countup_val, frames_since), overall_confidence, "OK")
        elif prefix == '10' and suffix == '01':
            # Timecode: "10" + 12-bit frame number + "01"
            frame_number = int(bits[2:14], 2)
            return (frame_number, overall_confidence, "OK")
        else:
            # Invalid marker pattern
            return None, overall_confidence, f"INVALID_MARKERS:prefix={prefix},suffix={suffix}"
    
    def detect_corner_markers(self, frame, red_lower=None, red_upper=None, blue_lower=None, blue_upper=None):
        """
        Detect colored corner markers in video frame (shared utility)
        
        Args:
            frame: Video frame (BGR)
            red_lower, red_upper: BGR color range for red markers (optional)
            blue_lower, blue_upper: BGR color range for blue markers (optional)
            
        Returns:
            dict: Corner detection results
        """
        # Use default color ranges if not provided
        if red_lower is None:
            red_lower = np.array([0, 0, 100], dtype="uint8")
        if red_upper is None:
            red_upper = np.array([50, 50, 255], dtype="uint8")
        if blue_lower is None:
            blue_lower = np.array([100, 0, 0], dtype="uint8")
        if blue_upper is None:
            blue_upper = np.array([255, 50, 50], dtype="uint8")
        
        height, width = frame.shape[:2]

        # Detect the red corners (top-left, bottom-right)
        red_mask = cv2.inRange(frame, red_lower, red_upper)

        # Detect the blue corners (top-right, bottom-left)
        blue_mask = cv2.inRange(frame, blue_lower, blue_upper)

        # Find contours for red markers
        red_contours, _ = cv2.findContours(red_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        blue_contours, _ = cv2.findContours(blue_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        red_corners = []
        blue_corners = []

        # Extract centroids of red corners
        for contour in red_contours:
            if cv2.contourArea(contour) > 50:  # Minimum size threshold
                M = cv2.moments(contour)
                if M["m00"] != 0:
                    cx = int(M["m10"] / M["m00"])
                    cy = int(M["m01"] / M["m00"])
                    red_corners.append((cx, cy))

        # Extract centroids of blue corners
        for contour in blue_contours:
            if cv2.contourArea(contour) > 50:  # Minimum size threshold
                M = cv2.moments(contour)
                if M["m00"] != 0:
                    cx = int(M["m10"] / M["m00"])
                    cy = int(M["m01"] / M["m00"])
                    blue_corners.append((cx, cy))

        # We expect 2 red corners (top-left, bottom-right) and 2 blue corners (top-right, bottom-left)
        if len(red_corners) >= 2 and len(blue_corners) >= 2:
            return {
                'red_corners': red_corners,
                'blue_corners': blue_corners,
                'detected': True
            }

        return {'detected': False}

    def correct_frame_perspective(self, frame, corner_info=None):
        """
        Use corner markers to correct perspective distortion in captured frames.

        The V2 encoding uses colored corner markers:
        - Red corners at top-left and bottom-right
        - Blue corners at top-right and bottom-left

        This method detects these corners and applies a perspective transform
        to correct for any skew or distortion from the VHS capture process.

        Args:
            frame: Video frame (BGR format)
            corner_info: Optional pre-detected corner info from detect_corner_markers()
                        If None, will detect corners automatically

        Returns:
            tuple: (corrected_frame, success, message)
                - corrected_frame: Perspective-corrected frame (or original if failed)
                - success: Boolean indicating if correction was applied
                - message: Status message explaining result
        """
        height, width = frame.shape[:2]

        # Detect corners if not provided
        if corner_info is None:
            corner_info = self.detect_corner_markers(frame)

        if not corner_info.get('detected', False):
            return frame, False, "Corners not detected"

        red_corners = corner_info['red_corners']
        blue_corners = corner_info['blue_corners']

        if len(red_corners) < 2 or len(blue_corners) < 2:
            return frame, False, f"Insufficient corners: {len(red_corners)} red, {len(blue_corners)} blue"

        # Sort corners by position to identify each corner
        # Red corners: top-left (smallest x+y) and bottom-right (largest x+y)
        # Blue corners: top-right (largest x, smallest y) and bottom-left (smallest x, largest y)

        # Sort red corners by x+y sum
        red_sorted = sorted(red_corners, key=lambda c: c[0] + c[1])
        top_left = red_sorted[0]  # Smallest x+y
        bottom_right = red_sorted[-1]  # Largest x+y

        # Sort blue corners - need to distinguish top-right from bottom-left
        # Top-right has large x, small y
        # Bottom-left has small x, large y
        blue_sorted = sorted(blue_corners, key=lambda c: c[0] - c[1])
        bottom_left = blue_sorted[0]  # Smallest x-y (small x, large y)
        top_right = blue_sorted[-1]  # Largest x-y (large x, small y)

        # Validate corner positions make sense
        # Top corners should have y < height/2, bottom corners y > height/2
        # Left corners should have x < width/2, right corners x > width/2
        if not (top_left[1] < height * 0.6 and top_left[0] < width * 0.6):
            return frame, False, f"Top-left corner position invalid: {top_left}"
        if not (top_right[1] < height * 0.6 and top_right[0] > width * 0.4):
            return frame, False, f"Top-right corner position invalid: {top_right}"
        if not (bottom_left[1] > height * 0.4 and bottom_left[0] < width * 0.6):
            return frame, False, f"Bottom-left corner position invalid: {bottom_left}"
        if not (bottom_right[1] > height * 0.4 and bottom_right[0] > width * 0.4):
            return frame, False, f"Bottom-right corner position invalid: {bottom_right}"

        # Source points (detected corners)
        src_points = np.float32([
            top_left,
            top_right,
            bottom_left,
            bottom_right
        ])

        # Destination points (ideal corner positions)
        # The corner markers are placed at corner_size pixels from the edges
        margin = self.corner_size // 2  # Center of the corner marker
        dst_points = np.float32([
            [margin, margin],                    # Top-left
            [width - margin, margin],            # Top-right
            [margin, height - margin],           # Bottom-left
            [width - margin, height - margin]    # Bottom-right
        ])

        # Calculate perspective transform matrix
        try:
            M = cv2.getPerspectiveTransform(src_points, dst_points)

            # Apply perspective transform
            corrected = cv2.warpPerspective(frame, M, (width, height))

            return corrected, True, "Perspective corrected successfully"

        except Exception as e:
            return frame, False, f"Transform failed: {str(e)}"

    def read_binary_strip_with_corners(self, frame, corner_info):
        """
        Read binary strip using corner markers for precise alignment (shared utility)
        
        Args:
            frame: Video frame (BGR or grayscale)
            corner_info: Corner detection results from detect_corner_markers()
            
        Returns:
            int: Frame number if successful, None if failed
        """
        height, width = frame.shape[:2]
        
        # Sort corners to identify positions
        red_corners = corner_info['red_corners']
        blue_corners = corner_info['blue_corners']
        
        # Find the top-left red corner and top-right blue corner
        top_left_red = min(red_corners, key=lambda p: p[0] + p[1])  # Minimum x+y
        top_right_blue = min(blue_corners, key=lambda p: -p[0] + p[1])  # Minimum -x+y
        
        # Calculate the expected binary strip region based on corner positions
        # The strip should be between x=40 and x=width-40 based on generator design
        strip_left = max(40, top_left_red[0] + 40)
        strip_right = min(width - 40, top_right_blue[0] - 40)
        strip_width = strip_right - strip_left
        
        if strip_width <= 0:
            return None
        
        # Extract the top 20 pixels in the strip region
        strip = frame[0:20, strip_left:strip_right]
        
        # Convert to grayscale
        if len(strip.shape) == 3:
            strip_gray = cv2.cvtColor(strip, cv2.COLOR_BGR2GRAY)
        else:
            strip_gray = strip
        
        # Read 32 bits from the aligned strip
        bits = []
        block_width = strip_width // 32
        
        for i in range(32):
            x_start = i * block_width
            x_end = min(x_start + block_width, strip_width)
            
            if x_end > x_start:
                # Sample the middle of this block
                block = strip_gray[:, x_start:x_end]
                avg_intensity = np.mean(block)
                
                # Try both normal and inverted thresholds
                bit_normal = '1' if avg_intensity > 128 else '0'
                bit_inverted = '0' if avg_intensity > 128 else '1'
                
                bits.append((bit_normal, bit_inverted))
        
        if len(bits) == 32:
            # Try both normal and inverted bit patterns
            for bit_pattern in ['normal', 'inverted']:
                binary_str = ''.join([bit[0] if bit_pattern == 'normal' else bit[1] for bit in bits])
                try:
                    frame_number = int(binary_str, 2)
                    # Basic sanity check
                    if 0 <= frame_number <= 1000000:  # Reasonable range
                        return frame_number
                except ValueError:
                    continue
        
        return None
    
    def frame_to_timecode(self, frame_number):
        """Convert frame number to timecode string"""
        if self.format_type == "PAL":
            fps = 25
        else:  # NTSC
            fps = 30  # Use 30 for display
        
        total_seconds = frame_number // fps
        frame_remainder = frame_number % fps
        
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60
        
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}:{frame_remainder:02d}"
    
    def generate_metadata(self, total_frames, duration_seconds):
        """Generate metadata for the V2 robust timecode system"""
        return {
            "timecode_metadata": {
                "generator": "VHS Robust Timecode Generator V2.0",
                "method_version": "2.0",
                "encoding_version": "V2",
                "timestamp": datetime.now().isoformat(),
                "format": self.format_type,
                "fps": self.fps,
                "resolution": f"{self.width}x{self.height}",
                "duration_seconds": duration_seconds,
                "total_frames": total_frames
            },
            "encoding_parameters": {
                "audio_sample_rate": self.sample_rate,
                "audio_channels": self.audio_channels,  # MONO
                "freq_0": self.freq_0,  # 400Hz for '0'
                "freq_1": self.freq_1,  # 800Hz for '1'
                "freq_pilot": self.freq_pilot,  # 1200Hz pilot tone
                "freq_0_range": self.freq_0_range,  # Detection range (300-500Hz)
                "freq_1_range": self.freq_1_range,  # Detection range (650-950Hz)
                "freq_pilot_range": self.freq_pilot_range,  # (1050-1350Hz)
                "bits_per_frame": self.bits_per_frame,  # 16 bits
                "samples_per_bit": self.samples_per_bit,  # ~120 samples
                "frame_structure": "10% pilot + 5% silence + 80% data + 5% silence"
            },
            "v2_visual_encoding": {
                "strip_height": f"{self.strip_height}px (3 rows x 20px)",
                "block_count": 16,
                "block_width": "~40px",
                "bit_1_color": "red (BGR: 0,0,255)",
                "bit_0_color": "blue (BGR: 255,0,0)",
                "background": "mid-gray (128,128,128)"
            },
            "v2_frame_types": {
                "leader": "0xFFFF (all 1s) - preparation/tail marker",
                "separator": "0x0000 (all 0s) - section transition",
                "countdown": "'11' + 4-bit countdown + 10-bit frames_until",
                "timecode": "'10' + 12-bit frame + '01' suffix",
                "leadout": "'00' + 4-bit countup + 10-bit frames_since"
            },
            "robustness_features": {
                "frequency_separation": f"{self.freq_1 - self.freq_0}Hz (2:1 ratio)",
                "guard_band_separation": f"{self.freq_1_range[0] - self.freq_0_range[1]}Hz",
                "pilot_tone": f"{self.freq_pilot}Hz for frame synchronization",
                "detection_methods": ["spectrogram", "pilot_sync", "zero_crossing", "color_based"],
                "visual_redundancy": "3 vertical rows with majority voting",
                "center_sampling": "Skip 25% margins to avoid edge contamination",
                "confidence_reporting": "Per-bit and per-frame confidence scores",
                "mono_audio": "Eliminates stereo channel confusion"
            },
            "usage_instructions": {
                "audio_channel": f"MONO - FSK-encoded ({self.freq_0}Hz='0', {self.freq_1}Hz='1')",
                "visual_timecode": "Human-readable HH:MM:SS:FF format",
                "binary_strip": "V2 16-bit color-coded strip (top 60px)",
                "sync_markers": "Red/Blue corner markers for perspective correction",
                "vhs_optimized": "Lower frequencies (400/800Hz) for VHS linear audio track"
            }
        }
    
    def _decode_frame_segment_enhanced(self, frame_audio):
        """
        Enhanced frame segment decoder with stricter validation
        
        Args:
            frame_audio: Audio samples for one frame
            
        Returns:
            tuple: (frame_id, confidence) or None if decode failed
        """
        # Use original decoding logic
        result = self._decode_frame_segment(frame_audio)
        
        if result is None:
            return None
        
        frame_id, confidence = result
        
        # Enhanced validation: require higher confidence
        if confidence < 0.75:  # Increased confidence threshold
            return None
        
        # Validate that the frame has reasonable signal strength
        if not self._validate_signal_strength(frame_audio):
            return None
        
        return frame_id, confidence
    
    def _validate_frame_id_range(self, frame_id):
        """
        Validate that frame ID is in reasonable range
        
        Args:
            frame_id: Decoded frame ID
            
        Returns:
            bool: True if frame ID is reasonable
        """
        # Frame ID should be reasonable for 30-second timecode (0-749 for PAL)
        max_expected_frames = int(30 * self.fps) + 50  # Add buffer
        
        if not (0 <= frame_id <= max_expected_frames):
            return False
        
        # Reject frame IDs that are suspiciously large (likely false positives)
        if frame_id > 16777215:  # 2^24 - 1 (max 24-bit value)
            return False
        
        return True
    
    def _validate_signal_strength(self, frame_audio):
        """
        Validate that the audio signal has reasonable strength for FSK
        
        Args:
            frame_audio: Audio samples for the frame
            
        Returns:
            bool: True if signal strength is reasonable
        """
        # Calculate RMS power
        rms = np.sqrt(np.mean(frame_audio**2))
        
        # Reject signals that are too weak (likely noise) or too strong (likely clipping)
        if rms < 0.01 or rms > 0.9:
            return False
        
        # Check that signal has reasonable dynamics (not constant)
        signal_std = np.std(frame_audio)
        if signal_std < 0.005:  # Signal too flat
            return False
        
        return True
    
    def _filter_overlapping_detections(self, raw_detections):
        """
        Filter overlapping detections to remove duplicates
        
        Args:
            raw_detections: List of (sample_pos, frame_id, confidence) tuples
            
        Returns:
            list: Filtered detections with duplicates removed
        """
        if not raw_detections:
            return []
        
        # Sort by sample position
        raw_detections.sort(key=lambda x: x[0])
        
        filtered = []
        frame_samples = self.samples_per_frame
        
        i = 0
        while i < len(raw_detections):
            sample_pos, frame_id, confidence = raw_detections[i]
            
            # Find all detections within one frame window
            window_detections = []
            j = i
            while j < len(raw_detections) and raw_detections[j][0] < sample_pos + frame_samples:
                window_detections.append(raw_detections[j])
                j += 1
            
            # Select best detection from this window
            best_detection = self._select_best_detection(window_detections)
            if best_detection is not None:
                filtered.append(best_detection)
            
            # Move to next non-overlapping window
            i = j
        
        return filtered
    
    def _select_best_detection(self, window_detections):
        """
        Select the best detection from overlapping detections
        
        Args:
            window_detections: List of detections in the same time window
            
        Returns:
            tuple: Best detection or None
        """
        if not window_detections:
            return None
        
        # Group by frame ID
        frame_groups = {}
        for detection in window_detections:
            sample_pos, frame_id, confidence = detection
            if frame_id not in frame_groups:
                frame_groups[frame_id] = []
            frame_groups[frame_id].append(detection)
        
        # If only one frame ID, return highest confidence detection
        if len(frame_groups) == 1:
            return max(window_detections, key=lambda x: x[2])
        
        # Multiple frame IDs - choose the one with highest average confidence
        best_frame_id = None
        best_avg_confidence = 0
        
        for frame_id, detections in frame_groups.items():
            avg_confidence = np.mean([conf for _, _, conf in detections])
            if avg_confidence > best_avg_confidence:
                best_avg_confidence = avg_confidence
                best_frame_id = frame_id
        
        if best_frame_id is not None:
            # Return the highest confidence detection for the best frame ID
            best_detections = frame_groups[best_frame_id]
            return max(best_detections, key=lambda x: x[2])

        return None

    # =========================================================================
    # V2 Spectrogram-Based FSK Decoding
    # =========================================================================

    def decode_fsk_spectrogram(self, audio_channel):
        """
        Spectrogram-based FSK decoding for better timing tolerance.

        Uses scipy's spectrogram to analyze frequency content over time,
        providing more robust detection than bit-by-bit approaches when
        timing is uncertain (common with VHS captures).

        Args:
            audio_channel: Mono audio samples

        Returns:
            list: List of (sample_position, decoded_result, confidence) tuples
                  where decoded_result is the return from decode_frame_with_validation
        """
        try:
            from scipy.signal import spectrogram
        except ImportError:
            print("Warning: scipy not available, falling back to standard FSK decoder")
            return self.decode_fsk_audio(audio_channel, strict=False)

        results = []

        # Compute spectrogram with overlapping windows
        # Using ~10ms windows (480 samples at 48kHz) with 50% overlap
        nperseg = 480
        noverlap = 240

        f, t, Sxx = spectrogram(audio_channel, fs=self.sample_rate,
                                nperseg=nperseg, noverlap=noverlap)

        # Find frequency bin indices for our target frequencies
        f0_idx = np.argmin(np.abs(f - self.freq_0))  # 400 Hz
        f1_idx = np.argmin(np.abs(f - self.freq_1))  # 800 Hz
        pilot_idx = np.argmin(np.abs(f - self.freq_pilot))  # 1200 Hz

        # Get power at each frequency
        f0_power = Sxx[f0_idx, :]
        f1_power = Sxx[f1_idx, :]
        pilot_power = Sxx[pilot_idx, :]

        # Find frame boundaries using pilot tone detection
        # The pilot tone appears at the start of each frame
        pilot_threshold = np.mean(pilot_power) + 2 * np.std(pilot_power)
        pilot_peaks = np.where(pilot_power > pilot_threshold)[0]

        # Group pilot peaks into frame starts
        frame_starts_time = []
        if len(pilot_peaks) > 0:
            current_group_start = pilot_peaks[0]
            for i in range(1, len(pilot_peaks)):
                # If gap is larger than expected pilot duration, it's a new frame
                expected_pilot_bins = int((self.samples_per_frame * self.pilot_ratio) /
                                          (nperseg - noverlap))
                if pilot_peaks[i] - pilot_peaks[i-1] > expected_pilot_bins * 2:
                    frame_starts_time.append(t[current_group_start])
                    current_group_start = pilot_peaks[i]
            frame_starts_time.append(t[current_group_start])

        # For each detected frame, decode the FSK bits
        for frame_start_time in frame_starts_time:
            sample_pos = int(frame_start_time * self.sample_rate)

            # Extract audio for this frame
            frame_end_sample = min(sample_pos + self.samples_per_frame, len(audio_channel))
            if frame_end_sample <= sample_pos:
                continue

            frame_audio = audio_channel[sample_pos:frame_end_sample]

            # Decode the FSK bits from this frame
            decoded_bits = self._decode_bits_from_spectrogram(frame_audio, f, Sxx, t, frame_start_time)

            if decoded_bits is not None and len(decoded_bits) == 16:
                # Parse the 16-bit pattern
                result = self._parse_v2_bits(decoded_bits)
                if result is not None:
                    results.append((sample_pos, result, 0.8))  # Spectrogram confidence

        return results

    def _decode_bits_from_spectrogram(self, frame_audio, f, Sxx, t, frame_start_time):
        """
        Decode individual bits from spectrogram data.

        Args:
            frame_audio: Audio samples for one frame
            f: Frequency bins from spectrogram
            Sxx: Spectrogram power data
            t: Time bins from spectrogram
            frame_start_time: Start time of this frame in seconds

        Returns:
            str: 16-character binary string or None if failed
        """
        try:
            from scipy.signal import spectrogram as sp
        except ImportError:
            return None

        # Compute a local spectrogram for just this frame
        if len(frame_audio) < 256:
            return None

        f_local, t_local, Sxx_local = sp(frame_audio, fs=self.sample_rate,
                                          nperseg=256, noverlap=128)

        f0_idx = np.argmin(np.abs(f_local - self.freq_0))
        f1_idx = np.argmin(np.abs(f_local - self.freq_1))

        f0_power = Sxx_local[f0_idx, :]
        f1_power = Sxx_local[f1_idx, :]

        # Skip the pilot tone portion (first 10% + 5% silence = 15%)
        data_start_bin = int(len(t_local) * 0.15)
        data_end_bin = int(len(t_local) * 0.95)

        if data_start_bin >= data_end_bin:
            return None

        # Divide data region into 16 bits
        data_bins = data_end_bin - data_start_bin
        bins_per_bit = data_bins // 16

        if bins_per_bit < 1:
            return None

        bits = []
        for i in range(16):
            bit_start = data_start_bin + (i * bins_per_bit)
            bit_end = bit_start + bins_per_bit

            # Compare power at f0 vs f1 for this bit
            f0_bit_power = np.mean(f0_power[bit_start:bit_end])
            f1_bit_power = np.mean(f1_power[bit_start:bit_end])

            # '1' = high frequency (f1), '0' = low frequency (f0)
            bit = '1' if f1_bit_power > f0_bit_power else '0'
            bits.append(bit)

        return ''.join(bits)

    def _parse_v2_bits(self, bits):
        """
        Parse a 16-bit V2 encoded pattern.

        Args:
            bits: 16-character binary string

        Returns:
            tuple or None: Parsed result based on frame type
        """
        if len(bits) != 16:
            return None

        prefix = bits[:2]
        suffix = bits[14:16]

        if bits == '1111111111111111':
            return ('leader', 1.0)
        elif bits == '0000000000000000':
            return ('separator', 1.0)
        elif prefix == '11':
            # Countdown
            countdown_val = int(bits[2:6], 2)
            frames_until = int(bits[6:16], 2)
            return (('countdown', countdown_val, frames_until), 0.9)
        elif prefix == '00':
            # Lead-out
            countup_val = int(bits[2:6], 2)
            frames_since = int(bits[6:16], 2)
            return (('leadout', countup_val, frames_since), 0.9)
        elif prefix == '10' and suffix == '01':
            # Timecode
            frame_number = int(bits[2:14], 2)
            return (frame_number, 0.95)
        else:
            return None

    # =========================================================================
    # V2 Pilot Tone Detection for Frame Synchronization
    # =========================================================================

    def detect_pilot_tones(self, audio_channel):
        """
        Detect 1200Hz pilot tones to identify frame boundaries in audio.

        The V2 encoding places a 1200Hz pilot tone at the start of each frame
        (first 10% of frame duration). This method detects these pilot tones
        to synchronize audio frame boundaries.

        Args:
            audio_channel: Mono audio samples

        Returns:
            dict: Detection results including:
                - 'frame_starts': List of sample positions where frames start
                - 'pilot_confidence': Average detection confidence (0-1)
                - 'detected_count': Number of pilot tones detected
                - 'expected_count': Expected number based on audio duration
        """
        try:
            from scipy.signal import butter, filtfilt
        except ImportError:
            # Fallback without scipy
            return self._detect_pilot_tones_simple(audio_channel)

        # Design a bandpass filter around 1200Hz
        nyquist = self.sample_rate / 2
        low_freq = (self.freq_pilot_range[0]) / nyquist
        high_freq = (self.freq_pilot_range[1]) / nyquist

        # Ensure frequencies are valid for filter design
        low_freq = max(0.01, min(0.99, low_freq))
        high_freq = max(low_freq + 0.01, min(0.99, high_freq))

        try:
            b, a = butter(4, [low_freq, high_freq], btype='band')
            filtered = filtfilt(b, a, audio_channel)
        except Exception:
            # Filter design failed, use simple approach
            return self._detect_pilot_tones_simple(audio_channel)

        # Compute envelope using absolute value and smoothing
        envelope = np.abs(filtered)
        # Smooth with moving average
        window_size = int(self.sample_rate * 0.005)  # 5ms window
        if window_size > 1:
            envelope = np.convolve(envelope, np.ones(window_size)/window_size, mode='same')

        # Calculate expected pilot duration in samples
        pilot_samples = int(self.samples_per_frame * self.pilot_ratio)  # ~192 samples

        # Dynamic threshold based on signal statistics
        threshold = np.mean(envelope) + 2 * np.std(envelope)

        # Find regions above threshold
        above_threshold = envelope > threshold

        # Find rising edges (transitions from below to above threshold)
        edges = np.diff(above_threshold.astype(int))
        rising_edges = np.where(edges == 1)[0]

        # Filter rising edges to ensure minimum spacing (one frame apart)
        min_spacing = int(self.samples_per_frame * 0.8)  # At least 80% of a frame
        frame_starts = []
        last_start = -min_spacing

        for edge in rising_edges:
            if edge - last_start >= min_spacing:
                frame_starts.append(edge)
                last_start = edge

        # Calculate expected count based on audio duration
        expected_count = len(audio_channel) // self.samples_per_frame

        # Calculate confidence
        if expected_count > 0:
            detection_ratio = len(frame_starts) / expected_count
            # Good confidence if we detect close to expected number
            confidence = max(0.0, min(1.0, 1.0 - abs(1.0 - detection_ratio)))
        else:
            confidence = 0.0

        return {
            'frame_starts': frame_starts,
            'pilot_confidence': confidence,
            'detected_count': len(frame_starts),
            'expected_count': expected_count
        }

    def _detect_pilot_tones_simple(self, audio_channel):
        """
        Simple pilot tone detection without scipy (using FFT).

        Args:
            audio_channel: Mono audio samples

        Returns:
            dict: Detection results
        """
        frame_starts = []
        window_size = int(self.samples_per_frame * self.pilot_ratio * 2)  # ~384 samples
        hop_size = self.samples_per_frame // 4  # Check every quarter frame

        # Scan through audio looking for pilot tone
        for start in range(0, len(audio_channel) - window_size, hop_size):
            window = audio_channel[start:start + window_size]

            # FFT to detect 1200Hz
            fft_result = np.fft.fft(window)
            freqs = np.fft.fftfreq(len(window), 1/self.sample_rate)

            # Find power at pilot frequency
            pilot_idx = np.argmin(np.abs(freqs - self.freq_pilot))
            pilot_power = np.abs(fft_result[pilot_idx])

            # Find power at neighboring frequencies (for comparison)
            total_power = np.sum(np.abs(fft_result[:len(fft_result)//2]))

            if total_power > 0:
                pilot_ratio = pilot_power / total_power
                # If pilot frequency dominates, this is likely a pilot tone
                if pilot_ratio > 0.3:  # Pilot is at least 30% of total power
                    # Check if this is a new frame (not too close to previous)
                    if len(frame_starts) == 0 or start - frame_starts[-1] >= self.samples_per_frame * 0.8:
                        frame_starts.append(start)

        expected_count = len(audio_channel) // self.samples_per_frame
        detection_ratio = len(frame_starts) / expected_count if expected_count > 0 else 0
        confidence = max(0.0, min(1.0, 1.0 - abs(1.0 - detection_ratio)))

        return {
            'frame_starts': frame_starts,
            'pilot_confidence': confidence,
            'detected_count': len(frame_starts),
            'expected_count': expected_count
        }

    def decode_fsk_with_pilot_sync(self, audio_channel):
        """
        Decode FSK audio using pilot tone synchronization for frame boundaries.

        This method first detects pilot tones to find frame boundaries,
        then decodes each frame's FSK data. This provides better accuracy
        than fixed-boundary decoding when timing is uncertain.

        Args:
            audio_channel: Mono audio samples

        Returns:
            list: List of (sample_position, decoded_result, confidence) tuples
        """
        # First, detect pilot tones to find frame boundaries
        pilot_info = self.detect_pilot_tones(audio_channel)
        frame_starts = pilot_info['frame_starts']

        if len(frame_starts) == 0:
            # No pilot tones detected, fall back to standard decoding
            return self.decode_fsk_audio(audio_channel, strict=False)

        results = []

        for i, frame_start in enumerate(frame_starts):
            # Determine frame end (next pilot or end of audio)
            if i + 1 < len(frame_starts):
                frame_end = frame_starts[i + 1]
            else:
                frame_end = min(frame_start + self.samples_per_frame, len(audio_channel))

            if frame_end <= frame_start:
                continue

            frame_audio = audio_channel[frame_start:frame_end]

            # Skip pilot portion and decode FSK data
            data_start = int(len(frame_audio) * (self.pilot_ratio + self.silence_ratio))
            data_end = int(len(frame_audio) * (1.0 - self.silence_ratio))

            if data_end <= data_start:
                continue

            data_audio = frame_audio[data_start:data_end]

            # Decode the 16 bits
            bits = self._decode_bits_from_audio(data_audio)

            if bits is not None and len(bits) == 16:
                result = self._parse_v2_bits(bits)
                if result is not None:
                    confidence = 0.85 + (pilot_info['pilot_confidence'] * 0.1)
                    results.append((frame_start, result, confidence))

        return results

    def _decode_bits_from_audio(self, audio_data):
        """
        Decode 16 FSK bits from audio data.

        Args:
            audio_data: Audio samples containing 16 bits of FSK data

        Returns:
            str: 16-character binary string or None if failed
        """
        if len(audio_data) < 16:
            return None

        samples_per_bit = len(audio_data) // 16
        bits = []

        for i in range(16):
            bit_start = i * samples_per_bit
            bit_end = bit_start + samples_per_bit
            bit_audio = audio_data[bit_start:bit_end]

            # Use zero-crossing rate to determine frequency
            # Higher ZCR = higher frequency = '1'
            # Lower ZCR = lower frequency = '0'
            zero_crossings = np.sum(np.abs(np.diff(np.sign(bit_audio))) > 0)
            zcr = zero_crossings / len(bit_audio) * self.sample_rate

            # Expected ZCR: freq_0 (400Hz) ≈ 800 crossings/sec, freq_1 (800Hz) ≈ 1600 crossings/sec
            threshold = (self.freq_0 + self.freq_1) / 2 * 2  # ≈ 1200
            bit = '1' if zcr > threshold else '0'
            bits.append(bit)

        return ''.join(bits)

    # =========================================================================
    # V2 State Machine Decoder
    # =========================================================================

    class DecoderState:
        """State machine states for V2 calibration cycle decoding"""
        SEARCHING = 'SEARCHING'
        IN_LEADER = 'IN_LEADER'
        IN_COUNTDOWN = 'IN_COUNTDOWN'
        READY_FOR_TIMECODE = 'READY_FOR_TIMECODE'
        READING_TIMECODE = 'READING_TIMECODE'
        TIMECODE_COMPLETE = 'TIMECODE_COMPLETE'
        IN_LEADOUT = 'IN_LEADOUT'
        CYCLE_COMPLETE = 'CYCLE_COMPLETE'

    def decode_with_state_machine(self, video_frames, get_frame_func=None):
        """
        State machine decoder for V2 structured calibration video.

        Processes video frames using a state machine to track the calibration
        cycle structure (Leader -> Countdown -> Separator -> Timecode ->
        Separator -> Count-up -> Tail).

        Args:
            video_frames: Either a list of frames or total frame count
            get_frame_func: Optional function to get frame by index.
                           If None, video_frames must be a list.

        Returns:
            dict: Decoding results including:
                - 'timecode_frames': List of (video_frame_num, decoded_frame_num, confidence)
                - 'state_transitions': List of (video_frame_num, old_state, new_state)
                - 'cycles_detected': Number of complete cycles found
                - 'errors': List of error messages
        """
        results = {
            'timecode_frames': [],
            'state_transitions': [],
            'cycles_detected': 0,
            'errors': []
        }

        state = self.DecoderState.SEARCHING
        cycles = 0
        consecutive_leader_frames = 0
        leader_threshold = 5  # Frames needed to confirm leader

        # Determine iteration method
        if get_frame_func is not None:
            frame_count = video_frames
            get_frame = get_frame_func
        else:
            frame_count = len(video_frames)
            get_frame = lambda i: video_frames[i]

        for frame_num in range(frame_count):
            try:
                frame = get_frame(frame_num)
                decoded, confidence, status = self.decode_frame_with_validation(frame)
            except Exception as e:
                results['errors'].append(f"Frame {frame_num}: {str(e)}")
                continue

            if status != "OK":
                # Frame decode failed - may indicate transition or noise
                consecutive_leader_frames = 0
                continue

            old_state = state

            # State machine transitions based on decoded content
            if decoded == 'leader':
                consecutive_leader_frames += 1
                if state == self.DecoderState.SEARCHING and consecutive_leader_frames >= leader_threshold:
                    state = self.DecoderState.IN_LEADER
                elif state == self.DecoderState.IN_LEADOUT:
                    state = self.DecoderState.CYCLE_COMPLETE
                    cycles += 1

            elif decoded == 'separator':
                consecutive_leader_frames = 0
                if state == self.DecoderState.IN_COUNTDOWN:
                    state = self.DecoderState.READY_FOR_TIMECODE
                elif state == self.DecoderState.READING_TIMECODE:
                    state = self.DecoderState.TIMECODE_COMPLETE

            elif isinstance(decoded, tuple) and decoded[0] == 'countdown':
                consecutive_leader_frames = 0
                state = self.DecoderState.IN_COUNTDOWN

            elif isinstance(decoded, tuple) and decoded[0] == 'leadout':
                consecutive_leader_frames = 0
                state = self.DecoderState.IN_LEADOUT

            elif isinstance(decoded, int):
                # Timecode frame number
                consecutive_leader_frames = 0
                if state in (self.DecoderState.READY_FOR_TIMECODE, self.DecoderState.READING_TIMECODE):
                    state = self.DecoderState.READING_TIMECODE
                    results['timecode_frames'].append((frame_num, decoded, confidence))

            # Record state transitions
            if state != old_state:
                results['state_transitions'].append((frame_num, old_state, state))

            # Reset for next cycle
            if state == self.DecoderState.CYCLE_COMPLETE:
                state = self.DecoderState.SEARCHING
                consecutive_leader_frames = 0

        results['cycles_detected'] = cycles
        return results

    def calculate_calibration_offset(self, state_machine_results):
        """
        Calculate the audio/video offset from state machine decoding results.

        Uses multi-point sampling with averaging to get a robust offset measurement.

        Args:
            state_machine_results: Results dict from decode_with_state_machine()

        Returns:
            dict: Offset analysis including:
                - 'mean_offset': Average offset in frames
                - 'std_offset': Standard deviation of offsets
                - 'sample_count': Number of samples used
                - 'confidence': Overall confidence (0-1)
                - 'offsets': List of individual offset measurements
        """
        timecode_frames = state_machine_results.get('timecode_frames', [])

        if len(timecode_frames) < 3:
            return {
                'mean_offset': None,
                'std_offset': None,
                'sample_count': len(timecode_frames),
                'confidence': 0.0,
                'offsets': [],
                'error': 'Insufficient timecode frames for calibration'
            }

        offsets = []
        for video_frame_num, decoded_frame_num, confidence in timecode_frames:
            # The offset is the difference between where we found the frame
            # and what frame number it claims to be
            # If video frame 100 contains timecode frame 95, offset is +5
            offset = video_frame_num - decoded_frame_num
            offsets.append(offset)

        # Use robust statistics (median and MAD) to handle outliers
        median_offset = np.median(offsets)
        mad = np.median(np.abs(np.array(offsets) - median_offset))

        # Filter outliers (more than 3 MAD from median)
        filtered_offsets = [o for o in offsets if abs(o - median_offset) <= 3 * mad]

        if len(filtered_offsets) < 3:
            filtered_offsets = offsets  # Fall back to all if too many filtered

        mean_offset = np.mean(filtered_offsets)
        std_offset = np.std(filtered_offsets)

        # Confidence based on consistency (low std = high confidence)
        max_acceptable_std = 5.0  # 5 frames of variation is acceptable
        confidence = max(0.0, 1.0 - (std_offset / max_acceptable_std))

        return {
            'mean_offset': mean_offset,
            'std_offset': std_offset,
            'sample_count': len(filtered_offsets),
            'confidence': confidence,
            'offsets': filtered_offsets,
            'outliers_removed': len(offsets) - len(filtered_offsets)
        }
