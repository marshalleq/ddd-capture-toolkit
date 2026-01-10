#!/usr/bin/env python3
"""
VHS Decode Segment Configuration Module
Handles per-project configuration and management of decode segments for testing purposes
"""

import os
import json
from datetime import datetime

CONFIG_FILE = "config/project_segments.json"


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


def _load_all_segments():
    """Load all segment configurations from file"""
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r') as f:
                data = json.load(f)
                if 'projects' not in data:
                    data['projects'] = {}
                return data
    except Exception as e:
        print(f"Warning: Could not load segment configs: {e}")
    return {'version': 1, 'projects': {}}


def _save_all_segments(data):
    """Save all segment configurations to file"""
    os.makedirs("config", exist_ok=True)
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(data, f, indent=2)
        return True
    except Exception as e:
        print(f"Error saving segment config: {e}")
        return False


def load_segment_config(project_name=None):
    """Load segment configuration for a specific project

    Args:
        project_name: Name of the project. If None, returns None (no global segments anymore)

    Returns:
        Segment config dict if found and enabled, None otherwise
    """
    if not project_name:
        return None

    data = _load_all_segments()
    config = data.get('projects', {}).get(project_name)

    if config and config.get('enabled', False):
        # Validate required fields
        required_fields = ['start_time', 'duration', 'start_frame_pal', 'frame_count_pal',
                          'start_frame_ntsc', 'frame_count_ntsc']
        if all(key in config for key in required_fields):
            return config

    return None


def save_segment_config(project_name, start_time, duration, description=None):
    """Save segment configuration for a specific project

    Args:
        project_name: Name of the project
        start_time: Start time in MM:SS or HH:MM:SS format
        duration: Duration in MM:SS or HH:MM:SS format
        description: Optional description

    Returns:
        True if saved successfully, False otherwise
    """
    if not project_name:
        print("Error: project_name is required")
        return False

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

    # Load existing data and update
    data = _load_all_segments()
    data['projects'][project_name] = config

    return _save_all_segments(data)


def toggle_segment_enabled(project_name, enable=None):
    """Enable or disable segment mode for a project while preserving configuration

    Args:
        project_name: Name of the project
        enable: True to enable, False to disable, None to toggle

    Returns:
        New enabled state, or False if no config exists
    """
    if not project_name:
        return False

    data = _load_all_segments()
    config = data.get('projects', {}).get(project_name)

    if config:
        if enable is None:
            config['enabled'] = not config.get('enabled', False)
        else:
            config['enabled'] = enable

        data['projects'][project_name] = config
        _save_all_segments(data)
        return config['enabled']
    else:
        print(f"No segment configuration found for project: {project_name}")
        return False


def clear_segment_config(project_name):
    """Remove segment configuration for a specific project

    Args:
        project_name: Name of the project

    Returns:
        True if cleared successfully
    """
    if not project_name:
        return False

    data = _load_all_segments()

    if project_name in data.get('projects', {}):
        del data['projects'][project_name]
        _save_all_segments(data)
        print(f"Segment configuration cleared for: {project_name}")
    else:
        print(f"No segment configuration found for: {project_name}")

    return True


def has_segment_config(project_name):
    """Check if a project has segment configuration (enabled or not)

    Args:
        project_name: Name of the project

    Returns:
        True if project has any segment config
    """
    if not project_name:
        return False

    data = _load_all_segments()
    return project_name in data.get('projects', {})


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
        'description': config.get('description', ''),
        'start_time': config.get('start_time', '00:00'),
        'end_time': config.get('end_time', '00:00'),
        'duration': config.get('duration', '00:00'),
        'start_frame': start_frame,
        'end_frame': end_frame,
        'frame_count': frame_count,
        'duration_minutes': duration_minutes,
        'enabled': config.get('enabled', False)
    }


def print_segment_warning(config, video_system):
    """Print prominent red warning about segment mode"""
    if not config:
        return

    info = get_segment_display_info(config, video_system)

    print("\033[91m" + "=" * 60 + "\033[0m")
    print("\033[91m" + "  SEGMENT MODE ACTIVE - NOT A FULL DECODE!" + "\033[0m")
    print("\033[91m" + "=" * 60 + "\033[0m")
    print(f"\033[91mTime Range: {info['start_time']} to {info['end_time']} ({info['duration']})\033[0m")
    print(f"\033[91mFrames: {info['start_frame']} to {info['end_frame']} ({info['frame_count']} frames)\033[0m")
    print(f"\033[91mEstimated Duration: {info['duration_minutes']:.1f} minutes\033[0m")
    print("\033[91m" + "  This will only decode a small portion of your capture!" + "\033[0m")
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


# Migration helper - convert old global config to per-project if needed
def migrate_old_config(project_name):
    """Migrate old global segment config to per-project format

    Args:
        project_name: Project to assign the old config to

    Returns:
        True if migration occurred, False otherwise
    """
    old_config_file = "config/capture_segment.json"

    if os.path.exists(old_config_file):
        try:
            with open(old_config_file, 'r') as f:
                old_config = json.load(f)

            if old_config and 'start_time' in old_config:
                # Save to new per-project format
                data = _load_all_segments()
                data['projects'][project_name] = old_config
                _save_all_segments(data)

                # Remove old file
                os.remove(old_config_file)
                print(f"Migrated old segment config to project: {project_name}")
                return True
        except Exception as e:
            print(f"Error migrating old config: {e}")

    return False
