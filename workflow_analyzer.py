#!/usr/bin/env python3
"""
Workflow Status Analyzer
Determines status of each workflow step by analyzing files and job queue state.
Integrates with the job queue system to prevent duplicates and show real-time progress.
"""

import os
from enum import Enum
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Set
from datetime import datetime

from project_discovery import Project, ProjectDiscovery
from job_queue_manager import JobQueueManager, JobStatus, QueuedJob

class WorkflowStep(Enum):
    """Workflow steps in the VHS archival process"""
    CAPTURE = "capture"
    DECODE = "decode"
    COMPRESS = "compress"
    EXPORT = "export"
    ALIGN = "align"
    FINAL = "final"

class StepStatus(Enum):
    """Status of individual workflow steps"""
    COMPLETE = "complete"          # Step finished successfully
    FAILED = "failed"              # Error occurred, needs attention
    VIDEO_ONLY = "video_only"      # No audio present, only video will be processed
    READY = "ready"                # Prerequisites met, can start
    PROCESSING = "processing"      # Currently being processed
    QUEUED = "queued"              # Waiting in job queue
    MISSING = "missing"            # Prerequisites not satisfied

@dataclass
class WorkflowStatus:
    """Complete workflow status for a project"""
    project_name: str
    steps: Dict[WorkflowStep, StepStatus] = field(default_factory=dict)
    step_details: Dict[WorkflowStep, str] = field(default_factory=dict)  # Additional info/error messages
    
    def __post_init__(self):
        """Initialize empty dicts if not provided"""
        if not self.steps:
            self.steps = {}
        if not self.step_details:
            self.step_details = {}

