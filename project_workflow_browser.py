#!/usr/bin/env python3
"""
Project Workflow Status Browser
Main interface for the Project Workflow Status Browser as specified in the architecture.
Provides project-centric workflow management with horizontal status visualisation.

IMPORTANT: This uses the existing shared components to avoid duplicating functionality:
- project_discovery.py for project detection
- workflow_analyzer.py for status analysis  
- project_status_display.py for Rich-based display
- job_queue_manager.py for job integration
- directory_manager.py for multi-location scanning
"""

import os
import sys
import time
from datetime import datetime
from typing import List, Optional

def show_project_workflow_status():
    """Main Project Workflow Status Browser interface"""
    from ddd_main_menu import clear_screen, display_header
    
    while True:
        clear_screen()
        display_header()
        print("\nPROJECT WORKFLOW STATUS BROWSER")
        print("=" * 45)
        print("Project-centric workflow management with horizontal status visualisation")
        print()
        
        try:
            # Initialize the workflow status browser components
            from project_discovery import ProjectDiscovery
            from workflow_analyzer import WorkflowAnalyzer
            from project_status_display import ProjectStatusDisplay, DisplayConfig
            from job_queue_manager import get_job_queue_manager
            from directory_manager import DirectoryManager
            
            # Get processing locations
            dir_manager = DirectoryManager()
            locations = dir_manager.get_enabled_locations()
            directories = [loc.path for loc in locations if os.path.exists(loc.path)]
            
            if not directories:
                print("⚠️  No processing locations configured or available.")
                print("\nPlease configure processing locations first:")
                print("   Main Menu → Configuration → Manage Processing Locations")
                print()
                print("Options:")
                print("1. Configure Processing Locations")
                print("2. Return to VHS-Decode Menu")
                
                choice = input("\nSelect option (1-2): ").strip()
                if choice == '1':
                    _configure_processing_locations()
                    continue
                else:
                    break
            
            # Initialize components using existing shared modules
            discovery = ProjectDiscovery()
            job_manager = get_job_queue_manager()
            analyzer = WorkflowAnalyzer(job_manager)
            
            # Configure display for retro terminal aesthetic as per architectural principles
            display_config = DisplayConfig(
                project_column_width=20,
                step_column_width=11,
                auto_refresh_seconds=5.0,
                show_legend=True,
                show_summary=True,
                color_enabled=True
            )
            
            display = ProjectStatusDisplay(discovery, analyzer, display_config)
            
            print(f"Scanning {len(directories)} processing location{'s' if len(directories) != 1 else ''}...")
            print("\nProject Workflow Status:")
            print()
            
            # Show the project status browser using existing display component
            display.show_project_status_browser(directories, auto_refresh=False)
            
            print("\n" + "=" * 80)
            print("\nPROJECT WORKFLOW BROWSER OPTIONS:")
            print("=" * 40)
            print("1. 🔄 Refresh Project Status")
            print("2. 🎯 Batch Operations Menu")
            print("3. 📊 View Project Details")
            print("4. ⚙️  Filter & Display Options")
            print("5. 📁 Manage Processing Locations")
            print("6. 🚀 Job Queue Management")
            print("7. 🔙 Return to VHS-Decode Menu")
            
            choice = input("\nSelect option (1-7): ").strip()
            
            if choice == '1':
                continue  # Refresh by restarting the loop
            elif choice == '2':
                _show_batch_operations_menu(discovery, analyzer, directories)
            elif choice == '3':
                _show_project_details_menu(discovery, analyzer, display, directories)
            elif choice == '4':
                _show_filter_display_options(display, directories)
            elif choice == '5':
                _configure_processing_locations()
            elif choice == '6':
                from job_queue_display import show_job_queue_display
                show_job_queue_display()
            elif choice == '7':
                break
            else:
                print("Invalid selection. Please enter 1-7.")
                time.sleep(1)
                
        except Exception as e:
            print(f"\n❌ Error initialising Project Workflow Browser: {e}")
            print("\nThis may indicate missing dependencies or configuration issues.")
            print("Please check:")
            print("   • Rich library is installed: pip install rich")
            print("   • Processing locations are configured")
            print("   • Job queue system is accessible")
            print()
            
            choice = input("Press Enter to return to menu or 'r' to retry: ").strip().lower()
            if choice == 'r':
                continue
            else:
                break

