#!/usr/bin/env python3
"""
DdD Sync Capture - Dependency Checker

This script verifies that all required dependencies are installed and working.
Run this after installation to ensure everything is set up correctly.
"""

import subprocess
import sys
import os
import importlib
from pathlib import Path

def check_python_version():
    """Check Python version requirement"""
    print("Checking Python version...")
    version = sys.version_info
    if version >= (3, 7):
        print(f"   Python {version.major}.{version.minor}.{version.micro} (>= 3.7 required) OK")
        return True
    else:
        print(f"   Python {version.major}.{version.minor}.{version.micro} (< 3.7, please upgrade) ERROR")
        return False

def check_python_packages():
    """Check required Python packages"""
    print("\nChecking Python packages...")
    
    required_packages = [
        ('PIL', 'Pillow'),
        ('numpy', 'NumPy'),
        ('cv2', 'opencv-python'),
    ]
    
    optional_packages = [
        ('scipy', 'SciPy'),
    ]
    
    all_good = True
    
    # Check required packages
    for package, name in required_packages:
        try:
            module = importlib.import_module(package)
            version = module.__version__ if hasattr(module, '__version__') else 'unknown'
            
            # Special check for NumPy version compatibility with vhs-decode
            if package == 'numpy':
                try:
                    major_version = int(version.split('.')[0])
                    if major_version >= 2:
                        print(f"   {name} {version} WARNING (vhs-decode requires NumPy 1.x)")
                        print(f"      Current NumPy 2.x may cause vhs-decode to fail")
                        print(f"      Fix with: pip install 'numpy<2.0'")
                    else:
                        print(f"   {name} {version} OK")
                except (ValueError, AttributeError):
                    print(f"   {name} {version} OK")
            else:
                print(f"   {name} {version} OK")
        except ImportError:
            print(f"   {name} ERROR (install with: pip install {name})")
            all_good = False
    
    # Check optional packages
    for package, name in optional_packages:
        try:
            module = importlib.import_module(package)
            version = module.__version__ if hasattr(module, '__version__') else 'unknown'
            print(f"   {name} {version} (optional) OK")
        except ImportError:
            print(f"   {name} (optional - install with: pip install {name})")
    
    return all_good

def check_system_commands():
    """Check required system commands"""
    print("\n Checking system commands...")
    
    commands = {
        'sox': 'SOX (audio processing)',
        'ffmpeg': 'FFmpeg (video processing)',
        sys.executable: 'Python (current executable)',
    }
    
    # Add vhs-decode check (critical for RF decoding)
    vhs_decode_paths = [
        'vhs-decode',  # In PATH
        str(Path.home() / '.local/bin/vhs-decode'),  # User local install
    ]
    
    vhs_decode_found = False
    for vhs_path in vhs_decode_paths:
        try:
            result = subprocess.run([vhs_path, '--help'], 
                                  capture_output=True, 
                                  text=True, 
                                  timeout=10)
            if result.returncode == 0:
                print(f"    vhs-decode (VHS RF decoder) - found at {vhs_path}")
                vhs_decode_found = True
                break
        except (FileNotFoundError, subprocess.TimeoutExpired):
            continue
        except Exception:
            continue
    
    if not vhs_decode_found:
        print(f"    vhs-decode (VHS RF decoder) - not found")
        print(f"      Install with: pip install vhs-decode")
        print(f"      Or check ~/.local/bin is in PATH")
    
    # Add platform-specific tools
    try:
        from platform_utils import detector
        if detector.is_windows:
            # Windows-specific tools
            commands['powershell'] = 'PowerShell (for screenshots and system integration)'
        elif detector.is_macos:
            # macOS-specific tools
            commands['screencapture'] = 'screencapture (for screenshots)'
        else:
            # Linux/Unix tools
            commands['mono'] = 'Mono .NET runtime (for VHS audio alignment, optional)'
    except ImportError:
        # Fallback if platform_utils not available
        if sys.platform == 'win32':
            commands['powershell'] = 'PowerShell (for screenshots and system integration)'
        elif sys.platform == 'darwin':
            commands['screencapture'] = 'screencapture (for screenshots)'
        else:
            commands['mono'] = 'Mono .NET runtime (for VHS audio alignment, optional)'
    
    # Add ld-decode check (critical for LaserDisc RF decoding)
    ld_decode_tools = ['ld-analyse', 'ld-chroma-decoder', 'ld-dropout-correct']
    ld_decode_found = False
    for tool in ld_decode_tools:
        try:
            result = subprocess.run([tool, '--version'], 
                                  capture_output=True, 
                                  text=True, 
                                  timeout=5)
            if result.returncode == 0:
                version_line = result.stdout.split('\n')[0] if result.stdout else result.stderr.split('\n')[0]
                print(f"    {tool} (LaserDisc RF decoder) - {version_line} OK")
                ld_decode_found = True
                break
        except (FileNotFoundError, subprocess.TimeoutExpired, Exception):
            continue
    
    if not ld_decode_found:
        print(f"    ld-decode (LaserDisc RF decoder) - not found")
        print(f"      Install following instructions at: https://github.com/happycube/ld-decode")
    
    # Add tbc-video-export check (critical for TBC to video conversion)
    try:
        result = subprocess.run(['tbc-video-export', '--version'], 
                              capture_output=True, 
                              text=True, 
                              timeout=10)
        if result.returncode == 0:
            version_line = result.stdout.split('\n')[0] if result.stdout else 'version info unavailable'
            print(f"    tbc-video-export (TBC to video converter) - {version_line} OK")
        else:
            print(f"    tbc-video-export (TBC to video converter) - command failed")
    except (FileNotFoundError, subprocess.TimeoutExpired):
        print(f"    tbc-video-export (TBC to video converter) - not found")
        print(f"      Install with: pip install tbc-video-export")
    except Exception as e:
        print(f"    tbc-video-export (TBC to video converter) - error: {e}")
    
    all_good = True
    
    for cmd, description in commands.items():
        try:
            result = subprocess.run([cmd, '--version'], 
                                  capture_output=True, 
                                  text=True, 
                                  timeout=5)
            # Some commands return non-zero exit codes but still work (like FFmpeg)
            # Check if we got meaningful output regardless of exit code
            has_output = bool(result.stdout.strip() or result.stderr.strip())
            success_codes = [0] if cmd != 'ffmpeg' else [0, 8]  # FFmpeg returns 8 for --version
            
            if result.returncode in success_codes or (has_output and 'version' in result.stdout.lower()):
                # Get version from output
                version_line = result.stdout.split('\n')[0] if result.stdout else result.stderr.split('\n')[0]
                print(f"    {description} - {version_line} OK")
            else:
                print(f"    {description} - command failed (exit code {result.returncode})")
                all_good = False
        except subprocess.TimeoutExpired:
            print(f"    {description} - command timeout")
            all_good = False
        except FileNotFoundError:
            print(f"    {description} - not found in PATH")
            all_good = False
        except Exception as e:
            print(f"    {description} - error: {e}")
            all_good = False
    
    return all_good

