#!/usr/bin/env python3
"""
DdD Sync Capture - Main Menu System
Enhanced menu providing access to all project functionality
"""

import os
import sys
import subprocess
import time
import shutil
from datetime import datetime

# Import project workflow management
from project_workflow import show_project_workflow_status

# Import process management utilities
try:
    from process_killer import run_interactive_process_killer
except ImportError:
    print("Warning: process_killer module not found")
    run_interactive_process_killer = None

# Import our cross-platform utilities
try:
    from platform_utils import detector, tools, runner, paths
except ImportError:
    # Fallback if platform_utils not available
    print("Warning: platform_utils not found, using basic platform detection")
    import platform
    
    class BasicDetector:
        def __init__(self):
            self.system = platform.system().lower()
            self.is_windows = self.system == 'windows'
            self.is_macos = self.system == 'darwin'
            self.is_linux = self.system == 'linux'
            self.platform_name = platform.system()
    
    class BasicRunner:
        def __init__(self, detector):
            self.detector = detector
        
        def clear_screen(self):
            os.system('cls' if self.detector.is_windows else 'clear')
        
        def run_command(self, cmd, **kwargs):
            return subprocess.run(cmd, **kwargs)
    
    detector = BasicDetector()
    runner = BasicRunner(detector)
    tools = None
    paths = None

def clear_screen():
    """Clear the terminal screen"""
    if 'runner' in globals() and runner is not None:
        runner.clear_screen()
    else:
        os.system('cls' if os.name == 'nt' else 'clear')

def display_header():
    """Display the project header"""
    print("=" * 60)
    print("    DdD Sync Capture - Complete Workflow System")
    print("=" * 60)
    print("  VHS Archival with Domesday Duplicator")
    print("  + Clockgen Lite + Automated Audio/Video Sync")
    print("=" * 60)

def display_main_menu():
    """Display the main menu options"""
    print("\nMAIN MENU")
    print("=" * 30)
    print("1. Capture New Video")
    print("2. VHS-Decode")
    print("3. A/V Calibration")
    print("4. Configuration")
    print("5. Check Dependencies")
    print("6. Help & Documentation")
    print("7. Exit")
    print("=" * 30)

def create_sync_test_videos():
    """Main sync test video creation menu"""
    clear_screen()
    display_header()
    print("\nSYNC TEST VIDEO CREATION")
    print("=" * 35)
    print("Create test videos for VHS archival workflows")
    print()
    
    # Check if test patterns exist first
    pal_pattern = "media/Test Patterns/testchartpal.tif"
    ntsc_pattern = "media/Test Patterns/testchartntsc.tif"
    
    if not os.path.exists(pal_pattern) or not os.path.exists(ntsc_pattern):
        print("Error: Test pattern images not found!")
        print(f"   Missing: {pal_pattern if not os.path.exists(pal_pattern) else ntsc_pattern}")
        print("\nRequired files:")
        print("- media/Test Patterns/testchartpal.tif")
        print("- media/Test Patterns/testchartntsc.tif")
        print("\nPlease ensure test pattern files are in media/Test Patterns/")
        input("\nPress Enter to return to menu...")
        return
    
    print("VIDEO CREATION OPTIONS")
    print("=" * 30)
    print("1. Calibration Videos (1s ON/OFF pattern)")
    print("2. VHS Sync Calibration Pattern (35s Cycles) (Recommended)")
    print("3. Long-Form Timecode Generator (Full Tape Duration)")
    print("4. Create Belle Nuit PAL Test Chart")
    print("5. Create Belle Nuit NTSC Test Chart")
    print("6. Create Custom Test Pattern Videos")
    print("7. Return to Main Menu")
    
    choice = input("\nSelect option (1-7): ").strip()
    
    if choice == '1':
        create_calibration_videos()
    elif choice == '2':
        create_vhs_pattern_generator()
    elif choice == '3':
        create_vhs_timecode_pattern()
    elif choice == '4':
        create_belle_nuit_chart_single('PAL')
    elif choice == '5':
        create_belle_nuit_chart_single('NTSC')
    elif choice == '6':
        create_custom_test_pattern_menu()
    elif choice == '7':
        return
    else:
        print("\nInvalid selection")
        time.sleep(1)
        input("\nPress Enter to return to menu...")

def create_calibration_videos():
    """Create the calibration sync test videos with 1s ON/OFF pattern"""
    clear_screen()
    display_header()
    print("\nCREATE CALIBRATION VIDEOS")
    print("=" * 35)
    print("Creates 1-hour test videos with 1-second ON/OFF patterns")
    print("for precise audio/video synchronisation calibration.")
    print()
    print("Features:")
    print("   • Video: Test pattern visible 1s, black 1s (repeating)")
    print("   • Audio: 1kHz tone 1s, silence 1s (repeating)")
    print("   • Duration: 1 hour each (PAL and NTSC)")
    print("   • Purpose: VHS capture timing calibration")
    print()
    
    # Check if test patterns exist
    pal_pattern = "media/Test Patterns/testchartpal.tif"
    ntsc_pattern = "media/Test Patterns/testchartntsc.tif"
    
    if not os.path.exists(pal_pattern) or not os.path.exists(ntsc_pattern):
        print("Error: Test pattern images not found!")
        print(f"   Missing: {pal_pattern if not os.path.exists(pal_pattern) else ntsc_pattern}")
        print("\nPlease ensure test pattern files are in media/Test Patterns/")
        input("\nPress Enter to return to menu...")
        return
    
    # Ensure mp4 directory exists
    os.makedirs("media/mp4", exist_ok=True)
    
    # Check if output files already exist
    pal_output = "media/mp4/pal_sync_test_1hour.mp4"
    ntsc_output = "media/mp4/ntsc_sync_test_1hour.mp4"
    
    if os.path.exists(pal_output) or os.path.exists(ntsc_output):
        print("Warning: Output files already exist!")
        if os.path.exists(pal_output):
            print(f"   - {pal_output}")
        if os.path.exists(ntsc_output):
            print(f"   - {ntsc_output}")
        
        choice = input("\nOverwrite existing files? (y/N): ").strip().lower()
        if choice not in ['y', 'yes']:
            print("Operation cancelled.")
            input("Press Enter to return to menu...")
            return
    
    print("\nStarting video creation...")
    print("This will take several minutes to complete.")
    print("Creating PAL and NTSC versions...")
    
    try:
        # Run the creation script
        result = subprocess.run([
            sys.executable, 'tools/create_sync_test.py'
        ], capture_output=True, text=True, timeout=1800)  # 30 minute timeout
        
        if result.returncode == 0:
            print("\nSUCCESS! Sync test videos created.")
            print("Files created:")
            if os.path.exists(pal_output):
                size_mb = os.path.getsize(pal_output) / (1024*1024)
                print(f"   - {pal_output} ({size_mb:.1f} MB)")
            if os.path.exists(ntsc_output):
                size_mb = os.path.getsize(ntsc_output) / (1024*1024)
                print(f"   - {ntsc_output} ({size_mb:.1f} MB)")
        else:
            print(f"\nError creating videos: {result.stderr}")
            
    except subprocess.TimeoutExpired:
        print("\nError: Video creation timed out (>30 minutes)")
    except Exception as e:
        print(f"\nError: {e}")
    
def create_vhs_pattern_generator():
    """Create VHS Pattern with Test Charts + Timecode using the new pattern generator"""
    clear_screen()
    display_header()
    print("\nVHS PATTERN WITH 4-STEP CYCLE")
    print("=" * 40)
    print("Create 4-step VHS test pattern for sync validation:")
    print()
    print("4-Step Cycle Structure (35-second cycles):")
    print("   1. 3s: Test chart + 1kHz tone")
    print("   2. 1s: Black screen (no audio) - Visual cue for recording")
    print("   3. 30s: Timecode - Timing reference")
    print("   4. 1s: Black screen (no audio) - Visual cue cycle finished")
    print("   Then loops back to step 1")
    print()
    print("This pattern is ideal for VHS validation as it provides:")
    print("   • Audio markers (1kHz tone) at cycle start for validation lock-on")
    print("   • Clear visual cues for VHS recording management")
    print("   • Consistent timing for measuring misaligned frame audio")
    print()
    
    # Get format preference
    while True:
        format_choice = input("Select format - P)AL (25fps) or N)TSC (29.97fps) or B)oth [P]: ").strip().upper()
        if not format_choice:
            format_choice = 'P'
        
        if format_choice in ['P', 'PAL']:
            formats = ['PAL']
            break
        elif format_choice in ['N', 'NTSC']:
            formats = ['NTSC']
            break
        elif format_choice in ['B', 'BOTH']:
            formats = ['PAL', 'NTSC']
            break
        else:
            print("Invalid choice. Please enter P, N, or B.")
    
    # Get number of cycles with helpful suggestions
    print("\nCycle count suggestions:")
    print("  Default: 10 cycles (5.8 minutes)")
    print("  30-min tape: 51 cycles")
    print("  1-hour tape: 103 cycles")
    print("  3-hour tape: 309 cycles")
    print("  4-hour tape: 411 cycles")
    print()
    
    while True:
        try:
            cycles_input = input("Number of 35-second cycles [10]: ").strip()
            if not cycles_input:
                num_cycles = 10  # Default 10 cycles = 7.5 minutes
            else:
                num_cycles = int(cycles_input)
            
            if num_cycles < 1:
                print("Must have at least 1 cycle")
                continue
            elif num_cycles > 500:
                print("Very large number of cycles - this will create a long video")
                confirm = input("Continue anyway? (y/N): ").strip().lower()
                if confirm not in ['y', 'yes']:
                    continue
            
            break
            
        except ValueError:
            print("Please enter a valid number")
    
    total_duration = num_cycles * 35
    print(f"\nTotal duration: {num_cycles} cycles × 35s = {total_duration}s ({total_duration/60:.1f} minutes)")
    
    # Ensure mp4 directory exists
    os.makedirs("media/mp4", exist_ok=True)
    
    # Check for existing files
    output_files = []
    for fmt in formats:
        output_file = f"media/mp4/vhs_pattern_{fmt.lower()}_{num_cycles}cycles_35s.mp4"
        output_files.append((fmt, output_file))
        
        if os.path.exists(output_file):
            size_mb = os.path.getsize(output_file) / (1024*1024)
            print(f"\nWarning: {fmt} output file already exists!")
            print(f"   {output_file} ({size_mb:.1f} MB)")
    
    if any(os.path.exists(output_file) for _, output_file in output_files):
        overwrite = input("\nOverwrite existing files? (y/N): ").strip().lower()
        if overwrite not in ['y', 'yes']:
            print("Operation cancelled.")
            input("\nPress Enter to return to menu...")
            return
    
    print(f"\nCreating VHS pattern(s) for {', '.join(formats)}...")
    print(f"Pattern: {num_cycles} cycles of 35 seconds each")
    print("This will take several minutes to complete.")
    print()
    
    try:
        # Check if pattern generator exists
        generator_script = "tools/timecode-generator/vhs_pattern_generator.py"
        
        if not os.path.exists(generator_script):
            print(f"ERROR: VHS pattern generator not found at {generator_script}")
            print("Please ensure the VHS pattern generator tool is available.")
            input("\nPress Enter to return to menu...")
            return
        
        # Create each format
        success_count = 0
        for fmt, output_file in output_files:
            print(f"\nGenerating {fmt} VHS pattern...")
            
            try:
                # Run the pattern generator using the current Python executable
                # This ensures we use the same Python environment (conda) as the main menu
                result = subprocess.run([
                    sys.executable, generator_script,
                    '--cycles', str(num_cycles),
                    '--format', fmt,
                    '--output', output_file
                ], capture_output=True, text=True, timeout=7200)  # 2 hour timeout
                
                if result.returncode == 0:
                    if os.path.exists(output_file):
                        size_mb = os.path.getsize(output_file) / (1024*1024)
                        print(f"SUCCESS: {fmt} VHS pattern created ({size_mb:.1f} MB)")
                        
                        # Check for metadata file
                        metadata_file = output_file.replace('.mp4', '_metadata.json')
                        if os.path.exists(metadata_file):
                            print(f"         Metadata: {os.path.basename(metadata_file)}")
                        
                        success_count += 1
                    else:
                        print(f"ERROR: {fmt} output file was not created")
                else:
                    print(f"ERROR creating {fmt} pattern:")
                    if result.stderr:
                        print(f"  {result.stderr.strip()}")
                    if result.stdout:
                        print(f"  {result.stdout.strip()}")
                        
            except subprocess.TimeoutExpired:
                print(f"ERROR: {fmt} generation timed out (>2 hours)")
            except Exception as e:
                print(f"ERROR generating {fmt} pattern: {e}")
        
        if success_count > 0:
            print(f"\nVHS pattern creation completed!")
            print(f"Successfully created {success_count}/{len(formats)} pattern(s)")
            print()
            print("USAGE INSTRUCTIONS:")
            print("1. Record these MP4 files to VHS tape")
            print("2. Capture back with Domesday Duplicator + audio interface")
            print("3. Use validation script to analyze the structured timecode sections")
            print("4. Get precise sync measurements with easy section identification")
        else:
            print(f"\nFailed to create VHS patterns.")
            print("Please check dependencies and try again.")
            
    except KeyboardInterrupt:
        print("\nOperation cancelled by user.")
    except Exception as e:
        print(f"\nUnexpected error: {e}")
    
    input("\nPress Enter to return to menu...")

def create_belle_nuit_chart_single(format_type):
    """Create a single Belle Nuit static test chart (PAL or NTSC)"""
    clear_screen()
    display_header()
    print("\nCREATE BELLE NUIT STATIC CHARTS")
    print("=" * 40)
    print("Creates static test chart videos for hardware testing")
    print("and general video work - no flashing patterns.")
    print()
    print("Features:")
    print("   • Video: Constant test pattern display (no ON/OFF)")
    print("   • Audio: Continuous 1kHz tone (for audio testing)")
    print("   • Duration: 200 minutes (perfect for E-180 tapes)")
    print("   • Purpose: Hardware testing, tape creation, equipment setup")
    print()
    
    # Check if test patterns exist
    pattern_map = {
        "PAL": "media/Test Patterns/testchartpal.tif",
        "NTSC": "media/Test Patterns/testchartntsc.tif"
    }
    
    # Ensure mp4 directory exists
    os.makedirs("media/mp4", exist_ok=True)
    
    pattern_file = pattern_map[format_type]
    output_file = f"media/mp4/{format_type.lower()}_belle_nuit.mp4"
    
    if not os.path.exists(pattern_file):
        print("Error: Test pattern image not found!")
        print(f"   Missing: {pattern_file}")
        print("\nPlease ensure test pattern files are in media/Test Patterns/")
        input("\nPress Enter to return to menu...")
        return
    
    # Check if output files already exist
    if os.path.exists(output_file):
        print("Warning: Output files already exist!")
        print(f"   - {output_file}")
        
        choice = input("\nOverwrite existing files? (y/N): ").strip().lower()
        if choice not in ['y', 'yes']:
            print("Operation cancelled.")
            return
    
    print("\nStarting static chart creation...")
    print("This will take a few minutes to complete.")
    print(f"Creating {format_type} version...")
    
    try:
        # Import and use the create_static_chart function
        sys.path.append('tools')
        from create_belle_nuit_charts import create_static_chart
        create_static_chart(output_file, pattern_file, format_type)
        print("\nSUCCESS! Belle Nuit static chart created.")
        size_mb = os.path.getsize(output_file) / (1024*1024)
        print(f"   - {output_file} ({size_mb:.1f} MB)")
    except Exception as e:
        print(f"\nError creating static chart: {e}")

def create_dvd_isos():
    """Create DVD ISOs from MP4s"""
    while True:
        clear_screen()
        display_header()
        print("\nCREATE DVD ISOS")
        print("=" * 25)
        print("Convert MP4 sync test videos to DVD-Video ISOs")
        print("that can be burned and played on hardware DVD players.")
        print()
        
        print("This process will:")
        print("1. Scan for all available MP4 test pattern files")
        print("2. Convert MP4s to DVD-compatible MPEG-2")
        print("3. Create proper VIDEO_TS structure")
        print("4. Generate ISO files ready for burning")
        print()
        
        print("DVD ISO OPTIONS")
        print("=" * 20)
        print("1. Create DVD ISOs from MP4s")
        print("2. Return to Main Menu")
        
        choice = input("\nSelect option (1-2): ").strip()
        
        if choice == '1':
            try:
                # Run the ISO creation script interactively
                subprocess.run([sys.executable, 'tools/create_iso_from_mp4.py'])
                
            except KeyboardInterrupt:
                print("\nOperation cancelled by user")
            except Exception as e:
                print(f"\nError: {e}")
            
            input("\nPress Enter to continue...")
        elif choice == '2':
            break  # Return to main menu
        else:
            print("\nInvalid selection")
            time.sleep(1)

def vhs_audio_alignment():
    """Run the VHS audio alignment tool"""
    clear_screen()
    display_header()
    print("\nVHS AUDIO ALIGNMENT TOOL")
    print("=" * 35)
    print("Align VHS audio captures using SOX analysis")
    print("Wrapper for advanced audio synchronisation workflows.")
    print()
    
    # First check dependencies
    print("Checking dependencies...")
    try:
        result = subprocess.run([sys.executable, 'tools/audio-sync/vhs_audio_align.py', '--check-deps'], 
                              capture_output=True, text=True)
        if result.returncode != 0:
            print("Dependency check failed!")
            print(result.stdout)
            print(result.stderr)
            input("\nPress Enter to return to menu...")
            return
        else:
            print("All dependencies are available")
            
    except Exception as e:
        print(f"Error checking dependencies: {e}")
        input("\nPress Enter to return to menu...")
        return
    
    print("\nAUDIO ALIGNMENT OPTIONS")
    print("=" * 30)
    print("1. View Usage Instructions")
    print("2. Process Audio Files (requires WAV + TBC JSON)")
    print("3. Demo Mode (uses test files)")
    print("4. Return to Main Menu")
    
    choice = input("\nSelect option (1-4): ").strip()
    
    if choice == '1':
        print("\nVHS AUDIO ALIGNMENT USAGE")
        print("=" * 35)
        print("This tool aligns VHS audio captures with RF timing data.")
        print()
        print("Required Files:")
        print("   • Input WAV: Audio captured from VHS (e.g., my_capture.wav)")
        print("   • TBC JSON: RF timing data (e.g., RF-Sample_2025-07-21.tbc.json)")
        print("   • Output WAV: Where aligned audio will be saved")
        print()
        print("Command Line Usage:")
        print("   python tools/audio-sync/vhs_audio_align.py input.wav timing.tbc.json output.wav")
        print()
        print("Workflow:")
        print("   1. Capture VHS RF data with Domesday Duplicator → creates TBC JSON")
        print("   2. Capture audio separately with Clockgen Lite → creates WAV")
        print("   3. Use this tool to align audio timing with RF data")
        print("   4. Result: Perfectly synchronised audio for archival")
        
    elif choice == '2':
        print("\nPROCESS AUDIO FILES")
        print("=" * 25)
        print("Enter the paths to your audio and timing files:")
        print()
        
        input_wav = input("Input WAV file path: ").strip()
        if not input_wav:
            print("No input file specified")
        elif not os.path.exists(input_wav):
            print(f"File not found: {input_wav}")
        else:
            tbc_json = input("TBC JSON file path: ").strip()
            if not tbc_json:
                print("No TBC file specified")
            elif not os.path.exists(tbc_json):
                print(f"File not found: {tbc_json}")
            else:
                output_wav = input("Output WAV file path: ").strip()
                if not output_wav:
                    print("No output file specified")
                else:
                    print(f"\nStarting audio alignment...")
                    try:
                        subprocess.run([sys.executable, 'tools/audio-sync/vhs_audio_align.py', 
                                      input_wav, tbc_json, output_wav])
                    except KeyboardInterrupt:
                        print("\nOperation cancelled by user")
                    except Exception as e:
                        print(f"\nError: {e}")
                        
    elif choice == '3':
        print("\nDEMO MODE")
        print("=" * 15)
        print("This will create test files and demonstrate the alignment process.")
        print("Note: This is for testing the tool interface only.")
        print()
        
        demo_choice = input("Continue with demo? (y/N): ").strip().lower()
        if demo_choice in ['y', 'yes']:
            print("\nCreating test files...")
            # Create minimal test files
            test_dir = "tools/audio-sync/test"
            os.makedirs(test_dir, exist_ok=True)
            
            test_wav = os.path.join(test_dir, "test_input.wav")
            test_json = os.path.join(test_dir, "test_timing.tbc.json")
            test_output = os.path.join(test_dir, "test_output.wav")
            
            # Create minimal test WAV (1 second of silence)
            try:
                subprocess.run([
                    'sox', '-n', test_wav, 
                    'synth', '1', 'sine', '0',  # 1 second of silence
                    'channels', '2'  # Stereo
                ], check=True)
                print(f"Created test WAV: {test_wav}")
                
                # Create minimal JSON file
                with open(test_json, 'w') as f:
                    f.write('{"test": true, "format": "tbc", "sample_rate": 78125}')
                print(f"Created test JSON: {test_json}")
                
                print(f"\nRunning alignment test...")
                print("This will likely fail as we're using fake data, but tests the pipeline.")
                
                try:
                    result = subprocess.run([
                        sys.executable, 'tools/audio-sync/vhs_audio_align.py',
                        test_wav, test_json, test_output
                    ], capture_output=True, text=True, timeout=30)
                    
                    print(f"\nTest Results:")
                    print(f"   Exit code: {result.returncode}")
                    if result.stdout:
                        print(f"   Output: {result.stdout[:200]}...")
                    if result.stderr:
                        print(f"   Errors: {result.stderr[:200]}...")
                        
                except subprocess.TimeoutExpired:
                    print("Test timed out - tool may be waiting for input")
                except Exception as e:
                    print(f"Test error: {e}")
                
            except Exception as e:
                print(f"Failed to create test files: {e}")
        
    elif choice == '4':
        return
    else:
        print("\nInvalid selection")
    
    input("\nPress Enter to return to menu...")

def display_vhs_decode_menu():
    """Display the VHS-Decode submenu with job queue as primary interface"""
    while True:
        clear_screen()
        display_header()
        print("\nVHS-DECODE MENU")
        print("=" * 20)
        print("Background job queue processing for VHS decode workflows")
        print("Queue jobs for processing while you continue using the menu system.")
        print()
        print("\n🚀 PRIMARY WORKFLOW INTERFACE:")
        print("=" * 35)
        print("1. VHS Workflow Control Centre (Enhanced with Real-time Status)")
        print("\n🛠️ BACKGROUND JOB MANAGEMENT:")
        print("=" * 30)
        print("2. Configure Job Queue Settings")
        print()
        print("📝 Note: Job status monitoring integrated into Workflow Control Centre")
        print("   Real-time progress bars, FPS, and ETA now appear directly in the workflow matrix.")
        print()
        print("OTHER OPTIONS:")
        print("=" * 20)
        print("5. Set Capture Segment (configure time range for testing)")
        print("6. Advanced VHS-Decode Settings...")
        print("7. Kill Rogue/Stuck Processes ⚠️")
        print("8. Return to Main Menu")
        
        selection = input("\nSelect option (1-9): ").strip().lower()
        
        if selection == '1':
            launch_workflow_control_centre()
        elif selection == '2':
            configure_job_queue_settings()
        elif selection == '5':
            set_capture_segment()
        elif selection == '6':
            display_advanced_vhs_decode_menu()
            break  # Return to main menu after advanced options
        elif selection == '7':
            kill_rogue_vhs_processes()
        elif selection == '8':
            break  # Return to main menu
        else:
            print("Invalid selection. Please enter 1-8.")
            time.sleep(1)

def legacy_direct_decode_menu():
    """Legacy direct decode menu - immediate processing (old behavior)"""
    while True:
        clear_screen()
        display_header()
        print("\nLEGACY DIRECT DECODE MENU")
        print("=" * 35)
        print("Direct VHS decode processing - jobs start immediately")
        print("These tools run decode operations directly without queueing.")
        print()
        print("⚠️  Note: Jobs block menu access until completion")
        print("⚠️  For background processing, use the main job queue options")
        print()
        print("SELECT RECORDING SPEED TO PROCESS (Match how the tape was originally recorded):")
        print("1. PAL SP (Standard Play) - E60=60min, E120=120min, E180=180min, E240=240min")
        print("2. PAL LP (Long Play) - E60=120min, E120=240min, E180=360min, E240=480min")
        print("3. PAL EP (Extended Play) - E60=180min, E120=360min, E180=540min, E240=720min")
        print("4. NTSC SP (Standard Play) - T60=60min, T120=120min, T180=180min, T240=240min")
        print("5. NTSC LP (Long Play) - T60=120min, T120=240min, T180=360min, T240=480min")
        print("6. NTSC EP (Extended Play) - T60=180min, T120=360min, T180=540min, T240=720min")
        print()
        print("EXPORT STEPS:")
        print("=" * 18)
        print("7. Run TBC Video Export (direct processing)")
        print()
        print("8. Return to VHS-Decode Menu")
        
        selection = input("\nSelect option (1-8): ").strip().lower()
        
        if selection == '1':
            manual_vhs_decode_with_params('pal', 'SP')
            break  # Return to main menu after decode
        elif selection == '2':
            manual_vhs_decode_with_params('pal', 'LP')
            break  # Return to main menu after decode
        elif selection == '3':
            manual_vhs_decode_with_params('pal', 'EP')
            break  # Return to main menu after decode
        elif selection == '4':
            manual_vhs_decode_with_params('ntsc', 'SP')
            break  # Return to main menu after decode
        elif selection == '5':
            manual_vhs_decode_with_params('ntsc', 'LP')
            break  # Return to main menu after decode
        elif selection == '6':
            manual_vhs_decode_with_params('ntsc', 'EP')
            break  # Return to main menu after decode
        elif selection == '7':
            manual_tbc_export()
            break  # Return to main menu after export
        elif selection == '8':
            break  # Return to VHS-Decode menu
        else:
            print("Invalid selection. Please enter 1-8.")
            time.sleep(1)

def manual_vhs_decode():
    """Manually run vhs-decode with PAL settings on RF files in configured capture directory"""
    clear_screen()
    display_header()
    print("\nMANUAL VHS-DECODE (PAL)")
    print("=" * 30)
    print("This will run vhs-decode with PAL settings on RF capture files.")
    print()
    print("Settings used:")
    print("   • Format: VHS")
    print("   • Standard: PAL")
    print("   • Tape speed: SP (Standard Play)")
    print("   • Threads: 3")
    print("   • No resampling, recheck phase enabled, IRE 0 adjust enabled")
    
    # Get additional user parameters
    print("\nADDITIONAL PARAMETERS (OPTIONAL)")
    print("=" * 40)
    print("You can add extra vhs-decode parameters here.")
    print("Examples:")
    print("   --dod-threshold X   # Dropout detection threshold")
    print("   --disable-pilot     # Disable pilot tone detection")
    print("   --cxadc-gain X      # CXADC gain adjustment")
    print("   --field-order X     # Field order (0=TFF, 1=BFF)")
    print("\nEnter additional parameters (space-separated) or press Enter to continue:")
    
    additional_params = input("> ").strip()
    
    # Store the additional parameters for use in vhs-decode command
    # We'll pass this to the decode function
    print()
    
    try:
        # Import config functions to get the configured capture directory
        sys.path.append('.')
        from config import get_capture_directory
        
        # Look for .lds files in configured capture directory
        capture_folder = get_capture_directory()
        
        if not os.path.exists(capture_folder):
            print(f"ERROR: Capture folder '{capture_folder}' does not exist!")
            print("Please run 'Capture New Video' first to create RF captures.")
            input("\nPress Enter to return to menu...")
            return
        
        # Find all .lds and .ldf files in capture folder
        rf_files = [f for f in os.listdir(capture_folder) if f.lower().endswith(('.lds', '.ldf'))]
        
        if not rf_files:
            print(f"ERROR: No RF capture files (.lds/.ldf) found in '{capture_folder}' folder!")
            print("Please run 'Capture New Video' first to create RF captures.")
            input("\nPress Enter to return to menu...")
            return
        
        print(f"Found {len(rf_files)} RF capture file(s) in capture folder:")
        print()
        
        # Sort files by modification time (newest first)
        rf_paths = [os.path.join(capture_folder, f) for f in rf_files]
        rf_paths.sort(key=os.path.getmtime, reverse=True)
        
        # Display files with selection numbers
        for i, rf_path in enumerate(rf_paths, 1):
            rf_file = os.path.basename(rf_path)
            file_size = os.path.getsize(rf_path) / (1024**2)  # MB
            mod_time = time.ctime(os.path.getmtime(rf_path))
            print(f"   {i}. {rf_file} ({file_size:.1f} MB) - {mod_time}")
        
        print()
        print("Select which RF file to decode:")
        
        try:
            selection = input(f"Enter number (1-{len(rf_paths)}) or 'q' to quit: ").strip().lower()
            
            if selection == 'q':
                print("VHS decode cancelled.")
                input("\nPress Enter to return to menu...")
                return
            
            file_index = int(selection) - 1
            if file_index < 0 or file_index >= len(rf_paths):
                raise ValueError("Invalid selection")
            
            rf_file = rf_paths[file_index]
            
        except (ValueError, IndexError):
            print("ERROR: Invalid selection. Please enter a valid number.")
            input("\nPress Enter to return to menu...")
            return
        
        # Generate output TBC filename based on RF file extension
        if rf_file.lower().endswith('.lds'):
            tbc_file = rf_file.replace('.lds', '.tbc')
        else:  # .ldf file
            tbc_file = rf_file.replace('.ldf', '.tbc')
        
        print(f"\nSelected RF file: {os.path.basename(rf_file)}")
        print(f"Output TBC file: {os.path.basename(tbc_file)}")
        print(f"Output JSON file: {os.path.basename(tbc_file)}.json")
        
        # Check if TBC files already exist
        if os.path.exists(tbc_file) and os.path.exists(tbc_file + '.json'):
            print(f"\nWARNING: TBC files already exist!")
            print(f"   {os.path.basename(tbc_file)}")
            print(f"   {os.path.basename(tbc_file)}.json")
            overwrite = input("\nOverwrite existing files? (y/N): ").strip().lower()
            if overwrite not in ['y', 'yes']:
                print("VHS decode cancelled.")
                input("\nPress Enter to return to menu...")
                return
        
        # Confirm before starting
        confirm = input("\nStart VHS decode? (Y/n): ").strip().lower()
        if confirm in ['n', 'no']:
            print("VHS decode cancelled.")
            input("\nPress Enter to return to menu...")
            return
        
        # Import and run the decode function from ddd_clockgen_sync
        print(f"\nStarting VHS decode...")
        try:
            sys.path.append('.')
            from ddd_clockgen_sync import run_vhs_decode_with_params, cleanup_existing_processes
            
            # Clean up any existing processes before starting
            cleanup_existing_processes()
            
            success = run_vhs_decode_with_params(rf_file, tbc_file, 'pal', 'SP', additional_params)
            
            if success:
                print(f"\nVHS decode completed successfully!")
                print(f"Files created:")
                print(f"   TBC: {os.path.basename(tbc_file)}")
                print(f"   JSON: {os.path.basename(tbc_file)}.json")
            else:
                print(f"\nVHS decode failed.")
        except Exception as e:
            print(f"\nError running VHS decode: {e}")
    
    except KeyboardInterrupt:
        print("\nVHS decode cancelled by user.")
    except Exception as e:
        print(f"\nError during VHS decode: {e}")
    
    input("\nPress Enter to return to menu...")

