import subprocess
import os
import cv2
import numpy as np


def analyze_test_pattern_timing(aligned_audio_file, video_file):
    """
    Analyze the synchronized audio and video files using multi-cycle detection.
    Excludes first and last cycles to account for human timing errors.
    Returns the calculated timing offset in seconds.
    """
    try:
        print("\n=== MULTI-CYCLE TIMING ANALYSIS ===")
        print("Analyzing both audio and video for multiple test pattern cycles...")
        
        # Find all audio tone starts
        audio_starts = find_all_audio_tone_starts(aligned_audio_file)
        if len(audio_starts) == 0:
            print(" No audio tone cycles detected")
            return None
            
        # Find all video pattern starts  
        video_starts = find_all_video_pattern_starts(video_file)
        if len(video_starts) == 0:
            print(" No video pattern cycles detected")
            return None
            
        print(f"Found {len(audio_starts)} audio cycles, {len(video_starts)} video cycles")
        
        # Remove first 2 and last 2 cycles (human error and startup/shutdown compensation)
        if len(audio_starts) > 4:
            audio_starts = audio_starts[2:-2]
            print(f"Keeping middle {len(audio_starts)} audio cycles (removed first/last 2)")
        elif len(audio_starts) > 2:
            audio_starts = audio_starts[1:-1]
            print(f"Keeping middle {len(audio_starts)} audio cycles (removed first/last 1 - insufficient cycles for 2)")
        
        if len(video_starts) > 4:
            video_starts = video_starts[2:-2]
            print(f"Keeping middle {len(video_starts)} video cycles (removed first/last 2)")
        elif len(video_starts) > 2:
            video_starts = video_starts[1:-1]
            print(f"Keeping middle {len(video_starts)} video cycles (removed first/last 1 - insufficient cycles for 2)")
        
        # Find best matching pairs by timing proximity instead of index pairing
        offsets = []
        paired_video_indices = set()  # Track which video patterns we've used
        
        print(f"\nCalculating offsets by finding closest timing matches:")
        print("-" * 50)
        
        for i, audio_time in enumerate(audio_starts):
            # Find the closest video pattern that hasn't been used yet
            best_video_idx = None
            best_time_diff = float('inf')
            
            for j, video_time in enumerate(video_starts):
                if j in paired_video_indices:
                    continue  # Already used this video pattern
                    
                time_diff = abs(audio_time - video_time)
                if time_diff < best_time_diff:
                    best_time_diff = time_diff
                    best_video_idx = j
            
            if best_video_idx is not None and best_time_diff < 1.0:  # Max 1s apart
                video_time = video_starts[best_video_idx]
                offset = audio_time - video_time
                offsets.append(offset)
                paired_video_indices.add(best_video_idx)
                print(f"Pair {len(offsets)}: Audio {audio_time:.3f}s - Video {video_time:.3f}s = {offset:+.3f}s")
            else:
                print(f"Skip: Audio {audio_time:.3f}s - no close video match (closest: {best_time_diff:.3f}s apart)")
        
        if len(offsets) == 0:
            print(" No valid timing pairs found")
            return None
        
        # Calculate statistics
        import numpy as np
        mean_offset = np.mean(offsets)
        std_offset = np.std(offsets)
        
        # Convert to frame measurements (assume PAL 25fps as default, but detect from video if possible)
        fps = 25.0  # Default PAL frame rate
        try:
            import cv2
            cap = cv2.VideoCapture(video_file)
            if cap.isOpened():
                detected_fps = cap.get(cv2.CAP_PROP_FPS)
                if detected_fps > 0:
                    fps = detected_fps
                cap.release()
        except:
            pass  # Use default fps
        
        # Calculate frame offset
        frame_offset = mean_offset * fps
        frame_std = std_offset * fps
        
        print("-" * 50)
        print(f"TIMING STATISTICS:")
        print(f"  Mean offset: {mean_offset:+.6f}s ({frame_offset:+.2f} frames @ {fps:.2f}fps)")
        print(f"  Std deviation: {std_offset:.6f}s ({frame_std:.2f} frames)")
        print(f"  Frame precision: {'Sub-frame' if abs(frame_offset) < 0.5 else 'Multi-frame'} offset")
        print(f"  Consistency: {'Good' if std_offset < 0.050 else 'Poor'} (std < 50ms or ~{1.25:.1f} frames)")
        print(f"  Pairs analyzed: {len(offsets)}")
        
        # Add interpretation
        if abs(frame_offset) < 0.5:
            print(f"  Interpretation: Sub-frame precision - very good sync")
        elif abs(frame_offset) < 1.0:
            print(f"  Interpretation: Less than 1 frame offset - acceptable sync")
        elif abs(frame_offset) < 2.0:
            print(f"  Interpretation: 1-2 frame offset - noticeable in critical content")
        else:
            print(f"  Interpretation: Multi-frame offset - correction recommended")
        
        return mean_offset
        
    except Exception as e:
        print(f"Error during multi-cycle analysis: {e}")
        import traceback
        traceback.print_exc()
        return None