def _show_batch_operations_menu(discovery: 'ProjectDiscovery', analyzer: 'WorkflowAnalyzer', directories: List[str]):
    """Show batch operations menu for multiple projects"""
    from ddd_main_menu import clear_screen, display_header
    
    clear_screen()
    display_header()
    print("\nBATCH OPERATIONS MENU")
    print("=" * 25)
    print("Perform operations on multiple projects simultaneously")
    print()
    
    # Discover projects and analyze status
    projects = discovery.discover_projects(directories)
    if not projects:
        print("No projects found to operate on.")
        input("Press Enter to continue...")
        return
    
    # Count projects by status
    ready_decode = []
    ready_export = []
    failed_jobs = []
    
    for project in projects:
        workflow_status = analyzer.analyze_project_workflow(project)
        
        from workflow_analyzer import WorkflowStep, StepStatus
        
        decode_status = workflow_status.steps.get(WorkflowStep.DECODE, StepStatus.MISSING)
        if decode_status == StepStatus.READY:
            ready_decode.append(project)
            
        export_status = workflow_status.steps.get(WorkflowStep.EXPORT, StepStatus.MISSING)
        if export_status == StepStatus.READY:
            ready_export.append(project)
            
        # Check for any failed steps
        has_failures = any(status == StepStatus.FAILED for status in workflow_status.steps.values())
        if has_failures:
            failed_jobs.append(project)
    
    print(f"Available batch operations:")
    print()
    print(f"1. Queue Decode Jobs ({len(ready_decode)} projects ready)")
    print(f"2. Queue Export Jobs ({len(ready_export)} projects ready)")
    print(f"3. Retry Failed Jobs ({len(failed_jobs)} projects with failures)")
    print(f"4. Clean Up Completed Projects")
    print(f"5. Export Project Status Report")
    print(f"6. Return to Browser")
    
    choice = input("\nSelect option (1-6): ").strip()
    
    if choice == '1' and ready_decode:
        _batch_queue_decode_jobs(ready_decode, analyzer)
    elif choice == '2' and ready_export:
        _batch_queue_export_jobs(ready_export, analyzer)
    elif choice == '3' and failed_jobs:
        _batch_retry_failed_jobs(failed_jobs, analyzer)
    elif choice == '4':
        _batch_cleanup_projects(projects)
    elif choice == '5':
        _export_project_report(projects, analyzer)
    elif choice == '6':
        return
    else:
        if choice in ['1', '2', '3']:
            available_counts = [len(ready_decode), len(ready_export), len(failed_jobs)]
            if available_counts[int(choice)-1] == 0:
                print(f"No projects available for this operation.")
            else:
                print("Invalid selection.")
        else:
            print("Invalid selection.")
        time.sleep(2)

def _batch_queue_decode_jobs(projects: List['Project'], analyzer: 'WorkflowAnalyzer'):
    """Queue decode jobs for multiple projects"""
    print(f"\nQueueing decode jobs for {len(projects)} projects:")
    
    for project in projects:
        print(f"   • {project.name}")
    
    confirm = input(f"\nProceed to queue {len(projects)} decode jobs? (y/N): ").strip().lower()
    if confirm in ['y', 'yes']:
        # Use existing job queue functionality
        print("\nAdding jobs to queue...")
        from ddd_main_menu import add_vhs_decode_jobs_to_queue
        add_vhs_decode_jobs_to_queue()
    else:
        print("Operation cancelled.")
    
    input("Press Enter to continue...")

def _batch_queue_export_jobs(projects: List['Project'], analyzer: 'WorkflowAnalyzer'):
    """Queue export jobs for multiple projects"""
    print(f"\nQueueing export jobs for {len(projects)} projects:")
    
    for project in projects:
        print(f"   • {project.name}")
    
    confirm = input(f"\nProceed to queue {len(projects)} export jobs? (y/N): ").strip().lower()
    if confirm in ['y', 'yes']:
        # Use existing job queue functionality
        print("\nAdding jobs to queue...")
        from ddd_main_menu import add_tbc_export_jobs_to_queue
        add_tbc_export_jobs_to_queue()
    else:
        print("Operation cancelled.")
    
    input("Press Enter to continue...")

def _batch_retry_failed_jobs(projects: List['Project'], analyzer: 'WorkflowAnalyzer'):
    """Retry failed jobs for multiple projects"""
    print(f"\nRetrying failed jobs for {len(projects)} projects with failures:")
    
    for project in projects:
        workflow_status = analyzer.analyze_project_workflow(project)
        failed_steps = []
        
        from workflow_analyzer import WorkflowStep, StepStatus
        
        for step, status in workflow_status.steps.items():
            if status == StepStatus.FAILED:
                failed_steps.append(step.value)
        
        if failed_steps:
            print(f"   • {project.name}: {', '.join(failed_steps)}")
    
    confirm = input(f"\nProceed to retry failed jobs? (y/N): ").strip().lower()
    if confirm in ['y', 'yes']:
        print("\n⚠️  Manual job retry not yet implemented.")
        print("Please use the Job Queue Management interface to retry specific jobs.")
    else:
        print("Operation cancelled.")
    
    input("Press Enter to continue...")

