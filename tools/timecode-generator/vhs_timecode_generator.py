#!/usr/bin/env python3
"""
VHS Timecode Generator for Precise Audio/Video Alignment - ROBUST FSK VERSION

This script generates test patterns with frame-accurate timecode for VHS calibration.
Each frame contains a unique identifier that is encoded in both video and audio,
allowing for microsecond-accurate alignment after capture.

Features:
- Visual frame counter with high contrast for VHS reliability
- ROBUST audio timecode encoding using improved FSK with wide frequency separation
- PAL/NTSC support with proper frame rates
- Enhanced error correction and multi-method voting for VHS tape quality
- Memory-efficient processing for any duration (seconds to hours)
- Colored corner markers for precise frame alignment
- MONO audio encoding to eliminate stereo channel confusion

Usage:
    python3 vhs_timecode_generator.py --duration 60 --format PAL --output calibration_timecode.mp4
"""

import cv2
import numpy as np
import subprocess
import argparse
import os
import sys
from datetime import datetime, timedelta
import json
import tempfile
from shared_timecode_robust import SharedTimecodeRobust

class VHSTimecodeGenerator(SharedTimecodeRobust):
    def __init__(self, format_type="PAL", width=720, height=576):
        """
        Initialize VHS timecode generator
        
        Args:
            format_type: "PAL" (25fps) or "NTSC" (29.97fps)
            width: Video width (720 for VHS standard)
            height: Video height (576 for PAL, 480 for NTSC)
        """
        # Initialize base class
        super().__init__(format_type, width, height)
        
        # Chunk size for memory-efficient audio processing (10 seconds worth)
        self.audio_chunk_seconds = 10
        self.audio_chunk_frames = int(self.audio_chunk_seconds * self.fps)
    
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
        format_text = f"{self.format_type} {self.fps}fps"
        (fw, fh), _ = cv2.getTextSize(format_text, font, 0.7, 2)
        cv2.putText(frame, format_text, (self.width - fw - 20, 70), font, 
                   0.7, self.text_color, 2)
        
        # Add machine-readable patterns for extra reliability
        self._add_sync_patterns(frame, frame_number)
        
        return frame
    
    def _add_sync_patterns(self, frame, frame_number):
        """Add machine-readable sync patterns to frame"""
        # Add binary representation as visual blocks (top edge)
        binary = format(frame_number, '032b')  # 32-bit binary
        
        # Position binary blocks
        available_width = self.width - 80  # Total width minus 40px corners
        block_width = available_width // 32
        start_offset = 40  # Start after left corner
        
        for i, bit in enumerate(binary):
            x_start = start_offset + (i * block_width)
            x_end = min(x_start + block_width, self.width - 40)
            
            # White for 1, dark gray for 0 (still visible)
            color = (255, 255, 255) if bit == '1' else (64, 64, 64)
            cv2.rectangle(frame, (x_start, 0), (x_end, 20), color, -1)
        
        # Add sync markers in corners for frame detection
        marker_size = 40
        marker_color = (255, 255, 255)
        
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
        """Generate audio timecode for a frame using ROBUST FSK system"""
        # Use the robust FSK audio generation
        mono_audio = self.generate_robust_fsk_audio(frame_number)
        
        # For backward compatibility with the chunked processing system,
        # return the mono audio as both left and right channels
        # The combining system will handle the mono output correctly
        return mono_audio, mono_audio
    
    def frame_to_timecode(self, frame_number):
        """Convert frame number to timecode string"""
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
    
    def generate_test_video(self, duration_seconds, output_path):
        """Generate complete timecode test video with memory-efficient audio processing"""
        total_frames = int(duration_seconds * self.fps)
        
        print(f"Generating {self.format_type} timecode video:")
        print(f"  Duration: {duration_seconds} seconds")
        print(f"  Total frames: {total_frames}")
        print(f"  Frame rate: {self.fps} fps")
        print(f"  Resolution: {self.width}x{self.height}")
        print(f"  Output: {output_path}")
        print(f"  Audio chunk size: {self.audio_chunk_seconds} seconds")
        
        # Create temporary files for video and audio
        temp_video = output_path.replace('.mp4', '_temp_video.mp4')
        temp_audio = output_path.replace('.mp4', '_temp_audio.wav')
        metadata_file = output_path.replace('.mp4', '_metadata.json')
        
        try:
            # Generate video frames
            self._generate_video_stream(total_frames, duration_seconds, temp_video)
            
            # Generate audio stream efficiently
            self._generate_audio_stream_efficient(total_frames, duration_seconds, temp_audio)
            
            # Combine video and audio
            self._combine_av_streams(temp_video, temp_audio, output_path)
            
            # Generate metadata file
            self._generate_metadata(total_frames, duration_seconds, metadata_file)
            
            print(f"\nTimecode video generated successfully!")
            print(f"Video file: {output_path}")
            print(f"Metadata: {metadata_file}")
            
        finally:
            # Clean up temporary files
            for temp_file in [temp_video, temp_audio]:
                if os.path.exists(temp_file):
                    os.remove(temp_file)
    
    def _generate_video_stream(self, total_frames, duration_seconds, output_path):
        """Generate video stream with OpenCV"""
        print("Generating video frames...")
        
        # Define codec and create VideoWriter
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(output_path, fourcc, self.fps, (self.width, self.height))
        
        if not out.isOpened():
            raise RuntimeError("Failed to open video writer")
        
        try:
            for frame_num in range(total_frames):
                if frame_num % 250 == 0:  # Progress every 10 seconds
                    print(f"  Frame {frame_num}/{total_frames} ({frame_num/total_frames*100:.1f}%)")
                
                timecode_str = self.frame_to_timecode(frame_num)
                frame_image = self.generate_frame_image(frame_num, timecode_str)
                
                out.write(frame_image)
            
        finally:
            out.release()
        
        print("Video frames generated.")
    
    def _generate_audio_stream_efficient(self, total_frames, duration_seconds, output_path):
        """Generate audio stream efficiently in chunks to avoid memory issues"""
        print("Generating audio timecode efficiently...")
        
        frame_duration = 1.0 / self.fps
        
        # Create temporary WAV file incrementally using sox
        with tempfile.NamedTemporaryFile(suffix='.raw', delete=False) as temp_raw:
            temp_raw_path = temp_raw.name
        
        try:
            # Process audio in chunks
            frames_processed = 0
            chunk_count = 0
            
            while frames_processed < total_frames:
                # Calculate chunk boundaries
                frames_in_chunk = min(self.audio_chunk_frames, total_frames - frames_processed)
                chunk_count += 1
                
                print(f"  Processing audio chunk {chunk_count} ({frames_processed}-{frames_processed + frames_in_chunk - 1})")
                
                # Generate audio for this chunk
                chunk_audio = []
                
                for i in range(frames_in_chunk):
                    frame_num = frames_processed + i
                    
                    # Get mono audio from robust FSK system
                    mono_audio, _ = self.generate_audio_timecode(frame_num, frame_duration)
                    chunk_audio.extend(mono_audio)
                
                # Convert chunk to numpy array
                mono_channel = np.array(chunk_audio, dtype=np.float32)
                
                # Normalize chunk to prevent clipping
                max_val = np.max(np.abs(mono_channel))
                if max_val > 0:
                    mono_channel = mono_channel / max_val * 0.9
                
                # Append to raw file (mono)
                with open(temp_raw_path, 'ab') as f:  # append binary mode
                    mono_channel.astype(np.float32).tofile(f)
                
                frames_processed += frames_in_chunk
                
                # Clear memory
                del chunk_audio, mono_channel
            
            # Convert raw file to WAV using sox (mono audio)
            print("  Converting raw audio to WAV format...")
            cmd = [
                'sox', '-t', 'f32', '-r', str(self.sample_rate), '-c', '1',
                temp_raw_path, output_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                raise RuntimeError(f"Sox conversion failed: {result.stderr}")
            
        finally:
            # Clean up temporary raw file
            if os.path.exists(temp_raw_path):
                os.remove(temp_raw_path)
        
        print("Audio timecode generated efficiently.")
    
    def _combine_av_streams(self, video_path, audio_path, output_path):
        """Combine video and audio using ffmpeg with progress monitoring"""
        print("Combining audio and video...")
        print(f"  Input video: {video_path}")
        print(f"  Input audio: {audio_path}")
        print(f"  Output file: {output_path}")
        
        # Try mpeg4 first (since libx264 isn't available on your system)
        codec_options = [
            {
                'video_codec': 'mpeg4', 
                'audio_codec': 'mp3',
                'extra_args': ['-q:v', '3']  # Good quality for mpeg4
            },
            {
                'video_codec': 'ffv1',  # Lossless codec, always available
                'audio_codec': 'pcm_s16le',
                'extra_args': []
            }
        ]
        
        for i, codec_option in enumerate(codec_options):
            cmd = [
                'ffmpeg', '-y',  # Overwrite output
                '-progress', 'pipe:1',  # Progress to stdout
                '-i', video_path,  # Video input
                '-i', audio_path,  # Audio input
                '-c:v', codec_option['video_codec'],
                '-c:a', codec_option['audio_codec'],
                '-b:a', '192k',     # Audio bitrate
            ] + codec_option['extra_args'] + [output_path]
            
            try:
                print(f"  Trying {codec_option['video_codec']} codec...")
                print(f"    This may take several minutes for long videos. Progress will be shown below:")
                
                # Run ffmpeg with real-time output
                process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, 
                                         universal_newlines=True, bufsize=1)
                
                # Monitor progress
                while True:
                    output = process.stdout.readline()
                    if output == '' and process.poll() is not None:
                        break
                    if output:
                        # Parse ffmpeg progress output
                        if 'out_time=' in output:
                            time_str = output.split('out_time=')[1].split()[0]
                            print(f"    Progress: {time_str}", end='\r')
                        elif 'progress=' in output and 'end' in output:
                            print(f"\n    FFmpeg encoding completed.")
                
                # Get final result
                stderr_output = process.stderr.read()
                return_code = process.poll()
                
                if return_code == 0:
                    print(f"Audio/video combination complete using {codec_option['video_codec']}.")
                    return
                else:
                    if i == len(codec_options) - 1:  # Last attempt
                        print(f"\nFFmpeg stderr: {stderr_output}")
                        raise RuntimeError(f"FFmpeg failed with all codecs. Last error: {stderr_output}")
                    else:
                        print(f"\nCodec {codec_option['video_codec']} failed, trying next...")
                        print(f"Error: {stderr_output}")
                        
            except Exception as e:
                if i == len(codec_options) - 1:  # Last attempt
                    raise RuntimeError(f"FFmpeg failed: {e}")
                else:
                    print(f"Exception with {codec_option['video_codec']}: {e}, trying next codec...")
    
    def _generate_metadata(self, total_frames, duration_seconds, metadata_path):
        """Generate metadata file with timing information"""
        # Use the robust system's metadata generation
        metadata = self.generate_metadata(total_frames, duration_seconds)
        
        # Add generator-specific information
        metadata["timecode_metadata"]["memory_efficient"] = True
        metadata["timecode_metadata"]["audio_chunk_seconds"] = self.audio_chunk_seconds
        
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)


