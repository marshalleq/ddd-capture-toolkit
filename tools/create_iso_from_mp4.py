#!/usr/bin/env python3
"""
Create DVD-Video ISO files from MP4 sync test patterns

This script converts the long-format MP4 sync test files into proper DVD-Video
ISO disc images with VIDEO_TS structure that can be played on hardware DVD players.
"""

import subprocess
import os
import sys
import tempfile
import shutil

def check_dependencies():
    """Check if required tools are available"""
    required_tools = ['ffmpeg']
    missing_tools = []
    missing_optional = []
    
    # Check required tools
    for tool in required_tools:
        try:
            subprocess.run([tool, '--help'], capture_output=True, check=True)
        except (FileNotFoundError, subprocess.CalledProcessError):
            missing_tools.append(tool)
    
    # Check dvdauthor separately (optional for DVD structure)
    dvdauthor_available = False
    try:
        # dvdauthor --help returns exit code 1, but still works
        result = subprocess.run(['dvdauthor', '--help'], capture_output=True)
        if result.returncode in [0, 1]:  # Accept both 0 and 1 as success
            dvdauthor_available = True
    except FileNotFoundError:
        pass
    
    if not dvdauthor_available:
        missing_optional.append('dvdauthor')
    
    # Check ISO creation tools - need at least one
    iso_tool_available = False
    for tool in ['mkisofs', 'genisoimage']:
        try:
            subprocess.run([tool, '--help'], capture_output=True, check=True)
            iso_tool_available = True
            break
        except (FileNotFoundError, subprocess.CalledProcessError):
            continue
    
    if not iso_tool_available:
        missing_tools.append('mkisofs or genisoimage')
    
    return missing_tools, missing_optional

