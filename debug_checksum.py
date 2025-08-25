#!/usr/bin/env python3
"""
Debug checksum validation in robust timecode system
"""

import numpy as np
import sys

# Add the timecode generator path
timecode_gen_path = os.path.join(os.path.dirname(__file__), 'tools', 'timecode-generator')
if os.path.exists(timecode_gen_path):
    sys.path.append(timecode_gen_path)
else:
    # Fallback to current directory for imports
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from shared_timecode_robust import SharedTimecodeRobust

def debug_checksum():
    generator = SharedTimecodeRobust("PAL")
    
    # Test frame 7
    frame_num = 7
    print(f"Debugging frame {frame_num}:")
    
    # Generate audio
    audio = generator.generate_robust_fsk_audio(frame_num)
    
    # Show expected encoding
    binary = format(frame_num, '024b')
    checksum = generator._calculate_robust_checksum(frame_num)
    checksum_bin = format(checksum, '08b')
    expected_bits = binary + checksum_bin
    
    print(f"Frame number: {frame_num}")
    print(f"Binary (24-bit): {binary}")
    print(f"Calculated checksum: {checksum}")
    print(f"Checksum binary: {checksum_bin}")
    print(f"Complete expected: {expected_bits}")
    print()
    
    # Decode each bit manually
    print("Bit-by-bit decoding:")
    print("Bit | Expected | Detected | Match")
    print("----|----------|----------|------")
    
    decoded_bits = []
    failed_bits = 0
    
    for bit_idx in range(32):
        start_bit = bit_idx * generator.samples_per_bit
        end_bit = start_bit + generator.samples_per_bit
        bit_audio = audio[start_bit:end_bit]
        
        # Decode this bit
        result = generator._analyze_bit_robust(bit_audio)
        
        expected_bit = expected_bits[bit_idx]
        
        if result is not None:
            detected_bit, confidence = result
            decoded_bits.append(detected_bit)
            match = "✓" if detected_bit == expected_bit else "✗"
        else:
            decoded_bits.append('?')
            detected_bit = '?'
            match = "✗"
            failed_bits += 1
        
        print(f"{bit_idx:3d} | {expected_bit:8s} | {detected_bit:8s} | {match}")
    
    print()
    print(f"Expected:  {expected_bits}")
    print(f"Decoded:   {''.join(decoded_bits)}")
    print(f"Failed bits: {failed_bits}")
    
    # Try checksum validation
    if '?' not in decoded_bits:
        frame_bits = decoded_bits[:24]
        checksum_bits = decoded_bits[24:]
        
        try:
            decoded_frame = int(''.join(frame_bits), 2)
            decoded_checksum = int(''.join(checksum_bits), 2)
            
            print(f"Decoded frame number: {decoded_frame}")
            print(f"Decoded checksum: {decoded_checksum}")
            
            # Calculate expected checksum for decoded frame
            expected_checksum = generator._calculate_robust_checksum(decoded_frame)
            print(f"Expected checksum for decoded frame: {expected_checksum}")
            
            if decoded_checksum == expected_checksum:
                print("✓ Checksum validation PASSED")
            else:
                print("✗ Checksum validation FAILED")
                
        except ValueError as e:
            print(f"Error decoding: {e}")
    
    # Test the full decoding pipeline
    print("\nTesting full decoding pipeline:")
    
    # Test _decode_frame_segment directly
    print("Testing _decode_frame_segment directly:")
    direct_result = generator._decode_frame_segment(audio)
    print(f"Direct frame segment result: {direct_result}")
    
    # Test full pipeline
    results = generator.decode_robust_fsk_audio(audio)
    print(f"Full pipeline results: {results}")

if __name__ == "__main__":
    debug_checksum()
