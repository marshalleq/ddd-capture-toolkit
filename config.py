#!/usr/bin/env python3
"""
DdD Sync Capture - Configuration Management

Handles loading, saving, and managing configuration settings including
capture directory location and other user preferences.
"""

import json
import os
import sys
from pathlib import Path

# Default configuration values
DEFAULT_CONFIG = {
    "capture_directory": "temp",  # Default to temp folder in project directory
    "default_capture_name": "my_vhs_capture",
    "audio_delay": 0.000,  # Default audio delay for sync
    "preferred_video_format": "PAL",  # PAL or NTSC
    "last_used_test_pattern": "default",  # For custom test patterns
    "performance_settings": {
        "ffmpeg_threads": 4,  # Limit FFmpeg threads to keep UI responsive
        "ffmpeg_threads_description": "Number of threads FFmpeg uses (0=auto, 1-16=specific). Lower values reduce CPU load during final muxing to keep UI responsive. Recommended: 4-6 threads for most systems."
    }
}

CONFIG_FILE = "config.json"

def get_project_root():
    """Get the project root directory (where this script is located)"""
    return Path(__file__).parent.resolve()

def load_config():
    """
    Load configuration from config.json file.
    Returns default config if file doesn't exist or is invalid.
    """
    config_path = get_project_root() / CONFIG_FILE
    
    try:
        if config_path.exists():
            with open(config_path, 'r') as f:
                config = json.load(f)
                
            # Ensure all default keys exist (for backwards compatibility)
            for key, default_value in DEFAULT_CONFIG.items():
                if key not in config:
                    config[key] = default_value
                    
            return config
        else:
            # First time - create default config
            return DEFAULT_CONFIG.copy()
            
    except (json.JSONDecodeError, IOError) as e:
        print(f"Warning: Could not load config file: {e}")
        print("Using default configuration.")
        return DEFAULT_CONFIG.copy()

def save_config(config):
    """
    Save configuration to config.json file.
    Returns True if successful, False otherwise.
    """
    config_path = get_project_root() / CONFIG_FILE
    
    try:
        with open(config_path, 'w') as f:
            json.dump(config, f, indent=4)
        return True
    except IOError as e:
        print(f"Error: Could not save config file: {e}")
        return False

def get_capture_directory():
    """
    Get the current capture directory as an absolute path.
    Creates the directory if it doesn't exist.
    """
    config = load_config()
    capture_dir = config.get("capture_directory", "temp")
    
    # Convert relative paths to absolute (relative to project root)
    if not os.path.isabs(capture_dir):
        capture_dir = get_project_root() / capture_dir
    else:
        capture_dir = Path(capture_dir)
    
    # Create directory if it doesn't exist
    try:
        capture_dir.mkdir(parents=True, exist_ok=True)
        return str(capture_dir)
    except OSError as e:
        print(f"Warning: Could not create capture directory {capture_dir}: {e}")
        # Fall back to temp directory in project root
        fallback_dir = get_project_root() / "temp"
        fallback_dir.mkdir(parents=True, exist_ok=True)
        return str(fallback_dir)

def set_capture_directory(new_directory):
    """
    Set a new capture directory.
    Returns True if successful, False otherwise.
    """
    try:
        # Validate the directory
        new_path = Path(new_directory).resolve()
        
        # Check if directory exists or can be created
        if not new_path.exists():
            try:
                new_path.mkdir(parents=True, exist_ok=True)
                print(f"Created directory: {new_path}")
            except OSError as e:
                print(f"Error: Cannot create directory {new_path}: {e}")
                return False
        
        # Check if directory is writable
        if not os.access(new_path, os.W_OK):
            print(f"Error: Directory {new_path} is not writable")
            return False
        
        # Update configuration
        config = load_config()
        config["capture_directory"] = str(new_path)
        
        if save_config(config):
            print(f"Capture directory updated to: {new_path}")
            return True
        else:
            return False
            
    except Exception as e:
        print(f"Error setting capture directory: {e}")
        return False