def create_dvd_iso_from_mp4(mp4_file, iso_file, volume_label, format_type):
    """
    Convert MP4 to proper DVD-Video ISO disc image
    
    Args:
        mp4_file: Path to source MP4 file
        iso_file: Path to output ISO file
        volume_label: Volume label for the disc
        format_type: 'pal' or 'ntsc' for format-specific encoding
    """
    
    if not os.path.exists(mp4_file):
        print(f"ERROR: Source file not found: {mp4_file}")
        return False
    
    print(f"Creating DVD-Video ISO from {os.path.basename(mp4_file)}...")
    print(f"   Volume label: {volume_label}")
    print(f"   Format: {format_type.upper()}")
    
    # Create temporary directory for DVD authoring
    with tempfile.TemporaryDirectory() as temp_dir:
        dvd_dir = os.path.join(temp_dir, 'dvd')
        mpeg_file = os.path.join(temp_dir, 'video.mpg')
        
        # Step 1: Convert MP4 to DVD-compatible MPEG-2
        print("   Converting to DVD-compatible MPEG-2...")
        
        # Set encoding parameters based on format
        if format_type.lower() == 'pal':
            video_params = [
                '-r', '25',                    # 25 fps for PAL
                '-s', '720x576',              # PAL resolution
                '-aspect', '4:3',             # 4:3 aspect ratio
                '-flags', '+cgop',            # Closed GOP for DVD compatibility
                '-sc_threshold', '1000000000', # Disable scene change detection
                '-dc', '10',                  # Intra DC precision
            ]
        else:  # NTSC
            video_params = [
                '-r', '30000/1001',           # 29.97 fps for NTSC
                '-s', '720x480',              # NTSC resolution  
                '-aspect', '4:3',             # 4:3 aspect ratio
                '-flags', '+cgop',            # Closed GOP for DVD compatibility
                '-sc_threshold', '1000000000', # Disable scene change detection
                '-dc', '10',                  # Intra DC precision
            ]
        
        # FFmpeg command to create DVD-compatible MPEG-2
        # Use conservative settings optimized for test pattern content
        ffmpeg_cmd = [
            'ffmpeg', '-y',               # Overwrite output
            '-i', mp4_file,              # Input file
        ] + video_params + [
            '-c:v', 'mpeg2video',        # MPEG-2 video codec
            '-b:v', '4000k',             # 4Mbps video bitrate (conservative for quality)
            '-maxrate', '6000k',         # Max bitrate
            '-bufsize', '2000k',         # Larger buffer for smooth playback
            '-g', '15',                  # GOP size (0.5-0.6 seconds)
            '-bf', '2',                  # B-frames for better compression
            '-qmin', '2',                # Minimum quantizer (better quality)
            '-qmax', '31',               # Maximum quantizer
            '-c:a', 'ac3',               # AC-3 audio codec
            '-b:a', '192k',              # 192kbps audio (sufficient for test patterns)
            '-ar', '48000',              # 48kHz sample rate
            '-ac', '2',                  # Stereo audio
            '-f', 'dvd',                 # DVD format
            mpeg_file
        ]
        
        try:
            result = subprocess.run(ffmpeg_cmd, capture_output=True, text=True, check=True)
            print("   MPEG-2 conversion completed")
        except subprocess.CalledProcessError as e:
            print(f"   MPEG-2 conversion failed: {e.stderr}")
            return False
        
        # Step 2: Check if we have DVD authoring tools
        dvdauthor_available = False
        try:
            # dvdauthor --help returns exit code 1, but still works
            result = subprocess.run(['dvdauthor', '--help'], capture_output=True)
            if result.returncode in [0, 1]:  # Accept both 0 and 1 as success
                dvdauthor_available = True
        except FileNotFoundError:
            pass
        
        if dvdauthor_available:
            # Step 2a: Use dvdauthor to create proper VIDEO_TS structure
            print("   Creating DVD structure with dvdauthor...")
            
            # Create DVD structure
            os.makedirs(dvd_dir, exist_ok=True)
            
            # Create DVD XML configuration
            dvd_xml = os.path.join(temp_dir, 'dvd.xml')
            
            # Set video format for VMGM based on format type
            video_format = 'pal' if format_type.lower() == 'pal' else 'ntsc'
            
            # Create proper DVD structure with VMGM (Video Manager) for hardware compatibility
            # Hardware DVD players require a valid VMGM section to recognize the disc
            xml_content = f'''<?xml version="1.0"?>
<dvdauthor>
    <vmgm />
    <titleset>
        <titles>
            <pgc>
                <vob file="{mpeg_file}" />
            </pgc>
        </titles>
    </titleset>
</dvdauthor>'''
            
            with open(dvd_xml, 'w') as f:
                f.write(xml_content)
            
            # Step 1: Create titleset with dvdauthor
            try:
                # Set video format before running dvdauthor
                os.environ['VIDEO_FORMAT'] = video_format.upper() if video_format else 'NTSC'
                dvdauthor_cmd = ['dvdauthor', '-o', dvd_dir, '-x', dvd_xml]
                result = subprocess.run(dvdauthor_cmd, capture_output=True, text=True)
                
                if result.returncode != 0:
                    print(f"   DVD titleset creation failed: {result.stderr}")
                    return False
                
                print("   DVD titleset created successfully")
                
                # Step 2: Create table of contents (VIDEO_TS.IFO)
                print("   Creating table of contents...")
                toc_cmd = ['dvdauthor', '-o', dvd_dir, '-T']
                toc_result = subprocess.run(toc_cmd, capture_output=True, text=True)
                
                if toc_result.returncode != 0:
                    print(f"   Table of contents creation failed: {toc_result.stderr}")
                    # Continue anyway, some versions give warnings but still work
                
                print("   Table of contents created")
                
                # Check final DVD structure
                video_ts_dir = os.path.join(dvd_dir, 'VIDEO_TS')
                required_files = [
                    'VIDEO_TS.IFO',      # Video Manager Information
                    'VIDEO_TS.BUP',      # Video Manager Backup
                    'VTS_01_0.IFO',      # Title Set Information
                    'VTS_01_0.BUP',      # Title Set Backup
                    'VTS_01_1.VOB'       # Title Video Object
                ]
                
                missing_files = []
                for filename in required_files:
                    if not os.path.exists(os.path.join(video_ts_dir, filename)):
                        missing_files.append(filename)
                
                if not missing_files:
                    print("   Complete DVD structure created")
                    if toc_result.returncode != 0:
                        print("   Table of contents created with warnings (disc should work)")
                elif 'VIDEO_TS.IFO' in missing_files:
                    print("   Video Manager creation failed")
                    print(f"   TOC error: {toc_result.stderr}")
                    return False
                else:
                    print(f"   DVD structure incomplete - missing: {', '.join(missing_files)}")
                    if 'VTS_01_1.VOB' in missing_files:
                        print(f"   DVD authoring failed: {result.stderr}")
                        return False
                    
            except Exception as e:
                print(f"   DVD authoring error: {str(e)}")
                return False
                
        else:
            # Step 2b: Create basic VIDEO_TS structure manually
            print("   Creating basic DVD structure (dvdauthor not available)...")
            
            video_ts_dir = os.path.join(dvd_dir, 'VIDEO_TS')
            os.makedirs(video_ts_dir, exist_ok=True)
            
            # Copy the MPEG file as the main video
            shutil.copy2(mpeg_file, os.path.join(video_ts_dir, 'VTS_01_1.VOB'))
            
            print("   Basic structure created (may not work on all DVD players)")
            print("   Install dvdauthor for proper DVD compatibility")
        
        # Step 3: Create ISO from DVD structure
        print("   Creating ISO image...")
        
        # Find ISO creation tool
        iso_cmd = None
        for cmd in ['mkisofs', 'genisoimage']:
            try:
                subprocess.run([cmd, '--help'], capture_output=True, check=True)
                iso_cmd = cmd
                break
            except (FileNotFoundError, subprocess.CalledProcessError):
                continue
        
        if not iso_cmd:
            print("   No ISO creation tool found (mkisofs or genisoimage needed)")
            return False
        
        # Create DVD-Video compatible ISO with proper settings for hardware players
        # Use only universally supported mkisofs/genisoimage options
        iso_create_cmd = [
            iso_cmd,
            '-dvd-video',                # DVD-Video format (supported on this system)
            '-o', iso_file,              # Output file
            '-V', volume_label,          # Volume label
            dvd_dir                      # Source directory
        ]
        
        try:
            result = subprocess.run(iso_create_cmd, capture_output=True, text=True, check=True)
            
            if os.path.exists(iso_file):
                iso_size = os.path.getsize(iso_file) / (1024*1024)  # MB
                print(f"   DVD-Video ISO created: {iso_size:.1f} MB")
                return True
            else:
                print("   ISO file was not created")
                return False
                
        except subprocess.CalledProcessError as e:
            print(f"   DVD-Video format failed, trying basic format: {e.stderr.split('mkisofs:')[1].split('.')[0] if 'mkisofs:' in e.stderr else 'format error'}")
            
            # Fallback: Create basic ISO with minimal options
            iso_create_cmd_fallback = [
                iso_cmd,
                '-o', iso_file,              # Output file
                '-V', volume_label,          # Volume label
                '-J', '-R',                  # Joliet and Rock Ridge extensions
                dvd_dir                      # Source directory
            ]
            
            try:
                result = subprocess.run(iso_create_cmd_fallback, capture_output=True, text=True, check=True)
                
                if os.path.exists(iso_file):
                    iso_size = os.path.getsize(iso_file) / (1024*1024)  # MB
                    print(f"   Basic ISO created: {iso_size:.1f} MB")
                    print("   Note: Contains proper VIDEO_TS structure for DVD players")
                    return True
                else:
                    print("   ISO file was not created")
                    return False
                    
            except subprocess.CalledProcessError as e2:
                print(f"   Basic ISO creation also failed: {e2.stderr}")
                return False

