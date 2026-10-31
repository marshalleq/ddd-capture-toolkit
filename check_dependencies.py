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
    """Check Python version requirement.

    The toolkit targets Python 3.12 (pinned in the conda environment files).
    vhs-decode >= 0.4.0 requires Python >= 3.11, and tbc-video-export
    publishes no wheels for Python >= 3.14, so a too-new interpreter
    (typically a system python.org install used instead of the conda env)
    fails to resolve dependencies. Flag both ends explicitly rather than
    passing them with an unhelpful "OK".
    """
    print("Checking Python version...")
    version = sys.version_info
    ver_str = f"{version.major}.{version.minor}.{version.micro}"
    if version < (3, 11):
        print(f"   Python {ver_str} ERROR (too old - vhs-decode >= 0.4.0 requires Python >= 3.11)")
        print(f"      The toolkit is designed to run in the 'ddd-capture-toolkit' conda env (Python 3.12).")
        print(f"      Recreate it: conda remove -n ddd-capture-toolkit --all, then ./setup.sh")
        return False
    elif version >= (3, 14):
        print(f"   Python {ver_str} ERROR (too new - tbc-video-export has no wheels for >= 3.14)")
        print(f"      The toolkit is designed to run in the 'ddd-capture-toolkit' conda env (Python 3.12).")
        print(f"      Do not pip install against a system Python. Run ./setup.sh, then:")
        print(f"      conda activate ddd-capture-toolkit")
        return False
    elif version[:2] != (3, 12):
        print(f"   Python {ver_str} OK (toolkit conda env pins 3.12)")
        return True
    else:
        print(f"   Python {ver_str} OK")
        return True

def _installed_vhs_decode_version():
    """Version string of the pip-installed vhs-decode, or None if it is not installed."""
    try:
        from importlib import metadata
        return metadata.version('vhs_decode')
    except Exception:
        return None


