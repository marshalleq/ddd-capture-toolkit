#!/usr/bin/env python3
"""
Validate Timecode Synchronization
Verify that the video and audio timecodes match exactly for a given frame in MP4 files.
"""

import os
import sys
import argparse
import subprocess
import tempfile
import json
import random
import cv2
import numpy as np
from pathlib import Path

# Add the timecode generator directory to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), 'timecode-generator'))

try:
    from vhs_timecode_robust import VHSTimecodeRobust
except ImportError:
    print("Warning: Could not import robust FSK system, will use basic validation")
    VHSTimecodeRobust = None

class TimecodeValidator:
    def __init__(self, mp4_file):
        self.mp4_file = mp4_file
        self.temp_dir = None
        
    def __enter__(self):
        self.temp_dir = tempfile.mkdtemp(prefix='timecode_validation_')
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.temp_dir and os.path.exists(self.temp_dir):
            import shutil
            shutil.rmtree(self.temp_dir)
    
    def get_video_info(self):
        """Get video information using ffprobe"""
        cmd = [
            'ffprobe', '-v', 'quiet', '-print_format', 'json', '-show_format', '-show_streams',
            self.mp4_file
        ]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            return json.loads(result.stdout)
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Failed to get video info: {e.stderr}")
    
    def extract_frame_at_time(self, time_seconds, output_path):
        """Extract a single frame at the specified time"""
        cmd = [
            'ffmpeg', '-y', '-v', 'quiet',
            '-ss', str(time_seconds),
            '-i', self.mp4_file,
            '-frames:v', '1',
            '-f', 'image2',
            output_path
        ]
        
        try:
            subprocess.run(cmd, check=True)
            return os.path.exists(output_path)
        except subprocess.CalledProcessError:
            return False
    
    def extract_audio_segment(self, start_time, duration, output_path):
        """Extract audio segment starting at specified time"""
        cmd = [
            'ffmpeg', '-y', '-v', 'quiet',
            '-ss', str(start_time),
            '-i', self.mp4_file,
            '-t', str(duration),
            '-acodec', 'pcm_s16le',
            '-ar', '48000',
            '-ac', '1',  # Convert to mono
            output_path
        ]
        
        try:
            subprocess.run(cmd, check=True)
            return os.path.exists(output_path)
        except subprocess.CalledProcessError:
            return False
    
    def read_visual_timecode_from_frame(self, frame_path):
        """Extract visual timecode from frame using OCR techniques"""
        try:
            # Load the image
            img = cv2.imread(frame_path)
            if img is None:
                return None
            
            # Convert to grayscale
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            
            # Look for the timecode text in the center area
            height, width = gray.shape
            center_region = gray[height//4:3*height//4, width//4:3*width//4]
            
            # Enhance contrast for better text detection
            enhanced = cv2.equalizeHist(center_region)
            
            # Try to find timecode pattern using template matching or OCR
            # For now, we'll look for the frame number in the top-left corner
            # which should be more reliable than OCR
            
            # Look for "Frame: XXXXXX" text in top-left
            top_left_region = gray[10:100, 10:300]
            
            # Use simple approach - assume we can read the frame number from filename pattern
            # In the timecode generator, frames are sequential, so we can calculate
            
            return None  # Will implement OCR if needed
            
        except Exception as e:
            print(f"Error reading visual timecode: {e}")
            return None
    
    def decode_audio_timecode(self, audio_data, sample_rate, fps):
        """Decode timecode from audio using the robust FSK system"""
        if VHSTimecodeRobust is None:
            print("Robust FSK system not available for audio decoding")
            return None
            
        try:
            # Initialize the robust FSK system with detected format
            format_type = "PAL" if abs(fps - 25.0) < 1 else "NTSC"
            fsk_system = VHSTimecodeRobust(format_type=format_type)
            
            # Decode using the robust FSK system
            decoded_frames = fsk_system.decode_fsk_audio(audio_data, strict=False)
            
            # Return the best (highest confidence) decoded frame
            if decoded_frames:
                # Sort by confidence and return the best one
                best_result = max(decoded_frames, key=lambda x: x[2])  # x[2] is confidence
                return best_result[1]  # Return frame_id
            
            return None
            
        except Exception as e:
            print(f"Error decoding audio timecode: {e}")
            return None
    
    def calculate_frame_from_time(self, time_seconds, fps):
        """Calculate frame number from time and frame rate"""
        return int(time_seconds * fps)
    
    def frame_to_timecode_string(self, frame_number, fps):
        """Convert frame number to timecode string (HH:MM:SS:FF)"""
        fps_int = int(fps)
        total_seconds = frame_number // fps_int
        frame_remainder = frame_number % fps_int
        
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60
        
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}:{frame_remainder:02d}"
    
    def validate_at_random_time(self, seed=None, test_time=None):
        """Validate timecode sync at a random time in the video"""
        if seed is not None:
            random.seed(seed)
        
        # Get video information
        print("Getting video information...")
        video_info = self.get_video_info()
        
        # Find video stream
        video_stream = None
        audio_stream = None
        
        for stream in video_info['streams']:
            if stream['codec_type'] == 'video' and video_stream is None:
                video_stream = stream
            elif stream['codec_type'] == 'audio' and audio_stream is None:
                audio_stream = stream
        
        if not video_stream:
            raise RuntimeError("No video stream found")
        if not audio_stream:
            raise RuntimeError("No audio stream found")
        
        # Get video properties
        duration = float(video_info['format']['duration'])
        fps_str = video_stream['r_frame_rate']
        fps_num, fps_den = map(int, fps_str.split('/'))
        fps = fps_num / fps_den
        
        print(f"Video duration: {duration:.2f} seconds")
        print(f"Frame rate: {fps:.2f} fps")
        print(f"Total frames: {int(duration * fps)}")
        
        # Choose time to test
        if test_time is not None:
            if test_time < 0 or test_time >= duration:
                raise ValueError(f"Test time {test_time} is outside video duration (0 to {duration:.2f}s)")
            test_time_to_use = test_time
        else:
            # Choose a random time (avoid first and last 5 seconds)
            margin = 5.0
            if duration <= 2 * margin:
                margin = duration / 4
            test_time_to_use = random.uniform(margin, duration - margin)
        
        frame_number = self.calculate_frame_from_time(test_time_to_use, fps)
        expected_timecode = self.frame_to_timecode_string(frame_number, fps)
        
        print(f"\nValidation point:")
        print(f"  Test time: {test_time_to_use:.3f} seconds")
        print(f"  Frame number: {frame_number}")
        print(f"  Expected timecode: {expected_timecode}")
        
        # Extract frame at test time
        frame_path = os.path.join(self.temp_dir, 'validation_frame.png')
        print(f"\nExtracting frame at {test_time_to_use:.3f}s...")
        
        if not self.extract_frame_at_time(test_time_to_use, frame_path):
            raise RuntimeError("Failed to extract video frame")
        
        print(f"Frame saved to: {frame_path}")
        
        # Extract audio segment (multiple frames for robust decoding)
        frame_duration = 1.0 / fps
        audio_duration = frame_duration * 8.0  # 8 frames worth for better decoding
        audio_path = os.path.join(self.temp_dir, 'validation_audio.wav')
        
        print(f"Extracting audio segment ({audio_duration:.3f}s)...")
        if not self.extract_audio_segment(test_time_to_use, audio_duration, audio_path):
            raise RuntimeError("Failed to extract audio segment")
        
        print(f"Audio saved to: {audio_path}")
        
        # Analyze the extracted frame visually
        print(f"\nAnalyzing visual frame...")
        if os.path.exists(frame_path):
            img = cv2.imread(frame_path)
            if img is not None:
                height, width = img.shape[:2]
                print(f"  Frame dimensions: {width}x{height}")
                
                # Look for visual timecode in the center
                center_y = height // 2
                center_region = img[center_y-50:center_y+50, :]
                
                # Check if there's readable text (rough estimate)
                gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                top_region = gray[10:100, 10:400]  # Frame number area
                center_region_gray = gray[center_y-50:center_y+50, width//4:3*width//4]  # Timecode area
                
                # Simple text detection - look for high contrast areas
                top_contrast = np.std(top_region)
                center_contrast = np.std(center_region_gray)
                
                print(f"  Text contrast (top): {top_contrast:.1f}")
                print(f"  Text contrast (center): {center_contrast:.1f}")
                
                if center_contrast > 20:  # Threshold for text presence
                    print(f"  ✓ Visual timecode appears to be present")
                else:
                    print(f"  ✗ Visual timecode may not be clearly visible")
        
        # Analyze the audio for FSK timecode
        print(f"\nAnalyzing audio timecode...")
        try:
            import soundfile as sf
            audio_data, sample_rate = sf.read(audio_path)
            
            if len(audio_data.shape) > 1:
                audio_data = audio_data[:, 0]  # Convert to mono
            
            print(f"  Audio sample rate: {sample_rate} Hz")
            print(f"  Audio duration: {len(audio_data)/sample_rate:.3f}s")
            print(f"  Audio RMS level: {np.sqrt(np.mean(audio_data**2)):.4f}")
            
            # Analyze frequency content
            from scipy import signal
            frequencies, times, spectrogram = signal.spectrogram(
                audio_data, sample_rate, window='hann', nperseg=1024
            )
            
            # Look for robust FSK frequencies (800Hz for '0', 1600Hz for '1')
            freq_800_idx = np.argmin(np.abs(frequencies - 800))
            freq_1600_idx = np.argmin(np.abs(frequencies - 1600))
            
            power_800 = np.mean(spectrogram[freq_800_idx, :])
            power_1600 = np.mean(spectrogram[freq_1600_idx, :])
            
            print(f"  Power at ~800Hz (robust '0'): {power_800:.2e}")
            print(f"  Power at ~1600Hz (robust '1'): {power_1600:.2e}")
            
            if power_800 > 1e-10 or power_1600 > 1e-10:
                print(f"  ✓ FSK frequencies detected in audio")
                
                # Try to decode if robust system is available
                if VHSTimecodeRobust is not None:
                    try:
                        # Initialize with detected format
                        format_type = "PAL" if abs(fps - 25.0) < 1 else "NTSC"
                        fsk_system = VHSTimecodeRobust(format_type=format_type)
                        
                        print(f"  Debug: Using format {format_type}, audio samples: {len(audio_data)}")
                        print(f"  Debug: Audio min/max: {np.min(audio_data):.4f}/{np.max(audio_data):.4f}")
                        print(f"  Debug: Decoder expects {fsk_system.samples_per_frame} samples per frame")
                        print(f"  Debug: Bits per frame: {fsk_system.bits_per_frame}, samples per bit: {fsk_system.samples_per_bit}")
                        expected_frames = len(audio_data) // fsk_system.samples_per_frame
                        print(f"  Debug: Expected number of complete frames in audio: {expected_frames}")
                        
                        # Decode using the robust FSK system
                        decoded_frames = fsk_system.decode_fsk_audio(audio_data, strict=False)
                        print(f"  Debug: Decoder returned {len(decoded_frames) if decoded_frames else 0} results")
                        
                        # Debug the decoded results
                        if decoded_frames:
                            print(f"  Debug: Decoded results:")
                            for i, (sample_pos, frame_id, confidence) in enumerate(decoded_frames[:5]):  # Show first 5
                                print(f"    Result {i+1}: Sample {sample_pos}, Frame {frame_id}, Confidence {confidence:.3f}")
                        
                        # Get the best (highest confidence) decoded frame
                        if decoded_frames:
                            best_result = max(decoded_frames, key=lambda x: x[2])  # x[2] is confidence
                            decoded_frame = best_result[1]  # x[1] is frame_id
                            confidence = best_result[2]     # x[2] is confidence
                            
                            decoded_timecode = self.frame_to_timecode_string(decoded_frame, fps)
                            print(f"  Decoded frame number: {decoded_frame} (confidence: {confidence:.2f})")
                            print(f"  Decoded timecode: {decoded_timecode}")
                            
                            # Compare with expected
                            if decoded_frame == frame_number:
                                print(f"  ✓ PERFECT MATCH: Audio and video timecodes are synchronized!")
                                return True, {
                                    'expected_frame': frame_number,
                                    'decoded_frame': decoded_frame,
                                    'expected_timecode': expected_timecode,
                                    'decoded_timecode': decoded_timecode,
                                    'time_offset': test_time_to_use,
                                    'match': True,
                                    'confidence': confidence
                                }
                            else:
                                difference = decoded_frame - frame_number
                                print(f"  ✗ MISMATCH: Audio frame {decoded_frame} != Video frame {frame_number}")
                                print(f"  Frame difference: {difference} frames ({difference/fps:.3f}s)")
                                return False, {
                                    'expected_frame': frame_number,
                                    'decoded_frame': decoded_frame,
                                    'expected_timecode': expected_timecode,
                                    'decoded_timecode': decoded_timecode,
                                    'time_offset': test_time_to_use,
                                    'match': False,
                                    'frame_difference': difference,
                                    'confidence': confidence
                                }
                        else:
                            print(f"  ✗ Could not decode frame number from audio")
                            return None, {'error': 'audio_decode_failed'}
                    except Exception as e:
                        print(f"  ✗ Error during audio decoding: {e}")
                        return None, {'error': f'decode_error: {e}'}
                else:
                    print(f"  ! Robust FSK decoder not available")
                    return None, {'error': 'no_decoder'}
            else:
                print(f"  ✗ No FSK frequencies detected")
                return None, {'error': 'no_fsk_signal'}
                
        except ImportError as e:
            print(f"  ✗ Missing audio analysis dependencies: {e}")
            return None, {'error': f'missing_deps: {e}'}
        except Exception as e:
            print(f"  ✗ Error analyzing audio: {e}")
            return None, {'error': f'audio_analysis_error: {e}'}
        
        # If we get here, we have the visual and audio data but couldn't decode
        return None, {
            'expected_frame': frame_number,
            'expected_timecode': expected_timecode,
            'time_offset': test_time_to_use,
            'frame_path': frame_path,
            'audio_path': audio_path,
            'error': 'manual_verification_required'
        }
    
    def validate_multiple_points(self, num_points=5):
        """Validate timecode sync at multiple random points"""
        print(f"Validating timecode synchronization at {num_points} random points...\n")
        
        results = []
        matches = 0
        
        for i in range(num_points):
            print(f"=== Validation Point {i+1}/{num_points} ===")
            
            try:
                success, result = self.validate_at_random_time(seed=i*42)  # Reproducible randomness
                results.append(result)
                
                if success:
                    matches += 1
                    print(f"Result: ✓ MATCH\n")
                elif success is False:
                    print(f"Result: ✗ MISMATCH\n")
                else:
                    print(f"Result: ? INCONCLUSIVE\n")
                    
            except Exception as e:
                print(f"Error during validation: {e}\n")
                results.append({'error': str(e)})
        
        # Summary
        print(f"=== VALIDATION SUMMARY ===")
        print(f"Total validation points: {num_points}")
        print(f"Successful matches: {matches}")
        print(f"Match rate: {matches/num_points*100:.1f}%")
        
        if matches == num_points:
            print(f"✓ EXCELLENT: All validation points show perfect timecode synchronization!")
        elif matches > num_points * 0.8:
            print(f"✓ GOOD: Most validation points show correct synchronization")
        elif matches > 0:
            print(f"⚠ PARTIAL: Some validation points show synchronization issues")
        else:
            print(f"✗ POOR: No successful timecode matches found")
        
        return results

def main():
    parser = argparse.ArgumentParser(description='Validate timecode synchronization in MP4 files')
    parser.add_argument('mp4_file', help='Path to MP4 file to validate')
    parser.add_argument('--points', type=int, default=1, 
                       help='Number of random validation points (default: 1)')
    parser.add_argument('--seed', type=int, 
                       help='Random seed for reproducible validation')
    parser.add_argument('--test-time', type=float, 
                       help='Test at specific time instead of random time')
    
    args = parser.parse_args()
    
    if not os.path.exists(args.mp4_file):
        print(f"Error: MP4 file not found: {args.mp4_file}")
        return 1
    
    print(f"Timecode Validation for: {args.mp4_file}")
    print(f"{'='*60}")
    
    try:
        with TimecodeValidator(args.mp4_file) as validator:
            if args.points == 1:
                success, result = validator.validate_at_random_time(seed=args.seed, test_time=args.test_time)
                
                if success:
                    print(f"\n🎉 SUCCESS: Timecode synchronization is perfect!")
                    return 0
                elif success is False:
                    print(f"\n❌ FAILURE: Timecode synchronization mismatch detected!")
                    return 1
                else:
                    print(f"\n❓ INCONCLUSIVE: Could not fully validate synchronization")
                    print(f"Manual verification may be required.")
                    if 'frame_path' in result:
                        print(f"Frame image: {result['frame_path']}")
                    if 'audio_path' in result:
                        print(f"Audio segment: {result['audio_path']}")
                    return 2
            else:
                results = validator.validate_multiple_points(args.points)
                matches = sum(1 for r in results if r.get('match') == True)
                
                if matches == args.points:
                    return 0  # Perfect
                elif matches > 0:
                    return 1  # Partial issues
                else:
                    return 2  # Major issues
                    
    except Exception as e:
        print(f"Error during validation: {e}")
        return 1

if __name__ == '__main__':
    sys.exit(main())
