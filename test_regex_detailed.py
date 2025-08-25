#!/usr/bin/env python3
"""
Test the regex parsing with detailed debugging
"""

import re

# Copy the exact line from the log
test_line = "Total Fields:  284578 Total Frames: 142289           Export Mode:    Luma + Chroma (merged)"

print("=== DETAILED REGEX TEST ===")
print(f"Line length: {len(test_line)}")
print(f"Line repr: {repr(test_line)}")
print()

# Check the condition first
if 'Total Frames:' in test_line:
    print("✅ 'Total Frames:' found in line")
    
    # Find the position
    pos = test_line.find('Total Frames:')
    print(f"Position: {pos}")
    print(f"Text around it: {repr(test_line[pos-5:pos+20])}")
    
    try:
        # Use regex to extract number directly after "Total Frames:"
        import re
        match = re.search(r'Total Frames:\s*(\d+)', test_line)
        if match:
            total_frames = int(match.group(1))
            print(f"✅ SUCCESS: extracted {total_frames}")
        else:
            print("❌ REGEX FAILED")
            
            # Debug: try variations
            print("\nTrying different patterns:")
            
            patterns = [
                r'Total Frames:\s*(\d+)',
                r'Total Frames: (\d+)',
                r'Total Frames:\s+(\d+)',
                r'Total Frames:\s*(\d+)\s',
            ]
            
            for pattern in patterns:
                match = re.search(pattern, test_line)
                if match:
                    print(f"✅ Pattern '{pattern}' works: {match.group(1)}")
                else:
                    print(f"❌ Pattern '{pattern}' failed")
                    
    except Exception as e:
        print(f"❌ EXCEPTION: {e}")
else:
    print("❌ 'Total Frames:' NOT found in line")
