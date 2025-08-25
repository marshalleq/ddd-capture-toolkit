#!/usr/bin/env python3

import os
import sys
from analyze_test_pattern import find_all_audio_tone_starts, find_all_video_pattern_starts

def debug_timing_analysis():
    """Debug the timing analysis to see what's being detected"""
    
    # Look for the most recent validation files
    temp_folder = "temp"
    
    if not os.path.exists(temp_folder):
        print(f"Temp folder {temp_folder} not found")
        return
    
    # Find validation files
    audio_files = [f for f in os.listdir(temp_folder) if f.startswith("validation_") and f.endswith("_aligned.wav")]
    video_files = [f for f in os.listdir(temp_folder) if f.startswith("RF-Sample_") and f.endswith("_ffv1.mkv")]
    
    if not audio_files:
        print("No validation aligned audio files found")
        return
        
    if not video_files:
        print("No RF video files found")
        return
    
    # Get most recent files
    audio_file = os.path.join(temp_folder, sorted(audio_files)[-1])
    video_file = os.path.join(temp_folder, sorted(video_files)[-1])
    
    print(f"Analyzing:")
    print(f"  Audio: {audio_file}")
    print(f"  Video: {video_file}")
    print()
    
    # Find audio tone starts
    print("=== AUDIO ANALYSIS ===")
    audio_starts = find_all_audio_tone_starts(audio_file)
    print(f"Audio tone starts: {len(audio_starts)} detected")
    for i, start in enumerate(audio_starts[:5]):  # Show first 5
        print(f"  Audio tone {i+1}: {start:.3f}s")
    if len(audio_starts) > 5:
        print(f"  ... and {len(audio_starts) - 5} more")
    print()
    
    # Find video pattern starts  
    print("=== VIDEO ANALYSIS ===")
    video_starts = find_all_video_pattern_starts(video_file)
    print(f"Video pattern starts: {len(video_starts)} detected")
    for i, start in enumerate(video_starts[:5]):  # Show first 5
        print(f"  Video pattern {i+1}: {start:.3f}s")
    if len(video_starts) > 5:
        print(f"  ... and {len(video_starts) - 5} more")
    print()
    
    # Calculate some sample offsets
    if audio_starts and video_starts:
        print("=== SAMPLE OFFSET CALCULATIONS ===")
        print("Using first few pairs:")
        
        for i in range(min(3, len(audio_starts), len(video_starts))):
            audio_time = audio_starts[i]
            video_time = video_starts[i]
            offset = audio_time - video_time
            print(f"  Pair {i+1}: Audio {audio_time:.3f}s - Video {video_time:.3f}s = {offset:+.3f}s")
            
            if offset > 0:
                print(f"    → Audio starts {offset:.3f}s AFTER video")
            else:
                print(f"    → Audio starts {abs(offset):.3f}s BEFORE video")
        print()
        
        # Show the expected result
        print("=== EXPECTED vs ACTUAL ===")
        print("Expected: Audio should start BEFORE video (negative offsets)")
        print("  Because: We start audio recording first, then start video after delay")
        print("Actual: See offset calculations above")
        print()
        
        if audio_starts[0] > video_starts[0]:
            print("⚠️  ISSUE DETECTED: First audio tone starts AFTER first video pattern")
            print("   This suggests either:")
            print("   1. Audio alignment is incorrectly shifting audio timing")
            print("   2. Test pattern detection is finding wrong reference points") 
            print("   3. There's a bug in the timing reference calculations")
        else:
            print("✓ Timing order looks correct: Audio starts before video")

if __name__ == "__main__":
    debug_timing_analysis()
    
    # Also test with unaligned audio to see if alignment is the problem
    print("\n" + "=" * 60)
    print("TESTING WITH UNALIGNED AUDIO")
    print("=" * 60)
    
    temp_folder = "temp"
    if os.path.exists(temp_folder):
        # Find unaligned validation audio files
        unaligned_files = [f for f in os.listdir(temp_folder) if f.startswith("validation_") and f.endswith(".flac")]
        
        if unaligned_files:
            unaligned_file = os.path.join(temp_folder, sorted(unaligned_files)[-1])
            print(f"Testing unaligned audio: {unaligned_file}")
            
            print("\n=== UNALIGNED AUDIO ANALYSIS ===")
            unaligned_audio_starts = find_all_audio_tone_starts(unaligned_file)
            print(f"Unaligned audio tone starts: {len(unaligned_audio_starts)} detected")
            for i, start in enumerate(unaligned_audio_starts[:5]):  # Show first 5
                print(f"  Unaligned tone {i+1}: {start:.3f}s")
            
            print("\n=== COMPARISON: ALIGNED vs UNALIGNED ===")
            if unaligned_audio_starts:
                print("Expected: If alignment is correct, unaligned should show audio BEFORE video")
                print("Expected: Aligned should match the timing we captured with")
                print("")
                
                # Compare first tone timing
                video_files = [f for f in os.listdir(temp_folder) if f.startswith("RF-Sample_") and f.endswith("_ffv1.mkv")]
                if video_files:
                    video_file = os.path.join(temp_folder, sorted(video_files)[-1])
                    video_starts = find_all_video_pattern_starts(video_file)
                    
                    if video_starts and unaligned_audio_starts:
                        unaligned_offset = unaligned_audio_starts[0] - video_starts[0]
                        print(f"Unaligned offset: {unaligned_offset:+.3f}s (audio - video)")
                        
                        # Get aligned offset from earlier analysis
                        aligned_files = [f for f in os.listdir(temp_folder) if f.startswith("validation_") and f.endswith("_aligned.wav")]
                        if aligned_files:
                            aligned_file = os.path.join(temp_folder, sorted(aligned_files)[-1])
                            aligned_audio_starts = find_all_audio_tone_starts(aligned_file)
                            if aligned_audio_starts:
                                aligned_offset = aligned_audio_starts[0] - video_starts[0]
                                print(f"Aligned offset:   {aligned_offset:+.3f}s (audio - video)")
                                print(f"Alignment shift:  {aligned_offset - unaligned_offset:+.3f}s")
                                print("")
                                
                                if unaligned_offset < 0 and aligned_offset > 0:
                                    print("🔍 DIAGNOSIS: Alignment is shifting audio in the wrong direction!")
                                    print("   - Unaligned: Audio before video (correct for our capture method)")
                                    print("   - Aligned: Audio after video (incorrect - alignment broke timing)")
                                elif unaligned_offset > 0:
                                    print("🔍 DIAGNOSIS: Problem is in capture timing, not alignment!")
                                    print("   - Even unaligned audio starts after video")
                                    print("   - This suggests video actually started before audio recording")
        else:
            print("No unaligned validation files found")