def create_simple_data_iso(mp4_file, iso_file, volume_label):
    """
    Fallback: Create simple data ISO (original behavior)
    
    Args:
        mp4_file: Path to source MP4 file
        iso_file: Path to output ISO file
        volume_label: Volume label for the disc
    """
    
    print(f"Creating data ISO from {os.path.basename(mp4_file)}...")
    print(f"   Volume label: {volume_label}")
    print("   This will be a data disc, not a video DVD")
    
    # Create temporary directory for ISO contents
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_mp4 = os.path.join(temp_dir, os.path.basename(mp4_file))
        
        # Copy MP4 to temp directory
        print("   Copying file to temporary directory...")
        shutil.copy2(mp4_file, temp_mp4)
        
        # Find ISO creation tool
        iso_cmd = None
        for cmd in ['mkisofs', 'genisoimage']:
            try:
                subprocess.run([cmd, '--help'], capture_output=True, check=True)
                iso_cmd = cmd
                break
            except (FileNotFoundError, subprocess.CalledProcessError):
                continue
        
        if not iso_cmd:
            print("   No ISO creation tool found")
            return False
        
        # Build ISO creation command
        cmd = [
            iso_cmd,
            '-o', iso_file,           # Output file
            '-V', volume_label,       # Volume label
            '-J', '-R',              # Joliet and Rock Ridge
            temp_dir                  # Source directory
        ]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            
            if os.path.exists(iso_file):
                iso_size = os.path.getsize(iso_file) / (1024*1024)  # MB
                print(f"   Data ISO created: {iso_size:.1f} MB")
                return True
            else:
                print("   ISO file was not created")
                return False
                
        except subprocess.CalledProcessError as e:
            print(f"   ISO creation failed: {e.stderr}")
            return False

