#!/usr/bin/env python3
"""
Debug version that captures and logs ALL vhs-decode output lines
"""
import subprocess
import re
import time

def run_debug_decode():
    """Run a short vhs-decode session and capture all output"""
    
    # First check if vhs-decode is available using the same method as working code
    import subprocess
    import os
    vhs_decode_path = None
    
    try:
        result = subprocess.run(['which', 'vhs-decode'], capture_output=True, text=True)
        if result.returncode == 0:
            vhs_decode_path = result.stdout.strip()
            print(f"Found vhs-decode in PATH: {vhs_decode_path}")
        else:
            print("vhs-decode not found in PATH")
            # Try looking for it manually
            possible_paths = [
                '/usr/local/bin/vhs-decode',
                '/usr/bin/vhs-decode', 
                os.path.expanduser('~/.local/bin/vhs-decode'),
                os.path.expanduser('~/anaconda3/envs/ddd-capture-toolkit/bin/vhs-decode')
            ]
            for path in possible_paths:
                if os.path.exists(path):
                    vhs_decode_path = path
                    print(f"Found vhs-decode at: {path}")
                    break
            else:
                print("vhs-decode not found anywhere - please install it first")
                return
    except Exception as e:
        print(f"Error checking for vhs-decode: {e}")
        return
    
    cmd = [
        vhs_decode_path,
        '--tf', 'vhs',
        '-t', '3',
        '--ts', 'SP',
        '--no_resample',
        '--recheck_phase',
        '--ire0_adjust',
        '--pal',
        '-s', '1000',  # Start at frame 1000
        '-l', '100',   # Only process 100 frames for quick test
        os.environ.get('TEST_RF_FILE', '/path/to/test.lds'),
        '/tmp/debug_test'
    ]
    
    print("Running debug vhs-decode command:")
    print(f"Command: {' '.join(cmd)}")
    print("=" * 60)
    
    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            universal_newlines=True
        )
        
        line_count = 0
        for line in iter(process.stdout.readline, ''):
            if not line:
                break
                
            line = line.strip()
            if not line:
                continue
                
            line_count += 1
            print(f"Line {line_count:3d}: {repr(line)}")
            
            # Test parsing on this line
            current_frame = None
            fps = None
            
            # Frame patterns
            frame_match = re.search(r'(?:Processing frame|Frame)[:]\s*(\d+)', line, re.IGNORECASE)
            if frame_match:
                current_frame = int(frame_match.group(1))
                print(f"         → FRAME MATCH: {current_frame}")
            
            ratio_match = re.search(r'(\d+)/(\d+)', line)
            if ratio_match and not frame_match:
                current_frame = int(ratio_match.group(1))
                print(f"         → RATIO MATCH: {current_frame}/{ratio_match.group(2)}")
            
            # FPS patterns
            fps_match = re.search(r'(?:at\s+)?([0-9.]+)\s*fps', line, re.IGNORECASE)
            if fps_match:
                fps = float(fps_match.group(1))
                print(f"         → FPS MATCH: {fps}")
            
            # Any line with numbers that might be frames or speed
            if re.search(r'\d+', line):
                print(f"         → Contains numbers: {line}")
            
            if line_count > 50:  # Limit output
                print("... (stopping after 50 lines)")
                break
        
        process.wait()
        print(f"\nProcess completed with return code: {process.returncode}")
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    run_debug_decode()
