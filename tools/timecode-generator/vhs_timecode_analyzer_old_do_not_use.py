#!/usr/bin/env python3
"""
VHS Timecode Analyzer for Precise Audio/Video Alignment - ROBUST FSK VERSION

This script analyzes captured VHS timecode test patterns to determine
precise audio/video synchronization offsets with microsecond accuracy.

It processes both the visual timecode and ROBUST FSK audio encoding to correlate
video frames with audio samples, providing detailed alignment measurements.

The analyzer now uses the robust FSK decoding system with:
- Wide frequency separation (800Hz vs 1600Hz)
- Multi-method voting detection
- Enhanced checksum verification
- Mono audio processing

Usage:
    python3 vhs_timecode_analyzer.py --video captured_video.mkv --audio captured_audio.wav
"""

import cv2
import numpy as np
import subprocess
import argparse
import os
import sys
import json
from datetime import datetime
import re
from shared_timecode_robust import SharedTimecodeRobust

class VHSTimecodeAnalyzer:
    def __init__(self, video_file, audio_file, metadata_file=None, vhs_calibration=False):
        """
        Initialize VHS timecode analyzer
        
        Args:
            video_file: Path to captured video file
            audio_file: Path to captured audio file
            metadata_file: Optional metadata from timecode generation
            vhs_calibration: Enable VHS-specific enhancements for step 5.2
        """
        self.video_file = video_file
        self.audio_file = audio_file
        self.metadata_file = metadata_file
        self.vhs_calibration = vhs_calibration  # Store VHS calibration mode flag
        
        # Default parameters (will be updated from metadata if available)
        # ROBUST FSK frequencies: 800Hz for '0', 1600Hz for '1'
        self.base_frequency = 800  # Changed from 1000 to match robust generator
        self.sync_frequency = 2000
        self.sample_rate = 48000
        self.expected_fps = 25.0
        # Color boundaries for detecting corner markers (BGR format)
        self.red_lower = np.array([0, 0, 100], dtype="uint8")
        self.red_upper = np.array([50, 50, 255], dtype="uint8")
        self.blue_lower = np.array([100, 0, 0], dtype="uint8")
        self.blue_upper = np.array([255, 50, 50], dtype="uint8")
        
        # Results storage
        self.video_timecodes = []  # List of (frame_number, detected_frame_id, confidence)
        self.audio_timecodes = []  # List of (sample_offset, decoded_frame_id, confidence)
        self.sync_pulses = []      # List of (sample_offset, confidence)
        
        # Load metadata if available
        if metadata_file and os.path.exists(metadata_file):
            self._load_metadata(metadata_file)
    
    def _load_metadata(self, metadata_file):
        """Load metadata from timecode generation"""
        try:
            with open(metadata_file, 'r') as f:
                metadata = json.load(f)
            
            encoding_params = metadata.get('encoding_parameters', {})
            timecode_meta = metadata.get('timecode_metadata', {})
            
            # Check method version compatibility
            method_version = timecode_meta.get('method_version', '1.0')
            if method_version != '1.0':
                print(f"Warning: Metadata method version {method_version} may not be fully compatible")
                print(f"         Analyzer supports method version 1.0")
                print(f"         Consider regenerating test pattern if analysis fails")
            
            self.base_frequency = encoding_params.get('base_frequency', 1000)
            self.sync_frequency = encoding_params.get('sync_frequency', 2000)
            self.sample_rate = encoding_params.get('audio_sample_rate', 48000)
            self.expected_fps = timecode_meta.get('fps', 25.0)
            
            
            # Update corner colors from metadata if available
            corner_markers = metadata.get('corner_markers', {})
            self.red_lower = np.array(corner_markers.get('primary_color_bgr', [0, 0, 100]), dtype="uint8")
            self.red_upper = np.array([min(255, c+50) for c in corner_markers.get('primary_color_bgr', [0, 0, 255])], dtype="uint8")
            self.blue_lower = np.array(corner_markers.get('secondary_color_bgr', [100, 0, 0]), dtype="uint8")
            self.blue_upper = np.array([min(255, c+50) for c in corner_markers.get('secondary_color_bgr', [255, 50, 50])], dtype="uint8")
            
            print(f"Loaded metadata: {self.expected_fps}fps, {self.sample_rate}Hz audio and custom corner colors")
            print(f"Method version: {method_version}")
            
        except Exception as e:
            print(f"Warning: Could not load metadata: {e}")
    
    def analyze_alignment(self):
        """
        Perform complete analysis of audio/video alignment
        
        Returns:
            dict: Analysis results with timing offsets and statistics
        """
        print("Starting VHS timecode analysis...")
        
        # Step 1: Detect timecode windows using shared pattern detection
        print("Detecting timecode pattern window...")
        robust_decoder = SharedTimecodeRobust(format_type="PAL" if abs(self.expected_fps - 25.0) < abs(self.expected_fps - 29.97) else "NTSC")
        
        # Detect video timecode window
        video_pattern_result = robust_decoder.detect_timecode_window_video(self.video_file, strict=False)  # VHS mode
        
        if not video_pattern_result['success']:
            return {
                'success': False,
                'error': f"Video pattern detection failed: {video_pattern_result.get('error', 'Unknown error')}",
                'pattern_result': video_pattern_result
            }
        
        # Detect audio timecode window
        audio_pattern_result = robust_decoder.detect_timecode_window_audio(self.audio_file, strict=False)  # VHS mode
        
        if not audio_pattern_result['success']:
            return {
                'success': False,
                'error': f"Audio pattern detection failed: {audio_pattern_result.get('error', 'Unknown error')}",
                'pattern_result': audio_pattern_result
            }
        
        self.video_timecode_window = video_pattern_result
        self.audio_timecode_window = audio_pattern_result
        print(f"  Found video timecode window: frames {video_pattern_result['timecode_start_frame']}-{video_pattern_result['timecode_end_frame']}")
        print(f"  Found audio timecode window: samples {audio_pattern_result['timecode_start_sample']}-{audio_pattern_result['timecode_end_sample']}")
        
        # Step 2: Analyze video timecode (limited to detected window)
        print("Analyzing video timecode...")
        self._analyze_video_timecode()
        
        # Step 3: Analyze audio timecode (limited to corresponding time window)
        print("Analyzing audio timecode...")
        self._analyze_audio_timecode()
        
        # Step 4: Correlate audio and video timecodes
        print("Correlating audio and video timecodes...")
        results = self._correlate_timecodes()

        # Calculate and print absolute delay recommendation if successful
        if results.get('success') and 'average_offset_seconds' in results:
            offset = results['average_offset_seconds']
            current_delay = 0.0  # Assume 0 if not set; could be retrieved from config
            recommended_total_delay = current_delay - offset
            print("\nTIMING ANALYSIS RESULTS:")
            if offset > 0:
                print(f"  Audio starts {offset:.3f}s AFTER video")
                print(f"  Recommendation: Set audio delay to {recommended_total_delay:.3f}s")
            elif offset < 0:
                print(f"  Audio starts {abs(offset):.3f}s BEFORE video")
                print(f"  Recommendation: Set audio delay to {recommended_total_delay:.3f}s")
            else:
                print(f"  Perfect synchronization detected!")
                print(f"  Recommendation: Set audio delay to {recommended_total_delay:.3f}s")
        
        # Add pattern detection info to results
        if 'analysis_summary' not in results:
            results['analysis_summary'] = {}
        results['analysis_summary']['video_pattern_detection'] = video_pattern_result['pattern_info']
        results['analysis_summary']['audio_pattern_detection'] = audio_pattern_result['pattern_info']
        
        return results

    def _analyze_video_timecode(self):
        """Analyze video stream to extract timecode information (limited to detected window)"""
        import time
        start_time = time.time()
        
        cap = cv2.VideoCapture(self.video_file)
        
        if not cap.isOpened():
            raise RuntimeError(f"Could not open video file: {self.video_file}")
        
        # Get total frame count for progress tracking
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        
        # Get timecode window bounds
        timecode_start = self.video_timecode_window['timecode_start_frame']
        timecode_end = self.video_timecode_window['timecode_end_frame']
        
        print(f"  Video contains {total_frames} total frames")
        print(f"  Analyzing timecode window: frames {timecode_start}-{timecode_end}")
        sys.stdout.flush()  # Ensure output is visible immediately
        
        try:
            frame_count = 0
            detected_frames = 0
            last_progress_time = start_time
            
            # Store test pattern transitions for A/V sync calculation if VHS calibration mode
            self.video_pattern_transitions = [] if self.vhs_calibration else None
            
            while True:
                ret, frame = cap.read()
                if not ret:
                    break
                
                current_time = time.time()
                
                # Progress reporting and timeout protection
                if frame_count % 25 == 0 or (current_time - last_progress_time) > 5.0:
                    elapsed = current_time - start_time
                    progress = (frame_count / total_frames) * 100 if total_frames > 0 else 0
                    fps_rate = frame_count / elapsed if elapsed > 0 else 0
                    print(f"  Processing frame {frame_count}/{total_frames} ({progress:.1f}%) - {fps_rate:.1f} fps")
                    sys.stdout.flush()  # Ensure progress is visible
                    last_progress_time = current_time
                    
                    # Timeout protection - if processing is too slow, something is wrong
                    if elapsed > 300:  # 5 minutes timeout
                        print(f"  ERROR: Video processing timeout after {elapsed:.1f}s")
                        print(f"  Processed {frame_count} frames at {fps_rate:.1f} fps")
                        sys.stdout.flush()
                        break
                
                # For VHS calibration, also detect test pattern transitions
                if self.vhs_calibration:
                    try:
                        pattern_detected = self._detect_test_pattern(frame)
                        if pattern_detected:
                            frame_time = frame_count / self.expected_fps
                            self.video_pattern_transitions.append((frame_count, frame_time))
                    except Exception as e:
                        if frame_count < 10:  # Only show first few errors
                            print(f"  Warning: Test pattern detection failed on frame {frame_count}: {e}")
                            sys.stdout.flush()
                
                # Only process frames within the timecode window
                if timecode_start <= frame_count < timecode_end:
                    # Try to detect timecode in this frame
                    try:
                        frame_id, confidence = self._detect_frame_timecode(frame)
                        
                        if frame_id is not None:
                            self.video_timecodes.append((frame_count, frame_id, confidence))
                            detected_frames += 1
                    except Exception as e:
                        # Don't let individual frame errors stop processing
                        if frame_count < timecode_start + 10:  # Show errors for first few frames only
                            print(f"  Warning: Frame {frame_count} timecode detection failed: {e}")
                            sys.stdout.flush()
                
                frame_count += 1
                
                # Stop processing after timecode window
                if frame_count >= timecode_end:
                    break
                
                # Safety limit - don't process unreasonably long videos
                if frame_count > 50000:  # ~33 minutes at 25fps
                    print(f"  Warning: Video too long ({frame_count} frames), stopping analysis")
                    sys.stdout.flush()
                    break
            
            elapsed_total = time.time() - start_time
            avg_fps = frame_count / elapsed_total if elapsed_total > 0 else 0
            print(f"  Completed video analysis in {elapsed_total:.1f}s (avg {avg_fps:.1f} fps)")
            print(f"  Detected timecode in {detected_frames}/{frame_count} video frames")
            
            # Note: video_pattern_transitions is just for internal VHS calibration use
            # Don't print confusing "transitions" count as it's not the pattern state transitions
            
            sys.stdout.flush()
                
        finally:
            cap.release()

    def _detect_frame_timecode(self, frame):
        """Extract timecode from a single video frame"""
        try:
            # Method 1: Try to read the binary strip at the top
            frame_id = self._read_binary_strip(frame)
            if frame_id is not None:
                return frame_id, 0.9  # High confidence for binary method
            
            # Method 2: Try OCR on the main timecode display
            frame_id = self._read_visual_timecode(frame)
            if frame_id is not None:
                return frame_id, 0.7  # Medium confidence for OCR
            
            # Method 3: Try to detect corner patterns
            frame_id = self._read_corner_patterns(frame)
            if frame_id is not None:
                return frame_id, 0.5  # Lower confidence for pattern matching
            
        except Exception as e:
            # Don't let individual frame errors stop the analysis
            pass
        
        return None, 0.0

    def _detect_corner_markers(self, frame):
        """Detect colored corner markers and return their positions"""
        height, width = frame.shape[:2]

        # Detect the red corners (top-left, bottom-right)
        red_mask = cv2.inRange(frame, self.red_lower, self.red_upper)

        # Detect the blue corners (top-right, bottom-left)
        blue_mask = cv2.inRange(frame, self.blue_lower, self.blue_upper)

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

    def _read_corner_patterns(self, frame):
        """Use corner markers to improve frame alignment and binary strip reading"""
        corner_info = self._detect_corner_markers(frame)
        
        if not corner_info['detected']:
            return None
            
        # Use corner detection to improve binary strip reading
        corrected_frame_id = self._read_binary_strip_with_corners(frame, corner_info)
        
        return corrected_frame_id

    def _read_binary_strip_with_corners(self, frame, corner_info):
        """Read binary strip using corner markers for precise alignment"""
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
                        if bit_pattern == 'inverted':
                            print(f"  DEBUG: Using inverted bits for frame {frame_number}")
                        return frame_number
                except ValueError:
                    continue
        
        return None

    def _read_binary_strip(self, frame):
        """Read binary timecode from top strip of frame using shared utility"""
        robust_decoder = SharedTimecodeRobust(format_type="PAL" if abs(self.expected_fps - 25.0) < abs(self.expected_fps - 29.97) else "NTSC")
        return robust_decoder.read_binary_strip(frame)

    def _read_visual_timecode(self, frame):
        """Read timecode using OCR on the main display"""
        try:
            # This would require pytesseract for OCR
            # For now, return None - can be implemented if needed
            return None
        except:
            return None

    def _analyze_audio_timecode(self):
        """Analyze audio stream to extract timecode and sync pulses"""
        # Load audio using subprocess (sox or ffmpeg)
        audio_data = self._load_audio_data()
        
        if audio_data is None:
            print("  Warning: Could not load audio data")
            return
        
        # Current system uses mono FSK timecode - no sync pulses needed
        # FSK timecode provides frame-level synchronization information
        mono_channel = audio_data[:, 0] if audio_data.ndim > 1 else audio_data
        print(f"  Decoding FSK timecode from mono channel...")
        self._decode_fsk_timecode(mono_channel)
        
        print(f"  Decoded {len(self.audio_timecodes)} audio timecodes")

    def _load_audio_data(self):
        """Load audio data using shared utility"""
        robust_decoder = SharedTimecodeRobust(format_type="PAL" if abs(self.expected_fps - 25.0) < abs(self.expected_fps - 29.97) else "NTSC")
        return robust_decoder.load_audio_data(self.audio_file)

    def _decode_fsk_timecode(self, audio_channel):
        """Decode FSK-encoded timecode from audio channel using ROBUST system (limited to detected window)"""
        # Limit audio analysis to detected timecode window
        timecode_start = self.audio_timecode_window['timecode_start_sample']
        timecode_end = self.audio_timecode_window['timecode_end_sample']
        
        print(f"  Limiting audio analysis to samples {timecode_start}-{timecode_end}")
        
        # Extract only the timecode portion of the audio
        if timecode_end <= len(audio_channel):
            timecode_audio = audio_channel[timecode_start:timecode_end]
        else:
            print(f"  Warning: Timecode window extends beyond audio length ({len(audio_channel)} samples)")
            timecode_audio = audio_channel[timecode_start:]
        
        print(f"  Audio timecode window contains {len(timecode_audio)} samples ({len(timecode_audio)/self.sample_rate:.1f}s)")
        
        # Initialize the robust FSK decoder with appropriate format
        # Try to determine format from metadata or use default
        format_type = "PAL"  # Default
        if hasattr(self, 'expected_fps'):
            format_type = "PAL" if abs(self.expected_fps - 25.0) < abs(self.expected_fps - 29.97) else "NTSC"
        
        print(f"  Using robust FSK decoder with {format_type} format")
        robust_decoder = SharedTimecodeRobust(format_type=format_type)
        
        # Use the robust decoding system (VHS mode - tolerant sliding window)
        print("  Applying robust multi-method FSK decoding...")
        decoded_frames = robust_decoder.decode_fsk_audio(timecode_audio, strict=False)
        
        print(f"  Robust decoder found {len(decoded_frames)} potential frames")
        
        # Convert results to our format, adjusting sample positions to original audio offset
        for sample_position, frame_id, confidence in decoded_frames:
            # Adjust sample position to account for the window offset
            adjusted_sample_position = sample_position + timecode_start
            self.audio_timecodes.append((adjusted_sample_position, frame_id, confidence))
        
        # Additional quality filtering
        if len(self.audio_timecodes) > 0:
            # Sort by confidence and keep the best results
            self.audio_timecodes.sort(key=lambda x: x[2], reverse=True)
            
            # Report quality statistics
            confidences = [conf for _, _, conf in self.audio_timecodes]
            avg_confidence = np.mean(confidences)
            high_conf_count = sum(1 for conf in confidences if conf > 0.8)
            
            print(f"  Quality stats: avg confidence {avg_confidence:.2f}, {high_conf_count} high-confidence frames")

    def _decode_fsk_segment(self, audio_segment, samples_per_bit):
        """Decode a single FSK segment to extract frame ID"""
        bits = []
        
        # Analyze each bit period
        for bit_index in range(32):  # 32 bits total
            start_bit = bit_index * samples_per_bit
            end_bit = min(start_bit + samples_per_bit, len(audio_segment))
            
            if end_bit <= start_bit:
                break
            
            bit_audio = audio_segment[start_bit:end_bit]
            
            # Analyze frequency content using simple method
            bit_value = self._analyze_bit_frequency(bit_audio)
            
            if bit_value is not None:
                bits.append(bit_value)
            else:
                # If we can't decode a bit, abandon this segment
                return None
        
        if len(bits) == 32:
            # Extract frame number (first 24 bits) and checksum (last 8 bits)
            frame_bits = bits[:24]
            checksum_bits = bits[24:]
            
            # Convert to integers
            frame_number = int(''.join(frame_bits), 2)
            received_checksum = int(''.join(checksum_bits), 2)
            
            # Verify checksum
            calculated_checksum = 0
            for bit in frame_bits:
                calculated_checksum ^= int(bit)
            
            if calculated_checksum == received_checksum:
                return frame_number
        
        return None

    def _analyze_bit_frequency(self, bit_audio):
        """Analyze audio segment to determine if it represents '0' or '1'"""
        if len(bit_audio) < 10:  # Need minimum samples
            return None

        # Apply window function to reduce spectral leakage
        windowed_audio = bit_audio * np.hanning(len(bit_audio))
        
        # Perform FFT to analyze the frequency content
        fft_result = np.fft.fft(windowed_audio)
        freqs = np.fft.fftfreq(len(bit_audio), d=1/self.sample_rate)
        
        # Only look at positive frequencies
        positive_freqs = freqs[:len(freqs)//2]
        positive_fft = np.abs(fft_result[:len(fft_result)//2])
        
        # Expected frequencies for ROBUST FSK
        freq_0 = self.base_frequency  # 800Hz for '0'
        freq_1 = self.base_frequency * 2  # 1600Hz for '1' (double frequency)
        
        # Find peaks in expected frequency ranges (with guard bands)
        freq_0_range = (freq_0 - 150, freq_0 + 150)  # 650-950Hz
        freq_1_range = (freq_1 - 250, freq_1 + 250)  # 1350-1850Hz
        
        # Get amplitude in each frequency range
        mask_0 = (positive_freqs >= freq_0_range[0]) & (positive_freqs <= freq_0_range[1])
        mask_1 = (positive_freqs >= freq_1_range[0]) & (positive_freqs <= freq_1_range[1])
        
        amp_0 = np.max(positive_fft[mask_0]) if np.any(mask_0) else 0
        amp_1 = np.max(positive_fft[mask_1]) if np.any(mask_1) else 0
        
        # Find overall peak frequency for debugging
        peak_idx = np.argmax(positive_fft)
        peak_freq = positive_freqs[peak_idx]
        
        # Debug output for frequency analysis
        if hasattr(self, '_debug_bit_count'):
            self._debug_bit_count += 1
        else:
            self._debug_bit_count = 1

        if self._debug_bit_count <= 64:  # Only show first 64 bits
            print(f"    Bit {self._debug_bit_count}: peak_freq={peak_freq:.1f}Hz, amp_0={amp_0:.2f}, amp_1={amp_1:.2f}")
        
        # Classify based on which frequency range has higher amplitude
        if amp_0 > amp_1 and amp_0 > 0.1:  # Minimum amplitude threshold
            return '0'
        elif amp_1 > amp_0 and amp_1 > 0.1:
            return '1'
        
        return None  # Unclear or no signal

    def _learn_frequencies(self, audio_channel, samples_per_bit):
        """Learn the actual FSK frequencies from the audio signal"""
        # Take several samples from different parts of the audio
        sample_locations = [0, len(audio_channel)//4, len(audio_channel)//2, 3*len(audio_channel)//4]
        all_frequencies = []
        
        for start_pos in sample_locations:
            if start_pos + samples_per_bit * 32 > len(audio_channel):
                continue
                
            # Analyze 32 consecutive bits to get a good sample
            for bit_idx in range(32):
                bit_start = start_pos + bit_idx * samples_per_bit
                bit_end = bit_start + samples_per_bit
                
                if bit_end > len(audio_channel):
                    break
                    
                bit_audio = audio_channel[bit_start:bit_end]
                
                if len(bit_audio) < 10:
                    continue
                    
                # Apply window and FFT
                windowed_audio = bit_audio * np.hanning(len(bit_audio))
                fft_result = np.fft.fft(windowed_audio)
                freqs = np.fft.fftfreq(len(bit_audio), d=1/self.sample_rate)
                
                # Find peak frequency
                positive_freqs = freqs[:len(freqs)//2]
                positive_fft = np.abs(fft_result[:len(fft_result)//2])
                
                if len(positive_fft) > 0:
                    peak_idx = np.argmax(positive_fft)
                    peak_freq = abs(positive_freqs[peak_idx])
                    
                    # Only consider reasonable frequencies
                    if 500 < peak_freq < 2000:
                        all_frequencies.append(peak_freq)
        
        if len(all_frequencies) < 10:
            return None, None
            
        # Cluster frequencies to find the two main FSK frequencies
        freq_array = np.array(all_frequencies)
        
        # Use simple clustering: find two peaks in histogram
        hist, bin_edges = np.histogram(freq_array, bins=50, range=(600, 1600))
        
        # Find the two highest peaks
        peak_indices = np.argsort(hist)[-2:]
        
        freq_0_bin = bin_edges[peak_indices[0]]
        freq_1_bin = bin_edges[peak_indices[1]]
        
        # Make sure freq_0 < freq_1
        if freq_0_bin > freq_1_bin:
            freq_0_bin, freq_1_bin = freq_1_bin, freq_0_bin
            
        return freq_0_bin, freq_1_bin

    def _detect_sync_pulses(self, audio_channel):
        """Detect sync pulses in right audio channel"""
        # Look for 2kHz pulses at expected frame boundaries
        expected_frame_duration = self.sample_rate / self.expected_fps
        pulse_duration = int(0.01 * self.sample_rate)  # 10ms pulses
        
        # Use energy-based detection
        for sample in range(0, len(audio_channel) - pulse_duration, int(expected_frame_duration // 4)):
            pulse_segment = audio_channel[sample:sample + pulse_duration]
            
            # Check if this looks like a sync pulse
            if self._is_sync_pulse(pulse_segment):
                confidence = 0.7  # Could be improved
                self.sync_pulses.append((sample, confidence))

    def _is_sync_pulse(self, audio_segment):
        """Determine if audio segment contains a sync pulse"""
        # Simple energy and frequency check
        energy = np.mean(audio_segment ** 2)
        
        # Count zero crossings to estimate frequency
        zero_crossings = 0
        for i in range(1, len(audio_segment)):
            if (audio_segment[i-1] >= 0) != (audio_segment[i] >= 0):
                zero_crossings += 1
        
        duration = len(audio_segment) / self.sample_rate
        estimated_freq = zero_crossings / (2 * duration)
        
        # Check if frequency is close to sync frequency (2kHz) and energy is sufficient
        freq_match = abs(estimated_freq - self.sync_frequency) < 200  # 200Hz tolerance
        energy_sufficient = energy > 0.01  # Minimum energy threshold
        
        return freq_match and energy_sufficient
    
    def _detect_test_pattern(self, frame):
        """
        Detect test patterns in VHS calibration mode
        
        Args:
            frame: Video frame to analyze
            
        Returns:
            bool: True if test pattern detected
        """
        # Simple test pattern detection - look for high contrast areas
        # This is a placeholder implementation for VHS calibration mode
        try:
            # Convert to grayscale
            if len(frame.shape) == 3:
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            else:
                gray = frame
            
            # Calculate image statistics
            mean_intensity = np.mean(gray)
            std_intensity = np.std(gray)
            
            # Test pattern detection heuristics:
            # 1. High contrast (standard deviation)
            # 2. Reasonable brightness range
            # 3. Not completely black or white
            
            has_contrast = std_intensity > 30  # Reasonable contrast
            reasonable_brightness = 20 < mean_intensity < 235  # Not too dark/bright
            
            # Simple edge detection to look for patterns
            edges = cv2.Canny(gray, 50, 150)
            edge_density = np.sum(edges > 0) / edges.size
            has_patterns = edge_density > 0.05  # At least 5% edges
            
            # Combine criteria
            is_test_pattern = has_contrast and reasonable_brightness and has_patterns
            
            return is_test_pattern
            
        except Exception as e:
            # Don't let test pattern detection errors stop the analysis
            return False

    def _correlate_timecodes(self):
        """Correlate video and audio timecodes to find alignment offset using shared correlation logic"""
        # Use the shared correlation method from the robust decoder
        robust_decoder = SharedTimecodeRobust(format_type="PAL" if abs(self.expected_fps - 25.0) < abs(self.expected_fps - 29.97) else "NTSC")
        
        # Use shared sequential correlation logic
        results = robust_decoder.correlate_timecodes(self.video_timecodes, self.audio_timecodes)
        
        # No sync pulse detection needed - FSK timecode provides frame-level sync
        
        return results


def main():
    parser = argparse.ArgumentParser(description='Analyze VHS timecode for precise A/V alignment')
    parser.add_argument('--video', required=True, help='Video file path')
    parser.add_argument('--audio', required=True, help='Audio file path')
    parser.add_argument('--metadata', help='Metadata file from timecode generation')
    parser.add_argument('--output', help='Output JSON file for results')
    parser.add_argument('--vhs-calibration', action='store_true', help='Enable VHS-specific enhancements for step 5.2')
    
    args = parser.parse_args()
    
    # Validate input files
    if not os.path.exists(args.video):
        print(f"Error: Video file not found: {args.video}")
        sys.exit(1)
    
    if not os.path.exists(args.audio):
        print(f"Error: Audio file not found: {args.audio}")
        sys.exit(1)
    
    # Check dependencies
    missing_deps = []
    try:
        import cv2
    except ImportError:
        missing_deps.append('opencv-python')
    
    try:
        subprocess.run(['sox', '--version'], capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        missing_deps.append('sox')
    
    if missing_deps:
        print("Missing dependencies:")
        for dep in missing_deps:
            print(f"  - {dep}")
        sys.exit(1)
    
    # Perform analysis
    analyzer = VHSTimecodeAnalyzer(args.video, args.audio, args.metadata, getattr(args, 'vhs_calibration', False))
    results = analyzer.analyze_alignment()
    
    # Display results
    print("\n" + "=" * 60)
    print("VHS TIMECODE ANALYSIS RESULTS")
    print("=" * 60)
    
    if results.get('success'):
        print(f"Analysis successful!")
        print(f"")
        print(f"TIMING OFFSET MEASUREMENT:")
        print(f"  Average offset: {results['average_offset_seconds']:+.6f} seconds")
        print(f"  Standard deviation: {results['offset_std_seconds']:.6f} seconds")
        print(f"  Offset range: {results['offset_range_seconds'][0]:+.6f} to {results['offset_range_seconds'][1]:+.6f} seconds")
        print(f"  Measurement precision: ±{results['offset_std_seconds']*1000:.1f} milliseconds")
        print(f"")
        print(f"ANALYSIS QUALITY:")
        print(f"  Total frame matches: {results['total_matches']}")
        print(f"  Average confidence: {results['average_confidence']:.1%}")
        print(f"  Video frames analyzed: {results['analysis_summary']['video_frames_analyzed']}")
        print(f"  Audio frames decoded: {results['analysis_summary']['audio_frames_decoded']}")
        
        # Interpret results
        offset = results['average_offset_seconds']
        if abs(offset) < 0.001:  # Within 1ms
            print(f"\nINTERPRETATION: EXCELLENT SYNC (within 1ms)")
        elif abs(offset) < 0.010:  # Within 10ms
            print(f"\nINTERPRETATION: GOOD SYNC (within 10ms)")
        elif abs(offset) < 0.050:  # Within 50ms
            print(f"\nINTERPRETATION: ACCEPTABLE SYNC (within 50ms)")
        else:
            print(f"\nINTERPRETATION: SYNC ADJUSTMENT NEEDED")
        
        # Calculate absolute delay recommendation
        # Current config delay (assume 0 if not known) + measured offset = total needed delay
        current_delay = 0.0  # TODO: Could read from config.json if available
        recommended_total_delay = current_delay - offset  # Negative offset means audio is early, so add delay
        
        if offset > 0:
            print(f"  Audio starts {offset:.3f}s AFTER video")
            print(f"  Recommendation: Set audio delay to {recommended_total_delay:.3f}s")
        elif offset < 0:
            print(f"  Audio starts {abs(offset):.3f}s BEFORE video")
            print(f"  Recommendation: Set audio delay to {recommended_total_delay:.3f}s")
        else:
            print(f"  Perfect synchronization detected!")
            print(f"  Recommendation: Set audio delay to {recommended_total_delay:.3f}s")
            
    else:
        print(f"Analysis failed: {results.get('error', 'Unknown error')}")
        if 'video_ids' in results and 'audio_ids' in results:
            print(f"  Sample video IDs: {results['video_ids']}")
            print(f"  Sample audio IDs: {results['audio_ids']}")
        if 'debug_info' in results:
            debug = results['debug_info']
            print(f"  Debug info:")
            print(f"    Unique video IDs: {debug['unique_video_ids']}")
            print(f"    Unique audio IDs: {debug['unique_audio_ids']}")
            print(f"    Common frame IDs: {debug['common_frame_ids']}")
            print(f"    Video ID range: {debug['video_id_range']}")
            print(f"    Audio ID range: {debug['audio_id_range']}")
            if debug['sample_common_ids']:
                print(f"    Sample common IDs: {debug['sample_common_ids']}")
    
    # Save results to file if requested
    if args.output:
        with open(args.output, 'w') as f:
            json.dump(results, f, indent=2)
        print(f"\nDetailed results saved to: {args.output}")
    
    print("=" * 60)


if __name__ == "__main__":
    main()
