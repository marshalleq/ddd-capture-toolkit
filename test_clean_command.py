#!/usr/bin/env python3

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from workflow_control_centre import WorkflowControlCentre

def test_clean_command():
    print("Testing clean command...")
    
    # Initialize workflow control centre
    wcc = WorkflowControlCentre()
    
    # Load data 
    wcc.refresh_data()
    
    print(f"Found {len(wcc.current_projects)} projects")
    print(f"Found {len(wcc.current_jobs)} jobs")
    
    # Test the clean command parsing and handling
    cmd = "clean 1e"
    print(f"\nTesting command: '{cmd}'")
    
    # Check command parsing
    if cmd.startswith('clean ') and len(cmd) >= 8:
        clean_cmd = cmd[6:].strip()
        print(f"Parsed clean_cmd: '{clean_cmd}'")
        if len(clean_cmd) == 2 and clean_cmd[0].isdigit() and clean_cmd[1] in "dcaef":
            project_num = int(clean_cmd[0])
            step_letter = clean_cmd[1]
            print(f"Project: {project_num}, Step: {step_letter}")
            
            # Call the handler directly
            wcc.handle_clean_command(project_num, step_letter)
            print(f"Result message: {wcc.message}")
        else:
            print(f"Invalid clean command format: '{clean_cmd}'")
    else:
        print(f"Command doesn't match clean pattern")

if __name__ == "__main__":
    test_clean_command()
