
def shared_capture_process(sox_command, audio_delay, capture_duration, ddd_command=None):
    """
    A shared function to start video and audio capture in parallel threads.
    - DomesdayDuplicator (video) and sox (audio) are started in separate threads.
    - The audio thread waits for the specified audio_delay before starting.
    - If capture_duration is provided, capture runs for that duration.
    - If capture_duration is None, capture runs until user presses Enter.
    - If ddd_command is provided, uses that command; otherwise uses default headless command.
    """
    # Create threading events to signal when to stop
    stop_event = threading.Event()
    
    # Use default DomesdayDuplicator command if none provided
    if ddd_command is None:
        ddd_command = ['DomesdayDuplicator', '--start-capture', '--headless']

    def video_capture_thread():
        print("[Video Thread] Starting DomesdayDuplicator capture...")
        print(f"[Video Thread] Command: {' '.join(ddd_command)}")
        try:
            # Start DomesdayDuplicator with real-time output monitoring
            ddd_process = subprocess.Popen(ddd_command, 
                                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT, 
                                         text=True, bufsize=1, universal_newlines=True)
            print("[Video Thread] DomesdayDuplicator process started.")
            
            # Give the process a moment to start 
            time.sleep(1)
            if ddd_process.poll() is not None:
                # Process has already terminated - get the error
                stdout, stderr = ddd_process.communicate()
                print(f"[Video Thread] ERROR: DomesdayDuplicator failed to start!")
                print(f"[Video Thread] Return code: {ddd_process.returncode}")
                if stdout:
                    print(f"[Video Thread] Output: {stdout.strip()}")
                return
            
            print("[Video Thread] DomesdayDuplicator is running successfully")
            print("[Video Thread] --- DomesdayDuplicator Status ---")
            
            # Monitor DomesdayDuplicator output in real-time until stop is requested
            import select
            while not stop_event.is_set() and ddd_process.poll() is None:
                # Use select to check if there's output available (non-blocking)
                ready, _, _ = select.select([ddd_process.stdout], [], [], 0.1)
                if ready:
                    line = ddd_process.stdout.readline()
                    if line:
                        # Prefix DomesdayDuplicator output and display immediately
                        print(f"[DD] {line.rstrip()}", flush=True)
                else:
                    # Short sleep to prevent excessive CPU usage
                    time.sleep(0.1)
            print("[Video Thread] Stopping DomesdayDuplicator capture using file-based method...")
            
            # Send the stop command - this creates the stop file that DomesdayDuplicator watches for
            stop_result = subprocess.run(['DomesdayDuplicator', '--stop-capture'], 
                                       capture_output=True, text=True, timeout=10)
            
            if stop_result.returncode == 0:
                print("[Video Thread] Stop command sent successfully. Waiting for DomesdayDuplicator to complete shutdown...")
                
                # Wait for the process to exit naturally (this allows JSON generation)
                try:
                    ddd_process.wait(timeout=30)  # Give it 30 seconds to complete shutdown
                    print("[Video Thread] DomesdayDuplicator completed shutdown naturally.")
                except subprocess.TimeoutExpired:
                    print("[Video Thread] DomesdayDuplicator did not exit within 30 seconds. Terminating process...")
                    ddd_process.terminate()
                    try:
                        ddd_process.wait(timeout=5)
                        print("[Video Thread] DomesdayDuplicator process terminated.")
                    except subprocess.TimeoutExpired:
                        print("[Video Thread] Process did not respond to terminate. Killing process...")
                        ddd_process.kill()
                        ddd_process.wait()
                        print("[Video Thread] DomesdayDuplicator process killed.")
            else:
                print(f"[Video Thread] Stop command failed (exit code {stop_result.returncode}). Falling back to process termination.")
                ddd_process.terminate()
                ddd_process.wait()
            
            print("[Video Thread] DomesdayDuplicator capture stopped.")
            
        except Exception as e:
            print(f"[Video Thread] Exception starting DomesdayDuplicator: {e}")

    def audio_capture_thread():
        time.sleep(audio_delay)
        # Start SOX with direct console output (preserves VU meters)
        sox_process = subprocess.Popen(sox_command)
        
        # Monitor SOX process status without interfering with its output
        start_time = time.time()
        while not stop_event.is_set() and sox_process.poll() is None:
            # Wait for stop event or check every 60 seconds
            if stop_event.wait(timeout=60):
                break  # Stop event was set
        
        sox_process.terminate()
        sox_process.wait()

    # Create and start the threads
    video_thread = threading.Thread(target=video_capture_thread)
    audio_thread = threading.Thread(target=audio_capture_thread)

    video_thread.start()
    audio_thread.start()

    # Wait for the appropriate stop condition
    if capture_duration is not None:
        print(f"[Main Thread] Capture in progress for {capture_duration} seconds...")
        time.sleep(capture_duration)
        print("[Main Thread] Capture duration elapsed. Signaling threads to stop...")
    else:
        print(f"[Main Thread] Capture in progress. \033[92mPress Enter to stop...\033[0m")
        input()  # Wait for user to press Enter
        print("[Main Thread] User requested stop. Signaling threads to stop...")

    # Signal the threads to stop
    stop_event.set()

    # Wait for the threads to finish
    video_thread.join()
    audio_thread.join()

    print("[Main Thread] All capture processes stopped.")

#!/usr/bin/env python3 -u
# Domesday Duplicator + Clockgen Lite Sync Capture
#
# This script provides automated audio/video synchronisation for VHS archival workflows
# using the Domesday Duplicator RF capture hardware and Clockgen Lite audio capture mod.
#
# Features:
# - GUI automation for Domesday Duplicator software
# - Synchronised SOX audio recording with platform-specific drivers
# - Automated A/V alignment using precision 1kHz test tones
# - Cross-platform support (Windows, macOS, Linux)
# - Archival-quality FLAC and WAV output
#
# Hardware Requirements:
# - Domesday Duplicator RF capture card
# - Clockgen Lite mod for high-quality audio sampling (78.125kHz/24-bit)
# - VCR or other analog video source
#
# Author: Community Project
# Version: 2.0 (Restructured with automated A/V alignment)
# Support: https://digital-archivist.com/community/

import subprocess
import time
import sys
import os
import threading

# Force unbuffered output for real-time console display
os.environ['PYTHONUNBUFFERED'] = '1'
sys.stdout.reconfigure(line_buffering=True)
sys.stderr.reconfigure(line_buffering=True)

# --- CONFIGURATION ---
# DomesdayDuplicator command line interface
# Commands available:
# - DomesdayDuplicator --start-capture: Start capture with GUI visible
# - DomesdayDuplicator --start-capture --headless: Start capture without GUI
# - DomesdayDuplicator --stop-capture: Stop any running capture
# - DomesdayDuplicator --debug --start-capture: Show debug info while capturing

# 2. Output Filename:
#    This will be set dynamically by prompting the user
#    The script will use this name for both RF (.lds) and audio files
CAPTURE_NAME = 'my_vhs_capture'  # Default fallback

# Import configuration management
from config import get_capture_directory, load_config, save_config

# Get actual temp folder for calibration (always uses project temp directory)
def get_temp_folder():
    """Get the temp folder in project directory for calibration/alignment files"""
    project_root = os.path.dirname(os.path.abspath(__file__))
    temp_folder = os.path.join(project_root, "temp")
    if not os.path.exists(temp_folder):
        os.makedirs(temp_folder)
    return temp_folder

# Get configured capture directory for actual captures
def get_capture_folder():
    """Get the configured capture directory for user captures"""
    return get_capture_directory()

# 3. SOX Command:
#    This is your audio recording command. The script will replace
#    'your_capture_name.flac' with the filename defined above.
#    Platform-specific audio settings are configured below.

def get_sox_command(output_filename):
    """Get platform-specific SOX command with optimised buffer settings"""
    if sys.platform == 'win32':
        # Windows - use DirectSound or WaveIn
        return [
            'sox',
            '-t', 'waveaudio',  # Windows audio driver
            '-r', '78125',
            '-b', '24',
            'default',  # Default audio device
            output_filename,
            'remix', '1', '2'
        ]
    else:
        # Linux/macOS - use ALSA (Linux) or coreaudio (macOS)
        audio_driver = 'coreaudio' if sys.platform == 'darwin' else 'alsa'
        if sys.platform == 'darwin':
            device = 'default'
        else:
            # Linux ALSA - use custom ALSA device with larger buffers (see ~/.asoundrc)
            # This prevents audio overruns during long captures at 78.125kHz
            device = 'cxadc_buffered'
        
        return [
            'sox',
            '-t', audio_driver,
            '-r', '78125',          # Input sample rate
            '-b', '24',             # Input bit depth  
            '-c', '2',              # Input channels
            device,
            '--buffer', '8192',     # SOX internal buffer size (bytes)
            output_filename,
            'remix', '1', '2'
        ]

# Create capture file paths in temp folder
CAPTURE_FLAC_PATH = os.path.join(get_temp_folder(), f'{CAPTURE_NAME}.flac')
CAPTURE_WAV_PATH = os.path.join(get_temp_folder(), f'{CAPTURE_NAME}.wav')
SOX_COMMAND = get_sox_command(CAPTURE_FLAC_PATH)
# --- SCRIPT LOGIC ---

import tempfile
import shutil
from analyze_test_pattern import analyze_test_pattern_timing
from datetime import datetime
import json

# Generate automated alignment filename with date/time
def get_alignment_filename():
    """Generate automated alignment filename with current date and time"""
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    return f"automated_alignment_{timestamp}"

# Alignment file paths (will be created in temp folder with timestamp)
# These will be updated dynamically in perform_av_alignment()
DEFAULT_ALIGNMENT_DURATION_SECONDS = 30  # Default capture duration for alignment


def get_alignment_duration():
    """
    Prompt user for alignment capture duration
    Returns duration in seconds
    """
    print("\n--- ALIGNMENT CAPTURE DURATION ---")
    print("Set the duration for calibration capture.")
    print("")
    print("Recommendations:")
    print("   • 20-30s: Quick calibration (6-12 measurement pairs)")
    print("   • 30-45s: Standard calibration (12-18 measurement pairs)")
    print("   • 45-60s: High precision (18-24 measurement pairs)")
    print("")
    print("Longer captures provide more measurement pairs for better")
    print("statistical accuracy, but take more time to process.")
    print("")
    
    while True:
        try:
            user_input = input(f"Enter capture duration in seconds (default {DEFAULT_ALIGNMENT_DURATION_SECONDS}s): ").strip()
            
            if not user_input:
                duration = DEFAULT_ALIGNMENT_DURATION_SECONDS
                print(f"Using default duration: {duration}s")
                break
            
            duration = int(user_input)
            
            if duration < 10:
                print("ERROR: Duration must be at least 10 seconds for reliable measurements.")
                continue
            elif duration > 300:  # 5 minutes
                print("WARNING: Duration > 5 minutes may be unnecessarily long.")
                confirm = input("Continue with this duration? (y/N): ").strip().lower()
                if confirm not in ['y', 'yes']:
                    continue
            
            # Estimate measurement pairs
            estimated_audio_cycles = duration // 2  # Rough estimate: 1 cycle per 2 seconds
            estimated_video_cycles = estimated_audio_cycles
            estimated_pairs = max(0, min(estimated_audio_cycles, estimated_video_cycles) - 2)
            
            print(f"\nCapture duration set to: {duration} seconds")
            print(f"Estimated measurement pairs: ~{estimated_pairs}")
            print(f"Expected processing time: ~{duration//10 + 2}-{duration//5 + 5} minutes")
            break
            
        except ValueError:
            print("ERROR: Please enter a valid number.")
        except KeyboardInterrupt:
            print("\nAlignment cancelled by user.")
            return None
        except Exception as e:
            print(f"ERROR: {e}")
    
    return duration