def _numpy2_breaks_installed_vhs_decode(numpy_version):
    """True if NumPy is 2.x and the installed vhs-decode is older than 0.4.0."""
    try:
        if int(str(numpy_version).split('.')[0]) < 2:
            return False
        vhs = _installed_vhs_decode_version()
        if not vhs:
            return False
        parts = [int(p) for p in vhs.split('.')[:2]]
        return parts < [0, 4]
    except (ValueError, TypeError):
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
            
            # NumPy 2.x is fine for vhs-decode 0.4.0 or newer (it declares numpy>=1.24 and
            # decodes correctly under NumPy 2.5). Earlier releases, including the 0.3.8.1
            # on PyPI that easy mode installs, crash on the first frame under NumPy 2
            # ("only 0-dimensional arrays can be converted to Python scalars").
            if package == 'numpy' and _numpy2_breaks_installed_vhs_decode(version):
                print(f"   {name} {version} WARNING (the installed vhs-decode needs NumPy 1.x)")
                print(f"      vhs-decode {_installed_vhs_decode_version()} crashes under NumPy 2.x; use vhs-decode 0.4.0 or newer")
                print(f"      (performance setup builds it), or: pip install 'numpy<2.0'")
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

    # LD helper programs the decode and export stages run. Flags copies that sit
    # outside the environment and copies that can no longer start (for example a
    # reader linked against an older FFmpeg after an operating system upgrade).
    ld_health_ok = True
    print(f"\n    LD helper programs (decode and export):")
    try:
        import tool_health
        for report in tool_health.check_ld_tools():
            lines, severity = tool_health.format_report(report)
            for line in lines:
                print(line)
            if severity == 'fail':
                ld_health_ok = False
    except ImportError:
        print(f"      (tool_health module not available - skipped)")

    # Add ld-compress dependencies check (for LDS to LDF compression)
    print(f"\n    LDS Compression dependencies (ld-compress):")

    # Check for ld-lds-converter (required for ld-compress)
    try:
        result = subprocess.run(['ld-lds-converter', '--help'],
                              capture_output=True,
                              text=True,
                              timeout=5)
        # ld-lds-converter may return non-zero for --help, check if we get output
        if result.stdout or result.stderr:
            print(f"      ld-lds-converter (LDS format converter) - OK")
        else:
            print(f"      ld-lds-converter (LDS format converter) - command failed")
    except FileNotFoundError:
        print(f"      ld-lds-converter (LDS format converter) - not found")
        print(f"        Required for ld-compress. Install with ld-decode tools.")
    except subprocess.TimeoutExpired:
        print(f"      ld-lds-converter (LDS format converter) - timeout")
    except Exception as e:
        print(f"      ld-lds-converter (LDS format converter) - error: {e}")

    # Check for ld-compress script
    ld_compress_paths = [
        str(Path(__file__).parent / 'external' / 'vhs-decode' / 'scripts' / 'ld-compress'),
        str(Path(__file__).parent / 'external' / 'ld-decode' / 'scripts' / 'ld-compress'),
    ]
    ld_compress_found = False
    for path in ld_compress_paths:
        if os.path.exists(path):
            print(f"      ld-compress script - found at {path}")
            ld_compress_found = True
            break

    # Also check if ld-compress is in PATH
    if not ld_compress_found:
        try:
            result = subprocess.run(['which', 'ld-compress'],
                                  capture_output=True,
                                  text=True,
                                  timeout=5)
            if result.returncode == 0 and result.stdout.strip():
                print(f"      ld-compress script - found in PATH at {result.stdout.strip()}")
                ld_compress_found = True
        except:
            pass

    if not ld_compress_found:
        print(f"      ld-compress script - not found")
        print(f"        Should be in external/vhs-decode/scripts/ or PATH")

    # Check for pv (pipeviewer - optional, for progress display)
    try:
        result = subprocess.run(['pv', '--version'],
                              capture_output=True,
                              text=True,
                              timeout=5)
        if result.returncode == 0:
            version_line = result.stdout.split('\n')[0] if result.stdout else 'unknown'
            print(f"      pv (pipeviewer for progress) - {version_line} OK")
        else:
            print(f"      pv (pipeviewer for progress) - command failed (optional)")
    except FileNotFoundError:
        print(f"      pv (pipeviewer for progress) - not found (optional)")
        print(f"        Install with: sudo apt install pv (for compression progress bars)")
    except Exception:
        print(f"      pv (pipeviewer for progress) - not available (optional)")
    
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
    
    return all_good and ld_health_ok

def check_ffmpeg_features():
    """Check that an ffmpeg with libsoxr is available for final-mux.

    The final mux resamples audio with aresample=resampler=soxr. Performance mode
    compiles an ffmpeg with it. conda-forge's ffmpeg (easy mode) has none, so easy
    mode needs a system ffmpeg that does; the mux finds it by itself.
    """
    print("\n  Checking FFmpeg features required by final-mux...")
    try:
        import tool_health
        found = tool_health.find_soxr_ffmpeg()
        if found:
            print(f"    libsoxr enabled (final-mux audio resampling: OK) - {found}")
            return True

        print("    No ffmpeg with libsoxr found")
        print("    The final-mux step uses aresample=resampler=soxr for audio")
        print("    sample-rate conversion and will FAIL without it.")
        print()
        print("    To fix:")
        print("      Easy mode: install a system ffmpeg yourself (setup does not install system")
        print("                 packages). conda's ffmpeg has no libsoxr.")
        print("                   Fedora: enable RPM Fusion, then sudo dnf swap ffmpeg-free ffmpeg --allowerasing")
        print("                   Debian/Ubuntu: sudo apt install ffmpeg")
        print("                   macOS: brew install ffmpeg")
        print("      Performance mode: re-run setup.sh --performance (compiles ffmpeg with libsoxr)")
        return False
    except FileNotFoundError:
        print("    FFmpeg not found in PATH")
        return False
    except Exception as e:
        print(f"    Error checking ffmpeg features: {e}")
        return False

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
        check_ffmpeg_features(),
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