def _batch_cleanup_projects(projects: List['Project']):
    """Clean up completed projects"""
    print(f"\nProject cleanup operations:")
    print("\n⚠️  Cleanup operations not yet implemented.")
    print("This feature will help remove temporary files and archive completed projects.")
    input("Press Enter to continue...")

def _export_project_report(projects: List['Project'], analyzer: 'WorkflowAnalyzer'):
    """Export project status report"""
    print(f"\nExporting project status report for {len(projects)} projects...")
    
    try:
        import json
        from datetime import datetime
        
        report_data = {
            'generated_at': datetime.now().isoformat(),
            'total_projects': len(projects),
            'projects': []
        }
        
        for project in projects:
            workflow_status = analyzer.analyze_project_workflow(project)
            
            project_data = {
                'name': project.name,
                'directory': project.source_directory,
                'capture_files': project.capture_files,
                'output_files': project.output_files,
                'workflow_status': {step.value: status.value for step, status in workflow_status.steps.items()}
            }
            
            report_data['projects'].append(project_data)
        
        # Generate filename with timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        report_filename = f"project_status_report_{timestamp}.json"
        
        with open(report_filename, 'w') as f:
            json.dump(report_data, f, indent=2)
        
        print(f"\n✅ Report exported to: {report_filename}")
        print(f"   Contains status for {len(projects)} projects")
        
    except Exception as e:
        print(f"\n❌ Error exporting report: {e}")
    
    input("Press Enter to continue...")

def _show_project_details_menu(discovery: 'ProjectDiscovery', analyzer: 'WorkflowAnalyzer', 
                               display: 'ProjectStatusDisplay', directories: List[str]):
    """Show detailed information for selected projects"""
    from ddd_main_menu import clear_screen, display_header
    
    projects = discovery.discover_projects(directories)
    if not projects:
        print("No projects found.")
        input("Press Enter to continue...")
        return
    
    clear_screen()
    display_header()
    print("\nPROJECT DETAILS MENU")
    print("=" * 25)
    print(f"Select a project to view detailed information ({len(projects)} projects):")
    print()
    
    # List projects
    for i, project in enumerate(projects, 1):
        workflow_status = analyzer.analyze_project_workflow(project)
        
        # Get a summary status
        from workflow_analyzer import StepStatus
        failed_count = sum(1 for status in workflow_status.steps.values() if status == StepStatus.FAILED)
        complete_count = sum(1 for status in workflow_status.steps.values() if status == StepStatus.COMPLETE)
        
        status_summary = f"{complete_count}/6 complete"
        if failed_count > 0:
            status_summary += f", {failed_count} failed"
        
        print(f"{i:2d}. {project.name[:40]:<40} ({status_summary})")
    
    print(f"{len(projects)+1:2d}. Return to Browser")
    
    try:
        choice = input(f"\nSelect project (1-{len(projects)+1}): ").strip()
        project_index = int(choice) - 1
        
        if 0 <= project_index < len(projects):
            selected_project = projects[project_index]
            
            clear_screen()
            display_header()
            print()
            display.show_project_details(selected_project)
            print()
            input("Press Enter to continue...")
        elif project_index == len(projects):
            return
        else:
            print("Invalid selection.")
            time.sleep(1)
            
    except (ValueError, IndexError):
        print("Invalid selection.")
        time.sleep(1)

def _show_filter_display_options(display: 'ProjectStatusDisplay', directories: List[str]):
    """Show filter and display configuration options"""
    from ddd_main_menu import clear_screen, display_header
    
    clear_screen()
    display_header()
    print("\nFILTER & DISPLAY OPTIONS")
    print("=" * 30)
    print("Configure how project status is displayed")
    print()
    print("Display Options:")
    print(f"1. Show Legend: {'✓' if display.config.show_legend else '✗'}")
    print(f"2. Show Summary: {'✓' if display.config.show_summary else '✗'}")
    print(f"3. Colours Enabled: {'✓' if display.config.color_enabled else '✗'}")
    print(f"4. Auto-refresh: {display.config.auto_refresh_seconds}s")
    print()
    print("Filter Options:")
    print("5. Show All Projects")
    print("6. Show Only Complete Workflows")
    print("7. Show Only Projects with Errors")
    print("8. Show Only Projects Ready for Processing")
    print("9. Show Only Running/Queued Projects")
    print()
    print("10. Enable Auto-refresh Mode")
    print("11. Return to Browser")
    
    choice = input("\nSelect option (1-11): ").strip()
    
    if choice == '1':
        display.config.show_legend = not display.config.show_legend
        print(f"Legend display {'enabled' if display.config.show_legend else 'disabled'}.")
    elif choice == '2':
        display.config.show_summary = not display.config.show_summary
        print(f"Summary display {'enabled' if display.config.show_summary else 'disabled'}.")
    elif choice == '3':
        display.config.color_enabled = not display.config.color_enabled
        print(f"Colour display {'enabled' if display.config.color_enabled else 'disabled'}.")
    elif choice == '4':
        try:
            new_interval = float(input("Enter auto-refresh interval in seconds (1-60): "))
            if 1 <= new_interval <= 60:
                display.config.auto_refresh_seconds = new_interval
                print(f"Auto-refresh interval set to {new_interval}s.")
            else:
                print("Invalid interval. Must be between 1 and 60 seconds.")
        except ValueError:
            print("Invalid input. Please enter a number.")
    elif choice == '10':
        print("\nStarting auto-refresh mode...")
        print("Press Ctrl+C to stop auto-refresh and return to menu.")
        time.sleep(2)
        try:
            display.show_project_status_browser(directories, auto_refresh=True)
        except KeyboardInterrupt:
            print("\nAuto-refresh stopped.")
            time.sleep(1)
    elif choice == '11':
        return
    else:
        print("\n⚠️  Filter options not yet fully implemented.")
        print("Currently showing all projects. Advanced filtering coming soon.")
    
    if choice not in ['10', '11']:
        time.sleep(1)