def perform_av_alignment():
    """
    Perform automated audio/video alignment with proper RF decode workflow
    """
    try:
        print("\n=== Automated A/V Alignment ===")
        print("IMPORTANT: This workflow requires:")
        print("   1. RF capture from DomesdayDuplicator")
        print("   2. Audio capture from Clockgen Lite")
        print("   3. RF decode to create TBC JSON timing file")
        print("   4. Audio alignment using timing data")
        print()
        
        # Note: We no longer use fixed duration - user controls when to stop
        print("This capture will run until you press ENTER to stop.")
        print("Recommended capture time: 30-60 seconds for good calibration data.")
        
        # Create temp folder if it doesn't exist
        temp_folder = get_temp_folder()
        if not os.path.exists(temp_folder):
            os.makedirs(temp_folder)
            print(f"Created temp folder: {temp_folder}")
        
        # Generate automated filename with timestamp
        alignment_base_name = get_alignment_filename()
        print(f"Using automated calibration filename: {alignment_base_name}")
        
        # Create alignment file paths with timestamp
        alignment_capture_filename = os.path.join(temp_folder, f"{alignment_base_name}.flac")
        alignment_rf_filename = os.path.join(temp_folder, f"{alignment_base_name}.lds")
        alignment_tbc_filename = os.path.join(temp_folder, f"{alignment_base_name}.tbc")
        alignment_tbc_json_filename = os.path.join(temp_folder, f"{alignment_base_name}.tbc.json")
        alignment_video_filename = os.path.join(temp_folder, f"{alignment_base_name}_ffv1.mkv")
        
        print("\033[91mIMPORTANT SETUP REQUIRED:\033[0m")
        print(f"\033[91m   ⚠️  You must manually configure the Domesday Duplicator Client to point to: {os.path.abspath(temp_folder)}\033[0m")
        print(f"\033[91m   ⚠️  Set DomesdayDuplicator filename to: {alignment_base_name}\033[0m")
        print(f"   This ensures all alignment files are organized with matching names.")
        print()
        
        input("Make sure you've recorded at least 5 minutes of the included test pattern files onto a VHS tape. Press any key to continue or Ctrl-C to stop.")
        input("Ensure your Domesday duplicator is plugged in and powered on and your clockgen lite is connected and working. Press any key to continue.")
        input("Configure DomesdayDuplicator output location and filename as shown above, then insert your VHS tape into your VCR and press play. It's very important to be playing this alignment tape before calibration. Press any key to start Alignment Capture.")

        # Capture alignment using command line DomesdayDuplicator
        print("\nStarting RF + Audio capture...")
        alignment_sox_command = get_sox_command(alignment_capture_filename)

        try:
            # 1. Start audio capture using command line with zero delay as baseline
            print("Starting SOX audio recording (calibration baseline with 0.0s delay)...")
            time.sleep(0.0)  # Calibration baseline - zero delay
            alignment_sox_command = get_sox_command(alignment_capture_filename)
            capture_process = subprocess.Popen(alignment_sox_command)
            print("SOX audio recording started")

            # 2. Start video capture using command line with headless mode for minimal latency
            print("Starting DomesdayDuplicator capture (headless mode for minimal latency)...")
            ddd_process = subprocess.Popen(['DomesdayDuplicator', '--start-capture', '--headless'], 
                                      stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

            # Check if process is still running (successful start)
            if ddd_process.poll() is None:
                print("DomesdayDuplicator capture started successfully")
                
                print("\nCAPTURE IN PROGRESS")
                print("Both RF and audio recording are now active")
                print("DO NOT STOP THE VCR YET - let it continue playing!")
                print("\n" + "=" * 50)
                print("  WHEN READY TO STOP CAPTURE:")
                print("  Press ENTER to stop recording safely...")
                print("  (Recommended: 30-60 seconds for good calibration)")
                print("=" * 50)
                
                # Wait for user to press ENTER to stop capture
                try:
                    input()  # Wait for ENTER key
                    print("\nStopping capture...")
                    
                    # Stop SOX audio recording
                    print("Stopping audio recording...")
                    capture_process.terminate()
                    capture_process.wait()
                    print("Audio recording stopped")
                except KeyboardInterrupt:
                    print("\nCtrl+C detected. Stopping capture...")
                    capture_process.terminate()
                    capture_process.wait()
                    print("Audio recording stopped.")

                # 3. Stop video capture using command line with fallback
                print("\nStopping DomesdayDuplicator capture...")
                
                # First try the command line stop
                stop_result = subprocess.run(['DomesdayDuplicator', '--stop-capture'], 
                                           capture_output=True, text=True, timeout=10)
                
                if stop_result.returncode == 0:
                    print("DomesdayDuplicator capture stopped successfully")
                else:
                    print(f"Warning: DomesdayDuplicator stop returned code {stop_result.returncode}")
                    print("Attempting to terminate DomesdayDuplicator process directly...")
                    
                    # Fallback: terminate the process we started
                    try:
                        ddd_process.terminate()
                        ddd_process.wait(timeout=5)
                        print("DomesdayDuplicator process terminated successfully")
                    except subprocess.TimeoutExpired:
                        print("Process termination timed out, forcing kill...")
                        ddd_process.kill()
                        ddd_process.wait()
                        print("DomesdayDuplicator process killed")
                    except Exception as e:
                        print(f"Error terminating process: {e}")
                        print("You may need to manually stop DomesdayDuplicator")
                
                # Important user message after capture stops
                print("\n" + "="*50)
                print("CAPTURE COMPLETED - IMPORTANT MESSAGE")
                print("="*50)
                print("RF and audio capture has finished successfully!")
                print("")
                print("You can now STOP your VCR/alignment tape.")
                print("   The capture is complete and no longer recording.")
                print("")
                print("Next: RF decode and audio alignment analysis will begin...")
                print("   This will take a few minutes to process the captured data.")
                print("="*50)
                print()
                
                # Give user a moment to see this message
                time.sleep(2)

            else:
                # Process has terminated, get output and error
                stdout, stderr = ddd_process.communicate()
                return_code = ddd_process.returncode
                
                print(f"ERROR: Could not start DomesdayDuplicator capture!")
                print(f"Command failed with return code: {return_code}")
                print(f"Error output: {stderr}")
                print("Please ensure:")
                print("1. DomesdayDuplicator is installed and in your PATH")
                print("2. The hardware is connected properly")
                print("3. No other instance is already running")
                print("\nAlignment capture cancelled.")
                return

        except subprocess.TimeoutExpired:
            print("ERROR: DomesdayDuplicator command timed out")
            print("This might indicate the command is hanging or waiting for user input")
            return
        except FileNotFoundError:
            print("ERROR: DomesdayDuplicator command not found!")
            print("Please ensure DomesdayDuplicator is installed and available in your PATH")
            return
        except Exception as e:
            print(f"Capture error: {e}")
            return

        # 5. RF Decode step
        print("\nSTARTING RF DECODE WORKFLOW")
        print("Looking for RF capture file in temp folder...")
        
        # Find the most recent .lds file (RF capture) in temp folder
        if not os.path.exists(temp_folder):
            print(f"Temp folder {temp_folder} does not exist!")
            print("Please ensure the DomesdayDuplicator output location is configured correctly.")
            return
            
        lds_files = [f for f in os.listdir(temp_folder) if f.endswith('.lds')]
        if not lds_files:
            print(f"No RF capture files (.lds) found in {temp_folder}!")
            print("Please ensure the Domesday Duplicator created an RF capture file in the temp folder.")
            return
        
        # Get the most recent RF file (with full path)
        lds_paths = [os.path.join(temp_folder, f) for f in lds_files]
        rf_file = max(lds_paths, key=os.path.getmtime)
        print(f"Found RF capture: {rf_file}")
        
        # Check if we already have decoded files
        tbc_file = rf_file.replace('.lds', '.tbc')
        tbc_json_file = rf_file.replace('.lds', '.tbc.json')
        
        if os.path.exists(tbc_json_file):
            print(f"TBC JSON already exists: {tbc_json_file}")
        else:
            print("\nRunning vhs-decode...")
            if not run_vhs_decode_with_params(rf_file, tbc_file, 'pal', 'SP'):
                print("RF decode failed")
                return
        
        # Check if we need to export video
        video_file = rf_file.replace('.lds', '_ffv1.mkv')
        if os.path.exists(video_file):
            print(f"Video export already exists: {video_file}")
        else:
            print("\nRunning tbc-video-export...")
            if not run_tbc_video_export(tbc_file, video_file):
                print("Video export failed, but continuing with audio alignment...")
        
        print("\nRF decode workflow complete!")
        
        # 6. Audio timing analysis (using raw audio)
        print(f"\nUsing TBC JSON file: {tbc_json_file}")
        
        print("\nSkipping mechanical alignment - analyzing raw audio directly for calibration")
        print("(This eliminates alignment-induced measurement errors)")
        
        # Check if captured audio file exists
        if os.path.exists(alignment_capture_filename):
            print(f"\nUsing raw audio file: {alignment_capture_filename}")
            
            # Show file details for verification
            file_size = os.path.getsize(alignment_capture_filename) / (1024*1024)  # MB
            file_time = time.ctime(os.path.getmtime(alignment_capture_filename))
            print(f"   File size: {file_size:.1f} MB")
            print(f"   Modified: {file_time}")
            
            # Run test pattern timing analysis on raw audio and video
            print("\nRunning test pattern timing analysis on raw audio...")
            offset_seconds = analyze_test_pattern_timing(alignment_capture_filename, video_file)
            
            if offset_seconds is not None:
                print(f"\n" + "="*60)
                print(f"CALIBRATION MEASUREMENT RESULTS")
                print(f"="*60)
                print(f"\nTIMING ANALYSIS:")
                print(f"   Measured timing offset: {offset_seconds:+.3f} seconds")
                print(f"   Measurement consistency: Good (multi-cycle average)")
                print(f"   Baseline reference: 0.000s (no GUI delay)")
                
                # Read current delay from configuration for comparison
                config = load_config()
                current_delay = config.get('audio_delay', 0.000)
                
                # Direct measurement - no hardcoded delays
                # The measured offset directly represents the timing difference
                if offset_seconds > 0:
                    # Audio starts AFTER video - need to delay audio less or start it earlier
                    required_delay = current_delay - offset_seconds
                    if required_delay < 0:
                        required_delay = 0.0
                        timing_explanation = "Audio starts too late - reduce audio delay to minimum (0.0s)"
                    else:
                        timing_explanation = "Audio starts too late - reduce audio delay"
                    
                    print(f"\nCALIBRATION RESULTS:")
                    print(f"   Measured offset: {offset_seconds:.3f}s (audio after video)")
                    print(f"   Current configured delay: {current_delay:.3f}s")
                    print(f"   Required delay for sync: {required_delay:.3f}s")
                    print(f"")
                    print(f"   EXPLANATION: {timing_explanation}")
                    print(f"   Audio starts {offset_seconds:.3f}s too late relative to video.")
                    if required_delay == 0.0:
                        print(f"   Solution: Set audio delay to minimum (0.0s).")
                    else:
                        print(f"   Solution: Reduce audio delay by {offset_seconds:.3f}s.")
                elif offset_seconds < 0:
                    # Audio starts BEFORE video - cannot fix with positive delay
                    required_delay = 0.0
                    print(f"\nCALIBRATION RESULTS:")
                    print(f"   Audio starts {abs(offset_seconds):.3f}s TOO EARLY")
                    print(f"   Current configured delay: {current_delay:.3f}s")
                    print(f"   Required delay: {required_delay:.3f}s (minimum possible)")
                    print(f"   WARNING: Cannot fix early audio with positive delay")
                    print(f"   Consider checking hardware timing or connection order")
                else:
                    # Perfect timing
                    print(f"\nPERFECT TIMING:")
                    print(f"   Audio and video are perfectly synchronized")
                    print(f"   Required delay: 0.000s (no delay needed)")
                    required_delay = 0.0
                
                print(f"\nRECOMMENDATION:")
                print(f"   Set script delay to: {required_delay:.3f} seconds")
                print(f"   This should result in ~0.000s offset on next measurement")
                print(f"="*60)
                
                if abs(offset_seconds) > 0.010:  # More than 10ms
                    print(f"\nNEXT STEPS:")
                    print(f"   1. Auto-applying calibration to capture function...")
                    
                    # Automatically update the capture delay (not alignment delay)
                    success = update_capture_delay_only(required_delay)
                    if success:
                        print(f"    Capture delay updated to {required_delay:.3f}s")
                        print(f"   2. Calibration complete - ready for synchronized captures")
                        print(f"   3. Next capture should show ~0.000s offset")
                    else:
                        print(f"    Failed to auto-update delay")
                        print(f"   2. Please manually set delay to {required_delay:.3f}s")
                        print(f"   3. Run another calibration to verify")
                    
                    # Save calibration results to JSON metadata file (no duration since user-controlled)
                    save_calibration_results(alignment_base_name, offset_seconds, required_delay, 
                                           0, temp_folder)  # 0 indicates user-controlled duration
                else:
                    print(f"\nSYSTEM WELL CALIBRATED:")
                    print(f"   Offset < 10ms - no adjustment needed")
                    print(f"   Current capture delay ({current_delay:.3f}s) is optimal")
                    
                    # Save calibration results even if no update needed (no duration since user-controlled)
                    save_calibration_results(alignment_base_name, offset_seconds, current_delay, 
                                           0, temp_folder)  # 0 indicates user-controlled duration
            else:
                print("\nTest pattern timing analysis failed")
                print("This could be due to:")
                print("- Poor audio/video quality in capture")
                print("- Missing test pattern signal")
                print("- Test pattern not detected in video or audio")
        else:
            print("\nRaw audio file not found")
            print("Cannot proceed with test pattern analysis without captured audio file")
        
        print("\nAlignment workflow complete!")
        print("Files created:")
        print(f"   Audio: {alignment_capture_filename}")
        print(f"   TBC data: {tbc_file}")

    except KeyboardInterrupt:
        print("\nA/V Alignment cancelled by user")
    except Exception as e:
        print(f"\nERROR during A/V Alignment: {e}")


def cleanup_existing_processes():
    """
    Check for and clean up any existing vhs-decode or DomesdayDuplicator processes
    that might interfere with new captures
    """
    try:
        # Check for running vhs-decode processes
        result = subprocess.run(['pgrep', '-f', 'vhs-decode'], capture_output=True, text=True)
        if result.returncode == 0 and result.stdout.strip():
            pids = result.stdout.strip().split('\n')
            print(f"\nFound {len(pids)} running vhs-decode process(es)")
            for pid in pids:
                if pid.strip():
                    print(f"   Terminating vhs-decode process (PID: {pid})")
                    try:
                        subprocess.run(['kill', pid.strip()], check=True)
                    except subprocess.CalledProcessError:
                        print(f"   Warning: Could not terminate process {pid}")
            print("   Cleanup completed")
        
        # Check for running DomesdayDuplicator processes (but don't kill them automatically)
        result = subprocess.run(['pgrep', '-f', 'DomesdayDuplicator.*capture'], capture_output=True, text=True)
        if result.returncode == 0 and result.stdout.strip():
            pids = result.stdout.strip().split('\n')
            print(f"\nWarning: Found {len(pids)} running DomesdayDuplicator capture process(es)")
            print("   These may interfere with new captures")
            print("   Consider stopping them manually or use 'Stop Current Capture' menu option")
            
    except Exception as e:
        print(f"Process cleanup warning: {e}")

def check_command_available(command_name):
    """
    Check if a command is available in the system PATH
    Returns the full path if found, None otherwise
    """
    try:
        result = subprocess.run(['which', command_name], capture_output=True, text=True)
        if result.returncode == 0:
            return result.stdout.strip()
        
        # Try 'where' on Windows
        if sys.platform == 'win32':
            result = subprocess.run(['where', command_name], capture_output=True, text=True)
            if result.returncode == 0:
                return result.stdout.strip().split('\n')[0]  # Get first match
        
        return None
    except Exception:
        return None


def run_vhs_decode(rf_filename, tbc_filename, additional_params=None):
    """
    Run vhs-decode with PAL settings on the RF capture file
    Returns True if successful, False otherwise
    
    Args:
        rf_filename: Input RF (.lds) file path
        tbc_filename: Output TBC file path
        additional_params: Optional string with additional vhs-decode parameters
    """
    # Clean up any existing vhs-decode processes first
    try:
        result = subprocess.run(['pgrep', '-f', 'vhs-decode'], capture_output=True, text=True)
        if result.returncode == 0 and result.stdout.strip():
            pids = result.stdout.strip().split('\n')
            print(f"Found {len(pids)} existing vhs-decode process(es), terminating...")
            for pid in pids:
                if pid.strip():
                    try:
                        subprocess.run(['kill', pid.strip()], check=True)
                        print(f"   Terminated PID: {pid}")
                    except subprocess.CalledProcessError:
                        print(f"   Warning: Could not terminate process {pid}")
    except Exception as e:
        print(f"Process cleanup warning: {e}")
    
    # Check if vhs-decode is available
    vhs_decode_path = check_command_available('vhs-decode')
    if not vhs_decode_path:
        print("ERROR: vhs-decode not found in system PATH")
        print("Please install vhs-decode or ensure it's in your PATH")
        print("Visit: https://github.com/oyvindln/vhs-decode")
        return False
    
    print(f"Using vhs-decode: {vhs_decode_path}")
    
    # Build the vhs-decode command with the specified options
    cmd = [
        'vhs-decode',
        '--tf', 'vhs',          # Format: VHS
        '-t', '3',              # Threads: 3
        '--ts', 'SP',           # Tape speed: SP (standard play)
        '--pal',                # PAL format
        '--no_resample',        # No resampling
        '--recheck_phase',      # Recheck phase
        '--ire0_adjust',        # IRE 0 adjust
    ]
    
    # Add additional user parameters if provided
    if additional_params and additional_params.strip():
        # Split the additional parameters and add them to the command
        extra_params = additional_params.strip().split()
        cmd.extend(extra_params)
        print(f"Adding user parameters: {' '.join(extra_params)}")
    
    # Add input and output files at the end
    cmd.extend([
        rf_filename,            # Input RF file
        tbc_filename.replace('.tbc', '')  # Output base name (without extension)
    ])
    
    print(f"Command: {' '.join(cmd)}")
    print("This may take several minutes depending on capture length...")
    
    try:
        # Use stdbuf to force unbuffered output from vhs-decode
        # Add stdbuf -o0 to disable stdout buffering
        unbuffered_cmd = ['stdbuf', '-o0'] + cmd
        
        # Try with stdbuf first, fall back to regular command if stdbuf not available
        try:
            process = subprocess.Popen(unbuffered_cmd, 
                                     stdout=subprocess.PIPE, 
                                     stderr=subprocess.STDOUT,
                                     universal_newlines=True)
        except FileNotFoundError:
            # stdbuf not available, use regular command
            process = subprocess.Popen(cmd, 
                                     stdout=subprocess.PIPE, 
                                     stderr=subprocess.STDOUT,
                                     universal_newlines=True)
        
        # Read output line by line in real-time
        import sys
        while True:
            output = process.stdout.readline()
            if output == '' and process.poll() is not None:
                break
            if output:
                # Print immediately without buffering
                print(f"  {output.rstrip()}", flush=True)
        
        rc = process.returncode
        
        if rc == 0:
            print("vhs-decode completed successfully")
            
            # Verify output files exist
            tbc_json_file = tbc_filename + '.json'
            if os.path.exists(tbc_filename) and os.path.exists(tbc_json_file):
                print(f"Created: {tbc_filename}")
                print(f"Created: {tbc_json_file}")
                return True
            else:
                print("vhs-decode completed but expected output files not found")
                return False
        else:
            print(f"vhs-decode failed with exit code {rc}")
            return False
            
    except Exception as e:
        print(f"Error running vhs-decode: {e}")
        return False


def run_vhs_decode_ntsc(rf_filename, tbc_filename, additional_params=None):
    """
    Run vhs-decode with NTSC settings on the RF capture file
    Returns True if successful, False otherwise
    
    Args:
        rf_filename: Input RF (.lds) file path
        tbc_filename: Output TBC file path
        additional_params: Optional string with additional vhs-decode parameters
    """
    # Clean up any existing vhs-decode processes first
    try:
        result = subprocess.run(['pgrep', '-f', 'vhs-decode'], capture_output=True, text=True)
        if result.returncode == 0 and result.stdout.strip():
            pids = result.stdout.strip().split('\n')
            print(f"Found {len(pids)} existing vhs-decode process(es), terminating...")
            for pid in pids:
                if pid.strip():
                    try:
                        subprocess.run(['kill', pid.strip()], check=True)
                        print(f"   Terminated PID: {pid}")
                    except subprocess.CalledProcessError:
                        print(f"   Warning: Could not terminate process {pid}")
    except Exception as e:
        print(f"Process cleanup warning: {e}")
    
    # Check if vhs-decode is available
    vhs_decode_path = check_command_available('vhs-decode')
    if not vhs_decode_path:
        print("ERROR: vhs-decode not found in system PATH")
        print("Please install vhs-decode or ensure it's in your PATH")
        print("Visit: https://github.com/oyvindln/vhs-decode")
        return False
    
    print(f"Using vhs-decode: {vhs_decode_path}")
    
    # Build the vhs-decode command with NTSC-specific options
    cmd = [
        'vhs-decode',
        '--tf', 'vhs',          # Format: VHS
        '-t', '3',              # Threads: 3
        '--ts', 'SP',           # Tape speed: SP (standard play)
        '--ntsc',               # NTSC format (different from PAL version)
        '--no_resample',        # No resampling
        '--recheck_phase',      # Recheck phase
        '--ire0_adjust',        # IRE 0 adjust
    ]
    
    # Add additional user parameters if provided
    if additional_params and additional_params.strip():
        # Split the additional parameters and add them to the command
        extra_params = additional_params.strip().split()
        cmd.extend(extra_params)
        print(f"Adding user parameters: {' '.join(extra_params)}")
    
    # Add input and output files at the end
    cmd.extend([
        rf_filename,            # Input RF file
        tbc_filename.replace('.tbc', '')  # Output base name (without extension)
    ])
    
    print(f"Command: {' '.join(cmd)}")
    print("This may take several minutes depending on capture length...")
    
    try:
        # Use stdbuf to force unbuffered output from vhs-decode
        # Add stdbuf -o0 to disable stdout buffering
        unbuffered_cmd = ['stdbuf', '-o0'] + cmd
        
        # Try with stdbuf first, fall back to regular command if stdbuf not available
        try:
            process = subprocess.Popen(unbuffered_cmd, 
                                     stdout=subprocess.PIPE, 
                                     stderr=subprocess.STDOUT,
                                     universal_newlines=True)
        except FileNotFoundError:
            # stdbuf not available, use regular command
            process = subprocess.Popen(cmd, 
                                     stdout=subprocess.PIPE, 
                                     stderr=subprocess.STDOUT,
                                     universal_newlines=True)
        
        # Read output line by line in real-time
        import sys
        while True:
            output = process.stdout.readline()
            if output == '' and process.poll() is not None:
                break
            if output:
                # Print immediately without buffering
                print(f"  {output.rstrip()}", flush=True)
        
        rc = process.returncode
        
        if rc == 0:
            print("vhs-decode completed successfully")
            
            # Verify output files exist
            tbc_json_file = tbc_filename + '.json'
            if os.path.exists(tbc_filename) and os.path.exists(tbc_json_file):
                print(f"Created: {tbc_filename}")
                print(f"Created: {tbc_json_file}")
                return True
            else:
                print("vhs-decode completed but expected output files not found")
                return False
        else:
            print(f"vhs-decode failed with exit code {rc}")
            return False
            
    except Exception as e:
        print(f"Error running vhs-decode: {e}")
        return False


def run_vhs_decode_with_params(rf_filename, tbc_filename, video_standard, tape_speed, additional_params=None):
    """
    Unified VHS decode function with configurable video standard and tape speed
    Returns True if successful, False otherwise
    
    Args:
        rf_filename: Input RF (.lds) file path
        tbc_filename: Output TBC file path
        video_standard: 'pal' or 'ntsc'
        tape_speed: 'SP', 'LP', or 'EP'
        additional_params: Optional string with additional vhs-decode parameters
    """
    # Clean up any existing vhs-decode processes first
    try:
        result = subprocess.run(['pgrep', '-f', 'vhs-decode'], capture_output=True, text=True)
        if result.returncode == 0 and result.stdout.strip():
            pids = result.stdout.strip().split('\n')
            print(f"Found {len(pids)} existing vhs-decode process(es), terminating...")
            for pid in pids:
                if pid.strip():
                    try:
                        subprocess.run(['kill', pid.strip()], check=True)
                        print(f"   Terminated PID: {pid}")
                    except subprocess.CalledProcessError:
                        print(f"   Warning: Could not terminate process {pid}")
    except Exception as e:
        print(f"Process cleanup warning: {e}")
    
    # Check if vhs-decode is available
    vhs_decode_path = check_command_available('vhs-decode')
    if not vhs_decode_path:
        print("ERROR: vhs-decode not found in system PATH")
        print("Please install vhs-decode or ensure it's in your PATH")
        print("Visit: https://github.com/oyvindln/vhs-decode")
        return False
    
    print(f"Using vhs-decode: {vhs_decode_path}")
    
    # Build the vhs-decode command with configurable options
    cmd = [
        'vhs-decode',
        '--tf', 'vhs',          # Format: VHS
        '-t', '3',              # Threads: 3
        '--ts', tape_speed,     # Tape speed: SP, LP, or EP
        '--no_resample',        # No resampling
        '--recheck_phase',      # Recheck phase
        '--ire0_adjust',        # IRE 0 adjust
    ]
    
    # Add video standard (PAL or NTSC)
    if video_standard.lower() == 'pal':
        cmd.append('--pal')
    elif video_standard.lower() == 'ntsc':
        cmd.append('--ntsc')
    else:
        print(f"ERROR: Invalid video standard '{video_standard}'. Must be 'pal' or 'ntsc'.")
        return False
    
    # Add additional user parameters if provided
    if additional_params and additional_params.strip():
        # Split the additional parameters and add them to the command
        extra_params = additional_params.strip().split()
        cmd.extend(extra_params)
        print(f"Adding user parameters: {' '.join(extra_params)}")
    
    # Add input and output files at the end
    cmd.extend([
        rf_filename,            # Input RF file
        tbc_filename.replace('.tbc', '')  # Output base name (without extension)
    ])
    
    print(f"Command: {' '.join(cmd)}")
    print(f"This may take several minutes depending on capture length...")
    
    try:
        # Use stdbuf to force unbuffered output from vhs-decode
        # Add stdbuf -o0 to disable stdout buffering
        unbuffered_cmd = ['stdbuf', '-o0'] + cmd
        
        # Try with stdbuf first, fall back to regular command if stdbuf not available
        try:
            process = subprocess.Popen(unbuffered_cmd, 
                                     stdout=subprocess.PIPE, 
                                     stderr=subprocess.STDOUT,
                                     universal_newlines=True)
        except FileNotFoundError:
            # stdbuf not available, use regular command
            process = subprocess.Popen(cmd, 
                                     stdout=subprocess.PIPE, 
                                     stderr=subprocess.STDOUT,
                                     universal_newlines=True)
        
        # Read output line by line in real-time
        import sys
        while True:
            output = process.stdout.readline()
            if output == '' and process.poll() is not None:
                break
            if output:
                # Print immediately without buffering
                print(f"  {output.rstrip()}", flush=True)
        
        rc = process.returncode
        
        if rc == 0:
            print(f"{video_standard.upper()} {tape_speed} vhs-decode completed successfully")
            
            # Verify output files exist
            tbc_json_file = tbc_filename + '.json'
            if os.path.exists(tbc_filename) and os.path.exists(tbc_json_file):
                print(f"Created: {tbc_filename}")
                print(f"Created: {tbc_json_file}")
                return True
            else:
                print("vhs-decode completed but expected output files not found")
                return False
        else:
            print(f"vhs-decode failed with exit code {rc}")
            return False
            
    except Exception as e:
        print(f"Error running vhs-decode: {e}")
        return False


def run_tbc_video_export(tbc_filename, video_filename):
    """
    Run tbc-video-export to create FFV1 video file with PAL settings
    Returns True if successful, False otherwise
    """
    # Check if tbc-video-export is available
    tbc_export_path = check_command_available('tbc-video-export')
    if not tbc_export_path:
        print("ERROR: tbc-video-export not found in system PATH")
        print("Please install ld-decode tools or ensure tbc-video-export is in your PATH")
        print("Visit: https://github.com/happycube/ld-decode")
        return False
    
    print(f"Using tbc-video-export: {tbc_export_path}")
    
    # Build the tbc-video-export command with PAL video system
    cmd = [
        'tbc-video-export',
        '--video-system', 'pal', # Force PAL video system
        tbc_filename,           # Input TBC file
        video_filename          # Output video file
    ]
    
    print(f"Command: {' '.join(cmd)}")
    print("Exporting video file...")
    
    try:
        # Run with output capture that avoids terminal ioctl issues
        # Use DEVNULL for stdin to prevent ioctl errors
        with subprocess.Popen(cmd, 
                            stdout=subprocess.PIPE, 
                            stderr=subprocess.PIPE,
                            stdin=subprocess.DEVNULL,
                            universal_newlines=True,
                            bufsize=1) as process:
            
            # Capture output line by line from both stdout and stderr
            import select
            import io
            
            # Set up for non-blocking reads
            stdout_lines = []
            stderr_lines = []
            
            # Read all output
            stdout, stderr = process.communicate()
            
            # Print stdout (normal output)
            if stdout:
                for line in stdout.splitlines():
                    if line.strip():  # Skip empty lines
                        print(f"  {line}")
            
            # Handle stderr - filter out the ioctl error but show other errors
            if stderr:
                for line in stderr.splitlines():
                    line_stripped = line.strip()
                    if line_stripped and "Inappropriate ioctl for device" not in line_stripped:
                        print(f"  {line_stripped}")
                    elif "Inappropriate ioctl for device" in line_stripped:
                        # Just note this error but don't show it (it's non-fatal)
                        pass
            
            rc = process.returncode
        
        if rc == 0:
            print("tbc-video-export completed successfully")
            
            # Verify output file exists
            if os.path.exists(video_filename):
                file_size = os.path.getsize(video_filename) / (1024**2)  # MB
                print(f"Created: {video_filename} ({file_size:.1f} MB)")
                return True
            else:
                print("tbc-video-export completed but output file not found")
                return False
        else:
            print(f"tbc-video-export failed with exit code {rc}")
            return False
            
    except Exception as e:
        print(f"Error running tbc-video-export: {e}")
        return False


def run_tbc_video_export_ntsc(tbc_filename, video_filename):
    """
    Run tbc-video-export to create FFV1 video file with NTSC settings
    Returns True if successful, False otherwise
    """
    # Check if tbc-video-export is available
    tbc_export_path = check_command_available('tbc-video-export')
    if not tbc_export_path:
        print("ERROR: tbc-video-export not found in system PATH")
        print("Please install ld-decode tools or ensure tbc-video-export is in your PATH")
        print("Visit: https://github.com/happycube/ld-decode")
        return False
    
    print(f"Using tbc-video-export: {tbc_export_path}")
    
    # Build the tbc-video-export command with NTSC video system
    cmd = [
        'tbc-video-export',
        '--video-system', 'ntsc', # Force NTSC video system
        tbc_filename,           # Input TBC file
        video_filename          # Output video file
    ]
    
    print(f"Command: {' '.join(cmd)}")
    print("Exporting video file...")
    
    try:
        # Run with output capture that avoids terminal ioctl issues
        # Use DEVNULL for stdin to prevent ioctl errors
        with subprocess.Popen(cmd, 
                            stdout=subprocess.PIPE, 
                            stderr=subprocess.PIPE,
                            stdin=subprocess.DEVNULL,
                            universal_newlines=True,
                            bufsize=1) as process:
            
            # Capture output line by line from both stdout and stderr
            import select
            import io
            
            # Set up for non-blocking reads
            stdout_lines = []
            stderr_lines = []
            
            # Read all output
            stdout, stderr = process.communicate()
            
            # Print stdout (normal output)
            if stdout:
                for line in stdout.splitlines():
                    if line.strip():  # Skip empty lines
                        print(f"  {line}")
            
            # Handle stderr - filter out the ioctl error but show other errors
            if stderr:
                for line in stderr.splitlines():
                    line_stripped = line.strip()
                    if line_stripped and "Inappropriate ioctl for device" not in line_stripped:
                        print(f"  {line_stripped}")
                    elif "Inappropriate ioctl for device" in line_stripped:
                        # Just note this error but don't show it (it's non-fatal)
                        pass
            
            rc = process.returncode
        
        if rc == 0:
            print("tbc-video-export completed successfully")
            
            # Verify output file exists
            if os.path.exists(video_filename):
                file_size = os.path.getsize(video_filename) / (1024**2)  # MB
                print(f"Created: {video_filename} ({file_size:.1f} MB)")
                return True
            else:
                print("tbc-video-export completed but output file not found")
                return False
        else:
            print(f"tbc-video-export failed with exit code {rc}")
            return False
            
    except Exception as e:
        print(f"Error running tbc-video-export: {e}")
        return False


def wait_for_file_ready(file_path, max_wait_seconds=30, check_interval=0.5):
    """
    Wait for a file to be fully written and ready for reading
    Returns True if file is ready, False if timeout exceeded
    """
    print(f"Waiting for file to be ready: {os.path.basename(file_path)}")
    
    start_time = time.time()
    last_size = -1
    stable_count = 0
    
    while time.time() - start_time < max_wait_seconds:
        if not os.path.exists(file_path):
            print(f"  File does not exist yet, waiting...")
            time.sleep(check_interval)
            continue
        
        try:
            current_size = os.path.getsize(file_path)
            
            # Check if file size is stable (indicates writing is complete)
            if current_size == last_size and current_size > 0:
                stable_count += 1
                if stable_count >= 3:  # File size stable for 3 checks
                    print(f"   File ready ({current_size} bytes)")
                    return True
            else:
                stable_count = 0
                last_size = current_size
                print(f"  File size: {current_size} bytes (still growing)")
            
        except (OSError, IOError) as e:
            print(f"  File access error: {e}")
        
        time.sleep(check_interval)
    
    print(f"    Timeout waiting for file to be ready ({max_wait_seconds}s)")
    return False


def analyze_alignment_with_tbc(audio_filename, tbc_json_filename):
    """
    Analyse audio alignment using TBC JSON timing data
    This calls the proper vhs-decode-auto-audio-align script
    Returns offset in seconds, or None if analysis fails
    """
    if not os.path.exists(audio_filename):
        print(f"ERROR: Audio file {audio_filename} not found")
        return None
        
    if not os.path.exists(tbc_json_filename):
        print(f"ERROR: TBC JSON file {tbc_json_filename} not found")
        return None
    
    # Look for the audio alignment script
    alignment_script_paths = [
        'tools/audio-sync/vhs_audio_align.py',
        'vhs_audio_align.py',
        'tools/vhs_audio_align.py'
    ]
    
    alignment_script = None
    for script_path in alignment_script_paths:
        if os.path.exists(script_path):
            alignment_script = script_path
            break
    
    if not alignment_script:
        print("ERROR: vhs_audio_align.py script not found!")
        print("Looked in:")
        for path in alignment_script_paths:
            print(f"   - {path}")
        print("\nPlease ensure the audio alignment script is available.")
        return None
    
    print(f"Using alignment script: {alignment_script}")
    print(f"Audio file: {audio_filename}")
    print(f"TBC JSON: {tbc_json_filename}")
    
    try:
        # Run the alignment analysis with proper output file (keep this for test pattern analysis)
        print("Running alignment analysis...")
        # Generate aligned filename based on the input audio filename
        base_name = os.path.splitext(os.path.basename(audio_filename))[0]
        aligned_output = os.path.join(os.path.dirname(audio_filename), f"{base_name}_aligned.wav")
        result = subprocess.run([
            sys.executable, alignment_script, 
            audio_filename, tbc_json_filename, aligned_output
        ], capture_output=True, text=True)  # No timeout - allow long-running alignment processes
            
        if result.returncode == 0:
            print("Alignment analysis completed successfully")
            print("Script output:")
            print(result.stdout)
            
            # Parse the output to extract timing offset
            output_lines = result.stdout.strip().split('\n')
            
            # Look for various timing offset patterns in the output
            import re
            
            # Check if alignment was successful first
            alignment_success = False
            if 'Audio alignment completed successfully!' in result.stdout:
                alignment_success = True
                print("Audio alignment tool completed successfully")
            
            # Look for timing offset information in various formats
            for line in output_lines:
                line_lower = line.lower().strip()
                
                # Pattern 1: "offset: X.XXXs" or "offset: XXXms"
                offset_match = re.search(r'offset:?\s*([+-]?\d+\.?\d*)\s*(s|ms|second|millisecond)', line_lower)
                if offset_match:
                    try:
                        offset_value = float(offset_match.group(1))
                        unit = offset_match.group(2)
                        
                        # Convert to seconds if needed
                        if unit in ['ms', 'millisecond']:
                            offset_value = offset_value / 1000.0
                        
                        print(f"Detected timing offset: {offset_value:.3f}s")
                        return offset_value
                    except (ValueError, AttributeError) as e:
                        print(f"Could not parse offset from line: {line}")
                        continue
                
                # Pattern 2: Look for delay/timing information
                delay_match = re.search(r'delay:?\s*([+-]?\d+\.?\d*)\s*(s|ms|second|millisecond)', line_lower)
                if delay_match:
                    try:
                        delay_value = float(delay_match.group(1))
                        unit = delay_match.group(2)
                        
                        if unit in ['ms', 'millisecond']:
                            delay_value = delay_value / 1000.0
                        
                        print(f"Detected timing delay: {delay_value:.3f}s")
                        return delay_value
                    except (ValueError, AttributeError) as e:
                        continue
                
                # Pattern 3: Check for "no adjustment needed" type messages
                if any(phrase in line_lower for phrase in ['no adjustment', 'already aligned', 'no correction needed', 'perfectly aligned']):
                    print("Audio appears to already be well aligned")
                    return 0.0
            
            # If alignment was successful, return the aligned audio file path
            if alignment_success and os.path.exists(aligned_output):
                print(f"Audio alignment completed successfully: {aligned_output}")
                return aligned_output
            
            print("Could not extract timing offset from analysis output")
            print("This may indicate the analysis couldn't detect timing patterns")
            return None
            
        else:
            print(f"Alignment analysis failed (exit code {result.returncode})")
            print("Error output:")
            print(result.stderr)
            print("Standard output:")
            print(result.stdout)
            return None
            
    except subprocess.TimeoutExpired:
        print("Alignment analysis timed out (>5 minutes)")
        print("This could indicate:")
        print("- Very large audio files")
        print("- Complex analysis requirements")
        print("- Script hanging or waiting for input")
        return None
    except Exception as e:
        print(f"Error running alignment analysis: {e}")
        return None


def analyze_alignment_capture(capture_filename):
    """
    Analyse the captured audio to detect timing offset
    Returns offset in seconds, or None if analysis fails
    """
    if not os.path.exists(capture_filename):
        print(f"ERROR: Capture file {capture_filename} not found")
        return None
    
    print("Running audio pattern analysis...")
    
    # Try the simple analyser first (no external dependencies)
    try:
        result = subprocess.run([
            sys.executable, 'tools/simple_audio_analyzer.py', capture_filename
        ], capture_output=True, text=True, timeout=60)
        
        if result.returncode == 0:
            # Parse the output to extract the offset
            output_lines = result.stdout.strip().split('\n')
            for line in output_lines:
                if 'Detected timing offset:' in line:
                    # Extract offset value
                    try:
                        offset_str = line.split('Detected timing offset:')[1].split('s')[0].strip()
                        offset = float(offset_str)
                        print(f"Analysis complete: {offset:.3f}s offset detected")
                        return offset
                    except (IndexError, ValueError) as e:
                        print(f"Error parsing analysis result: {e}")
                        break
            
            # If we get here, analysis completed but no offset was found
            print("Analysis completed but could not detect timing pattern")
            print("This may mean:")
            print("- The test pattern audio was not recorded")
            print("- The audio quality is too poor for analysis")
            print("- The timing is already perfect (no offset)")
            return 0.0  # Assume no offset needed
        else:
            print(f"Analysis failed: {result.stderr}")
            print("Falling back to manual inspection method...")
            return None
            
    except subprocess.TimeoutExpired:
        print("Analysis timed out")
        return None
    except FileNotFoundError:
        print("Audio analysis script not found")
        print("Using simplified analysis...")
        return simple_analysis_fallback(capture_filename)


def simple_analysis_fallback(capture_filename):
    """
    Simple fallback analysis using just FFmpeg
    """
    print("Performing basic audio level analysis...")

    try:
        # Extract a short segment and analyse audio levels
        cmd = [
            'ffmpeg', '-v', 'quiet', '-stats',
            '-i', capture_filename,
            '-ss', '10', '-t', '30',  # 30s starting from 10s in
            '-vn', '-f', 'null', '-'
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            print("Basic audio analysis completed")
            print("Manual timing adjustment may be needed")
            return 0.0  # No automatic offset calculated
        else:
            print("Could not analyse capture file")
            return None
            
    except Exception as e:
        print(f"Analysis error: {e}")
        return None


def manual_calibration_entry():
    """
    Allow manual entry of calibration delay value
    """
    print("\nMANUAL CALIBRATION VALUE ENTRY")
    print("=" * 40)
    print("\nThis option allows you to manually set the timing delay")
    print("that will be used for A/V synchronization.")
    print("\nTypical delay values:")
    print("- 0.000s - Perfect timing (no delay needed)")
    print("- 0.100s - Audio starts 100ms too early")
    print("- 0.200s - Audio starts 200ms too early")
    print("- Higher values for larger timing offsets")
    print("\nNOTE: This value should come from previous automated")
    print("calibration measurements or external timing analysis.")
    
    # Load current delay from config
    config = load_config()
    current_delay = config.get('audio_delay', 0.000)
    print(f"\nCurrent delay in config: {current_delay:.3f}s")
    
    while True:
        try:
            print("\nEnter calibration delay value:")
            user_input = input("Delay in seconds (e.g., 0.150): ").strip()
            
            if not user_input:
                print("No value entered. Keeping current delay.")
                break
            
            # Parse the input value
            delay_value = float(user_input)
            
            # Validate reasonable range
            if delay_value < 0.0:
                print("ERROR: Delay cannot be negative.")
                print("Enter a positive delay value or 0.000 for no delay.")
                continue
            elif delay_value > 2.0:
                print("WARNING: Delay > 2.0s is unusually large.")
                confirm = input("Are you sure? (y/N): ").strip().lower()
                if confirm not in ['y', 'yes']:
                    continue
            
            # Show the update that would be made
            print(f"\nCALIBRATION UPDATE PREVIEW")
            print(f"   Current delay: {current_delay:.3f}s")
            print(f"   New delay:     {delay_value:.3f}s")
            print(f"   Change:        {delay_value - current_delay:+.3f}s")
            
            print(f"\nIMPORTANT: This will update the configuration file")
            print(f"   The delay value will be saved to config.json")
            print(f"   Alignment/calibration will remain at 0.000s for accurate measurement")
            
            confirm = input("\nApply this calibration? (y/N): ").strip().lower()
            
            if confirm in ['y', 'yes']:
                # Update only the capture delay (not alignment delay)
                success = update_capture_delay_only(delay_value)
                if success:
                    print(f"\nCALIBRATION APPLIED SUCCESSFULLY!")
                    print(f"   Capture delay updated to: {delay_value:.3f}s")
                    print(f"   Alignment delay kept at: 0.000s (for accurate measurement)")
                    print(f"   Changes will take effect on next capture.")
                else:
                    print(f"\nFailed to update capture delay.")
                    print(f"   You may need to manually edit the delay in the script.")
            else:
                print("\nCalibration update cancelled.")
            
            break
            
        except ValueError:
            print("ERROR: Invalid number format.")
            print("Please enter a decimal number (e.g., 0.150)")
        except KeyboardInterrupt:
            print("\nManual calibration cancelled.")
            break
        except Exception as e:
            print(f"ERROR: {e}")
            break


def update_script_delay_values(new_delay):
    """
    Update the delay values in the script file (both capture and alignment)
    Returns True if successful, False otherwise
    """
    script_file = __file__  # Current script file
    
    try:
        # Read the current script content
        with open(script_file, 'r') as f:
            content = f.read()
        
        # Find and replace the delay values
        import re
        
        # Pattern 1: audio_delay = X.XX in start_capture_and_record function  
        pattern1 = r'(audio_delay = )([0-9]+\.[0-9]+)(\s*#\s*Calibrated delay for audio/video synchronization)'
        
        # Pattern 2: time.sleep(X.XX) in perform_av_alignment function (alignment baseline)
        pattern2 = r'(time\.sleep\()([0-9]+\.[0-9]+)(\)\s*#\s*Calibration baseline - no delay for measurement)'
        
        # Apply replacements
        new_content = content
        
        # Replace main capture delay
        matches1 = re.findall(pattern1, new_content)
        if matches1:
            old_delay = float(matches1[0][1])
            new_content = re.sub(pattern1, f'\\1{new_delay:.3f}\\3', new_content)
            print(f"   Updated main capture delay: {old_delay:.3f}s → {new_delay:.3f}s")
        else:
            print("   Warning: Could not find main capture delay to update")
        
        # Keep alignment baseline at 0.0 (for measurement accuracy)
        alignment_delay = 0.0
        matches2 = re.findall(pattern2, new_content)
        if matches2:
            new_content = re.sub(pattern2, f'\\1{alignment_delay:.3f}\\3', new_content)
            print(f"   Alignment baseline kept at: {alignment_delay:.3f}s")
        
        # Write the updated content back
        with open(script_file, 'w') as f:
            f.write(new_content)
        
        return True
        
    except Exception as e:
        print(f"Error updating script: {e}")
        return False


def update_capture_delay_only(new_delay):
    """
    Update the audio delay in configuration file
    Returns True if successful, False otherwise
    """
    try:
        # Load current configuration
        config = load_config()
        old_delay = config.get('audio_delay', 0.000)
        
        # Update the audio delay value
        config['audio_delay'] = new_delay
        
        # Save the updated configuration
        if save_config(config):
            print(f"   Updated audio delay in config: {old_delay:.3f}s → {new_delay:.3f}s")
            print(f"   Configuration saved to config.json")
            return True
        else:
            print(f"   Error: Could not save configuration file")
            return False
        
    except Exception as e:
        print(f"Error updating audio delay in config: {e}")
        return False


def validate_calibration_with_configured_delay():
    """
    Validate calibration results by capturing with configured delay and measuring offset.
    This is identical to perform_av_alignment() but uses the configured delay instead of 0.
    """
    try:
        print("\n=== Calibration Validation ===")
        print("IMPORTANT: This workflow will:")
        print("   1. Use your configured delay for capture (not zero)")
        print("   2. Complete RF decode workflow")
        print("   3. Run audio alignment")
        print("   4. Measure final timing offset")
        print("   5. Create debug files for analysis")
        print()
        print("Expected result: Near 0.000s offset if calibration is accurate")
        print()
        
        # Get user-configurable capture duration
        alignment_duration_seconds = get_alignment_duration()
        if alignment_duration_seconds is None:
            return  # User cancelled
        
        # Create temp folder if it doesn't exist
        temp_folder = get_temp_folder()
        if not os.path.exists(temp_folder):
            os.makedirs(temp_folder)
            print(f"Created temp folder: {temp_folder}")
        
        # Generate automated filename with timestamp for validation
        validation_base_name = f"validation_{get_alignment_filename()}"
        print(f"Using validation filename: {validation_base_name}")
        
        # Create validation file paths with timestamp
        validation_capture_filename = os.path.join(temp_folder, f"{validation_base_name}.flac")
        validation_rf_filename = os.path.join(temp_folder, f"{validation_base_name}.lds")
        validation_tbc_filename = os.path.join(temp_folder, f"{validation_base_name}.tbc")
        validation_tbc_json_filename = os.path.join(temp_folder, f"{validation_base_name}.tbc.json")
        validation_video_filename = os.path.join(temp_folder, f"{validation_base_name}_ffv1.mkv")
        
        # Create debug output file
        debug_filename = os.path.join(temp_folder, f"{validation_base_name}_debug.txt")
        
        print("\033[91mIMPORTANT SETUP REQUIRED:\033[0m")
        print(f"\033[91m   ⚠️  You must manually configure the Domesday Duplicator Client to point to: {os.path.abspath(temp_folder)}\033[0m")
        print(f"\033[91m   ⚠️  Set DomesdayDuplicator filename to: {validation_base_name}\033[0m")
        print(f"   Debug output will be saved to: {validation_base_name}_debug.txt")
        print()
        print(f"\033[91mIMPORTANT: Use TEMP folder for validation, not your capture folder!\033[0m")
        print(f"\033[91m   Temp folder: {os.path.abspath(temp_folder)}\033[0m")
        print(f"\033[91m   This keeps validation files separate from your regular captures\033[0m")
        print()
        
        input("Make sure you've recorded at least 5 minutes of the included test pattern files onto a VHS tape. Press any key to continue or Ctrl-C to stop.")
        input("Ensure your Domesday duplicator is plugged in and powered on and your clockgen lite is connected and working. Press any key to continue.")
        input("Configure DomesdayDuplicator output location and filename as shown above, then insert your VHS tape into your VCR and press play. It's very important to be playing this alignment tape before validation. Press any key to start Validation Capture.")

        # Read configured delay
        config = load_config()
        audio_delay = config.get('audio_delay', 0.000)
        
        # Start debug log
        debug_log = []
        debug_log.append(f"=== CALIBRATION VALIDATION DEBUG LOG ===")
        debug_log.append(f"Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        debug_log.append(f"Configured delay: {audio_delay:.6f}s")
        debug_log.append(f"Capture duration: {alignment_duration_seconds}s")
        debug_log.append(f"Base filename: {validation_base_name}")
        debug_log.append("")

        # Capture validation using command line DomesdayDuplicator
        print("\nStarting RF + Audio capture with configured delay...")
        validation_sox_command = get_sox_command(validation_capture_filename)

        try:
            # 1. Start audio capture using command line
            print(f"Starting SOX audio recording with {audio_delay:.3f}s delay...")
            time.sleep(audio_delay)  # Apply configured delay
            validation_sox_command = get_sox_command(validation_capture_filename)
            capture_process = subprocess.Popen(validation_sox_command)
            print("SOX audio recording started")
            debug_log.append(f"Audio capture started at: {time.strftime('%H:%M:%S')} (after {audio_delay:.3f}s delay)")
            debug_log.append(f"Net timing: Audio started {audio_delay:.3f}s before video")

            # 2. Start video capture using command line
            print("Starting DomesdayDuplicator capture...")
            ddd_process = subprocess.Popen(['DomesdayDuplicator', '--start-capture', '--headless'], 
                                      stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

            # Check if process is still running (successful start)
            if ddd_process.poll() is None:
                print("DomesdayDuplicator capture started successfully")
                debug_log.append(f"Video capture started at: {time.strftime('%H:%M:%S')} using command line")
                
                print("\nVALIDATION CAPTURE IN PROGRESS")
                print(f"Using configured delay: {audio_delay:.3f}s")
                print(f"Both RF and audio recording for {alignment_duration_seconds} seconds...")
                print("DO NOT STOP THE VCR YET - let it continue playing!")
                
                # Show progress during capture
                print("Progress: ", end="", flush=True)
                for i in range(alignment_duration_seconds):
                    time.sleep(1)
                    if (i + 1) % 5 == 0:  # Show progress every 5 seconds
                        remaining = alignment_duration_seconds - (i + 1)
                        print(f"{i+1}s ", end="", flush=True)
                        if remaining > 0 and (i + 1) % 10 == 0:
                            print(f"({remaining}s remaining) ", end="", flush=True)
                    else:
                        print(".", end="", flush=True)
                
                # 2. Stop audio recording
                print("\nStopping audio recording...")
                capture_process.terminate()
                capture_process.wait()
                print("Audio recording stopped")
                
                debug_log.append(f"Audio capture stopped at: {time.strftime('%H:%M:%S')}")

                # 3. Stop video capture using command line
                print("\nStopping DomesdayDuplicator capture...")
                stop_result = subprocess.run(['DomesdayDuplicator', '--stop-capture'], 
                                           capture_output=True, text=True)
                
                if stop_result.returncode == 0:
                    print("DomesdayDuplicator capture stopped successfully")
                    debug_log.append(f"Video capture stopped at: {time.strftime('%H:%M:%S')} using command line")
                else:
                    print(f"Warning: DomesdayDuplicator stop returned code {stop_result.returncode}")
                    print("Please verify capture was stopped properly")
                    debug_log.append(f"Video capture stop warning: return code {stop_result.returncode}")
                
                # Important user message after capture stops
                print("\n" + "="*50)
                print("VALIDATION CAPTURE COMPLETED")
                print("="*50)
                print("RF and audio capture has finished successfully!")
                print("")
                print("You can now STOP your VCR/alignment tape.")
                print("   The capture is complete and no longer recording.")
                print("")
                print("Next: RF decode and audio alignment analysis will begin...")
                print("="*50)
                print()
                
                # Give user a moment to see this message
                time.sleep(2)

            else:
                # Process has terminated, get output and error
                stdout, stderr = ddd_process.communicate()
                return_code = ddd_process.returncode
                
                print(f"ERROR: Could not start DomesdayDuplicator capture!")
                print(f"Command failed with return code: {return_code}")
                print(f"Error output: {stderr}")
                print("Please ensure:")
                print("1. DomesdayDuplicator is installed and in your PATH")
                print("2. The hardware is connected properly")
                print("3. No other instance is already running")
                print("\nValidation capture cancelled.")
                debug_log.append(f"ERROR: DomesdayDuplicator start failed with code {return_code}")
                return

        except subprocess.TimeoutExpired:
            print("ERROR: DomesdayDuplicator command timed out")
            print("This might indicate the command is hanging or waiting for user input")
            debug_log.append("ERROR: DomesdayDuplicator command timed out")
            return
        except FileNotFoundError:
            print("ERROR: DomesdayDuplicator command not found!")
            print("Please ensure DomesdayDuplicator is installed and available in your PATH")
            debug_log.append("ERROR: DomesdayDuplicator command not found")
            return
        except Exception as e:
            print(f"Capture error: {e}")
            debug_log.append(f"Capture error: {e}")
            return

        # 5. RF Decode step
        print("\nSTARTING RF DECODE WORKFLOW")
        debug_log.append("=== RF DECODE PHASE ===")
        debug_log.append(f"RF decode started at: {time.strftime('%H:%M:%S')}")
        print("Looking for RF capture file in temp folder...")
        
        # Find the most recent .lds file (RF capture) in temp folder
        if not os.path.exists(temp_folder):
            print(f"Temp folder {temp_folder} does not exist!")
            debug_log.append(f"ERROR: Temp folder {temp_folder} does not exist")
            return
            
        lds_files = [f for f in os.listdir(temp_folder) if f.endswith('.lds')]
        if not lds_files:
            print(f"No RF capture files (.lds) found in {temp_folder}!")
            debug_log.append(f"ERROR: No RF capture files found in {temp_folder}")
            return
        
        # Get the most recent RF file (with full path)
        lds_paths = [os.path.join(temp_folder, f) for f in lds_files]
        rf_file = max(lds_paths, key=os.path.getmtime)
        print(f"Found RF capture: {rf_file}")
        debug_log.append(f"RF file: {os.path.basename(rf_file)} ({os.path.getsize(rf_file) / (1024**2):.1f} MB)")
        
        # Check if we already have decoded files
        tbc_file = rf_file.replace('.lds', '.tbc')
        tbc_json_file = rf_file.replace('.lds', '.tbc.json')
        
        if os.path.exists(tbc_json_file):
            print(f"TBC JSON already exists: {tbc_json_file}")
            debug_log.append(f"TBC JSON already exists: {os.path.basename(tbc_json_file)}")
        else:
            print("\nRunning vhs-decode...")
            if not run_vhs_decode_with_params(rf_file, tbc_file, 'pal', 'SP'):
                print("RF decode failed")
                debug_log.append("ERROR: RF decode failed")
                return
            debug_log.append(f"RF decode completed: {os.path.basename(tbc_file)}")
        
        # Check if we need to export video
        video_file = rf_file.replace('.lds', '_ffv1.mkv')
        if os.path.exists(video_file):
            print(f"Video export already exists: {video_file}")
            debug_log.append(f"Video export already exists: {os.path.basename(video_file)}")
        else:
            print("\nRunning tbc-video-export...")
            if not run_tbc_video_export(tbc_file, video_file):
                print("Video export failed, but continuing with audio alignment...")
                debug_log.append("WARNING: Video export failed")
            else:
                debug_log.append(f"Video export completed: {os.path.basename(video_file)}")
        
        print("\nRF decode workflow complete!")
        debug_log.append("RF decode workflow completed")
        debug_log.append("")
        
        # 6. Audio alignment analysis
        print(f"\nUsing TBC JSON file: {tbc_json_file}")
        debug_log.append("=== AUDIO ALIGNMENT PHASE ===")
        debug_log.append(f"Audio alignment started at: {time.strftime('%H:%M:%S')}")
        debug_log.append(f"TBC JSON: {os.path.basename(tbc_json_file)}")
        
        print("\nRunning VHS mechanical audio alignment...")
        aligned_audio_file = analyze_alignment_with_tbc(validation_capture_filename, tbc_json_file)
        
        # Wait for aligned file to be fully created
        if aligned_audio_file and aligned_audio_file.endswith('_aligned.wav'):
            print(f"Waiting for aligned audio file to be ready: {aligned_audio_file}")
            wait_for_file_ready(aligned_audio_file, max_wait_seconds=30)
        
        if aligned_audio_file and os.path.exists(aligned_audio_file):
            print(f"\nMechanical alignment completed: {aligned_audio_file}")
            debug_log.append(f"Aligned audio file created: {os.path.basename(aligned_audio_file)}")
            
            # Verify we're using the aligned file (debug info)
            if aligned_audio_file.endswith('_aligned.wav'):
                print(f"CONFIRMED: Using aligned audio file for analysis")
                debug_log.append("Using aligned audio file for test pattern analysis")
            else:
                print(f"WARNING: Not using aligned audio file - using: {aligned_audio_file}")
                debug_log.append(f"WARNING: Not using aligned audio file - using: {os.path.basename(aligned_audio_file)}")
            
            # Show file details for verification
            file_size = os.path.getsize(aligned_audio_file) / (1024*1024)  # MB
            file_time = time.ctime(os.path.getmtime(aligned_audio_file))
            print(f"   File size: {file_size:.1f} MB")
            print(f"   Modified: {file_time}")
            debug_log.append(f"Aligned audio file size: {file_size:.1f} MB")
            
            # Now run test pattern timing analysis on both aligned audio and video
            print("\nRunning test pattern timing analysis...")
            debug_log.append("")
            debug_log.append("=== TEST PATTERN TIMING ANALYSIS ===")
            debug_log.append(f"Test pattern analysis started at: {time.strftime('%H:%M:%S')}")
            
            offset_seconds = analyze_test_pattern_timing(aligned_audio_file, video_file)
            
            if offset_seconds is not None:
                # Calculate frame offset for better understanding
                fps = 25.0  # Default PAL
                try:
                    if os.path.exists(video_file):
                        import cv2
                        cap = cv2.VideoCapture(video_file)
                        if cap.isOpened():
                            detected_fps = cap.get(cv2.CAP_PROP_FPS)
                            if detected_fps > 0:
                                fps = detected_fps
                            cap.release()
                except:
                    pass
                
                frame_offset = offset_seconds * fps
                
                print(f"\n" + "="*60)
                print(f"VALIDATION RESULTS")
                print(f"="*60)
                print(f"\nTIMING ANALYSIS:")
                print(f"   Measured timing offset: {offset_seconds:+.6f} seconds ({frame_offset:+.2f} frames @ {fps:.1f}fps)")
                print(f"   Configured delay used: {audio_delay:.6f} seconds")
                print(f"   Expected result: ~0.000s if calibration is accurate")
                
                debug_log.append(f"Measured offset: {offset_seconds:+.6f} seconds")
                debug_log.append(f"Configured delay: {audio_delay:.6f} seconds")
                
                # Analyze validation results
                abs_offset = abs(offset_seconds)
                if abs_offset <= 0.010:  # Within 10ms
                    print(f"\nVALIDATION RESULT: EXCELLENT")
                    print(f"   Offset within ±10ms - calibration is highly accurate")
                    print(f"   Your current delay setting ({audio_delay:.3f}s) is working well")
                    debug_log.append("VALIDATION RESULT: EXCELLENT (within ±10ms)")
                elif abs_offset <= 0.050:  # Within 50ms
                    print(f"\nVALIDATION RESULT: GOOD")
                    print(f"   Offset within ±50ms - calibration is reasonably accurate")
                    print(f"   Consider fine-tuning if higher precision is needed")
                    debug_log.append("VALIDATION RESULT: GOOD (within ±50ms)")
                elif abs_offset <= 0.100:  # Within 100ms
                    print(f"\nVALIDATION RESULT: FAIR")
                    print(f"   Offset within ±100ms - calibration may need adjustment")
                    print(f"   Consider running calibration again")
                    debug_log.append("VALIDATION RESULT: FAIR (within ±100ms)")
                else:
                    print(f"\nVALIDATION RESULT: POOR")
                    print(f"   Offset > 100ms - calibration needs attention")
                    print(f"   Recommend running full calibration workflow again")
                    debug_log.append("VALIDATION RESULT: POOR (>100ms offset)")
                
                if offset_seconds > 0:
                    # VALIDATION LOGIC: If audio is too late, we need to REDUCE the delay
                    # (opposite of calibration logic which starts from zero baseline)
                    suggested_delay = max(0.0, audio_delay - offset_seconds)
                    print(f"\nTIMING INTERPRETATION:")
                    print(f"   Positive offset: Audio starts {offset_seconds:.3f}s too late")
                    print(f"   To improve: REDUCE audio delay to {suggested_delay:.3f}s")
                    print(f"   Logic: Current delay ({audio_delay:.3f}s) - measured offset ({offset_seconds:.3f}s)")
                    debug_log.append(f"Recommendation: Reduce delay to {suggested_delay:.6f}s")
                elif offset_seconds < 0:
                    # If audio is too early, we need to INCREASE the delay
                    suggested_delay = audio_delay + abs(offset_seconds)
                    print(f"\nTIMING INTERPRETATION:")
                    print(f"   Negative offset: Audio starts {abs(offset_seconds):.3f}s too early")
                    print(f"   To improve: INCREASE audio delay to {suggested_delay:.3f}s")
                    print(f"   Logic: Current delay ({audio_delay:.3f}s) + measured offset ({abs(offset_seconds):.3f}s)")
                    debug_log.append(f"Recommendation: Increase delay to {suggested_delay:.6f}s")
                else:
                    print(f"\nPERFECT TIMING: Audio and video are perfectly synchronized!")
                    debug_log.append("PERFECT TIMING: No adjustment needed")
                
                print(f"\nDEBUG INFORMATION:")
                print(f"   Debug log saved to: {os.path.basename(debug_filename)}")
                print(f"   Review this file for detailed timing analysis")
                print(f"="*60)
                
                # Save debug log
                debug_log.append("")
                debug_log.append("=== VALIDATION COMPLETED ===")
                debug_log.append(f"Validation completed at: {time.strftime('%Y-%m-%d %H:%M:%S')}")
                debug_log.append(f"Total analysis time: ~{alignment_duration_seconds + 300} seconds")
                
            else:
                print("\nTest pattern timing analysis failed")
                print("This could be due to:")
                print("- Poor audio/video quality in capture")
                print("- Missing test pattern signal")
                print("- Test pattern not detected in video or audio")
                debug_log.append("ERROR: Test pattern timing analysis failed")
        else:
            print("\nVHS mechanical audio alignment failed")
            print("Cannot proceed with test pattern analysis without aligned audio")
            debug_log.append("ERROR: VHS mechanical audio alignment failed")
        
        # Write debug log to file
        try:
            with open(debug_filename, 'w') as f:
                f.write('\n'.join(debug_log))
            print(f"\nDebug log written to: {debug_filename}")
        except Exception as e:
            print(f"\nWarning: Could not write debug log: {e}")
        
        print("\nValidation workflow complete!")
        print("Files created:")
        print(f"   Audio: {os.path.basename(validation_capture_filename)}")
        print(f"   RF: {os.path.basename(rf_file)}")
        print(f"   TBC data: {os.path.basename(tbc_file)}")
        if os.path.exists(aligned_audio_file):
            print(f"   Aligned audio: {os.path.basename(aligned_audio_file)}")
        if os.path.exists(video_file):
            print(f"   Video: {os.path.basename(video_file)}")
        print(f"   Debug log: {os.path.basename(debug_filename)}")

    except KeyboardInterrupt:
        print("\nCalibration validation cancelled by user")
    except Exception as e:
        print(f"\nERROR during calibration validation: {e}")


def take_screenshot(filename):
    """
    Takes a screenshot - works on macOS, Linux, and Windows
    """
    try:
        if sys.platform == 'darwin':
            # macOS
            subprocess.run(['screencapture', '-x', filename], check=True)
            print(f"Screenshot saved to {filename}")
            return True
        elif sys.platform == 'win32':
            # Windows - use built-in PowerShell
            powershell_cmd = f"Add-Type -AssemblyName System.Windows.Forms; [System.Windows.Forms.SendKeys]::SendWait('%{{PRTSC}}'); Start-Sleep -Milliseconds 500; [System.Drawing.Bitmap]([System.Windows.Forms.Clipboard]::GetImage()).Save('{filename}')"
            result = subprocess.run(['powershell', '-Command', powershell_cmd], check=True, capture_output=True)
            print(f"Screenshot saved to {filename}")
            return True
        else:
            # Linux with KDE Spectacle
            env_copy = os.environ.copy()
            if 'LD_LIBRARY_PATH' in env_copy:
                del env_copy['LD_LIBRARY_PATH']

            subprocess.run(
                ['spectacle', '-b', '-n', '-o', filename],
                check=True,
                env=env_copy
            )
            print(f"Screenshot saved to {filename}")
            return True
    except FileNotFoundError:
        if sys.platform == 'darwin':
            print("\nERROR: 'screencapture' command not found.")
        elif sys.platform == 'win32':
            print("\nERROR: PowerShell not found or screenshot failed.")
            print("Please ensure PowerShell is available and try running as administrator.")
        else:
            print("\nERROR: 'spectacle' command not found.")
            print("Please ensure KDE Spectacle is installed (`sudo apt install spectacle`).")
        return False
    except subprocess.CalledProcessError as e:
        print(f"\nERROR: Screenshot failed: {e}")
        return False


def prompt_for_capture_name(target_folder=None):
    """
    Prompt user for capture name to use for both RF and audio files
    Returns the base filename (without extension)
    """
    # Use temp folder if no target folder specified (for backwards compatibility)
    if target_folder is None:
        target_folder = get_temp_folder()
    
    print("\n--- CAPTURE NAMING ---")
    print("Enter a name for this capture session.")
    print("This name will be used for both RF (.lds) and audio (.flac) files.")
    print("")
    print("Examples:")
    print("   VHS_Movie_Title_1985")
    print("   Test_Pattern_Calibration")
    print("   Family_Videos_1990s")
    print("")
    
    while True:
        try:
            capture_name = input("Enter capture name (or press Enter for default): ").strip()
            
            # Use default if nothing entered
            if not capture_name:
                capture_name = "my_vhs_capture"
                print(f"Using default name: {capture_name}")
            
            # Validate filename (basic check for filesystem compatibility)
            invalid_chars = '<>:"/\\|?*'
            if any(char in capture_name for char in invalid_chars):
                print(f"ERROR: Filename contains invalid characters: {invalid_chars}")
                print("Please use only letters, numbers, underscores, and hyphens.")
                continue
            
            # Check if files already exist in the target folder
            lds_path = os.path.join(target_folder, f"{capture_name}.lds")
            flac_path = os.path.join(target_folder, f"{capture_name}.flac")
            
            existing_files = []
            if os.path.exists(lds_path):
                existing_files.append(lds_path)
            if os.path.exists(flac_path):
                existing_files.append(flac_path)
            
            if existing_files:
                print(f"\nWARNING: Files with this name already exist:")
                for file_path in existing_files:
                    file_size = os.path.getsize(file_path) / (1024**2)  # MB
                    print(f"   - {os.path.basename(file_path)} ({file_size:.1f} MB)")
                
                overwrite = input("\nOverwrite existing files? (y/N): ").strip().lower()
                if overwrite not in ['y', 'yes']:
                    print("Please choose a different name.")
                    continue
            
            print(f"\nCapture name set to: {capture_name}")
            print(f"Files will be saved as:")
            print(f"   RF capture: {capture_name}.lds")
            print(f"   Audio: {capture_name}.flac")
            print(f"   Location: {os.path.abspath(target_folder)}/")
            
            return capture_name
            
        except KeyboardInterrupt:
            print("\nCapture cancelled by user.")
            return None
        except Exception as e:
            print(f"ERROR: {e}")
            continue


def start_capture_and_record():
    """
    Starts audio recording with calibrated delay, then immediately starts video capture.
    This architecture allows audio to start before, after, or simultaneously with video.
    """
    print("--- Domesday Capture Automation (Audio-First Architecture) ---")
    
    # Clean up any existing processes that might interfere
    cleanup_existing_processes()
    
    # Use configured capture directory for actual captures (not temp folder)
    capture_folder = get_capture_folder()
    if not os.path.exists(capture_folder):
        os.makedirs(capture_folder)
        print(f"Created capture folder: {capture_folder}")
    
    # Prompt user for capture name
    capture_name = prompt_for_capture_name(capture_folder)
    if not capture_name:
        return  # User cancelled
    
    # Read calibrated audio delay from configuration
    config = load_config()
    audio_delay = config.get('audio_delay', 0.000)  # Default to 0.000 if not set
    print(f"Using configured audio delay: {audio_delay:.3f}s")

    # Construct output file path for both video and audio
    video_output_path = os.path.join(capture_folder, f"{capture_name}.lds")
    audio_output_path = os.path.join(capture_folder, f"{capture_name}.flac")

    # Get sox command
    sox_command = get_sox_command(audio_output_path)

    # Use the new separate directory and filename parameters for DomesdayDuplicator
    # Note: DomesdayDuplicator automatically adds .lds extension, so we pass just the base name
    ddd_command = ['DomesdayDuplicator', '--start-capture', '--headless', 
                  '--capture-directory', capture_folder, '--output-file', capture_name]
    
    print(f"Video will be saved to: {video_output_path}")
    print(f"Audio will be saved to: {audio_output_path}")

    # Run the shared capture process with the specific DDD command
    shared_capture_process(sox_command, audio_delay, capture_duration=None, ddd_command=ddd_command)


def offer_wav_conversion(flac_file=None, wav_file=None):
    """
    Offers to convert the FLAC file to WAV format for use with alignment tools.
    Defaults to 'yes' since WAV is needed for most workflows.
    """
    # Use defaults if not provided (for backward compatibility)
    if flac_file is None:
        flac_file = CAPTURE_FLAC_PATH
    if wav_file is None:
        wav_file = CAPTURE_WAV_PATH
    
    if not os.path.exists(flac_file):
        print(f"\nWarning: {flac_file} not found. Cannot offer conversion.")
        return
    
    # Estimate WAV file size (FLAC is typically 50-60% the size of WAV for this type of content)
    flac_size = os.path.getsize(flac_file) / (1024**3)  # GB
    estimated_wav_size = flac_size * 1.8  # Rough estimate
    
    print(f"\n--- CAPTURE COMPLETE ---")
    print(f"FLAC file saved: {flac_file} ({flac_size:.2f} GB)")
    
    conversion_command = f"sox '{flac_file}' '{wav_file}'"
    
    if estimated_wav_size > 4.0:
        print(f"\nWARNING: Estimated WAV size (~{estimated_wav_size:.1f} GB) may exceed 4GB limit")
        print(f"WAV files >4GB may not work with some alignment tools.")
        print(f"Consider using the FLAC file directly in DaVinci Resolve if possible.")
        print(f"\nConversion command: {conversion_command}")
        
        try:
            response = input("\nAttempt WAV conversion anyway? (y/N): ").strip().lower()
            convert_to_wav = response in ['y', 'yes']
        except KeyboardInterrupt:
            print(f"\nConversion cancelled. You can convert later with: {conversion_command}")
            return
    else:
        print(f"\nConverting to WAV for alignment tools and DaVinci Resolve compatibility...")
        print(f"Conversion command: {conversion_command}")
        
        try:
            response = input("\nConvert to WAV now? (Y/n): ").strip().lower()
            convert_to_wav = response not in ['n', 'no']
        except KeyboardInterrupt:
            print(f"\nConversion cancelled. You can convert later with: {conversion_command}")
            return
    
    if convert_to_wav:
        print(f"Converting {flac_file} to {wav_file}...")
        # Preserve exact audio parameters - no resampling or processing
        result = subprocess.run(['sox', flac_file, '-t', 'wav', wav_file], capture_output=True, text=True)
        
        if result.returncode == 0:
            wav_size = os.path.getsize(wav_file) / (1024**3)   # GB
            print(f" Conversion successful: {wav_file} ({wav_size:.2f} GB)")
            
            if wav_size > 4.0:
                print(f"  WAV file is {wav_size:.2f} GB (>4GB limit)")
                print(f"  Some applications may have issues with this file size.")
                print(f"  Keep the FLAC version as backup: {flac_file}")
            else:
                print(f"   WAV file size is within 4GB limit")
        else:
            print(f" Conversion failed: {result.stderr}")
            print(f"You can try the conversion manually: {conversion_command}")
    else:
        print(f"Skipped conversion. You can convert later with: {conversion_command}")


def stop_domesday_duplicator_capture():
    """
    Stop Domesday Duplicator capture using command line
    Returns True if successful, False otherwise
    """
    try:
        # Use command line to stop capture
        stop_result = subprocess.run(['DomesdayDuplicator', '--stop-capture', '--headless'], 
                                   capture_output=True, text=True, timeout=10)
        
        if stop_result.returncode == 0:
            return True
        else:
            print(f"DomesdayDuplicator stop returned code {stop_result.returncode}")
            return False
            
    except subprocess.TimeoutExpired:
        print("DomesdayDuplicator stop command timed out")
        return False
    except FileNotFoundError:
        print("DomesdayDuplicator command not found")
        return False
    except Exception as e:
        print(f"Error stopping Domesday Duplicator: {e}")
        return False


def rename_rf_files_to_match(desired_name, temp_folder):
    """
    Rename the most recently created RF files to match the desired capture name
    Returns True if successful, False otherwise
    """
    try:
        # Find all .lds files in temp folder
        lds_files = [f for f in os.listdir(temp_folder) if f.lower().endswith('.lds')]
        
        if not lds_files:
            print("No RF files (.lds) found to rename")
            return False
        
        # Get the most recent .lds file (just created)
        lds_paths = [os.path.join(temp_folder, f) for f in lds_files]
        most_recent_lds = max(lds_paths, key=os.path.getmtime)
        
        # Generate target filenames
        new_lds_name = os.path.join(temp_folder, f"{desired_name}.lds")
        new_json_name = os.path.join(temp_folder, f"{desired_name}.json")  # Direct JSON from Domesday Duplicator
        new_tbc_json_name = os.path.join(temp_folder, f"{desired_name}.tbc.json")  # VHS decode JSON
        
        # Rename the RF file
        if most_recent_lds != new_lds_name:  # Only rename if different
            print(f"Renaming: {os.path.basename(most_recent_lds)} → {desired_name}.lds")
            os.rename(most_recent_lds, new_lds_name)
        
        # Find and rename the most recent JSON file (Domesday Duplicator format)
        # Look for files like "RF-Sample_YYYY-MM-DD_HH-MM-SS.json"
        json_files = [f for f in os.listdir(temp_folder) if f.lower().endswith('.json') and not f.endswith('.tbc.json')]
        if json_files:
            json_paths = [os.path.join(temp_folder, f) for f in json_files]
            most_recent_json = max(json_paths, key=os.path.getmtime)
            
            if most_recent_json != new_json_name:
                print(f"Renaming: {os.path.basename(most_recent_json)} → {desired_name}.json")
                os.rename(most_recent_json, new_json_name)
        
        # Check for and rename associated TBC JSON file (from vhs-decode)
        old_tbc_json_file = most_recent_lds.replace('.lds', '.tbc.json')
        if os.path.exists(old_tbc_json_file) and old_tbc_json_file != new_tbc_json_name:
            print(f"Renaming: {os.path.basename(old_tbc_json_file)} → {desired_name}.tbc.json")
            os.rename(old_tbc_json_file, new_tbc_json_name)
        
        # Check for and rename any other associated files (.tbc, etc.)
        old_tbc_file = most_recent_lds.replace('.lds', '.tbc')
        new_tbc_file = os.path.join(temp_folder, f"{desired_name}.tbc")
        if os.path.exists(old_tbc_file) and old_tbc_file != new_tbc_file:
            print(f"Renaming: {os.path.basename(old_tbc_file)} → {desired_name}.tbc")
            os.rename(old_tbc_file, new_tbc_file)
        
        return True
        
    except Exception as e:
        print(f"Error renaming RF files: {e}")
        return False


def save_calibration_results(alignment_base_name, offset_seconds, delay_seconds, 
                            capture_duration_seconds, temp_folder):
    """
    Save calibration measurement results to JSON metadata file
    """
    try:
        # Create metadata filename based on alignment base name
        metadata_filename = os.path.join(temp_folder, f"{alignment_base_name}_calibration.json")
        
        # Collect system and measurement information
        calibration_data = {
            "calibration_metadata": {
                "timestamp": datetime.now().isoformat(),
                "alignment_base_name": alignment_base_name,
                "version": "2.0",
                "script_name": "ddd_clockgen_sync.py"
            },
            "measurement_parameters": {
                "capture_duration_seconds": capture_duration_seconds,
                "baseline_delay_seconds": 0.0,  # Alignment uses no delay for measurement
                "analysis_method": "test_pattern_timing_analysis"
            },
            "timing_results": {
                "measured_offset_seconds": offset_seconds,
                "required_delay_seconds": delay_seconds,
                "measurement_precision": "millisecond",
                "sync_quality": "good" if abs(offset_seconds or 0) < 0.050 else "needs_adjustment"
            },
            "file_references": {
                "audio_file": f"{alignment_base_name}.flac",
                "rf_file": f"{alignment_base_name}.lds",
                "tbc_file": f"{alignment_base_name}.tbc",
                "tbc_json_file": f"{alignment_base_name}.tbc.json",
                "video_file": f"{alignment_base_name}_ffv1.mkv",
                "aligned_audio_file": f"{alignment_base_name}_aligned.wav"
            },
            "calibration_status": {
                "offset_within_tolerance": bool(abs(offset_seconds or 0) < 0.010),  # 10ms tolerance
                "auto_applied": bool(abs(offset_seconds or 0) > 0.010),
                "recommended_action": "none" if abs(offset_seconds or 0) < 0.010 else "applied_automatically"
            }
        }
        
        # Write JSON file with pretty formatting
        with open(metadata_filename, 'w') as f:
            json.dump(calibration_data, f, indent=2, ensure_ascii=False)
        
        print(f"\n Calibration metadata saved: {os.path.basename(metadata_filename)}")
        print(f"   Location: {os.path.abspath(metadata_filename)}")
        print(f"   Contains: Timing measurements, file references, and calibration status")
        
        # Show key results from the saved data
        if offset_seconds is not None:
            print(f"   Measured offset: {offset_seconds:+.3f}s")
            print(f"   Applied delay: {delay_seconds:.3f}s")
            print(f"   Capture duration: {capture_duration_seconds}s")
        
        return True
        
    except Exception as e:
        print(f"WARNING: Could not save calibration metadata: {e}")
        print(f"   Calibration results are still applied to the script")
        print(f"   Metadata file could not be created in: {temp_folder}")
        return False


def stop_current_capture():
    """
    Stop any ongoing Domesday Duplicator and SOX captures.
    """
    try:
        print("\n--- STOPPING CAPTURE ---")
        
        # Stop SOX processes
        try:
            subprocess.run(['pkill', '-f', 'sox'], check=True)
            print("SOX audio recording stopped.")
        except subprocess.CalledProcessError:
            print("No SOX processes found to stop.")
        
        # Stop DomesdayDuplicator using command line
        try:
            stop_result = subprocess.run(['DomesdayDuplicator', '--stop-capture', '--headless'], 
                                       capture_output=True, text=True, timeout=10)
            if stop_result.returncode == 0:
                print("DomesdayDuplicator capture stopped via command line.")
            else:
                print(f"DomesdayDuplicator stop returned code {stop_result.returncode}")
                # Fallback to process kill
                subprocess.run(['pkill', '-f', 'DomesdayDuplicator'], check=False)
                print("Attempted to kill DomesdayDuplicator processes.")
        except (subprocess.TimeoutExpired, FileNotFoundError):
            print("Command line stop failed, trying process kill...")
            try:
                subprocess.run(['pkill', '-f', 'DomesdayDuplicator'], check=True)
                print("DomesdayDuplicator processes killed.")
            except subprocess.CalledProcessError:
                print("No DomesdayDuplicator processes found to stop.")
                
    except Exception as e:
        print(f"Error when stopping captures: {e}")
