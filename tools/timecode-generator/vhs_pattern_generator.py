#!/usr/bin/env python3
"""
VHS Pattern Generator with 4-Step Cycle for Sync Validation

This creates a repeating 4-step pattern designed for VHS recording and validation:
1. Test chart + 1kHz tone
2. Black screen (no audio) - Visual cue for recording control  
3. Timecode - Timing reference during cycle
4. Black screen (no audio) - Visual cue that 30 seconds is finished

Then loops back to step 1, creating continuous cycles for validation.
Each cycle is 35 seconds total.
"""

import os
import sys
import argparse
import cv2
import numpy as np
import subprocess
import tempfile
import json
from datetime import datetime

# Add the current directory to path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from shared_timecode_robust import SharedTimecodeRobust
except ImportError:
    print("Warning: Could not import robust FSK system")
    SharedTimecodeRobust = None

class VHSPatternGenerator:
    def __init__(self, format_type="PAL", width=720, height=576):
        """
        Initialize VHS pattern generator
        
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
            self.test_chart_path = "media/Test Patterns/testchartpal.tif"
        elif self.format_type == "NTSC":
            self.fps = 29.97
            self.width = width
            self.height = height if height else 480
            self.test_chart_path = "media/Test Patterns/testchartntsc.tif"
        else:
            raise ValueError("Format must be PAL or NTSC")
        
        # Audio parameters
        self.sample_rate = 48000
        self.audio_channels = 1  # MONO
        
        # Pattern timing (in seconds) - 35 second cycles
        self.test_chart_duration = 3.0      # Step 1: Test chart + 1kHz tone
        self.black_screen_1_duration = 1.0  # Step 2: Black screen (no audio)
        self.timecode_duration = 30.0       # Step 3: Timecode + FSK audio
        self.black_screen_2_duration = 1.0  # Step 4: Black screen (no audio)
        self.total_cycle_duration = 35.0    # Total cycle duration
        
        # Initialize timecode system if available
        if SharedTimecodeRobust:
            self.timecode_system = SharedTimecodeRobust(format_type=self.format_type, width=self.width, height=self.height)
        else:
            self.timecode_system = None
        
        print(f"Initialized {self.format_type} pattern generator")
        print(f"4-step cycle structure:")
        print(f"  1. {self.test_chart_duration}s test chart + 1kHz tone")
        print(f"  2. {self.black_screen_1_duration}s black screen (no audio)")
        print(f"  3. {self.timecode_duration}s timecode + FSK audio")
        print(f"  4. {self.black_screen_2_duration}s black screen (no audio)")
        print(f"  Total cycle: {self.total_cycle_duration}s")
    
    def load_test_chart(self):
        """Load the test chart image"""
        # Try different possible paths for the test chart
        possible_paths = [
            self.test_chart_path,  # Relative from current directory
            os.path.join("..", "..", self.test_chart_path),  # From tools/timecode-generator/
            os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), self.test_chart_path)  # Absolute project root
        ]
        
        chart_found = None
        for path in possible_paths:
            if os.path.exists(path):
                chart_found = path
                break
        
        if not chart_found:
            raise FileNotFoundError(f"Test chart not found. Tried paths: {possible_paths}")
        
        # Load and resize test chart to match video dimensions
        chart = cv2.imread(chart_found)
        if chart is None:
            raise ValueError(f"Could not load test chart: {chart_found}")
        
        # Resize to match video dimensions
        chart = cv2.resize(chart, (self.width, self.height))
        return chart
    
    def create_black_frame(self):
        """Create a black frame"""
        return np.zeros((self.height, self.width, 3), dtype=np.uint8)
    
    def generate_pattern_video(self, num_cycles, output_file):
        """
        Generate the complete pattern video
        
        Args:
            num_cycles: Number of 35-second cycles to generate
            output_file: Output MP4 file path
        """
        if num_cycles < 1:
            raise ValueError("Must have at least 1 cycle")
            
        actual_duration = num_cycles * self.total_cycle_duration
        print(f"Generating {num_cycles} cycles ({actual_duration}s total)...")
        
        # Load test chart
        test_chart = self.load_test_chart()
        black_frame = self.create_black_frame()
        
        # Create temporary directory for video frames and audio
        with tempfile.TemporaryDirectory(prefix='vhs_pattern_') as temp_dir:
            print("Generating video frames...")
            
            frame_count = 0
            total_frames = int(actual_duration * self.fps)
            
            # Create frames for each cycle
            for cycle in range(num_cycles):
                cycle_start_time = cycle * self.total_cycle_duration
                
                # Step 1: Test chart + 1kHz tone (3 seconds)
                chart_frames = int(self.test_chart_duration * self.fps)
                for f in range(chart_frames):
                    frame_path = os.path.join(temp_dir, f"frame_{frame_count:08d}.png")
                    cv2.imwrite(frame_path, test_chart)
                    frame_count += 1
                
                # Step 2: Black screen (no audio) - 5 seconds
                black1_frames = int(self.black_screen_1_duration * self.fps)
                for f in range(black1_frames):
                    frame_path = os.path.join(temp_dir, f"frame_{frame_count:08d}.png")
                    cv2.imwrite(frame_path, black_frame)
                    frame_count += 1
                
                # Step 3: Timecode frames (30 seconds)
                timecode_frames = int(self.timecode_duration * self.fps)
                
                for f in range(timecode_frames):
                    # Frame number starts from 0 for each timecode segment
                    timecode_frame_number = f
                    timecode_str = self.frame_to_timecode_string(timecode_frame_number, self.fps)
                    
                    if self.timecode_system:
                        timecode_frame = self.timecode_system.generate_frame_image(timecode_frame_number, timecode_str)
                    else:
                        # Fallback: create simple timecode display
                        timecode_frame = self.create_simple_timecode_frame(timecode_frame_number, timecode_str)
                    
                    frame_path = os.path.join(temp_dir, f"frame_{frame_count:08d}.png")
                    cv2.imwrite(frame_path, timecode_frame)
                    frame_count += 1
                
                # Step 4: Black screen (no audio) - 5 seconds
                black2_frames = int(self.black_screen_2_duration * self.fps)
                for f in range(black2_frames):
                    frame_path = os.path.join(temp_dir, f"frame_{frame_count:08d}.png")
                    cv2.imwrite(frame_path, black_frame)
                    frame_count += 1
            
            print(f"Generated {frame_count} frames ({frame_count/self.fps:.1f}s)")
            
            # Generate audio
            print("Generating audio...")
            audio_path = os.path.join(temp_dir, "audio.wav")
            self.generate_pattern_audio(num_cycles, audio_path)
            
            # Combine video and audio with FFmpeg
            print("Combining video and audio...")
            self.combine_video_audio(temp_dir, audio_path, output_file, actual_duration)
            
        print(f"Pattern video created: {output_file}")
        return output_file
    
    def generate_pattern_audio(self, num_cycles, output_path):
        """Generate the complete pattern audio with frame-perfect timing"""
        # Use exact sample calculations to avoid cumulative timing errors
        cycle_samples = int(self.total_cycle_duration * self.sample_rate)
        total_samples = cycle_samples * num_cycles
        audio_data = np.zeros(total_samples, dtype=np.float32)
        
        # Pre-calculate frame-perfect sample counts
        chart_samples = int(self.test_chart_duration * self.sample_rate)
        black1_samples = int(self.black_screen_1_duration * self.sample_rate)
        timecode_samples = int(self.timecode_duration * self.sample_rate)
        black2_samples = int(self.black_screen_2_duration * self.sample_rate)
        
        # Calculate exact samples per video frame (critical for sync)
        samples_per_video_frame = self.sample_rate / self.fps  # Keep as float for precision
        timecode_frames = int(self.timecode_duration * self.fps)
        
        print(f"Frame-accurate audio timing:")
        print(f"  Samples per video frame: {samples_per_video_frame:.6f}")
        print(f"  Timecode frames: {timecode_frames}")
        print(f"  Chart: {chart_samples} samples")
        print(f"  Timecode: {timecode_samples} samples")
        
        for cycle in range(num_cycles):
            cycle_start = cycle * cycle_samples
            
            # Step 1: Test chart with clean 1kHz tone
            tone_1khz = self.generate_tone(1000.0, self.test_chart_duration)
            actual_chart_samples = min(len(tone_1khz), chart_samples)
            audio_data[cycle_start:cycle_start + actual_chart_samples] = tone_1khz[:actual_chart_samples]
            
            # Step 2: Black screen with silence (1 second)
            black1_start = cycle_start + chart_samples
            audio_data[black1_start:black1_start + black1_samples] = 0.0
            
            # Step 3: Timecode with FSK audio - FRAME PERFECT TIMING
            timecode_start = black1_start + black1_samples
            
            if self.timecode_system:
                # Generate FSK timecode with exact frame boundaries
                for frame_idx in range(timecode_frames):
                    # Calculate exact sample boundaries for each frame
                    frame_start_exact = timecode_start + (frame_idx * samples_per_video_frame)
                    frame_end_exact = timecode_start + ((frame_idx + 1) * samples_per_video_frame)
                    
                    # Convert to integer sample positions
                    frame_start_int = int(round(frame_start_exact))
                    frame_end_int = int(round(frame_end_exact))
                    
                    # Ensure we don't exceed the timecode section
                    frame_end_int = min(frame_end_int, timecode_start + timecode_samples)
                    
                    if frame_end_int > frame_start_int:
                        frame_audio = self.timecode_system.generate_robust_fsk_audio(frame_idx)
                        actual_samples = min(len(frame_audio), frame_end_int - frame_start_int)
                        audio_data[frame_start_int:frame_start_int + actual_samples] = frame_audio[:actual_samples]
            else:
                # Fallback: generate simple tone for timecode section
                timecode_tone = self.generate_tone(800, self.timecode_duration)  # 800Hz tone
                audio_data[timecode_start:timecode_start + len(timecode_tone)] = timecode_tone
            
            # Step 4: Black screen with silence (1 second)
            black2_start = timecode_start + timecode_samples
            audio_data[black2_start:black2_start + black2_samples] = 0.0
        
        # Save audio as WAV
        self.save_audio_wav(audio_data, output_path)
    
    def generate_tone(self, frequency, duration):
        """Generate a clean sine wave tone"""
        samples = int(duration * self.sample_rate)
        # Create time array from 0 to duration
        t = np.arange(samples, dtype=np.float32) / self.sample_rate
        # Generate pure sine wave at specified frequency
        tone = 0.6 * np.sin(2.0 * np.pi * frequency * t)
        return tone
    
    def save_audio_wav(self, audio_data, output_path):
        """Save audio data as WAV file"""
        # Normalize to 16-bit range
        audio_16bit = (audio_data * 32767).astype(np.int16)
        
        # Use scipy.io.wavfile if available, otherwise use subprocess
        try:
            from scipy.io import wavfile
            wavfile.write(output_path, self.sample_rate, audio_16bit)
        except ImportError:
            # Fallback: create WAV using sox
            temp_raw = output_path + ".raw"
            audio_16bit.tofile(temp_raw)
            
            subprocess.run([
                'sox', '-t', 'raw', '-r', str(self.sample_rate), '-e', 'signed', '-b', '16', '-c', '1',
                temp_raw, output_path
            ], check=True)
            
            os.remove(temp_raw)
    
    def combine_video_audio(self, frames_dir, audio_path, output_path, duration):
        """Combine video frames and audio using FFmpeg"""
        # Create video from frames
        temp_video = os.path.join(os.path.dirname(output_path), "temp_video.mp4")
        
        ffmpeg_cmd = [
            'ffmpeg', '-y',
            '-r', str(self.fps),
            '-i', os.path.join(frames_dir, 'frame_%08d.png'),
            '-i', audio_path,
            '-c:v', 'mpeg4',  # Use mpeg4 instead of libx264 for better compatibility
            '-c:a', 'pcm_s16le',
            '-pix_fmt', 'yuv420p',
            '-qscale:v', '3',  # High quality for mpeg4
            '-t', str(duration),
            '-map', '0:v',
            '-map', '1:a',
            output_path
        ]
        
        subprocess.run(ffmpeg_cmd, check=True)
    
    def create_simple_timecode_frame(self, frame_number, timecode_str):
        """Create a simple timecode frame (fallback when robust system unavailable)"""
        frame = np.zeros((self.height, self.width, 3), dtype=np.uint8)
        
        # Add frame number in top-left
        font = cv2.FONT_HERSHEY_SIMPLEX
        cv2.putText(frame, f"Frame: {frame_number:06d}", (20, 70), font, 1.0, (255, 255, 255), 2)
        
        # Add timecode in center
        (text_width, text_height), baseline = cv2.getTextSize(timecode_str, font, 3.0, 8)
        x = (self.width - text_width) // 2
        y = (self.height + text_height) // 2
        cv2.putText(frame, timecode_str, (x, y), font, 3.0, (255, 255, 255), 8)
        
        return frame
    
    def frame_to_timecode_string(self, frame_number, fps):
        """Convert frame number to timecode string (HH:MM:SS:FF)"""
        fps_int = int(fps)
        total_seconds = frame_number // fps_int
        frame_remainder = frame_number % fps_int
        
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60
        
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}:{frame_remainder:02d}"
    
    def generate_metadata(self, num_cycles, output_file):
        """Generate metadata for the pattern"""
        duration_seconds = num_cycles * self.total_cycle_duration
        
        metadata = {
            "pattern_metadata": {
                "generator": "VHS Pattern Generator v2.0 - 4-Step Cycle",
                "timestamp": datetime.now().isoformat(),
                "format": self.format_type,
                "fps": self.fps,
                "resolution": f"{self.width}x{self.height}",
                "duration_seconds": duration_seconds,
                "total_cycles": num_cycles
            },
            "cycle_structure": {
                "total_cycle_duration": self.total_cycle_duration,
                "test_chart_duration": self.test_chart_duration,
                "black_screen_1_duration": self.black_screen_1_duration,
                "timecode_duration": self.timecode_duration,
                "black_screen_2_duration": self.black_screen_2_duration,
                "steps": [
                    {"step": 1, "duration": self.test_chart_duration, "content": "test_chart + 1kHz_tone"},
                    {"step": 2, "duration": self.black_screen_1_duration, "content": "black_screen + silence"},
                    {"step": 3, "duration": self.timecode_duration, "content": "timecode_frames + FSK_audio"},
                    {"step": 4, "duration": self.black_screen_2_duration, "content": "black_screen + silence"}
                ]
            },
            "audio_parameters": {
                "sample_rate": self.sample_rate,
                "channels": self.audio_channels,
                "test_tone_frequency": 1000,  # Hz
                "timecode_encoding": "robust_FSK" if self.timecode_system else "fallback_tone"
            },
            "usage_instructions": {
                "purpose": "VHS recording with test charts and timecode validation",
                "workflow": [
                    "Record this MP4 to VHS tape",
                    "Capture back with Domesday Duplicator + audio interface", 
                    "Use validation script to check sync at timecode segments",
                    "Test charts provide visual reference and audio calibration"
                ]
            }
        }
        
        metadata_file = output_file.replace('.mp4', '_metadata.json')
        with open(metadata_file, 'w') as f:
            json.dump(metadata, f, indent=2)
        
        return metadata_file

def main():
    parser = argparse.ArgumentParser(description='Generate VHS pattern with 4-step cycles for sync validation')
    parser.add_argument('--cycles', type=int, default=10, help='Number of 35-second cycles (default: 10)')
    parser.add_argument('--format', choices=['PAL', 'NTSC'], default='PAL', help='Video format (default: PAL)')
    parser.add_argument('--output', required=True, help='Output MP4 file path')
    
    args = parser.parse_args()
    
    # Show helpful cycle count suggestions
    if args.cycles == 10:
        print("\nCycle count suggestions:")
        print("  Default: 10 cycles (5.8 minutes)")
        print("  30-min tape: 51 cycles")
        print("  1-hour tape: 103 cycles")
        print("  3-hour tape: 309 cycles")
        print("  4-hour tape: 411 cycles")
        print()
    
    try:
        # Create generator
        generator = VHSPatternGenerator(format_type=args.format)
        
        # Generate pattern
        output_file = generator.generate_pattern_video(args.cycles, args.output)
        
        # Generate metadata
        metadata_file = generator.generate_metadata(args.cycles, output_file)
        
        duration_minutes = (args.cycles * 35) / 60
        
        print(f"\nPattern generation completed!")
        print(f"Video file: {output_file}")
        print(f"Metadata: {metadata_file}")
        print(f"Duration: {args.cycles} cycles × 35s = {duration_minutes:.1f} minutes")
        
        # Show file info
        if os.path.exists(output_file):
            size_mb = os.path.getsize(output_file) / (1024*1024)
            print(f"File size: {size_mb:.1f} MB")
        
        return 0
        
    except Exception as e:
        print(f"Error generating pattern: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