class WorkflowAnalyzer:
    """Analyzes project workflow status including job queue integration"""
    
    # Status colors for display (matches architecture spec)
    STATUS_COLORS = {
        'complete': 'green',
        'failed': 'red', 
        'video_only': 'orange3',
        'ready': 'white',
        'processing': 'blue',
        'queued': 'bright_black',
        'missing': 'bright_black'
    }
    
    # Status descriptions
    STATUS_DESCRIPTIONS = {
        'complete': 'Step finished successfully',
        'failed': 'Error occurred, needs attention',
        'video_only': 'No audio present, only video will be processed',
        'ready': 'Prerequisites met, can start',
        'processing': 'Currently being processed - See Job Status Screen',
        'queued': 'Waiting in job queue',
        'missing': 'Prerequisites not satisfied'
    }
    
    def __init__(self, job_manager: Optional[JobQueueManager] = None):
        """
        Initialize workflow analyzer
        
        Args:
            job_manager: Optional job queue manager for status integration
        """
        self.job_manager = job_manager
        
    def analyze_project_workflow(self, project: Project) -> WorkflowStatus:
        """
        Analyze all workflow steps for a project
        
        Args:
            project: Project to analyze
            
        Returns:
            WorkflowStatus with status of all steps
        """
        workflow_status = WorkflowStatus(project_name=project.name)
        
        # Analyze each workflow step
        for step in WorkflowStep:
            step_status = self.get_step_status(step, project)
            workflow_status.steps[step] = step_status
            
            # Add details for failed/processing steps
            if step_status == StepStatus.FAILED:
                workflow_status.step_details[step] = self._get_failure_reason(step, project)
            elif step_status == StepStatus.PROCESSING:
                workflow_status.step_details[step] = "Processing..."
                
        return workflow_status
    
    def get_step_status(self, step: WorkflowStep, project: Project) -> StepStatus:
        """
        Determine status of individual workflow step
        
        Args:
            step: Workflow step to check
            project: Project to check
            
        Returns:
            StepStatus for the step
        """
        # Priority order as per architecture: Running > Queued > Failed > Complete > Ready > Missing
        
        # 1. Check if processing/running
        if self._is_step_running(step, project):
            return StepStatus.PROCESSING
            
        # 2. Check if queued
        if self._is_step_queued(step, project):
            return StepStatus.QUEUED
            
        # 3. Check if failed
        if self._is_step_failed(step, project):
            return StepStatus.FAILED
            
        # 4. Check if complete
        if self._is_step_complete(step, project):
            return StepStatus.COMPLETE
            
        # 5. Check if ready to start
        if self._can_step_start(step, project):
            return StepStatus.READY
            
        # 6. Default to missing prerequisites
        return StepStatus.MISSING
    
    def _is_step_running(self, step: WorkflowStep, project: Project) -> bool:
        """Check if step is currently running via job queue"""
        if not self.job_manager:
            return False
            
        job_type = self._get_job_type_for_step(step)
        if not job_type:
            return False
            
        # Use non-blocking method with timeout to avoid UI freezing
        running_jobs = self.job_manager.get_jobs_nonblocking(JobStatus.RUNNING, timeout=0.1)
        if running_jobs is None:
            # Job manager is busy - return False to avoid blocking UI
            return False
            
        for job in running_jobs:
            if (job.job_type == job_type and 
                self._is_job_for_project(job, project)):
                return True
        return False
    
    def _is_step_queued(self, step: WorkflowStep, project: Project) -> bool:
        """Check if step is queued via job queue"""
        if not self.job_manager:
            return False
            
        job_type = self._get_job_type_for_step(step)
        if not job_type:
            return False
            
        # Use non-blocking method with timeout to avoid UI freezing
        queued_jobs = self.job_manager.get_jobs_nonblocking(JobStatus.QUEUED, timeout=0.1)
        if queued_jobs is None:
            # Job manager is busy - return False to avoid blocking UI
            return False
            
        for job in queued_jobs:
            if (job.job_type == job_type and 
                self._is_job_for_project(job, project)):
                return True
        return False
    
    def _is_step_failed(self, step: WorkflowStep, project: Project) -> bool:
        """Check if step has failed"""
        # First check if step is actually complete with valid output files
        # If files exist and are valid, ignore old failed jobs
        if self._is_step_complete(step, project):
            return False
        
        # Check job queue for failed jobs only if step is not actually complete
        if self.job_manager:
            job_type = self._get_job_type_for_step(step)
            if job_type:
                # Use non-blocking method with timeout to avoid UI freezing
                failed_jobs = self.job_manager.get_jobs_nonblocking(JobStatus.FAILED, timeout=0.1)
                if failed_jobs is not None:  # Only process if we got a response
                    for job in failed_jobs:
                        if (job.job_type == job_type and 
                            self._is_job_for_project(job, project)):
                            return True
        
        # Check for suspicious output files (exist but too small)
        expected_file = self._get_expected_output_file(step, project)
        if expected_file and os.path.exists(expected_file):
            file_size = os.path.getsize(expected_file)
            if file_size < 1024:  # Less than 1KB is suspicious
                return True
                
        return False
    
    def _is_step_complete(self, step: WorkflowStep, project: Project) -> bool:
        """Check if step is complete"""
        if step == WorkflowStep.CAPTURE:
            return self._is_capture_complete(project)
        elif step == WorkflowStep.DECODE:
            return self._is_decode_complete(project)
        elif step == WorkflowStep.COMPRESS:
            return self._is_compress_complete(project)
        elif step == WorkflowStep.EXPORT:
            return self._is_export_complete(project)
        elif step == WorkflowStep.ALIGN:
            return self._is_align_complete(project)
        elif step == WorkflowStep.FINAL:
            return self._is_final_complete(project)
        return False
    
    def _can_step_start(self, step: WorkflowStep, project: Project) -> bool:
        """Check if step prerequisites are satisfied"""
        return self.check_prerequisites(step, project)
    
    def check_prerequisites(self, step: WorkflowStep, project: Project) -> bool:
        """
        Verify if step prerequisites are satisfied
        
        Args:
            step: Workflow step to check
            project: Project to check
            
        Returns:
            True if prerequisites are satisfied
        """
        if step == WorkflowStep.CAPTURE:
            # Capture has no prerequisites (it's the starting point)
            return True
        elif step == WorkflowStep.DECODE:
            # Requires video capture to be complete
            return self._is_capture_complete(project)
        elif step == WorkflowStep.COMPRESS:
            # Requires decode to be complete
            return self._is_decode_complete(project)
        elif step == WorkflowStep.EXPORT:
            # Requires decode to be complete
            return self._is_decode_complete(project)
        elif step == WorkflowStep.ALIGN:
            # Requires capture complete and audio file present
            return (self._is_capture_complete(project) and 
                   'audio' in project.capture_files)
        elif step == WorkflowStep.FINAL:
            # Requires export complete AND (no audio OR align complete)
            export_complete = self._is_export_complete(project)
            audio_complete = ('audio' not in project.capture_files or 
                            self._is_align_complete(project))
            return export_complete and audio_complete
        return False
    
    def _is_capture_complete(self, project: Project) -> bool:
        """Check if capture step is complete"""
        # Must have video file, audio is optional
        has_video = ('video' in project.capture_files and 
                    os.path.exists(project.capture_files['video']))
        
        if not has_video:
            return False
            
        # Check file size is reasonable (RF files should be large)
        video_file = project.capture_files['video']
        video_size = os.path.getsize(video_file)
        if video_size < 1024 * 1024:  # Less than 1MB is suspicious
            return False
            
        return True
    
    def _is_decode_complete(self, project: Project) -> bool:
        """Check if decode step is complete"""
        if 'decode' not in project.output_files:
            return False
            
        tbc_file = project.output_files['decode']
        if not os.path.exists(tbc_file):
            return False
            
        # Check file size is reasonable
        tbc_size = os.path.getsize(tbc_file)
        return tbc_size > 1024 * 1024  # Should be at least 1MB
    
    def _is_compress_complete(self, project: Project) -> bool:
        """Check if compress step is complete (placeholder for future)"""
        if 'compress' not in project.output_files:
            return False
            
        compress_file = project.output_files['compress']
        if not os.path.exists(compress_file):
            return False
            
        # Check file size is reasonable
        compress_size = os.path.getsize(compress_file)
        return compress_size > 1024 * 1024  # Should be at least 1MB
    
    def _is_export_complete(self, project: Project) -> bool:
        """Check if export step is complete"""
        # First check if project discovery found an export file
        if 'export' in project.output_files:
            export_file = project.output_files['export']
            if os.path.exists(export_file):
                export_size = os.path.getsize(export_file)
                if export_size > 1024 * 1024:  # Should be at least 1MB
                    return True
        
        # If not found by project discovery, check expected file names
        # based on workflow control centre naming convention
        if 'decode' in project.output_files:
            tbc_file = project.output_files['decode']
            if os.path.exists(tbc_file):
                # Generate expected export filename
                base_name = os.path.splitext(os.path.basename(tbc_file))[0]
                expected_export = os.path.join(os.path.dirname(tbc_file), f"{base_name}_ffv1.mkv")
                if os.path.exists(expected_export):
                    export_size = os.path.getsize(expected_export)
                    if export_size > 1024 * 1024:  # Should be at least 1MB
                        return True
        
        # Also try based on capture files if decode info not available
        if 'video' in project.capture_files:
            rf_file = project.capture_files['video']
            if rf_file.endswith('.ldf'):
                base_name = os.path.splitext(os.path.basename(rf_file))[0]
                tbc_file = os.path.join(os.path.dirname(rf_file), f"{base_name}.tbc")
                if os.path.exists(tbc_file):
                    tbc_base_name = os.path.splitext(os.path.basename(tbc_file))[0]
                    expected_export = os.path.join(os.path.dirname(tbc_file), f"{tbc_base_name}_ffv1.mkv")
                    if os.path.exists(expected_export):
                        export_size = os.path.getsize(expected_export)
                        if export_size > 1024 * 1024:  # Should be at least 1MB
                            return True
        
        return False
    
    def _is_align_complete(self, project: Project) -> bool:
        """Check if align step is complete"""
        # Only applicable if audio capture exists
        if 'audio' not in project.capture_files:
            return True  # N/A for video-only projects
            
        if 'align' not in project.output_files:
            return False
            
        align_file = project.output_files['align']
        if not os.path.exists(align_file):
            return False
            
        # Check file size is reasonable
        align_size = os.path.getsize(align_file)
        return align_size > 1024  # Should be at least 1KB for audio
    
    def _is_final_complete(self, project: Project) -> bool:
        """Check if final step is complete"""
        if 'final' not in project.output_files:
            return False
            
        final_file = project.output_files['final']
        if not os.path.exists(final_file):
            return False
            
        # Check file size is reasonable
        final_size = os.path.getsize(final_file)
        return final_size > 1024 * 1024  # Should be at least 1MB
    
    def _get_job_type_for_step(self, step: WorkflowStep) -> Optional[str]:
        """Get job type string for workflow step"""
        job_type_mapping = {
            WorkflowStep.DECODE: "vhs-decode",
            WorkflowStep.EXPORT: "tbc-export",
            WorkflowStep.ALIGN: "audio-align",
            WorkflowStep.FINAL: "final-mux",
        }
        return job_type_mapping.get(step)
    
    def _is_job_for_project(self, job: QueuedJob, project: Project) -> bool:
        """Check if a job belongs to a specific project"""
        # Simple check: see if project name is in input/output file paths
        project_base = project.name.lower()
        input_file = os.path.basename(job.input_file).lower()
        output_file = os.path.basename(job.output_file).lower()
        
        return project_base in input_file or project_base in output_file
    
    def _get_expected_output_file(self, step: WorkflowStep, project: Project) -> Optional[str]:
        """Get expected output file path for a workflow step"""
        if step == WorkflowStep.DECODE:
            return project.output_files.get('decode')
        elif step == WorkflowStep.COMPRESS:
            return project.output_files.get('compress')
        elif step == WorkflowStep.EXPORT:
            return project.output_files.get('export')
        elif step == WorkflowStep.ALIGN:
            return project.output_files.get('align')
        elif step == WorkflowStep.FINAL:
            return project.output_files.get('final')
        return None
    
    def _get_failure_reason(self, step: WorkflowStep, project: Project) -> str:
        """Get reason for step failure"""
        # Check job queue for error messages
        if self.job_manager:
            job_type = self._get_job_type_for_step(step)
            if job_type:
                failed_jobs = self.job_manager.get_jobs(JobStatus.FAILED)
                for job in failed_jobs:
                    if (job.job_type == job_type and 
                        self._is_job_for_project(job, project)):
                        return job.error_message if job.error_message else "Job failed"
        
        # Check for file issues
        expected_file = self._get_expected_output_file(step, project)
        if expected_file and os.path.exists(expected_file):
            file_size = os.path.getsize(expected_file)
            if file_size < 1024:
                return f"Output file too small ({file_size} bytes)"
        
        return "Unknown error"
    
    def prevent_duplicate_submission(self, step: WorkflowStep, project: Project) -> bool:
        """
        Check if job already exists in queue for this project/step
        
        Args:
            step: Workflow step to check
            project: Project to check
            
        Returns:
            True if duplicate job exists (should prevent submission)
        """
        if not self.job_manager:
            return False
            
        job_type = self._get_job_type_for_step(step)
        if not job_type:
            return False
        
        # Check for running or queued jobs
        active_jobs = (self.job_manager.get_jobs(JobStatus.RUNNING) + 
                      self.job_manager.get_jobs(JobStatus.QUEUED))
        
        for job in active_jobs:
            if (job.job_type == job_type and 
                self._is_job_for_project(job, project)):
                return True
        return False
    
    def get_step_display_status(self, step_status: StepStatus, project: Project = None, step: WorkflowStep = None) -> str:
        """
        Get display string for step status
        
        Args:
            step_status: Status to display
            project: Optional project for context
            step: Optional step for context
            
        Returns:
            Display string for status
        """
        # Handle special cases
        if (step_status == StepStatus.COMPLETE and step == WorkflowStep.ALIGN and 
            project and 'audio' not in project.capture_files):
            return "N/A"  # No audio to align
            
        if (step_status == StepStatus.COMPLETE and step == WorkflowStep.FINAL and 
            project and 'audio' not in project.capture_files):
            return "Video Only"  # Final output is video-only
            
        # Standard status display
        status_display = {
            StepStatus.COMPLETE: "Complete",
            StepStatus.FAILED: "Failed",
            StepStatus.VIDEO_ONLY: "Video Only",
            StepStatus.READY: "Ready",
            StepStatus.PROCESSING: "Processing",
            StepStatus.QUEUED: "Queued",
            StepStatus.MISSING: "Missing"
        }
        
        return status_display.get(step_status, str(step_status.value))

def main():
    """Test the workflow analyzer"""
    from job_queue_manager import get_job_queue_manager
    
    # Initialize components
    discovery = ProjectDiscovery()
    job_manager = get_job_queue_manager()
    analyzer = WorkflowAnalyzer(job_manager)
    
    # Discover projects (replace with actual directories)
    directories = ["/path/to/captures"]
    projects = discovery.discover_projects(directories)
    
    print(f"Analyzing workflow status for {len(projects)} projects:")
    
    for project in projects:
        workflow_status = analyzer.analyze_project_workflow(project)
        
        print(f"\nProject: {project.name}")
        for step in WorkflowStep:
            status = workflow_status.steps.get(step, StepStatus.MISSING)
            display_status = analyzer.get_step_display_status(status, project, step)
            print(f"  {step.value.title()}: {display_status}")
            
            if step in workflow_status.step_details:
                print(f"    Details: {workflow_status.step_details[step]}")

if __name__ == "__main__":
    main()
