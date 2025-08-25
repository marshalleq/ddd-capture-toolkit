#!/usr/bin/env python3
"""
VHS Audio Alignment Tool

This script wraps the VHS decode audio alignment process using SOX and the
VhsDecodeAutoAudioAlign.exe tool. It processes captured VHS audio to align
it with the RF capture timing.

Dependencies:
- SOX (audio processing)
- mono (for running .NET applications on Unix)
- VhsDecodeAutoAudioAlign.exe (from vhs-decode-auto-audio-align project)
"""

import subprocess
import os
import sys
import argparse
import platform
from pathlib import Path

def check_dependencies():
    """Check if required tools are available"""
    required_tools = []
    missing_tools = []
    
    # Check SOX
    try:
        subprocess.run(['sox', '--version'], capture_output=True, check=True)
    except (FileNotFoundError, subprocess.CalledProcessError):
        missing_tools.append('sox')
    
    # Check mono (only on Unix-like systems)
    if platform.system() != 'Windows':
        try:
            subprocess.run(['mono', '--version'], capture_output=True, check=True)
        except (FileNotFoundError, subprocess.CalledProcessError):
            missing_tools.append('mono')
    
    return missing_tools

def find_align_tool():
    """
    Find the VhsDecodeAutoAudioAlign.exe tool
    
    Returns path to the tool or None if not found
    """
    
    # Common locations to check
    possible_paths = [
        # In the same directory as this script
        Path(__file__).parent / "VhsDecodeAutoAudioAlign.exe",
        
        # In tools directory (relative to project root)
        Path(__file__).parent.parent.parent / "tools" / "VhsDecodeAutoAudioAlign.exe",
        
        # In tools directory (from current working directory)
        Path.cwd() / "tools" / "VhsDecodeAutoAudioAlign.exe",
        
        # In parent tools directory
        Path(__file__).parent.parent / "VhsDecodeAutoAudioAlign.exe",
        
        # User's project directory (from your example)
        Path.home() / "projects" / "vhs-decode-auto-audio-align" / "VhsDecodeAutoAudioAlign.exe",
        
        # Current working directory
        Path.cwd() / "VhsDecodeAutoAudioAlign.exe",
    ]
    
    for path in possible_paths:
        if path.exists():
            return str(path)
    
    return None