def find_tone_start_time(audio_file):
    """
    Use Sox to detect the start time of the 1kHz tone in the audio file.
    Returns the start time in seconds or None if not detected.
    """
    try:
        # Method 1: Use Sox to find the first significant audio event
        # This looks for the first moment when audio level exceeds a threshold
        print("Searching for tone start using amplitude threshold detection...")
        
        # First, get overall audio statistics
        stat_command = ['sox', audio_file, '-n', 'stat']
        stat_result = subprocess.run(stat_command, capture_output=True, text=True)
        
        if stat_result.returncode != 0:
            print(f"Could not analyse audio file: {stat_result.stderr}")
            return None
            
        # Parse maximum amplitude from statistics
        max_amplitude = None
        for line in stat_result.stderr.splitlines():
            if "Maximum amplitude" in line:
                try:
                    max_amplitude = float(line.split()[-1])
                    break
                except (ValueError, IndexError):
                    continue
        
        if max_amplitude is None or max_amplitude < 0.01:  # Very low signal
            print("Audio signal too weak or not found")
            return None
            
        print(f"Maximum amplitude detected: {max_amplitude:.4f}")
        
        # Set threshold at 10% of maximum amplitude
        threshold = max_amplitude * 0.1
        
        # Method 2: Use FFmpeg to find first audio event above threshold
        # This is more reliable for finding the actual start time
        ffmpeg_command = [
            'ffmpeg', '-i', audio_file, '-af', 
            f'silencedetect=noise=-{20*np.log10(threshold):.1f}dB:duration=0.1',
            '-f', 'null', '-'
        ]
        
        print(f"Running FFmpeg silence detection...")
        ffmpeg_result = subprocess.run(ffmpeg_command, capture_output=True, text=True)
        
        # Parse FFmpeg output for silence detection
        for line in ffmpeg_result.stderr.splitlines():
            if "silence_end" in line:
                try:
                    # Extract time from something like: [silencedetect @ 0x...] silence_end: 2.034
                    parts = line.split("silence_end:")
                    if len(parts) > 1:
                        time_str = parts[1].split()[0]
                        tone_start = float(time_str)
                        print(f"Detected tone start at: {tone_start:.3f} seconds")
                        return tone_start
                except (ValueError, IndexError):
                    continue
        
        # Fallback: assume tone starts very early if no silence detected
        print("No clear silence/tone boundary detected, assuming tone starts early")
        return 0.1  # Assume tone starts 100ms in
        
    except Exception as e:
        print(f"Error detecting tone start in audio: {e}")
        import traceback
        traceback.print_exc()

    return None


def find_pattern_start_time(video_file):
    """
    Use OpenCV to detect the start time of the test pattern in the video file.
    Returns the start time in seconds or None if not detected.
    """
    try:
        print("Opening video file for pattern analysis...")
        # Open the video file
        cap = cv2.VideoCapture(video_file)
        if not cap.isOpened():
            print("Failed to open video file.")
            return None

        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration = total_frames / fps
        
        print(f"Video info: {fps} fps, {total_frames} frames, {duration:.2f} seconds")
        
        frame_count = 0
        pattern_found = False
        pattern_start_frame = None
        
        # Sample frames more efficiently - check every 10th frame initially
        sample_interval = 10
        brightness_history = []
        
        print("Analyzing video frames for pattern detection...")
        
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break

            frame_count += 1
            
            # Skip frames for efficiency, but analyze every 10th frame
            if frame_count % sample_interval != 0:
                continue
            
            # Calculate frame brightness/activity
            brightness = calculate_frame_brightness(frame)
            brightness_history.append((frame_count, brightness))
            
            # Print progress every 250 frames (10 seconds at 25fps)
            if frame_count % 250 == 0:
                time_pos = frame_count / fps
                print(f"  Analyzed {frame_count}/{total_frames} frames ({time_pos:.1f}s), brightness: {brightness:.3f}")
        
        cap.release()
        
        # Analyze brightness history to find pattern transitions
        if len(brightness_history) < 5:
            print("Not enough frames analyzed for pattern detection")
            return None
            
        print(f"Analyzed {len(brightness_history)} sample frames")
        
        # Look for significant brightness changes that indicate pattern start
        pattern_start_frame = detect_pattern_transitions(brightness_history, fps)
        
        if pattern_start_frame is not None:
            # Calculate the start time
            start_time = pattern_start_frame / fps
            print(f"Detected video pattern start at frame {pattern_start_frame} ({start_time:.3f}s)")
            return start_time
        else:
            print("Could not detect clear pattern transitions in video")
            # Fallback: assume pattern starts early in the video
            fallback_time = 0.1
            print(f"Using fallback pattern start time: {fallback_time:.3f}s")
            return fallback_time

    except Exception as e:
        print(f"Error detecting pattern start in video: {e}")
        import traceback
        traceback.print_exc()

    return None