def main():
    parser = argparse.ArgumentParser(description='Generate VHS timecode test pattern')
    parser.add_argument('--duration', type=int, default=60,
                       help='Duration in seconds (default: 60)')
    parser.add_argument('--format', choices=['PAL', 'NTSC'], default='PAL',
                       help='Video format (default: PAL)')
    parser.add_argument('--output', type=str, default='vhs_timecode_test.mp4',
                       help='Output file path (default: vhs_timecode_test.mp4)')
    parser.add_argument('--width', type=int, default=720,
                       help='Video width (default: 720)')
    parser.add_argument('--height', type=int, default=None,
                       help='Video height (default: 576 for PAL, 480 for NTSC)')
    
    args = parser.parse_args()
    
    # Validate dependencies
    missing_deps = []
    try:
        import cv2
    except ImportError:
        missing_deps.append('opencv-python')
    
    # Check for ffmpeg
    try:
        subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        missing_deps.append('ffmpeg')
    
    # Check for sox
    try:
        subprocess.run(['sox', '--version'], capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        missing_deps.append('sox')
    
    if missing_deps:
        print("Missing dependencies:")
        for dep in missing_deps:
            print(f"  - {dep}")
        print("\nInstall with:")
        print("  pip install opencv-python")
        print("  # Install ffmpeg and sox via your system package manager")
        sys.exit(1)
    
    # Generate timecode video
    generator = VHSTimecodeGenerator(
        format_type=args.format,
        width=args.width,
        height=args.height
    )
    
    generator.generate_test_video(args.duration, args.output)


if __name__ == "__main__":
    main()
