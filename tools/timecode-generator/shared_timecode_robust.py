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
        
        # ROBUST frequency selection for VHS
        # Wide separation: 800Hz for '0', 1600Hz for '1' (2:1 ratio)
        self.freq_0 = 800   # Low frequency for '0' bit
        self.freq_1 = 1600  # High frequency for '1' bit (exactly double)
        
        # Detection ranges with significant guard bands
        self.freq_0_range = (650, 950)    # 300Hz guard band around 800Hz
        self.freq_1_range = (1350, 1850) # 250Hz guard band around 1600Hz
        # No overlap: 950Hz < 1350Hz, 400Hz separation between ranges
        
        # Bit timing for reliable encoding
        self.samples_per_frame = int(self.sample_rate / self.fps)
        self.bits_per_frame = 32  # 24-bit frame + 8-bit checksum
        self.samples_per_bit = self.samples_per_frame // self.bits_per_frame
        
        # Visual parameters
        self.font_scale = 3.0
        self.font_thickness = 8
        self.text_color = (255, 255, 255)  # White text
        self.bg_color = (0, 0, 0)          # Black background
        
        # Corner marker colors (BGR format)
        self.corner_color_primary = (0, 0, 255)    # Red corners
        self.corner_color_secondary = (255, 0, 0)  # Blue corners

    def generate_frame_image(self, frame_number, timecode_str):
        """Generate a single frame with visual timecode"""
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
        
        # Add frame number in top-left corner
        frame_text = f"Frame: {frame_number:06d}"
        cv2.putText(frame, frame_text, (20, 70), font, 
                   1.0, self.text_color, 2)
        
        # Add format info in top-right corner
        format_text = f"{self.format_type} {self.fps}fps - ROBUST FSK"
        (fw, fh), _ = cv2.getTextSize(format_text, font, 0.7, 2)
        cv2.putText(frame, format_text, (self.width - fw - 20, 70), font, 
                   0.7, self.text_color, 2)
        
        # Add machine-readable patterns
        self._add_sync_patterns(frame, frame_number)
        
        return frame
    
    def _add_sync_patterns(self, frame, frame_number):
        """Add machine-readable sync patterns to frame"""
        # Add binary representation as visual blocks (top edge)
        binary = format(frame_number, '032b')  # 32-bit binary
        
        # Position binary blocks between corner markers
        available_width = self.width - 80  # Total width minus 40px corners
        block_width = available_width // 32
        start_offset = 40  # Start after left corner
        
        for i, bit in enumerate(binary):
            x_start = start_offset + (i * block_width)
            x_end = min(x_start + block_width, self.width - 40)
            
            # White for 1, dark gray for 0 (still visible)
            color = (255, 255, 255) if bit == '1' else (64, 64, 64)
            cv2.rectangle(frame, (x_start, 0), (x_end, 20), color, -1)
        
        # Add sync markers in corners
        marker_size = 40
        
        # Top-left and bottom-right: red squares
        cv2.rectangle(frame, (0, 0), (marker_size, marker_size), self.corner_color_primary, -1)
        cv2.rectangle(frame, (self.width - marker_size, self.height - marker_size), 
                     (self.width, self.height), self.corner_color_primary, -1)
        
        # Top-right and bottom-left: blue squares
        cv2.rectangle(frame, (self.width - marker_size, 0), 
                     (self.width, marker_size), self.corner_color_secondary, -1)
        cv2.rectangle(frame, (0, self.height - marker_size), 
                     (marker_size, self.height), self.corner_color_secondary, -1)
    
    def generate_robust_fsk_audio(self, frame_number):
        """
        Generate robust FSK audio for a single frame
        
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
        
        # Generate audio samples
        audio = np.zeros(self.samples_per_frame)
        
        for i, bit in enumerate(data_bits):
            start_sample = i * self.samples_per_bit
            end_sample = min(start_sample + self.samples_per_bit, self.samples_per_frame)
            
            # Select frequency based on bit value
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
        Read binary timecode from top strip of video frame (shared utility)
        
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
        # If strip is very dark (mean < 100), use mean + std/2 as threshold
        # Otherwise use traditional 128 threshold
        if strip_mean < 100 and strip_std > 20:
            threshold = strip_mean + (strip_std * 0.5)
        else:
            threshold = 128
        
        # Read 32 bits
        bits = []
        block_width = width // 32
        
        for i in range(32):
            x_start = i * block_width
            x_end = min(x_start + block_width, width)
            
            if x_end > x_start:
                # Sample the middle of this block
                block = strip_gray[:, x_start:x_end]
                avg_intensity = np.mean(block)
                
                # Use adaptive threshold
                bit = '1' if avg_intensity > threshold else '0'
                bits.append(bit)
        
        if len(bits) == 32:
            # Convert binary to frame number
            binary_str = ''.join(bits)
            try:
                frame_number = int(binary_str, 2)
                # Use robust frame ID validation
                if self._validate_frame_id_range(frame_number):
                    return frame_number
            except ValueError:
                pass
        
        return None
    
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
        """Generate metadata for the robust timecode system"""
        return {
            "timecode_metadata": {
                "generator": "VHS Robust Timecode Generator v2.0",
                "method_version": "2.0",  # Robust version
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
                "freq_0": self.freq_0,  # 800Hz for '0'
                "freq_1": self.freq_1,  # 1600Hz for '1'
                "freq_0_range": self.freq_0_range,  # Detection range
                "freq_1_range": self.freq_1_range,  # Detection range
                "bits_per_frame": self.bits_per_frame,
                "samples_per_bit": self.samples_per_bit,
                "checksum_method": "enhanced_xor_rotation"
            },
            "robustness_features": {
                "frequency_separation": f"{self.freq_1 - self.freq_0}Hz (2:1 ratio)",
                "guard_band_separation": f"{self.freq_1_range[0] - self.freq_0_range[1]}Hz",
                "detection_methods": ["fft_amplitude", "zero_crossing_rate", "autocorrelation"],
                "error_correction": "enhanced_checksum_with_voting",
                "mono_audio": "eliminates_stereo_channel_confusion"
            },
            "usage_instructions": {
                "audio_channel": "MONO - FSK-encoded frame numbers (800Hz='0', 1600Hz='1')",
                "visual_timecode": "Human-readable HH:MM:SS:FF format",
                "binary_strip": "Machine-readable frame number (top edge)",
                "sync_markers": "Colored corner markers for frame detection",
                "vhs_optimized": "Wide frequency separation and robust detection for VHS recording/playback"
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
