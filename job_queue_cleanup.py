#!/usr/bin/env python3
"""
Job Queue Cleanup Utility
Helps clean up failed jobs and reset the job queue state
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path

def load_job_queue(queue_file="config/job_queue.json"):
    """Load the current job queue"""
    if not os.path.exists(queue_file):
        print(f"Job queue file {queue_file} not found.")
        return None
    
    with open(queue_file, 'r') as f:
        return json.load(f)

def save_job_queue(data, queue_file="config/job_queue.json"):
    """Save the job queue"""
    with open(queue_file, 'w') as f:
        json.dump(data, f, indent=2)

def show_job_status(data):
    """Display current job status"""
    print("\n=== Current Job Queue Status ===")
    print(f"Max concurrent jobs: {data.get('max_concurrent_jobs', 'N/A')}")
    print(f"Total jobs: {len(data.get('jobs', []))}")
    
    status_counts = {}
    for job in data.get('jobs', []):
        status = job.get('status', 'unknown')
        status_counts[status] = status_counts.get(status, 0) + 1
    
    for status, count in status_counts.items():
        print(f"  {status}: {count}")
    
    print("\n=== Job Details ===")
    for i, job in enumerate(data.get('jobs', []), 1):
        print(f"{i:2d}. {job['job_id']} | {job['status']} | {job['job_type']} | {job.get('progress', 0):.1f}%")
        print(f"    Input:  {job['input_file']}")
        print(f"    Output: {job['output_file']}")
        if job.get('error_message'):
            print(f"    Error:  {job['error_message']}")
        print()

def cleanup_jobs(data, options):
    """Clean up jobs based on options"""
    original_count = len(data.get('jobs', []))
    jobs_to_keep = []
    
    for job in data.get('jobs', []):
        keep_job = True
        
        if options.get('remove_failed') and job.get('status') == 'failed':
            keep_job = False
            print(f"Removing failed job: {job['job_id']}")
        
        if options.get('remove_completed') and job.get('status') == 'completed':
            keep_job = False
            print(f"Removing completed job: {job['job_id']}")
        
        if options.get('remove_running') and job.get('status') == 'running':
            # Reset running jobs to queued (they were interrupted)
            job['status'] = 'queued'
            job['started_at'] = None
            job['progress'] = 0.0
            print(f"Reset running job to queued: {job['job_id']}")
        
        if keep_job:
            jobs_to_keep.append(job)
    
    data['jobs'] = jobs_to_keep
    removed_count = original_count - len(jobs_to_keep)
    
    if removed_count > 0:
        print(f"\nRemoved {removed_count} jobs from queue.")
    else:
        print("\nNo jobs were removed.")
    
    return data

def fix_stale_running_jobs(data):
    """Fix jobs that are stuck in 'running' state"""
    fixed_count = 0
    
    for job in data.get('jobs', []):
        if job.get('status') == 'running':
            # Check if output file exists and job should be marked completed
            output_file = job.get('output_file', '')
            if output_file and os.path.exists(output_file):
                job['status'] = 'completed'
                job['progress'] = 100.0
                job['completed_at'] = datetime.now().isoformat()
                print(f"Fixed completed job: {job['job_id']} (output file exists)")
                fixed_count += 1
            else:
                # Reset to queued state
                job['status'] = 'queued'
                job['started_at'] = None
                job['progress'] = 0.0
                print(f"Reset stale running job to queued: {job['job_id']}")
                fixed_count += 1
    
    if fixed_count > 0:
        print(f"\nFixed {fixed_count} stale running jobs.")
    
    return data

def main():
    queue_file = "config/job_queue.json"
    
    print("Job Queue Cleanup Utility")
    print("=" * 30)
    
    # Load current queue
    data = load_job_queue(queue_file)
    if not data:
        return
    
    # Show current status
    show_job_status(data)
    
    print("\nCleanup Options:")
    print("1. Remove all failed jobs")
    print("2. Remove all completed jobs") 
    print("3. Fix stale running jobs")
    print("4. Remove failed AND completed jobs")
    print("5. Full cleanup (remove failed/completed, fix running)")
    print("6. Show status only (no changes)")
    print("0. Exit")
    
    try:
        choice = input("\nEnter your choice (0-6): ").strip()
        
        if choice == '0':
            print("Exiting without changes.")
            return
        elif choice == '6':
            print("Status displayed above. No changes made.")
            return
        
        # Create backup
        backup_file = f"{queue_file}.backup.{int(datetime.now().timestamp())}"
        with open(backup_file, 'w') as f:
            json.dump(data, f, indent=2)
        print(f"\nCreated backup: {backup_file}")
        
        # Apply cleanup based on choice
        if choice == '1':
            data = cleanup_jobs(data, {'remove_failed': True})
        elif choice == '2':
            data = cleanup_jobs(data, {'remove_completed': True})
        elif choice == '3':
            data = fix_stale_running_jobs(data)
        elif choice == '4':
            data = cleanup_jobs(data, {'remove_failed': True, 'remove_completed': True})
        elif choice == '5':
            data = cleanup_jobs(data, {'remove_failed': True, 'remove_completed': True, 'remove_running': True})
            data = fix_stale_running_jobs(data)
        else:
            print("Invalid choice.")
            return
        
        # Save updated queue
        save_job_queue(data, queue_file)
        print(f"\nUpdated job queue saved to {queue_file}")
        
        # Show final status
        print("\n=== Updated Status ===")
        show_job_status(data)
        
    except KeyboardInterrupt:
        print("\n\nOperation cancelled.")
    except Exception as e:
        print(f"\nError: {e}")

if __name__ == "__main__":
    main()
