#!/usr/bin/env python3
"""
DdD Sync Capture - Configuration Management

Handles loading, saving, and managing configuration settings including
capture directory location and other user preferences.
"""

import json
import os
import sys
import subprocess
import re
from pathlib import Path

# Known Clockgen audio device name patterns across platforms
CLOCKGEN_DEVICE_PATTERNS = [
    r'CXADC.*ClockGen',      # Linux ALSA: "CXADC+ADC-ClockGen" or similar
    r'cxadc.*clockgen',      # Case-insensitive variant
    r'ADC.*ClockGen',        # Alternate naming
    r'ClockGen.*Lite',       # Clockgen Lite variant
    r'PCM2707',              # TI PCM2707 USB audio codec (common in DIY clockgen)
    r'PCM2706',              # TI PCM2706 USB audio codec variant
    r'PCM270\d',             # Any PCM270x variant
    r'USB.*Audio.*78125',    # Generic USB audio with clockgen sample rate
]

# Clockgen devices typically support this exact sample rate
CLOCKGEN_SAMPLE_RATE = 78125

# Default configuration values
DEFAULT_CONFIG = {
    "capture_directory": "temp",  # Default to temp folder in project directory
    "default_capture_name": "my_vhs_capture",
    "audio_delay": 0.000,  # Default audio delay for sync
    "preferred_video_format": "PAL",  # PAL or NTSC
    "last_used_test_pattern": "default",  # For custom test patterns
    "audio_device": {
        "device_id": None,  # Platform-specific device identifier (auto-detected if None)
        "device_name": None,  # Human-readable name for display
        "sample_rate": 78125,  # Clockgen Lite sample rate
        "bit_depth": 24,
        "channels": 2
    },
    "performance_settings": {
        "ffmpeg_threads": 4,  # Limit FFmpeg threads to keep UI responsive
        "ffmpeg_threads_description": "Number of threads FFmpeg uses (0=auto, 1-16=specific). Lower values reduce CPU load during final muxing to keep UI responsive. Recommended: 4-6 threads for most systems.",
        "compress_use_gpu": False,  # Use ld-compress -a (flaldf/OpenCL) instead of -c (CPU FLAC)
        "compress_use_gpu_description": "Whether the compress step uses GPU acceleration via flaldf. Requires flaldf binary and an OpenCL runtime - see docs/gpu-compression.md.",
        "default_audio_resample_rate": "96000",  # Default target rate for final-mux audio
        "default_audio_resample_rate_description": "Sample rate for audio in the final muxed output. Options: 'none' (keep clockgen-Lite native 78125 Hz), '48000', '96000', '192000'. 96000 is recommended: closest common standard above 78125 (NLEs like DaVinci Resolve don't accept the native rate) and uses high-quality soxr resampler.",
        "default_audio_format": "flac",  # Default audio codec for final-mux output
        "default_audio_format_description": "Audio codec for the final muxed output. Options: 'flac' (lossless, compressed, no size limit), 'wav' (lossless, uncompressed, classic 4GB limit). FLAC recommended unless an editor cannot read it. DaVinci Resolve 16+ supports FLAC natively."
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

def get_preferred_video_format():
    """
    Get the preferred video format (PAL or NTSC) for VHS decoding.
    Returns 'pal' or 'ntsc' (lowercase for use with vhs-decode).
    """
    config = load_config()
    format_pref = config.get('preferred_video_format', 'PAL')

    # Normalize to lowercase for vhs-decode compatibility
    if isinstance(format_pref, str) and format_pref.upper() in ['PAL', 'NTSC']:
        return format_pref.lower()
    else:
        return 'pal'  # Default to PAL

def set_preferred_video_format(format_type):
    """
    Set the preferred video format (PAL or NTSC).

    Args:
        format_type: 'PAL' or 'NTSC' (case-insensitive)

    Returns:
        True if successful, False otherwise.
    """
    if not isinstance(format_type, str) or format_type.upper() not in ['PAL', 'NTSC']:
        print(f"Error: Invalid video format '{format_type}'. Must be 'PAL' or 'NTSC'.")
        return False

    config = load_config()
    config['preferred_video_format'] = format_type.upper()
    return save_config(config)

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

_VALID_AUDIO_RATES = ("none", "48000", "96000", "192000")
_VALID_AUDIO_FORMATS = ("flac", "wav")


def get_default_audio_resample_rate():
    """Get configured default sample rate for final-mux audio output.

    Returns one of: 'none', '48000', '96000', '192000'.
    'none' means keep the source rate (78125 Hz from clockgen-Lite).
    Per-project audio flags can override this default.
    """
    config = load_config()
    perf = config.get('performance_settings', {})
    rate = perf.get('default_audio_resample_rate', '96000')
    if rate not in _VALID_AUDIO_RATES:
        return '96000'
    return rate


def set_default_audio_resample_rate(rate):
    """Set the default sample rate for final-mux audio output.

    rate: one of 'none', '48000', '96000', '192000'. Returns True on success.
    """
    if rate not in _VALID_AUDIO_RATES:
        print(f"Error: rate must be one of {_VALID_AUDIO_RATES} (got {rate!r})")
        return False
    try:
        config = load_config()
        if 'performance_settings' not in config:
            config['performance_settings'] = {}
        config['performance_settings']['default_audio_resample_rate'] = rate
        if save_config(config):
            print(f"Default audio resample rate set to: {rate}")
            return True
        return False
    except Exception as e:
        print(f"Error setting audio resample rate: {e}")
        return False


def get_default_audio_format():
    """Get configured default audio codec for final-mux output.

    Returns 'flac' or 'wav'. Per-project audio flags can override this.
    """
    config = load_config()
    perf = config.get('performance_settings', {})
    fmt = perf.get('default_audio_format', 'flac')
    if fmt not in _VALID_AUDIO_FORMATS:
        return 'flac'
    return fmt


def set_default_audio_format(fmt):
    """Set the default audio codec for final-mux output.

    fmt: one of 'flac', 'wav'. Returns True on success.
    """
    if fmt not in _VALID_AUDIO_FORMATS:
        print(f"Error: format must be one of {_VALID_AUDIO_FORMATS} (got {fmt!r})")
        return False
    try:
        config = load_config()
        if 'performance_settings' not in config:
            config['performance_settings'] = {}
        config['performance_settings']['default_audio_format'] = fmt
        if save_config(config):
            print(f"Default audio format set to: {fmt}")
            return True
        return False
    except Exception as e:
        print(f"Error setting audio format: {e}")
        return False


def get_compress_use_gpu():
    """
    Whether the compress step should use GPU acceleration (flaldf/OpenCL).
    Returns bool. Defaults to False so existing setups are unaffected.
    """
    config = load_config()
    perf_settings = config.get('performance_settings', {})
    return bool(perf_settings.get('compress_use_gpu', False))


def set_compress_use_gpu(enabled):
    """
    Enable or disable GPU acceleration for the compress step.
    Returns True if saved successfully.
    """
    if not isinstance(enabled, bool):
        print(f"Error: compress_use_gpu must be bool (got {type(enabled).__name__})")
        return False

    config = load_config()
    if 'performance_settings' not in config:
        config['performance_settings'] = {}
    config['performance_settings']['compress_use_gpu'] = enabled

    if save_config(config):
        print(f"Compress GPU acceleration: {'enabled' if enabled else 'disabled'}")
        return True
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

    # Get audio device info
    audio_device = get_audio_device()
    if audio_device:
        audio_status = f"{audio_device['device_name']} ({audio_device['device_id']})"
    else:
        audio_status = "Not detected (will auto-detect on capture)"

    summary = [
        "CURRENT CONFIGURATION",
        "=" * 30,
        f"Capture Directory: {capture_dir}",
        f"Disk Space: {space_status}{space_warning}",
        f"Default Capture Name: {config.get('default_capture_name', 'my_vhs_capture')}",
        f"Audio Delay: {config.get('audio_delay', 0.000):.3f}s",
        f"Preferred Format: {config.get('preferred_video_format', 'PAL')}",
        f"Audio Device: {audio_status}",
    ]

    return "\n".join(summary)


# =============================================================================
# Audio Device Detection and Management
# =============================================================================

def detect_audio_devices_linux():
    """
    Detect available audio capture devices on Linux using ALSA.
    Returns list of dicts with 'card', 'device', 'name', 'device_id' keys.
    """
    devices = []
    try:
        result = subprocess.run(['arecord', '-l'], capture_output=True, text=True, timeout=5)
        if result.returncode != 0:
            return devices

        # Parse arecord -l output
        # Format: "card 0: CXADCADCClockGe [CXADC+ADC-ClockGen], device 0: USB Audio [USB Audio]"
        for line in result.stdout.split('\n'):
            match = re.match(r'card (\d+): (\w+) \[([^\]]+)\], device (\d+): (.+)', line)
            if match:
                card_num = match.group(1)
                card_id = match.group(2)
                card_name = match.group(3)
                device_num = match.group(4)
                device_desc = match.group(5)

                devices.append({
                    'card': int(card_num),
                    'device': int(device_num),
                    'card_id': card_id,
                    'name': card_name,
                    'description': device_desc,
                    'device_id': f'hw:{card_num},{device_num}'
                })
    except (subprocess.TimeoutExpired, FileNotFoundError, Exception) as e:
        print(f"Warning: Could not detect Linux audio devices: {e}")

    return devices


def detect_audio_devices_macos():
    """
    Detect available audio capture devices on macOS using system_profiler.
    Returns list of dicts with 'name', 'device_id' keys.
    """
    devices = []
    try:
        # Use system_profiler to get audio devices
        result = subprocess.run(
            ['system_profiler', 'SPAudioDataType', '-json'],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode != 0:
            return devices

        import json as json_module
        data = json_module.loads(result.stdout)

        # Parse the audio devices
        audio_data = data.get('SPAudioDataType', [])
        for item in audio_data:
            items = item.get('_items', [])
            for device in items:
                name = device.get('_name', '')
                if name:
                    devices.append({
                        'name': name,
                        'device_id': name,  # macOS uses device name directly
                        'description': device.get('coreaudio_device_manufacturer', '')
                    })
    except (subprocess.TimeoutExpired, FileNotFoundError, Exception) as e:
        print(f"Warning: Could not detect macOS audio devices: {e}")

    return devices


def detect_audio_devices_windows():
    """
    Detect available audio capture devices on Windows.
    Returns list of dicts with 'name', 'device_id' keys.
    """
    devices = []
    try:
        # Use PowerShell to get audio devices
        ps_command = "Get-WmiObject Win32_SoundDevice | Select-Object Name, DeviceID | ConvertTo-Json"
        result = subprocess.run(
            ['powershell', '-Command', ps_command],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode != 0:
            return devices

        import json as json_module
        data = json_module.loads(result.stdout)

        # Handle single device (returns dict) vs multiple (returns list)
        if isinstance(data, dict):
            data = [data]

        for device in data:
            name = device.get('Name', '')
            if name:
                devices.append({
                    'name': name,
                    'device_id': 'default',  # Windows SOX typically uses 'default'
                    'description': device.get('DeviceID', '')
                })
    except (subprocess.TimeoutExpired, FileNotFoundError, Exception) as e:
        print(f"Warning: Could not detect Windows audio devices: {e}")

    return devices


def detect_audio_devices():
    """
    Detect available audio capture devices on the current platform.
    Returns list of device dicts.
    """
    if sys.platform == 'linux':
        return detect_audio_devices_linux()
    elif sys.platform == 'darwin':
        return detect_audio_devices_macos()
    elif sys.platform == 'win32':
        return detect_audio_devices_windows()
    else:
        print(f"Warning: Unsupported platform for audio detection: {sys.platform}")
        return []


def find_clockgen_device():
    """
    Auto-detect the Clockgen audio device by:
    1. Matching known name patterns
    2. Checking for devices that support the unique 78125 Hz sample rate

    Returns device dict if found, None otherwise.
    """
    devices = detect_audio_devices()

    # First try: match by known name patterns
    for device in devices:
        device_name = device.get('name', '') + ' ' + device.get('description', '')
        for pattern in CLOCKGEN_DEVICE_PATTERNS:
            if re.search(pattern, device_name, re.IGNORECASE):
                return device

    # Second try: on Linux, check for devices that support 78125 Hz sample rate
    # This is the unique clockgen sample rate and is unlikely to be supported by normal audio devices
    if sys.platform == 'linux':
        for device in devices:
            device_info = get_device_info_linux(device['device_id'])
            if device_info and device_info.get('sample_rates'):
                if CLOCKGEN_SAMPLE_RATE in device_info['sample_rates']:
                    print(f"Auto-detected Clockgen device by sample rate: {device.get('name', device['device_id'])}")
                    return device

    return None


def get_audio_device():
    """
    Get the configured audio device, auto-detecting if not set.
    Returns device dict with 'device_id', 'device_name', etc. or None if not found.
    """
    config = load_config()
    audio_config = config.get('audio_device', {})

    # If device_id is set, verify it still exists
    if audio_config.get('device_id'):
        devices = detect_audio_devices()
        for device in devices:
            if device['device_id'] == audio_config['device_id']:
                return {
                    'device_id': device['device_id'],
                    'device_name': device.get('name', audio_config.get('device_name', 'Unknown')),
                    'sample_rate': audio_config.get('sample_rate', 78125),
                    'bit_depth': audio_config.get('bit_depth', 24),
                    'channels': audio_config.get('channels', 2)
                }
        # Configured device not found, try auto-detection
        print(f"Warning: Configured audio device '{audio_config.get('device_id')}' not found, auto-detecting...")

    # Auto-detect Clockgen device
    clockgen = find_clockgen_device()
    if clockgen:
        return {
            'device_id': clockgen['device_id'],
            'device_name': clockgen.get('name', 'Clockgen'),
            'sample_rate': audio_config.get('sample_rate', 78125),
            'bit_depth': audio_config.get('bit_depth', 24),
            'channels': audio_config.get('channels', 2)
        }

    return None


def set_audio_device(device_id, device_name=None):
    """
    Set the audio device for capture.
    device_id: Platform-specific device identifier (e.g., 'hw:0,0' on Linux)
    device_name: Human-readable name (optional, for display)
    Returns True if successful, False otherwise.
    """
    try:
        config = load_config()

        if 'audio_device' not in config:
            config['audio_device'] = DEFAULT_CONFIG['audio_device'].copy()

        config['audio_device']['device_id'] = device_id
        if device_name:
            config['audio_device']['device_name'] = device_name

        if save_config(config):
            print(f"Audio device set to: {device_name or device_id}")
            return True
        return False

    except Exception as e:
        print(f"Error setting audio device: {e}")
        return False


def get_sox_device_args():
    """
    Get SOX command arguments for the configured/detected audio device.
    Returns tuple of (driver, device_id) for use in SOX commands.
    """
    audio_device = get_audio_device()

    if sys.platform == 'win32':
        driver = 'waveaudio'
        device = 'default'
    elif sys.platform == 'darwin':
        driver = 'coreaudio'
        device = audio_device['device_id'] if audio_device else 'default'
    else:  # Linux
        driver = 'alsa'
        device = audio_device['device_id'] if audio_device else 'default'

    return driver, device


def get_device_info_linux(device_id):
    """
    Get detailed device information for a Linux ALSA device.
    Returns dict with 'channels', 'sample_rates', 'formats' or None on error.
    """
    if sys.platform != 'linux':
        return None

    try:
        # Extract card and device numbers from device_id (e.g., "hw:2,0")
        match = re.match(r'hw:(\d+),(\d+)', device_id)
        if not match:
            return None
        card_num = match.group(1)

        # Read from /proc/asound/cardX/stream0 for USB audio devices
        stream_path = f"/proc/asound/card{card_num}/stream0"
        if os.path.exists(stream_path):
            with open(stream_path, 'r') as f:
                content = f.read()

            info = {'channels': None, 'sample_rates': [], 'formats': []}

            # Parse channels
            channels_match = re.search(r'Channels:\s*(\d+)', content)
            if channels_match:
                info['channels'] = int(channels_match.group(1))

            # Parse sample rates
            rates_match = re.search(r'Rates:\s*([^\n]+)', content)
            if rates_match:
                rates_str = rates_match.group(1)
                info['sample_rates'] = [int(r) for r in re.findall(r'\d+', rates_str)]

            # Parse formats
            formats_match = re.search(r'Format:\s*([^\n]+)', content)
            if formats_match:
                info['formats'] = [formats_match.group(1).strip()]

            return info

    except Exception as e:
        pass

    return None


def verify_audio_device(device_id, channels=None):
    """
    Verify if an audio device is accessible for recording.
    If channels not specified, will try to detect from device info.
    Returns tuple (accessible: bool, error_message: str or None).
    """
    if sys.platform != 'linux':
        return True, None  # Skip verification on non-Linux

    # Get actual channel count if not provided
    if channels is None:
        device_info = get_device_info_linux(device_id)
        if device_info and device_info.get('channels'):
            channels = device_info['channels']
        else:
            channels = 2  # Default fallback

    try:
        # Try a quick test with arecord (0 duration = just probe, no actual recording)
        result = subprocess.run(
            ['arecord', '-D', device_id, '-d', '0', '-f', 'S24_3LE', '-r', '78125', '-c', str(channels), '/dev/null'],
            capture_output=True, text=True, timeout=3
        )

        if result.returncode == 0:
            return True, None

        stderr = result.stderr.lower()
        combined_output = (result.stdout + result.stderr).lower()

        # If we see "Recording WAVE" it means the device was opened successfully
        # Input/output errors during -d 0 test are normal if no signal is present
        if 'recording wave' in combined_output:
            # Device opened successfully - input/output error just means no signal
            if 'input/output error' in stderr:
                return True, None  # Device is accessible, just no signal
            return True, None

        if 'busy' in stderr or 'resource busy' in stderr:
            return False, "Device is busy (possibly held by PipeWire/PulseAudio)"
        elif 'no such' in stderr or 'not found' in stderr:
            return False, "Device not found (may have changed USB ports)"
        elif 'channel' in stderr and 'non available' in stderr:
            return False, f"Device doesn't support {channels} channels"
        else:
            return False, result.stderr.strip()

    except subprocess.TimeoutExpired:
        return False, "Device check timed out"
    except Exception as e:
        return False, str(e)


def release_audio_device_linux(device_id):
    """
    Attempt to release an audio device from PipeWire/PulseAudio on Linux.
    This uses pactl to suspend the device so ALSA can access it directly.
    Returns True if release was attempted, False otherwise.
    """
    if sys.platform != 'linux':
        return False

    try:
        # Try to find and suspend the PulseAudio/PipeWire source
        # List sources to find matching ALSA input devices
        result = subprocess.run(['pactl', 'list', 'sources', 'short'],
                                capture_output=True, text=True, timeout=5)
        if result.returncode != 0:
            return False

        suspended_any = False
        for line in result.stdout.split('\n'):
            # Look for ALSA input sources that might be our clockgen device
            # Match on known patterns: clockgen, cxadc, pcm2707, or 78125 Hz sample rate
            line_lower = line.lower()
            if 'alsa_input' in line_lower:
                is_clockgen = any(pattern in line_lower for pattern in
                                  ['clockgen', 'cxadc', 'pcm2707', 'pcm2706', '78125'])
                if is_clockgen:
                    parts = line.split()
                    if len(parts) >= 2:
                        source_name = parts[1]
                        # Suspend the source
                        subprocess.run(['pactl', 'suspend-source', source_name, '1'],
                                       capture_output=True, timeout=5)
                        print(f"   Suspended PipeWire/PulseAudio source: {source_name}")
                        suspended_any = True

        return suspended_any

    except (subprocess.TimeoutExpired, FileNotFoundError, Exception):
        return False


def prepare_audio_device(device_id=None):
    """
    Prepare an audio device for capture by:
    1. Auto-detecting if no device_id provided
    2. Verifying accessibility
    3. Attempting to release from PipeWire/PulseAudio if busy

    Returns tuple (device_info: dict or None, error_message: str or None).
    """
    # Auto-detect device if not provided
    if device_id is None:
        audio_device = get_audio_device()
        if audio_device is None:
            return None, "No Clockgen audio device detected. Check USB connection."
        device_id = audio_device['device_id']
        device_name = audio_device.get('device_name', 'Unknown')
    else:
        device_name = device_id

    # Get actual device capabilities
    if sys.platform == 'linux':
        device_info = get_device_info_linux(device_id)
        if device_info and device_info.get('channels'):
            actual_channels = device_info['channels']
        else:
            actual_channels = 2  # Default
    else:
        actual_channels = 2
        device_info = None

    # Verify device is accessible (using actual channel count)
    accessible, error = verify_audio_device(device_id, channels=actual_channels)

    if not accessible:
        print(f"Audio device {device_id} not immediately accessible: {error}")

        # Try to release from PipeWire/PulseAudio
        if 'busy' in (error or '').lower():
            print("   Attempting to release device from audio server...")
            if release_audio_device_linux(device_id):
                import time
                time.sleep(0.5)  # Give time for release
                # Retry verification with correct channel count
                accessible, error = verify_audio_device(device_id, channels=actual_channels)
                if accessible:
                    print("   Device successfully released!")
                else:
                    print(f"   Device still not accessible: {error}")

        if not accessible:
            return None, f"Audio device {device_id} not accessible: {error}"

    # Build full device info
    config = load_config()
    audio_config = config.get('audio_device', {})

    return {
        'device_id': device_id,
        'device_name': device_name,
        'sample_rate': audio_config.get('sample_rate', CLOCKGEN_SAMPLE_RATE),
        'bit_depth': audio_config.get('bit_depth', 24),
        'channels': actual_channels,
        'device_capabilities': device_info
    }, None


def list_audio_devices():
    """
    List all detected audio devices with their details.
    Returns formatted string for display.
    """
    devices = detect_audio_devices()

    if not devices:
        return "No audio capture devices detected."

    lines = ["DETECTED AUDIO DEVICES", "=" * 50]

    clockgen = find_clockgen_device()
    clockgen_id = clockgen['device_id'] if clockgen else None

    for i, device in enumerate(devices):
        marker = " [CLOCKGEN]" if device['device_id'] == clockgen_id else ""
        lines.append(f"{i+1}. {device.get('name', 'Unknown')}{marker}")
        lines.append(f"   Device ID: {device['device_id']}")
        if device.get('description'):
            lines.append(f"   Description: {device['description']}")

        # Show device capabilities on Linux
        if sys.platform == 'linux':
            info = get_device_info_linux(device['device_id'])
            if info:
                if info.get('channels'):
                    lines.append(f"   Channels: {info['channels']}")
                if info.get('sample_rates'):
                    rates = ', '.join(str(r) for r in info['sample_rates'][:5])
                    if len(info['sample_rates']) > 5:
                        rates += '...'
                    lines.append(f"   Sample rates: {rates}")

    return "\n".join(lines)

if __name__ == "__main__":
    # Quick test/demo
    print("DdD Sync Capture - Configuration Manager")
    print("=" * 50)
    print(get_config_summary())
    print()
    print(f"Current capture directory: {get_capture_directory()}")