def manual_vhs_decode_ntsc():
    """Manually run vhs-decode with NTSC settings on RF files in configured capture directory"""
    clear_screen()
    display_header()
    print("\nMANUAL VHS-DECODE (NTSC)")
    print("=" * 30)
    print("This will run vhs-decode with NTSC settings on RF capture files.")
    print()
    print("Settings used:")
    print("   • Format: VHS")
    print("   • Standard: NTSC")
    print("   • Tape speed: SP (Standard Play)")
    print("   • Threads: 3")
    print("   • No resampling, recheck phase enabled, IRE 0 adjust enabled")
    
    # Get additional user parameters
    print("\nADDITIONAL PARAMETERS (OPTIONAL)")
    print("=" * 40)
    print("You can add extra vhs-decode parameters here.")
    print("Examples:")
    print("   --dod-threshold X   # Dropout detection threshold")
    print("   --disable-pilot     # Disable pilot tone detection")
    print("   --cxadc-gain X      # CXADC gain adjustment")
    print("   --field-order X     # Field order (0=TFF, 1=BFF)")
    print("\nEnter additional parameters (space-separated) or press Enter to continue:")
    
    additional_params = input("> ").strip()
    
    # Store the additional parameters for use in vhs-decode command
    # We'll pass this to the decode function
    print()
    
    try:
        # Import config functions to get the configured capture directory
        sys.path.append('.')
        from config import get_capture_directory
        
        # Look for .lds files in configured capture directory
        capture_folder = get_capture_directory()
        
        if not os.path.exists(capture_folder):
            print(f"ERROR: Capture folder '{capture_folder}' does not exist!")
            print("Please run 'Capture New Video' first to create RF captures.")
            input("\nPress Enter to return to menu...")
            return
        
        # Find all .lds and .ldf files in capture folder
        rf_files = [f for f in os.listdir(capture_folder) if f.lower().endswith(('.lds', '.ldf'))]
        
        if not rf_files:
            print(f"ERROR: No RF capture files (.lds/.ldf) found in '{capture_folder}' folder!")
            print("Please run 'Capture New Video' first to create RF captures.")
            input("\nPress Enter to return to menu...")
            return
        
        print(f"Found {len(rf_files)} RF capture file(s) in capture folder:")
        print()
        
        # Sort files by modification time (newest first)
        rf_paths = [os.path.join(capture_folder, f) for f in rf_files]
        rf_paths.sort(key=os.path.getmtime, reverse=True)
        
        # Display files with selection numbers
        for i, rf_path in enumerate(rf_paths, 1):
            rf_file = os.path.basename(rf_path)
            file_size = os.path.getsize(rf_path) / (1024**2)  # MB
            mod_time = time.ctime(os.path.getmtime(rf_path))
            print(f"   {i}. {rf_file} ({file_size:.1f} MB) - {mod_time}")
        
        print()
        print("Select which RF file to decode:")
        
        try:
            selection = input(f"Enter number (1-{len(rf_paths)}) or 'q' to quit: ").strip().lower()
            
            if selection == 'q':
                print("VHS decode cancelled.")
                input("\nPress Enter to return to menu...")
                return
            
            file_index = int(selection) - 1
            if file_index < 0 or file_index >= len(rf_paths):
                raise ValueError("Invalid selection")
            
            rf_file = rf_paths[file_index]
            
        except (ValueError, IndexError):
            print("ERROR: Invalid selection. Please enter a valid number.")
            input("\nPress Enter to return to menu...")
            return
        
        # Generate output TBC filename based on RF file extension
        if rf_file.lower().endswith('.lds'):
            tbc_file = rf_file.replace('.lds', '.tbc')
        else:  # .ldf file
            tbc_file = rf_file.replace('.ldf', '.tbc')
        
        print(f"\nSelected RF file: {os.path.basename(rf_file)}")
        print(f"Output TBC file: {os.path.basename(tbc_file)}")
        print(f"Output JSON file: {os.path.basename(tbc_file)}.json")
        
        # Check if TBC files already exist
        if os.path.exists(tbc_file) and os.path.exists(tbc_file + '.json'):
            print(f"\nWARNING: TBC files already exist!")
            print(f"   {os.path.basename(tbc_file)}")
            print(f"   {os.path.basename(tbc_file)}.json")
            overwrite = input("\nOverwrite existing files? (y/N): ").strip().lower()
            if overwrite not in ['y', 'yes']:
                print("VHS decode cancelled.")
                input("\nPress Enter to return to menu...")
                return
        
        # Confirm before starting
        confirm = input("\nStart VHS decode? (Y/n): ").strip().lower()
        if confirm in ['n', 'no']:
            print("VHS decode cancelled.")
            input("\nPress Enter to return to menu...")
            return
        
        # Import and run the decode function from ddd_clockgen_sync
        print(f"\nStarting VHS decode...")
        try:
            sys.path.append('.')
            from ddd_clockgen_sync import run_vhs_decode_with_params, cleanup_existing_processes
            
            # Clean up any existing processes before starting
            cleanup_existing_processes()
            
            success = run_vhs_decode_with_params(rf_file, tbc_file, 'ntsc', 'SP', additional_params)
            
            if success:
                print(f"\nVHS decode completed successfully!")
                print(f"Files created:")
                print(f"   TBC: {os.path.basename(tbc_file)}")
                print(f"   JSON: {os.path.basename(tbc_file)}.json")
            else:
                print(f"\nVHS decode failed.")
        except Exception as e:
            print(f"\nError running VHS decode: {e}")
    
    except KeyboardInterrupt:
        print("\nVHS decode cancelled by user.")
    except Exception as e:
        print(f"\nError during VHS decode: {e}")
    
    input("\nPress Enter to return to menu...")

def set_capture_segment():
    """Configure time range segment for testing decode parameters"""
    clear_screen()
    display_header()
    print("\nSET CAPTURE SEGMENT (CONFIGURE TIME RANGE FOR TESTING)")
    print("=" * 60)
    print("Configure a specific time range segment for testing decode parameters")
    print("without processing entire capture files. This creates persistent")
    print("segment configuration for repeated testing.")
    print()
    print("Purpose:")
    print("   • Test different decode parameters on consistent segments")
    print("   • Speed up decode testing workflows")
    print("   • Avoid processing entire large capture files repeatedly")
    print("   • Generate segment-specific output files")
    print()
    
    # Load existing segment configuration
    segment_config_path = "config/capture_segment.json"
    print(f"Configuration file: {segment_config_path}")
    print("(You can edit this JSON file directly if preferred)")
    print()
    current_segment = None
    
    try:
        if os.path.exists(segment_config_path):
            import json
            with open(segment_config_path, 'r') as f:
                current_segment = json.load(f)
                
            print("CURRENT SEGMENT CONFIGURATION:")
            print(f"   Start time: {current_segment.get('start_time', 'N/A')}")
            print(f"   End time: {current_segment.get('end_time', 'N/A')}")
            print(f"   Duration: {current_segment.get('duration', 'N/A')}")
            print(f"   Enabled: {current_segment.get('enabled', False)}")
            print(f"   Description: {current_segment.get('description', 'N/A')}")
            print()
        else:
            print("No segment configuration found.")
            print()
            
    except Exception as e:
        print(f"Error reading existing configuration: {e}")
        print()
    
    print("SEGMENT CONFIGURATION OPTIONS:")
    print("=" * 40)
    print("1. Set new time range segment")
    print("2. Enable/disable current segment")
    print("3. Clear segment configuration")
    print("4. Test segment on existing files")
    print("5. Display current settings (detailed view)")
    print("6. Return to VHS-Decode Menu")
    
    choice = input("\nSelect option (1-6): ").strip()
    
    if choice == '1':
        set_new_segment(segment_config_path)
    elif choice == '2':
        toggle_segment_enabled_menu(segment_config_path, current_segment)
    elif choice == '3':
        clear_segment_configuration(segment_config_path)
    elif choice == '4':
        test_segment_on_files(current_segment)
    elif choice == '5':
        display_current_segment_settings(segment_config_path, current_segment)
    elif choice == '6':
        return
    else:
        print("\nInvalid selection.")
        time.sleep(1)
    
    input("\nPress Enter to continue...")

def set_new_segment(config_path):
    """Set a new time range segment"""
    print("\nSET NEW TIME RANGE SEGMENT")
    print("=" * 35)
    print("Enter start and end times for the segment.")
    print("Format: HH:MM:SS (e.g., 00:05:30 for 5 minutes 30 seconds)")
    print()
    
    try:
        # Get start time
        while True:
            start_input = input("Start time (HH:MM:SS): ").strip()
            if not start_input:
                print("Start time is required.")
                continue
            
            try:
                start_parts = start_input.split(':')
                if len(start_parts) != 3:
                    raise ValueError("Invalid format")
                    
                start_hours = int(start_parts[0])
                start_minutes = int(start_parts[1])
                start_seconds = int(start_parts[2])
                
                if start_hours < 0 or start_minutes < 0 or start_minutes >= 60 or start_seconds < 0 or start_seconds >= 60:
                    raise ValueError("Invalid time values")
                    
                start_total_seconds = start_hours * 3600 + start_minutes * 60 + start_seconds
                break
                
            except ValueError:
                print("Invalid time format. Use HH:MM:SS (e.g., 00:05:30)")
        
        # Get end time
        while True:
            end_input = input("End time (HH:MM:SS): ").strip()
            if not end_input:
                print("End time is required.")
                continue
            
            try:
                end_parts = end_input.split(':')
                if len(end_parts) != 3:
                    raise ValueError("Invalid format")
                    
                end_hours = int(end_parts[0])
                end_minutes = int(end_parts[1])
                end_seconds = int(end_parts[2])
                
                if end_hours < 0 or end_minutes < 0 or end_minutes >= 60 or end_seconds < 0 or end_seconds >= 60:
                    raise ValueError("Invalid time values")
                    
                end_total_seconds = end_hours * 3600 + end_minutes * 60 + end_seconds
                
                if end_total_seconds <= start_total_seconds:
                    print("End time must be after start time.")
                    continue
                    
                break
                
            except ValueError:
                print("Invalid time format. Use HH:MM:SS (e.g., 00:10:00)")
        
        # Calculate duration
        duration_seconds = end_total_seconds - start_total_seconds
        duration_minutes = duration_seconds // 60
        duration_hours = duration_minutes // 60
        duration_display = f"{duration_hours:02d}:{(duration_minutes % 60):02d}:{(duration_seconds % 60):02d}"
        
        # Get optional description
        description = input("\nOptional description (e.g., 'Test pattern section'): ").strip()
        if not description:
            description = f"Segment {start_input} to {end_input}"
        
        # Create segment configuration
        segment_config = {
            "start_time": start_input,
            "end_time": end_input,
            "start_seconds": start_total_seconds,
            "end_seconds": end_total_seconds,
            "duration": duration_display,
            "duration_seconds": duration_seconds,
            "description": description,
            "enabled": True,
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S")
        }
        
        print(f"\nSEGMENT CONFIGURATION SUMMARY:")
        print(f"   Start: {start_input}")
        print(f"   End: {end_input}")
        print(f"   Duration: {duration_display}")
        print(f"   Description: {description}")
        print(f"   Enabled: Yes")
        
        confirm = input("\nSave this segment configuration? (Y/n): ").strip().lower()
        if confirm not in ['n', 'no']:
            # Ensure config directory exists
            os.makedirs("config", exist_ok=True)
            
            # Save configuration
            import json
            with open(config_path, 'w') as f:
                json.dump(segment_config, f, indent=2)
            
            print(f"\n✓ Segment configuration saved!")
            print(f"   File: {config_path}")
            print(f"   This segment will be offered when running VHS decode operations.")
        else:
            print("\nSegment configuration cancelled.")
            
    except KeyboardInterrupt:
        print("\nOperation cancelled.")
    except Exception as e:
        print(f"\nError creating segment configuration: {e}")

def toggle_segment_enabled_menu(config_path, current_segment):
    """Enable or disable the current segment"""
    if not current_segment:
        print("\nNo segment configuration found to toggle.")
        return
    
    current_status = current_segment.get('enabled', False)
    new_status = not current_status
    
    print(f"\nCurrent segment status: {'Enabled' if current_status else 'Disabled'}")
    print(f"Change to: {'Enabled' if new_status else 'Disabled'}")
    
    confirm = input("\nApply this change? (Y/n): ").strip().lower()
    if confirm not in ['n', 'no']:
        try:
            # Use the new segment_config module function
            from segment_config import toggle_segment_enabled
            result = toggle_segment_enabled(new_status)
            
            if result == new_status:
                print(f"\n✓ Segment {'enabled' if new_status else 'disabled'}!")
            else:
                print(f"\nFailed to update segment status.")
        except Exception as e:
            print(f"\nError updating segment status: {e}")
    else:
        print("\nNo changes made.")

def clear_segment_configuration(config_path):
    """Clear/remove the segment configuration"""
    print("\nCLEAR SEGMENT CONFIGURATION")
    print("=" * 35)
    print("This will permanently remove the current segment configuration.")
    print("All decode operations will return to processing full captures.")
    
    confirm = input("\nPermanently clear segment configuration? (y/N): ").strip().lower()
    if confirm in ['y', 'yes']:
        try:
            # Use the new segment_config module function
            from segment_config import clear_segment_config
            if clear_segment_config():
                print("\n✓ Segment configuration cleared successfully!")
            else:
                print("\n✗ Failed to clear segment configuration.")
        except Exception as e:
            print(f"\nError clearing segment configuration: {e}")
    else:
        print("\nSegment configuration preserved.")

def display_current_segment_settings(config_path, current_segment):
    """Display detailed current segment settings"""
    clear_screen()
    display_header()
    print("\nCURRENT SEGMENT SETTINGS (DETAILED VIEW)")
    print("=" * 50)
    
    try:
        if not current_segment:
            print("No segment configuration found.")
            print("\nTo create a segment configuration:")
            print("   1. Return to the Segment Configuration menu")
            print("   2. Select 'Set new time range segment'")
            print("   3. Configure your desired time range")
        else:
            print("SEGMENT CONFIGURATION DETAILS:")
            print("=" * 40)
            
            # Basic timing information
            print(f"Start Time:        {current_segment.get('start_time', 'N/A')}")
            print(f"End Time:          {current_segment.get('end_time', 'N/A')}")
            print(f"Duration:          {current_segment.get('duration', 'N/A')}")
            print(f"Duration (seconds): {current_segment.get('duration_seconds', 'N/A')}")
            
            # Status information
            enabled = current_segment.get('enabled', False)
            print(f"Status:            {'ENABLED' if enabled else 'DISABLED'}")
            print(f"Description:       {current_segment.get('description', 'N/A')}")
            
            # Creation information
            created_at = current_segment.get('created_at', 'N/A')
            print(f"Created:           {created_at}")
            
            # Calculated values for VHS-decode
            if 'start_seconds' in current_segment and 'duration_seconds' in current_segment:
                print("\nVHS-DECODE PARAMETERS:")
                print("=" * 30)
                
                # Calculate for both PAL and NTSC using exact same logic as decode function
                start_seconds = current_segment['start_seconds']
                duration_seconds = current_segment['duration_seconds']
                
                # PAL (25.0 fps) - exact calculation
                pal_start_frame = int(start_seconds * 25.0)
                pal_length_frames = int(duration_seconds * 25.0)
                print(f"PAL (25fps):")
                print(f"   Start frame (-s): {pal_start_frame}")
                print(f"   Length (-l):      {pal_length_frames}")
                
                # NTSC (29.97 fps) - exact calculation
                ntsc_start_frame = int(start_seconds * 29.97)
                ntsc_length_frames = int(duration_seconds * 29.97)
                print(f"NTSC (29.97fps):")
                print(f"   Start frame (-s): {ntsc_start_frame}")
                print(f"   Length (-l):      {ntsc_length_frames}")
                
                print(f"\nThese are the exact frame parameters that will be applied")
                print(f"when running PAL or NTSC decode with this segment.")
            
            # Configuration file information
            print("\nCONFIGURATION FILE:")
            print("=" * 25)
            print(f"Location: {config_path}")
            
            if os.path.exists(config_path):
                file_size = os.path.getsize(config_path)
                mod_time = time.ctime(os.path.getmtime(config_path))
                print(f"Size: {file_size} bytes")
                print(f"Modified: {mod_time}")
            else:
                print("Status: File does not exist")
            
            # Usage information
            print("\nUSAGE INFORMATION:")
            print("=" * 25)
            if enabled:
                print("This segment configuration is ACTIVE and will be used when:")
                print("   • Running VHS-decode operations from the VHS-Decode menu")
                print("   • The segment parameters will be automatically applied")
                print("   • Output files will include segment suffix in filename")
            else:
                print("This segment configuration is DISABLED:")
                print("   • VHS-decode operations will process full captures")
                print("   • Enable it using 'Enable/disable current segment' option")
            
            print("\nCUSTOMIZATION OPTIONS:")
            print("=" * 30)
            print("• Edit the JSON file directly for advanced customization")
            print("• Add custom metadata fields")
            print("• Modify timing precision")
            print("• Create multiple segment configurations by copying the file")
            
    except Exception as e:
        print(f"Error displaying segment settings: {e}")
        print("\nThere may be an issue with the segment configuration file.")
        print(f"Configuration file: {config_path}")
        
        if os.path.exists(config_path):
            print("\nThe file exists but may have formatting issues.")
            show_raw = input("\nShow raw file contents? (y/N): ").strip().lower()
            if show_raw in ['y', 'yes']:
                try:
                    with open(config_path, 'r') as f:
                        content = f.read()
                    print("\nRAW FILE CONTENTS:")
                    print("-" * 30)
                    print(content)
                    print("-" * 30)
                except Exception as read_error:
                    print(f"Could not read file: {read_error}")

def test_segment_on_files(current_segment):
    """Test the current segment configuration on existing files"""
    if not current_segment or not current_segment.get('enabled', False):
        print("\nNo enabled segment configuration found.")
        print("Please configure a segment first.")
        return
    
    print("\nTEST SEGMENT ON EXISTING FILES")
    print("=" * 40)
    print("This will show you what the segment parameters would be")
    print("when applied to actual RF files, without running decode.")
    print()
    
    # Find RF files in capture directory
    try:
        sys.path.append('.')
        from config import get_capture_directory
        
        capture_folder = get_capture_directory()
        if not os.path.exists(capture_folder):
            print(f"Capture directory not found: {capture_folder}")
            return
        
        rf_files = [f for f in os.listdir(capture_folder) if f.lower().endswith(('.lds', '.ldf'))]
        if not rf_files:
            print(f"No RF files found in {capture_folder}")
            return
        
        # Show available files
        print(f"Found {len(rf_files)} RF file(s):")
        rf_paths = [os.path.join(capture_folder, f) for f in rf_files]
        rf_paths.sort(key=os.path.getmtime, reverse=True)
        
        for i, rf_path in enumerate(rf_paths, 1):
            rf_file = os.path.basename(rf_path)
            size_mb = os.path.getsize(rf_path) / (1024**2)
            print(f"   {i}. {rf_file} ({size_mb:.1f} MB)")
        
        selection = input(f"\nSelect file to test segment on (1-{len(rf_paths)}): ").strip()
        file_index = int(selection) - 1
        selected_file = rf_paths[file_index]
        
        # Calculate segment parameters based on file and timing
        # This is a preview - actual implementation would need RF file analysis
        print(f"\nSEGMENT TEST PREVIEW:")
        print(f"   RF file: {os.path.basename(selected_file)}")
        print(f"   Segment: {current_segment['start_time']} to {current_segment['end_time']}")
        print(f"   Duration: {current_segment['duration']}")
        print()
        
        # Estimate frame parameters (this is simplified - real implementation needs RF analysis)
        # Assume PAL 25fps for estimation
        start_frame = current_segment['start_seconds'] * 25
        length_frames = current_segment['duration_seconds'] * 25
        
        print(f"ESTIMATED VHS-DECODE PARAMETERS:")
        print(f"   -s {start_frame}  # Start frame (estimated for PAL 25fps)")
        print(f"   -l {length_frames}  # Length in frames (estimated)")
        print()
        
        # Show what output filename would be
        base_name = os.path.splitext(os.path.basename(selected_file))[0]
        segment_suffix = f"_seg_{current_segment['start_time'].replace(':', '')}_{current_segment['end_time'].replace(':', '')}"
        output_tbc = f"{base_name}{segment_suffix}.tbc"
        
        print(f"OUTPUT FILES WOULD BE:")
        print(f"   TBC: {output_tbc}")
        print(f"   JSON: {output_tbc}.json")
        print()
        print(f"Note: This is a preview. Actual frame numbers depend on RF file analysis.")
        
    except Exception as e:
        print(f"Error testing segment: {e}")

def manual_vhs_decode_with_params(video_standard, tape_speed):
    """Unified VHS decode function with configurable video standard and tape speed"""
    clear_screen()
    display_header()
    print(f"\nMANUAL VHS-DECODE ({video_standard.upper()} {tape_speed})")
    print("=" * 40)
    print(f"This will run vhs-decode with {video_standard.upper()} {tape_speed} settings on RF capture files.")
    print()
    print("Settings used:")
    print("   • Format: VHS")
    print(f"   • Standard: {video_standard.upper()}")
    print(f"   • Tape speed: {tape_speed}")
    print("   • Threads: 3")
    print("   • No resampling, recheck phase enabled, IRE 0 adjust enabled")
    
    # Speed descriptions
    speed_descriptions = {
        'SP': 'Standard Play (highest quality, ~2 hours)',
        'LP': 'Long Play (medium quality, ~4 hours)', 
        'EP': 'Extended Play (lower quality, ~6+ hours)'
    }
    
    print(f"\nTape Speed Details:")
    print(f"   {speed_descriptions.get(tape_speed, 'Unknown speed')}")
    
    # Check for active segment configuration
    segment_config_path = "config/capture_segment.json"
    current_segment = None
    
    try:
        if os.path.exists(segment_config_path):
            import json
            with open(segment_config_path, 'r') as f:
                current_segment = json.load(f)
                
            if current_segment and current_segment.get('enabled', False):
                # Calculate format-specific frame parameters NOW (at decode time)
                fps = 25.0 if video_standard.lower() == 'pal' else 29.97
                start_seconds = current_segment.get('start_seconds', 0)
                duration_seconds = current_segment.get('duration_seconds', 0)
                
                start_frame = int(start_seconds * fps)
                length_frames = int(duration_seconds * fps)
                
                print("\n" + "="*60)
                print(f"⚠️  SEGMENT MODE ACTIVE - {video_standard.upper()} DECODE")
                print("="*60)
                print(f"Time Range: {current_segment.get('start_time', 'N/A')} to {current_segment.get('end_time', 'N/A')}")
                print(f"Duration: {current_segment.get('duration', 'N/A')}")
                print(f"Format-specific frames for {video_standard.upper()} ({fps}fps):")
                print(f"   Start frame (-s): {start_frame}")
                print(f"   Length frames (-l): {length_frames}")
                print(f"⚠️  This will decode only {duration_seconds}s of your capture!")
                print("="*60)
                
                # Store segment parameters for later use
                current_segment['calculated_start_frame'] = start_frame
                current_segment['calculated_length_frames'] = length_frames
                current_segment['calculated_for_format'] = video_standard.upper()
    except Exception as e:
        print(f"Warning: Error reading segment configuration: {e}")
        current_segment = None
    
    # Get additional user parameters
    print("\nADDITIONAL PARAMETERS (OPTIONAL)")
    print("=" * 40)
    print("You can add extra vhs-decode parameters here.")
    print("Examples:")
    print("   --dod-threshold X   # Dropout detection threshold")
    print("   --disable-pilot     # Disable pilot tone detection")
    print("   --cxadc-gain X      # CXADC gain adjustment")
    print("   --field-order X     # Field order (0=TFF, 1=BFF)")
    
    if tape_speed in ['LP', 'EP']:
        print("\nSpeed-specific parameters you might want to consider:")
        if tape_speed == 'LP':
            print("   --dod-threshold 0.8 # Lower dropout detection (LP tapes have more dropouts)")
        elif tape_speed == 'EP':
            print("   --dod-threshold 0.6 # Much lower dropout detection (EP tapes very prone to dropouts)")
    
    print("\nEnter additional parameters (space-separated) or press Enter to continue:")
    
    additional_params = input("> ").strip()
    
    # Store the additional parameters for use in vhs-decode command
    # We'll pass this to the decode function
    print()
    
    try:
        # Import config functions to get the configured capture directory
        sys.path.append('.')
        from config import get_capture_directory
        
        # Look for .lds files in configured capture directory
        capture_folder = get_capture_directory()
        
        if not os.path.exists(capture_folder):
            print(f"ERROR: Capture folder '{capture_folder}' does not exist!")
            print("Please run 'Capture New Video' first to create RF captures.")
            input("\nPress Enter to return to menu...")
            return
        
        # Find all .lds and .ldf files in capture folder
        rf_files = [f for f in os.listdir(capture_folder) if f.lower().endswith(('.lds', '.ldf'))]
        
        if not rf_files:
            print(f"ERROR: No RF capture files (.lds/.ldf) found in '{capture_folder}' folder!")
            print("Please run 'Capture New Video' first to create RF captures.")
            input("\nPress Enter to return to menu...")
            return
        
        print(f"Found {len(rf_files)} RF capture file(s) in capture folder:")
        print()
        
        # Sort files by modification time (newest first)
        rf_paths = [os.path.join(capture_folder, f) for f in rf_files]
        rf_paths.sort(key=os.path.getmtime, reverse=True)
        
        # Display files with selection numbers
        for i, rf_path in enumerate(rf_paths, 1):
            rf_file = os.path.basename(rf_path)
            file_size = os.path.getsize(rf_path) / (1024**2)  # MB
            mod_time = time.ctime(os.path.getmtime(rf_path))
            print(f"   {i}. {rf_file} ({file_size:.1f} MB) - {mod_time}")
        
        print()
        print("Select which RF file to decode:")
        
        try:
            selection = input(f"Enter number (1-{len(rf_paths)}) or 'q' to quit: ").strip().lower()
            
            if selection == 'q':
                print("VHS decode cancelled.")
                input("\nPress Enter to return to menu...")
                return
            
            file_index = int(selection) - 1
            if file_index < 0 or file_index >= len(rf_paths):
                raise ValueError("Invalid selection")
            
            rf_file = rf_paths[file_index]
            
        except (ValueError, IndexError):
            print("ERROR: Invalid selection. Please enter a valid number.")
            input("\nPress Enter to return to menu...")
            return
        
        # Generate output TBC filename based on RF file extension
        if rf_file.lower().endswith('.lds'):
            tbc_file = rf_file.replace('.lds', '.tbc')
        else:  # .ldf file
            tbc_file = rf_file.replace('.ldf', '.tbc')
        
        print(f"\nSelected RF file: {os.path.basename(rf_file)}")
        print(f"Output TBC file: {os.path.basename(tbc_file)}")
        print(f"Output JSON file: {os.path.basename(tbc_file)}.json")
        
        # Check if TBC files already exist
        if os.path.exists(tbc_file) and os.path.exists(tbc_file + '.json'):
            print(f"\nWARNING: TBC files already exist!")
            print(f"   {os.path.basename(tbc_file)}")
            print(f"   {os.path.basename(tbc_file)}.json")
            overwrite = input("\nOverwrite existing files? (y/N): ").strip().lower()
            if overwrite not in ['y', 'yes']:
                print("VHS decode cancelled.")
                input("\nPress Enter to return to menu...")
                return
        
        # Confirm before starting
        confirm = input(f"\nStart {video_standard.upper()} {tape_speed} VHS decode? (Y/n): ").strip().lower()
        if confirm in ['n', 'no']:
            print("VHS decode cancelled.")
            input("\nPress Enter to return to menu...")
            return
        
        # Import and run the appropriate decode function from ddd_clockgen_sync
        print(f"\nStarting {video_standard.upper()} {tape_speed} VHS decode...")
        try:
            sys.path.append('.')
            from ddd_clockgen_sync import run_vhs_decode_with_params, cleanup_existing_processes
            
            # Clean up any existing processes before starting
            cleanup_existing_processes()
            
            # If segment is active, apply the calculated frame parameters
            if current_segment and current_segment.get('enabled', False):
                start_frame = current_segment.get('calculated_start_frame', 0)
                length_frames = current_segment.get('calculated_length_frames', 0)
                
                # Add segment parameters to additional params
                segment_params = f"-s {start_frame} -l {length_frames}"
                if additional_params:
                    additional_params = f"{segment_params} {additional_params}"
                else:
                    additional_params = segment_params
                
                print(f"\nApplying segment parameters:")
                print(f"   Start frame: {start_frame}")
                print(f"   Length frames: {length_frames}")
                print(f"   Command addition: {segment_params}")
            
            success = run_vhs_decode_with_params(rf_file, tbc_file, video_standard, tape_speed, additional_params)
            
            if success:
                print(f"\n{video_standard.upper()} {tape_speed} VHS decode completed successfully!")
                print(f"Files created:")
                print(f"   TBC: {os.path.basename(tbc_file)}")
                print(f"   JSON: {os.path.basename(tbc_file)}.json")
                if current_segment and current_segment.get('enabled', False):
                    duration = current_segment.get('duration_seconds', 0)
                    print(f"   Segment: {current_segment.get('start_time')} to {current_segment.get('end_time')} ({duration}s)")
            else:
                print(f"\n{video_standard.upper()} {tape_speed} VHS decode failed.")
        except Exception as e:
            print(f"\nError running VHS decode: {e}")
    
    except KeyboardInterrupt:
        print("\nVHS decode cancelled by user.")
    except Exception as e:
        print(f"\nError during VHS decode: {e}")
    
    input("\nPress Enter to return to menu...")

