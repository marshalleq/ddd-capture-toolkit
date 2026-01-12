#!/usr/bin/env python3
"""
VHS Pattern Generator with V2 Robust Calibration Cycle

This creates a repeating calibration cycle with machine-readable lead-in/lead-out
structure for VHS recording and validation. The V2 encoding uses:
- 16-bit frames with marker-based validation
- 400/800 Hz FSK audio (optimized for VHS linear audio)
- Red/blue visual encoding for color-based detection
- 3 vertical rows for redundancy

62-second V2 Calibration Cycle Structure:
  Section 1: Leader     (10s) - 0xFFFF pattern, preparation period
  Section 2: Countdown  (5s)  - "11" prefix + countdown value
  Section 3: Separator  (1s)  - 0x0000 pattern, transition marker
  Section 4: Timecode   (30s) - "10" prefix + 12-bit frame + "01" suffix
  Section 5: Separator  (1s)  - 0x0000 pattern, transition marker
  Section 6: Count-up   (5s)  - "00" prefix + count-up value
  Section 7: Tail       (10s) - 0xFFFF pattern, cycle complete

Then loops back to Section 1 for continuous cycles.
Each cycle is 62 seconds total.
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

        # V2 Pattern timing (in seconds) - 62 second cycles
        # Lead-in structure
        self.leader_duration = 10.0           # Section 1: Leader (0xFFFF)
        self.countdown_duration = 5.0         # Section 2: Countdown ("11" prefix)
        self.separator_duration = 1.0         # Section 3 & 5: Separator (0x0000)
        # Main timecode section
        self.timecode_duration = 30.0         # Section 4: Timecode ("10" prefix)
        # Lead-out structure
        self.countup_duration = 5.0           # Section 6: Count-up ("00" prefix)
        self.tail_duration = 10.0             # Section 7: Tail (0xFFFF)

        # Total cycle duration: 10 + 5 + 1 + 30 + 1 + 5 + 10 = 62 seconds
        self.total_cycle_duration = (self.leader_duration + self.countdown_duration +
                                     self.separator_duration + self.timecode_duration +
                                     self.separator_duration + self.countup_duration +
                                     self.tail_duration)

        # Initialize timecode system if available
        if SharedTimecodeRobust:
            self.timecode_system = SharedTimecodeRobust(format_type=self.format_type, width=self.width, height=self.height)
        else:
            self.timecode_system = None

        print(f"Initialized {self.format_type} V2 pattern generator")
        print(f"62-second calibration cycle structure:")
        print(f"  1. Leader     ({self.leader_duration}s)    - 0xFFFF pattern")
        print(f"  2. Countdown  ({self.countdown_duration}s)     - '11' prefix + countdown")
        print(f"  3. Separator  ({self.separator_duration}s)     - 0x0000 pattern")
        print(f"  4. Timecode   ({self.timecode_duration}s)    - '10' prefix + frame + '01'")
        print(f"  5. Separator  ({self.separator_duration}s)     - 0x0000 pattern")
        print(f"  6. Count-up   ({self.countup_duration}s)     - '00' prefix + count-up")
        print(f"  7. Tail       ({self.tail_duration}s)    - 0xFFFF pattern")
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
        Generate the complete V2 pattern video with lead-in/lead-out structure

        Args:
            num_cycles: Number of 62-second cycles to generate
            output_file: Output MP4 file path
        """
        if num_cycles < 1:
            raise ValueError("Must have at least 1 cycle")

        actual_duration = num_cycles * self.total_cycle_duration
        print(f"Generating {num_cycles} V2 cycles ({actual_duration}s total)...")

        # Create temporary directory for video frames and audio
        with tempfile.TemporaryDirectory(prefix='vhs_pattern_v2_') as temp_dir:
            print("Generating video frames...")

            frame_count = 0
            total_frames = int(actual_duration * self.fps)

            # Pre-calculate frame counts for each section
            leader_frames = int(self.leader_duration * self.fps)
            countdown_frames = int(self.countdown_duration * self.fps)
            separator_frames = int(self.separator_duration * self.fps)
            timecode_frames = int(self.timecode_duration * self.fps)
            countup_frames = int(self.countup_duration * self.fps)
            tail_frames = int(self.tail_duration * self.fps)

            # Create frames for each cycle
            for cycle in range(num_cycles):
                print(f"  Cycle {cycle + 1}/{num_cycles}...", end='', flush=True)

                # Section 1: Leader (10s) - 0xFFFF pattern
                for f in range(leader_frames):
                    frame = self._generate_section_frame('leader', f, leader_frames)
                    frame_path = os.path.join(temp_dir, f"frame_{frame_count:08d}.png")
                    cv2.imwrite(frame_path, frame)
                    frame_count += 1

                # Section 2: Countdown (5s) - "11" prefix with countdown value
                for f in range(countdown_frames):
                    # Calculate frames remaining until timecode starts (countdown + separator)
                    frames_until_timecode = (countdown_frames - f) + separator_frames
                    frame = self._generate_section_frame('countdown', f, countdown_frames,
                                                          frames_until_timecode=frames_until_timecode)
                    frame_path = os.path.join(temp_dir, f"frame_{frame_count:08d}.png")
                    cv2.imwrite(frame_path, frame)
                    frame_count += 1

                # Section 3: Separator (1s) - 0x0000 pattern
                for f in range(separator_frames):
                    frame = self._generate_section_frame('separator', f, separator_frames)
                    frame_path = os.path.join(temp_dir, f"frame_{frame_count:08d}.png")
                    cv2.imwrite(frame_path, frame)
                    frame_count += 1

                # Section 4: Timecode (30s) - "10" + 12-bit frame + "01"
                for f in range(timecode_frames):
                    timecode_str = self.frame_to_timecode_string(f, self.fps)
                    if self.timecode_system:
                        frame = self.timecode_system.generate_frame_image(f, timecode_str, frame_type='timecode')
                    else:
                        frame = self.create_simple_timecode_frame(f, timecode_str)
                    frame_path = os.path.join(temp_dir, f"frame_{frame_count:08d}.png")
                    cv2.imwrite(frame_path, frame)
                    frame_count += 1

                # Section 5: Separator (1s) - 0x0000 pattern
                for f in range(separator_frames):
                    frame = self._generate_section_frame('separator', f, separator_frames)
                    frame_path = os.path.join(temp_dir, f"frame_{frame_count:08d}.png")
                    cv2.imwrite(frame_path, frame)
                    frame_count += 1

                # Section 6: Count-up (5s) - "00" prefix with count-up value
                for f in range(countup_frames):
                    # Frames since timecode ended
                    frames_since_timecode = f + separator_frames
                    frame = self._generate_section_frame('leadout', f, countup_frames,
                                                          frames_since_timecode=frames_since_timecode)
                    frame_path = os.path.join(temp_dir, f"frame_{frame_count:08d}.png")
                    cv2.imwrite(frame_path, frame)
                    frame_count += 1

                # Section 7: Tail (10s) - 0xFFFF pattern (same as leader)
                for f in range(tail_frames):
                    frame = self._generate_section_frame('leader', f, tail_frames)  # Same pattern as leader
                    frame_path = os.path.join(temp_dir, f"frame_{frame_count:08d}.png")
                    cv2.imwrite(frame_path, frame)
                    frame_count += 1

                print(" done")

            print(f"Generated {frame_count} frames ({frame_count/self.fps:.1f}s)")

            # Generate audio
            print("Generating audio...")
            audio_path = os.path.join(temp_dir, "audio.wav")
            self.generate_pattern_audio(num_cycles, audio_path)

            # Combine video and audio with FFmpeg
            print("Combining video and audio...")
            self.combine_video_audio(temp_dir, audio_path, output_file, actual_duration)

        print(f"V2 Pattern video created: {output_file}")
        return output_file

    def _generate_section_frame(self, section_type, frame_in_section, section_total_frames,
                                 frames_until_timecode=None, frames_since_timecode=None):
        """
        Generate a video frame for a specific section of the calibration cycle

        Args:
            section_type: 'leader', 'countdown', 'separator', 'leadout'
            frame_in_section: Frame index within this section
            section_total_frames: Total frames in this section
            frames_until_timecode: For countdown, frames until timecode starts
            frames_since_timecode: For leadout, frames since timecode ended

        Returns:
            Video frame with visual pattern and section indicator
        """
        if self.timecode_system:
            # Use the V2 timecode system to generate the frame with proper visual encoding
            if section_type == 'countdown':
                # Calculate countdown value (5, 4, 3, 2, 1) based on position
                seconds_remaining = int((section_total_frames - frame_in_section) / self.fps) + 1
                countdown_val = min(5, max(1, seconds_remaining))
                display_text = f"COUNTDOWN: {countdown_val}"
                frame = self.timecode_system.generate_frame_image(
                    frame_in_section, display_text, frame_type='countdown',
                    countdown_value=countdown_val, frames_until_timecode=frames_until_timecode or 0
                )
            elif section_type == 'leadout':
                # Calculate count-up value (1, 2, 3, 4, 5) based on position
                seconds_elapsed = int(frame_in_section / self.fps) + 1
                countup_val = min(5, max(1, seconds_elapsed))
                display_text = f"COUNT-UP: {countup_val}"
                frame = self.timecode_system.generate_frame_image(
                    frame_in_section, display_text, frame_type='leadout',
                    countup_value=countup_val, frames_since_timecode=frames_since_timecode or 0
                )
            elif section_type == 'separator':
                display_text = "SEPARATOR"
                frame = self.timecode_system.generate_frame_image(
                    frame_in_section, display_text, frame_type='separator'
                )
            else:  # 'leader' (and 'tail' uses same)
                display_text = "LEADER"
                frame = self.timecode_system.generate_frame_image(
                    frame_in_section, display_text, frame_type='leader'
                )
        else:
            # Fallback: simple labeled frame
            frame = self._create_simple_section_frame(section_type, frame_in_section)

        return frame

    def _create_simple_section_frame(self, section_type, frame_in_section):
        """Create a simple labeled frame when timecode system is unavailable"""
        frame = np.zeros((self.height, self.width, 3), dtype=np.uint8)

        # Section type label
        font = cv2.FONT_HERSHEY_SIMPLEX
        label = section_type.upper()
        cv2.putText(frame, label, (20, 70), font, 2.0, (255, 255, 255), 3)
        cv2.putText(frame, f"Frame: {frame_in_section}", (20, 130), font, 1.0, (200, 200, 200), 2)

        return frame
    
    def generate_pattern_audio(self, num_cycles, output_path):
        """Generate the complete V2 pattern audio with frame-perfect timing for all sections"""
        # Use exact sample calculations to avoid cumulative timing errors
        cycle_samples = int(self.total_cycle_duration * self.sample_rate)
        total_samples = cycle_samples * num_cycles
        audio_data = np.zeros(total_samples, dtype=np.float32)

        # Pre-calculate frame-perfect sample counts for each section
        leader_samples = int(self.leader_duration * self.sample_rate)
        countdown_samples = int(self.countdown_duration * self.sample_rate)
        separator_samples = int(self.separator_duration * self.sample_rate)
        timecode_samples = int(self.timecode_duration * self.sample_rate)
        countup_samples = int(self.countup_duration * self.sample_rate)
        tail_samples = int(self.tail_duration * self.sample_rate)

        # Calculate exact samples per video frame (critical for sync)
        samples_per_video_frame = self.sample_rate / self.fps  # Keep as float for precision

        # Frame counts for each section
        leader_frames = int(self.leader_duration * self.fps)
        countdown_frames = int(self.countdown_duration * self.fps)
        separator_frames = int(self.separator_duration * self.fps)
        timecode_frames = int(self.timecode_duration * self.fps)
        countup_frames = int(self.countup_duration * self.fps)
        tail_frames = int(self.tail_duration * self.fps)

        print(f"V2 Frame-accurate audio timing:")
        print(f"  Samples per video frame: {samples_per_video_frame:.6f}")
        print(f"  Leader frames: {leader_frames} ({leader_samples} samples)")
        print(f"  Countdown frames: {countdown_frames} ({countdown_samples} samples)")
        print(f"  Separator frames: {separator_frames} ({separator_samples} samples)")
        print(f"  Timecode frames: {timecode_frames} ({timecode_samples} samples)")
        print(f"  Count-up frames: {countup_frames} ({countup_samples} samples)")
        print(f"  Tail frames: {tail_frames} ({tail_samples} samples)")

        for cycle in range(num_cycles):
            cycle_start = cycle * cycle_samples
            current_pos = cycle_start

            # Section 1: Leader (10s) - 0xFFFF FSK pattern
            if self.timecode_system:
                self._generate_section_audio(audio_data, current_pos, leader_frames,
                                             samples_per_video_frame, 'leader')
            current_pos += leader_samples

            # Section 2: Countdown (5s) - "11" prefix FSK pattern
            if self.timecode_system:
                for frame_idx in range(countdown_frames):
                    frame_start = current_pos + int(frame_idx * samples_per_video_frame)
                    frame_end = current_pos + int((frame_idx + 1) * samples_per_video_frame)

                    # Calculate countdown value and frames until timecode
                    seconds_remaining = int((countdown_frames - frame_idx) / self.fps) + 1
                    countdown_val = min(5, max(1, seconds_remaining))
                    frames_until = (countdown_frames - frame_idx) + separator_frames

                    frame_audio = self.timecode_system.generate_robust_fsk_audio(
                        frame_idx, frame_type='countdown',
                        countdown_val=countdown_val, frames_count=frames_until
                    )
                    actual_samples = min(len(frame_audio), frame_end - frame_start)
                    audio_data[frame_start:frame_start + actual_samples] = frame_audio[:actual_samples]
            current_pos += countdown_samples

            # Section 3: Separator (1s) - 0x0000 FSK pattern
            if self.timecode_system:
                self._generate_section_audio(audio_data, current_pos, separator_frames,
                                             samples_per_video_frame, 'separator')
            current_pos += separator_samples

            # Section 4: Timecode (30s) - "10" + 12-bit frame + "01" FSK pattern
            if self.timecode_system:
                for frame_idx in range(timecode_frames):
                    frame_start = current_pos + int(frame_idx * samples_per_video_frame)
                    frame_end = current_pos + int((frame_idx + 1) * samples_per_video_frame)
                    frame_end = min(frame_end, current_pos + timecode_samples)

                    if frame_end > frame_start:
                        frame_audio = self.timecode_system.generate_robust_fsk_audio(
                            frame_idx, frame_type='timecode'
                        )
                        actual_samples = min(len(frame_audio), frame_end - frame_start)
                        audio_data[frame_start:frame_start + actual_samples] = frame_audio[:actual_samples]
            else:
                # Fallback: generate simple tone for timecode section
                timecode_tone = self.generate_tone(800, self.timecode_duration)
                audio_data[current_pos:current_pos + len(timecode_tone)] = timecode_tone
            current_pos += timecode_samples

            # Section 5: Separator (1s) - 0x0000 FSK pattern
            if self.timecode_system:
                self._generate_section_audio(audio_data, current_pos, separator_frames,
                                             samples_per_video_frame, 'separator')
            current_pos += separator_samples

            # Section 6: Count-up (5s) - "00" prefix FSK pattern
            if self.timecode_system:
                for frame_idx in range(countup_frames):
                    frame_start = current_pos + int(frame_idx * samples_per_video_frame)
                    frame_end = current_pos + int((frame_idx + 1) * samples_per_video_frame)

                    # Calculate count-up value and frames since timecode
                    seconds_elapsed = int(frame_idx / self.fps) + 1
                    countup_val = min(5, max(1, seconds_elapsed))
                    frames_since = frame_idx + separator_frames

                    frame_audio = self.timecode_system.generate_robust_fsk_audio(
                        frame_idx, frame_type='leadout',
                        countdown_val=countup_val, frames_count=frames_since
                    )
                    actual_samples = min(len(frame_audio), frame_end - frame_start)
                    audio_data[frame_start:frame_start + actual_samples] = frame_audio[:actual_samples]
            current_pos += countup_samples

            # Section 7: Tail (10s) - 0xFFFF FSK pattern (same as leader)
            if self.timecode_system:
                self._generate_section_audio(audio_data, current_pos, tail_frames,
                                             samples_per_video_frame, 'leader')
            current_pos += tail_samples

        # Save audio as WAV
        self.save_audio_wav(audio_data, output_path)

    def _generate_section_audio(self, audio_data, start_pos, num_frames, samples_per_frame, frame_type):
        """
        Generate FSK audio for a section of uniform frame type (leader, separator)

        Args:
            audio_data: Output audio array to fill
            start_pos: Starting sample position
            num_frames: Number of frames in section
            samples_per_frame: Samples per video frame
            frame_type: 'leader' or 'separator'
        """
        for frame_idx in range(num_frames):
            frame_start = start_pos + int(frame_idx * samples_per_frame)
            frame_end = start_pos + int((frame_idx + 1) * samples_per_frame)

            frame_audio = self.timecode_system.generate_robust_fsk_audio(
                frame_idx, frame_type=frame_type
            )
            actual_samples = min(len(frame_audio), frame_end - frame_start)
            audio_data[frame_start:frame_start + actual_samples] = frame_audio[:actual_samples]
    
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
        """Generate metadata for the V2 pattern"""
        duration_seconds = num_cycles * self.total_cycle_duration

        metadata = {
            "pattern_metadata": {
                "generator": "VHS Pattern Generator V2.0 - Robust Calibration Cycle",
                "encoding_version": "V2",
                "timestamp": datetime.now().isoformat(),
                "format": self.format_type,
                "fps": self.fps,
                "resolution": f"{self.width}x{self.height}",
                "duration_seconds": duration_seconds,
                "total_cycles": num_cycles
            },
            "v2_encoding": {
                "bits_per_frame": 16,
                "visual_encoding": {
                    "num_blocks": 16,
                    "block_width_px": 40,
                    "vertical_rows": 3,
                    "strip_height_px": 60,
                    "bit_1_color": "red",
                    "bit_0_color": "blue",
                    "background_color": "mid-gray (128)"
                },
                "audio_encoding": {
                    "freq_0_hz": 400,
                    "freq_1_hz": 800,
                    "pilot_tone_hz": 1200,
                    "type": "FSK with pilot tone"
                },
                "frame_types": {
                    "leader": "0xFFFF (all 1s)",
                    "separator": "0x0000 (all 0s)",
                    "countdown": "'11' + 4-bit countdown + 10-bit frames_until_timecode",
                    "timecode": "'10' + 12-bit frame_number + '01'",
                    "leadout": "'00' + 4-bit countup + 10-bit frames_since_timecode"
                }
            },
            "cycle_structure": {
                "total_cycle_duration": self.total_cycle_duration,
                "sections": [
                    {"section": 1, "name": "leader", "duration": self.leader_duration,
                     "content": "0xFFFF pattern - preparation period"},
                    {"section": 2, "name": "countdown", "duration": self.countdown_duration,
                     "content": "'11' prefix + countdown value + frames until timecode"},
                    {"section": 3, "name": "separator", "duration": self.separator_duration,
                     "content": "0x0000 pattern - transition marker"},
                    {"section": 4, "name": "timecode", "duration": self.timecode_duration,
                     "content": "'10' prefix + 12-bit frame + '01' suffix"},
                    {"section": 5, "name": "separator", "duration": self.separator_duration,
                     "content": "0x0000 pattern - transition marker"},
                    {"section": 6, "name": "countup", "duration": self.countup_duration,
                     "content": "'00' prefix + count-up value + frames since timecode"},
                    {"section": 7, "name": "tail", "duration": self.tail_duration,
                     "content": "0xFFFF pattern - cycle complete"}
                ]
            },
            "audio_parameters": {
                "sample_rate": self.sample_rate,
                "channels": self.audio_channels,
                "encoding": "V2 robust FSK" if self.timecode_system else "fallback_tone"
            },
            "usage_instructions": {
                "purpose": "VHS calibration with machine-readable lead-in/lead-out structure",
                "workflow": [
                    "1. Record this MP4 to VHS tape via DVD burner or capture card",
                    "2. Capture VHS back with Domesday Duplicator + audio interface",
                    "3. Run vhs-decode to produce TBC output with clock synchronization",
                    "4. Run timecode analyzer to detect state machine transitions",
                    "5. Use multi-point sampling during timecode section for offset calculation",
                    "6. Apply calibration offset to future captures"
                ],
                "decoding_notes": [
                    "Leader/Tail (0xFFFF) indicates preparation or cycle boundary",
                    "Countdown ('11' prefix) indicates timecode starting soon",
                    "Separator (0x0000) marks section boundaries",
                    "Timecode ('10' prefix + '01' suffix) contains actual frame numbers",
                    "Count-up ('00' prefix) indicates timecode section has ended"
                ]
            }
        }

        metadata_file = output_file.replace('.mp4', '_metadata.json')
        with open(metadata_file, 'w') as f:
            json.dump(metadata, f, indent=2)

        return metadata_file

