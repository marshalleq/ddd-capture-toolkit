#!/usr/bin/env python3
"""
Test exactly what the job queue manager is doing
"""

def test_parsing():
    # Simulate the exact code from job_queue_manager.py
    line = "Total Fields:  284578 Total Frames: 142289           Export Mode:    Luma + Chroma (merged)"
    total_frames = 0
    
    print(f"Testing line: {repr(line)}")
    print(f"'Total Frames:' in line: {'Total Frames:' in line}")
    print(f"total_frames == 0: {total_frames == 0}")
    
    # Exact code from job_queue_manager.py
    if 'Total Frames:' in line and total_frames == 0:
        print("✅ Condition passed")
        try:
            # Use regex to extract number directly after "Total Frames:"
            import re
            match = re.search(r'Total Frames:\s*(\d+)', line)
            if match:
                total_frames = int(match.group(1))
                print(f"✅ SUCCESS: extracted {total_frames}")
            else:
                print(f"❌ REGEX FAILED: Could not parse total frames from line: {line}")
        except Exception as e:
            print(f"❌ EXCEPTION: Error parsing total frames: {e}")
    else:
        print("❌ Condition failed")

if __name__ == "__main__":
    test_parsing()