def display_advanced_vhs_decode_menu():
    """Display advanced VHS decode menu with full parameter control"""
    while True:
        clear_screen()
        display_header()
        print("\nADVANCED VHS-DECODE SETTINGS")
        print("=" * 40)
        print("Full control over VHS decode parameters and advanced features")
        print()
        print("ADVANCED OPTIONS:")
        print("1. Custom Parameter Builder")
        print("2. Noise Reduction Settings...")
        print("3. Dropout Detection Settings...")
        print("4. Phase/IRE Adjustments...")
        print("5. Speed/Quality Presets...")
        print("6. Save/Load Parameter Sets...")
        print("7. Reset to Defaults")
        print("8. Return to VHS-Decode Menu")
        
        selection = input("\nSelect advanced option (1-8): ").strip().lower()
        
        if selection == '1':
            custom_parameter_builder()
            break
        elif selection == '2':
            noise_reduction_settings()
        elif selection == '3':
            dropout_detection_settings()
        elif selection == '4':
            phase_ire_adjustments()
        elif selection == '5':
            speed_quality_presets()
        elif selection == '6':
            save_load_parameters()
        elif selection == '7':
            reset_defaults()
        elif selection == '8':
            break  # Return to VHS-Decode menu
        else:
            print("Invalid selection. Please enter 1-8.")
            time.sleep(1)

def custom_parameter_builder():
    """Interactive parameter builder for advanced users"""
    clear_screen()
    display_header()
    print("\nCUSTOM PARAMETER BUILDER")
    print("=" * 35)
    print("Build a custom vhs-decode command with guided parameter selection")
    print("This will create and run a fully customized decode operation.")
    print()
    
    # Initialize parameters
    params = {
        'video_standard': 'pal',
        'tape_speed': 'SP', 
        'threads': '3',
        'additional': []
    }
    
    # Step 1: Video Standard
    while True:
        standard = input("Video standard (PAL/NTSC) [PAL]: ").strip().upper()
        if not standard:
            standard = 'PAL'
        if standard in ['PAL', 'NTSC']:
            params['video_standard'] = standard.lower()
            break
        print("Please enter PAL or NTSC")
    
    # Step 2: Tape Speed
    while True:
        speed = input("Tape speed (SP/LP/EP) [SP]: ").strip().upper()
        if not speed:
            speed = 'SP'
        if speed in ['SP', 'LP', 'EP']:
            params['tape_speed'] = speed
            break
        print("Please enter SP, LP, or EP")
    
    # Step 3: Threading
    while True:
        try:
            threads = input("Number of threads [3]: ").strip()
            if not threads:
                threads = '3'
            thread_count = int(threads)
            if 1 <= thread_count <= 16:
                params['threads'] = str(thread_count)
                break
            else:
                print("Please enter a number between 1 and 16")
        except ValueError:
            print("Please enter a valid number")
    
    # Step 4: Quality/Noise Reduction
    print(f"\nQuality settings for {params['video_standard'].upper()} {params['tape_speed']}:")
    
    # Chroma noise reduction
    while True:
        try:
            chroma_nr = input("Chroma noise reduction (0-4, 0=off) [auto]: ").strip()
            if not chroma_nr or chroma_nr.lower() == 'auto':
                if params['tape_speed'] == 'SP':
                    break  # No chroma NR for SP
                elif params['tape_speed'] == 'LP':
                    params['additional'].extend(['--chroma-nr', '1'])
                    break
                else:  # EP
                    params['additional'].extend(['--chroma-nr', '2'])
                    break
            chroma_val = int(chroma_nr)
            if 0 <= chroma_val <= 4:
                if chroma_val > 0:
                    params['additional'].extend(['--chroma-nr', str(chroma_val)])
                break
            else:
                print("Please enter a number between 0 and 4")
        except ValueError:
            print("Please enter a valid number or 'auto'")
    
    # Luma noise reduction
    while True:
        try:
            luma_nr = input("Luma noise reduction (0-4, 0=off) [auto]: ").strip()
            if not luma_nr or luma_nr.lower() == 'auto':
                if params['tape_speed'] == 'SP':
                    break  # No luma NR for SP
                elif params['tape_speed'] == 'LP':
                    params['additional'].extend(['--luma-nr', '1'])
                    break
                else:  # EP
                    params['additional'].extend(['--luma-nr', '2'])
                    break
            luma_val = int(luma_nr)
            if 0 <= luma_val <= 4:
                if luma_val > 0:
                    params['additional'].extend(['--luma-nr', str(luma_val)])
                break
            else:
                print("Please enter a number between 0 and 4")
        except ValueError:
            print("Please enter a valid number or 'auto'")
    
    # Optional: Additional advanced parameters
    print("\nAdvanced parameters (optional):")
    extra_params = input("Enter any additional parameters (space-separated): ").strip()
    if extra_params:
        params['additional'].extend(extra_params.split())
    
    # Summary
    print(f"\n=== DECODE CONFIGURATION SUMMARY ===")
    print(f"Video Standard: {params['video_standard'].upper()}")
    print(f"Tape Speed: {params['tape_speed']}")
    print(f"Threads: {params['threads']}")
    if params['additional']:
        print(f"Additional: {' '.join(params['additional'])}")
    print()
    
    # Confirm and run
    confirm = input("Run decode with these settings? (Y/n): ").strip().lower()
    if confirm not in ['n', 'no']:
        # Use the same file selection logic as the main decode functions
        try:
            sys.path.append('.')
            from config import get_capture_directory
            from ddd_clockgen_sync import run_vhs_decode_with_params, cleanup_existing_processes
            
            capture_folder = get_capture_directory()
            lds_files = [f for f in os.listdir(capture_folder) if f.lower().endswith('.lds')]
            
            if not lds_files:
                print("No RF files found to decode.")
                input("\nPress Enter to continue...")
                return
            
            # Show files and let user select
            print(f"\nFound {len(lds_files)} RF file(s):")
            lds_paths = [os.path.join(capture_folder, f) for f in lds_files]
            lds_paths.sort(key=os.path.getmtime, reverse=True)
            
            for i, rf_path in enumerate(lds_paths, 1):
                rf_file = os.path.basename(rf_path)
                file_size = os.path.getsize(rf_path) / (1024**2)  # MB
                print(f"   {i}. {rf_file} ({file_size:.1f} MB)")
            
            selection = input(f"\nSelect file (1-{len(lds_paths)}): ").strip()
            file_index = int(selection) - 1
            rf_file = lds_paths[file_index]
            tbc_file = rf_file.replace('.lds', '.tbc')
            
            print(f"\nStarting custom decode...")
            cleanup_existing_processes()
            
            # Convert additional params list to string
            additional_params_str = ' '.join(params['additional']) if params['additional'] else None
            
            success = run_vhs_decode_with_params(rf_file, tbc_file, 
                                                params['video_standard'], 
                                                params['tape_speed'], 
                                                additional_params_str)
            
            if success:
                print("\nCustom decode completed successfully!")
            else:
                print("\nCustom decode failed.")
                
        except Exception as e:
            print(f"\nError during custom decode: {e}")
    
    input("\nPress Enter to continue...")

# Placeholder functions for advanced menu options
def noise_reduction_settings():
    print("\nNoise reduction settings - Coming soon!")
    input("Press Enter to continue...")

def dropout_detection_settings():
    print("\nDropout detection settings - Coming soon!")
    input("Press Enter to continue...")

def phase_ire_adjustments():
    print("\nPhase/IRE adjustments - Coming soon!")
    input("Press Enter to continue...")

def speed_quality_presets():
    print("\nSpeed/Quality presets - Coming soon!")
    input("Press Enter to continue...")

def save_load_parameters():
    print("\nSave/Load parameters - Coming soon!")
    input("Press Enter to continue...")

def reset_defaults():
    print("\nReset to defaults - Coming soon!")
    input("Press Enter to continue...")

def parallel_vhs_decode_menu():
    """Display parallel VHS decode menu for multi-job processing"""
    clear_screen()
    display_header()
    print("\n🚀 BACKGROUND JOB PROCESSING")
    print("=" * 40)
    print("Queue and monitor background processing jobs with decoupled interface")
    print()
    print("Features:")
    print("• Queue multiple jobs for background processing")
    print("• Configurable max concurrent jobs")
    print("• Persistent job queue survives menu exits")
    print("• Real-time progress monitoring")
    print("• Job priority and status management")
    print()
    print("JOB MANAGEMENT OPTIONS:")
    print("=" * 30)
    print("1. Add VHS Decode Jobs to Queue")
    print("2. Add TBC Export Jobs to Queue")
    print("3. View Job Queue Status & Progress")
    print("4. Configure Job Queue Settings")
    print("5. Legacy: Direct Multi-Job Decode (Old Interface)")
    print("6. Return to Advanced Menu")
    
    choice = input("\nSelect option (1-6): ").strip()
    
    if choice == '1':
        add_vhs_decode_jobs_to_queue()
    elif choice == '2':
        add_tbc_export_jobs_to_queue()
    elif choice == '3':
        show_job_queue_display()
    elif choice == '4':
        configure_job_queue_settings()
    elif choice == '5':
        legacy_parallel_decode_menu()
    elif choice == '6':
        return
    else:
        print("\nInvalid selection")
        time.sleep(1)
        parallel_vhs_decode_menu()  # Return to this menu

def start_auto_parallel_decode():
    """Auto-detect RF files and start parallel decode"""
    clear_screen()
    display_header()
    print("\nAUTO-DETECT PARALLEL VHS DECODE")
    print("=" * 40)
    
    try:
        # Import config to get capture directory
        sys.path.append('.')
        from config import get_capture_directory
        
        capture_folder = get_capture_directory()
        if not os.path.exists(capture_folder):
            print(f"ERROR: Capture folder '{capture_folder}' does not exist!")
            print("Please ensure you have RF capture files in the configured directory.")
            input("\nPress Enter to return to menu...")
            return
        
        # Find all .lds files with corresponding .json metadata
        rf_files = []
        for f in os.listdir(capture_folder):
            if f.endswith('.lds'):
                json_file = f.replace('.lds', '.json')
                json_path = os.path.join(capture_folder, json_file)
                rf_path = os.path.join(capture_folder, f)
                
                if os.path.exists(json_path):
                    rf_files.append({
                        'rf_file': rf_path,
                        'json_file': json_path,
                        'name': os.path.splitext(f)[0]
                    })
                else:
                    print(f"Warning: No JSON metadata for {f} - skipping")
        
        if not rf_files:
            print(f"No RF files with JSON metadata found in {capture_folder}")
            print("Parallel decode requires JSON metadata for frame counting.")
            print("\nEnsure your RF files have corresponding .json files:")
            print("  example.lds → example.json")
            input("\nPress Enter to return to menu...")
            return
        
        print(f"Found {len(rf_files)} RF file(s) with metadata:")
        for i, rf_info in enumerate(rf_files, 1):
            size_mb = os.path.getsize(rf_info['rf_file']) / (1024**2)
            print(f"   {i}. {rf_info['name']} ({size_mb:.1f} MB)")
        
        # Get decode settings
        print("\nDECODE SETTINGS:")
        print("=" * 20)
        
        # Video standard
        while True:
            standard = input("Video standard (PAL/NTSC) [PAL]: ").strip().upper()
            if not standard:
                standard = 'PAL'
            if standard in ['PAL', 'NTSC']:
                video_standard = standard.lower()
                break
            print("Please enter PAL or NTSC")
        
        # Tape speed
        while True:
            speed = input("Tape speed (SP/LP/EP) [SP]: ").strip().upper()
            if not speed:
                speed = 'SP'
            if speed in ['SP', 'LP', 'EP']:
                tape_speed = speed
                break
            print("Please enter SP, LP, or EP")
        
        # Max parallel jobs
        while True:
            try:
                max_jobs_input = input(f"Max parallel jobs [2]: ").strip()
                if not max_jobs_input:
                    max_jobs = 2
                else:
                    max_jobs = int(max_jobs_input)
                if 1 <= max_jobs <= 8:
                    break
                else:
                    print("Please enter 1-8 jobs")
            except ValueError:
                print("Please enter a valid number")
        
        print(f"\nStarting parallel decode...")
        print(f"Settings: {video_standard.upper()} {tape_speed}, max {max_jobs} jobs")
        print("Press Ctrl+C to stop all jobs")
        print()
        
        # Import and run the parallel decode system
        try:
            # Ensure the current directory is in Python path
            if '.' not in sys.path:
                sys.path.insert(0, '.')
            from parallel_vhs_decode import run_parallel_decode
            
            # Convert to expected format for parallel_vhs_decode
            jobs = []
            for rf_info in rf_files:
                job = {
                    'name': rf_info['name'],
                    'rf_file': rf_info['rf_file'],
                    'json_file': rf_info['json_file'],
                    'video_standard': video_standard,
                    'tape_speed': tape_speed
                }
                jobs.append(job)
            
            # Run the parallel decode
            success = run_parallel_decode(jobs, max_workers=max_jobs)
            
            if success:
                print("\n✅ All decode jobs completed successfully!")
            else:
                print("\n⚠️ Some decode jobs had errors - check the output above")
                
        except ImportError:
            print("ERROR: parallel_vhs_decode module not found")
            print("Please ensure parallel_vhs_decode.py is in the project directory")
        except Exception as e:
            print(f"ERROR running parallel decode: {e}")
    
    except Exception as e:
        print(f"Error setting up parallel decode: {e}")
    
    input("\nPress Enter to return to menu...")

def configure_parallel_decode():
    """Configure specific RF files for parallel decode"""
    clear_screen()
    display_header()
    print("\nCONFIGURE PARALLEL DECODE JOBS")
    print("=" * 40)
    print("Select specific RF files and configure individual decode settings")
    print()
    
    try:
        # Import config to get capture directory
        sys.path.append('.')
        from config import get_capture_directory
        
        capture_folder = get_capture_directory()
        if not os.path.exists(capture_folder):
            print(f"ERROR: Capture folder '{capture_folder}' does not exist!")
            input("\nPress Enter to return to menu...")
            return
        
        # Find all .lds files
        lds_files = [f for f in os.listdir(capture_folder) if f.endswith('.lds')]
        
        if not lds_files:
            print(f"No RF files (.lds) found in {capture_folder}")
            input("\nPress Enter to return to menu...")
            return
        
        # Sort by modification time (newest first)
        lds_paths = [os.path.join(capture_folder, f) for f in lds_files]
        lds_paths.sort(key=os.path.getmtime, reverse=True)
        
        print("Available RF files:")
        for i, lds_path in enumerate(lds_paths, 1):
            lds_file = os.path.basename(lds_path)
            size_mb = os.path.getsize(lds_path) / (1024**2)
            mod_time = time.ctime(os.path.getmtime(lds_path))
            
            # Check for JSON metadata
            json_path = lds_path.replace('.lds', '.json')
            json_status = "✓" if os.path.exists(json_path) else "⚠️ no JSON"
            
            print(f"   {i}. {lds_file} ({size_mb:.1f} MB) - {mod_time} {json_status}")
        
        print("\nSelect files to decode (e.g., '1,3,4' or 'all'):")
        selection = input("> ").strip().lower()
        
        selected_files = []
        if selection == 'all':
            selected_files = lds_paths
        else:
            try:
                indices = [int(x.strip()) for x in selection.split(',')]
                for idx in indices:
                    if 1 <= idx <= len(lds_paths):
                        selected_files.append(lds_paths[idx-1])
                    else:
                        print(f"Warning: Invalid index {idx} - skipping")
            except ValueError:
                print("Invalid selection format")
                input("\nPress Enter to return to menu...")
                return
        
        if not selected_files:
            print("No valid files selected")
            input("\nPress Enter to return to menu...")
            return
        
        print(f"\nSelected {len(selected_files)} file(s) for parallel decode")
        
        # Show decode configuration interface
        print("\nThis feature will be available in a future update!")
        print("For now, use option 1 for automatic parallel decode.")
        
    except Exception as e:
        print(f"Error configuring parallel decode: {e}")
    
    input("\nPress Enter to return to menu...")

def run_parallel_demo():
    """Run parallel decode demo with limited frames"""
    clear_screen()
    display_header()
    print("\nPARALLEL DECODE DEMO MODE")
    print("=" * 35)
    print("Quick demonstration of parallel decode with limited frame processing")
    print("This processes only 100 frames per job for fast testing.")
    print()
    
    try:
        # Check if demo script exists
        demo_script = "test_parallel_decode.py"
        if not os.path.exists(demo_script):
            print(f"Demo script not found: {demo_script}")
            print("Please ensure test_parallel_decode.py is in the project directory")
            input("\nPress Enter to return to menu...")
            return
        
        print("Starting parallel decode demo...")
        print("This will process a limited number of frames from each RF file.")
        print()
        
        # Run the demo script
        result = subprocess.run([sys.executable, demo_script], 
                              capture_output=False, text=True)
        
        if result.returncode == 0:
            print("\n✅ Demo completed successfully!")
        else:
            print(f"\n⚠️ Demo finished with return code {result.returncode}")
    
    except Exception as e:
        print(f"Error running demo: {e}")
    
    input("\nPress Enter to return to menu...")

def test_progress_display():
    """Test the Rich progress display interface"""
    clear_screen()
    display_header()
    print("\nTEST PROGRESS DISPLAY")
    print("=" * 30)
    print("Test the Rich terminal interface with simulated decode jobs")
    print()
    
    try:
        # Check Rich availability
        try:
            from rich.console import Console
            from rich.table import Table
            from rich.live import Live
            from rich.progress import Progress, TextColumn, BarColumn, TimeRemainingColumn
            
            console = Console()
            console.print("[green]✓[/green] Rich library is available")
            console.print("[blue]Starting progress display test...[/blue]")
            
            # Create a simple progress test
            with Progress(
                TextColumn("[bold blue]{task.fields[name]}", justify="left"),
                BarColumn(bar_width=None),
                "[progress.percentage]{task.percentage:>3.1f}%",
                "[bold green]{task.fields[frames]:>6}/{task.fields[total_frames]:>6}",
                "[yellow]{task.fields[fps]:>4.1f} fps",
                "[cyan]{task.fields[status]}",
                console=console
            ) as progress:
                
                # Add some test jobs
                job1 = progress.add_task(
                    "Test Job 1",
                    name="job1",
                    total=1000,
                    frames=0,
                    total_frames=1000,
                    fps=0.0,
                    status="Starting"
                )
                
                job2 = progress.add_task(
                    "Test Job 2",
                    name="job2", 
                    total=1500,
                    frames=0,
                    total_frames=1500,
                    fps=0.0,
                    status="Starting"
                )
                
                # Simulate progress
                import random
                for i in range(50):
                    time.sleep(0.1)
                    
                    # Update job 1
                    frames1 = min(1000, i * 25)
                    fps1 = random.uniform(18, 27)
                    progress.update(job1, 
                                  advance=25, 
                                  frames=frames1,
                                  fps=fps1,
                                  status="Decoding" if frames1 < 1000 else "Complete")
                    
                    # Update job 2
                    frames2 = min(1500, i * 35)
                    fps2 = random.uniform(15, 25)
                    progress.update(job2,
                                  advance=35,
                                  frames=frames2, 
                                  fps=fps2,
                                  status="Decoding" if frames2 < 1500 else "Complete")
                    
                    if frames1 >= 1000 and frames2 >= 1500:
                        break
            
            console.print("\n[green]✅ Progress display test completed![/green]")
            
        except ImportError:
            print("Rich library not available - falling back to simple progress")
            print("Installing Rich library...")
            
            result = subprocess.run([sys.executable, '-m', 'pip', 'install', 'rich'], 
                                  capture_output=True, text=True)
            
            if result.returncode == 0:
                print("✅ Rich installed successfully!")
                print("You can now use the enhanced progress display.")
            else:
                print("⚠️ Failed to install Rich library")
                print("Parallel decode will use simple text progress")
    
    except Exception as e:
        print(f"Error testing progress display: {e}")
    
    input("\nPress Enter to return to menu...")

def manual_tbc_export():
    """Manually run tbc-video-export to create FFV1 video from TBC files in configured capture directory"""
    clear_screen()
    display_header()
    print("\nMANUAL TBC VIDEO EXPORT")
    print("=" * 30)
    print("This will create an FFV1 video file from a TBC file.")
    print()
    print("The exported video can be used for:")
    print("   • Visual verification of decode quality")
    print("   • Test pattern timing analysis")
    print("   • Preview of decoded content")
    print()
    
    try:
        # Import config functions to get the configured capture directory
        sys.path.append('.')
        from config import get_capture_directory
        
        # Look for .tbc files in configured capture directory
        capture_folder = get_capture_directory()
        
        if not os.path.exists(capture_folder):
            print(f"ERROR: Capture folder '{capture_folder}' does not exist!")
            print("Please run VHS-Decode first to create TBC files.")
            input("\nPress Enter to return to menu...")
            return
        
        # Find all .tbc files in capture folder
        tbc_files = [f for f in os.listdir(capture_folder) if f.lower().endswith('.tbc')]
        
        if not tbc_files:
            print(f"ERROR: No TBC files (.tbc) found in '{capture_folder}' folder!")
            print("Please run VHS-Decode first to create TBC files from RF captures.")
            input("\nPress Enter to return to menu...")
            return
        
        print(f"Found {len(tbc_files)} TBC file(s) in capture folder:")
        print()
        
        # Sort files by modification time (newest first)
        tbc_paths = [os.path.join(capture_folder, f) for f in tbc_files]
        tbc_paths.sort(key=os.path.getmtime, reverse=True)
        
        # Display files with selection numbers
        for i, tbc_path in enumerate(tbc_paths, 1):
            tbc_file = os.path.basename(tbc_path)
            file_size = os.path.getsize(tbc_path) / (1024**2)  # MB
            mod_time = time.ctime(os.path.getmtime(tbc_path))
            
            # Check if corresponding video already exists
            video_path = tbc_path.replace('.tbc', '_ffv1.mkv')
            status = "(video exists)" if os.path.exists(video_path) else ""
            
            print(f"   {i}. {tbc_file} ({file_size:.1f} MB) - {mod_time} {status}")
        
        print()
        print("Select which TBC file to export:")
        
        try:
            selection = input(f"Enter number (1-{len(tbc_paths)}) or 'q' to quit: ").strip().lower()
            
            if selection == 'q':
                print("TBC video export cancelled.")
                input("\nPress Enter to return to menu...")
                return
            
            file_index = int(selection) - 1
            if file_index < 0 or file_index >= len(tbc_paths):
                raise ValueError("Invalid selection")
            
            tbc_file = tbc_paths[file_index]
            
        except (ValueError, IndexError):
            print("ERROR: Invalid selection. Please enter a valid number.")
            input("\nPress Enter to return to menu...")
            return
        
        # Generate output video filename
        video_file = tbc_file.replace('.tbc', '_ffv1.mkv')
        
        print(f"\nSelected TBC file: {os.path.basename(tbc_file)}")
        print(f"Output video file: {os.path.basename(video_file)}")
        
        # Check if video file already exists
        if os.path.exists(video_file):
            existing_size = os.path.getsize(video_file) / (1024**2)  # MB
            print(f"\nWARNING: Video file already exists!")
            print(f"   {os.path.basename(video_file)} ({existing_size:.1f} MB)")
            overwrite = input("\nOverwrite existing file? (y/N): ").strip().lower()
            if overwrite not in ['y', 'yes']:
                print("TBC video export cancelled.")
                input("\nPress Enter to return to menu...")
                return
        
        # Confirm before starting
        confirm = input("\nStart TBC video export? (Y/n): ").strip().lower()
        if confirm in ['n', 'no']:
            print("TBC video export cancelled.")
            input("\nPress Enter to return to menu...")
            return
        
        # Import and run the export function from ddd_clockgen_sync
        print(f"\nStarting TBC video export...")
        try:
            sys.path.append('.')
            from ddd_clockgen_sync import run_tbc_video_export
            success = run_tbc_video_export(tbc_file, video_file)
            
            if success:
                file_size = os.path.getsize(video_file) / (1024**2)  # MB
                print(f"\nTBC video export completed successfully!")
                print(f"Video file created: {os.path.basename(video_file)} ({file_size:.1f} MB)")
            else:
                print(f"\nTBC video export failed.")
        except Exception as e:
            print(f"\nError running TBC video export: {e}")
    
    except KeyboardInterrupt:
        print("\nTBC video export cancelled by user.")
    except Exception as e:
        print(f"\nError during TBC video export: {e}")
    
    input("\nPress Enter to return to menu...")

def mux_video_audio():
    """Mux video and audio files to create final MKV"""
    clear_screen()
    display_header()
    print("\nMUX VIDEO + AUDIO (CREATE FINAL MKV)")
    print("=" * 45)
    print("Combine decoded video and audio files into a final MKV file.")
    print()
    print("This will:")
    print("   • Let you select a video file (.mkv)")
    print("   • Let you select an audio file (.wav/.flac)")
    print("   • Create a final MKV with synchronized audio and video")
    print("   • Preserve video quality while adding selected audio")
    print()
    
    try:
        # Import config functions to get the configured capture directory
        sys.path.append('.')
        from config import get_capture_directory
        
        # Look for files in configured capture directory
        capture_folder = get_capture_directory()
        
        if not os.path.exists(capture_folder):
            print(f"ERROR: Capture folder '{capture_folder}' does not exist!")
            print("Please run previous steps to create video and audio files.")
            input("\nPress Enter to return to menu...")
            return
        
        # STEP 1: Select video file
        # Find video files (.mkv)
        video_files = [f for f in os.listdir(capture_folder) if f.lower().endswith('.mkv')]
        
        if not video_files:
            print(f"ERROR: No video files (.mkv) found in '{capture_folder}' folder!")
            print("Please run 'TBC Video Export' first to create video files.")
            input("\nPress Enter to return to menu...")
            return
        
        print(f"Found {len(video_files)} video file(s) in capture folder:")
        print()
        
        # Sort files by modification time (newest first)
        video_paths = [os.path.join(capture_folder, f) for f in video_files]
        video_paths.sort(key=os.path.getmtime, reverse=True)
        
        # Display video files with selection numbers
        for i, video_path in enumerate(video_paths, 1):
            video_file = os.path.basename(video_path)
            file_size = os.path.getsize(video_path) / (1024**2)  # MB
            mod_time = time.ctime(os.path.getmtime(video_path))
            print(f"   {i}. {video_file} ({file_size:.1f} MB) - {mod_time}")
        
        print()
        print("Select which video file to use:")
        
        try:
            selection = input(f"Enter number (1-{len(video_paths)}) or 'q' to quit: ").strip().lower()
            
            if selection == 'q':
                print("Muxing cancelled.")
                input("\nPress Enter to return to menu...")
                return
            
            file_index = int(selection) - 1
            if file_index < 0 or file_index >= len(video_paths):
                raise ValueError("Invalid selection")
            
            selected_video = video_paths[file_index]
            
        except (ValueError, IndexError):
            print("ERROR: Invalid selection. Please enter a valid number.")
            input("\nPress Enter to return to menu...")
            return
        
        # STEP 2: Select audio file
        # Find audio files (.wav, .flac)
        audio_files = [f for f in os.listdir(capture_folder) if f.lower().endswith(('.wav', '.flac'))]
        
        if not audio_files:
            print(f"\nERROR: No audio files (.wav/.flac) found in '{capture_folder}' folder!")
            print("Please ensure you have audio files in the capture directory.")
            input("\nPress Enter to return to menu...")
            return
        
        print(f"\nFound {len(audio_files)} audio file(s) in capture folder:")
        print()
        
        # Sort audio files by modification time (newest first)
        audio_paths = [os.path.join(capture_folder, f) for f in audio_files]
        audio_paths.sort(key=os.path.getmtime, reverse=True)
        
        # Display audio files with selection numbers
        for i, audio_path in enumerate(audio_paths, 1):
            audio_file = os.path.basename(audio_path)
            file_size = os.path.getsize(audio_path) / (1024**2)  # MB
            mod_time = time.ctime(os.path.getmtime(audio_path))
            
            # Show if this is aligned audio
            status = "(aligned)" if "_aligned" in audio_file else ""
            
            print(f"   {i}. {audio_file} ({file_size:.1f} MB) - {mod_time} {status}")
        
        print()
        print("Select which audio file to use:")
        
        try:
            selection = input(f"Enter number (1-{len(audio_paths)}) or 'q' to quit: ").strip().lower()
            
            if selection == 'q':
                print("Muxing cancelled.")
                input("\nPress Enter to return to menu...")
                return
            
            file_index = int(selection) - 1
            if file_index < 0 or file_index >= len(audio_paths):
                raise ValueError("Invalid selection")
            
            selected_audio = audio_paths[file_index]
            
        except (ValueError, IndexError):
            print("ERROR: Invalid selection. Please enter a valid number.")
            input("\nPress Enter to return to menu...")
            return
        
        # Generate output filename based on video file
        video_basename = os.path.splitext(os.path.basename(selected_video))[0]
        audio_basename = os.path.splitext(os.path.basename(selected_audio))[0]
        
        # Create descriptive output filename
        final_mkv_file = os.path.join(capture_folder, f"{video_basename}_muxed_with_{audio_basename}.mkv")
        
        print(f"\nSelected files:")
        print(f"   Video: {os.path.basename(selected_video)}")
        print(f"   Audio: {os.path.basename(selected_audio)}")
        print(f"   Output: {os.path.basename(final_mkv_file)}")
        
        # Check if output file already exists
        if os.path.exists(final_mkv_file):
            existing_size = os.path.getsize(final_mkv_file) / (1024**2)  # MB
            print(f"\nWARNING: Output MKV file already exists!")
            print(f"   {os.path.basename(final_mkv_file)} ({existing_size:.1f} MB)")
            overwrite = input("\nOverwrite existing file? (y/N): ").strip().lower()
            if overwrite not in ['y', 'yes']:
                print("Muxing cancelled.")
                input("\nPress Enter to return to menu...")
                return
        
        # Confirm before starting
        confirm = input("\nStart video/audio muxing? (Y/n): ").strip().lower()
        if confirm in ['n', 'no']:
            print("Muxing cancelled.")
            input("\nPress Enter to return to menu...")
            return
        
        # Run FFmpeg to mux video and audio
        print(f"\nStarting video/audio muxing...")
        print("This may take several minutes depending on file size...")
        
        try:
            # Use FFmpeg to combine video and audio
            ffmpeg_command = [
                'ffmpeg',
                '-i', selected_video,      # Input video
                '-i', selected_audio,      # Input audio
                '-c:v', 'copy',           # Copy video stream (no re-encoding)
                '-c:a', 'flac',           # Encode audio as FLAC for archival quality
                '-map', '0:v:0',          # Map first video stream from input 0
                '-map', '1:a:0',          # Map first audio stream from input 1
                '-y',                     # Overwrite output file if it exists
                final_mkv_file
            ]
            
            print(f"Running FFmpeg command...")
            
            result = subprocess.run(ffmpeg_command, capture_output=True, text=True)
            
            if result.returncode == 0:
                file_size = os.path.getsize(final_mkv_file) / (1024**2)  # MB
                print(f"\nMuxing completed successfully!")
                print(f"Final MKV created: {os.path.basename(final_mkv_file)} ({file_size:.1f} MB)")
                print()
                print("The final MKV contains:")
                print(f"   • Video: {os.path.basename(selected_video)}")
                print(f"   • Audio: {os.path.basename(selected_audio)}")
                print(f"   • Audio codec: FLAC (archival quality)")
                print(f"   • Ready for archival storage")
            else:
                print(f"\nMuxing failed!")
                print(f"FFmpeg error output:")
                if result.stderr:
                    print(result.stderr)
                if result.stdout:
                    print(result.stdout)
                
        except FileNotFoundError:
            print(f"\nERROR: FFmpeg not found!")
            print("Please install FFmpeg to use the muxing feature.")
            print("Ubuntu/Debian: sudo apt install ffmpeg")
            print("Fedora: sudo dnf install ffmpeg")
            print("macOS: brew install ffmpeg")
        except Exception as e:
            print(f"\nError during muxing: {e}")
    
    except KeyboardInterrupt:
        print("\nMuxing cancelled by user.")
    except Exception as e:
        print(f"\nError during muxing process: {e}")
    
    input("\nPress Enter to return to menu...")