def main():
    """Main function to create DVD-Video ISOs from all long MP4 files"""
    
    print("DdD Sync Test - DVD-Video ISO Creator")
    print("=" * 50)
    
    # Check dependencies
    missing_required, missing_optional = check_dependencies()
    if missing_required:
        print(f"Missing required tools: {', '.join(missing_required)}")
        print("\nInstallation instructions:")
        if 'ffmpeg' in missing_required:
            print("  FFmpeg:")
            print("    macOS: brew install ffmpeg")
            print("    Linux: sudo apt install ffmpeg")
            print("    Windows: Download from https://ffmpeg.org/")
        return 1
    
    print("Required tools available")
    
    if missing_optional:
        print(f"Optional tools missing: {', '.join(missing_optional)}")
        print("   DVD authoring quality may be reduced")
        print("   Install for better compatibility:")
        if 'dvdauthor' in missing_optional:
            print("     macOS: brew install dvdauthor")
            print("     Linux: sudo apt install dvdauthor")
        if 'mkisofs' in missing_optional and 'genisoimage' in missing_optional:
            print("     macOS: brew install cdrtools")
            print("     Linux: sudo apt install genisoimage")
        print()
    
    # Get script directory and media directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    media_dir = os.path.join(os.path.dirname(script_dir), 'media')
    iso_dir = os.path.join(media_dir, 'iso')
    
    # Create ISO directory if it doesn't exist
    os.makedirs(iso_dir, exist_ok=True)
    
    # Ask user for ISO type preference
    print("Choose ISO creation mode:")
    print("1. DVD-Video (recommended - plays on hardware DVD players)")
    print("2. Data disc (simple - MP4 files only, for computers)")
    choice = input("\nSelect mode (1-2) [1]: ").strip() or '1'
    
    use_dvd_mode = choice == '1'
    
    if use_dvd_mode and ('mkisofs' in missing_optional and 'genisoimage' in missing_optional):
        print("\nDVD-Video mode requires mkisofs or genisoimage")
        print("Falling back to data disc mode...")
        use_dvd_mode = False
    
    print(f"\nCreating {'DVD-Video' if use_dvd_mode else 'data'} ISOs...")
    
    # Scan for any MP4 files in the media directory
    conversions = []
    
    if not os.path.exists(media_dir):
        print(f"Error: Media directory not found: {media_dir}")
        print("Please ensure the media directory exists and contains MP4 files.")
        return 1
    
    # Look for MP4 files in both media/ and media/mp4/ directories
    mp4_files = []
    search_dirs = [
        media_dir,  # Original location for backward compatibility
        os.path.join(media_dir, 'mp4')  # New organized location
    ]
    
    try:
        for search_dir in search_dirs:
            if not os.path.exists(search_dir):
                continue
                
            for filename in os.listdir(search_dir):
                if filename.lower().endswith('.mp4'):
                    mp4_path = os.path.join(search_dir, filename)
                    if os.path.isfile(mp4_path):  # Ensure it's a file, not a directory
                        # Store relative path info for better organization
                        relative_dir = os.path.relpath(search_dir, media_dir)
                        if relative_dir == '.':
                            mp4_files.append(filename)
                        else:
                            mp4_files.append(os.path.join(relative_dir, filename))
    except Exception as e:
        print(f"Error scanning media directories: {e}")
        return 1
    
    if not mp4_files:
        print("No MP4 files found in media directory!")
        print(f"\nScanned directory: {media_dir}")
        print("\nCreate MP4 files first using Menu option 4:")
        print("   - Calibration Videos (sync test with ON/OFF pattern)")
        print("   - Belle Nuit Static Charts (continuous test pattern)")
        print("   - Custom Test Pattern Videos (using your own test pattern)")
        print("   - VHS Timecode Test Pattern (precision sync)")
        return 1
    
    print(f"Found {len(mp4_files)} MP4 file(s):")
    
    # Create conversion info for each MP4 file
    for mp4_filename in sorted(mp4_files):
        mp4_path = os.path.join(media_dir, mp4_filename)
        
        # Generate ISO filename (replace .mp4 with .iso, extract basename only)
        iso_filename = os.path.basename(mp4_filename).replace('.mp4', '.iso')
        iso_path = os.path.join(iso_dir, iso_filename)
        
        # Generate volume label from filename (max 32 chars for ISO, uppercase, replace spaces/special chars)
        base_name = os.path.splitext(mp4_filename)[0]
        volume_label = base_name.upper().replace(' ', '_').replace('-', '_')[:32]
        # Remove any remaining special characters that might cause issues
        volume_label = ''.join(c for c in volume_label if c.isalnum() or c == '_')
        if not volume_label:  # Fallback if name becomes empty
            volume_label = 'TEST_VIDEO'
        
        # Try to detect format from filename for DVD mode
        detected_format = 'ntsc'  # Default to NTSC
        filename_lower = mp4_filename.lower()
        if 'pal' in filename_lower:
            detected_format = 'pal'
        elif 'ntsc' in filename_lower:
            detected_format = 'ntsc'
        # Could add more detection logic here if needed
        
        # Show file info
        file_size = os.path.getsize(mp4_path) / (1024*1024)  # MB
        iso_status = "(ISO exists)" if os.path.exists(iso_path) else ""
        format_info = f"(detected: {detected_format.upper()})" if use_dvd_mode else ""
        print(f"   • {mp4_filename} ({file_size:.1f} MB) {format_info} {iso_status}")
        
        conversions.append({
            'mp4': mp4_path,
            'iso': iso_path,
            'label': volume_label,
            'format': detected_format
        })
    
    successful_conversions = 0
    total_conversions = len(conversions)
    
    for conversion in conversions:
        mp4_file = conversion['mp4']
        iso_file = conversion['iso']
        label = conversion['label']
        format_type = conversion['format']
        
        if os.path.exists(iso_file):
            print(f"\nISO already exists: {os.path.basename(iso_file)}")
            response = input("   Overwrite? (y/N): ").strip().lower()
            if response not in ['y', 'yes']:
                print("   Skipped.")
                continue
        
        print(f"\nProcessing {format_type.upper()} file...")
        
        if use_dvd_mode:
            success = create_dvd_iso_from_mp4(mp4_file, iso_file, label, format_type)
        else:
            success = create_simple_data_iso(mp4_file, iso_file, label)
        
        if success:
            successful_conversions += 1
    
    print("\n" + "=" * 50)
    print(f"Completed: {successful_conversions}/{total_conversions} ISOs created")
    
    if successful_conversions > 0:
        print(f"\n{('DVD-Video' if use_dvd_mode else 'Data')} ISO Usage:")
        if use_dvd_mode:
            print("1. Burn ISO files to DVD using your preferred burning software")
            print("2. Play directly on hardware DVD players or game consoles")
            print("3. Test sync patterns with real hardware timing")
            print("4. Record DVD output to VHS for sync test tapes")
        else:
            print("1. Burn ISO files to CD/DVD as data discs")
            print("2. Access MP4 files on computers with disc drives")
            print("3. Use for file transfer or backup purposes")
        
        print(f"\nISO files saved to: {iso_dir}")
    
    return 0 if successful_conversions > 0 else 1

if __name__ == "__main__":
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\nOperation cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\nUnexpected error: {e}")
        sys.exit(1)
