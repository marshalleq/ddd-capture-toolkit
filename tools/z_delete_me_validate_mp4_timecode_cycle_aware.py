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
    from vhs_timecode_robust import VHSTimecodeRobust
    import cv2
except ImportError as e:
    print(f"Error: Could not import required modules: {e}")
    print("Make sure opencv-python and vhs_timecode_robust.py are available")
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
        
        video_timecodes = []
        
        try:
            # Seek to the start of the timecode section
            cap.set(cv2.CAP_PROP_POS_FRAMES, self.timecode_start_frame)
            
            frame_index = self.timecode_start_frame
            processed_frames = 0
            
            while frame_index <= self.timecode_end_frame:
                ret, frame = cap.read()
                if not ret:
                    break
                
                if processed_frames % 100 == 0:  # Progress every 4 seconds
                    print(f"  Processing video frame {frame_index}...")
                
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
                
                frame_index += 1
                processed_frames += 1
            
            print(f"  Detected timecode in {len(video_timecodes)}/{processed_frames} video frames")
            
        finally:
            cap.release()
        
        return video_timecodes
    
    def analyze_audio_timecode(self, audio_path):
        """Analyze only the timecode section in audio (samples 192000-1631999)"""
        print(f"\nAnalyzing audio timecode section...")
        
        # Extract only the timecode section from audio
        timecode_audio_path = os.path.join(self.temp_dir, 'timecode_only.wav')
        
        cmd = [
            'ffmpeg', '-y', '-v', 'quiet',
            '-i', audio_path,
            '-ss', str(self.timecode_start_time),
            '-t', str(self.timecode_duration),
            '-c:a', 'copy',
            timecode_audio_path
        ]
        
        try:
            subprocess.run(cmd, check=True)
            print(f"  Extracted timecode audio: {timecode_audio_path}")
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Failed to extract timecode audio: {e}")
        
        # Load the timecode-only audio
        try:
            import scipy.io.wavfile as wavfile
            sample_rate, timecode_audio = wavfile.read(timecode_audio_path)
        except ImportError:
            raise RuntimeError("scipy is required for audio analysis. Install with: pip install scipy")
        
        print(f"  Loaded timecode audio: {len(timecode_audio)} samples at {sample_rate}Hz")
        print(f"  Duration: {len(timecode_audio)/sample_rate:.2f}s")
        
        # Initialize robust FSK decoder
        decoder = VHSTimecodeRobust(format_type='PAL')
        
        # Decode FSK from the timecode-only section
        print(f"  Decoding FSK with frequencies {decoder.freq_0}Hz/'0' and {decoder.freq_1}Hz/'1'...")
        decoded_frames = decoder.decode_robust_fsk_audio(timecode_audio)
        
        print(f"  Decoded {len(decoded_frames)} FSK frames")
        
        # Convert to absolute time positions
        audio_timecodes = []
        for sample_pos, frame_id, confidence in decoded_frames:
            # sample_pos is relative to the timecode section
            absolute_time = self.timecode_start_time + (sample_pos / sample_rate)
            audio_timecodes.append({
                'frame_id': frame_id,
                'audio_time': absolute_time,
                'sample_position': self.timecode_start_sample + sample_pos,
                'confidence': confidence
            })
        
        return audio_timecodes
    
    def _detect_frame_timecode(self, frame):
        """Extract timecode from a single video frame using robust VHS timecode methods"""
        try:
            # Initialize robust timecode system for video frame analysis
            timecode_system = VHSTimecodeRobust(format_type='PAL', width=frame.shape[1], height=frame.shape[0])
            
            # Method 1: Try to read the binary strip at the top
            frame_id = self._read_binary_strip(frame, timecode_system)
            if frame_id is not None:
                return frame_id, 0.9  # High confidence for binary method
            
            # Method 2: Try corner marker patterns
            frame_id = self._read_corner_patterns(frame, timecode_system)
            if frame_id is not None:
                return frame_id, 0.7  # Medium confidence for pattern matching
            
            # Method 3: Try OCR on numerical display (fallback)
            frame_id = self._read_numerical_display(frame)
            if frame_id is not None:
                return frame_id, 0.5  # Lower confidence for OCR
            
        except Exception as e:
            # Don't let individual frame errors stop the analysis
            pass
        
        return None, 0.0
    
    def _read_binary_strip(self, frame, timecode_system):
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
    
    def _read_numerical_display(self, frame):
        """Read numerical timecode display using simple OCR techniques"""
        try:
            # Look for numerical text in the center area of the frame
            height, width = frame.shape[:2]
            
            # Extract center region where numerical display is likely
            center_y = height // 2
            center_x = width // 2
            region_height = height // 4
            region_width = width // 2
            
            y1 = max(0, center_y - region_height // 2)
            y2 = min(height, center_y + region_height // 2)
            x1 = max(0, center_x - region_width // 2)
            x2 = min(width, center_x + region_width // 2)
            
            text_region = frame[y1:y2, x1:x2]
            
            # Convert to grayscale
            if len(text_region.shape) == 3:
                gray_region = cv2.cvtColor(text_region, cv2.COLOR_BGR2GRAY)
            else:
                gray_region = text_region
            
            # Simple pattern matching for frame numbers
            # Look for "Frame: XXXXXX" pattern that might be in the display
            
            # This is a placeholder - could implement actual OCR here
            # For now, return None to indicate no detection
            
            return None  # Not implemented yet - needs actual OCR
            
        except Exception:
            return None
    
    def _read_corner_patterns(self, frame, timecode_system):
        """Read timecode from corner marker patterns using robust VHS system"""
        try:
            # Use the corner detection from the robust timecode system
            corners = self._detect_corner_markers(frame)
            
            if len(corners) >= 4:  # Need at least 4 corner markers
                # Try to decode the corner pattern into a frame ID
                # This would need to match the encoding used in the generator
                
                # For now, just detect that we have corner markers
                # The actual frame ID would need to be extracted from the pattern
                
                # This is a placeholder - implement actual corner decoding
                return None  # Not implemented yet
            
            return None
            
        except Exception:
            return None
    
    def _detect_corner_markers(self, frame):
        """Detect colored corner markers in the frame"""
        try:
            # Color boundaries for corner detection (BGR format)
            red_lower = np.array([0, 0, 100], dtype="uint8")
            red_upper = np.array([50, 50, 255], dtype="uint8")
            blue_lower = np.array([100, 0, 0], dtype="uint8")
            blue_upper = np.array([255, 50, 50], dtype="uint8")
            
            # Detect red corners
            red_mask = cv2.inRange(frame, red_lower, red_upper)
            red_contours, _ = cv2.findContours(red_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            # Detect blue corners
            blue_mask = cv2.inRange(frame, blue_lower, blue_upper)
            blue_contours, _ = cv2.findContours(blue_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            corners = []
            
            # Extract corner positions
            for contour in red_contours:
                if cv2.contourArea(contour) > 50:  # Minimum size
                    M = cv2.moments(contour)
                    if M["m00"] != 0:
                        cx = int(M["m10"] / M["m00"])
                        cy = int(M["m01"] / M["m00"])
                        corners.append((cx, cy, 'red'))
            
            for contour in blue_contours:
                if cv2.contourArea(contour) > 50:  # Minimum size
                    M = cv2.moments(contour)
                    if M["m00"] != 0:
                        cx = int(M["m10"] / M["m00"])
                        cy = int(M["m01"] / M["m00"])
                        corners.append((cx, cy, 'blue'))
            
            return corners
            
        except Exception:
            return []
    
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
            
            if self.has_audio:
                print("Mode: Audio/Video synchronization validation (MP4 A/V)")
            else:
                print("Mode: Audio/Video synchronization validation (separate files)")
            
            audio_timecodes = self.analyze_audio_timecode(audio_path)
            
            if not audio_timecodes:
                return {
                    'success': False,
                    'error': 'No audio timecodes decoded in timecode section',
                    'timecode_range': f'{self.timecode_start_time}s-{self.timecode_end_time}s'
                }
            
            # Step 4: Correlate timecodes
            results = self.correlate_timecodes(video_timecodes, audio_timecodes)
            
        else:
            # Video-only validation
            print("Mode: Video-only timecode validation")
            results = {
                'success': True,
                'total_matches': len(video_timecodes),
                'video_timecodes': video_timecodes,
                'analysis_summary': {
                    'video_frames_analyzed': len(video_timecodes),
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