def calculate_frame_brightness(frame):
    """
    Calculate the brightness/luminance of a video frame.
    Returns a value between 0 and 1.
    """
    if frame is None:
        return 0.0
    
    # Convert to grayscale if needed
    if len(frame.shape) == 3:
        # Convert BGR to grayscale
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    else:
        gray = frame
    
    # Calculate mean brightness, normalized to 0-1
    mean_brightness = np.mean(gray) / 255.0
    return mean_brightness


def detect_pattern_transitions(brightness_history, fps):
    """
    Analyze brightness history to detect pattern transitions.
    Look for the pattern of: low -> high -> low (indicating pattern appearance)
    Returns the frame number where the pattern likely starts, or None.
    """
    if len(brightness_history) < 10:
        return None
    
    print("Analyzing brightness transitions...")
    
    # Extract just the brightness values
    brightnesses = [b[1] for b in brightness_history]
    frames = [b[0] for b in brightness_history]
    
    # Calculate statistics
    mean_brightness = np.mean(brightnesses)
    std_brightness = np.std(brightnesses)
    min_brightness = np.min(brightnesses)
    max_brightness = np.max(brightnesses)
    
    print(f"Brightness stats: mean={mean_brightness:.3f}, std={std_brightness:.3f}, range={min_brightness:.3f}-{max_brightness:.3f}")
    
    # If there's very little variation, the video might be mostly static
    if std_brightness < 0.05:
        print("Very little brightness variation detected - possibly static video")
        # Look for any small changes
        threshold = mean_brightness + (std_brightness * 0.5)
    else:
        # Use a threshold based on the brightness distribution
        threshold = mean_brightness + (std_brightness * 1.0)
    
    print(f"Using brightness threshold: {threshold:.3f}")
    
    # Look for the first significant brightness increase (pattern appears)
    for i in range(1, len(brightnesses)):
        prev_brightness = brightnesses[i-1]
        curr_brightness = brightnesses[i]
        
        # Check if we cross the threshold from below
        if prev_brightness < threshold and curr_brightness >= threshold:
            pattern_frame = frames[i]
            frame_time = pattern_frame / fps
            print(f"Found brightness increase at frame {pattern_frame} ({frame_time:.3f}s): {prev_brightness:.3f} -> {curr_brightness:.3f}")
            return pattern_frame
    
    # If no clear threshold crossing, look for the maximum brightness point
    max_idx = np.argmax(brightnesses)
    if max_idx > 0:
        pattern_frame = frames[max_idx]
        frame_time = pattern_frame / fps
        print(f"Using maximum brightness point at frame {pattern_frame} ({frame_time:.3f}s): {brightnesses[max_idx]:.3f}")
        return pattern_frame
    
    return None