def _configure_processing_locations():
    """Configure processing locations"""
    from ddd_main_menu import clear_screen, display_header
    
    clear_screen()
    display_header()
    print("\nPROCESSING LOCATIONS CONFIGURATION")
    print("=" * 40)
    print("The Workflow Status Browser scans multiple directories for VHS projects.")
    print("Configure which directories to include in the scan.")
    print()
    
    try:
        from directory_manager import DirectoryManager
        
        dir_manager = DirectoryManager()
        locations = dir_manager.get_all_locations()
        
        if locations:
            print("Current processing locations:")
            for i, location in enumerate(locations, 1):
                status = "✓ Enabled" if location.enabled else "✗ Disabled"
                exists = "(exists)" if os.path.exists(location.path) else "(missing)"
                print(f"{i:2d}. {location.name}: {location.path} {status} {exists}")
        else:
            print("No processing locations configured.")
            
            # Suggest adding the capture directory as a starting point
            from config import get_capture_directory
            capture_dir = get_capture_directory()
            
            print(f"\nWould you like to add your capture directory as a processing location?")
            print(f"Directory: {capture_dir}")
            
            if input("Add capture directory? (Y/n): ").strip().lower() != 'n':
                success = dir_manager.add_location("Capture Directory", capture_dir)
                if success:
                    print(f"✅ Added: {capture_dir}")
                else:
                    print(f"❌ Failed to add directory")
        
        print()
        print("Options:")
        print("1. Add New Location")
        print("2. Remove Location")
        print("3. Toggle Location Enabled/Disabled")
        print("4. Return to Browser")
        
        choice = input("\nSelect option (1-4): ").strip()
        
        if choice == '1':
            name = input("Location name: ").strip()
            path = input("Directory path: ").strip()
            
            if name and path:
                # Expand user paths following architectural principles
                from pathlib import Path
                expanded_path = str(Path(path).expanduser().resolve())
                
                success = dir_manager.add_location(name, expanded_path)
                if success:
                    print(f"✅ Added: {name} → {expanded_path}")
                else:
                    print(f"❌ Failed to add location (may already exist)")
            else:
                print("❌ Name and path are required")
                
        elif choice == '2' and locations:
            try:
                index = int(input(f"Remove location (1-{len(locations)}): ")) - 1
                if 0 <= index < len(locations):
                    location = locations[index]
                    confirm = input(f"Remove '{location.name}'? (y/N): ").strip().lower()
                    if confirm in ['y', 'yes']:
                        success = dir_manager.remove_location(location.path)
                        if success:
                            print(f"✅ Removed: {location.name}")
                        else:
                            print(f"❌ Failed to remove location")
                else:
                    print("❌ Invalid selection")
            except ValueError:
                print("❌ Invalid input")
                
        elif choice == '3' and locations:
            try:
                index = int(input(f"Toggle location (1-{len(locations)}): ")) - 1
                if 0 <= index < len(locations):
                    location = locations[index]
                    # Toggle enabled status (this would need to be implemented in DirectoryManager)
                    print(f"⚠️  Toggle functionality not yet implemented for: {location.name}")
                else:
                    print("❌ Invalid selection")
            except ValueError:
                print("❌ Invalid input")
                
        elif choice == '4':
            return
        else:
            print("❌ Invalid selection")
            
    except Exception as e:
        print(f"❌ Error managing processing locations: {e}")
    
    input("Press Enter to continue...")

if __name__ == "__main__":
    show_project_workflow_status()