def manual_audio_alignment():
    """Manually run audio alignment using TBC JSON and WAV files in capture directory"""
    clear_screen()
    display_header()
    print("\nMANUAL AUDIO ALIGNMENT")
    print("=" * 30)
    print("This will align audio captures with RF timing data using the")
    print("vhs_audio_align.py script.")
    print()
    print("Process:")
    print("   • Finds captured audio (.wav/.flac) files in configured capture directory")
    print("   • Uses RF timing data to calculate audio sync offset")
    print("   • Creates properly aligned audio output")
    print("   • Purpose: Perfect A/V synchronization for archival")
    print()
    
    try:
        # Import config functions to get capture directory
        sys.path.append('.')
        from config import get_capture_directory
        
        # Look for audio files in capture directory only
        capture_folder = get_capture_directory()
        
        if not os.path.exists(capture_folder):
            print(f"ERROR: Capture folder '{capture_folder}' does not exist!")
            print("Please run 'Capture New Video' first to create audio captures.")
            input("\nPress Enter to return to menu...")
            return
        
        # Search for audio files in capture folder
        audio_files = [f for f in os.listdir(capture_folder) if f.lower().endswith(('.wav', '.flac'))]
        
        if not audio_files:
            print(f"ERROR: No audio files (.wav/.flac) found in capture directory!")
            print(f"Directory: {capture_folder}")
            print(f"\nPlease run 'Capture New Video' first to create audio captures.")
            input("\nPress Enter to return to menu...")
            return
        
        # Create full paths
        audio_paths = [os.path.join(capture_folder, f) for f in audio_files]
        
        print(f"Found {len(audio_files)} audio file(s) in capture directory:")
        print()
        
        # Sort files by modification time (newest first)
        audio_paths.sort(key=os.path.getmtime, reverse=True)
        
        # Display files with selection numbers
        for i, audio_path in enumerate(audio_paths, 1):
            audio_file = os.path.basename(audio_path)
            file_size = os.path.getsize(audio_path) / (1024**2)  # MB
            mod_time = time.ctime(os.path.getmtime(audio_path))
            
            # Check if corresponding TBC JSON exists (supports both WAV and FLAC)
            audio_ext = os.path.splitext(audio_file)[1].lower()
            base_name = os.path.splitext(audio_path)[0]
            
            # Look for TBC JSON in capture folder (same folder as the audio file)
            tbc_json_possibilities = [
                base_name + '.tbc.json',
                audio_path.replace('_audio' + audio_ext, '.tbc.json'),
                audio_path.replace('av_alignment_capture' + audio_ext, 'RF-Sample*.tbc.json')
            ]
            
            # Also look for RF-Sample files in the capture folder
            import glob
            rf_pattern = os.path.join(capture_folder, 'RF-Sample*.tbc.json')
            rf_matches = glob.glob(rf_pattern)
            if rf_matches:
                tbc_json_possibilities.extend(rf_matches)
            
            tbc_status = "(no TBC JSON found)"
            for tbc_path in tbc_json_possibilities:
                if '*' in tbc_path:
                    # Handle wildcard patterns
                    matches = glob.glob(tbc_path)
                    if matches:
                        tbc_status = f"(→ {os.path.basename(matches[0])})"
                        break
                elif os.path.exists(tbc_path):
                    tbc_status = f"(→ {os.path.basename(tbc_path)})"
                    break
            
            print(f"   {i}. {audio_file} ({file_size:.1f} MB) - {mod_time} {tbc_status}")
        
        print()
        print("Select which audio file to align:")
        
        try:
            selection = input(f"Enter number (1-{len(audio_paths)}) or 'q' to quit: ").strip().lower()
            
            if selection == 'q':
                print("Audio alignment cancelled.")
                input("\nPress Enter to return to menu...")
                return
            
            file_index = int(selection) - 1
            if file_index < 0 or file_index >= len(audio_paths):
                raise ValueError("Invalid selection")
            
            audio_file_path = audio_paths[file_index]
            
        except (ValueError, IndexError):
            print("ERROR: Invalid selection. Please enter a valid number.")
            input("\nPress Enter to return to menu...")
            return
        
        # Now find the corresponding TBC JSON file
        tbc_json_file = None
        audio_ext = os.path.splitext(audio_file_path)[1].lower()
        base_name = os.path.splitext(audio_file_path)[0]
        
        tbc_json_possibilities = [
            base_name + '.tbc.json',
            audio_file_path.replace('_audio' + audio_ext, '.tbc.json'),
            audio_file_path.replace('av_alignment_capture' + audio_ext, 'RF-Sample*.tbc.json')
        ]
        
        # Also look for RF-Sample files in the capture folder
        import glob
        rf_pattern = os.path.join(capture_folder, 'RF-Sample*.tbc.json')
        rf_matches = glob.glob(rf_pattern)
        if rf_matches:
            # Use the most recent RF-Sample file
            rf_matches.sort(key=os.path.getmtime, reverse=True)
            tbc_json_possibilities.append(rf_matches[0])
        
        for tbc_path in tbc_json_possibilities:
            if os.path.exists(tbc_path):
                tbc_json_file = tbc_path
                break
        
        if not tbc_json_file:
            print(f"\nERROR: No corresponding TBC JSON file found!")
            print(f"Selected audio: {os.path.basename(audio_file_path)}")
            print(f"Looked for:")
            for tbc_path in tbc_json_possibilities:
                if '*' not in tbc_path:  # Don't show wildcard patterns in error message  
                    print(f"   - {os.path.basename(tbc_path)}")
            print(f"\nPlease ensure TBC JSON files are available in the capture directory.")
            input("\nPress Enter to return to menu...")
            return
        
        # Generate output aligned audio filename (support both WAV and FLAC)
        if audio_ext == '.wav':
            aligned_audio_file = audio_file_path.replace('.wav', '_aligned.wav')
        elif audio_ext == '.flac':
            aligned_audio_file = audio_file_path.replace('.flac', '_aligned.wav')  # Output as WAV
        else:
            # Fallback for other extensions
            aligned_audio_file = os.path.splitext(audio_file_path)[0] + '_aligned.wav'
        
        print(f"\nSelected audio file: {os.path.basename(audio_file_path)}")
        print(f"TBC JSON file: {os.path.basename(tbc_json_file)}")
        print(f"Output aligned audio: {os.path.basename(aligned_audio_file)}")
        
        # Check if aligned audio file already exists
        if os.path.exists(aligned_audio_file):
            existing_size = os.path.getsize(aligned_audio_file) / (1024**2)  # MB
            print(f"\nWARNING: Aligned audio file already exists!")
            print(f"   {os.path.basename(aligned_audio_file)} ({existing_size:.1f} MB)")
            overwrite = input("\nOverwrite existing file? (y/N): ").strip().lower()
            if overwrite not in ['y', 'yes']:
                print("Audio alignment cancelled.")
                input("\nPress Enter to return to menu...")
                return
        
        # Confirm before starting
        confirm = input("\nStart audio alignment? (Y/n): ").strip().lower()
        if confirm in ['n', 'no']:
            print("Audio alignment cancelled.")
            input("\nPress Enter to return to menu...")
            return
        
        # Import and run the alignment function from ddd_clockgen_sync
        print(f"\nStarting audio alignment...")
        try:
            sys.path.append('.')
            from ddd_clockgen_sync import analyze_alignment_with_tbc
            result = analyze_alignment_with_tbc(audio_file_path, tbc_json_file)
            
            if result is not None:
                if isinstance(result, str):  # File path returned
                    print(f"\nAudio alignment completed successfully!")
                    if os.path.exists(result):
                        file_size = os.path.getsize(result) / (1024**2)  # MB
                        print(f"Aligned audio file: {os.path.basename(result)} ({file_size:.1f} MB)")
                elif isinstance(result, (int, float)):  # Offset value returned
                    print(f"\nAudio alignment analysis completed!")
                    print(f"Detected timing offset: {result:.3f} seconds")
                    if result == 0.0:
                        print("Audio appears to be well aligned already.")
                    else:
                        print(f"Apply this offset when processing final audio.")
                else:
                    print(f"\nAudio alignment completed successfully!")
                    print(f"Result: {result}")
            else:
                print(f"\nAudio alignment failed or could not detect timing patterns.")
                print(f"This may indicate:")
                print(f"   - No clear timing patterns in the audio")
                print(f"   - Incompatible audio/TBC formats")
                print(f"   - Missing test pattern audio signals")
        except Exception as e:
            print(f"\nError running audio alignment: {e}")
    
    except KeyboardInterrupt:
        print("\nAudio alignment cancelled by user.")
    except Exception as e:
        print(f"\nError during audio alignment: {e}")
    
    input("\nPress Enter to return to menu...")

def capture_new_video():
    """Start video capture workflow using the updated DomesdayDuplicator with file-based stop mechanism"""
    clear_screen()
    display_header()
    print("\nCAPTURE NEW VIDEO")
    print("=" * 25)
    print("Start Domesday Duplicator capture with synchronised audio")
    print("(Uses updated file-based stop mechanism for proper JSON metadata generation)")
    print()
    
    # Import and run the original capture function
    try:
        sys.path.append('.')
        from ddd_clockgen_sync import start_capture_and_record
        start_capture_and_record()
    except Exception as e:
        print(f"Error starting capture: {e}")
    
    input("\nPress Enter to return to menu...")

def run_av_alignment():
    """Perform A/V alignment"""
    clear_screen()
    display_header()
    print("\nA/V ALIGNMENT")
    print("=" * 15)
    print("Automated audio/video synchronisation")
    print()
    
    # Import and run the original alignment function
    try:
        sys.path.append('.')
        from ddd_clockgen_sync import perform_av_alignment
        perform_av_alignment()
    except Exception as e:
        print(f"Error during alignment: {e}")
    
    input("\nPress Enter to return to menu...")


def display_av_calibration_menu():
    """Display the A/V calibration submenu and handle user selection"""
    while True:
        clear_screen()
        display_header()
        print("\nA/V CALIBRATION MENU")
        print("=" * 30)
        print("1. A/V 1 Second Pulse Calibration")
        print("2. Precision Timecode Capture (Recommended)")
        print("3. Validate VHS Capture Results")
        print("4. MP4 Timecode Validation (Direct Test)")
        print("5. Manual Calibration Value Entry")
        print("6. Calculate DdD Startup Delay")
        print("7. Calculate SOX Startup Delay")
        print("8. Validate Results")
        print("9. Create Sync Test Videos (MP4)")
        print("10. Create DVD ISOs from MP4s")
        print("11. View Testing Setup")
        print("12. Return to Main Menu")
        
        selection = input("\nSelect calibration option (1-12): ").strip().lower()
        
        if selection == '1':
            run_av_alignment()
            break  # Return to main menu after calibration
        elif selection == '2':
            precision_timecode_capture()
            break  # Return to main menu after timecode capture
        elif selection == '3':
            capture_vhs_validation_tape()
            break  # Return to main menu after VHS validation
        elif selection == '4':
            validate_mp4_timecode()
            break  # Return to main menu after MP4 validation
        elif selection == '5':
            manual_calibration_entry()
            break  # Return to main menu after manual entry
        elif selection == '6':
            calculate_ddd_startup_delay()
            break  # Return to main menu after startup delay calculation
        elif selection == '7':
            calculate_sox_startup_delay()
            break  # Return to main menu after SOX delay calculation
        elif selection == '8':
            validate_calibration_results()
            break  # Return to main menu after validation
        elif selection == '9':
            create_sync_test_videos()
            # Don't break here - return to this menu after creating videos
        elif selection == '10':
            create_dvd_isos()
            # Don't break here - return to this menu after creating ISOs
        elif selection == '11':
            show_project_summary()
            # Don't break here - return to this menu after viewing setup
        elif selection == '12':
            break  # Return to main menu
        else:
            print("Invalid selection. Please enter 1-12.")


def manual_calibration_entry():
    """Allow manual entry of calibration delay value"""
    clear_screen()
    display_header()
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
    
    # Import config functions
    sys.path.append('.')
    from config import load_config, save_config
    
    # Read the current delay from the configuration file
    config = load_config()
    current_delay = config.get('audio_delay', 0.000)
    print(f"\nCurrent delay in configuration: {current_delay:.3f}s")
    
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
            
            print(f"\nIMPORTANT: This will update the configuration file (config.json)")
            print(f"   The delay value will be stored for future captures.")
            
            confirm = input("\nApply this calibration? (y/N): ").strip().lower()
            
            if confirm in ['y', 'yes']:
                # Update the delay value in the configuration
                config['audio_delay'] = delay_value
                success = save_config(config)
                if success:
                    print(f"\nCALIBRATION APPLIED SUCCESSFULLY!")
                    print(f"   Configuration delay updated to: {delay_value:.3f}s")
                    print(f"   Changes will take effect on next capture.")
                else:
                    print(f"\nFailed to update configuration delay value.")
                    print(f"   Check file permissions and try again.")
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
    
    input("\nPress Enter to return to menu...")

def calculate_ddd_startup_delay():
    """Calculate DomesdayDuplicator startup delay using shell-based timing method for accuracy"""
    clear_screen()
    display_header()
    print("\nCALCULATE DdD STARTUP DELAY")
    print("=" * 35)
    print("This tool measures the time between issuing the DomesdayDuplicator start command")
    print("and when the first .lds file data is actually written to disk.")
    print()
    print("Purpose:")
    print("   • Measure DomesdayDuplicator hardware/software startup latency")
    print("   • Understand timing delays in the capture pipeline")
    print("   • Compare with SOX startup delay for sync analysis")
    print("   • Help debug audio sync timing issues")
    print()
    print("Process:")
    print("   1. Uses shell-based timing for maximum accuracy")
    print("   2. Tests DomesdayDuplicator headless capture mode")
    print("   3. Monitors file creation and data writing separately")
    print("   4. Provides millisecond-precision timing measurements")
    print()
    print("This test uses a 5-second capture to minimize impact.")
    print()
    
    # Use temp directory for this test
    temp_dir = "temp"
    if not os.path.exists(temp_dir):
        os.makedirs(temp_dir)
        print(f"Created temp directory: {temp_dir}")
    
    print(f"Using test directory: {os.path.abspath(temp_dir)}")
    print()
    
    # Check for existing .lds files and offer to clean
    existing_lds = [f for f in os.listdir(temp_dir) if f.endswith('.lds')]
    if existing_lds:
        print(f"Found {len(existing_lds)} existing .lds file(s) in temp directory:")
        for f in existing_lds[:3]:  # Show first 3
            print(f"   - {f}")
        if len(existing_lds) > 3:
            print(f"   ... and {len(existing_lds) - 3} more")
        print()
        
        clean_choice = input("Clean existing .lds files before test? (Y/n): ").strip().lower()
        if clean_choice not in ['n', 'no']:
            try:
                for f in existing_lds:
                    os.remove(os.path.join(temp_dir, f))
                print(f"Removed {len(existing_lds)} existing .lds files")
            except Exception as e:
                print(f"Warning: Could not remove some files: {e}")
        print()
    
    # Prepare test filename for DomesdayDuplicator
    test_filename = "ddd_startup_test"
    test_lds_file = os.path.join(temp_dir, f"{test_filename}.lds")
    
    print("\033[91mIMPORTANT SETUP:\033[0m")
    print(f"\033[91m   ⚠️  Ensure your RF input is connected (tape playing or signal generator)\033[0m")
    print(f"\033[91m   ⚠️  This uses DomesdayDuplicator headless mode for accurate timing\033[0m")
    print(f"   ⚠️  Test captures for 5 seconds then automatically stops")
    print(f"   ⚠️  Uses shell timing for maximum measurement accuracy")
    print(f"   ⚠️  Output file: {test_filename}.lds in temp directory")
    print()
    
    confirm = input("Ready to start DdD startup delay measurement? (Y/n): ").strip().lower()
    if confirm in ['n', 'no']:
        print("Test cancelled.")
        input("\nPress Enter to return to menu...")
        return
    
    print("\nStarting shell-based DdD startup delay measurement...")
    print("This will capture for exactly 5 seconds then stop.")
    print()
    
    try:
        # Create shell script for precise timing measurement
        # Note: DomesdayDuplicator doesn't take output file parameter in headless mode
        # It uses its own naming scheme and saves to current directory or configured location
        shell_script = f'''
#!/bin/bash
echo "Testing DomesdayDuplicator startup timing..."
start_time=$(date +%s.%3N)
echo "Start time: $start_time"

# Record existing .lds files before starting
existing_files=$(find "{temp_dir}" -name "*.lds" 2>/dev/null | wc -l)
echo "Existing .lds files: $existing_files"

# Start DomesdayDuplicator in background
DomesdayDuplicator --start-capture --headless &
ddd_pid=$!
echo "DomesdayDuplicator PID: $ddd_pid"

# Monitor for new .lds files
file_created_time=""
data_time=""
new_file=""

# Wait for DomesdayDuplicator to start and create file
for i in {{1..300}}; do  # Wait up to 30 seconds (300 * 0.1s)
    # Check for new .lds files
    current_files=$(find "{temp_dir}" -name "*.lds" 2>/dev/null | wc -l)
    
    if [ "$current_files" -gt "$existing_files" ] && [ -z "$file_created_time" ]; then
        file_created_time=$(date +%s.%3N)
        # Find the newest .lds file
        new_file=$(find "{temp_dir}" -name "*.lds" -printf "%T@ %p\\n" 2>/dev/null | sort -n | tail -1 | cut -d' ' -f2-)
        echo "File created at: $file_created_time"
        echo "New file: $(basename "$new_file")"
    fi
    
    # Check if the new file has data
    if [ -n "$new_file" ] && [ -f "$new_file" ] && [ -s "$new_file" ] && [ -z "$data_time" ]; then
        data_time=$(date +%s.%3N)
        size=$(stat -c%s "$new_file" 2>/dev/null || echo "0")
        echo "Data written at: $data_time"
        echo "File size: $size bytes"
        break
    fi
    
    sleep 0.1
done

# Let capture run for 5 seconds total, then stop
echo "Letting capture run for 5 seconds..."
sleep 5

# Stop DomesdayDuplicator
echo "Stopping DomesdayDuplicator..."
DomesdayDuplicator --stop-capture 2>/dev/null || kill $ddd_pid 2>/dev/null
wait $ddd_pid 2>/dev/null

echo "DomesdayDuplicator stopped"
end_time=$(date +%s.%3N)

# Calculate delays
if [ -n "$file_created_time" ]; then
    creation_delay=$(echo "$file_created_time - $start_time" | bc -l)
    echo "Creation delay: ${{creation_delay}}s"
fi

if [ -n "$data_time" ]; then
    data_delay=$(echo "$data_time - $start_time" | bc -l)
    echo "Data writing delay: ${{data_delay}}s"
fi

total_time=$(echo "$end_time - $start_time" | bc -l)
echo "Total time: ${{total_time}}s"

if [ -n "$new_file" ]; then
    echo "Created file: $(basename "$new_file")"
    if [ -f "$new_file" ]; then
        final_size=$(stat -c%s "$new_file" 2>/dev/null || echo "0")
        echo "Final size: $final_size bytes"
    fi
fi
'''
        
        # Write and execute shell script
        script_path = os.path.join(temp_dir, "ddd_timing_test.sh")
        with open(script_path, 'w') as f:
            f.write(shell_script)
        
        os.chmod(script_path, 0o755)
        
        print("Executing shell-based timing measurement...")
        print()
        
        # Run the shell script and capture output
        result = subprocess.run(['bash', script_path], capture_output=True, text=True, timeout=60)
        
        print(result.stdout)
        if result.stderr:
            print("DomesdayDuplicator stderr output:")
            print(result.stderr)
        
        # Parse the timing results from output
        lines = result.stdout.split('\n')
        creation_delay = None
        data_delay = None
        total_time = None
        created_file = None
        final_size = None
        
        for line in lines:
            if 'Creation delay:' in line:
                try:
                    creation_delay = float(line.split('Creation delay: ')[1].replace('s', ''))
                except:
                    pass
            elif 'Data writing delay:' in line:
                try:
                    data_delay = float(line.split('Data writing delay: ')[1].replace('s', ''))
                except:
                    pass
            elif 'Total time:' in line:
                try:
                    total_time = float(line.split('Total time: ')[1].replace('s', ''))
                except:
                    pass
            elif 'Created file:' in line:
                try:
                    created_file = line.split('Created file: ')[1].strip()
                except:
                    pass
            elif 'Final size:' in line:
                try:
                    final_size = int(line.split('Final size: ')[1].split(' bytes')[0])
                except:
                    pass
        
        # Display formatted results
        print("\n" + "=" * 60)
        print("DdD STARTUP DELAY MEASUREMENT RESULTS")
        print("=" * 60)
        
        if creation_delay is not None and data_delay is not None:
            print(f"\nTIMING BREAKDOWN:")
            print(f"   File creation delay: {creation_delay*1000:.1f}ms ({creation_delay:.3f}s)")
            print(f"   Data writing delay: {data_delay*1000:.1f}ms ({data_delay:.3f}s)")
            print(f"   Total test time: {total_time:.1f}s")
            
            print(f"\nDdD STARTUP DELAY ANALYSIS:")
            print(f"   ✓ Effective startup delay: {data_delay*1000:.1f}ms ({data_delay:.3f}s)")
            
            # Provide interpretation
            if data_delay < 0.100:
                print(f"   → Very fast startup (<100ms)")
            elif data_delay < 0.500:
                print(f"   → Fast startup (<500ms)")
            elif data_delay < 1.000:
                print(f"   → Moderate startup (<1s)")
            else:
                print(f"   → Slow startup (>1s)")
            
            print(f"\nIMPLICATIONS FOR AUDIO SYNC:")
            print(f"   • DomesdayDuplicator has ~{data_delay*1000:.0f}ms startup delay")
            print(f"   • Video recording starts {data_delay:.3f}s after command issued")
            print(f"   • This is the baseline delay for video in sync calculations")
            
            # Compare with current audio delay config and SOX delay
            try:
                from config import load_config
                config = load_config()
                current_delay = config.get('audio_delay', 0.000)
                
                print(f"\nTIMING COMPARISON:")
                print(f"   Current audio delay: {current_delay:.3f}s ({current_delay*1000:.0f}ms)")
                print(f"   Measured DdD delay: {data_delay:.3f}s ({data_delay*1000:.0f}ms)")
                
                # Calculate the effective offset
                net_offset = current_delay - data_delay
                print(f"   Net timing offset: {net_offset:+.3f}s ({net_offset*1000:+.0f}ms)")
                
                if abs(net_offset) < 0.050:  # Within 50ms
                    print(f"   ✓ Audio and video delays are well balanced")
                elif net_offset > 0:
                    print(f"   → Audio delay is {net_offset:.3f}s longer than DdD delay")
                    print(f"   → Audio will start after video (audio delay compensates for more than just DdD)")
                else:
                    print(f"   → Audio delay is {abs(net_offset):.3f}s shorter than DdD delay")
                    print(f"   → Audio may start before video (potential sync issue)")
                    
            except Exception as e:
                print(f"   Could not compare with current config: {e}")
        else:
            print(f"   ✗ Could not parse timing measurements")
            print(f"   ✗ Check the raw output above for timing information")
            print(f"\nPOSSIBLE ISSUES:")
            print(f"   • DomesdayDuplicator not properly installed or configured")
            print(f"   • No RF input signal detected")
            print(f"   • Hardware connection issues")
            print(f"   • Insufficient permissions to write files")
        
        # Show created file info
        if created_file and final_size is not None:
            print(f"\nCAPTURE FILE DETAILS:")
            print(f"   File: {created_file}")
            print(f"   Size: {final_size} bytes ({final_size/1024/1024:.2f} MB)")
            print(f"   Location: {temp_dir}/")
            
            # Estimate data rate for RF captures
            if final_size > 0 and total_time and total_time > 0:
                data_rate_mbps = (final_size / 1024 / 1024) / total_time
                print(f"   Estimated data rate: {data_rate_mbps:.2f} MB/s")
                
                # RF captures are typically 40-50 MB/s for good signal
                if data_rate_mbps > 30:
                    print(f"   → Data rate looks normal for RF capture")
                elif data_rate_mbps > 10:
                    print(f"   → Lower data rate may indicate weak signal")
                else:
                    print(f"   → Very low data rate, check RF input signal")
            
            # Clean up test file
            try:
                test_file_path = os.path.join(temp_dir, created_file)
                if os.path.exists(test_file_path):
                    os.remove(test_file_path)
                    print(f"   → Test file cleaned up")
            except:
                print(f"   → Test file left for inspection")
        
        # Clean up script file
        try:
            os.remove(script_path)
        except:
            pass
        
        print("\n" + "=" * 60)
        
    except KeyboardInterrupt:
        print("\nTest cancelled by user")
        # Try to stop DomesdayDuplicator if it's running and clean up files
        try:
            subprocess.run(['DomesdayDuplicator', '--stop-capture'], timeout=5)
            script_path = os.path.join(temp_dir, "ddd_timing_test.sh")
            if os.path.exists(script_path):
                os.remove(script_path)
        except:
            pass
    except subprocess.TimeoutExpired:
        print("\nTest timed out - DomesdayDuplicator may be having issues")
        print("Check hardware connections and RF input signal")
    except Exception as e:
        print(f"\nError during DdD startup delay measurement: {e}")
        import traceback
        traceback.print_exc()
    
    input("\nPress Enter to return to menu...")

