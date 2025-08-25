#!/usr/bin/env python3
"""
Test script for Parallel VHS Decode
Demo version with limited frame range
"""

import os
import sys
from parallel_vhs_decode import ParallelVHSDecoder

def main():
    print("🎬 Parallel VHS Decode - Demo Version")
    print("=" * 50)
    print("This will run a limited decode (100 frames) to demonstrate the interface")
    print()
    
    decoder = ParallelVHSDecoder()
    
    # Find RF files
    # Try to get capture directory from config or environment
    capture_dir = os.environ.get('CAPTURE_DIR', '/path/to/captures')
    
    # If default path doesn't exist, try common locations
    if not os.path.exists(capture_dir):
        possible_paths = [
            '/media/captures',
            '/mnt/captures',
            os.path.expanduser('~/Captures'),
            os.path.expanduser('~/Desktop/Captures')
        ]
        for path in possible_paths:
            if os.path.exists(path):
                capture_dir = path
                break
        else:
            print(f"❌ Capture directory not found. Please set CAPTURE_DIR environment variable.")
            print(f"   Current setting: {capture_dir}")
            return
    rf_files = [f for f in os.listdir(capture_dir) if f.endswith('.lds') or f.endswith('.ldf')]
    
    if not rf_files:
        print("❌ No RF files found for testing")
        return
    
    print(f"Found {len(rf_files)} RF file(s):")
    for i, f in enumerate(rf_files, 1):
        size_gb = os.path.getsize(os.path.join(capture_dir, f)) / (1024**3)
        print(f"  {i}. {f} ({size_gb:.1f} GB)")
    
    print()
    choice = input("Which file would you like to test? (Enter number or 'all' for all files): ").strip()
    
    selected_files = []
    if choice.lower() == 'all':
        selected_files = rf_files
    else:
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(rf_files):
                selected_files = [rf_files[idx]]
            else:
                print("Invalid selection")
                return
        except ValueError:
            print("Invalid input")
            return
    
    # Add jobs with limited frame count for demo
    for rf_file in selected_files:
        rf_path = os.path.join(capture_dir, rf_file)
        
        # Demo: limit to 100 frames for quick testing
        additional_params = "-s 1000 -l 100"  # Start at frame 1000, length 100 frames
        
        # You can choose PAL or NTSC
        standard = 'PAL'  # Change to 'NTSC' if needed
        
        job = decoder.add_job(rf_path, standard, 'SP', additional_params)
        
        # Override total frames for demo (since we're only processing 100)
        job.total_frames = 100
        
        print(f"✅ Added demo job: {rf_file} (100 frames, {standard})")
    
    if not decoder.jobs:
        print("No jobs added")
        return
    
    print(f"\n🚀 Starting parallel decode of {len(decoder.jobs)} job(s)...")
    print("📊 Demo limited to 100 frames per job for quick testing")
    print("⏹️  Press Ctrl+C to stop all jobs")
    print("=" * 50)
    
    try:
        decoder.run_parallel_decode()
    except KeyboardInterrupt:
        print("\n⏹️  Demo cancelled by user")
    
    print("\n✅ Demo completed!")

if __name__ == '__main__':
    main()
