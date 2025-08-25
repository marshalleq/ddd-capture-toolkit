#!/usr/bin/env python3
"""
Test clean command in the live workflow control centre interface
"""

import sys
import os
import time

# Add current directory to path to import our modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_live_clean_command():
    """Test the clean command in the live interface using automation"""
    from workflow_control_centre import WorkflowControlCentre
    
    print("Testing clean command in live workflow control centre interface...")
    
    # Initialize the control centre
    control_centre = WorkflowControlCentre()
    
    # Refresh data to get current projects and jobs
    print("Refreshing project and job data...")
    control_centre.refresh_data()
    
    print(f"Found {len(control_centre.current_projects)} projects")
    print(f"Found {len(control_centre.current_jobs)} active jobs")
    
    if control_centre.current_projects:
        project = control_centre.current_projects[0]
        print(f"Project 1: {project.name}")
    else:
        print("No projects found!")
        return
    
    # Test the clean command directly
    print("\nTesting 'clean 1e' command...")
    control_centre.handle_command("clean 1e")
    print(f"Result message: {control_centre.message}")
    
    # Also test with coordinate command parsing
    print("\nTesting coordinate command parsing...")
    test_commands = ["clean 1e", "clean 2d", "clean 1a"]
    
    for cmd in test_commands:
        print(f"\nTesting command: {cmd}")
        control_centre.handle_command(cmd)
        print(f"Message: {control_centre.message}")
        time.sleep(1)  # Brief pause between commands

if __name__ == "__main__":
    test_live_clean_command()