def calculate_sox_startup_delay():
    """Calculate SOX startup delay using shell-based timing method for accuracy"""
    clear_screen()
    display_header()
    print("\nCALCULATE SOX STARTUP DELAY")
    print("=" * 35)
    print("This tool measures the time between issuing the SOX recording command")
    print("and when audio data is actually written to disk.")
    print()
    print("Purpose:")
    print("   • Measure SOX audio recording startup latency")
    print("   • Understand timing delays in the audio capture pipeline")
    print("   • Compare with DomesdayDuplicator startup delay")
    print("   • Help debug audio sync timing issues")
    print()
    print("Process:")
    print("   1. Uses shell-based timing for maximum accuracy")
    print("   2. Tests actual SOX command used by capture system")
    print("   3. Monitors file creation and data writing separately")
    print("   4. Provides millisecond-precision timing measurements")
    print()
    print("This test uses a 3-second recording with your actual SOX configuration.")
    print()
    
    # Use temp directory for this test
    temp_dir = "temp"
    if not os.path.exists(temp_dir):
        os.makedirs(temp_dir)
        print(f"Created temp directory: {temp_dir}")
    
    print(f"Using test directory: {os.path.abspath(temp_dir)}")
    print()
    
    # Import to get actual SOX command used by system
    try:
        sys.path.append('.')
        from ddd_clockgen_sync import get_sox_command
        test_audio_file = os.path.join(temp_dir, "sox_startup_test.flac")
        sox_command_parts = get_sox_command(test_audio_file)
        
        # Add trim parameter for 3-second test
        sox_command_full = sox_command_parts + ['trim', '0', '3']
        
        print("SOX Configuration:")
        print(f"   Command: {' '.join(sox_command_full)}")
        print(f"   Test file: {test_audio_file}")
        print()
        
    except Exception as e:
        print(f"Error getting SOX command: {e}")
        print("Using fallback configuration...")
        test_audio_file = os.path.join(temp_dir, "sox_startup_test.flac")
        sox_command_full = ['sox', '-t', 'alsa', '-r', '78125', '-b', '24', 'hw:2,0', 
                           test_audio_file, 'remix', '1', '2', 'trim', '0', '3']
    
    # Check for existing test file and clean if needed
    if os.path.exists(test_audio_file):
        print(f"Found existing test file: {os.path.basename(test_audio_file)}")
        clean_choice = input("Remove existing test file? (Y/n): ").strip().lower()
        if clean_choice not in ['n', 'no']:
            try:
                os.remove(test_audio_file)
                print("Removed existing test file")
            except Exception as e:
                print(f"Warning: Could not remove file: {e}")
        print()
    
    print("\033[91mIMPORTANT SETUP:\033[0m")
    print(f"\033[91m   ⚠️  Ensure your CXADC+ADC-ClockGen is connected and working\033[0m")
    print(f"\033[91m   ⚠️  This uses your actual capture hardware configuration\033[0m")
    print(f"   ⚠️  Test records for 3 seconds then automatically stops")
    print(f"   ⚠️  Uses shell timing for maximum measurement accuracy")
    print()
    
    confirm = input("Ready to start SOX startup delay measurement? (Y/n): ").strip().lower()
    if confirm in ['n', 'no']:
        print("Test cancelled.")
        input("\nPress Enter to return to menu...")
        return
    
    print("\nStarting shell-based SOX startup delay measurement...")
    print("This will record for exactly 3 seconds then stop.")
    print()
    
    try:
        # Create shell script for precise timing measurement
        shell_script = f'''
#!/bin/bash
echo "Testing SOX startup timing..."
start_time=$(date +%s.%3N)
echo "Start time: $start_time"

# Start SOX in background and capture its PID
{' '.join([f"'{part}'" for part in sox_command_full])} &
sox_pid=$!

# Monitor for file creation and data
file="{test_audio_file}"
created_time=""
data_time=""

while [ -z "$data_time" ] && kill -0 $sox_pid 2>/dev/null; do
    if [ -f "$file" ] && [ -z "$created_time" ]; then
        created_time=$(date +%s.%3N)
        echo "File created at: $created_time"
    fi
    
    if [ -f "$file" ] && [ -s "$file" ] && [ -z "$data_time" ]; then
        data_time=$(date +%s.%3N)
        echo "Data written at: $data_time"
        size=$(stat -c%s "$file")
        echo "File size: $size bytes"
        break
    fi
    
    sleep 0.1
done

wait $sox_pid
echo "SOX finished"
end_time=$(date +%s.%3N)

# Calculate delays
if [ -n "$created_time" ]; then
    creation_delay=$(echo "$created_time - $start_time" | bc -l)
    echo "Creation delay: ${{creation_delay}}s"
fi

if [ -n "$data_time" ]; then
    data_delay=$(echo "$data_time - $start_time" | bc -l)
    echo "Data writing delay: ${{data_delay}}s"
fi

total_time=$(echo "$end_time - $start_time" | bc -l)
echo "Total time: ${{total_time}}s"
'''
        
        # Write and execute shell script
        script_path = os.path.join(temp_dir, "sox_timing_test.sh")
        with open(script_path, 'w') as f:
            f.write(shell_script)
        
        os.chmod(script_path, 0o755)
        
        print("Executing shell-based timing measurement...")
        print()
        
        # Run the shell script and capture output
        result = subprocess.run(['bash', script_path], capture_output=True, text=True, timeout=30)
        
        print(result.stdout)
        if result.stderr:
            print("SOX stderr output:")
            print(result.stderr)
        
        # Parse the timing results from output
        lines = result.stdout.split('\n')
        creation_delay = None
        data_delay = None
        total_time = None
        
        for line in lines:
            if 'Creation delay:' in line:
                try:
                    creation_delay = float(line.split('Creation delay: ')[1].replace('s', ''))
                except:
                    pass
            elif 'Data writing delay:' in line:
                try:
                    data_delay = float(line.split('Data writing delay: ')[1].replace('s', ''))
                except:
                    pass
            elif 'Total time:' in line:
                try:
                    total_time = float(line.split('Total time: ')[1].replace('s', ''))
                except:
                    pass
        
        # Display formatted results
        print("\n" + "=" * 60)
        print("SOX STARTUP DELAY MEASUREMENT RESULTS")
        print("=" * 60)
        
        if creation_delay is not None and data_delay is not None:
            print(f"\nTIMING BREAKDOWN:")
            print(f"   File creation delay: {creation_delay*1000:.1f}ms ({creation_delay:.3f}s)")
            print(f"   Data writing delay: {data_delay*1000:.1f}ms ({data_delay:.3f}s)")
            print(f"   Total test time: {total_time:.1f}s")
            
            print(f"\nSOX STARTUP DELAY ANALYSIS:")
            print(f"   ✓ Effective startup delay: {data_delay*1000:.1f}ms ({data_delay:.3f}s)")
            
            # Provide interpretation
            if data_delay < 0.100:
                print(f"   → Very fast startup (<100ms)")
            elif data_delay < 0.500:
                print(f"   → Fast startup (<500ms)")
            elif data_delay < 1.000:
                print(f"   → Moderate startup (<1s)")
            else:
                print(f"   → Slow startup (>1s)")
            
            print(f"\nIMPLICATIONS FOR AUDIO SYNC:")
            print(f"   • SOX has ~{data_delay*1000:.0f}ms startup delay")
            print(f"   • Audio recording starts {data_delay:.3f}s after command issued")
            print(f"   • This contributes to audio sync timing offset")
            
            # Compare with current audio delay config and hardcoded value
            try:
                from config import load_config
                config = load_config()
                current_delay = config.get('audio_delay', 0.000)
                
                print(f"\nCURRENT CONFIGURATION COMPARISON:")
                print(f"   Current audio delay: {current_delay:.3f}s ({current_delay*1000:.0f}ms)")
                print(f"   Measured SOX delay: {data_delay:.3f}s ({data_delay*1000:.0f}ms)")
                
                # Check hardcoded value in calibration code
                print(f"\nHARDCODED VALUE CHECK:")
                print(f"   Calibration code uses: 0.560s (560ms) - NEEDS UPDATE!")
                print(f"   Actual measured delay: {data_delay:.3f}s ({data_delay*1000:.0f}ms)")
                
                if abs(data_delay - 0.560) > 0.100:  # More than 100ms difference
                    print(f"   ⚠️  SIGNIFICANT DIFFERENCE: {abs(data_delay - 0.560)*1000:.0f}ms")
                    print(f"   ⚠️  Consider updating SOX_STARTUP_DELAY in calibration code")
                    print(f"   ⚠️  File: ddd_clockgen_sync.py, line ~482")
                else:
                    print(f"   ✓ Hardcoded value is reasonably close")
                    
            except Exception as e:
                print(f"   Could not compare with current config: {e}")
        else:
            print(f"   ✗ Could not parse timing measurements")
            print(f"   ✗ Check the raw output above for timing information")
        
        # Show created file info
        if os.path.exists(test_audio_file):
            final_size = os.path.getsize(test_audio_file)
            print(f"\nRECORDING FILE DETAILS:")
            print(f"   File: {os.path.basename(test_audio_file)}")
            print(f"   Size: {final_size} bytes ({final_size/1024/1024:.2f} MB)")
            print(f"   Location: {test_audio_file}")
            
            # Estimate recording quality for 78.125kHz/24-bit/2-channel
            expected_size = 3 * 78125 * 3 * 3  # 3s * 78.125kHz * 3ch * 3bytes(24-bit)
            if final_size > 0:
                print(f"   Expected size: ~{expected_size} bytes ({expected_size/1024/1024:.2f} MB)")
                if abs(final_size - expected_size) / expected_size < 0.2:  # Within 20%
                    print(f"   → Recording size looks correct")
                elif final_size < expected_size * 0.5:
                    print(f"   → Recording may be incomplete or truncated")
                else:
                    print(f"   → Recording size differs from expected (format overhead or different config)")
            
            # Clean up test file
            try:
                os.remove(test_audio_file)
                print(f"   → Test file cleaned up")
            except:
                print(f"   → Test file left for inspection")
        
        # Clean up script file
        try:
            os.remove(script_path)
        except:
            pass
        
        print("\n" + "=" * 60)
        
    except KeyboardInterrupt:
        print("\nTest cancelled by user")
        # Clean up any test files
        try:
            if os.path.exists(test_audio_file):
                os.remove(test_audio_file)
            script_path = os.path.join(temp_dir, "sox_timing_test.sh")
            if os.path.exists(script_path):
                os.remove(script_path)
        except:
            pass
    except subprocess.TimeoutExpired:
        print("\nTest timed out - SOX may be having issues")
        print("Check audio hardware and driver configuration")
    except Exception as e:
        print(f"\nError during SOX startup delay measurement: {e}")
        import traceback
        traceback.print_exc()
    
    input("\nPress Enter to return to menu...")