def find_all_audio_tone_starts(audio_file):
    """
    Find all audio tone start times using FFmpeg silence detection.
    Returns a list of start times in seconds.
    """
    print("Detecting all audio tone start times...")
    
    # Get audio statistics first
    stat_result = subprocess.run(['sox', audio_file, '-n', 'stat'], capture_output=True, text=True)
    max_amplitude = None
    for line in stat_result.stderr.splitlines():
        if 'Maximum amplitude' in line:
            max_amplitude = float(line.split()[-1])
            break
    
    if max_amplitude is None:
        print("Could not determine audio amplitude")
        return []
    
    print(f"Audio max amplitude: {max_amplitude:.4f}")
    
    # Try multiple threshold levels to find the best one
    threshold_levels = [0.05, 0.10, 0.15, 0.20]  # 5%, 10%, 15%, 20%
    
    for threshold_pct in threshold_levels:
        threshold = max_amplitude * threshold_pct
        
        # Use FFmpeg to detect all silence periods with more sensitive settings
        ffmpeg_cmd = [
            'ffmpeg', '-i', audio_file, '-af',
            f'silencedetect=noise=-{20*np.log10(threshold):.1f}dB:duration=0.1',  # Shorter duration
            '-f', 'null', '-'
        ]
        
        result = subprocess.run(ffmpeg_cmd, capture_output=True, text=True)
        
        tone_starts = []
        
        for line in result.stderr.splitlines():
            if 'silence_end' in line:
                try:
                    parts = line.split('silence_end:')
                    if len(parts) > 1:
                        time_val = float(parts[1].split()[0])
                        tone_starts.append(time_val)
                except (ValueError, IndexError):
                    continue
        
        print(f"Threshold {threshold_pct*100:.0f}% ({threshold:.4f}): Found {len(tone_starts)} tone starts")
        
        # If we found a reasonable number of tones (4-10 for 15 seconds), use this threshold
        if 4 <= len(tone_starts) <= 10:
            print(f"Using threshold {threshold_pct*100:.0f}% - found good number of cycles")
            print(f"Tone starts: {[f'{t:.3f}s' for t in tone_starts]}")
            return tone_starts
    
    # If no threshold worked well, try the most permissive approach
    print("No automatic threshold worked, trying manual approach...")
    
    # Very sensitive detection
    ffmpeg_cmd = [
        'ffmpeg', '-i', audio_file, '-af',
        'silencedetect=noise=-50dB:duration=0.05',  # Very low threshold, very short duration
        '-f', 'null', '-'
    ]
    
    result = subprocess.run(ffmpeg_cmd, capture_output=True, text=True)
    
    tone_starts = []
    
    for line in result.stderr.splitlines():
        if 'silence_end' in line:
            try:
                parts = line.split('silence_end:')
                if len(parts) > 1:
                    time_val = float(parts[1].split()[0])
                    tone_starts.append(time_val)
            except (ValueError, IndexError):
                continue
    
    print(f"Manual approach found {len(tone_starts)} tone starts: {[f'{t:.3f}s' for t in tone_starts[:10]]}{'...' if len(tone_starts) > 10 else ''}")
    return tone_starts


def find_all_video_pattern_starts(video_file, duration=None):
    """
    Find all video pattern ON transitions within the specified duration.
    If duration is None, analyzes the entire video file.
    Returns a list of start times in seconds.
    """
    print("Detecting all video pattern start times...")
    
    cap = cv2.VideoCapture(video_file)
    if not cap.isOpened():
        return []
    
    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    
    if duration is None:
        # Use entire video duration
        max_frames = total_frames
        actual_duration = total_frames / fps
        print(f"Analyzing entire video: {actual_duration:.1f} seconds ({total_frames} frames at {fps:.1f} fps)")
    else:
        # Use specified duration
        max_frames = min(int(duration * fps), total_frames)
        print(f"Analyzing first {duration:.1f} seconds of video ({max_frames} frames at {fps:.1f} fps)")
    
    # Sample every frame for first analysis
    brightnesses = []
    
    for frame_num in range(max_frames):
        ret, frame = cap.read()
        if not ret:
            break
            
        if len(frame.shape) == 3:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        else:
            gray = frame
        brightness = np.mean(gray) / 255.0
        time_pos = frame_num / fps
        brightnesses.append((time_pos, brightness))
    
    cap.release()
    
    if len(brightnesses) < 100:
        return []
    
    # Calculate threshold for ON/OFF detection
    all_brightness = [b[1] for b in brightnesses]
    mean_brightness = np.mean(all_brightness)
    threshold = mean_brightness + 0.05  # 5% above mean
    
    print(f"Brightness threshold for pattern detection: {threshold:.4f}")
    
    # Find all transitions from OFF to ON
    pattern_starts = []
    in_pattern = False
    
    for i, (time_pos, brightness) in enumerate(brightnesses):
        if not in_pattern and brightness > threshold:
            # Transition from OFF to ON
            pattern_starts.append(time_pos)
            in_pattern = True
            if len(pattern_starts) <= 10:  # Only print first 10
                print(f"  Pattern ON at {time_pos:.3f}s (brightness: {brightness:.4f})")
        elif in_pattern and brightness <= threshold:
            # Transition from ON to OFF
            in_pattern = False
    
    print(f"Found {len(pattern_starts)} pattern starts: {[f'{t:.3f}s' for t in pattern_starts[:10]]}{'...' if len(pattern_starts) > 10 else ''}")
    return pattern_starts


def detect_test_pattern(frame):
    """
    Analyze the video frame to detect if it contains the test pattern.
    Return True if found, False otherwise.
    """
    # Dummy function: Real implementation needed
    # For simplicity, return True for the first few frames
    return True if frame is not None and np.mean(frame) > 128 else False

