#!/usr/bin/env python3
"""
Test the updated clean command with improved diagnostics
"""

import sys
import os

# Add current directory to path to import our modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_clean_with_diagnostics():
    """Test the clean command with the new diagnostic features"""
    from workflow_control_centre import WorkflowControlCentre
    
    print("Testing clean command with improved diagnostics...")
    
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
    
    # Test the clean command with the new diagnostics
    print("\n=== TESTING CLEAN 1E COMMAND ===")
    control_centre.handle_command("clean 1e")
    print(f"Result message: {control_centre.message}")
    
    # Test clean command for a project/step with no matches (should show diagnostic)
    print("\n=== TESTING CLEAN 2D COMMAND (should show diagnostic) ===")
    control_centre.handle_command("clean 2d")
    print(f"Result message: {control_centre.message}")
    
    # Test clean command for invalid step 
    print("\n=== TESTING CLEAN 1X COMMAND (invalid step) ===")
    control_centre.handle_command("clean 1x")
    print(f"Result message: {control_centre.message}")

if __name__ == "__main__":
    test_clean_with_diagnostics()
