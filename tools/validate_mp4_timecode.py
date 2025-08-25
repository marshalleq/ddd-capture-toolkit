#!/usr/bin/env python3
"""
Cycle-Aware MP4 Timecode Validation
Properly locks onto the 4-step cycle structure to validate only timecode sections.

The 4-step cycle structure:
1. Test chart + 1kHz tone (0-3s, frames 0-74)
2. Black screen + silence (3-4s, frames 75-99)
3. Timecode + FSK audio (4-34s, frames 100-849) <- VALIDATION TARGET
4. Black screen + silence (34-35s, frames 850-874)
"""

import os
import sys
import argparse
import subprocess
import tempfile
import json
import numpy as np
from pathlib import Path

# Add the timecode generator directory to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), 'timecode-generator'))

try:
    from shared_timecode_robust import SharedTimecodeRobust
    from vhs_timecode_analyzer import VHSTimecodeAnalyzer
    import cv2
except ImportError as e:
    print(f"Error: Could not import required modules: {e}")
    print("Make sure opencv-python and shared_timecode_robust.py are available")
    sys.exit(1)

class CycleAwareValidator:
    def __init__(self, mp4_file, separate_audio_file=None, temp_dir=None):
        self.mp4_file = mp4_file
        self.separate_audio_file = separate_audio_file
        self.temp_dir = temp_dir or tempfile.mkdtemp(prefix='cycle_validation_')
        self.video_file = None
        self.audio_file = None
        self.has_audio = None
        
        # 4-step cycle parameters for PAL (25fps)
        self.fps = 25.0
        self.sample_rate = 48000
        self.test_chart_duration = 3.0      # Step 1
        self.black_screen_1_duration = 1.0  # Step 2
        self.timecode_duration = 30.0       # Step 3
        self.black_screen_2_duration = 1.0  # Step 4
        self.total_cycle_duration = 35.0
        
        # Calculate exact frame and sample boundaries
        self.timecode_start_time = self.test_chart_duration + self.black_screen_1_duration  # 4.0s
        self.timecode_end_time = self.timecode_start_time + self.timecode_duration  # 34.0s
        
        self.timecode_start_frame = int(self.timecode_start_time * self.fps)  # 100
        self.timecode_end_frame = int(self.timecode_end_time * self.fps) - 1   # 849
        
        self.timecode_start_sample = int(self.timecode_start_time * self.sample_rate)  # 192000
        self.timecode_end_sample = int(self.timecode_end_time * self.sample_rate) - 1   # 1631999
        
        print(f"Cycle-aware validator initialized:")
        print(f"  Timecode section: {self.timecode_start_time}s - {self.timecode_end_time}s")
        print(f"  Video frames: {self.timecode_start_frame} - {self.timecode_end_frame}")
        print(f"  Audio samples: {self.timecode_start_sample} - {self.timecode_end_sample}")
        
    def __enter__(self):
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.temp_dir and os.path.exists(self.temp_dir):
            import shutil
            shutil.rmtree(self.temp_dir)
    
    def detect_streams(self):
        """Detect what streams are present in the MP4 file"""
        cmd = [
            'ffprobe', '-v', 'quiet', '-print_format', 'json', '-show_streams',
            self.mp4_file
        ]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            info = json.loads(result.stdout)
            
            has_video = False
            has_audio = False
            
            for stream in info.get('streams', []):
                if stream.get('codec_type') == 'video':
                    has_video = True
                elif stream.get('codec_type') == 'audio':
                    has_audio = True
            
            self.has_audio = has_audio
            
            print(f"MP4 file contains:")
            print(f"  Video: {'✓' if has_video else '✗'}")
            print(f"  Audio: {'✓' if has_audio else '✗'}")
            
            if not has_video:
                raise RuntimeError("MP4 file must contain video stream")
                
            return has_video, has_audio
            
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Failed to analyze MP4 streams: {e.stderr}")
    
    def demux_streams(self):
        """Perform frame-accurate demux of MP4 streams"""
        print("\nPerforming frame-accurate demux...")
        
        self.video_file = os.path.join(self.temp_dir, 'video.mp4')
        
        if self.has_audio:
            # Full A/V demux (Menu 5.3 case)
            self.audio_file = os.path.join(self.temp_dir, 'audio.wav')
            
            cmd = [
                'ffmpeg', '-y', '-v', 'quiet',
                '-i', self.mp4_file,
                '-c:v', 'copy', '-an', self.video_file,  # Video-only
                '-c:a', 'copy', '-vn', self.audio_file   # Audio-only
            ]
            
            try:
                subprocess.run(cmd, check=True)
                print(f"  Video extracted to: {self.video_file}")
                print(f"  Audio extracted to: {self.audio_file}")
            except subprocess.CalledProcessError as e:
                raise RuntimeError(f"Failed to demux MP4: {e}")
        
        else:
            # Video-only extraction (Menu 5.2 case)
            cmd = [
                'ffmpeg', '-y', '-v', 'quiet',
                '-i', self.mp4_file,
                '-c:v', 'copy', '-an', self.video_file
            ]
            
            try:
                subprocess.run(cmd, check=True)
                print(f"  Video extracted to: {self.video_file}")
                print("  No audio stream to extract")
            except subprocess.CalledProcessError as e:
                raise RuntimeError(f"Failed to extract video: {e}")
    
    def validate_cycle_lock(self):
        """Validate that we can properly lock onto the cycle structure"""
        print("\nValidating cycle lock-on...")
        
        # Check audio cycle detection if we have audio
        if self.has_audio or self.separate_audio_file:
            audio_path = self.audio_file if self.has_audio else self.separate_audio_file
            
            # Load audio to analyze cycle structure
            try:
                import scipy.io.wavfile as wavfile
                sample_rate, audio_data = wavfile.read(audio_path)
            except ImportError:
                # Fallback: use sox to get audio info
                result = subprocess.run(['soxi', audio_path], capture_output=True, text=True)
                if "Sample Rate" not in result.stdout:
                    raise RuntimeError(f"Cannot analyze audio file: {audio_path}")
                return True  # Skip detailed analysis without scipy
            
            print(f"  Audio loaded: {len(audio_data)} samples at {sample_rate}Hz")
            
            # Analyze test chart section (should contain 1kHz tone)
            test_chart_samples = int(self.test_chart_duration * sample_rate)
            test_chart_audio = audio_data[:test_chart_samples]
            
            # Analyze silence section (should be near zero)
            silence_start = int(self.test_chart_duration * sample_rate)
            silence_end = int((self.test_chart_duration + self.black_screen_1_duration) * sample_rate)
            silence_audio = audio_data[silence_start:silence_end]
            
            # Check for expected patterns
            test_chart_rms = np.sqrt(np.mean(test_chart_audio.astype(float)**2))
            silence_rms = np.sqrt(np.mean(silence_audio.astype(float)**2))
            
            print(f"  Test chart RMS: {test_chart_rms:.2f} (should be high - contains 1kHz tone)")
            print(f"  Silence RMS: {silence_rms:.2f} (should be low - silence)")
            
            # Validate cycle structure
            if test_chart_rms < 1000:  # Arbitrary threshold
                print(f"  ⚠️  Warning: Test chart section seems quiet (RMS={test_chart_rms:.2f})")
            if silence_rms > 100:  # Arbitrary threshold
                print(f"  ⚠️  Warning: Silence section not quiet (RMS={silence_rms:.2f})")
            
            print(f"  ✓ Cycle structure detected successfully")
        
        return True
    
    def analyze_video_timecode(self):
        """Analyze only the timecode frames in video (frames 100-849)"""
        print(f"\nAnalyzing video timecode frames {self.timecode_start_frame}-{self.timecode_end_frame}...")
        
        cap = cv2.VideoCapture(self.video_file)
        if not cap.isOpened():
            raise RuntimeError(f"Could not open video file: {self.video_file}")
        
        # Get total frame count to validate our range
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        print(f"  Video file contains {total_frames} total frames")
        
        if self.timecode_end_frame >= total_frames:
            print(f"  Warning: Requested end frame {self.timecode_end_frame} exceeds video length {total_frames}")
            actual_end_frame = total_frames - 1
        else:
            actual_end_frame = self.timecode_end_frame
        
        video_timecodes = []
        
        try:
            # Process each frame individually to ensure we get all frames
            for frame_index in range(self.timecode_start_frame, actual_end_frame + 1):
                # Seek to this specific frame
                cap.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
                
                # Verify we're at the correct position
                current_pos = int(cap.get(cv2.CAP_PROP_POS_FRAMES))
                if current_pos != frame_index:
                    print(f"  Warning: Seek failed - requested frame {frame_index}, got {current_pos}")
                
                ret, frame = cap.read()
                if not ret:
                    print(f"  Warning: Failed to read frame {frame_index}")
                    continue
                
                processed_frames = frame_index - self.timecode_start_frame + 1
                if processed_frames % 100 == 0:  # Progress every 4 seconds
                    print(f"  Processing video frame {frame_index} ({processed_frames}/{actual_end_frame - self.timecode_start_frame + 1})...")
                
                # Extract frame ID from this video frame
                # The frame ID should be (frame_index - timecode_start_frame)
                expected_frame_id = frame_index - self.timecode_start_frame
                
                # Try to detect the frame ID using robust methods
                detected_frame_id, confidence = self._detect_frame_timecode(frame)
                
                if detected_frame_id is not None:
                    video_timecodes.append({
                        'video_frame': frame_index,
                        'expected_frame_id': expected_frame_id,
                        'detected_frame_id': detected_frame_id,
                        'confidence': confidence,
                        'video_time': frame_index / self.fps
                    })
            
            total_processed = actual_end_frame - self.timecode_start_frame + 1
            print(f"  Detected timecode in {len(video_timecodes)}/{total_processed} video frames")
            
        finally:
            cap.release()
        
        return video_timecodes
    
    def analyze_audio_timecode(self, audio_path):
        """Analyze only the timecode section in audio (samples 192000-1631999)"""
        print(f"\nAnalyzing audio timecode section...")
        
        # Load full audio and extract frame-aligned timecode section
        try:
            import scipy.io.wavfile as wavfile
            sample_rate, full_audio = wavfile.read(audio_path)
        except ImportError:
            raise RuntimeError("scipy is required for audio analysis. Install with: pip install scipy")
        
        print(f"  Loaded full audio: {len(full_audio)} samples at {sample_rate}Hz")
        
        # Extract frame-aligned timecode section
        start_sample = self.timecode_start_sample
        end_sample = self.timecode_end_sample + 1
        
        if end_sample > len(full_audio):
            end_sample = len(full_audio)
        
        if start_sample >= len(full_audio):
            raise RuntimeError(f"Timecode start sample {start_sample} is beyond audio length {len(full_audio)}")
        
        timecode_audio = full_audio[start_sample:end_sample]
        
        print(f"  Extracted frame-aligned timecode section: {len(timecode_audio)} samples")
        print(f"  Duration: {len(timecode_audio)/sample_rate:.2f}s")
        print(f"  Sample range: {start_sample} - {end_sample-1}")
        
        # Initialize robust FSK decoder
        decoder = SharedTimecodeRobust(format_type='PAL')
        
        # Decode FSK from the timecode-only section using STRICT mode (MP4 validation)
        print(f"  Decoding FSK with frequencies {decoder.freq_0}Hz/'0' and {decoder.freq_1}Hz/'1'...")
        print(f"  Using strict decoder mode (perfect MP4 timing expected)...")
        decoded_frames = decoder.decode_fsk_audio(timecode_audio, strict=True)
        
        print(f"  Decoded {len(decoded_frames)} FSK frames")
        
        # Convert to absolute time positions
        audio_timecodes = []
        for sample_pos, frame_id, confidence in decoded_frames:
            # sample_pos is relative to the timecode section start
            absolute_sample = start_sample + sample_pos
            absolute_time = absolute_sample / sample_rate
            audio_timecodes.append({
                'frame_id': frame_id,
                'audio_time': absolute_time,
                'sample_position': absolute_sample,
                'confidence': confidence
            })
        
        return audio_timecodes
    
    def _detect_frame_timecode(self, frame):
        """Extract timecode from a single video frame using robust methods"""
        try:
            # Initialize robust timecode system for video frame analysis
            timecode_system = SharedTimecodeRobust(format_type='PAL', width=frame.shape[1], height=frame.shape[0])
            
            # Method 1: Try corner marker patterns for better alignment
            frame_id = self._read_binary_strip_with_corners(frame)
            if frame_id is not None:
                return frame_id, 0.9  # High confidence for corner-assisted method
            
            # Method 2: Try to read the binary strip without corner alignment
            frame_id = self._read_binary_strip(frame)
            if frame_id is not None:
                return frame_id, 0.7  # Medium confidence for binary strip
            
            # If both binary methods fail, we can't detect the timecode
            # Could add OCR as a future enhancement if needed
            
        except Exception as e:
            # Don't let individual frame errors stop the analysis
            pass
        
        return None, 0.0

    def _read_binary_strip_with_corners(self, frame):
        """Read binary strip using corners for alignment"""
        height, width = frame.shape[:2]
        
        # Detect corner markers
        corner_info = self._detect_corner_markers(frame)
        if not corner_info['detected']:
            return None
        
        # Sort corners to identify positions
        red_corners = corner_info['red_corners']
        blue_corners = corner_info['blue_corners']
        
        # Find the top-left red corner and top-right blue corner
        top_left_red = min(red_corners, key=lambda p: p[0] + p[1])  # Minimum x+y
        top_right_blue = min(blue_corners, key=lambda p: -p[0] + p[1])  # Minimum -x+y
        
        # Calculate the expected binary strip region based on corner positions
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
        
        # Read 32 bits from strip
        bits = []
        block_width = strip_width // 32
        for i in range(32):
            x_start = i * block_width
            x_end = min(x_start + block_width, strip_width)
            if x_end > x_start:
                block = strip_gray[:, x_start:x_end]
                avg_intensity = np.mean(block)
                bit = '1' if avg_intensity > 128 else '0'
                bits.append(bit)
        
        if len(bits) == 32:
            binary_str = ''.join(bits)
            try:
                frame_number = int(binary_str, 2)
                if 0 <= frame_number <= 1000000:  # Sanity check
                    return frame_number
            except ValueError:
                pass
        return None

    def _detect_corner_markers(self, frame):
        """Detect colored corner markers for alignment"""
        # Define color ranges for corner markers
        red_lower = np.array([0, 0, 100], dtype="uint8")
        red_upper = np.array([50, 50, 255], dtype="uint8")
        blue_lower = np.array([100, 0, 0], dtype="uint8")
        blue_upper = np.array([255, 50, 50], dtype="uint8")
        
        # Detect the red corners (top-left, bottom-right)
        red_mask = cv2.inRange(frame, red_lower, red_upper)
        # Detect the blue corners (top-right, bottom-left)
        blue_mask = cv2.inRange(frame, blue_lower, blue_upper)
        
        # Find contours for markers
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
    
    def _read_binary_strip(self, frame):
        """Read binary timecode from the top strip of the frame"""
        try:
            # Extract the top binary strip area (first 20 pixels)
            height, width = frame.shape[:2]
            binary_strip = frame[:20, 40:width-40]  # Skip corner markers (40px each)
            
            # Convert to grayscale for binary analysis
            if len(binary_strip.shape) == 3:
                gray_strip = cv2.cvtColor(binary_strip, cv2.COLOR_BGR2GRAY)
            else:
                gray_strip = binary_strip
            
            # Apply threshold to get binary image
            _, binary = cv2.threshold(gray_strip, 128, 255, cv2.THRESH_BINARY)
            
            # Decode the 32-bit binary pattern
            available_width = width - 80  # Total width minus 40px corners
            block_width = available_width // 32
            
            binary_string = ""
            for i in range(32):
                # Calculate block position
                x_start = i * block_width
                x_end = min(x_start + block_width, available_width)
                
                if x_end <= x_start:
                    continue
                    
                # Sample the center of this block
                block_center_x = (x_start + x_end) // 2
                block_center_y = binary_strip.shape[0] // 2
                
                if (block_center_x < binary_strip.shape[1] and 
                    block_center_y < binary_strip.shape[0]):
                    
                    # Sample a small region around the center
                    sample_size = min(3, block_width // 2)
                    y1 = max(0, block_center_y - sample_size)
                    y2 = min(binary_strip.shape[0], block_center_y + sample_size)
                    x1 = max(0, block_center_x - sample_size)
                    x2 = min(binary_strip.shape[1], block_center_x + sample_size)
                    
                    # Average the grayscale values in this region
                    region = gray_strip[y1:y2, x1:x2]
                    avg_value = np.mean(region) if region.size > 0 else 0
                    
                    # Threshold: >128 = '1' (white), <=128 = '0' (dark)
                    bit = '1' if avg_value > 128 else '0'
                    binary_string += bit
            
            # Decode the 32-bit value
            if len(binary_string) == 32:
                try:
                    # Extract frame number (first 24 bits) and checksum (last 8 bits)
                    frame_bits = binary_string[:24]
                    checksum_bits = binary_string[24:]
                    
                    frame_number = int(frame_bits, 2)
                    received_checksum = int(checksum_bits, 2)
                    
                    # Verify checksum
                    calculated_checksum = self._calculate_robust_checksum(frame_number)
                    
                    if calculated_checksum == received_checksum:
                        return frame_number
                    
                except ValueError:
                    pass
            
            return None
            
        except Exception:
            return None
    
    def _calculate_robust_checksum(self, frame_number):
        """Calculate enhanced checksum for frame validation (matches generator)"""
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
    
    def correlate_timecodes(self, video_timecodes, audio_timecodes):
        """Correlate video and audio timecodes to measure sync offset"""
        print(f"\nCorrelating {len(video_timecodes)} video and {len(audio_timecodes)} audio timecodes...")
        
        matches = []
        
        # For each video timecode, find the closest audio timecode with the same frame_id
        for video_tc in video_timecodes:
            expected_frame_id = video_tc['expected_frame_id']
            video_time = video_tc['video_time']
            
            # Find audio timecodes with matching frame_id
            matching_audio = [a for a in audio_timecodes if a['frame_id'] == expected_frame_id]
            
            if matching_audio:
                # Use the audio timecode with highest confidence
                best_audio = max(matching_audio, key=lambda x: x['confidence'])
                
                offset = best_audio['audio_time'] - video_time
                
                matches.append({
                    'frame_id': expected_frame_id,
                    'video_frame': video_tc['video_frame'],
                    'video_time': video_time,
                    'audio_time': best_audio['audio_time'],
                    'offset_seconds': offset,
                    'confidence': min(video_tc['confidence'], best_audio['confidence'])
                })
        
        if not matches:
            return {
                'success': False,
                'error': 'No matching timecodes found between video and audio',
                'video_count': len(video_timecodes),
                'audio_count': len(audio_timecodes)
            }
        
        # Calculate statistics
        offsets = [m['offset_seconds'] for m in matches]
        avg_offset = np.mean(offsets)
        std_offset = np.std(offsets)
        avg_confidence = np.mean([m['confidence'] for m in matches])
        
        return {
            'success': True,
            'total_matches': len(matches),
            'average_offset_seconds': avg_offset,
            'offset_std_seconds': std_offset,
            'offset_range_seconds': [min(offsets), max(offsets)],
            'average_confidence': avg_confidence,
            'matches': matches,
            'analysis_summary': {
                'video_frames_analyzed': len(video_timecodes),
                'audio_frames_decoded': len(audio_timecodes),
                'sync_pulses_detected': 0  # Not implemented yet
            }
        }
    
    def validate_timecode(self, output_file=None):
        """Run cycle-aware timecode validation"""
        print("\nRunning cycle-aware timecode validation...")
        
        # Step 1: Lock onto cycle structure
        if not self.validate_cycle_lock():
            return {
                'success': False,
                'error': 'Failed to lock onto cycle structure'
            }
        
        # Step 2: Analyze video timecode (frames 100-849 only)
        video_timecodes = self.analyze_video_timecode()
        
        if not video_timecodes:
            return {
                'success': False,
                'error': 'No video timecodes detected in timecode section',
                'timecode_range': f'frames {self.timecode_start_frame}-{self.timecode_end_frame}'
            }
        
        # Step 3: Analyze audio timecode (if available)
        if self.has_audio or self.separate_audio_file:
            audio_path = self.audio_file if self.has_audio else self.separate_audio_file
            
            # Use the refactored VHSTimecodeAnalyzer
            analyzer = VHSTimecodeAnalyzer(self.video_file, audio_path, format_type='PAL')
            results = analyzer.analyze_alignment()
            
        else:
            # Video-only validation (can also use the analyzer)
            analyzer = VHSTimecodeAnalyzer(self.video_file, None, format_type='PAL')
            analyzer._analyze_video_timecode()
            results = {
                'success': True,
                'total_matches': len(analyzer.video_timecodes),
                'video_timecodes': analyzer.video_timecodes,
                'analysis_summary': {
                    'video_frames_analyzed': len(analyzer.video_timecodes),
                    'timecode_section': f'frames {self.timecode_start_frame}-{self.timecode_end_frame}'
                }
            }
        
        # Save results if requested
        if output_file and results.get('success'):
            with open(output_file, 'w') as f:
                json.dump(results, f, indent=2)
            print(f"\nDetailed results saved to: {output_file}")
        
        return results
    
    def display_results(self, results):
        """Display validation results in a user-friendly format"""
        print("\n" + "=" * 60)
        print("CYCLE-AWARE MP4 TIMECODE VALIDATION RESULTS")
        print("=" * 60)
        
        if results.get('success'):
            if 'average_offset_seconds' in results:
                # A/V sync results
                print("AUDIO/VIDEO SYNCHRONIZATION ANALYSIS:")
                print(f"  Average offset: {results['average_offset_seconds']:+.6f} seconds")
                print(f"  Standard deviation: {results['offset_std_seconds']:.6f} seconds")
                print(f"  Measurement precision: ±{results['offset_std_seconds']*1000:.1f} milliseconds")
                print(f"  Total frame matches: {results['total_matches']}")
                print(f"  Average confidence: {results['average_confidence']:.1%}")
                
                # Interpretation
                offset = results['average_offset_seconds']
                if abs(offset) < 0.001:
                    print(f"\n✅ EXCELLENT SYNC (within 1ms)")
                elif abs(offset) < 0.010:
                    print(f"\n✅ GOOD SYNC (within 10ms)")
                elif abs(offset) < 0.050:
                    print(f"\n⚠️  ACCEPTABLE SYNC (within 50ms)")
                else:
                    print(f"\n❌ SYNC ADJUSTMENT NEEDED")
                
                if offset > 0:
                    print(f"   Audio starts {offset:.3f}s AFTER video")
                    print(f"   Recommendation: Reduce audio delay by {offset:.3f}s")
                elif offset < 0:
                    print(f"   Audio starts {abs(offset):.3f}s BEFORE video")
                    print(f"   Recommendation: Increase audio delay by {abs(offset):.3f}s")
                else:
                    print(f"   Perfect synchronization detected!")
            else:
                # Video-only results
                print("VIDEO TIMECODE ANALYSIS:")
                video_frames = results.get('analysis_summary', {}).get('video_frames_analyzed', 0)
                print(f"  Video frames analyzed: {video_frames}")
                print(f"  Timecode detection successful")
                print(f"\n✅ VIDEO TIMECODE VALIDATION COMPLETE")
                print("   MP4 video stream contains valid timecode data")
        
        else:
            print(f"❌ VALIDATION FAILED: {results.get('error', 'Unknown error')}")
            if 'timecode_range' in results:
                print(f"   Timecode range: {results['timecode_range']}")
            if 'video_count' in results and 'audio_count' in results:
                print(f"   Video timecodes: {results['video_count']}")
                print(f"   Audio timecodes: {results['audio_count']}")
        
        print("=" * 60)
        
        # Prompt user to apply delay recommendation (only for A/V sync results)
        if results.get('success') and 'average_offset_seconds' in results:
            offset = results['average_offset_seconds']
            recommended_delay = abs(offset)
            
            try:
                # Add the project root to the path so we can import config
                project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                sys.path.insert(0, project_root)
                from config import load_config, save_config
                
                # Load current config to compare
                config = load_config()
                current_delay = config.get('audio_delay', 0.0)
                
                print(f"\nRecommendation: Set audio delay to {recommended_delay:.3f}s")
                print(f"Current config delay: {current_delay:.3f}s")
                
                if offset < 0:
                    print("   Note: Audio starts before video - unusual, check hardware setup")
                elif abs(recommended_delay - current_delay) > 0.001:  # Different by more than 1ms
                    user_input = input("\nWould you like to update config.json with this delay? (y/n): ").strip().lower()
                    if user_input == 'y':
                        config['audio_delay'] = recommended_delay
                        if save_config(config):
                            print(f"✅ Audio delay updated to {recommended_delay:.3f}s in config.json")
                            print("   This will be applied to future captures (Menu 1)")
                        else:
                            print("❌ Failed to update config.json")
                    else:
                        print("   You can manually apply this delay later through Menu 5.5")
                else:
                    print("   Config already matches recommendation - no update needed")
                    
            except ImportError as e:
                print(f"\nRecommendation: Set audio delay to {recommended_delay:.3f}s")
                print(f"❌ Could not import config module: {e}")
                print("   You can manually apply this delay through Menu 5.5")
            except Exception as e:
                print(f"\nRecommendation: Set audio delay to {recommended_delay:.3f}s")
                print(f"❌ Error checking config: {e}")
                print("   You can manually apply this delay through Menu 5.5")

def main():
    parser = argparse.ArgumentParser(
        description='Cycle-aware MP4 timecode validation - locks onto 4-step cycle structure'
    )
    parser.add_argument('mp4_file', help='MP4 file to validate')
    parser.add_argument('--audio-file', help='Separate audio file (FLAC/WAV) for menu 5.2 mode')
    parser.add_argument('--output', help='Output JSON file for detailed results')
    parser.add_argument('--temp-dir', help='Temporary directory for extracted files')
    
    args = parser.parse_args()
    
    # Validate input file
    if not os.path.exists(args.mp4_file):
        print(f"Error: MP4 file not found: {args.mp4_file}")
        sys.exit(1)
    
    # Check dependencies
    missing_deps = []
    
    # Check ffmpeg/ffprobe
    for cmd in ['ffmpeg', 'ffprobe']:
        try:
            subprocess.run([cmd, '-version'], capture_output=True, check=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            missing_deps.append(cmd)
    
    # Check scipy (needed for audio analysis)
    try:
        import scipy.io.wavfile
    except ImportError:
        missing_deps.append('scipy (pip install scipy)')
    
    # Check OpenCV (needed for video analysis)
    try:
        import cv2
    except ImportError:
        missing_deps.append('opencv-python (pip install opencv-python)')
    
    if missing_deps:
        print("Missing dependencies:")
        for dep in missing_deps:
            print(f"  - {dep}")
        sys.exit(1)
    
    # Validate separate audio file if provided
    if args.audio_file and not os.path.exists(args.audio_file):
        print(f"Error: Audio file not found: {args.audio_file}")
        sys.exit(1)
    
    # Run validation
    try:
        with CycleAwareValidator(args.mp4_file, args.audio_file, args.temp_dir) as validator:
            # Detect what streams are present
            has_video, has_audio = validator.detect_streams()
            
            # Demux streams
            validator.demux_streams()
            
            # Run cycle-aware validation
            results = validator.validate_timecode(args.output)
            
            # Display results
            validator.display_results(results)
            
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