def align_audio(input_wav, tbc_json, output_wav, sample_rate=78125):
    """
    Align VHS audio using the decode pipeline
    
    Args:
        input_wav: Path to input WAV file
        tbc_json: Path to corresponding TBC JSON file
        output_wav: Path for aligned output WAV file  
        sample_rate: Sample rate for processing (default: 78125 Hz)
    """
    
    print(f"Starting VHS audio alignment...")
    print(f"   Input:  {input_wav}")
    print(f"   TBC:    {tbc_json}")
    print(f"   Output: {output_wav}")
    
    # Check inputs exist
    if not os.path.exists(input_wav):
        print(f"Input WAV file not found: {input_wav}")
        return False
        
    if not os.path.exists(tbc_json):
        print(f"TBC JSON file not found: {tbc_json}")
        return False
    
    # Find alignment tool
    align_tool = find_align_tool()
    if not align_tool:
        print("VhsDecodeAutoAudioAlign.exe not found!")
        print("   Please ensure it's installed in one of these locations:")
        print("   - tools/audio-sync/VhsDecodeAutoAudioAlign.exe")
        print("   - ~/projects/vhs-decode-auto-audio-align/VhsDecodeAutoAudioAlign.exe")
        return False
    
    print(f"Found alignment tool: {align_tool}")
    
    # Build the complex pipeline command
    # This replicates: sox -D input.wav -t raw ... | mono VhsDecodeAutoAudioAlign.exe ... | sox -D -t raw ... output.wav
    
    try:
        # Step 1: SOX input processing (matches working Mac command)
        sox_input_cmd = [
            'sox', '-D', input_wav, 
            '-t', 'raw', 
            '-b', '24', 
            '-c', '2', 
            '-L', 
            '-e', 'signed-integer', 
            '-'
        ]
        
        # Step 2: Audio alignment (with mono if not Windows)
        if platform.system() == 'Windows':
            align_cmd = [
                align_tool, 'stream-align',
                '--sample-size-bytes', '6',
                '--stream-sample-rate-hz', str(sample_rate),
                '--json', tbc_json
            ]
        else:
            align_cmd = [
                'mono', align_tool, 'stream-align',
                '--sample-size-bytes', '6', 
                '--stream-sample-rate-hz', str(sample_rate),
                '--json', tbc_json
            ]
        
        # Step 3: SOX output processing  
        sox_output_cmd = [
            'sox', '-D',
            '-t', 'raw',
            '-r', str(sample_rate),
            '-b', '24',
            '-c', '2', 
            '-L',
            '-e', 'signed-integer',
            '-',
            output_wav
        ]
        
        print("Running alignment pipeline...")
        print(f"   Step 1: {' '.join(sox_input_cmd)}")
        print(f"   Step 2: {' '.join(align_cmd)}")
        print(f"   Step 3: {' '.join(sox_output_cmd)}")
        
        # Create the pipeline: sox | align | sox
        proc1 = subprocess.Popen(sox_input_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        proc2 = subprocess.Popen(align_cmd, stdin=proc1.stdout, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        proc1.stdout.close()  # Allow proc1 to receive SIGPIPE if proc2 exits
        proc3 = subprocess.Popen(sox_output_cmd, stdin=proc2.stdout, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        proc2.stdout.close()  # Allow proc2 to receive SIGPIPE if proc3 exits
        
        # Wait for completion
        stdout, stderr = proc3.communicate()
        
        # Get errors from all processes
        proc1_stdout, proc1_stderr = proc1.communicate() if proc1.poll() is None else (b'', b'')
        proc2_stdout, proc2_stderr = proc2.communicate() if proc2.poll() is None else (b'', b'')
        
        # Check if successful
        if proc3.returncode == 0:
            if os.path.exists(output_wav):
                output_size = os.path.getsize(output_wav) / (1024*1024)  # MB
                print(f"Audio alignment completed successfully!")
                print(f"   Output file: {output_size:.1f} MB")
                return True
            else:
                print("Alignment completed but output file not found")
                return False
        else:
            print(f"Audio alignment failed (exit code: {proc3.returncode})")
            if stderr:
                print(f"   Error: {stderr.decode()}")
            return False
            
    except Exception as e:
        print(f"Error during audio alignment: {e}")
        return False

def main():
    """Main function with command line argument parsing"""
    parser = argparse.ArgumentParser(
        description='Align VHS audio capture with RF timing using VHS decode tools',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic alignment
  python vhs_audio_align.py my_capture.wav RF-Sample_2025-07-21.tbc.json aligned_output.wav
  
  # Custom sample rate
  python vhs_audio_align.py --sample-rate 96000 capture.wav timing.json output.wav
        """
    )
    
    parser.add_argument('input_wav', nargs='?', help='Input WAV file from VHS capture')
    parser.add_argument('tbc_json', nargs='?', help='TBC JSON file with RF timing data')  
    parser.add_argument('output_wav', nargs='?', help='Output aligned WAV file')
    parser.add_argument('--sample-rate', type=int, default=78125, 
                       help='Sample rate for processing (default: 78125 Hz)')
    parser.add_argument('--check-deps', action='store_true',
                       help='Check dependencies and exit')
    
    args = parser.parse_args()
    
    print("VHS Audio Alignment Tool")
    print("=" * 50)
    
    # Check dependencies
    missing_deps = check_dependencies()
    if missing_deps:
        print(f"Missing dependencies: {', '.join(missing_deps)}")
        print("\nInstallation instructions:")
        for dep in missing_deps:
            if dep == 'sox':
                print("  SOX:")
                print("    macOS: brew install sox")
                print("    Linux: sudo apt install sox")
                print("    Windows: Download from http://sox.sourceforge.net/")
            elif dep == 'mono':
                print("  Mono (.NET runtime):")
                print("    macOS: brew install mono")
                print("    Linux: sudo apt install mono-runtime")
        return 1
    
    if args.check_deps:
        print("All dependencies are available")
        
        # Also check for the alignment tool
        align_tool = find_align_tool()
        if align_tool:
            print(f"VhsDecodeAutoAudioAlign.exe found at: {align_tool}")
        else:
            print("VhsDecodeAutoAudioAlign.exe not found")
            print("   Download from: https://github.com/oyvindln/vhs-decode")
            print("   Place in: tools/audio-sync/VhsDecodeAutoAudioAlign.exe")
        
        return 0
    
    # Validate required arguments for alignment
    if not all([args.input_wav, args.tbc_json, args.output_wav]):
        print("Missing required arguments for audio alignment")
        print("Usage: python vhs_audio_align.py input.wav timing.tbc.json output.wav")
        print("Or use: python vhs_audio_align.py --check-deps")
        return 1
    
    print("Dependencies check passed")
    print()
    
    # Run alignment
    success = align_audio(args.input_wav, args.tbc_json, args.output_wav, args.sample_rate)
    
    if success:
        print("Audio alignment completed successfully!")
        print(f"   Aligned audio saved to: {args.output_wav}")
        return 0
    else:
        print("Audio alignment failed")
        return 1

if __name__ == "__main__":
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("Operation cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}")
        sys.exit(1)
