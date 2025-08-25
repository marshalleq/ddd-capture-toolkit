#!/usr/bin/env python3
"""
VHS Decode Segment Configuration Module
Handles configuration and management of decode segments for testing purposes
"""

import os
import json
from datetime import datetime

def parse_time_to_seconds(time_str):
    """Convert HH:MM:SS or MM:SS to seconds"""
    if not time_str or time_str.strip() == "":
        return 0
    
    parts = time_str.strip().split(':')
    if len(parts) == 2:  # MM:SS
        minutes, seconds = map(int, parts)
        return minutes * 60 + seconds
    elif len(parts) == 3:  # HH:MM:SS
        hours, minutes, seconds = map(int, parts)
        return hours * 3600 + minutes * 60 + seconds
    else:
        raise ValueError(f"Invalid time format: {time_str}. Use HH:MM:SS or MM:SS")

def seconds_to_time(seconds):
    """Convert seconds to HH:MM:SS format"""
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    else:
        return f"{minutes:02d}:{secs:02d}"

def load_segment_config():
    """Load segment configuration from file"""
    config_file = "config/capture_segment.json"
    try:
        if os.path.exists(config_file):
            with open(config_file, 'r') as f:
                config = json.load(f)
                # Validate required fields
                if config.get('enabled', False) and all(key in config for key in 
                    ['start_time', 'duration', 'start_frame_pal', 'frame_count_pal', 
                     'start_frame_ntsc', 'frame_count_ntsc']):
                    return config
    except Exception as e:
        print(f"Warning: Could not load segment config: {e}")
    return None

def save_segment_config(start_time, duration, description=None):
    """Save segment configuration with frame calculations"""
    
    # Parse time strings
    try:
        start_seconds = parse_time_to_seconds(start_time)
        duration_seconds = parse_time_to_seconds(duration)
    except ValueError as e:
        print(f"Error parsing time: {e}")
        return False
    
    if start_seconds < 0 or duration_seconds <= 0:
        print("Error: Start time must be >= 0 and duration must be > 0")
        return False
    
    # Calculate frame numbers for both systems
    start_frame_pal = int(start_seconds * 25)
    frame_count_pal = int(duration_seconds * 25)
    start_frame_ntsc = int(start_seconds * 29.97)
    frame_count_ntsc = int(duration_seconds * 29.97)
    
    # Calculate end times
    end_seconds = start_seconds + duration_seconds
    end_time = seconds_to_time(end_seconds)
    
    if not description:
        description = f"{duration} from {start_time}"
    
    config = {
        "enabled": True,
        "segment_type": "time_range",
        "start_time": start_time,
        "duration": duration,
        "end_time": end_time,
        "start_frame_pal": start_frame_pal,
        "frame_count_pal": frame_count_pal,
        "start_frame_ntsc": start_frame_ntsc,
        "frame_count_ntsc": frame_count_ntsc,
        "description": description,
        "created": datetime.now().isoformat()
    }
    
    # Ensure config directory exists
    os.makedirs("config", exist_ok=True)
    
    try:
        with open("config/capture_segment.json", 'w') as f:
            json.dump(config, f, indent=2)
        return True
    except Exception as e:
        print(f"Error saving segment config: {e}")
        return False

def toggle_segment_enabled(enable=None):
    """Enable or disable segment mode while preserving configuration"""
    config_file = "config/capture_segment.json"
    try:
        if os.path.exists(config_file):
            # Load existing config
            with open(config_file, 'r') as f:
                config = json.load(f)
            
            # Toggle or set enabled state
            if enable is None:
                config['enabled'] = not config.get('enabled', False)
            else:
                config['enabled'] = enable
            
            # Save updated config
            with open(config_file, 'w') as f:
                json.dump(config, f, indent=2)
            
            return config['enabled']
        else:
            print("No segment configuration found to enable/disable")
            return False
    except Exception as e:
        print(f"Error toggling segment config: {e}")
        return False

def clear_segment_config():
    """Completely remove segment configuration file"""
    config_file = "config/capture_segment.json"
    try:
        if os.path.exists(config_file):
            os.remove(config_file)
            print("Segment configuration cleared completely")
        else:
            print("No segment configuration file to clear")
        return True
    except Exception as e:
        print(f"Error clearing segment config: {e}")
        return False

def get_segment_display_info(config, video_system):
    """Get formatted display information for segment config"""
    if not config:
        return None
    
    video_system = video_system.upper()
    if video_system == 'PAL':
        start_frame = config['start_frame_pal']
        frame_count = config['frame_count_pal']
        fps = 25
    else:
        start_frame = config['start_frame_ntsc']
        frame_count = config['frame_count_ntsc']
        fps = 29.97
    
    end_frame = start_frame + frame_count
    duration_minutes = frame_count / fps / 60
    
    return {
        'description': config['description'],
        'start_time': config['start_time'],
        'end_time': config['end_time'],
        'duration': config['duration'],
        'start_frame': start_frame,
        'end_frame': end_frame,
        'frame_count': frame_count,
        'duration_minutes': duration_minutes
    }

def print_segment_warning(config, video_system):
    """Print prominent red warning about segment mode"""
    if not config:
        return
    
    info = get_segment_display_info(config, video_system)
    
    print("\033[91m" + "=" * 60 + "\033[0m")
    print("\033[91m" + "⚠️  SEGMENT MODE ACTIVE - NOT A FULL DECODE!" + "\033[0m")
    print("\033[91m" + "=" * 60 + "\033[0m")
    print(f"\033[91mTime Range: {info['start_time']} to {info['end_time']} ({info['duration']})\033[0m")
    print(f"\033[91mFrames: {info['start_frame']} to {info['end_frame']} ({info['frame_count']} frames)\033[0m")
    print(f"\033[91mEstimated Duration: {info['duration_minutes']:.1f} minutes\033[0m")
    print("\033[91m" + "⚠️  This will only decode a small portion of your capture!" + "\033[0m")
    print("\033[91m" + "=" * 60 + "\033[0m")

def create_quick_segment_presets():
    """Create common segment presets"""
    presets = {
        "start_30s": {
            "start_time": "00:00:00",
            "duration": "00:30",
            "description": "30 seconds from start"
        },
        "start_1m": {
            "start_time": "00:00:00", 
            "duration": "01:00",
            "description": "1 minute from start"
        },
        "start_2m": {
            "start_time": "00:00:00",
            "duration": "02:00", 
            "description": "2 minutes from start"
        },
        "middle_1m": {
            "start_time": "30:00:00",  # Assumes 1-hour tape, middle
            "duration": "01:00",
            "description": "1 minute from middle (assumes 1-hour tape)"
        }
    }
    return presets