def precision_timecode_capture():
    """Automated Precision Timecode Capture with VHS Timecode Test Patterns"""
    clear_screen()
    display_header()
    print("\nPRECISION TIMECODE ANALYSIS (RECOMMENDED)")
    print("=" * 50)
    print("Automated A/V synchronisation using VHS timecode test patterns")
    print("This is the most accurate calibration method available.")
    print()
    print("Process:")
    print("   1. Record VHS timecode test pattern to tape")
    print("   2. Capture back with Domesday Duplicator + audio interface")
    print("   3. Analyze timecode for microsecond-accurate timing measurements")
    print("   4. Automatically update calibration settings")
    print()
    print("This uses the SAME timecode validation code as the MP4 Direct Test,")
    print("ensuring consistent and reliable results across both workflows.")
    print()
    
    # For calibration, always use project temp directory (not user's configured capture directory)
    sys.path.append('.')
    project_root = os.path.dirname(os.path.abspath(__file__))
    capture_folder = os.path.join(project_root, "temp")
    
    # Create temp directory if it doesn't exist
    if not os.path.exists(capture_folder):
        try:
            os.makedirs(capture_folder)
            print(f"Created calibration temp directory: {capture_folder}")
        except Exception as e:
            print(f"ERROR: Could not create calibration temp directory: {e}")
            input("\nPress Enter to return to menu...")
            return
    
    print(f"Using calibration directory: {capture_folder}")
    
    # CAPTURE PHASE - Fixed 45-second duration for calibration consistency
    print("\nSTEP 1: CAPTURE VHS WITH DOMESDAY DUPLICATOR + SOX AUDIO")
    print("=" * 55)
    
    # Use fixed 45-second duration for calibration (not user-configurable)
    alignment_duration_seconds = 45
    print(f"Calibration capture duration: {alignment_duration_seconds} seconds (fixed for consistency)")
    
    # Generate automated filename with timestamp
    from datetime import datetime
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    alignment_base_name = f"precision_calibration_{timestamp}"
    print(f"Using calibration filename: {alignment_base_name}")
    
    # Create alignment file paths with timestamp
    alignment_capture_filename = os.path.join(capture_folder, f"{alignment_base_name}.flac")
    alignment_rf_filename = os.path.join(capture_folder, f"{alignment_base_name}.lds")
    alignment_tbc_filename = os.path.join(capture_folder, f"{alignment_base_name}.tbc")
    alignment_tbc_json_filename = os.path.join(capture_folder, f"{alignment_base_name}.tbc.json")
    alignment_video_filename = os.path.join(capture_folder, f"{alignment_base_name}_ffv1.mkv")
    
    print("\033[91mIMPORTANT SETUP REQUIRED:\033[0m")
    print(f"\033[91m   ⚠️  You must manually configure the Domesday Duplicator Client to point to: {os.path.abspath(capture_folder)}\033[0m")
    print(f"\033[91m   ⚠️  Set DomesdayDuplicator filename to: {alignment_base_name}\033[0m")
    print(f"   This ensures all calibration files are organized with matching names.")
    print()
    
    print("BEFORE STARTING CALIBRATION CAPTURE:")
    print("1. Make sure you've recorded at least 5 minutes of the included test pattern files onto a VHS tape")
    print("2. Ensure your Domesday duplicator is plugged in and powered on")
    print("3. Ensure your clockgen lite is connected and working")
    print("4. Configure DomesdayDuplicator output location and filename as shown above")
    print("5. Insert your VHS tape into your VCR and press play")
    print()
    
    print("\033[92m⚠️  Press Play on your VCR before pressing Enter now or alignment will be out of sync\033[0m")
    input("When all setup steps above are complete, press Enter to start Calibration Capture (or Ctrl-C to cancel): ")

    # Capture calibration using command line DomesdayDuplicator
    print("\nStarting RF + Audio capture...")
    try:
        from ddd_clockgen_sync import get_sox_command
        
        alignment_sox_command = get_sox_command(alignment_capture_filename)
        
        try:
            # 1. Start video capture using command line (headless mode for minimal latency)
            print("Starting DomesdayDuplicator capture (headless mode for minimal latency)...")
            ddd_process = subprocess.Popen(['DomesdayDuplicator', '--start-capture', '--headless'], 
                                      stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            time.sleep(2)  # Wait for startup
            
            # Check if process started successfully
            if ddd_process.poll() is None:
                print("DomesdayDuplicator capture started successfully")
                
                # For calibration, use zero delay as baseline (no audio delay)
                print("Starting SOX audio recording after 0.0s delay (calibration baseline)...")
                time.sleep(0.0)  # Calibration baseline - zero delay
                
                print(f"Starting SOX audio recording for {alignment_duration_seconds} seconds...")
                print(f"Command: {' '.join(alignment_sox_command)}")
                capture_process = subprocess.Popen(alignment_sox_command)
                print("Audio recording started")
                
                print("\nCAPTURE IN PROGRESS")
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
                
                # 3. Stop audio recording
                print("\nStopping audio recording...")
                capture_process.terminate()
                capture_process.wait()
                print("Audio recording stopped")

                # 3. Stop video capture using command line
                print("\nStopping DomesdayDuplicator capture...")
                stop_result = subprocess.run(['DomesdayDuplicator', '--stop-capture'], 
                                           capture_output=True, text=True, timeout=10)
                
                if stop_result.returncode == 0:
                    print("DomesdayDuplicator capture stopped successfully")
                else:
                    print(f"Warning: DomesdayDuplicator stop returned code {stop_result.returncode}")
                    print("Please verify capture was stopped properly")
                
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
                print(f"ERROR: Could not start DomesdayDuplicator capture!")
                stdout, stderr = ddd_process.communicate()
                print(f"Process failed to start properly")
                if stderr:
                    print(f"Error output: {stderr}")
                print("Please ensure:")
                print("1. DomesdayDuplicator is installed and in your PATH")
                print("2. The hardware is connected properly")
                print("3. No other instance is already running")
                print("\nCalibration capture cancelled.")
                input("\nPress Enter to return to menu...")
                return
        except subprocess.TimeoutExpired:
            print("ERROR: DomesdayDuplicator command timed out")
            print("This might indicate the command is hanging or waiting for user input")
            input("\nPress Enter to return to menu...")
            return
        except FileNotFoundError:
            print("ERROR: DomesdayDuplicator command not found!")
            print("Please ensure DomesdayDuplicator is installed and available in your PATH")
            input("\nPress Enter to return to menu...")
            return
        except Exception as e:
            print(f"Capture error: {e}")
            input("\nPress Enter to return to menu...")
            return

        # RF Decode step
        print("\nSTEP 2: RF DECODE WORKFLOW")
        print("=" * 30)
        print("Looking for RF capture file in temp folder...")
        
        # Find the most recent .lds file (RF capture) in temp folder
        if not os.path.exists(capture_folder):
            print(f"Temp folder {capture_folder} does not exist!")
            print("Please ensure the DomesdayDuplicator output location is configured correctly.")
            input("\nPress Enter to return to menu...")
            return
            
        lds_files = [f for f in os.listdir(capture_folder) if f.endswith('.lds')]
        if not lds_files:
            print(f"No RF capture files (.lds) found in {capture_folder}!")
            print("Please ensure the Domesday Duplicator created an RF capture file in the temp folder.")
            input("\nPress Enter to return to menu...")
            return
        
        # Get the most recent RF file (with full path)
        lds_paths = [os.path.join(capture_folder, f) for f in lds_files]
        rf_file = max(lds_paths, key=os.path.getmtime)
        print(f"Found RF capture: {rf_file}")
        
        # Check if we already have decoded files
        tbc_file = rf_file.replace('.lds', '.tbc')
        tbc_json_file = rf_file.replace('.lds', '.tbc.json')
        
        if os.path.exists(tbc_json_file):
            print(f"TBC JSON already exists: {tbc_json_file}")
        else:
            print("\nRunning vhs-decode...")
            from ddd_clockgen_sync import run_vhs_decode_with_params
            if not run_vhs_decode_with_params(rf_file, tbc_file, 'pal', 'SP'):
                print("RF decode failed")
                input("\nPress Enter to return to menu...")
                return
        
        # Check if we need to export video
        video_file = rf_file.replace('.lds', '_ffv1.mkv')
        if os.path.exists(video_file):
            print(f"Video export already exists: {video_file}")
        else:
            print("\nRunning tbc-video-export...")
            from ddd_clockgen_sync import run_tbc_video_export
            if not run_tbc_video_export(tbc_file, video_file):
                print("Video export failed, but continuing with audio alignment...")
        
        print("\nRF decode workflow complete!")
        
        # Audio timing analysis and config update
        print("\nSTEP 3: AUDIO ALIGNMENT ANALYSIS")
        print("=" * 35)
        print(f"Using TBC JSON file: {tbc_json_file}")
        print("\nAnalyzing raw audio directly for calibration")
        print("(This eliminates alignment-induced measurement errors)")
        
        # Check if captured audio file exists
        if not os.path.exists(alignment_capture_filename):
            print(f"\nERROR: Audio capture file not found: {alignment_capture_filename}")
            print("The audio capture may have failed.")
            input("\nPress Enter to return to menu...")
            return
        
        print(f"\nAnalyzing alignment between:")
        print(f"   TBC JSON: {os.path.basename(tbc_json_file)}")
        print(f"   Audio: {os.path.basename(alignment_capture_filename)}")
        
        try:
            from ddd_clockgen_sync import analyze_alignment_with_tbc
            timing_result = analyze_alignment_with_tbc(alignment_capture_filename, tbc_json_file)
            
            if timing_result is not None:
                if isinstance(timing_result, (int, float)):
                    measured_offset = timing_result
                    print(f"\n=== CALIBRATION MEASUREMENT RESULTS ===")
                    print(f"Raw measured offset: {measured_offset:+.3f}s")
                    print(f"   Positive = audio starts after video")
                    print(f"   Negative = audio starts before video")
                    
                    # Calculate required delay (same logic as menu 5.1)
                    if measured_offset >= 0:
                        required_delay = measured_offset
                        print(f"\nRequired audio delay: {required_delay:.3f}s")
                        print(f"   This delay will synchronize audio with video")
                        
                        # Apply calibration automatically
                        try:
                            from config import load_config, save_config
                            config = load_config()
                            config['audio_delay'] = required_delay
                            
                            if save_config(config):
                                print(f"\n✓ CALIBRATION APPLIED: {required_delay:.3f}s delay saved to config")
                                print("✓ This calibration will be used for future captures")
                            else:
                                print("\n⚠ Failed to save calibration to config file")
                        except Exception as e:
                            print(f"\n⚠ Error applying calibration: {e}")
                    else:
                        print(f"\nNegative offset detected - this suggests system timing issues")
                        print(f"Please review the measurement and consider manual calibration")
                        
                else:
                    print(f"\nAlignment analysis completed with result: {timing_result}")
            else:
                print(f"\nAlignment analysis failed or could not detect timing patterns.")
                print(f"This may indicate:")
                print(f"   - No clear timing patterns in the audio")
                print(f"   - Incompatible audio/TBC formats")
                print(f"   - Missing test pattern audio signals")
                
        except Exception as e:
            print(f"\nError during alignment analysis: {e}")
            print(f"Continuing to validation step...")
            
    except Exception as e:
        print(f"Error during capture process: {e}")
    
    print("\n" + "="*60)
    print("CALIBRATION CAPTURE COMPLETED")
    print("=" * 60)
    print("VHS timecode capture has been completed successfully!")
    print()
    print("Files created in calibration temp directory:")
    print(f"• RF capture (.lds)")
    print(f"• Decoded video (.mkv)")
    print(f"• Raw audio (.flac)")
    print(f"• TBC timing data (.tbc.json)")
    print()
    print("NEXT STEPS:")
    print("• Use 'Menu 5 → Option 3: Capture VHS Validation Tape' to analyze these files")
    print("• The validation will measure your capture timing and calculate needed calibration")
    print("• Apply the calibration results using 'Menu 5 → Option 5: Manual Calibration Entry'")
    
    input("\nPress Enter to return to menu...")


def capture_vhs_validation_tape():
    """Capture VHS Validation Tape function - wrapper for vhs_capture_validation"""
    vhs_capture_validation()

def vhs_capture_validation():
    """Validate existing VHS captures using enhanced VHS timecode analysis"""
    clear_screen()
    display_header()
    print("\nVHS CAPTURE VALIDATION (EXISTING FILES)")
    print("=" * 45)
    print("Analyze existing VHS captures using enhanced VHS-specific sync detection")
    print("This uses the same enhanced detection as the calibration workflow.")
    print()
    print("Purpose:")
    print("   • Test the VHS calibration detection on your existing captures")
    print("   • Measure audio/video sync offset in captured VHS files")
    print("   • Uses enhanced sync pulse detection for VHS mechanical variations")
    print()
    print("This uses the SAME enhanced VHS detection as step 5.2 calibration,")
    print("but works on files you've already captured.")
    print()
    
    # Look for video and audio files in temp directory
    temp_dir = "temp"
    if not os.path.exists(temp_dir):
        print(f"Temp directory '{temp_dir}' not found.")
        print("Please ensure you have some VHS captures in the temp folder.")
        input("\nPress Enter to return to menu...")
        return
    
    print(f"Looking for VHS captures in {temp_dir}/ directory...")
    
    # Find video files
    video_files = []
    audio_files = []
    
    for f in os.listdir(temp_dir):
        if f.lower().endswith(('_ffv1.mkv', '.mkv', '.mp4')):
            video_files.append(os.path.join(temp_dir, f))
        elif f.lower().endswith(('.wav', '.flac')):
            audio_files.append(os.path.join(temp_dir, f))
    
    if not video_files:
        print(f"No video files found in {temp_dir}/ directory.")
        print("Please ensure you have VHS video captures (.mkv files) in the temp folder.")
        input("\nPress Enter to return to menu...")
        return
    
    if not audio_files:
        print(f"No audio files found in {temp_dir}/ directory.")
        print("Please ensure you have VHS audio captures (.wav/.flac files) in the temp folder.")
        input("\nPress Enter to return to menu...")
        return
    
    # Sort by modification time (newest first)
    video_files.sort(key=os.path.getmtime, reverse=True)
    audio_files.sort(key=os.path.getmtime, reverse=True)
    
    print(f"\nFound {len(video_files)} video file(s) and {len(audio_files)} audio file(s)")
    print()
    
    # Let user select video file
    print("VIDEO FILES:")
    for i, video_file in enumerate(video_files, 1):
        filename = os.path.basename(video_file)
        size_mb = os.path.getsize(video_file) / (1024*1024)
        mod_time = time.ctime(os.path.getmtime(video_file))
        print(f"   {i}. {filename} ({size_mb:.1f} MB) - {mod_time}")
    
    try:
        video_selection = input(f"\nSelect video file (1-{len(video_files)}): ").strip()
        video_idx = int(video_selection) - 1
        if video_idx < 0 or video_idx >= len(video_files):
            raise ValueError("Invalid selection")
        selected_video = video_files[video_idx]
    except (ValueError, IndexError):
        print("Invalid selection.")
        input("\nPress Enter to return to menu...")
        return
    
    # Let user select audio file
    print(f"\nAUDIO FILES:")
    for i, audio_file in enumerate(audio_files, 1):
        filename = os.path.basename(audio_file)
        size_mb = os.path.getsize(audio_file) / (1024*1024)
        mod_time = time.ctime(os.path.getmtime(audio_file))
        print(f"   {i}. {filename} ({size_mb:.1f} MB) - {mod_time}")
    
    try:
        audio_selection = input(f"\nSelect audio file (1-{len(audio_files)}): ").strip()
        audio_idx = int(audio_selection) - 1
        if audio_idx < 0 or audio_idx >= len(audio_files):
            raise ValueError("Invalid selection")
        selected_audio = audio_files[audio_idx]
    except (ValueError, IndexError):
        print("Invalid selection.")
        input("\nPress Enter to return to menu...")
        return
    
    print(f"\nSelected files:")
    print(f"   Video: {os.path.basename(selected_video)}")
    print(f"   Audio: {os.path.basename(selected_audio)}")
    
    # Check if the analyzer script exists
    analyzer_script = "tools/timecode-generator/vhs_timecode_analyzer.py"
    if not os.path.exists(analyzer_script):
        print(f"\nERROR: VHS timecode analyzer not found at {analyzer_script}")
        print("The analyzer script is required for VHS validation.")
        input("\nPress Enter to return to menu...")
        return
    
    print(f"\nStarting VHS capture validation...")
    print("This uses enhanced VHS-specific sync pulse detection.")
    print("Analysis may take several minutes...")
    print()
    
    try:
        # Run the analyzer with the refactored VHS timecode analyzer
        # This uses the same enhanced detection as calibration step 5.2
        result = subprocess.run([
            sys.executable, analyzer_script,
            '--video', selected_video,
            '--audio', selected_audio
        ], capture_output=True, text=True, timeout=1800)  # 30 minute timeout
        
        if result.returncode == 0:
            print("=" * 70)
            print("VHS CAPTURE VALIDATION RESULTS")
            print("=" * 70)
            print(result.stdout)
            print("=" * 70)
            print()
            
            # Parse the output to extract timing offset/delay information
            calculated_delay = None
            output_lines = result.stdout.split('\n')
            
            # Look for the absolute delay value from the analyzer
            import re
            for line in output_lines:
                # Look for "Required delay: X.XXXs"
                delay_match = re.search(r'Required delay:\s*([0-9]+\.?[0-9]*)s', line, re.IGNORECASE)
                if delay_match:
                    try:
                        calculated_delay = float(delay_match.group(1))
                        break
                    except ValueError:
                        continue
                
                # Handle the "Cannot fix" case
                if "Cannot fix" in line:
                    calculated_delay = None # Indicates unfixable sync issue
                    break
            
            print("VALIDATION INTERPRETATION:")
            print("✓ SUCCESS: VHS capture analysis completed using enhanced detection")
            print("✓ This uses the same enhanced sync detection as calibration step 5.2")
            print("✓ Results show how well your VHS capture is synchronized")
            print()
            
            # If we found a calculated delay, offer to save it to config
            if calculated_delay is not None:
                print(f"CALCULATED CALIBRATION:")
                print(f"   Recommended delay: {calculated_delay:.3f}s")
                print()
                
                # Load current config to show comparison
                try:
                    sys.path.append('.')
                    from config import load_config, save_config
                    config = load_config()
                    current_delay = config.get('audio_delay', 0.000)
                    
                    print(f"   Current delay in config: {current_delay:.3f}s")
                    print(f"   Suggested new delay: {calculated_delay:.3f}s")
                    print(f"   Change would be: {calculated_delay - current_delay:+.3f}s")
                    print()
                    
                    # Offer to save the calculated delay
                    apply_delay = input("Apply this calculated delay to config.json? (y/N): ").strip().lower()
                    
                    if apply_delay in ['y', 'yes']:
                        config['audio_delay'] = calculated_delay
                        success = save_config(config)
                        if success:
                            print(f"\n✓ SUCCESS: Configuration updated!")
                            print(f"   Audio delay set to: {calculated_delay:.3f}s")
                            print(f"   Changes will take effect on next capture.")
                        else:
                            print(f"\n✗ ERROR: Failed to save configuration.")
                            print(f"   Check file permissions and try again.")
                    else:
                        print(f"\nConfiguration not changed.")
                        print(f"   You can manually apply delay {calculated_delay:.3f}s using Menu 5 → Option 5")
                        
                except Exception as e:
                    print(f"\nNote: Could not access configuration system: {e}")
                    print(f"   You can manually apply delay {calculated_delay:.3f}s using Menu 5 → Option 5")
            else:
                print("Note: No specific delay recommendation found in analysis output.")
                print("   Review the timing measurements above for manual calibration.")
            
            print()
            print("NEXT STEPS:")
            print("• Review the timing offset measurement above")
            if calculated_delay is not None:
                print(f"• The recommended delay ({calculated_delay:.3f}s) can improve synchronization")
            print("• If sync issues persist, consider re-capturing with adjusted settings")
            print("• The enhanced detection handles VHS mechanical variations")
            
        else:
            print("=" * 70)
            print("VHS CAPTURE VALIDATION FAILED")
            print("=" * 70)
            print("Error details:")
            if result.stderr:
                print(result.stderr)
            if result.stdout:
                print("Output:")
                print(result.stdout)
            print()
            print("TROUBLESHOOTING:")
            print("• Ensure the video contains VHS timecode test pattern")
            print("• Verify audio contains FSK timecode data")
            print("• Check that files are not corrupted")
            print("• The enhanced VHS detection may still have found issues")
            
    except subprocess.TimeoutExpired:
        print("ERROR: Analysis timed out (>30 minutes)")
        print("This may indicate very long captures or system performance issues.")
    except Exception as e:
        print(f"ERROR: Failed to run analysis: {e}")
    
    input("\nPress Enter to return to menu...")

def validate_mp4_timecode():
    """Validate MP4 file timecode using the VHS timecode validation method"""
    clear_screen()
    display_header()
    print("\nMP4 TIMECODE VALIDATION (DIRECT TEST)")
    print("=" * 45)
    print("Test an MP4 timecode file directly using the same validation method")
    print("that is used in the VHS capture workflow.")
    print()
    print("Purpose:")
    print("   • Validate that timecode encoding is working correctly")
    print("   • Test the validation method on a known-good MP4 file")
    print("   • Prove that the same code works for both MP4 and VHS analysis")
    print()
    print("This uses the EXACT SAME timecode validation code as the VHS")
    print("calibration method, providing a controlled test environment.")
    print()
    
    # Look for timecode MP4 files in the media/mp4 directory
    mp4_dir = "media/mp4"
    if os.path.exists(mp4_dir):
        # Find timecode-related MP4 files
        mp4_files = []
        for f in os.listdir(mp4_dir):
            if f.endswith('.mp4') and ('timecode' in f.lower() or 'pattern' in f.lower()):
                mp4_files.append(os.path.join(mp4_dir, f))
        
        if mp4_files:
            print(f"Found {len(mp4_files)} potential timecode file(s):")
            mp4_files.sort(key=os.path.getmtime, reverse=True)  # Most recent first
            
            for i, mp4_file in enumerate(mp4_files, 1):
                filename = os.path.basename(mp4_file)
                size_mb = os.path.getsize(mp4_file) / (1024*1024)
                mod_time = time.ctime(os.path.getmtime(mp4_file))
                print(f"   {i}. {filename} ({size_mb:.1f} MB) - {mod_time}")
            
            print(f"   {len(mp4_files) + 1}. Enter custom path")
            print(f"   {len(mp4_files) + 2}. Cancel")
            
            try:
                selection = input(f"\nSelect MP4 file (1-{len(mp4_files) + 2}): ").strip()
                selection_num = int(selection)
                
                if 1 <= selection_num <= len(mp4_files):
                    mp4_file = mp4_files[selection_num - 1]
                elif selection_num == len(mp4_files) + 1:
                    mp4_file = input("\nEnter full path to MP4 file: ").strip()
                    if not mp4_file or not os.path.exists(mp4_file):
                        print(f"File not found: {mp4_file}")
                        input("\nPress Enter to return to menu...")
                        return
                elif selection_num == len(mp4_files) + 2:
                    print("Validation cancelled.")
                    input("\nPress Enter to return to menu...")
                    return
                else:
                    print("Invalid selection.")
                    input("\nPress Enter to return to menu...")
                    return
                    
            except (ValueError, IndexError):
                print("Invalid selection.")
                input("\nPress Enter to return to menu...")
                return
        else:
            # No timecode files found, ask for manual input
            print("No timecode MP4 files found in media/mp4/ directory.")
            print("\nTo create timecode test files, use Menu 4 → Option 3 (VHS Timecode Test Pattern)")
            print()
            mp4_file = input("Enter full path to MP4 file to validate (or press Enter to cancel): ").strip()
            
            if not mp4_file:
                print("Validation cancelled.")
                input("\nPress Enter to return to menu...")
                return
            
            if not os.path.exists(mp4_file):
                print(f"File not found: {mp4_file}")
                input("\nPress Enter to return to menu...")
                return
    else:
        # No media/mp4 directory
        print("media/mp4/ directory not found.")
        print("\nTo create timecode test files, use Menu 4 → Option 3 (VHS Timecode Test Pattern)")
        print()
        mp4_file = input("Enter full path to MP4 file to validate (or press Enter to cancel): ").strip()
        
        if not mp4_file:
            print("Validation cancelled.")
            input("\nPress Enter to return to menu...")
            return
        
        if not os.path.exists(mp4_file):
            print(f"File not found: {mp4_file}")
            input("\nPress Enter to return to menu...")
            return
    
    print(f"\nSelected file: {os.path.basename(mp4_file)}")
    print(f"File size: {os.path.getsize(mp4_file) / (1024*1024):.1f} MB")
    print()
    
    # Check if the cycle-aware validator exists
    validator_script = "tools/validate_mp4_timecode.py"
    if not os.path.exists(validator_script):
        print(f"ERROR: MP4 timecode validator not found at {validator_script}")
        print("The cycle-aware validator script is required for validation.")
        input("\nPress Enter to return to menu...")
        return
    
    print("Running validation using the cycle-aware MP4 timecode validator...")
    print("This will lock onto the 4-step cycle structure for frame-accurate measurement.")
    print("This may take a few moments...")
    print()
    
    try:
        # Run the cycle-aware validator (Menu 5.3 mode - MP4 with audio and video)
        result = subprocess.run([
            sys.executable, validator_script, mp4_file
        ], capture_output=True, text=True, timeout=300)  # 5 minute timeout
        
        if result.returncode == 0:
            print("=" * 60)
            print("MP4 TIMECODE VALIDATION RESULTS")
            print("=" * 60)
            print(result.stdout)
            print("=" * 60)
            print()
            print("VALIDATION INTERPRETATION:")
            print("✓ SUCCESS: The timecode validation method is working correctly")
            print("✓ The same code that validates VHS captures works on MP4 files")
            print("✓ This proves the validation system is functioning properly")
            print()
            print("NEXT STEPS:")
            print("• You can now use this validated method for VHS capture analysis")
            print("• The same validation logic will work for captured VHS content")
            print("• Any issues found would indicate problems with VHS capture, not the validation method")
        else:
            print("=" * 60)
            print("MP4 TIMECODE VALIDATION FAILED")
            print("=" * 60)
            print("Error details:")
            if result.stderr:
                print(result.stderr)
            if result.stdout:
                print("Output:")
                print(result.stdout)
            print()
            print("TROUBLESHOOTING:")
            print("• Check that the MP4 file contains valid timecode")
            print("• Ensure the file was created with the VHS timecode generator")
            print("• Verify that audio channel contains FSK timecode data")
            print("• Try creating a new timecode test file with Menu 4 → Option 3")
            
    except subprocess.TimeoutExpired:
        print("ERROR: Validation timed out (>5 minutes)")
        print("This may indicate issues with the MP4 file or validation method.")
    except Exception as e:
        print(f"ERROR: Failed to run validation: {e}")
    
    input("\nPress Enter to return to menu...")

def validate_calibration_results():
    """Validate calibration results using configured delay"""
    clear_screen()
    display_header()
    print("\nVALIDATE CALIBRATION RESULTS")
    print("=" * 40)
    print("This will test your current calibration by capturing with the")
    print("configured delay and measuring the resulting offset.")
    print()
    print("Process:")
    print("   1. Uses configured delay (not zero) for capture")
    print("   2. Runs complete workflow: capture → decode → align → analyze")
    print("   3. Measures final timing offset")
    print("   4. Creates debug output for analysis")
    print("   5. Shows if calibration is working correctly")
    print()
    print("Expected result: ~0.000s offset if calibration is accurate")
    print()
    
    # Import config functions to show current settings
    sys.path.append('.')
    from config import load_config
    
    config = load_config()
    current_delay = config.get('audio_delay', 0.000)
    
    print(f"Current configuration:")
    print(f"   Audio delay: {current_delay:.3f}s")
    print(f"   This delay will be applied during validation capture")
    print()
    
    if current_delay == 0.000:
        print("WARNING: Audio delay is 0.000s")
        print("   You may want to run calibration first to establish a baseline.")
        print("   Continuing anyway...")
        print()
    
    confirm = input("Start validation capture? (Y/n): ").strip().lower()
    if confirm in ['n', 'no']:
        print("Validation cancelled.")
        input("\nPress Enter to return to menu...")
        return
    
    try:
        # Import and run the validation function from ddd_clockgen_sync
        from ddd_clockgen_sync import validate_calibration_with_configured_delay
        validate_calibration_with_configured_delay()
    except Exception as e:
        print(f"Error during validation: {e}")
    
    input("\nPress Enter to return to menu...")


def get_current_script_delay():
    """Read the current delay value from the script file"""
    script_file = "ddd_clockgen_sync.py"
    
    try:
        with open(script_file, 'r') as f:
            content = f.read()
        
        import re
        # Pattern to find: audio_delay = X.XXX  # Calibrated delay for audio/video synchronization
        pattern = r'audio_delay = ([0-9]+\.[0-9]+)\s*#\s*Calibrated delay for audio/video synchronization'
        
        matches = re.findall(pattern, content)
        if matches:
            return float(matches[0])
        else:
            print("   Warning: Could not find current delay in script")
            return 0.0  # Default fallback
            
    except Exception as e:
        print(f"   Error reading current delay: {e}")
        return 0.0  # Default fallback

def update_script_delay_values(new_delay):
    """Update the delay values in the script file"""
    script_file = "ddd_clockgen_sync.py"  # Target script file
    
    try:
        # Read the current script content
        with open(script_file, 'r') as f:
            content = f.read()
        
        # Find and replace the delay values
        import re
        
        # Pattern 1: audio_delay = X.XXX in start_capture_and_record function
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
def show_project_summary():
    """Display testing setup status and file summary"""
    clear_screen()
    display_header()
    print("\nTESTING SETUP")
    print("=" * 25)
    print("Overview of test pattern videos, DVD ISOs, and calibration files")
    print()
    
    # Check for calibration sync test MP4s
    print("Calibration Videos (1s ON/OFF):")
    pal_sync_mp4 = "media/mp4/pal_sync_test_1hour.mp4"
    ntsc_sync_mp4 = "media/mp4/ntsc_sync_test_1hour.mp4"
    
    if os.path.exists(pal_sync_mp4):
        size_mb = os.path.getsize(pal_sync_mp4) / (1024*1024)
        print(f"   PAL:  {pal_sync_mp4} ({size_mb:.1f} MB)")
    else:
        print(f"   PAL:  {pal_sync_mp4} (not created)")
    
    if os.path.exists(ntsc_sync_mp4):
        size_mb = os.path.getsize(ntsc_sync_mp4) / (1024*1024)
        print(f"   NTSC: {ntsc_sync_mp4} ({size_mb:.1f} MB)")
    else:
        print(f"   NTSC: {ntsc_sync_mp4} (not created)")
    
    # Check for Belle Nuit static chart MP4s
    print("\nBelle Nuit Static Charts:")
    pal_belle_mp4 = "media/mp4/pal_belle_nuit.mp4"
    ntsc_belle_mp4 = "media/mp4/ntsc_belle_nuit.mp4"
    
    if os.path.exists(pal_belle_mp4):
        size_mb = os.path.getsize(pal_belle_mp4) / (1024*1024)
        print(f"   PAL:  {pal_belle_mp4} ({size_mb:.1f} MB)")
    else:
        print(f"   PAL:  {pal_belle_mp4} (not created)")
    
    if os.path.exists(ntsc_belle_mp4):
        size_mb = os.path.getsize(ntsc_belle_mp4) / (1024*1024)
        print(f"   NTSC: {ntsc_belle_mp4} ({size_mb:.1f} MB)")
    else:
        print(f"   NTSC: {ntsc_belle_mp4} (not created)")
    
    # Check for DVD ISOs
    print("\nDVD ISO Files:")
    iso_dir = "media/iso"
    if os.path.exists(iso_dir):
        iso_files = [f for f in os.listdir(iso_dir) if f.endswith('.iso')]
        if iso_files:
            for iso_file in sorted(iso_files):
                iso_path = os.path.join(iso_dir, iso_file)
                size_mb = os.path.getsize(iso_path) / (1024*1024)
                print(f"   {iso_file} ({size_mb:.1f} MB)")
        else:
            print("   No ISO files found")
    else:
        print("   ISO directory not found")
    
    # Check for custom test pattern videos
    print("\nCustom Test Pattern Videos:")
    custom_pal_sync = "media/mp4/custom_pal_sync_test_1hour.mp4"
    custom_ntsc_sync = "media/mp4/custom_ntsc_sync_test_1hour.mp4"
    custom_pal_belle = "media/mp4/custom_pal_belle_nuit.mp4"
    custom_ntsc_belle = "media/mp4/custom_ntsc_belle_nuit.mp4"
    
    custom_videos_exist = False
    if os.path.exists(custom_pal_sync):
        size_mb = os.path.getsize(custom_pal_sync) / (1024*1024)
        print(f"   PAL Sync:    {custom_pal_sync} ({size_mb:.1f} MB)")
        custom_videos_exist = True
    if os.path.exists(custom_ntsc_sync):
        size_mb = os.path.getsize(custom_ntsc_sync) / (1024*1024)
        print(f"   NTSC Sync:   {custom_ntsc_sync} ({size_mb:.1f} MB)")
        custom_videos_exist = True
    if os.path.exists(custom_pal_belle):
        size_mb = os.path.getsize(custom_pal_belle) / (1024*1024)
        print(f"   PAL Belle:   {custom_pal_belle} ({size_mb:.1f} MB)")
        custom_videos_exist = True
    if os.path.exists(custom_ntsc_belle):
        size_mb = os.path.getsize(custom_ntsc_belle) / (1024*1024)
        print(f"   NTSC Belle:  {custom_ntsc_belle} ({size_mb:.1f} MB)")
        custom_videos_exist = True
    
    if not custom_videos_exist:
        print("   No custom test pattern videos created")
    
    # Check for test patterns
    print("\nTest Patterns:")
    patterns = [
        ("PAL Pattern", "media/Test Patterns/testchartpal.tif"),
        ("NTSC Pattern", "media/Test Patterns/testchartntsc.tif"),
        ("Custom Pattern", "media/Test Patterns/custom_pattern.tif")
    ]
    for name, pattern in patterns:
        if os.path.exists(pattern):
            print(f"   {name} ({os.path.basename(pattern)})")
        else:
            print(f"   {name} ({os.path.basename(pattern)}) (missing)")
    
    # Show tools status
    print("\nAvailable Tools:")
    tools = [
        ("Sync Test Creator", "tools/create_sync_test.py"),
        ("ISO Creator", "tools/create_iso_from_mp4.py"),
        ("Audio Alignment", "tools/audio-sync/vhs_audio_align.py"),
        ("Summary Tool", "tools/sync_test_summary.py")
    ]
    
    for name, path in tools:
        if os.path.exists(path):
            print(f"   {name}")
        else:
            print(f"   {name} (missing)")
    
    input("\nPress Enter to return to menu...")

def check_dependencies():
    """Check system dependencies including dvdauthor"""
    clear_screen()
    display_header()
    print("\nDEPENDENCY CHECK")
    print("=" * 25)
    
    # Check if check_dependencies.py exists and run it
    if os.path.exists('check_dependencies.py'):
        try:
            print("Running main dependency checker...")
            subprocess.run([sys.executable, 'check_dependencies.py'])
        except Exception as e:
            print(f"Error running main dependency checker: {e}")
    else:
        print("Main dependency checker (check_dependencies.py) not found")
        print("Running basic checks manually...")
    
    # Additional check for dvdauthor which is critical for DVD ISO creation
    print("\nCHECKING ADDITIONAL DVD-RELATED DEPENDENCIES:")
    print("=" * 50)
    
    # Check for dvdauthor (uses --help instead of --version as it returns exit code 1)
    try:
        result = subprocess.run(['dvdauthor', '--help'], 
                              capture_output=True, text=True, timeout=5)
        if result.returncode in [0, 1]:  # Accept both 0 and 1 as success (dvdauthor --help returns 1)
            # Extract version from stderr (dvdauthor prints version there)
            version_output = result.stderr if result.stderr else result.stdout
            version_line = version_output.split('\n')[0] if version_output else "dvdauthor found"
            print(f"✓ dvdauthor: {version_line}")
        else:
            print(f"✗ dvdauthor: Unexpected exit code {result.returncode}")
    except FileNotFoundError:
        print("✗ dvdauthor: Not found (required for DVD ISO creation)")
        print("  Install with: sudo apt-get install dvdauthor (Ubuntu/Debian)")
        print("  Or: brew install dvdauthor (macOS)")
    except subprocess.TimeoutExpired:
        print("✗ dvdauthor: Version check timed out")
    except Exception as e:
        print(f"✗ dvdauthor: Check failed - {e}")
    
    # Check for other DVD-related tools
    dvd_tools = [
        ('mkisofs', 'Create ISO files'),
        ('genisoimage', 'Alternative ISO creation tool'),
        ('growisofs', 'DVD burning tool')
    ]
    
    for tool, description in dvd_tools:
        try:
            result = subprocess.run([tool, '--version'], 
                                  capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                version_info = result.stdout.split('\n')[0] if result.stdout else "Available"
                print(f"✓ {tool}: {version_info}")
            else:
                print(f"? {tool}: Available but version check failed")
        except FileNotFoundError:
            print(f"✗ {tool}: Not found ({description})")
        except subprocess.TimeoutExpired:
            print(f"? {tool}: Version check timed out")
        except Exception:
            print(f"? {tool}: Check failed")
    
    print("\nNOTE: dvdauthor is essential for DVD ISO creation (Menu 5).")
    print("Other DVD tools are optional but may improve compatibility.")
    
    input("\nPress Enter to return to menu...")

def show_help():
    """Display help and documentation"""
    clear_screen()
    display_header()
    print("\nHELP & DOCUMENTATION")
    print("=" * 30)
    print()
    print("Project Overview:")
    print("   This system creates sync test videos for VHS archival")
    print("   workflows using Domesday Duplicator hardware and audio alignment.")
    print()
    print("Typical Workflow:")
    print("   1. Create sync test videos (1-hour MP4s with test patterns)")
    print("   2. Convert MP4s to DVD ISOs for hardware playback")
    print("   3. Burn DVDs and record to VHS tapes")
    print("   4. Use for calibrating VHS capture timing")
    print()
    print("Hardware Requirements:")
    print("   - Domesday Duplicator RF capture card")
    print("   - Clockgen Lite audio sampling mod")
    print("   - VCR or analog video source")
    print()
    print("File Formats:")
    print("   - MP4: H.264 video with PCM audio for computer playback")
    print("   - ISO: DVD-Video format with MPEG-2/AC-3 for hardware players")
    print()
    print("Documentation:")
    print("   - README.md: Complete setup and usage guide")
    print("   - tools/ directory: Individual tool documentation")
    print("   - GitHub: https://github.com/user/ddd-sync-capture")
    
    input("\nPress Enter to return to menu...")

def create_custom_test_pattern_menu():
    """Menu for creating custom test pattern videos"""
    clear_screen()
    display_header()
    print("\nCREATE CUSTOM TEST PATTERN VIDEOS")
    print("=" * 40)
    print("Create videos using your own custom test pattern image")
    print("Place your test pattern as 'custom_pattern.tif' in media/Test Patterns/")
    print()
    
    # Check if custom pattern exists
    custom_pattern = "media/Test Patterns/custom_pattern.tif"
    
    if not os.path.exists(custom_pattern):
        print("Error: Custom test pattern not found!")
        print(f"   Missing: {custom_pattern}")
        print()
        print("To use custom patterns:")
        print("   1. Place your test pattern image in media/Test Patterns/")
        print("   2. Name it exactly 'custom_pattern.tif'")
        print("   3. Return to this menu")
        print()
        print("Notes:")
        print("   • TIFF format is recommended")
        print("   • 720x576 (PAL) or 720x480 (NTSC) resolution preferred")
        print("   • Will be used for both PAL and NTSC versions")
        input("\nPress Enter to return to menu...")
        return
    
    print(f"Found custom pattern: {custom_pattern}")
    print()
    print("CUSTOM PATTERN OPTIONS")
    print("=" * 30)
    print("1. Create Custom Calibration Videos (1s ON/OFF)")
    print("2. Create Custom PAL Static Chart")
    print("3. Create Custom NTSC Static Chart")
    print("4. Return to Video Menu")
    
    choice = input("\nSelect option (1-4): ").strip()
    
    if choice == '1':
        create_custom_calibration_videos(custom_pattern)
    elif choice == '2':
        create_custom_belle_nuit_chart('PAL', custom_pattern)
    elif choice == '3':
        create_custom_belle_nuit_chart('NTSC', custom_pattern)
    elif choice == '4':
        return
    else:
        print("\nInvalid selection")
        time.sleep(1)
    
    input("\nPress Enter to return to menu...")

def create_custom_calibration_videos(custom_pattern):
    """Create calibration videos using custom pattern"""
    clear_screen()
    display_header()
    print("\nCREATE CUSTOM CALIBRATION VIDEOS")
    print("=" * 40)
    print("Creates 1-hour test videos with 1-second ON/OFF patterns")
    print("using your custom test pattern image.")
    print()
    print("Features:")
    print("   • Video: Custom pattern visible 1s, black 1s (repeating)")
    print("   • Audio: 1kHz tone 1s, silence 1s (repeating)")
    print("   • Duration: 1 hour each (PAL and NTSC)")
    print("   • Purpose: VHS capture timing calibration")
    print()
    
    # Ensure mp4 directory exists
    os.makedirs("media/mp4", exist_ok=True)
    
    # Check if output files already exist
    pal_output = "media/mp4/custom_pal_sync_test_1hour.mp4"
    ntsc_output = "media/mp4/custom_ntsc_sync_test_1hour.mp4"
    
    if os.path.exists(pal_output) or os.path.exists(ntsc_output):
        print("Warning: Output files already exist!")
        if os.path.exists(pal_output):
            print(f"   - {pal_output}")
        if os.path.exists(ntsc_output):
            print(f"   - {ntsc_output}")
        
        choice = input("\nOverwrite existing files? (y/N): ").strip().lower()
        if choice not in ['y', 'yes']:
            print("Operation cancelled.")
            return
    
    print("\nStarting custom video creation...")
    print("This will take several minutes to complete.")
    print("Creating PAL and NTSC versions with your custom pattern...")
    
    try:
        # Import and use the sync test creation functions directly
        sys.path.append('tools')
        from create_sync_test import create_sync_test_video
        
        # Create PAL version
        print("\nCreating PAL version...")
        create_sync_test_video(custom_pattern, pal_output, "PAL", 1)  # 1 hour
        
        # Create NTSC version 
        print("\nCreating NTSC version...")
        create_sync_test_video(custom_pattern, ntsc_output, "NTSC", 1)  # 1 hour
        
        print("\nSUCCESS! Custom sync test videos created.")
        print("Files created:")
        if os.path.exists(pal_output):
            size_mb = os.path.getsize(pal_output) / (1024*1024)
            print(f"   - {pal_output} ({size_mb:.1f} MB)")
        if os.path.exists(ntsc_output):
            size_mb = os.path.getsize(ntsc_output) / (1024*1024)
            print(f"   - {ntsc_output} ({size_mb:.1f} MB)")
            
    except Exception as e:
        print(f"\nError creating custom videos: {e}")

def create_vhs_timecode_pattern():
    """Create VHS Timecode Test Pattern for precision synchronisation"""
    clear_screen()
    display_header()
    print("\nVHS TIMECODE TEST PATTERN")
    print("=" * 35)
    print("Create professional timecode pattern for microsecond-accurate A/V sync")
    print()
    print("Features:")
    print("   • Frame-accurate timecode encoding in video and audio")
    print("   • FSK audio encoding (1000Hz='0', 1200Hz='1')")
    print("   • Visual timecode display (HH:MM:SS:FF)")
    print("   • Binary frame strips and sync markers")
    print("   • Optimised for VHS tape recording quality")
    print("   • Eliminates cycle counting errors")
    print()
    print("This advanced pattern provides broadcast-quality timing precision")
    print("for professional VHS digitisation workflows.")
    print()
    
    # Get format preference
    while True:
        format_choice = input("Select format - P)AL (25fps) or N)TSC (29.97fps) or B)oth [P]: ").strip().upper()
        if not format_choice:
            format_choice = 'P'
        
        if format_choice in ['P', 'PAL']:
            formats = ['PAL']
            break
        elif format_choice in ['N', 'NTSC']:
            formats = ['NTSC']
            break
        elif format_choice in ['B', 'BOTH']:
            formats = ['PAL', 'NTSC']
            break
        else:
            print("Invalid choice. Please enter P, N, or B.")
    
    # Get duration
    while True:
        try:
            duration_input = input("Duration in seconds [120]: ").strip()
            if not duration_input:
                duration = 120  # Default 2 minutes
            else:
                duration = int(duration_input)
            
            if duration < 10:
                print("Duration must be at least 10 seconds")
                continue
            elif duration > 3600:
                print("Duration should be less than 1 hour for practical use")
                confirm = input("Continue anyway? (y/N): ").strip().lower()
                if confirm not in ['y', 'yes']:
                    continue
            
            break
            
        except ValueError:
            print("Please enter a valid number")
    
    # Ensure mp4 directory exists
    os.makedirs("media/mp4", exist_ok=True)
    
    # Check for existing files
    output_files = []
    for fmt in formats:
        output_file = f"media/mp4/vhs_timecode_{fmt.lower()}_{duration}s.mp4"
        output_files.append((fmt, output_file))
        
        if os.path.exists(output_file):
            size_mb = os.path.getsize(output_file) / (1024*1024)
            print(f"\nWarning: {fmt} output file already exists!")
            print(f"   {output_file} ({size_mb:.1f} MB)")
    
    if any(os.path.exists(output_file) for _, output_file in output_files):
        overwrite = input("\nOverwrite existing files? (y/N): ").strip().lower()
        if overwrite not in ['y', 'yes']:
            print("Operation cancelled.")
            input("\nPress Enter to return to menu...")
            return
    
    print(f"\nCreating timecode test pattern(s) for {', '.join(formats)}...")
    print(f"Duration: {duration} seconds")
    print("This will take a few minutes to complete.")
    print()
    
    try:
        # Check if timecode generator exists - use efficient version for long durations
        if duration > 600:  # Use efficient version for durations > 10 minutes
            generator_script = "tools/timecode-generator/vhs_timecode_generator_efficient.py"
            print(f"Using memory-efficient generator for long duration ({duration} seconds)")
        else:
            generator_script = "tools/timecode-generator/vhs_timecode_generator.py"
        
        if not os.path.exists(generator_script):
            print(f"ERROR: Timecode generator not found at {generator_script}")
            print("Please ensure the VHS timecode generator is available.")
            input("\nPress Enter to return to menu...")
            return
        
        # Create each format
        success_count = 0
        for fmt, output_file in output_files:
            print(f"\nGenerating {fmt} timecode pattern...")
            
            try:
                # Run the timecode generator
                result = subprocess.run([
                    sys.executable, generator_script,
                    '--duration', str(duration),
                    '--format', fmt,
                    '--output', output_file
                ], capture_output=True, text=True, timeout=10800)  # 3 hour timeout
                
                if result.returncode == 0:
                    if os.path.exists(output_file):
                        size_mb = os.path.getsize(output_file) / (1024*1024)
                        print(f"SUCCESS: {fmt} timecode pattern created ({size_mb:.1f} MB)")
                        
                        # Check for metadata file
                        metadata_file = output_file.replace('.mp4', '_metadata.json')
                        if os.path.exists(metadata_file):
                            print(f"         Metadata: {os.path.basename(metadata_file)}")
                        
                        success_count += 1
                    else:
                        print(f"ERROR: {fmt} output file was not created")
                else:
                    print(f"ERROR creating {fmt} pattern:")
                    if result.stderr:
                        print(f"  {result.stderr.strip()}")
                    if result.stdout:
                        print(f"  {result.stdout.strip()}")
                        
            except subprocess.TimeoutExpired:
                print(f"ERROR: {fmt} generation timed out (>3 hours)")
            except Exception as e:
                print(f"ERROR generating {fmt} pattern: {e}")
        
        if success_count > 0:
            print(f"\nTimecode pattern creation completed!")
            print(f"Successfully created {success_count}/{len(formats)} pattern(s)")
            print()
            print("USAGE INSTRUCTIONS:")
            print("1. Record these MP4 files to VHS tape")
            print("2. Capture back with Domesday Duplicator + audio interface")
            print("3. Use 'A/V Calibration → Precision Timecode Analysis' to analyse")
            print("4. Get microsecond-accurate timing measurements")
        else:
            print(f"\nFailed to create timecode patterns.")
            print("Please check dependencies and try again.")
            
    except KeyboardInterrupt:
        print("\nOperation cancelled by user.")
    except Exception as e:
        print(f"\nUnexpected error: {e}")
    
    input("\nPress Enter to return to menu...")

def create_custom_belle_nuit_chart(format_type, custom_pattern):
    """Create static test chart using custom pattern"""
    clear_screen()
    display_header()
    print(f"\nCREATE CUSTOM {format_type} STATIC CHART")
    print("=" * 40)
    print("Creates static test chart video using your custom pattern")
    print("for hardware testing - no flashing patterns.")
    print()
    print("Features:")
    print("   • Video: Constant custom pattern display (no ON/OFF)")
    print("   • Audio: Continuous 1kHz tone (for audio testing)")
    print("   • Duration: 200 minutes (perfect for E-180 tapes)")
    print("   • Purpose: Hardware testing, tape creation, equipment setup")
    print()
    
    # Ensure mp4 directory exists
    os.makedirs("media/mp4", exist_ok=True)
    
    output_file = f"media/mp4/custom_{format_type.lower()}_belle_nuit.mp4"
    
    # Check if output file already exists
    if os.path.exists(output_file):
        print("Warning: Output file already exists!")
        print(f"   - {output_file}")
        
        choice = input("\nOverwrite existing file? (y/N): ").strip().lower()
        if choice not in ['y', 'yes']:
            print("Operation cancelled.")
            return
    
    print("\nStarting custom static chart creation...")
    print("This will take a few minutes to complete.")
    print(f"Creating {format_type} version with your custom pattern...")
    
    try:
        # Import and use the create_static_chart function
        sys.path.append('tools')
        from create_belle_nuit_charts import create_static_chart
        create_static_chart(output_file, custom_pattern, format_type)
        print("\nSUCCESS! Custom Belle Nuit static chart created.")
        size_mb = os.path.getsize(output_file) / (1024*1024)
        print(f"   - {output_file} ({size_mb:.1f} MB)")
    except Exception as e:
        print(f"\nError creating custom static chart: {e}")

def display_settings_menu():
    """Display the Settings & Configuration submenu"""
    while True:
        clear_screen()
        display_header()
        
        # Import config functions
        sys.path.append('.')
        from config import get_config_summary, get_capture_directory, set_capture_directory
        
        print("\nSETTINGS & CONFIGURATION")
        print("=" * 35)
        print()
        print(get_config_summary())
        print()
        print("CONFIGURATION OPTIONS")
        print("=" * 30)
        print("1. Change Capture Directory")
        print("2. Manage Processing Locations")
        print("3. Performance Settings")
        print("4. View Current Settings")
        print("5. Reset to Defaults")
        print("6. Return to Main Menu")
        
        selection = input("\nSelect option (1-6): ").strip()
        
        if selection == '1':
            change_capture_directory()
        elif selection == '2':
            manage_processing_locations()
        elif selection == '3':
            display_performance_settings_menu()
        elif selection == '4':
            view_detailed_settings()
        elif selection == '5':
            reset_to_defaults()
        elif selection == '6':
            break  # Return to main menu
        else:
            print("Invalid selection. Please enter 1, 2, 3, 4, 5, or 6.")
            time.sleep(1)

def manage_processing_locations():
    """Manage multiple scanning/processing directories"""
    clear_screen()
    display_header()
    print("\nMANAGE PROCESSING LOCATIONS")
    print("=" * 35)
    print("Add and manage multiple directories for scanning RF files and processing.")
    print("This allows you to organize captures across different storage locations.")
    print()
    
    # Load current processing locations from config
    sys.path.append('.')
    from config import load_config, save_config
    
    config = load_config()
    processing_locations = config.get('processing_locations', [])
    
    # Show current locations
    print("CURRENT PROCESSING LOCATIONS:")
    print("=" * 40)
    if processing_locations:
        for i, location in enumerate(processing_locations, 1):
            # Check if directory exists and get space info
            if os.path.exists(location):
                try:
                    if sys.platform == 'win32':
                        import shutil
                        total, used, free = shutil.disk_usage(location)
                        free_gb = free / (1024**3)
                    else:
                        statvfs = os.statvfs(location)
                        free_gb = (statvfs.f_frsize * statvfs.f_bavail) / (1024**3)
                    
                    # Count RF files
                    rf_files = len([f for f in os.listdir(location) if f.lower().endswith(('.lds', '.ldf', '.tbc'))])
                    print(f"   {i}. {location} ({free_gb:.1f} GB free, {rf_files} RF files)")
                except Exception as e:
                    print(f"   {i}. {location} (error: {e})")
            else:
                print(f"   {i}. {location} (not found)")
    else:
        print("   No processing locations configured.")
        print("   Add some directories to scan for RF files and processing.")
    
    print()
    print("LOCATION MANAGEMENT OPTIONS:")
    print("=" * 35)
    print("1. Add New Processing Location")
    print("2. Remove Processing Location")
    print("3. View Location Details")
    print("4. Clear All Locations")
    print("5. Return to Settings Menu")
    
    choice = input("\nSelect option (1-5): ").strip()
    
    if choice == '1':
        add_processing_location()
    elif choice == '2':
        remove_processing_location()
    elif choice == '3':
        view_location_details()
    elif choice == '4':
        clear_all_locations()
    elif choice == '5':
        return
    else:
        print("Invalid selection. Please enter 1-5.")
        time.sleep(1)
        manage_processing_locations()  # Return to this menu

def set_decode_processing_location():
    """Set dedicated location for decode processing (TBC files, etc.)"""
    clear_screen()
    display_header()
    print("\nSET DECODE PROCESSING LOCATION")
    print("=" * 40)
    print("Configure where TBC files and decode processing occurs.")
    print()
    print("Recommendations:")
    print("• Use fast storage (SSD) for decode processing")
    print("• Ensure adequate free space (20+ GB recommended)")
    print("• Can be different from capture location for optimization")
    print()
    
    print("This feature will be available in a future update.")
    print("Currently, decode processing uses the main capture directory.")
    
    input("\nPress Enter to continue...")

def configure_temp_processing_directory():
    """Configure temporary processing directory"""
    clear_screen()
    display_header()
    print("\nCONFIGURE TEMPORARY PROCESSING DIRECTORY")
    print("=" * 50)
    print("Set location for temporary files during processing.")
    print()
    print("Current temporary directory: temp/")
    print()
    print("Recommendations:")
    print("• Use fast storage for temporary files")
    print("• Ensure automatic cleanup of old temp files")
    print("• Consider RAM disk for very fast processing")
    print()
    
    print("This feature will be available in a future update.")
    print("Currently, temporary files use the 'temp/' directory.")
    
    input("\nPress Enter to continue...")

def set_output_video_location():
    """Set location for output video files"""
    clear_screen()
    display_header()
    print("\nSET OUTPUT VIDEO STORAGE LOCATION")
    print("=" * 45)
    print("Configure where final processed video files are stored.")
    print()
    print("Current output directory: media/mp4/")
    print()
    print("Recommendations:")
    print("• Use high-capacity storage for video archives")
    print("• Consider network storage for shared access")
    print("• Ensure adequate space for multiple large files")
    print()
    
    print("This feature will be available in a future update.")
    print("Currently, output videos use the 'media/mp4/' directory.")
    
    input("\nPress Enter to continue...")

def configure_iso_output_directory():
    """Configure ISO output directory"""
    clear_screen()
    display_header()
    print("\nCONFIGURE ISO OUTPUT DIRECTORY")
    print("=" * 40)
    print("Set location for DVD ISO file creation.")
    print()
    print("Current ISO directory: media/iso/")
    print()
    print("Recommendations:")
    print("• Use storage with good write performance")
    print("• Ensure adequate space for multiple ISOs")
    print("• Consider proximity to DVD burning hardware")
    print()
    
    print("This feature will be available in a future update.")
    print("Currently, ISO files use the 'media/iso/' directory.")
    
    input("\nPress Enter to continue...")

def view_all_processing_locations():
    """View all processing locations with details"""
    clear_screen()
    display_header()
    print("\nALL PROCESSING LOCATIONS")
    print("=" * 35)
    
    # Import config functions
    sys.path.append('.')
    from config import get_capture_directory, check_disk_space
    
    locations = [
        ("Primary Capture", get_capture_directory(), "RF files, audio captures"),
        ("Temporary Processing", "temp/", "Temporary files, processing cache"),
        ("Output Videos", "media/mp4/", "Final processed MP4 files"),
        ("DVD ISOs", "media/iso/", "DVD image files"),
        ("Test Patterns", "media/Test Patterns/", "Test pattern images"),
    ]
    
    print("LOCATION DETAILS:")
    print("=" * 25)
    
    for name, path, description in locations:
        print(f"\n{name}:")
        print(f"   Path: {path}")
        print(f"   Purpose: {description}")
        
        # Check if location exists and get space info
        if os.path.exists(path):
            try:
                free_gb, has_space = check_disk_space(path)
                status = "OK" if has_space else "Low space"
                print(f"   Status: Exists ({free_gb:.1f} GB free, {status})")
                
                # Count relevant files
                if name == "Primary Capture":
                    rf_files = len([f for f in os.listdir(path) if f.endswith(('.lds', '.tbc'))])
                    audio_files = len([f for f in os.listdir(path) if f.endswith(('.wav', '.flac'))])
                    print(f"   Contents: {rf_files} RF/TBC files, {audio_files} audio files")
                elif name == "Output Videos":
                    mp4_files = len([f for f in os.listdir(path) if f.endswith('.mp4')])
                    print(f"   Contents: {mp4_files} MP4 files")
                elif name == "DVD ISOs":
                    iso_files = len([f for f in os.listdir(path) if f.endswith('.iso')])
                    print(f"   Contents: {iso_files} ISO files")
                elif name == "Test Patterns":
                    pattern_files = len([f for f in os.listdir(path) if f.endswith(('.tif', '.png', '.jpg'))])
                    print(f"   Contents: {pattern_files} pattern files")
                elif name == "Temporary Processing":
                    temp_files = len([f for f in os.listdir(path) if not f.startswith('.')])
                    print(f"   Contents: {temp_files} temporary files")
                    
            except Exception as e:
                print(f"   Status: Error checking location - {e}")
        else:
            print(f"   Status: Does not exist")
    
    print("\n" + "=" * 60)
    print("PROCESSING LOCATION GUIDELINES:")
    print("=" * 60)
    print("• Capture Location: Should be fast storage with plenty of space")
    print("• Temp Processing: Benefits from SSD or fast storage")
    print("• Output Videos: Can use slower but high-capacity storage")
    print("• DVD ISOs: Moderate speed requirements, consider burning location")
    print("• Test Patterns: Small files, any storage is fine")
    
    input("\nPress Enter to continue...")

def reset_all_locations_to_defaults():
    """Reset all processing locations to defaults"""
    clear_screen()
    display_header()
    print("\nRESET ALL PROCESSING LOCATIONS TO DEFAULTS")
    print("=" * 55)
    print("This will reset all processing locations to their default values:")
    print()
    print("Default locations:")
    print("• Primary Capture: temp/")
    print("• Temporary Processing: temp/")
    print("• Output Videos: media/mp4/")
    print("• DVD ISOs: media/iso/")
    print("• Test Patterns: media/Test Patterns/")
    print()
    print("WARNING: This will not move existing files, only change where")
    print("new files will be created.")
    print()
    
    confirm = input("Reset all processing locations to defaults? (y/N): ").strip().lower()
    
    if confirm in ['y', 'yes']:
        try:
            # Import config functions
            sys.path.append('.')
            from config import set_capture_directory
            
            # Reset capture directory to default
            if set_capture_directory('temp'):
                print("\nProcessing locations reset to defaults successfully!")
                print("\nNote: Existing files remain in their current locations.")
                print("Only new operations will use the default locations.")
            else:
                print("\nFailed to reset processing locations.")
                
        except Exception as e:
            print(f"\nError resetting locations: {e}")
    else:
        print("\nReset cancelled. No changes made.")
    
    input("\nPress Enter to continue...")

def change_capture_directory():
    """Allow user to change the capture directory with interactive browsing"""
    clear_screen()
    display_header()
    print("\nCHANGE CAPTURE DIRECTORY")
    print("=" * 35)
    
    # Import config functions
    sys.path.append('.')
    from config import get_capture_directory, set_capture_directory, check_disk_space
    
    current_dir = get_capture_directory()
    free_gb, has_space = check_disk_space(current_dir)
    
    print(f"Current directory: {current_dir}")
    print(f"Available space: {free_gb:.1f} GB")
    print()
    
    print("DIRECTORY SELECTION OPTIONS")
    print("=" * 35)
    print("1. Interactive Directory Browser (recommended)")
    print("2. Quick Select from Common Locations")
    print("3. Enter Path Manually")
    print("4. Cancel")
    
    choice = input("\nSelect option (1-4): ").strip()
    
    if choice == '1':
        new_path = interactive_directory_browser()
    elif choice == '2':
        new_path = quick_location_selector()
    elif choice == '3':
        new_path = get_manual_path_input()
    elif choice == '4':
        print("\nNo changes made.")
        input("Press Enter to continue...")
        return
    else:
        print("Invalid selection.")
        input("Press Enter to continue...")
        return
    
    if not new_path:
        return
    
    # Expand user home directory if needed
    if new_path.startswith('~'):
        new_path = os.path.expanduser(new_path)
    
    print(f"\nValidating directory: {new_path}")
    
    # Try to set the new directory
    try:
        if set_capture_directory(new_path):
            # Check space on new directory
            new_free_gb, new_has_space = check_disk_space(new_path)
            print(f"\nSUCCESS! Capture directory updated.")
            print(f"New directory: {new_path}")
            print(f"Available space: {new_free_gb:.1f} GB")
            
            if not new_has_space:
                print("\nWARNING: Low disk space (<10 GB available)")
                print("Consider choosing a location with more free space.")
        else:
            print("\nFailed to set capture directory.")
            print("Please check the path and permissions.")
            
    except KeyboardInterrupt:
        print("\nOperation cancelled.")
    except Exception as e:
        print(f"\nError: {e}")
    
    input("\nPress Enter to continue...")

def interactive_directory_browser(start_path=None):
    """Interactive directory browser with navigation"""
    if start_path is None:
        start_path = os.path.expanduser('~')  # Start from home directory
    
    current_path = os.path.abspath(start_path)
    page = 0  # Initialize page number for pagination
    while True:
        try:
            clear_screen()
            display_header()
            print("\nINTERACTIVE DIRECTORY BROWSER")
            print("=" * 40)
            
            # Show current location and available space
            try:
                if sys.platform == 'win32':
                    import shutil
                    total, used, free = shutil.disk_usage(current_path)
                    free_gb = free / (1024**3)
                else:
                    statvfs = os.statvfs(current_path)
                    free_gb = (statvfs.f_frsize * statvfs.f_bavail) / (1024**3)
                space_info = f" ({free_gb:.1f} GB free)"
            except:
                space_info = ""
            
            print(f"Current location: {current_path}{space_info}")
            print()
            
            # List directory contents
            try:
                items = os.listdir(current_path)
                directories = []
                files = []
                
                for item in items:
                    item_path = os.path.join(current_path, item)
                    if os.path.isdir(item_path):
                        # Skip hidden directories starting with . unless it's current user's hidden folders
                        if not item.startswith('.') or item in ['.config', '.local', '.cache']:
                            directories.append(item)
                    else:
                        files.append(item)
                        
                directories.sort()
                files.sort()
                
                # Paginate directories
                num_per_page = 15
                start_idx = page * num_per_page
                end_idx = start_idx + num_per_page
                total_pages = (len(directories) // num_per_page) + (1 if len(directories) % num_per_page != 0 else 0)
                current_page_dirs = directories[start_idx:end_idx]
                
                print("DIRECTORIES:")
                print("-" * 20)
                
                # Show parent directory option (unless at root)
                parent_option = 1
                if current_path != os.path.dirname(current_path):  # Not at root
                    print(f"   {parent_option}. .. (parent directory)")
                    parent_option += 1
                
                # Show directories for current page
                dir_start = parent_option
                for i, directory in enumerate(current_page_dirs, dir_start):
                    print(f"   {i}. {directory}/")
                
                # Show pagination info and controls
                if len(directories) > num_per_page:
                    print(f"\n   ... showing {start_idx + 1}-{min(end_idx, len(directories))} of {len(directories)} directories")
                    if end_idx < len(directories):
                        print("   n. Next page")
                    if page > 0:
                        print("   p. Previous page")
                
                next_option = dir_start + len(current_page_dirs)
                    
                # Show some files for context (but can't select them)
                if files:
                    print(f"\nFILES (for reference):")
                    print("-" * 25)
                    for f in files[:5]:  # Show first 5 files
                        print(f"     {f}")
                    if len(files) > 5:
                        print(f"     ... and {len(files) - 5} more files")
                    
                print(f"\nNAVIGATION OPTIONS:")
                print("-" * 25)
                print(f"   {next_option}. USE THIS DIRECTORY as capture location")
                print(f"   {next_option + 1}. CREATE NEW FOLDER here")
                print(f"   {next_option + 2}. Go to Home Directory")
                print(f"   {next_option + 3}. Show Drive/Mount Points")
                print(f"   {next_option + 4}. Cancel")
                    
                print()
                selection = input(f"Select option (1-{next_option + 4}): ").strip()
                
                if not selection:
                    continue
                
                # Handle pagination commands
                if selection.lower() == 'n' and end_idx < len(directories):
                    page += 1
                    continue
                elif selection.lower() == 'p' and page > 0:
                    page -= 1
                    continue
                
                try:
                    selection_num = int(selection)
                    
                    # Handle parent directory navigation
                    if current_path != os.path.dirname(current_path) and selection_num == 1:
                        current_path = os.path.dirname(current_path)
                        page = 0  # Reset pagination when changing directories
                        continue
                    
                    # Handle directory selection
                    if current_path != os.path.dirname(current_path):  # Not at root
                        dir_selection_start = 2
                    else:
                        dir_selection_start = 1
                    
                    if dir_selection_start <= selection_num < dir_selection_start + len(current_page_dirs):
                        selected_dir = current_page_dirs[selection_num - dir_selection_start]
                        new_path = os.path.join(current_path, selected_dir)
                        if os.path.exists(new_path) and os.access(new_path, os.R_OK):
                            current_path = new_path
                            page = 0  # Reset pagination when changing directories
                        else:
                            print(f"\nCannot access directory: {selected_dir}")
                            input("Press Enter to continue...")
                        continue
                    
                    # Handle special options
                    elif selection_num == next_option:
                        # Use this directory
                        return current_path
                    
                    elif selection_num == next_option + 1:
                        # Create new folder
                        folder_name = input("\nEnter new folder name: ").strip()
                        if folder_name:
                            if not any(char in folder_name for char in ['/', '\\', ':', '*', '?', '"', '<', '>', '|']):
                                new_folder_path = os.path.join(current_path, folder_name)
                                try:
                                    os.makedirs(new_folder_path, exist_ok=True)
                                    print(f"\nCreated folder: {folder_name}")
                                    use_new = input("Use this new folder as capture directory? (Y/n): ").strip().lower()
                                    if use_new not in ['n', 'no']:
                                        return new_folder_path
                                except Exception as e:
                                    print(f"\nError creating folder: {e}")
                                    input("Press Enter to continue...")
                            else:
                                print("\nInvalid folder name. Avoid special characters.")
                                input("Press Enter to continue...")
                    
                    elif selection_num == next_option + 2:
                        # Go to home directory
                        current_path = os.path.expanduser('~')
                        page = 0  # Reset pagination when changing directories
                    
                    elif selection_num == next_option + 3:
                        # Show drive/mount points
                        drive_path = show_drive_selector()
                        if drive_path:
                            current_path = drive_path
                            page = 0  # Reset pagination when changing directories
                    
                    elif selection_num == next_option + 4:
                        # Cancel
                        return None
                    
                    else:
                        print("\nInvalid selection.")
                        input("Press Enter to continue...")
                        
                except ValueError:
                    print("\nInvalid input. Please enter a number or 'n'/'p' for pagination.")
                    input("Press Enter to continue...")
                    
            except PermissionError:
                print(f"\nPermission denied accessing: {current_path}")
                print("Returning to parent directory...")
                current_path = os.path.dirname(current_path)
                input("Press Enter to continue...")
            except Exception as e:
                print(f"\nError reading directory: {e}")
                input("Press Enter to continue...")
                
        except KeyboardInterrupt:
            return None
        except ValueError:
            print("\nInvalid input. Please enter a number.")
            input("Press Enter to continue...")
        except Exception as e:
            print(f"\nUnexpected error: {e}")
            input("Press Enter to continue...")

def show_drive_selector():
    """Show available drives/mount points for selection"""
    clear_screen()
    display_header()
    print("\nSELECT DRIVE/MOUNT POINT")
    print("=" * 35)
    
    available_locations = []
    
    try:
        if sys.platform == 'win32':
            # Show Windows drive letters
            import string
            for letter in string.ascii_uppercase:
                if os.path.exists(f'{letter}:\\'):
                    try:
                        total, used, free = shutil.disk_usage(f'{letter}:\\')
                        free_gb = free / (1024**3)
                        available_locations.append((f'{letter}:\\', f'{letter}:\\ ({free_gb:.1f} GB free)'))
                    except:
                        available_locations.append((f'{letter}:\\', f'{letter}:\\ (unknown space)'))
        else:
            # Show useful mount points on Unix/Linux/Mac
            common_mounts = ['/', '/home', '/mnt', '/media', '/Volumes']
            
            # Add root filesystem
            if os.path.exists('/'):
                try:
                    statvfs = os.statvfs('/')
                    free_gb = (statvfs.f_frsize * statvfs.f_bavail) / (1024**3)
                    available_locations.append(('/', f'Root filesystem (/) - {free_gb:.1f} GB free'))
                except:
                    available_locations.append(('/', 'Root filesystem (/) - unknown space'))
            
            # Add home directory
            home_dir = os.path.expanduser('~')
            if os.path.exists(home_dir):
                available_locations.append((home_dir, f'Home directory (~)'))
            
            # Look for external mounts
            for mount_base in ['/mnt', '/media', '/Volumes']:
                if os.path.exists(mount_base):
                    try:
                        for item in os.listdir(mount_base):
                            mount_path = os.path.join(mount_base, item)
                            if os.path.isdir(mount_path) and os.access(mount_path, os.R_OK):
                                try:
                                    statvfs = os.statvfs(mount_path)
                                    free_gb = (statvfs.f_frsize * statvfs.f_bavail) / (1024**3)
                                    available_locations.append((mount_path, f'{mount_path} ({free_gb:.1f} GB free)'))
                                except:
                                    available_locations.append((mount_path, f'{mount_path} (external)'))
                    except:
                        pass
                        
    except Exception as e:
        print(f"Error detecting drives: {e}")
    
    if not available_locations:
        print("No drives/mount points detected.")
        input("Press Enter to continue...")
        return None
    
    print("Available locations:")
    for i, (path, description) in enumerate(available_locations, 1):
        print(f"   {i}. {description}")
    
    print(f"   {len(available_locations) + 1}. Cancel")
    
    try:
        selection = input(f"\nSelect location (1-{len(available_locations) + 1}): ").strip()
        selection_num = int(selection)
        
        if 1 <= selection_num <= len(available_locations):
            return available_locations[selection_num - 1][0]
        elif selection_num == len(available_locations) + 1:
            return None
        else:
            print("Invalid selection.")
            input("Press Enter to continue...")
            return None
            
    except (ValueError, IndexError):
        print("Invalid selection.")
        input("Press Enter to continue...")
        return None

def quick_location_selector():
    """Quick selection from common locations (original simplified method)"""
    available_locations = []
    
    try:
        if sys.platform == 'win32':
            # Show Windows drive letters
            import string
            for letter in string.ascii_uppercase:
                if os.path.exists(f'{letter}:\\'):
                    try:
                        total, used, free = shutil.disk_usage(f'{letter}:\\')
                        free_gb_drive = free / (1024**3)
                        available_locations.append((f'{letter}:\\', f'{letter}:\\ ({free_gb_drive:.1f} GB free)'))
                    except:
                        available_locations.append((f'{letter}:\\', f'{letter}:\\ (unknown space)'))
        else:
            # Add common user directories
            home_dir = os.path.expanduser('~')
            if os.path.exists(home_dir):
                available_locations.append((home_dir, f'Home directory (~)'))
            
            desktop_dir = os.path.join(home_dir, 'Desktop')
            if os.path.exists(desktop_dir):
                available_locations.append((desktop_dir, f'Desktop'))
            
            videos_dir = os.path.join(home_dir, 'Videos')
            if os.path.exists(videos_dir):
                available_locations.append((videos_dir, f'Videos folder'))
            
            documents_dir = os.path.join(home_dir, 'Documents')
            if os.path.exists(documents_dir):
                available_locations.append((documents_dir, f'Documents folder'))
                
    except Exception as e:
        print(f"Could not detect storage locations: {e}")
    
    if not available_locations:
        print("No common locations detected.")
        return get_manual_path_input()
    
    clear_screen()
    display_header()
    print("\nQUICK LOCATION SELECTOR")
    print("=" * 30)
    print("Select a common location and specify subdirectory:")
    print()
    
    for i, (path, description) in enumerate(available_locations, 1):
        print(f"   {i}. {description}")
    print(f"   {len(available_locations) + 1}. Enter custom path manually")
    print()
    
    try:
        selection = input(f"Select option (1-{len(available_locations) + 1}) or 'q' to cancel: ").strip().lower()
        
        if selection == 'q':
            return None
        
        selection_num = int(selection)
        
        if 1 <= selection_num <= len(available_locations):
            # User selected a detected location
            base_path = available_locations[selection_num - 1][0]
            
            # Suggest a VHS capture subdirectory
            suggested_path = os.path.join(base_path, 'VHS_Captures')
            
            print(f"\nSelected: {base_path}")
            print(f"Suggested capture directory: {suggested_path}")
            
            custom_name = input(f"\nUse suggested path? (Y/n) or enter custom subdirectory name: ").strip()
            
            if custom_name.lower() in ['n', 'no']:
                # User wants to specify custom subdirectory
                subdir = input("Enter subdirectory name (e.g., 'My_VHS_Archive'): ").strip()
                if subdir:
                    new_path = os.path.join(base_path, subdir)
                else:
                    new_path = base_path
            elif custom_name and custom_name.lower() not in ['y', 'yes', '']:
                # User entered a custom subdirectory name
                new_path = os.path.join(base_path, custom_name)
            else:
                # Use suggested path
                new_path = suggested_path
            
            return new_path
                
        elif selection_num == len(available_locations) + 1:
            # User wants to enter custom path
            return get_manual_path_input()
        else:
            print("Invalid selection.")
            return None
            
    except (ValueError, IndexError):
        print("Invalid selection.")
        return None

def get_manual_path_input():
    """Get manual path input from user with examples"""
    print("Enter new capture directory path:")
    print("Examples:")
    if sys.platform == 'win32':
        print("   D:\\VHS_Captures")
        print("   C:\\Users\\username\\Videos\\VHS")
        print("   E:\\External_Drive\\Captures")
        print("   %USERPROFILE%\\Desktop\\VHS_Archive")
    elif sys.platform == 'darwin':
        print("   /Volumes/External/VHS_Captures")
        print("   ~/Desktop/VHS_Archive")
        print("   ~/Movies/VHS_Digitization")
    else:
        print("   /mnt/external/VHS_Captures")
        print("   /media/USB_Drive/VHS")
        print("   ~/Videos/VHS")
        print("   ~/Desktop/Captures")
    print()
    
    print("Tips:")
    print("   • Use full paths for external drives")
    print("   • Ensure the drive has plenty of space (10+ GB recommended)")
    print("   • Directory will be created if it doesn't exist")
    if sys.platform == 'win32':
        print("   • Use backslashes (\\) or forward slashes (/) in Windows paths")
        print("   • %USERPROFILE% expands to your user folder")
    else:
        print("   • Use ~ for your home directory")
        print("   • Tab completion works in most terminals")
    print()
    
    try:
        new_path = input("New capture directory (or press Enter to cancel): ").strip()
        
        if not new_path:
            print("\nNo changes made.")
            input("Press Enter to continue...")
            return None
            
        return new_path
        
    except KeyboardInterrupt:
        print("\nOperation cancelled.")
        return None

def view_detailed_settings():
    """Show detailed configuration information"""
    clear_screen()
    display_header()
    print("\nDETAILED SETTINGS")
    print("=" * 25)
    
    # Import config functions
    sys.path.append('.')
    from config import load_config, get_capture_directory, check_disk_space
    
    config = load_config()
    capture_dir = get_capture_directory()
    free_gb, has_space = check_disk_space(capture_dir)
    
    print(f"Configuration File: config.json")
    print(f"Project Root: {os.path.dirname(os.path.abspath(__file__))}")
    print()
    print("CAPTURE SETTINGS:")
    print(f"   Directory: {capture_dir}")
    print(f"   Disk Space: {free_gb:.1f} GB available")
    print(f"   Space Status: {'OK' if has_space else 'Low space'}")
    print(f"   Default Name: {config.get('default_capture_name', 'N/A')}")
    print()
    print("SYNC SETTINGS:")
    print(f"   Audio Delay: {config.get('audio_delay', 0.000):.3f}s")
    print(f"   Video Format: {config.get('preferred_video_format', 'PAL')}")
    print()
    print("OTHER SETTINGS:")
    print(f"   Last Test Pattern: {config.get('last_used_test_pattern', 'default')}")
    
    # Show directory contents if it exists
    if os.path.exists(capture_dir):
        try:
            files = os.listdir(capture_dir)
            capture_files = [f for f in files if f.endswith(('.lds', '.flac', '.wav', '.tbc', '.json'))]
            
            print(f"\nCAPTURE DIRECTORY CONTENTS:")
            if capture_files:
                print(f"   Found {len(capture_files)} capture-related files")
                # Show most recent files
                recent_files = sorted(capture_files, key=lambda x: os.path.getmtime(os.path.join(capture_dir, x)), reverse=True)[:5]
                for f in recent_files:
                    file_path = os.path.join(capture_dir, f)
                    size_mb = os.path.getsize(file_path) / (1024**2)
                    print(f"     - {f} ({size_mb:.1f} MB)")
                if len(capture_files) > 5:
                    print(f"     ... and {len(capture_files) - 5} more files")
            else:
                print("   No capture files found")
        except Exception as e:
            print(f"   Could not read directory: {e}")
    
    input("\nPress Enter to continue...")

def reset_to_defaults():
    """Reset configuration to default values"""
    clear_screen()
    display_header()
    print("\nRESET TO DEFAULTS")
    print("=" * 25)
    print("This will reset all configuration settings to their default values.")
    print()
    print("Current settings will be lost:")
    print("   • Capture directory will reset to 'temp'")
    print("   • Audio delay will reset to 0.000s")
    print("   • Other preferences will be reset")
    print()
    
    confirm = input("Are you sure you want to reset all settings? (y/N): ").strip().lower()
    
    if confirm in ['y', 'yes']:
        try:
            # Import config functions
            sys.path.append('.')
            from config import DEFAULT_CONFIG, save_config
            
            # Save default configuration
            if save_config(DEFAULT_CONFIG.copy()):
                print("\nConfiguration reset to defaults successfully!")
                print("\nDefault settings:")
                print(f"   Capture Directory: temp")
                print(f"   Audio Delay: 0.000s")
                print(f"   Video Format: PAL")
                print(f"   Default Capture Name: my_vhs_capture")
            else:
                print("\nFailed to reset configuration.")
                print("You may need to manually delete config.json and restart.")
                
        except Exception as e:
            print(f"\nError resetting configuration: {e}")
    else:
        print("\nReset cancelled. No changes made.")
    
    input("\nPress Enter to continue...")

def stop_current_capture():
    """Stop ongoing Domesday Duplicator capture using command line"""
    clear_screen()
    display_header()
    print("\nSTOP CURRENT CAPTURE")
    print("=" * 30)
    print("This will stop any ongoing Domesday Duplicator capture")
    print("and terminate SOX audio recording processes.")
    print()
    
    try:
        # First, try to stop SOX processes
        print("Stopping SOX audio recording...")
        try:
            result = subprocess.run(['pkill', '-f', 'sox'], capture_output=True, text=True)
            if result.returncode == 0:
                print("SOX audio recording stopped successfully")
            else:
                print("No SOX processes found running")
        except Exception as e:
            print(f"Could not stop SOX: {e}")
        
        # Now try to stop Domesday Duplicator using command line
        print("\nStopping Domesday Duplicator capture...")
        
        try:
            stop_result = subprocess.run(['DomesdayDuplicator', '--stop-capture'], 
                                       capture_output=True, text=True, timeout=10)
            
            if stop_result.returncode == 0:
                print("DomesdayDuplicator capture stopped successfully via command line")
                print("\nCapture stopped successfully!")
            else:
                print(f"DomesdayDuplicator stop returned code {stop_result.returncode}")
                print("Falling back to process termination...")
                # Fallback to process kill
                try:
                    subprocess.run(['pkill', '-f', 'DomesdayDuplicator'], check=True)
                    print("DomesdayDuplicator processes terminated")
                    print("\nCapture stopped!")
                except subprocess.CalledProcessError:
                    print("No DomesdayDuplicator processes found to stop")
                    print("\nNo active captures detected")
                    
        except subprocess.TimeoutExpired:
            print("DomesdayDuplicator stop command timed out")
            print("Attempting to terminate processes...")
            try:
                subprocess.run(['pkill', '-f', 'DomesdayDuplicator'], check=True)
                print("DomesdayDuplicator processes terminated")
            except subprocess.CalledProcessError:
                print("No DomesdayDuplicator processes found")
                
        except FileNotFoundError:
            print("DomesdayDuplicator command not found")
            print("Attempting to terminate any running processes...")
            try:
                subprocess.run(['pkill', '-f', 'DomesdayDuplicator'], check=True)
                print("DomesdayDuplicator processes terminated")
            except subprocess.CalledProcessError:
                print("No DomesdayDuplicator processes found")
    
    except Exception as e:
        print(f"Error during stop operation: {e}")
    
    input("\nPress Enter to return to menu...")

def main():
    """Main menu loop"""
    while True:
        try:
            clear_screen()
            display_header()
            display_main_menu()
            
            choice = input("\nSelect an option (1-10): ").strip()
            
            if choice == '1':
                capture_new_video()
            elif choice == '2':
                display_vhs_decode_menu()
            elif choice == '3':
                display_av_calibration_menu()
            elif choice == '4':
                display_settings_menu()
            elif choice == '5':
                check_dependencies()
            elif choice == '6':
                show_help()
            elif choice == '7':
                clear_screen()
                print("Thanks for using DdD Sync Capture!")
                print("Happy archiving! ")
                break
            else:
                print("Invalid selection. Please choose 1-7.")
                time.sleep(1)
                
        except KeyboardInterrupt:
            clear_screen()
            print("\nGoodbye!")
            break
        except Exception as e:
            print(f"\nUnexpected error: {e}")
            input("Press Enter to continue...")

# New job queue interface functions
def add_vhs_decode_jobs_to_queue():
    """Add VHS decode jobs to the background queue"""
    clear_screen()
    display_header()
    print("\nADD VHS DECODE JOBS TO QUEUE")
    print("=" * 35)
    print("Queue VHS decode jobs for background processing")
    print()
    
    try:
        # Import job queue manager
        sys.path.append('.')
        from job_queue_manager import get_job_queue_manager
        from config import get_capture_directory
        
        job_manager = get_job_queue_manager()
        capture_folder = get_capture_directory()
        
        if not os.path.exists(capture_folder):
            print(f"ERROR: Capture folder '{capture_folder}' does not exist!")
            print("Please ensure you have RF capture files in the configured directory.")
            input("\nPress Enter to return to menu...")
            return
        
        # Find all .lds files with corresponding .json metadata
        rf_files = []
        for f in os.listdir(capture_folder):
            if f.endswith('.lds'):
                json_file = f.replace('.lds', '.json')
                json_path = os.path.join(capture_folder, json_file)
                rf_path = os.path.join(capture_folder, f)
                
                if os.path.exists(json_path):
                    rf_files.append({
                        'rf_file': rf_path,
                        'json_file': json_path,
                        'name': os.path.splitext(f)[0]
                    })
                else:
                    print(f"Warning: No JSON metadata for {f} - skipping")
        
        if not rf_files:
            print(f"No RF files with JSON metadata found in {capture_folder}")
            print("Background decode requires JSON metadata for frame counting.")
            print("\nEnsure your RF files have corresponding .json files:")
            print("  example.lds → example.json")
            input("\nPress Enter to return to menu...")
            return
        
        print(f"Found {len(rf_files)} RF file(s) with metadata:")
        for i, rf_info in enumerate(rf_files, 1):
            size_mb = os.path.getsize(rf_info['rf_file']) / (1024**2)
            print(f"   {i}. {rf_info['name']} ({size_mb:.1f} MB)")
        
        # Get decode settings
        print("\nDECODE SETTINGS:")
        print("=" * 20)
        
        # Video standard
        while True:
            standard = input("Video standard (PAL/NTSC) [PAL]: ").strip().upper()
            if not standard:
                standard = 'PAL'
            if standard in ['PAL', 'NTSC']:
                video_standard = standard.lower()
                break
            print("Please enter PAL or NTSC")
        
        # Tape speed
        while True:
            speed = input("Tape speed (SP/LP/EP) [SP]: ").strip().upper()
            if not speed:
                speed = 'SP'
            if speed in ['SP', 'LP', 'EP']:
                tape_speed = speed
                break
            print("Please enter SP, LP, or EP")
        
        # Additional parameters
        additional_params = input("Additional parameters (optional): ").strip()
        
        # Priority
        while True:
            try:
                priority_input = input("Job priority (1-10, higher = more urgent) [1]: ").strip()
                if not priority_input:
                    priority = 1
                else:
                    priority = int(priority_input)
                if 1 <= priority <= 10:
                    break
                else:
                    print("Please enter 1-10")
            except ValueError:
                print("Please enter a valid number")
        
        print(f"\nQueueing {len(rf_files)} VHS decode jobs...")
        print(f"Settings: {video_standard.upper()} {tape_speed}, priority {priority}")
        print()
        
        # Add jobs to queue
        queued_jobs = []
        for rf_info in rf_files:
            tbc_file = rf_info['rf_file'].replace('.lds', '.tbc')
            
            parameters = {
                'video_standard': video_standard,
                'tape_speed': tape_speed,
                'additional_params': additional_params
            }
            
            job_id = job_manager.add_job(
                job_type="vhs-decode",
                input_file=rf_info['rf_file'],
                output_file=tbc_file,
                parameters=parameters,
                priority=priority
            )
            
            queued_jobs.append(job_id)
            print(f"✓ Queued: {rf_info['name']} → Job {job_id}")
        
        print(f"\n✅ Successfully queued {len(queued_jobs)} VHS decode jobs!")
        print("\nJobs will be processed in the background based on:")
        print(f"• Priority: {priority}")
        print(f"• Queue order: First-in-first-out within same priority")
        print(f"• Max concurrent: {job_manager.max_concurrent_jobs}")
        print("\nUse 'View Job Queue Status & Progress' to monitor progress")
        
    except Exception as e:
        print(f"Error adding jobs to queue: {e}")
    
    input("\nPress Enter to return to menu...")

def add_tbc_export_jobs_to_queue():
    """Add TBC export jobs to the background queue"""
    clear_screen()
    display_header()
    print("\nADD TBC EXPORT JOBS TO QUEUE")
    print("=" * 35)
    print("Queue TBC video export jobs for background processing")
    print()
    
    try:
        # Import job queue manager
        sys.path.append('.')
        from job_queue_manager import get_job_queue_manager
        from config import get_capture_directory
        
        job_manager = get_job_queue_manager()
        capture_folder = get_capture_directory()
        
        if not os.path.exists(capture_folder):
            print(f"ERROR: Capture folder '{capture_folder}' does not exist!")
            print("Please run VHS-Decode first to create TBC files.")
            input("\nPress Enter to return to menu...")
            return
        
        # Find all main .tbc files (exclude _chroma.tbc files as those are handled internally by tbc-video-export)
        all_tbc_files = [f for f in os.listdir(capture_folder) 
                        if f.endswith('.tbc') and not f.endswith('_chroma.tbc')]
        
        # Build list of TBC files to export
        tbc_files = []
        
        # Add main TBC files that haven't been exported
        for f in all_tbc_files:
            tbc_path = os.path.join(capture_folder, f)
            
            # Check for both possible video file naming conventions
            base_name = os.path.splitext(f)[0]  # Remove .tbc extension
            possible_video_files = [
                os.path.join(capture_folder, f"{base_name}_ffv1.mkv"),  # lowercase
                os.path.join(capture_folder, f"{base_name}_FFV1.mkv"),  # uppercase
            ]
            
            # Check if any of the possible video files exist
            video_exists = any(os.path.exists(video_file) for video_file in possible_video_files)
            
            # Only show files that haven't been exported yet
            if not video_exists:
                # Use the standard lowercase naming for new exports
                video_file = os.path.join(capture_folder, f"{base_name}_ffv1.mkv")
                tbc_files.append({
                    'tbc_file': tbc_path,
                    'video_file': video_file,
                    'name': base_name
                })
        
        if not tbc_files:
            print(f"No TBC files ready for export found in {capture_folder}")
            print("Either no TBC files exist, or they have already been exported.")
            input("\nPress Enter to return to menu...")
            return
        
        print(f"Found {len(tbc_files)} TBC file(s) ready for export:")
        for i, tbc_info in enumerate(tbc_files, 1):
            size_mb = os.path.getsize(tbc_info['tbc_file']) / (1024**2)
            print(f"   {i}. {tbc_info['name']} ({size_mb:.1f} MB)")
        
        # Priority
        while True:
            try:
                priority_input = input("\nJob priority (1-10, higher = more urgent) [2]: ").strip()
                if not priority_input:
                    priority = 2  # Slightly higher than decode jobs by default
                else:
                    priority = int(priority_input)
                if 1 <= priority <= 10:
                    break
                else:
                    print("Please enter 1-10")
            except ValueError:
                print("Please enter a valid number")
        
        print(f"\nQueueing {len(tbc_files)} TBC export jobs...")
        print(f"Priority: {priority}")
        print()
        
        # Add jobs to queue
        queued_jobs = []
        for tbc_info in tbc_files:
            job_id = job_manager.add_job(
                job_type="tbc-export",
                input_file=tbc_info['tbc_file'],
                output_file=tbc_info['video_file'],
                parameters={},
                priority=priority
            )
            
            queued_jobs.append(job_id)
            print(f"✓ Queued: {tbc_info['name']} → Job {job_id}")
        
        print(f"\n✅ Successfully queued {len(queued_jobs)} TBC export jobs!")
        print("\nJobs will be processed in the background.")
        print("Note: TBC export jobs use significant CPU resources.")
        print("\nUse 'View Job Queue Status & Progress' to monitor progress")
        
    except Exception as e:
        print(f"Error adding TBC export jobs to queue: {e}")
    
    input("\nPress Enter to return to menu...")

def show_job_queue_display():
    """Show the job queue status display"""
    try:
        # Import the display system
        sys.path.append('.')
        from job_queue_display import JobQueueDisplay
        
        display = JobQueueDisplay()
        display.run_display()
        
    except ImportError:
        print("ERROR: Job queue display system not available")
        print("Please ensure job_queue_display.py is in the project directory")
        input("\nPress Enter to return to menu...")
    except Exception as e:
        print(f"Error running job queue display: {e}")
        input("\nPress Enter to return to menu...")

def configure_job_queue_settings():
    """Configure job queue settings"""
    clear_screen()
    display_header()
    print("\nJOB QUEUE SETTINGS")
    print("=" * 25)
    
    try:
        # Import job queue manager
        sys.path.append('.')
        from job_queue_manager import get_job_queue_manager
        
        job_manager = get_job_queue_manager()
        status = job_manager.get_queue_status()
        
        print(f"Current settings:")
        print(f"• Max concurrent jobs: {status['max_concurrent']}")
        print(f"• Processor status: {'Running' if status['processor_running'] else 'Stopped'}")
        print(f"• Total jobs in queue: {status['total_jobs']}")
        print(f"• Running: {status['running']}, Queued: {status['queued']}")
        print()
        
        print("CONFIGURATION OPTIONS:")
        print("=" * 30)
        print("1. Change max concurrent jobs")
        print("2. Start/stop job processor")
        print("3. Clean up old completed jobs")
        print("4. View detailed job information")
        print("5. Return to menu")
        
        choice = input("\nSelect option (1-5): ").strip()
        
        if choice == '1':
            try:
                current = job_manager.max_concurrent_jobs
                new_max = input(f"Enter new max concurrent jobs (1-8, current: {current}): ").strip()
                
                if new_max:
                    max_jobs = int(new_max)
                    if 1 <= max_jobs <= 8:
                        job_manager.set_max_concurrent_jobs(max_jobs)
                        print(f"Max concurrent jobs set to {max_jobs}")
                    else:
                        print("Please enter a number between 1 and 8")
                
            except ValueError:
                print("Invalid number entered")
        
        elif choice == '2':
            if job_manager.stop_processing:
                job_manager.start_processor()
                print("Job processor started")
            else:
                job_manager.stop_processor()
                print("Job processor stopped")
        
        elif choice == '3':
            try:
                days = input("Remove completed/failed jobs older than how many days? [7]: ").strip()
                days = int(days) if days else 7
                
                print(f"Cleaning up jobs older than {days} days...")
                job_manager.cleanup_old_jobs(days)
                print("Cleanup completed")
                
            except ValueError:
                print("Invalid number entered")
        
        elif choice == '4':
            jobs = job_manager.get_jobs()
            
            if not jobs:
                print("No jobs in queue")
            else:
                print("\nDETAILED JOB INFORMATION:")
                print("=" * 50)
                
                for i, job in enumerate(jobs, 1):
                    print(f"\n{i}. Job: {job.job_id}")
                    print(f"   Type: {job.job_type}")
                    print(f"   Input: {os.path.basename(job.input_file)}")
                    print(f"   Output: {os.path.basename(job.output_file)}")
                    print(f"   Status: {job.status.value}")
                    print(f"   Progress: {job.progress:.1f}%")
                    print(f"   Priority: {job.priority}")
                    print(f"   Created: {job.created_at.strftime('%Y-%m-%d %H:%M:%S')}")
                    
                    if job.started_at:
                        print(f"   Started: {job.started_at.strftime('%Y-%m-%d %H:%M:%S')}")
                    if job.completed_at:
                        print(f"   Completed: {job.completed_at.strftime('%Y-%m-%d %H:%M:%S')}")
                    if job.error_message:
                        print(f"   Error: {job.error_message}")
        
        elif choice == '5':
            return
        
    except Exception as e:
        print(f"Error accessing job queue: {e}")
    
    input("\nPress Enter to continue...")

def legacy_parallel_decode_menu():
    """Legacy direct multi-job decode interface (old behavior)"""
    clear_screen()
    display_header()
    print("\n🚀 LEGACY PARALLEL VHS DECODE")
    print("=" * 40)
    print("Run multiple VHS decode jobs simultaneously with real-time progress tracking")
    print("(This is the original immediate processing interface)")
    print()
    print("Features:")
    print("• Process multiple RF files concurrently")
    print("• Real-time progress bars for each job")
    print("• Frame-accurate progress based on JSON metadata")
    print("• Rich terminal interface with live updates")
    print("• Job status monitoring (frames/sec, ETA, errors)")
    print()
    print("Note: Jobs start immediately and block menu access.")
    print("For background processing, use the main job queue options.")
    print()
    print("LEGACY PARALLEL DECODE OPTIONS:")
    print("=" * 40)
    print("1. Start Multi-Job Decode (Auto-detect RF files)")
    print("2. Configure Parallel Jobs (Select specific files)")
    print("3. Demo Mode (Quick test with limited frames)")
    print("4. View Progress Display (Test interface)")
    print("5. Return to Job Processing Menu")
    
    choice = input("\nSelect option (1-5): ").strip()
    
    if choice == '1':
        start_auto_parallel_decode()
    elif choice == '2':
        configure_parallel_decode()
    elif choice == '3':
        run_parallel_demo()
    elif choice == '4':
        test_progress_display()
    elif choice == '5':
        return
    else:
        print("\nInvalid selection")
        time.sleep(1)
        legacy_parallel_decode_menu()  # Return to this menu

def add_processing_location():
    """Add a new processing location"""
    clear_screen()
    display_header()
    print("\nADD NEW PROCESSING LOCATION")
    print("=" * 35)
    print("Add a directory for scanning RF files and processing.")
    print()
    
    # Get the new directory path
    new_location = input("Enter directory path (or press Enter to cancel): ").strip()
    
    if not new_location:
        print("Operation cancelled.")
        input("\nPress Enter to continue...")
        return
    
    # Expand user home directory if needed
    if new_location.startswith('~'):
        new_location = os.path.expanduser(new_location)
    
    new_location = os.path.abspath(new_location)
    
    # Check if directory exists
    if not os.path.exists(new_location):
        create_dir = input(f"\nDirectory doesn't exist. Create it? (y/N): ").strip().lower()
        if create_dir in ['y', 'yes']:
            try:
                os.makedirs(new_location, exist_ok=True)
                print(f"Created directory: {new_location}")
            except Exception as e:
                print(f"Error creating directory: {e}")
                input("\nPress Enter to continue...")
                return
        else:
            print("Operation cancelled.")
            input("\nPress Enter to continue...")
            return
    
    # Load current config and add the new location
    try:
        sys.path.append('.')
        from config import load_config, save_config
        
        config = load_config()
        processing_locations = config.get('processing_locations', [])
        
        if new_location in processing_locations:
            print(f"\nLocation already exists in list: {new_location}")
        else:
            processing_locations.append(new_location)
            config['processing_locations'] = processing_locations
            
            if save_config(config):
                print(f"\n✓ Successfully added processing location:")
                print(f"   {new_location}")
                
                # Show directory info
                try:
                    rf_files = len([f for f in os.listdir(new_location) if f.lower().endswith(('.lds', '.ldf', '.tbc'))])
                    print(f"   Found {rf_files} RF/TBC files in directory")
                    
                    if sys.platform == 'win32':
                        import shutil
                        total, used, free = shutil.disk_usage(new_location)
                        free_gb = free / (1024**3)
                    else:
                        statvfs = os.statvfs(new_location)
                        free_gb = (statvfs.f_frsize * statvfs.f_bavail) / (1024**3)
                    print(f"   Available space: {free_gb:.1f} GB")
                    
                except Exception as e:
                    print(f"   Note: Could not read directory info: {e}")
            else:
                print(f"\nFailed to save processing location to config.")
                
    except Exception as e:
        print(f"\nError adding processing location: {e}")
    
    input("\nPress Enter to continue...")

def remove_processing_location():
    """Remove a processing location"""
    clear_screen()
    display_header()
    print("\nREMOVE PROCESSING LOCATION")
    print("=" * 35)
    
    # Load current config
    try:
        sys.path.append('.')
        from config import load_config, save_config
        
        config = load_config()
        processing_locations = config.get('processing_locations', [])
        
        if not processing_locations:
            print("No processing locations configured.")
            input("\nPress Enter to continue...")
            return
        
        print("Current processing locations:")
        for i, location in enumerate(processing_locations, 1):
            status = "exists" if os.path.exists(location) else "not found"
            print(f"   {i}. {location} ({status})")
        
        try:
            selection = input(f"\nSelect location to remove (1-{len(processing_locations)}) or 'q' to cancel: ").strip().lower()
            
            if selection == 'q':
                print("Operation cancelled.")
                input("\nPress Enter to continue...")
                return
            
            selection_num = int(selection) - 1
            if 0 <= selection_num < len(processing_locations):
                location_to_remove = processing_locations[selection_num]
                
                confirm = input(f"\nRemove location: {location_to_remove}? (y/N): ").strip().lower()
                if confirm in ['y', 'yes']:
                    processing_locations.remove(location_to_remove)
                    config['processing_locations'] = processing_locations
                    
                    if save_config(config):
                        print(f"\n✓ Successfully removed processing location:")
                        print(f"   {location_to_remove}")
                        print(f"\nNote: The directory and its files were not deleted.")
                    else:
                        print(f"\nFailed to save updated configuration.")
                else:
                    print("Operation cancelled.")
            else:
                print("Invalid selection.")
                
        except ValueError:
            print("Invalid selection.")
            
    except Exception as e:
        print(f"\nError removing processing location: {e}")
    
    input("\nPress Enter to continue...")

def view_location_details():
    """View detailed information about processing locations"""
    clear_screen()
    display_header()
    print("\nPROCESSING LOCATION DETAILS")
    print("=" * 40)
    
    # Load current config
    try:
        sys.path.append('.')
        from config import load_config
        
        config = load_config()
        processing_locations = config.get('processing_locations', [])
        
        if not processing_locations:
            print("No processing locations configured.")
            print("\nUse 'Add New Processing Location' to configure directories")
            print("for scanning RF files and processing.")
            input("\nPress Enter to continue...")
            return
        
        for i, location in enumerate(processing_locations, 1):
            print(f"\nLOCATION {i}: {location}")
            print("=" * 60)
            
            if os.path.exists(location):
                try:
                    # Get directory info
                    files = os.listdir(location)
                    
                    # Count different file types
                    rf_files = [f for f in files if f.lower().endswith(('.lds', '.ldf'))]
                    tbc_files = [f for f in files if f.lower().endswith('.tbc')]
                    json_files = [f for f in files if f.lower().endswith('.tbc.json')]
                    audio_files = [f for f in files if f.lower().endswith(('.wav', '.flac'))]
                    
                    print(f"Status: Directory exists")
                    print(f"RF files (.lds/.ldf): {len(rf_files)}")
                    print(f"TBC files: {len(tbc_files)}")
                    print(f"JSON metadata: {len(json_files)}")
                    print(f"Audio files: {len(audio_files)}")
                    print(f"Total files: {len(files)}")
                    
                    # Show disk space
                    try:
                        if sys.platform == 'win32':
                            import shutil
                            total, used, free = shutil.disk_usage(location)
                            free_gb = free / (1024**3)
                            total_gb = total / (1024**3)
                            used_gb = used / (1024**3)
                        else:
                            statvfs = os.statvfs(location)
                            free_gb = (statvfs.f_frsize * statvfs.f_bavail) / (1024**3)
                            total_gb = (statvfs.f_frsize * statvfs.f_blocks) / (1024**3)
                            used_gb = total_gb - free_gb
                        
                        usage_percent = (used_gb / total_gb) * 100 if total_gb > 0 else 0
                        print(f"Disk space: {free_gb:.1f} GB free of {total_gb:.1f} GB ({usage_percent:.1f}% used)")
                        
                    except Exception as e:
                        print(f"Disk space: Could not determine ({e})")
                    
                    # Show some recent files
                    if rf_files or tbc_files or audio_files:
                        print(f"\nRecent files:")
                        all_media_files = rf_files + tbc_files + audio_files
                        all_media_paths = [os.path.join(location, f) for f in all_media_files]
                        all_media_paths.sort(key=os.path.getmtime, reverse=True)
                        
                        for j, file_path in enumerate(all_media_paths[:5], 1):
                            file_name = os.path.basename(file_path)
                            file_size = os.path.getsize(file_path) / (1024**2)  # MB
                            file_ext = os.path.splitext(file_name)[1]
                            print(f"   {j}. {file_name} ({file_size:.1f} MB, {file_ext})")
                        
                        if len(all_media_paths) > 5:
                            print(f"   ... and {len(all_media_paths) - 5} more media files")
                    
                except PermissionError:
                    print(f"Status: Permission denied - cannot read directory contents")
                except Exception as e:
                    print(f"Status: Error reading directory - {e}")
            else:
                print(f"Status: Directory does not exist")
                print(f"Note: This location should be removed from the list")
        
        print(f"\n" + "=" * 60)
        print(f"SUMMARY: {len(processing_locations)} processing locations configured")
        
    except Exception as e:
        print(f"\nError viewing processing locations: {e}")
    
    input("\nPress Enter to continue...")

def launch_workflow_control_centre():
    """Launch the VHS Workflow Control Centre (Phase 1.3 Implementation)"""
    try:
        # Import and run the workflow control centre
        sys.path.append('.')
        from workflow_control_centre import run_workflow_control_centre
        
        # Clear screen and launch the control centre
        clear_screen()
        
        # Run the workflow control centre
        run_workflow_control_centre()
        
    except ImportError:
        clear_screen()
        display_header()
        print("\nVHS WORKFLOW CONTROL CENTRE")
        print("=" * 35)
        print("ERROR: Workflow Control Centre module not found!")
        print()
        print("The workflow_control_centre.py module is required but not available.")
        print("Please ensure the module is in the project directory.")
        print()
        print("Expected file: workflow_control_centre.py")
        print("This module contains the Phase 1.3 integrated workflow interface.")
        input("\nPress Enter to return to menu...")
    except Exception as e:
        clear_screen()
        display_header()
        print("\nVHS WORKFLOW CONTROL CENTRE")
        print("=" * 35)
        print(f"ERROR: Failed to launch Workflow Control Centre: {e}")
        print()
        print("Please check the workflow_control_centre.py module for issues.")
        input("\nPress Enter to return to menu...")


def display_performance_settings_menu():
    """Display the Performance Settings submenu"""
    while True:
        clear_screen()
        display_header()
        
        # Import config functions
        sys.path.append('.')
        from config import get_ffmpeg_thread_count
        
        current_threads = get_ffmpeg_thread_count()
        
        print("\nPERFORMANCE SETTINGS")
        print("=" * 25)
        print("Configure system performance and resource usage settings")
        print()
        print("CURRENT SETTINGS:")
        print("=" * 20)
        print(f"FFmpeg Thread Count: {current_threads} threads")
        print(f"   (Controls CPU usage for video muxing operations)")
        print()
        print("PERFORMANCE OPTIONS:")
        print("=" * 25)
        print("1. Configure FFmpeg Thread Count")
        print("2. View Performance Status")
        print("3. Reset to Defaults")
        print("4. Return to Settings Menu")
        
        selection = input("\nSelect option (1-4): ").strip()
        
        if selection == '1':
            configure_ffmpeg_threads()
        elif selection == '2':
            view_performance_status()
        elif selection == '3':
            reset_performance_defaults()
        elif selection == '4':
            break  # Return to settings menu
        else:
            print("Invalid selection. Please enter 1-4.")
            time.sleep(1)

def configure_ffmpeg_threads():
    """Configure FFmpeg thread count setting"""
    clear_screen()
    display_header()
    print("\nCONFIGURE FFMPEG THREAD COUNT")
    print("=" * 40)
    print("Configure the number of CPU threads used by FFmpeg for video processing")
    print()
    
    # Import config functions
    sys.path.append('.')
    from config import get_ffmpeg_thread_count, set_ffmpeg_thread_count
    
    current_threads = get_ffmpeg_thread_count()
    
    print(f"Current setting: {current_threads} threads")
    print()
    print("Thread Count Guidelines:")
    print("• 0: Auto-detect (uses all available CPU cores)")
    print("• 1-2: Conservative (low CPU usage, slower processing)")
    print("• 3-4: Balanced (moderate CPU usage, good performance)")
    print("• 5-8: Aggressive (high CPU usage, fastest processing)")
    print("• 9-16: Very aggressive (maximum CPU usage)")
    print()
    print("Recommendations:")
    print("• Use 0 for fastest processing if system has adequate cooling")
    print("• Use 2-4 for laptops or systems with limited cooling")
    print("• Use 1 if you need to keep CPU usage very low")
    print()
    
    while True:
        try:
            thread_input = input(f"Enter thread count (0-16, current: {current_threads}): ").strip()
            
            if not thread_input:
                print("No changes made.")
                break
                
            thread_count = int(thread_input)
            
            if thread_count < 0 or thread_count > 16:
                print("Please enter a number between 0 and 16.")
                continue
            
            if thread_count == current_threads:
                print(f"Thread count is already set to {thread_count}.")
                break
            
            # Show what will change
            print(f"\nConfiguration change:")
            print(f"   Current: {current_threads} threads")
            print(f"   New:     {thread_count} threads")
            
            if thread_count == 0:
                print(f"   Effect:  FFmpeg will use all available CPU cores")
            elif thread_count < current_threads:
                print(f"   Effect:  Lower CPU usage, slower processing")
            elif thread_count > current_threads:
                print(f"   Effect:  Higher CPU usage, faster processing")
            
            confirm = input("\nApply this change? (Y/n): ").strip().lower()
            
            if confirm not in ['n', 'no']:
                if set_ffmpeg_thread_count(thread_count):
                    print(f"\n✓ SUCCESS: FFmpeg thread count set to {thread_count}")
                    print(f"   Changes will take effect for new muxing operations")
                else:
                    print(f"\n✗ ERROR: Failed to save thread count setting")
            else:
                print("\nNo changes made.")
            
            break
            
        except ValueError:
            print("Please enter a valid number.")
        except KeyboardInterrupt:
            print("\nOperation cancelled.")
            break
        except Exception as e:
            print(f"\nError: {e}")
            break
    
    input("\nPress Enter to continue...")

def view_performance_status():
    """View current performance status and system information"""
    clear_screen()
    display_header()
    print("\nPERFORMANCE STATUS")
    print("=" * 25)
    
    # Import config functions
    sys.path.append('.')
    from config import get_ffmpeg_thread_count
    
    current_threads = get_ffmpeg_thread_count()
    
    print("CURRENT PERFORMANCE SETTINGS:")
    print("=" * 40)
    print(f"FFmpeg Thread Count: {current_threads}")
    
    if current_threads == 0:
        print(f"   → FFmpeg will auto-detect and use all CPU cores")
        print(f"   → Maximum processing speed")
        print(f"   → High CPU usage expected")
    elif current_threads == 1:
        print(f"   → Single-threaded processing")
        print(f"   → Lowest CPU usage")
        print(f"   → Slowest processing speed")
    elif current_threads <= 4:
        print(f"   → Conservative multi-threading")
        print(f"   → Moderate CPU usage")
        print(f"   → Good for laptops and low-power systems")
    else:
        print(f"   → Aggressive multi-threading")
        print(f"   → High CPU usage")
        print(f"   → Fast processing speed")
    
    # Show system information if available
    try:
        import os
        import platform
        
        print(f"\nSYSTEM INFORMATION:")
        print(f"=" * 25)
        print(f"Platform: {platform.system()} {platform.release()}")
        print(f"Architecture: {platform.machine()}")
        
        # Try to get CPU core count
        try:
            cpu_count = os.cpu_count()
            if cpu_count:
                print(f"CPU Cores: {cpu_count} logical cores detected")
                
                if current_threads == 0:
                    print(f"   → FFmpeg will use all {cpu_count} cores")
                elif current_threads > cpu_count:
                    print(f"   → Warning: Thread count ({current_threads}) exceeds CPU cores ({cpu_count})")
                elif current_threads == cpu_count:
                    print(f"   → Thread count matches CPU core count")
                else:
                    usage_percent = (current_threads / cpu_count) * 100
                    print(f"   → Using {usage_percent:.0f}% of available CPU cores")
            else:
                print(f"CPU Cores: Could not detect")
        except:
            print(f"CPU Cores: Information not available")
            
    except Exception as e:
        print(f"\nSystem information unavailable: {e}")
    
    print(f"\nPERFORMANCE IMPACT:")
    print(f"=" * 25)
    print(f"• Video muxing operations are affected by thread count")
    print(f"• Higher thread count = faster processing, more CPU usage")
    print(f"• Lower thread count = slower processing, less CPU usage")
    print(f"• Thread count of 0 = automatic (usually best performance)")
    
    print(f"\nOTHER PERFORMANCE FACTORS:")
    print(f"=" * 35)
    print(f"• Storage speed (SSD vs HDD) significantly affects processing")
    print(f"• Available RAM impacts large file operations")
    print(f"• System temperature may cause CPU throttling")
    print(f"• Background processes can compete for CPU resources")
    
    input("\nPress Enter to continue...")

def reset_performance_defaults():
    """Reset performance settings to defaults"""
    clear_screen()
    display_header()
    print("\nRESET PERFORMANCE SETTINGS TO DEFAULTS")
    print("=" * 50)
    print("This will reset all performance settings to their default values.")
    print()
    print("Default settings:")
    print("• FFmpeg Thread Count: 4 (balanced performance)")
    print()
    
    # Import config functions
    sys.path.append('.')
    from config import set_ffmpeg_thread_count
    
    confirm = input("Reset performance settings to defaults? (y/N): ").strip().lower()
    
    if confirm in ['y', 'yes']:
        try:
            if set_ffmpeg_thread_count(4):
                print("\n✓ Performance settings reset to defaults successfully!")
                print("\nDefault settings applied:")
                print("• FFmpeg Thread Count: 4 threads")
                print("\nChanges will take effect for new operations.")
            else:
                print("\n✗ Failed to reset performance settings.")
                print("Please check configuration file permissions.")
                
        except Exception as e:
            print(f"\nError resetting performance settings: {e}")
    else:
        print("\nReset cancelled. No changes made.")
    
    input("\nPress Enter to continue...")

def kill_rogue_vhs_processes():
    """Launch the interactive process killer interface"""
    clear_screen()
    display_header()
    print("\nKILL ROGUE/STUCK VHS PROCESSES")
    print("=" * 40)
    print("Launch interactive process management tool to identify and terminate")
    print("stuck or problematic VHS processing processes.")
    print()
    
    if run_interactive_process_killer is None:
        print("ERROR: Process killer module not available")
        print("Please ensure process_killer.py is in the project directory")
        input("\nPress Enter to return to menu...")
        return
    
    try:
        print("Launching interactive process killer...")
        print("Use the interactive interface to identify and terminate stuck processes.")
        print()
        
        # Launch the interactive process killer
        run_interactive_process_killer()
        
        # No extra input prompt needed - the interactive killer handles its own exit
        
    except KeyboardInterrupt:
        print("\nProcess killer cancelled by user.")
        input("\nPress Enter to return to menu...")
    except Exception as e:
        print(f"\nError running process killer: {e}")
        print("Please check that process_killer.py is available and working properly.")
        input("\nPress Enter to return to menu...")

def clear_all_locations():
    """Clear all processing locations"""
    clear_screen()
    display_header()
    print("\nCLEAR ALL PROCESSING LOCATIONS")
    print("=" * 40)
    
    # Load current config
    try:
        sys.path.append('.')
        from config import load_config, save_config
        
        config = load_config()
        processing_locations = config.get('processing_locations', [])
        
        if not processing_locations:
            print("No processing locations are currently configured.")
            input("\nPress Enter to continue...")
            return
        
        print(f"This will remove all {len(processing_locations)} processing locations:")
        for i, location in enumerate(processing_locations, 1):
            print(f"   {i}. {location}")
        
        print(f"\nWARNING: This only removes the locations from the configuration.")
        print(f"The directories and their files will not be deleted.")
        
        confirm = input(f"\nClear all {len(processing_locations)} processing locations? (y/N): ").strip().lower()
        
        if confirm in ['y', 'yes']:
            config['processing_locations'] = []
            
            if save_config(config):
                print(f"\n✓ Successfully cleared all processing locations.")
                print(f"   {len(processing_locations)} locations removed from configuration")
                print(f"\nYou can add new processing locations using 'Add New Processing Location'")
            else:
                print(f"\nFailed to save updated configuration.")
        else:
            print("Operation cancelled.")
        
    except Exception as e:
        print(f"\nError clearing processing locations: {e}")
    
    input("\nPress Enter to continue...")

if __name__ == "__main__":
    main()