def check_disk_space(directory, required_gb=10):
    """
    Check if directory has enough free disk space.
    Returns (available_gb, has_enough_space)
    """
    try:
        if sys.platform == 'win32':
            import shutil
            total, used, free = shutil.disk_usage(directory)
            free_gb = free / (1024**3)
        else:
            # Unix/Linux
            statvfs = os.statvfs(directory)
            free_gb = (statvfs.f_frsize * statvfs.f_bavail) / (1024**3)
        
        return free_gb, free_gb >= required_gb
        
    except Exception as e:
        print(f"Warning: Could not check disk space: {e}")
        return 0, False

def get_ffmpeg_threads():
    """
    Get the configured FFmpeg thread count for performance control.
    Returns an integer between 0-16, where 0 means auto-detect.
    """
    config = load_config()
    perf_settings = config.get('performance_settings', {})
    threads = perf_settings.get('ffmpeg_threads', 4)  # Default to 4 threads
    
    # Validate thread count (0 = auto, 1-16 = specific)
    if isinstance(threads, int) and 0 <= threads <= 16:
        return threads
    else:
        # Invalid value, return default
        return 4

def set_ffmpeg_threads(thread_count):
    """
    Set the FFmpeg thread count for performance control.
    thread_count: int between 0-16 (0 = auto-detect)
    Returns True if successful, False otherwise.
    """
    # Validate input
    if not isinstance(thread_count, int) or not (0 <= thread_count <= 16):
        print(f"Error: FFmpeg thread count must be between 0-16 (got {thread_count})")
        return False
    
    try:
        config = load_config()
        
        # Ensure performance_settings exists
        if 'performance_settings' not in config:
            config['performance_settings'] = {}
        
        # Update thread count
        config['performance_settings']['ffmpeg_threads'] = thread_count
        
        if save_config(config):
            threads_desc = "auto-detect" if thread_count == 0 else f"{thread_count} threads"
            print(f"FFmpeg thread count updated to: {threads_desc}")
            return True
        else:
            return False
            
    except Exception as e:
        print(f"Error setting FFmpeg thread count: {e}")
        return False

def get_performance_summary():
    """
    Get a formatted summary of current performance settings.
    """
    config = load_config()
    perf_settings = config.get('performance_settings', {})
    
    ffmpeg_threads = get_ffmpeg_threads()
    threads_desc = "Auto-detect" if ffmpeg_threads == 0 else f"{ffmpeg_threads} threads"
    
    summary = [
        "PERFORMANCE SETTINGS",
        "=" * 30,
        f"FFmpeg Threads: {threads_desc}",
        "  (Lower values reduce CPU load during final muxing)",
        "  (Recommended: 4-6 threads for most systems)",
        "  (0 = auto-detect, 1-16 = specific count)"
    ]
    
    return "\n".join(summary)

def get_config_summary():
    """Get a formatted summary of current configuration"""
    config = load_config()
    capture_dir = get_capture_directory()
    
    # Check disk space
    free_gb, has_space = check_disk_space(capture_dir)
    space_status = f"{free_gb:.1f} GB free" if free_gb > 0 else "Unknown"
    space_warning = "" if has_space else "   (Low space!)"
    
    summary = [
        "CURRENT CONFIGURATION",
        "=" * 30,
        f"Capture Directory: {capture_dir}",
        f"Disk Space: {space_status}{space_warning}",
        f"Default Capture Name: {config.get('default_capture_name', 'my_vhs_capture')}",
        f"Audio Delay: {config.get('audio_delay', 0.000):.3f}s",
        f"Preferred Format: {config.get('preferred_video_format', 'PAL')}",
    ]
    
    return "\n".join(summary)

if __name__ == "__main__":
    # Quick test/demo
    print("DdD Sync Capture - Configuration Manager")
    print("=" * 50)
    print(get_config_summary())
    print()
    print(f"Current capture directory: {get_capture_directory()}")
