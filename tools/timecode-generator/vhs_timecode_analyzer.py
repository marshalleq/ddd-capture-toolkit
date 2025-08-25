#!/usr/bin/env python3
"""
VHS Timecode Analyzer for Precise Audio/Video Alignment

This script analyzes captured VHS timecode test patterns to determine
precise audio/video synchronization offsets with microsecond accuracy.

It processes both the visual timecode and audio FSK encoding to correlate
video frames with audio samples, providing detailed alignment measurements.

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
import tempfile
from datetime import datetime
import re
from shared_timecode_robust import SharedTimecodeRobust

class VHSTimecodeAnalyzer(SharedTimecodeRobust):
    def __init__(self, video_file, audio_file, metadata_file=None, format_type="PAL", width=720, height=576):
        """
        Initialize VHS timecode analyzer
        
        Args:
            video_file: Path to captured video file
            audio_file: Path to captured audio file
            metadata_file: Optional metadata from timecode generation
            format_type: "PAL" or "NTSC" for format detection
        """
        # Initialize parent class first
        super().__init__(format_type, width, height)
        
        self.video_file = video_file
        self.audio_file = audio_file
        self.metadata_file = metadata_file
        
        # Results storage
        self.video_timecodes = []  # List of (frame_number, detected_frame_id, confidence)
        self.audio_timecodes = []  # List of (sample_offset, decoded_frame_id, confidence)
        self.sync_pulses = []      # List of (sample_offset, confidence)
        
        # Load metadata if available - this may update parent class settings
        if metadata_file and os.path.exists(metadata_file):
            self._load_metadata(metadata_file)
    
    def _load_metadata(self, metadata_file):
        """Load metadata from timecode generation"""
        try:
            with open(metadata_file, 'r') as f:
                metadata = json.load(f)
            
            encoding_params = metadata.get('encoding_parameters', {})
            timecode_meta = metadata.get('timecode_metadata', {})
            
            # Update parent class parameters from metadata
            if 'audio_sample_rate' in encoding_params:
                self.sample_rate = encoding_params['audio_sample_rate']
            if 'fps' in timecode_meta:
                self.fps = timecode_meta['fps']
            
            print(f"Loaded metadata: {self.fps}fps, {self.sample_rate}Hz audio")
            
        except Exception as e:
            print(f"Warning: Could not load metadata: {e}")
    
    def analyze_alignment(self):
        """
        Perform complete analysis of audio/video alignment
        
        Returns:
            dict: Analysis results with timing offsets and statistics
        """
        print("Starting VHS timecode analysis...")
        
        # Step 1: Analyze video timecode
        print("Analyzing video timecode...")
        self._analyze_video_timecode()
        
        # Step 2: Analyze audio timecode
        print("Analyzing audio timecode...")
        self._analyze_audio_timecode()
        
        # Step 3: Correlate audio and video timecodes
        print("Correlating audio and video timecodes...")
        results = self._correlate_timecodes()
        return results

    def _analyze_video_timecode(self):
        """Analyze video stream to extract timecode information"""
        cap = cv2.VideoCapture(self.video_file)
        
        if not cap.isOpened():
            raise RuntimeError(f"Could not open video file: {self.video_file}")
        
        try:
            frame_count = 0
            detected_frames = 0
            
            while True:
                ret, frame = cap.read()
                if not ret:
                    break
                
                if frame_count % 25 == 0:  # Progress every second
                    print(f"  Processing video frame {frame_count}...")
                
                # Preprocess frame for VHS conditions
                processed_frame = self._preprocess_vhs_frame(frame)
                
                # Try to detect timecode in this frame
                frame_id, confidence = self._detect_frame_timecode(processed_frame)
                
                if frame_id is not None:
                    self.video_timecodes.append((frame_count, frame_id, confidence))
                    detected_frames += 1
                    print(f"    Found frame ID {frame_id} at frame {frame_count} (confidence: {confidence:.2f})")
                
                frame_count += 1
            
            print(f"  Detected timecode in {detected_frames}/{frame_count} video frames")
        finally:
            cap.release()
    
    def _preprocess_vhs_frame(self, frame):
        """Preprocess VHS frame to improve timecode detection"""
        # Deinterlace if needed (VHS is typically interlaced)
        height, width = frame.shape[:2]
        
        # Basic deinterlacing - combine odd and even lines
        if height % 2 == 0:
            # Average odd and even lines to reduce interlacing artifacts
            even_lines = frame[::2, :]
            odd_lines = frame[1::2, :]
            if even_lines.shape[0] == odd_lines.shape[0]:
                deinterlaced = (even_lines.astype(np.float32) + odd_lines.astype(np.float32)) / 2
                frame = deinterlaced.astype(np.uint8)
        
        # Resize to expected timecode dimensions if needed
        target_width = 720
        target_height = 576
        
        if width != target_width or height != target_height:
            frame = cv2.resize(frame, (target_width, target_height), interpolation=cv2.INTER_CUBIC)
        
        return frame

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

    def _read_binary_strip(self, frame):
        """Read binary timecode from top strip of frame"""
        height, width = frame.shape[:2]
        
        # Extract the top 20 pixels
        strip = frame[0:20, :]
        
        # Convert to grayscale
        if len(strip.shape) == 3:
            strip_gray = cv2.cvtColor(strip, cv2.COLOR_BGR2GRAY)
        else:
            strip_gray = strip
        
        # Apply adaptive thresholding for degraded VHS signals
        # First get overall statistics
        strip_mean = np.mean(strip_gray)
        strip_std = np.std(strip_gray)
        
        # Skip frames with very low variance (likely no signal)
        if strip_std < 5.0:  # Very low variance indicates no pattern
            return None
        
        # Handle different aspect ratios - map to expected 720px wide pattern
        # The timecode pattern was designed for 720px, so we need to map our 
        # actual width to that expected pattern
        expected_width = 720
        width_scale = width / expected_width
        
        # Read 32 bits with proper scaling
        bits = []
        block_intensities = []
        
        # Calculate block positions based on the original 720px design
        expected_block_width = expected_width // 32  # 22.5px per block at 720px
        actual_block_width = width / 32  # Actual block width in our resolution
        
        for i in range(32):
            # Calculate block boundaries
            x_start = int(i * actual_block_width)
            x_end = int((i + 1) * actual_block_width)
            x_end = min(x_end, width)  # Ensure we don't exceed image bounds
            
            if x_end > x_start:
                # Sample the middle portion of this block to avoid edge artifacts
                block_center_start = x_start + (x_end - x_start) // 4
                block_center_end = x_end - (x_end - x_start) // 4
                block_center_end = max(block_center_end, block_center_start + 1)
                
                block = strip_gray[:, block_center_start:block_center_end]
                if block.size > 0:
                    avg_intensity = np.mean(block)
                    block_intensities.append(avg_intensity)
                else:
                    block_intensities.append(strip_mean)  # Fallback
        
        if len(block_intensities) < 32:
            return None
            
        # Use adaptive threshold based on the distribution of intensities
        # in THIS frame rather than a fixed threshold
        block_mean = np.mean(block_intensities)
        block_std = np.std(block_intensities)
        
        # Skip if there's insufficient variation between blocks
        if block_std < 3.0:  # Not enough variation for binary pattern
            return None
            
        # Debug output for troubleshooting
        if len(self.video_timecodes) == 0:  # Only print for first potential detection
            print(f"    Binary strip analysis: width={width}, blocks_std={block_std:.1f}")
            print(f"    Sample intensities: {[f'{x:.1f}' for x in block_intensities[:8]]}...")
            
        # Use adaptive threshold with some hysteresis to handle VHS noise
        threshold = block_mean
        
        # Apply hysteresis - if a block is very close to threshold, 
        # check neighboring blocks for consistency
        for i, intensity in enumerate(block_intensities):
            if abs(intensity - threshold) < block_std * 0.2:  # Close to threshold
                # Look at neighbors for context
                neighbors = []
                if i > 0:
                    neighbors.append(block_intensities[i-1])
                if i < len(block_intensities) - 1:
                    neighbors.append(block_intensities[i+1])
                
                if neighbors:
                    neighbor_avg = np.mean(neighbors)
                    # Use neighbor context to resolve ambiguous blocks
                    bit = '1' if neighbor_avg > threshold else '0'
                else:
                    bit = '1' if intensity > threshold else '0'
            else:
                bit = '1' if intensity > threshold else '0'
            bits.append(bit)
        
        if len(bits) == 32:
            # Convert binary to frame number
            binary_str = ''.join(bits)
            
            if len(self.video_timecodes) == 0:  # Debug output for first detection attempt
                print(f"    Binary string: {binary_str[:16]}...{binary_str[16:]}")
            
            try:
                frame_number = int(binary_str, 2)
                # Basic sanity check - reasonable range for frame numbers
                if 0 <= frame_number <= 285000:  # Expected range from metadata
                    return frame_number
                elif len(self.video_timecodes) == 0:
                    print(f"    Frame number {frame_number} out of expected range (0-285000)")
                    
                # Try inverted binary (VHS capture might invert the signal)
                inverted_bits = ['0' if b == '1' else '1' for b in bits]
                inverted_binary_str = ''.join(inverted_bits)
                inverted_frame_number = int(inverted_binary_str, 2)
                
                print(f"    Trying inverted: {inverted_binary_str[:16]}...{inverted_binary_str[16:]}")
                print(f"    Inverted frame number: {inverted_frame_number}")
                
                if 0 <= inverted_frame_number <= 285000:
                    print(f"    Using inverted frame number: {inverted_frame_number}")
                    return inverted_frame_number
                    
            except ValueError:
                pass
        
        return None

    def _read_visual_timecode(self, frame):
        """Read timecode using OCR on the main display"""
        try:
            # This would require pytesseract for OCR
            # For now, return None - can be implemented if needed
            return None
        except:
            return None

    def _read_corner_patterns(self, frame):
        """Read timecode from corner intensity patterns"""
        height, width = frame.shape[:2]
        marker_size = 40
        
        try:
            # Check if frame dimensions are large enough
            if height < marker_size or width < marker_size:
                return None
            
            # Extract corner regions
            top_right = frame[0:marker_size, width-marker_size:width]
            bottom_left = frame[height-marker_size:height, 0:marker_size]
            
            # Convert to grayscale and get average intensity
            if len(top_right.shape) == 3:
                tr_gray = cv2.cvtColor(top_right, cv2.COLOR_BGR2GRAY)
                bl_gray = cv2.cvtColor(bottom_left, cv2.COLOR_BGR2GRAY)
            else:
                tr_gray = top_right
                bl_gray = bottom_left
            
            tr_intensity = np.mean(tr_gray)
            bl_intensity = np.mean(bl_gray)
            
            # Decode pattern (frame_number % 4) * 64
            tr_pattern = round(tr_intensity / 64)
            bl_pattern = round(bl_intensity / 64)
            
            # Both corners should have the same pattern
            if tr_pattern == bl_pattern and 0 <= tr_pattern <= 3:
                # This gives us frame_number % 4, not the full frame number
                # Useful for validation but not for absolute frame ID
                return None  # Would need additional context
        
        except:
            pass
        
        return None
    def _analyze_audio_timecode(self):
        """Analyze audio stream to extract FSK timecode using the shared robust decoder"""
        try:
            # Use FFmpeg to convert audio to a temporary WAV file for analysis
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_wav:
                temp_wav_path = temp_wav.name

            command = [
                'ffmpeg', '-y', '-v', 'quiet',
                '-i', self.audio_file,
                '-ar', str(self.sample_rate),
                '-ac', '1',  # Convert to mono for analysis
                temp_wav_path
            ]
            subprocess.run(command, check=True)
            
            # Load the mono audio data
            import scipy.io.wavfile as wavfile
            sample_rate, audio_data = wavfile.read(temp_wav_path)
            
            if sample_rate != self.sample_rate:
                raise ValueError(f"Audio sample rate mismatch: expected {self.sample_rate}, got {sample_rate}")

            # Use the robust FSK decoder from the shared module (in tolerant VHS mode)
            print("  Decoding FSK timecode using robust tolerant decoder...")
            self.audio_timecodes = self.decode_fsk_audio(audio_data, strict=False)
            
            print(f"  Decoded {len(self.audio_timecodes)} audio timecodes")

        except Exception as e:
            print(f"  Error analyzing audio: {e}")
            import traceback
            traceback.print_exc()
        finally:
            if 'temp_wav_path' in locals() and os.path.exists(temp_wav_path):
                os.remove(temp_wav_path)
        print(f"  Detected {len(self.sync_pulses)} sync pulses")

    def _load_audio_data(self):
        """Load audio data using sox or similar tool"""
        try:
            # Try using sox to convert to raw format
            cmd = [
                'sox', self.audio_file, '-t', 'f32', '-r', str(self.sample_rate), '-'
            ]
            
            result = subprocess.run(cmd, capture_output=True, check=True)
            
            # Parse raw audio data
            audio_raw = np.frombuffer(result.stdout, dtype=np.float32)
            
            # Determine if stereo or mono
            # Try to detect channel count by analyzing the length
            # This is a heuristic - ideally we'd get this info from the file
            if len(audio_raw) % 2 == 0:
                # Assume stereo
                audio_data = audio_raw.reshape(-1, 2)
            else:
                # Assume mono
                audio_data = audio_raw.reshape(-1, 1)
            
            return audio_data
            
        except subprocess.CalledProcessError as e:
            print(f"  Sox error: {e}")
        except Exception as e:
            print(f"  Audio loading error: {e}")
        
        return None

    def _decode_fsk_timecode(self, audio_channel):
        """Decode FSK-encoded timecode from audio channel"""
        # Parameters for FSK decoding
        freq_0 = self.base_frequency      # 1000Hz for '0'
        freq_1 = self.base_frequency + 200  # 1200Hz for '1'
        
        # Expected bit duration in samples
        expected_frame_duration = self.sample_rate / self.expected_fps
        bits_per_frame = 32  # 24-bit frame + 8-bit checksum
        samples_per_bit = int(expected_frame_duration / bits_per_frame)
        
        # Use sliding window to find potential FSK sequences
        frame_samples = int(expected_frame_duration)
        
        for start_sample in range(0, len(audio_channel) - frame_samples, frame_samples // 4):
            end_sample = start_sample + frame_samples
            frame_audio = audio_channel[start_sample:end_sample]
            
            # Try to decode this segment as FSK
            frame_id = self._decode_fsk_segment(frame_audio, samples_per_bit)
            
            if frame_id is not None:
                confidence = 0.8  # Could be improved with signal quality analysis
                self.audio_timecodes.append((start_sample, frame_id, confidence))

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
        
        # Simple frequency analysis using zero crossings and energy
        # More sophisticated approach would use FFT
        
        # Count zero crossings
        zero_crossings = 0
        for i in range(1, len(bit_audio)):
            if (bit_audio[i-1] >= 0) != (bit_audio[i] >= 0):
                zero_crossings += 1
        
        # Estimate frequency from zero crossings
        duration = len(bit_audio) / self.sample_rate
        estimated_freq = zero_crossings / (2 * duration)
        
        # Classify as 0 or 1 based on frequency
        freq_0 = self.base_frequency
        freq_1 = self.base_frequency + 200
        
        diff_0 = abs(estimated_freq - freq_0)
        diff_1 = abs(estimated_freq - freq_1)
        
        # Choose the closer frequency, but only if reasonably close
        if diff_0 < diff_1 and diff_0 < 100:  # Within 100Hz tolerance
            return '0'
        elif diff_1 < diff_0 and diff_1 < 100:
            return '1'
        
        return None  # Unclear or no signal

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

    def _correlate_timecodes(self):
        """Correlate video and audio timecodes to find alignment offset"""
        if not self.video_timecodes or not self.audio_timecodes:
            return {
                'error': 'Insufficient timecode data for correlation',
                'video_frames': len(self.video_timecodes),
                'audio_frames': len(self.audio_timecodes)
            }
        
        # Find matching frame IDs between video and audio
        matches = []
        
        for video_frame, video_id, video_conf in self.video_timecodes:
            for audio_sample, audio_id, audio_conf in self.audio_timecodes:
                if video_id == audio_id:
                    # Calculate time offset
                    video_time = video_frame / self.fps
                    audio_time = audio_sample / self.sample_rate
                    
                    offset = audio_time - video_time
                    combined_confidence = min(video_conf, audio_conf)
                    
                    matches.append({
                        'frame_id': video_id,
                        'video_frame': video_frame,
                        'audio_sample': audio_sample,
                        'video_time': video_time,
                        'audio_time': audio_time,
                        'offset_seconds': offset,
                        'confidence': combined_confidence
                    })
        
        if not matches:
            return {
                'error': 'No matching frame IDs found between video and audio',
                'video_ids': [vid for _, vid, _ in self.video_timecodes[:10]],
                'audio_ids': [aid for _, aid, _ in self.audio_timecodes[:10]]
            }
        
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
                'video_frames_analyzed': len(self.video_timecodes),
                'audio_frames_decoded': len(self.audio_timecodes),
                'sync_pulses_detected': len(self.sync_pulses)
            }
        }
        
        return results


def main():
    parser = argparse.ArgumentParser(description='Analyze VHS timecode for precise A/V alignment')
    parser.add_argument('--video', required=True, help='Video file path')
    parser.add_argument('--audio', required=True, help='Audio file path')
    parser.add_argument('--metadata', help='Metadata file from timecode generation')
    parser.add_argument('--output', help='Output JSON file for results')
    
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
    analyzer = VHSTimecodeAnalyzer(args.video, args.audio, args.metadata)
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
        
        # Calculate absolute delay needed for config.json
        offset = results['average_offset_seconds']
        
        # The offset represents: audio_time - video_time
        # If positive: audio starts after video → would need video delay (not implemented)
        # If negative: audio starts before video → need audio delay = abs(offset)
        
        # Interpret results
        if abs(offset) < 0.001:  # Within 1ms
            print(f"\nINTERPRETATION: EXCELLENT SYNC (within 1ms)")
        elif abs(offset) < 0.010:  # Within 10ms
            print(f"\nINTERPRETATION: GOOD SYNC (within 10ms)")
        elif abs(offset) < 0.050:  # Within 50ms
            print(f"\nINTERPRETATION: ACCEPTABLE SYNC (within 50ms)")
        else:
            print(f"\nINTERPRETATION: SYNC ADJUSTMENT NEEDED")
        
        if offset > 0:
            print(f"  Audio starts {offset:.3f}s AFTER video")
            print(f"  WARNING: Would need video delay (not implemented)")
            print(f"  Required delay: Cannot fix - video delay not supported")
        elif offset < 0:
            print(f"  Audio starts {abs(offset):.3f}s BEFORE video")
            print(f"  Required delay: {abs(offset):.3f}s")
        else:
            print(f"  Perfect synchronization detected!")
            print(f"  Required delay: 0.000s")
            
    else:
        print(f"Analysis failed: {results.get('error', 'Unknown error')}")
        if 'video_ids' in results and 'audio_ids' in results:
            print(f"  Sample video IDs: {results['video_ids']}")
            print(f"  Sample audio IDs: {results['audio_ids']}")
    
    # Save results to file if requested
    if args.output:
        with open(args.output, 'w') as f:
            json.dump(results, f, indent=2)
        print(f"\nDetailed results saved to: {args.output}")
    
    print("=" * 60)


if __name__ == "__main__":
    main()
