#!/usr/bin/env python3
"""
Project Status Display Module
Rich-based interactive display of project workflow status with colored table,
status legend, summary statistics, and interactive controls.
"""

import os
import time
from typing import List, Dict, Optional, Set
from dataclasses import dataclass

try:
    from rich.console import Console
    from rich.table import Table
    from rich.text import Text
    from rich.live import Live
    from rich.panel import Panel
    from rich.columns import Columns
    from rich.align import Align
    from rich.box import HEAVY
    from rich import print as rich_print
except ImportError:
    print("Warning: Rich library not found. Install with: pip install rich")
    # Fallback to simple print
    def rich_print(*args, **kwargs):
        print(*args, **kwargs)

from project_discovery import Project, ProjectDiscovery
from workflow_analyzer import WorkflowAnalyzer, WorkflowStep, StepStatus, WorkflowStatus
from job_queue_manager import JobQueueManager
from shared.progress_display_utils import ProgressDisplayUtils

@dataclass
class DisplayConfig:
    """Configuration for display appearance"""
    project_column_width: int = 20
    step_column_width: int = 11
    auto_refresh_seconds: float = 5.0
    show_legend: bool = True
    show_summary: bool = True
    color_enabled: bool = True

class ProjectStatusDisplay:
    """Rich-based display for project workflow status"""
    
    def __init__(self, discovery: ProjectDiscovery, analyzer: WorkflowAnalyzer, config: DisplayConfig = None):
        """
        Initialize project status display
        
        Args:
            discovery: Project discovery instance
            analyzer: Workflow analyzer instance
            config: Display configuration
        """
        self.discovery = discovery
        self.analyzer = analyzer
        self.config = config or DisplayConfig()
        
        try:
            self.console = Console()
        except:
            self.console = None
        
        # Status colors from analyzer (matches architecture spec)
        self.status_colors = self.analyzer.STATUS_COLORS
        self.status_descriptions = self.analyzer.STATUS_DESCRIPTIONS
    
    def _debug_log(self, message: str):
        """Log debug message to workflow debug log file"""
        from datetime import datetime
        timestamp = datetime.now().strftime('%H:%M:%S')
        try:
            with open('workflow_debug.log', 'a', encoding='utf-8') as f:
                f.write(f"[{timestamp}] PROJECT_STATUS: {message}\n")
        except Exception:
            pass  # Fail silently if logging fails
    
    def create_project_status_table(self, projects: List[Project]) -> Table:
        """
        Create Rich table with colored status indicators
        
        Args:
            projects: List of projects to display
            
        Returns:
            Rich Table object
        """
        # Create table with heavy borders as per architecture
        table = Table(title="PROJECT WORKFLOW STATUS", box=HEAVY, show_header=True)
        
        # Add columns
        table.add_column("Project", width=self.config.project_column_width, style="cyan", no_wrap=True)
        table.add_column("Capture", width=self.config.step_column_width, justify="center")
        table.add_column("Decode", width=self.config.step_column_width, justify="center") 
        table.add_column("Compress", width=self.config.step_column_width, justify="center")
        table.add_column("Export", width=self.config.step_column_width, justify="center")
        table.add_column("Align", width=self.config.step_column_width, justify="center")
        table.add_column("Final", width=self.config.step_column_width, justify="center")
        
        # Add project rows
        for idx, project in enumerate(projects):
            workflow_status = self.analyzer.analyze_project_workflow(project)
            
            # Get status for each step
            steps = [
                WorkflowStep.CAPTURE,
                WorkflowStep.DECODE,
                WorkflowStep.COMPRESS,
                WorkflowStep.EXPORT,
                WorkflowStep.ALIGN,
                WorkflowStep.FINAL
            ]
            
            # Add project number and name (1-indexed)
            project_num = idx + 1
            project_name = f"{project_num}. {project.name}"
            row_data = [project_name]
            
            for step in steps:
                step_status = workflow_status.steps.get(step, StepStatus.MISSING)
                display_text = self.analyzer.get_step_display_status(step_status, project, step)
                
                # Apply color if enabled
                if self.config.color_enabled and self.console:
                    color = self.status_colors.get(step_status.value, 'white')
                    colored_text = Text(display_text, style=color)
                    row_data.append(colored_text)
                else:
                    row_data.append(display_text)
            
            table.add_row(*row_data)
        
        return table
    
    def create_enhanced_status_cell(self, project: Project, step: WorkflowStep, step_status: StepStatus) -> Text:
        """
        Create enhanced status cell with progress bars for running jobs
        
        Args:
            project: Project instance
            step: Workflow step
            step_status: Current status of the step
            
        Returns:
            Rich Text object with enhanced status display
        """
        # Debug logging to file instead of terminal
        debug_enabled = True  # Keep enabled but log to file
        
        if debug_enabled:
            self._debug_log(f"Enhanced cell for {project.name} step {step.value}: status={step_status}, job_manager={self.analyzer.job_manager is not None}")
        
        # First check: If step is complete, always show complete status regardless of job queue
        if step_status == StepStatus.COMPLETE:
            if debug_enabled:
                self._debug_log(f"Step {step.value} for {project.name} is complete - showing complete status")
            return self._create_simple_status_text(step_status, project, step)
        
        # Second check: Only show progress for steps that are actually processing or queued
        if step_status in [StepStatus.PROCESSING, StepStatus.QUEUED] and self.analyzer.job_manager:
            # Get job type mapping for progress extraction
            job_type = self.analyzer._get_job_type_for_step(step)
            
            if debug_enabled:
                self._debug_log(f"Job type for {step.value}: {job_type}")
            
            if job_type:
                try:
                    # Use specific job progress extraction to find the exact job for this project+step cell
                    from shared.progress_display_utils import extract_specific_job_progress_info
                    progress_info = extract_specific_job_progress_info(
                        self.analyzer.job_manager, project.name, job_type)
                    
                    if debug_enabled:
                        self._debug_log(f"Progress info: {progress_info}")
                    
                    if progress_info:
                        if debug_enabled:
                            self._debug_log(f"Creating progress display with {progress_info.get('percentage', 0)}% progress")
                        
                        # Show progress bar for any running job, even at 0%
                        progress_bar = ProgressDisplayUtils.create_progress_bar(
                            progress_info['percentage'], width=11)  # Fit column width
                        
                        # Format FPS if available
                        fps_text = ""
                        if progress_info.get('fps') and progress_info['fps'] > 0:
                            fps_text = f" {progress_info['fps']:.1f}fps"
                        
                        # Calculate ETA if we have enough data
                        eta_text = ""
                        if (progress_info.get('fps') and progress_info['fps'] > 0 and 
                            progress_info.get('percentage', 0) > 0):
                            remaining_percent = 100 - progress_info['percentage']
                            if progress_info.get('runtime_seconds', 0) > 30:  # Only show ETA after 30 seconds
                                eta_seconds = (remaining_percent / progress_info['percentage']) * progress_info['runtime_seconds']
                                if eta_seconds > 0:
                                    eta_text = f"ETA {ProgressDisplayUtils.format_time(int(eta_seconds))}"
                        
                        # For new jobs with no progress yet, show "Starting..." in ETA line
                        if not eta_text and progress_info.get('runtime_seconds', 0) < 30:
                            eta_text = "Starting..."
                        
                        # Assemble multi-line cell (4 lines total for better info display)
                        line1 = Text(progress_bar, style="green")
                        
                        # Second line: percentage
                        percentage_line = f"{progress_info['percentage']:.1f}%"
                        line2 = Text(percentage_line, style="cyan")
                        
                        # Third line: FPS if available
                        if progress_info.get('fps') and progress_info['fps'] > 0:
                            fps_line = f"{progress_info['fps']:.1f}fps"
                            line3 = Text(fps_line, style="bright_green")
                        else:
                            line3 = Text("--fps", style="dim")
                        
                        # Fourth line: ETA if available, otherwise show placeholder
                        if eta_text:
                            line4 = Text(eta_text, style="yellow")
                        else:
                            line4 = Text("ETA: --:--", style="dim")  # Show placeholder for ETA
                        
                        # Create multi-line text with consistent spacing (4 lines)
                        multiline_text = Text()
                        multiline_text.append_text(line1)
                        multiline_text.append("\n")
                        multiline_text.append_text(line2) 
                        multiline_text.append("\n")
                        multiline_text.append_text(line3)
                        multiline_text.append("\n")
                        multiline_text.append_text(line4)
                        
                        return multiline_text
                        
                except Exception as e:
                    if debug_enabled:
                        self._debug_log(f"Exception extracting progress info: {e}")
                    # Fall back to simple status text on error
                    pass
                    
        
        # Return simple status for non-processing states or when no progress data available
        return self._create_simple_status_text(step_status, project, step)
    
    def _create_simple_status_text(self, step_status: StepStatus, project: Project, step: WorkflowStep) -> Text:
        """Create simple status text with color"""
        display_text = self.analyzer.get_step_display_status(step_status, project, step)
        
        # Apply color if enabled
        if self.config.color_enabled:
            color = self.status_colors.get(step_status.value, 'white')
            return Text(display_text, style=color)
        else:
            return Text(display_text)
    
    def create_enhanced_project_status_table(self, projects: List[Project]) -> Table:
        """
        Create enhanced Rich table with multi-line progress cells for running jobs
        
        Args:
            projects: List of projects to display
            
        Returns:
            Rich Table object with enhanced progress display
        """
        # Create table with heavy borders and increased row height
        table = Table(title="WORKFLOW PROGRESSION BY PROJECT", box=HEAVY, show_header=True)
        
        # Add columns with proper sizing for multi-line content
        table.add_column("Project", width=self.config.project_column_width, style="cyan", no_wrap=True)
        table.add_column("(C)apture", width=13, justify="center", no_wrap=False)  # Enable multi-line for progress bars
        table.add_column("(D)ecode", width=13, justify="center", no_wrap=False) 
        table.add_column("Co(m)press", width=13, justify="center", no_wrap=False)
        table.add_column("(E)xport", width=13, justify="center", no_wrap=False)
        table.add_column("(A)lign", width=13, justify="center", no_wrap=False)
        table.add_column("(F)inal", width=13, justify="center", no_wrap=False)
        
        # Add project rows with enhanced status cells
        for idx, project in enumerate(projects):
            workflow_status = self.analyzer.analyze_project_workflow(project)
            
            # Get status for each step
            steps = [
                WorkflowStep.CAPTURE,
                WorkflowStep.DECODE,
                WorkflowStep.COMPRESS,
                WorkflowStep.EXPORT,
                WorkflowStep.ALIGN,
                WorkflowStep.FINAL
            ]
            
            # Add project number and name (1-indexed)
            project_num = idx + 1
            project_name = f"{project_num}. {project.name}"
            row_data = [project_name]
            
            for step in steps:
                step_status = workflow_status.steps.get(step, StepStatus.MISSING)
                
                # Use enhanced status cell for better progress display
                enhanced_cell = self.create_enhanced_status_cell(project, step, step_status)
                row_data.append(enhanced_cell)
            
            table.add_row(*row_data)
        
        return table
    
    def create_status_legend(self) -> Table:
        """
        Create status legend with colors and descriptions
        
        Returns:
            Rich Table with legend
        """
        legend_table = Table(title="Status Legend", show_header=False, box=None, padding=(0, 1))
        legend_table.add_column("Status", style="bold", width=12)
        legend_table.add_column("Description", width=50)
        
        # Add legend entries
        for status_key, description in self.status_descriptions.items():
            if self.config.color_enabled and self.console:
                color = self.status_colors.get(status_key, 'white')
                status_text = Text(status_key.replace('_', ' ').title(), style=color)
            else:
                status_text = status_key.replace('_', ' ').title()
                
            legend_table.add_row(status_text, description)
        
        return legend_table
    
    def calculate_summary_stats(self, projects: List[Project]) -> Dict[str, int]:
        """
        Generate summary statistics for display
        
        Args:
            projects: List of projects to analyze
            
        Returns:
            Dictionary with summary statistics
        """
        stats = {
            'total_projects': len(projects),
            'ready_for_decode': 0,
            'decode_running': 0,
            'decode_failed': 0,
            'complete_workflows': 0,
            'projects_with_issues': 0,
            'ready_for_export': 0,
            'export_running': 0,
        }
        
        for project in projects:
            workflow_status = self.analyzer.analyze_project_workflow(project)
            
            # Check decode status
            decode_status = workflow_status.steps.get(WorkflowStep.DECODE, StepStatus.MISSING)
            if decode_status == StepStatus.READY:
                stats['ready_for_decode'] += 1
            elif decode_status == StepStatus.PROCESSING:
                stats['decode_running'] += 1
            elif decode_status == StepStatus.FAILED:
                stats['decode_failed'] += 1
            
            # Check export status
            export_status = workflow_status.steps.get(WorkflowStep.EXPORT, StepStatus.MISSING)
            if export_status == StepStatus.READY:
                stats['ready_for_export'] += 1
            elif export_status == StepStatus.PROCESSING:
                stats['export_running'] += 1
            
            # Check for complete workflows
            final_status = workflow_status.steps.get(WorkflowStep.FINAL, StepStatus.MISSING)
            if final_status == StepStatus.COMPLETE:
                stats['complete_workflows'] += 1
            
            # Check for any issues (failed steps)
            has_issues = any(status == StepStatus.FAILED 
                           for status in workflow_status.steps.values())
            if has_issues:
                stats['projects_with_issues'] += 1
        
        return stats
    
    def create_summary_panel(self, stats: Dict[str, int]) -> Panel:
        """
        Create summary panel with key statistics
        
        Args:
            stats: Summary statistics
            
        Returns:
            Rich Panel with summary
        """
        summary_parts = []
        
        # Key stats
        summary_parts.append(f"{stats['total_projects']} projects")
        
        if stats['ready_for_decode'] > 0:
            summary_parts.append(f"{stats['ready_for_decode']} ready for decode")
        
        if stats['decode_running'] > 0:
            summary_parts.append(f"{stats['decode_running']} decode running")
        
        if stats['decode_failed'] > 0:
            summary_parts.append(f"{stats['decode_failed']} decode failed")
        
        if stats['complete_workflows'] > 0:
            summary_parts.append(f"{stats['complete_workflows']} complete workflow{'s' if stats['complete_workflows'] != 1 else ''}")
        
        summary_text = " • ".join(summary_parts)
        
        return Panel(
            Align.center(summary_text),
            title="Summary",
            border_style="blue"
        )
    
    def show_project_status_browser(self, directories: List[str], auto_refresh: bool = False) -> None:
        """
        Main interactive browser interface
        
        Args:
            directories: List of directories to scan for projects
            auto_refresh: Whether to auto-refresh the display
        """
        if not self.console:
            self._show_fallback_display(directories)
            return
        
        def create_display():
            """Create the complete display"""
            # Discover projects
            projects = self.discovery.discover_projects(directories)
            
            # Create main table
            status_table = self.create_project_status_table(projects)
            
            # Create summary
            stats = self.calculate_summary_stats(projects)
            summary_panel = self.create_summary_panel(stats)
            
            # Create legend if enabled
            if self.config.show_legend:
                legend = self.create_status_legend()
            else:
                legend = None
            
            # Combine elements
            display_elements = [status_table]
            
            if self.config.show_summary:
                display_elements.append(summary_panel)
            
            if legend:
                display_elements.append(legend)
            
            return display_elements
        
        if auto_refresh:
            # Use Live display for auto-refresh
            try:
                with Live(refresh_per_second=1/self.config.auto_refresh_seconds, console=self.console) as live:
                    while True:
                        display_elements = create_display()
                        
                        # Create a single renderable from multiple elements
                        combined_display = "\n\n".join([
                            self.console.render_str(element) for element in display_elements
                        ])
                        
                        live.update(combined_display)
                        time.sleep(self.config.auto_refresh_seconds)
            except KeyboardInterrupt:
                self.console.print("\n[yellow]Auto-refresh stopped[/yellow]")
        else:
            # Static display
            display_elements = create_display()
            
            for element in display_elements:
                self.console.print(element)
                self.console.print()  # Add spacing
    
    def _show_fallback_display(self, directories: List[str]) -> None:
        """
        Fallback display when Rich is not available
        
        Args:
            directories: List of directories to scan for projects
        """
        print("PROJECT WORKFLOW STATUS")
        print("=" * 80)
        print()
        
        # Discover projects
        projects = self.discovery.discover_projects(directories)
        
        # Table header
        print(f"{'Project':<20} {'Capture':<11} {'Decode':<11} {'Compress':<11} {'Export':<11} {'Align':<11} {'Final':<11}")
        print("-" * 95)
        
        # Project rows
        for idx, project in enumerate(projects):
            workflow_status = self.analyzer.analyze_project_workflow(project)
            
            steps = [
                WorkflowStep.CAPTURE,
                WorkflowStep.DECODE,
                WorkflowStep.COMPRESS,
                WorkflowStep.EXPORT,
                WorkflowStep.ALIGN,
                WorkflowStep.FINAL
            ]
            
            # Add project number and name (1-indexed)
            project_num = idx + 1
            project_name = f"{project_num}. {project.name}"
            row = [project_name[:19]]  # Truncate long names
            
            for step in steps:
                step_status = workflow_status.steps.get(step, StepStatus.MISSING)
                display_text = self.analyzer.get_step_display_status(step_status, project, step)
                row.append(display_text[:10])  # Truncate if needed
            
            print(f"{row[0]:<20} {row[1]:<11} {row[2]:<11} {row[3]:<11} {row[4]:<11} {row[5]:<11} {row[6]:<11}")
        
        # Summary
        print()
        stats = self.calculate_summary_stats(projects)
        summary_parts = [
            f"{stats['total_projects']} projects",
            f"{stats['ready_for_decode']} ready for decode",
            f"{stats['decode_running']} decode running",
            f"{stats['decode_failed']} decode failed",
            f"{stats['complete_workflows']} complete workflow{'s' if stats['complete_workflows'] != 1 else ''}"
        ]
        print("Summary: " + " • ".join(summary_parts))
        
        # Legend
        print()
        print("Status Legend:")
        for status_key, description in self.status_descriptions.items():
            print(f"  {status_key.replace('_', ' ').title():<12} {description}")
    
    def show_project_details(self, project: Project) -> None:
        """
        Show detailed information for a specific project
        
        Args:
            project: Project to show details for
        """
        if not self.console:
            self._show_project_details_fallback(project)
            return
        
        # Create detailed table for project
        detail_table = Table(title=f"Project Details: {project.name}", box=HEAVY)
        detail_table.add_column("Attribute", style="cyan", width=20)
        detail_table.add_column("Value", width=60)
        
        # Basic info
        detail_table.add_row("Name", project.name)
        detail_table.add_row("Directory", project.source_directory)
        
        # Capture files
        detail_table.add_row("", "")  # Separator
        detail_table.add_row("[bold]Capture Files[/bold]", "")
        for file_type, file_path in project.capture_files.items():
            file_name = os.path.basename(file_path)
            file_size = project.file_sizes.get(file_name, 0)
            size_str = self._format_file_size(file_size)
            detail_table.add_row(f"  {file_type.title()}", f"{file_name} ({size_str})")
        
        # Output files
        if project.output_files:
            detail_table.add_row("", "")  # Separator
            detail_table.add_row("[bold]Output Files[/bold]", "")
            for file_type, file_path in project.output_files.items():
                file_name = os.path.basename(file_path)
                file_size = project.file_sizes.get(file_name, 0)
                size_str = self._format_file_size(file_size)
                exists = "✓" if os.path.exists(file_path) else "✗"
                detail_table.add_row(f"  {file_type.title()}", f"{exists} {file_name} ({size_str})")
        
        # Workflow status
        workflow_status = self.analyzer.analyze_project_workflow(project)
        detail_table.add_row("", "")  # Separator
        detail_table.add_row("[bold]Workflow Status[/bold]", "")
        
        for step in WorkflowStep:
            step_status = workflow_status.steps.get(step, StepStatus.MISSING)
            display_text = self.analyzer.get_step_display_status(step_status, project, step)
            
            if self.config.color_enabled:
                color = self.status_colors.get(step_status.value, 'white')
                colored_text = Text(display_text, style=color)
                detail_table.add_row(f"  {step.value.title()}", colored_text)
            else:
                detail_table.add_row(f"  {step.value.title()}", display_text)
        
        self.console.print(detail_table)
    
    def _show_project_details_fallback(self, project: Project) -> None:
        """
        Fallback project details display
        
        Args:
            project: Project to show details for
        """
        print(f"Project Details: {project.name}")
        print("=" * 50)
        print(f"Directory: {project.source_directory}")
        print()
        
        print("Capture Files:")
        for file_type, file_path in project.capture_files.items():
            file_name = os.path.basename(file_path)
            file_size = project.file_sizes.get(file_name, 0)
            size_str = self._format_file_size(file_size)
            print(f"  {file_type.title()}: {file_name} ({size_str})")
        
        if project.output_files:
            print("\nOutput Files:")
            for file_type, file_path in project.output_files.items():
                file_name = os.path.basename(file_path)
                file_size = project.file_sizes.get(file_name, 0)
                size_str = self._format_file_size(file_size)
                exists = "EXISTS" if os.path.exists(file_path) else "MISSING"
                print(f"  {file_type.title()}: {file_name} ({size_str}) - {exists}")
        
        print("\nWorkflow Status:")
        workflow_status = self.analyzer.analyze_project_workflow(project)
        for step in WorkflowStep:
            step_status = workflow_status.steps.get(step, StepStatus.MISSING)
            display_text = self.analyzer.get_step_display_status(step_status, project, step)
            print(f"  {step.value.title()}: {display_text}")
    
    def _format_file_size(self, size_bytes: int) -> str:
        """
        Format file size in human-readable format
        
        Args:
            size_bytes: Size in bytes
            
        Returns:
            Formatted size string
        """
        if size_bytes == 0:
            return "0 B"
        
        units = ['B', 'KB', 'MB', 'GB', 'TB']
        unit_index = 0
        size = float(size_bytes)
        
        while size >= 1024 and unit_index < len(units) - 1:
            size /= 1024
            unit_index += 1
        
        if unit_index == 0:
            return f"{int(size)} {units[unit_index]}"
        else:
            return f"{size:.1f} {units[unit_index]}"

def main():
    """Test the project status display"""
    from job_queue_manager import get_job_queue_manager
    
    # Initialize components
    discovery = ProjectDiscovery()
    job_manager = get_job_queue_manager()
    analyzer = WorkflowAnalyzer(job_manager)
    display = ProjectStatusDisplay(discovery, analyzer)
    
    # Test directories (replace with actual paths)
    directories = ["/path/to/captures"]
    
    print("Testing Project Status Display...")
    print("Press Ctrl+C to exit auto-refresh mode")
    
    try:
        # Show static display first
        display.show_project_status_browser(directories, auto_refresh=False)
        
        # Ask user if they want auto-refresh
        try:
            response = input("\nEnable auto-refresh? (y/n): ")
            if response.lower().startswith('y'):
                display.show_project_status_browser(directories, auto_refresh=True)
        except KeyboardInterrupt:
            pass
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
