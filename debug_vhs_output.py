#!/usr/bin/env python3
"""
Debug script to capture and analyze real vhs-decode output patterns
"""
import re
import sys

def test_parsing_patterns():
    """Test various parsing patterns against example output"""
    
    # Common patterns we might see in vhs-decode output
    test_lines = [
        "Processing frame 12345",
        "Frame: 12345/54321 (22.7%)",
        "12345/54321 (22.7%)",
        "Processed 12345 frames at 23.4 fps",
        "23.4 fps",
        "at 23.4fps",
        "Speed: 23.4 fps",
        "Decoding at 23.4 fps",
        "Frame 12345, 23.4fps",
        "12345 frames processed (23.4 fps)",
        "[12345/54321] 22.7% - 23.4fps",
        "12345/54321 at 23.4 fps",
    ]
    
    print("Testing parsing patterns on example output:")
    print("=" * 50)
    
    for line in test_lines:
        print(f"\nInput: '{line}'")
        
        # Test frame patterns
        current_frame = None
        total_frames = None
        
        # Pattern 1: "Processing frame 12345" or "Frame 12345"
        frame_match = re.search(r'(?:Processing frame|Frame)[:]\s*(\d+)', line, re.IGNORECASE)
        if frame_match:
            current_frame = int(frame_match.group(1))
            print(f"  Frame Pattern 1: {current_frame}")
        
        # Pattern 2: "12345/25000" or "Frame: 12345/25000"
        if current_frame is None:
            frame_ratio_match = re.search(r'(\d+)/(\d+)', line)
            if frame_ratio_match:
                current_frame = int(frame_ratio_match.group(1))
                total_frames = int(frame_ratio_match.group(2))
                print(f"  Frame Pattern 2: {current_frame}/{total_frames}")
        
        # Pattern 3: Just "12345" (standalone number)
        if current_frame is None:
            standalone_match = re.search(r'\b(\d+)\b', line)
            if standalone_match:
                current_frame = int(standalone_match.group(1))
                print(f"  Frame Pattern 3: {current_frame}")
        
        # Test FPS patterns
        fps = None
        
        # Pattern 1: "23.4 fps" or "at 23.4fps"
        fps_match = re.search(r'(?:at\s+)?([0-9.]+)\s*fps', line, re.IGNORECASE)
        if fps_match:
            fps = float(fps_match.group(1))
            print(f"  FPS Pattern 1: {fps}")
        
        # Pattern 2: "Speed: 23.4"
        if fps is None:
            speed_match = re.search(r'speed[:]\s*([0-9.]+)', line, re.IGNORECASE)
            if speed_match:
                fps = float(speed_match.group(1))
                print(f"  FPS Pattern 2: {fps}")
        
        if current_frame is None and fps is None:
            print("  No patterns matched")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        # Parse actual vhs-decode output from file or stdin
        print("Analyzing real vhs-decode output...")
        with open(sys.argv[1], 'r') if sys.argv[1] != '-' else sys.stdin as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                    
                # Apply parsing logic
                frame_match = re.search(r'(?:Processing frame|Frame)[:]\s*(\d+)', line, re.IGNORECASE)
                ratio_match = re.search(r'(\d+)/(\d+)', line)
                fps_match = re.search(r'(?:at\s+)?([0-9.]+)\s*fps', line, re.IGNORECASE)
                
                if frame_match or ratio_match or fps_match:
                    print(f"Line {line_num}: {line}")
                    if frame_match:
                        print(f"  -> Frame: {frame_match.group(1)}")
                    if ratio_match:
                        print(f"  -> Ratio: {ratio_match.group(1)}/{ratio_match.group(2)}")
                    if fps_match:
                        print(f"  -> FPS: {fps_match.group(1)}")
                    print()
    else:
        test_parsing_patterns()
