#!/usr/bin/env python3
"""
Test the regex parsing to see why it's failing
"""

import re

# The actual line from the log
test_line = "Total Fields:  284578 Total Frames: 142289           Export Mode:    Luma + Chroma (merged)"

print(f"Testing line: '{test_line}'")
print()

# Test the new regex
pattern = r'Total Frames:\s*(\d+)'
match = re.search(pattern, test_line)

if match:
    total_frames = int(match.group(1))
    print(f"✅ NEW REGEX WORKS: extracted {total_frames}")
else:
    print("❌ NEW REGEX FAILED")

# Test if 'Total Frames:' is in the line
if 'Total Frames:' in test_line:
    print("✅ 'Total Frames:' found in line")
else:
    print("❌ 'Total Frames:' NOT found in line")