def check_platform_specific():
    """Check platform-specific requirements"""
    print(f"\n  Checking platform-specific features ({sys.platform})...")
    
    if sys.platform == 'win32':
        # Windows - check PowerShell
        try:
            result = subprocess.run(['powershell', '-Command', 'Get-Host'], 
                                  capture_output=True, timeout=5)
            if result.returncode == 0:
                print("    PowerShell available (for screenshots)")
            else:
                print("    PowerShell not working")
        except:
            print("    PowerShell not available")
    
    elif sys.platform == 'darwin':
        # macOS - check screencapture
        try:
            result = subprocess.run(['screencapture', '-h'], 
                                  capture_output=True, timeout=5)
            if result.returncode in [0, 1]:  # screencapture returns 1 for help
                print("    screencapture available")
            else:
                print("    screencapture not working")
        except:
            print("    screencapture not available")
    
    else:
        # Linux - check spectacle (optional)
        try:
            result = subprocess.run(['spectacle', '--help'], 
                                  capture_output=True, timeout=5)
            if result.returncode == 0:
                print("    KDE Spectacle available")
            else:
                print("     KDE Spectacle not working (install with: sudo apt install spectacle)")
        except:
            print("     KDE Spectacle not found (install with: sudo apt install spectacle)")

def check_vhs_audio_tools():
    """Check VHS audio alignment tools"""
    print("\n Checking VHS audio alignment tools...")
    
    # Check for VhsDecodeAutoAudioAlign.exe
    possible_paths = [
        'tools/VhsDecodeAutoAudioAlign.exe',  # Correct location
        'tools/audio-sync/VhsDecodeAutoAudioAlign.exe',  # Alternative location
        str(Path.home() / 'projects' / 'vhs-decode-auto-audio-align' / 'VhsDecodeAutoAudioAlign.exe'),
        'VhsDecodeAutoAudioAlign.exe'
    ]
    
    found_tool = False
    for path in possible_paths:
        if os.path.exists(path):
            size = os.path.getsize(path) / (1024*1024)  # MB
            print(f"    VhsDecodeAutoAudioAlign.exe found ({size:.1f} MB) at {path}")
            found_tool = True
            break
    
    if not found_tool:
        print("     VhsDecodeAutoAudioAlign.exe not found (optional for VHS audio alignment)")
        print("      Download from: https://github.com/oyvindln/vhs-decode")
        print("      Place in: tools/VhsDecodeAutoAudioAlign.exe")
    
    # Check the wrapper script
    audio_script = 'tools/audio-sync/vhs_audio_align.py'
    if os.path.exists(audio_script):
        print(f"    VHS audio alignment wrapper script available")
    else:
        print(f"    VHS audio alignment wrapper script missing")


def main():
    """Main dependency check routine"""
    print("DdD Sync Capture - Dependency Checker")
    print("=" * 50)
    
    checks = [
        check_python_version(),
        check_python_packages(),
        check_system_commands(),
    ]
    
    check_platform_specific()
    check_vhs_audio_tools()
    
    print("\n" + "=" * 50)
    
    if all(checks):
        print(" All critical dependencies are satisfied!")
        print("You should be able to run the DdD Sync Capture system.")
        return 0
    else:
        print(" Some critical dependencies are missing.")
        print("Please install the missing components and run this check again.")
        print("\nInstallation help:")
        print("- conda env create -f environment.yml")
        print("- pip install -r requirements.txt")
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
