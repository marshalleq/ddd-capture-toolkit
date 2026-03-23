#!/usr/bin/env python3
"""
Debug test for workflow control centre coordinate commands
"""

import sys
sys.path.append('.')

from workflow_control_centre import WorkflowControlCentre

def test_coordinate_command():
    """Test the coordinate command handling directly"""
    print("Testing workflow control centre coordinate command handling...")
    
    try:
        # Create workflow control centre instance
        control_centre = WorkflowControlCentre()
        
        # Initialize data
        control_centre.refresh_data()
        
        print(f"Found {len(control_centre.current_projects)} projects")
        
        if not control_centre.current_projects:
            print("No projects found - cannot test coordinate commands")
            return
        
        project = control_centre.current_projects[0]
        print(f"Testing with project: {project.name}")
        
        if hasattr(project, 'workflow_status'):
            print(f"Workflow status: {project.workflow_status.steps}")
        else:
            print("No workflow status available")
        
        # Find a project with failed export
        failed_project_num = None
        for i, proj in enumerate(control_centre.current_projects):
            if hasattr(proj, 'workflow_status'):
                from workflow_analyzer import WorkflowStep, StepStatus
                export_status = proj.workflow_status.steps.get(WorkflowStep.EXPORT)
                if export_status == StepStatus.FAILED:
                    failed_project_num = i + 1
                    break
        
        if failed_project_num:
            print(f"\nTesting coordinate command '{failed_project_num}e' (Export for Project {failed_project_num} - FAILED status)...")
            control_centre.handle_coordinate_command(failed_project_num, 'e')
        else:
            print("\nTesting coordinate command '1e' (Export for Project 1)...")
            control_centre.handle_coordinate_command(1, 'e')
        
        print(f"Result message: {control_centre.message}")
        
    except Exception as e:
        import traceback
        print(f"Error during test: {e}")
        traceback.print_exc()

if __name__ == '__main__':
    test_coordinate_command()
