#!/usr/bin/env python3
"""
Analyze the expected timecode bit patterns for early frames

This helps us understand if the dominance of 800Hz (0 bits) is expected
based on the actual frame ID values that should be encoded.
"""

def frame_id_to_bits(frame_id):
    """Convert frame ID to 32-bit binary representation"""
    return format(frame_id, '032b')

def analyze_expected_patterns():
    """Analyze the expected bit patterns for first several frames"""
    print("Expected timecode bit patterns for early frames:")
    print("Frame ID | 32-bit binary (MSB first)           | Zeros | Ones | Ratio")
    print("---------|-------------------------------------|-------|------|-------")
    
    for frame_id in range(10):
        bits = frame_id_to_bits(frame_id)
        zero_count = bits.count('0')
        one_count = bits.count('1')
        zero_ratio = zero_count / 32
        
        print(f"{frame_id:8d} | {bits} | {zero_count:5d} | {one_count:4d} | {zero_ratio:.3f}")
    
    print("\nBit position analysis for frames 0-9:")
    
    # Analyze each bit position
    bit_stats = {}
    for bit_pos in range(32):
        zeros = 0
        ones = 0
        for frame_id in range(10):
            bits = frame_id_to_bits(frame_id)
            if bits[bit_pos] == '0':
                zeros += 1
            else:
                ones += 1
        bit_stats[bit_pos] = (zeros, ones)
    
    print("Bit Pos | Zeros | Ones | Dominant")
    print("--------|-------|------|----------")
    for bit_pos in range(32):
        zeros, ones = bit_stats[bit_pos]
        dominant = '0' if zeros > ones else '1'
        print(f"{bit_pos:7d} | {zeros:5d} | {ones:4d} | {dominant:8s}")

if __name__ == "__main__":
    analyze_expected_patterns()
