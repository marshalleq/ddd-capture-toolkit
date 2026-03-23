#!/usr/bin/env python3

"""
Demo script showing what the enhanced workflow display looks like 
with running jobs that have progress information.
"""

import os
import sys

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def create_progress_bar(percentage, width=20):
    """Create a simple progress bar"""
    filled = int(width * percentage / 100)
    bar = '█' * filled + '░' * (width - filled)
    return bar

def format_time(seconds):
    """Format seconds into readable time"""
    if seconds < 60:
        return f"{seconds:.0f}s"
    elif seconds < 3600:
        minutes = seconds // 60
        secs = seconds % 60
        return f"{minutes:.0f}m {secs:.0f}s"
    else:
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        return f"{hours:.0f}h {minutes:.0f}m"

def create_enhanced_progress_cell(job_name, percentage, fps, eta_seconds, status="running"):
    """Create an enhanced status cell with progress information"""
    
    if status == "running" and percentage > 0:
        # Multi-line cell with progress bar
        progress_bar = create_progress_bar(percentage, 18)
        eta_str = format_time(eta_seconds) if eta_seconds > 0 else "Unknown"
        
        lines = [
            f"Running {percentage:4.1f}%",
            f"[{progress_bar}]",
            f"🎬 {fps:5.1f}fps",
            f"⏱️  ETA {eta_str}"
        ]
        return "\n".join(lines)
        
    elif status == "running" and percentage == 0:
        return "Processing...\n⏳ Starting up\n🔄 Initializing\n📊 0% complete"
        
    elif status == "failed":
        return "❌ Failed\n💾 Check space\n🗂️  /tmp full\n🔧 Needs fix"
        
    elif status == "complete":
        return "✅ Complete\n📁 File ready\n✨ Success\n🎉 Done"
        
    elif status == "ready":
        return "⏳ Ready\n📝 Configured\n🚀 Can start\n▶️  Pending"
        
    else:
        return f"{status}\n \n \n "

def demo_enhanced_display():
    """Show what the enhanced display looks like with progress"""
    
    print("=" * 80)
    print("ENHANCED WORKFLOW CONTROL CENTRE - PROGRESS DEMO")
    print("=" * 80)
    print()
    
    print("This shows what you would see when jobs are running with progress:")
    print()
    
    # Simulate the table layout
    print("┏━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━┓")
    print("┃ Project        ┃ (D)ecode RF  ┃ (E)xport     ┃ (A)lign      ┃ (F)inal      ┃")
    print("┣━━━━━━━━━━━━━━━━╋━━━━━━━━━━━━━━━╋━━━━━━━━━━━━━━━╋━━━━━━━━━━━━━━━╋━━━━━━━━━━━━━━━┫")
    
    # Row 1: Project with running export job showing progress
    export_cell = create_enhanced_progress_cell("Export", 34.2, 28.5, 420, "running")
    decode_cell = create_enhanced_progress_cell("Decode", 0, 0, 0, "complete")
    align_cell = create_enhanced_progress_cell("Align", 0, 0, 0, "ready")
    final_cell = create_enhanced_progress_cell("Final", 0, 0, 0, "ready")
    
    project_1_lines = [
        "┃ 1. Metallica1  ┃",
        "┃                ┃", 
        "┃                ┃",
        "┃                ┃"
    ]
    
    decode_lines = decode_cell.split('\n')
    export_lines = export_cell.split('\n')
    align_lines = align_cell.split('\n')
    final_lines = final_cell.split('\n')
    
    for i in range(4):
        line = project_1_lines[i]
        line += f" {decode_lines[i]:13s} ┃"
        line += f" {export_lines[i]:13s} ┃" 
        line += f" {align_lines[i]:13s} ┃"
        line += f" {final_lines[i]:13s} ┃"
        print(line)
    
    print("┣━━━━━━━━━━━━━━━━╋━━━━━━━━━━━━━━━╋━━━━━━━━━━━━━━━╋━━━━━━━━━━━━━━━╋━━━━━━━━━━━━━━━┫")
    
    # Row 2: Project with failed job due to disk space
    decode2_cell = create_enhanced_progress_cell("Decode", 0, 0, 0, "ready")  
    export2_cell = create_enhanced_progress_cell("Export", 0, 0, 0, "failed")
    align2_cell = create_enhanced_progress_cell("Align", 0, 0, 0, "ready")
    final2_cell = create_enhanced_progress_cell("Final", 0, 0, 0, "ready")
    
    project_2_lines = [
        "┃ 2. Test_Tape   ┃",
        "┃                ┃",
        "┃                ┃", 
        "┃                ┃"
    ]
    
    decode2_lines = decode2_cell.split('\n')
    export2_lines = export2_cell.split('\n')
    align2_lines = align2_cell.split('\n')
    final2_lines = final2_cell.split('\n')
    
    for i in range(4):
        line = project_2_lines[i]
        line += f" {decode2_lines[i]:13s} ┃"
        line += f" {export2_lines[i]:13s} ┃"
        line += f" {align2_lines[i]:13s} ┃"
        line += f" {final2_lines[i]:13s} ┃"
        print(line)
    
    print("┗━━━━━━━━━━━━━━━━┻━━━━━━━━━━━━━━━┻━━━━━━━━━━━━━━━┻━━━━━━━━━━━━━━━┻━━━━━━━━━━━━━━━┛")
    
    print()
    print("LEGEND:")
    print("🎬 = Frames per second (processing speed)")
    print("⏱️  = Estimated time remaining")
    print("⏳ = Processing/Starting")
    print("❌ = Failed (likely due to disk space)")
    print("✅ = Completed successfully")
    print("📊 = Progress percentage")
    print()
    
    print("=" * 80)
    print("CURRENT ISSUE: /tmp FILESYSTEM IS 100% FULL")
    print("=" * 80)
    print()
    print("Your jobs are failing because /tmp has no space left:")
    print("  /tmp: 63G used / 63G total (100% full)")
    print()
    print("SOLUTIONS:")
    print("1. Free up /tmp space:")
    print("   sudo rm -rf /tmp/ffmpeg_* /tmp/tbc_* /tmp/*.tmp")
    print()  
    print("2. Configure output to use /mnt/nvme2tb (2TB available):")
    print("   Edit job configuration to use /mnt/nvme2tb instead of /tmp")
    print()
    print("3. Increase /tmp size (if using tmpfs):")
    print("   sudo mount -o remount,size=100G tmpfs /tmp")
    print()
    print("Once space is available, start a new job and you'll see:")
    print("✓ Real-time progress bars")
    print("✓ FPS counters")  
    print("✓ ETA calculations")
    print("✓ Multi-line status cells with color coding")

if __name__ == "__main__":
    demo_enhanced_display()
