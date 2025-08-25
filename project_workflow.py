#!/usr/bin/env python3
"""
Project Workflow Management Interface
Provides consolidated functions for managing project workflows and jobs.

This is now a compatibility wrapper that delegates to the full
Project Workflow Status Browser implementation.
"""

import os
import sys
import time
from datetime import datetime

def show_project_workflow_status():
    """Main Project Workflow Status Browser interface"""
    # Import and delegate to the comprehensive implementation
    try:
        from project_workflow_browser import show_project_workflow_status as browser_main
        browser_main()
    except ImportError as e:
        # Fallback to the original simplified implementation
        _show_legacy_workflow_status()
        
def _show_legacy_workflow_status():
    """Legacy fallback implementation for compatibility"""
    from ddd_main_menu import clear_screen, display_header
    
    while True:
        clear_screen()
        display_header()
        print("\nMANAGE PROJECT (JOBS, WORKFLOW, STATUS)")
        print("=" * 45)
        print("Consolidated interface for project management and workflow control")
        print()
        
        try:
            # Import job queue manager to show current status
            sys.path.append('.')
            from job_queue_manager import get_job_queue_manager
            from config import get_capture_directory
            
            job_manager = get_job_queue_manager()
            status = job_manager.get_queue_status()
            capture_folder = get_capture_directory()
            
            # Show current project status
            print("📊 CURRENT PROJECT STATUS:")
            print("=" * 35)
            print(f"   Capture Directory: {capture_folder}")
            print(f"   Jobs in Queue: {status['total_jobs']} total")
            print(f"   Currently Running: {status['running']} jobs")
            print(f"   Waiting: {status['queued']} jobs")
            print(f"   Completed: {status['completed']} jobs")
            print(f"   Failed: {status['failed']} jobs")
            print(f"   Processor Status: {'🟢 Running' if status['processor_running'] else '🔴 Stopped'}")
            print(f"   Max Concurrent: {status['max_concurrent']} jobs")
            
            # Show recent files in capture directory if available
            if os.path.exists(capture_folder):
                try:
                    files = os.listdir(capture_folder)
                    rf_files = [f for f in files if f.lower().endswith(('.lds', '.ldf'))]
                    tbc_files = [f for f in files if f.lower().endswith('.tbc')]
                    audio_files = [f for f in files if f.lower().endswith(('.wav', '.flac'))]
                    video_files = [f for f in files if f.lower().endswith('.mkv')]
                    
                    print(f"\n📁 PROJECT FILES:")
                    print(f"   RF Captures: {len(rf_files)} files")
                    print(f"   TBC Files: {len(tbc_files)} files")
                    print(f"   Audio Files: {len(audio_files)} files")
                    print(f"   Video Files: {len(video_files)} files")
                except Exception:
                    pass
            
        except Exception as e:
            print("📊 PROJECT STATUS: (Job queue system not available)")
            print(f"   Error: {e}")
            # Continue without job queue status
        
        print()
        print("🚀 PROJECT MANAGEMENT OPTIONS:")
        print("=" * 40)
        print("1. Add VHS Decode Jobs to Queue")
        print("2. Add TBC Export Jobs to Queue")
        print("3. View Detailed Job Queue Status")
        print("4. Return to VHS-Decode Menu")
        
        # Import functions here to avoid circular imports
        from ddd_main_menu import add_vhs_decode_jobs_to_queue, add_tbc_export_jobs_to_queue
        from job_queue_display import show_job_queue_display
        
        selection = input("\nSelect option (1-4): ").strip()
        
        if selection == '1':
            add_vhs_decode_jobs_to_queue()
        elif selection == '2':
            add_tbc_export_jobs_to_queue()
        elif selection == '3':
            show_job_queue_display()
        elif selection == '4':
            break  # Return to VHS-Decode menu
        else:
            print("Invalid selection. Please enter 1-4.")
            time.sleep(1)
