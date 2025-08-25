#!/usr/bin/env python3
"""
Test script to verify progress display functionality in enhanced workflow control centre
"""

import sys
import time
from workflow_control_centre import WorkflowControlCentre
from project_status_display import ProjectStatusDisplay, DisplayConfig
from project_discovery import ProjectDiscovery
from workflow_analyzer import WorkflowAnalyzer
from job_queue_manager import get_job_queue_manager
from shared.progress_display_utils import ProgressDisplayUtils

def test_progress_display():
    """Test the progress display components"""
    print("Testing Progress Display Components")
    print("=" * 50)
    
    # Test 1: Progress bar creation
    print("\n1. Testing progress bar creation:")
    for percentage in [0, 25, 50, 75, 100]:
        bar = ProgressDisplayUtils.create_progress_bar(percentage, width=20)
        print(f"   {percentage:3d}%: [{bar}]")
    
    # Test 2: Time formatting
    print("\n2. Testing time formatting:")
    for seconds in [30, 90, 3600, 7325]:
        formatted = ProgressDisplayUtils.format_time(seconds)
        print(f"   {seconds:4d}s: {formatted}")
    
    # Test 3: Job progress extraction
    print("\n3. Testing job progress extraction:")
    job_manager = get_job_queue_manager()
    
    jobs = job_manager.get_jobs()
    print(f"   Total jobs: {len(jobs)}")
    
    running_jobs = [j for j in jobs if 'running' in str(j.status).lower()]
    print(f"   Running jobs: {len(running_jobs)}")
    
    for job in running_jobs[:3]:  # Test first 3 running jobs
        print(f"   Job: {job.job_id} - {job.job_type}")
        print(f"        Status: {job.status}")
        print(f"        Progress: {getattr(job, 'progress', 0)}%")
        
        # Test progress extraction
        progress_info = ProgressDisplayUtils.extract_job_progress_info(
            job_manager, "Metallica1", job.job_type)
        
        if progress_info:
            print(f"        Progress Info: {progress_info}")
        else:
            print(f"        Progress Info: None")
    
    # Test 4: Enhanced status cell creation  
    print("\n4. Testing enhanced status cell creation:")
    try:
        # Initialize components
        discovery = ProjectDiscovery()
        analyzer = WorkflowAnalyzer(job_manager)
        config = DisplayConfig(color_enabled=True)
        display = ProjectStatusDisplay(discovery, analyzer, config)
        
        # Get directories from workflow control centre
        wcc = WorkflowControlCentre()
        directories = wcc.directories
        
        print(f"   Processing directories: {directories}")
        
        # Discover projects
        projects = discovery.discover_projects(directories)
        print(f"   Found {len(projects)} projects")
        
        for project in projects[:2]:  # Test first 2 projects
            print(f"   Project: {project.name}")
            
            # Analyze workflow status
            workflow_status = analyzer.analyze_project_workflow(project)
            
            # Test enhanced cells for each step
            from workflow_analyzer import WorkflowStep, StepStatus
            steps = [WorkflowStep.DECODE, WorkflowStep.EXPORT, WorkflowStep.ALIGN, WorkflowStep.FINAL]
            
            for step in steps:
                step_status = workflow_status.steps.get(step, StepStatus.MISSING)
                
                # Create enhanced cell
                enhanced_cell = display.create_enhanced_status_cell(project, step, step_status)
                
                # Get plain text representation for testing
                try:
                    cell_text = str(enhanced_cell.plain)  # Get plain text from Rich Text object
                except:
                    cell_text = str(enhanced_cell)
                
                # Show summary (first line only to avoid clutter)
                first_line = cell_text.split('\n')[0] if '\n' in cell_text else cell_text
                print(f"      {step.value}: {step_status.value} -> {first_line}")
        
        print("\n5. Enhanced table creation:")
        enhanced_table = display.create_enhanced_project_status_table(projects)
        print(f"   Created enhanced table with {len(enhanced_table.rows)} rows")
        
    except Exception as e:
        print(f"   Error testing enhanced display: {e}")
        import traceback
        traceback.print_exc()
    
    print("\nTest completed!")

if __name__ == "__main__":
    print("\n" + "="*60)
    print("ENHANCED WORKFLOW DISPLAY - PROGRESS DEMO")
    print("="*60)
    print("This demo shows what the display looks like with running jobs:")
    print("• Progress bars with real percentages")
    print("• FPS and ETA information") 
    print("• Multi-line enhanced status cells")
    print("• Color-coded progress indicators")
    print("")
    print("Note: Your current jobs are failing due to full /tmp (100% full)")
    print("Real progress bars will appear when jobs can actually run.")
    print("")
    
    # Show one demo cycle
    import sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from project_status_display import ProjectStatusDisplay
    from project_scanner import ProjectScanner
    
    # Create mock manager with progress
    mock_manager = MockJobManager()
    
    # Monkey patch
    import job_queue_manager
    job_queue_manager._instance = mock_manager
    
    scanner = ProjectScanner()
    projects = scanner.scan_projects()
    display = ProjectStatusDisplay(projects, mock_manager)
    
    print("DEMO: Enhanced layout with progress bars:")
    print("="*50)
    enhanced_output = display.create_enhanced_layout()
    print(enhanced_output)
    
    print("\n" + "="*50)
    print("CURRENT SIMULATED JOBS:")
    print("="*50)
    for job in mock_manager.demo_jobs:
        if job['status'] == 'running':
            prog = job['progress']
            if prog['percentage'] > 0:
                print(f"✓ {job['job_id']}:")
                print(f"    Progress: {prog['percentage']:.1f}%")
                print(f"    Frames: {prog['current_frame']:,}/{prog['total_frames']:,}")
                print(f"    Speed: {prog['fps']:.1f} fps")
                print(f"    ETA: {prog['eta_seconds']:.0f} seconds")
                print()
            else:
                print(f"⏳ {job['job_id']}: Processing... (0%)")
    
    print("\nTo see REAL progress bars:")
    print("1. Clean up /tmp space: sudo rm -rf /tmp/* (as root)")
    print("2. Or configure jobs to use /mnt/nvme2tb instead of /tmp")
    print("3. Start a new export job")
    print("4. Run the workflow control center to see live progress")
    test_progress_display()