def main():
    parser = argparse.ArgumentParser(
        description='Generate VHS V2 calibration pattern with 62-second cycles',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
V2 Calibration Cycle Structure (62 seconds):
  1. Leader     (10s) - 0xFFFF pattern, preparation period
  2. Countdown  (5s)  - '11' prefix + countdown value
  3. Separator  (1s)  - 0x0000 pattern, transition marker
  4. Timecode   (30s) - '10' prefix + 12-bit frame + '01'
  5. Separator  (1s)  - 0x0000 pattern, transition marker
  6. Count-up   (5s)  - '00' prefix + count-up value
  7. Tail       (10s) - 0xFFFF pattern, cycle complete

V2 Encoding Features:
  - 16-bit frames with marker-based validation
  - 400/800 Hz FSK audio (optimized for VHS linear audio)
  - Red/blue visual encoding for color-based detection
  - 3 vertical rows for redundancy
  - Machine-readable lead-in/lead-out structure
""")
    parser.add_argument('--cycles', type=int, default=10,
                        help='Number of 62-second cycles (default: 10)')
    parser.add_argument('--format', choices=['PAL', 'NTSC'], default='PAL',
                        help='Video format (default: PAL)')
    parser.add_argument('--output', required=True,
                        help='Output MP4 file path')

    args = parser.parse_args()

    try:
        # Create generator
        generator = VHSPatternGenerator(format_type=args.format)

        # Generate pattern
        output_file = generator.generate_pattern_video(args.cycles, args.output)

        # Generate metadata
        metadata_file = generator.generate_metadata(args.cycles, output_file)

        duration_minutes = (args.cycles * 62) / 60

        print(f"\nV2 Pattern generation completed!")
        print(f"Video file: {output_file}")
        print(f"Metadata: {metadata_file}")
        print(f"Duration: {args.cycles} cycles x 62s = {duration_minutes:.1f} minutes")

        # Show file info
        if os.path.exists(output_file):
            size_mb = os.path.getsize(output_file) / (1024*1024)
            print(f"File size: {size_mb:.1f} MB")

        return 0

    except Exception as e:
        print(f"Error generating pattern: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())
