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
    COMPLETE = "complete"          # Step finished successfully (file exists, no hash recorded)
    FAILED = "failed"              # Error occurred, needs attention
    VIDEO_ONLY = "video_only"      # No audio present, only video will be processed
    READY = "ready"                # Prerequisites met, can start
    PROCESSING = "processing"      # Currently being processed
    QUEUED = "queued"              # Waiting in job queue
    MISSING = "missing"            # Prerequisites not satisfied
    # Hash / validation states
    HASHING = "hashing"            # A checksum job is currently running for this step's outputs
    VALIDATED = "validated"        # Step complete AND hash recorded AND file size+mtime unchanged
    STALE = "stale"                # Hash recorded but file has changed (size/mtime differs from log)
    INVALID = "invalid"            # Explicit verify revealed a hash mismatch — file may be corrupt
    # Archive staging
    ARCHIVED = "archived"          # Project's intermediate files have been moved into <basename>.intermediate/

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
        'missing': 'bright_black',
        # Hash / validation states
        'hashing': 'bright_cyan',       # rendered with flash by the matrix view
        'validated': 'bright_green',    # subtly brighter than 'complete'
        'stale': 'yellow',              # file changed since last hash
        'invalid': 'bold red',          # explicit verify revealed mismatch
        'archived': 'bright_magenta',   # staged for archive — intermediates moved aside
    }

    # Status descriptions
    STATUS_DESCRIPTIONS = {
        'complete': 'Step finished successfully',
        'failed': 'Error occurred, needs attention',
        'video_only': 'No audio present, only video will be processed',
        'ready': 'Prerequisites met, can start',
        'processing': 'Currently being processed - See Job Status Screen',
        'queued': 'Waiting in job queue',
        'missing': 'Prerequisites not satisfied',
        'hashing': 'Checksum job running for this step\'s outputs',
        'validated': 'Step complete and hash matches recorded value (file unchanged since hash)',
        'stale': 'Hash recorded but file has been modified since (size/mtime differ) — re-hash or verify',
        'invalid': 'Verify revealed a hash mismatch — file may be corrupt',
        'archived': 'Project staged for archive — intermediate files moved into <basename>.intermediate/',
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

        # If this project has been staged for archive (the .intermediate/
        # subfolder exists), every step shows ARCHIVED and we skip the
        # per-step analysis. Without this short-circuit the matrix would
        # incorrectly read missing intermediates (the .tbc, _ffv1.mkv, etc.
        # are inside the subfolder, not at the top level) as "step broken".
        if self._is_project_archived(project):
            for step in WorkflowStep:
                workflow_status.steps[step] = StepStatus.ARCHIVED
            return workflow_status

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

    @staticmethod
    def _is_project_archived(project: Project) -> bool:
        """Check whether the project has been staged for archive — i.e. its
        <basename>.intermediate/ subfolder exists next to the capture files.
        Presence of that folder means the WCC's `stage N` command has moved
        intermediates aside and the project should be displayed as ARCHIVED.
        """
        source_dir = getattr(project, 'source_directory', None)
        name = getattr(project, 'name', None)
        if not source_dir or not name:
            return False
        return os.path.isdir(os.path.join(source_dir, name + '.intermediate'))
    
    def get_step_status(self, step: WorkflowStep, project: Project) -> StepStatus:
        """
        Determine status of individual workflow step
        
        Args:
            step: Workflow step to check
            project: Project to check
            
        Returns:
            StepStatus for the step
        """
        # Priority: Running > Queued > Failed > Hashing > Invalid > Stale > Validated > Complete > Ready > Missing

        # 1. Step itself currently running (decode, compress, etc.)
        if self._is_step_running(step, project):
            return StepStatus.PROCESSING

        # 2. Step itself queued
        if self._is_step_queued(step, project):
            return StepStatus.QUEUED

        # 3. Step failed
        if self._is_step_failed(step, project):
            return StepStatus.FAILED

        # 4. Step's outputs exist? Determine the appropriate post-completion state.
        if self._is_step_complete(step, project):
            # Is a checksum job currently running for this step's outputs?
            if self._is_step_hashing(step, project):
                return StepStatus.HASHING
            # Look at the hash state of the step's tracked outputs
            hash_state = self._get_step_hash_state(step, project)
            if hash_state == 'invalid':
                return StepStatus.INVALID
            if hash_state == 'stale':
                return StepStatus.STALE
            if hash_state == 'validated':
                return StepStatus.VALIDATED
            # 'no-hash' or 'mixed' falls through to plain COMPLETE
            return StepStatus.COMPLETE

        # 5. Ready to start?
        if self._can_step_start(step, project):
            return StepStatus.READY

        # 6. Default: missing prerequisites
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
        """Check if step has failed.

        Looks at the most-recent job for this project + step only. Old failed
        jobs are ignored once a newer attempt (queued/running/completed/cancelled)
        exists, so re-imported captures don't inherit prior failure indicators.
        Use 'clean failed' to wipe stale entries explicitly.
        """
        # If the step has valid output files, any prior failure is moot
        if self._is_step_complete(step, project):
            return False

        if self.job_manager:
            job_type = self._get_job_type_for_step(step)
            if job_type:
                all_jobs = self.job_manager.get_jobs_nonblocking(timeout=0.1)
                if all_jobs is not None:
                    matching = [
                        j for j in all_jobs
                        if j.job_type == job_type and self._is_job_for_project(j, project)
                    ]
                    if matching:
                        latest = max(matching, key=lambda j: j.created_at)
                        # Only treat as failed if the latest attempt failed.
                        # Any newer queued/running/completed/cancelled job hides
                        # earlier failures.
                        if latest.status == JobStatus.FAILED:
                            return True
                        return False

        # No matching jobs at all — fall back to detecting a suspiciously small
        # output file as evidence of a prior failure that left a ghost behind.
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

    def _get_step_tracked_files(self, step: WorkflowStep, project: Project):
        """Return the list of files whose hash state determines this step's
        VALIDATED/STALE/INVALID result. Empty list = no tracked files for this
        step (e.g. DECODE doesn't have a stable single output we track hashes
        for; users care about the .tbc but it's a derivative of the .lds so
        typically only the .tbc.json + capture originals are hashed).
        """
        # capture step: .lds, .flac, .json originals
        if step == WorkflowStep.CAPTURE:
            files = []
            for key in ('video', 'audio'):
                p = project.capture_files.get(key) if hasattr(project, 'capture_files') else None
                if p and os.path.isfile(p):
                    files.append(p)
            # Also the .json metadata if present (derived from video path)
            if hasattr(project, 'capture_files') and 'video' in project.capture_files:
                vp = project.capture_files['video']
                base = vp[:-4] if vp.endswith(('.lds', '.ldf')) else os.path.splitext(vp)[0]
                jp = base + '.json'
                if os.path.isfile(jp):
                    files.append(jp)
            return files
        # compress: the .ldf
        if step == WorkflowStep.COMPRESS:
            p = project.output_files.get('compress') if hasattr(project, 'output_files') else None
            return [p] if p and os.path.isfile(p) else []
        # align: the _aligned audio
        if step == WorkflowStep.ALIGN:
            p = project.output_files.get('align') if hasattr(project, 'output_files') else None
            return [p] if p and os.path.isfile(p) else []
        # export: the _ffv1.mkv
        if step == WorkflowStep.EXPORT:
            p = project.output_files.get('export') if hasattr(project, 'output_files') else None
            return [p] if p and os.path.isfile(p) else []
        # final: the _final.mkv
        if step == WorkflowStep.FINAL:
            p = project.output_files.get('final') if hasattr(project, 'output_files') else None
            return [p] if p and os.path.isfile(p) else []
        # decode: not tracked (intermediate .tbc, regenerable from .lds)
        return []

    def _is_step_hashing(self, step: WorkflowStep, project: Project) -> bool:
        """Check if a checksum job is currently running for this step."""
        if not self.job_manager:
            return False
        running = self.job_manager.get_jobs_nonblocking(JobStatus.RUNNING, timeout=0.1)
        if running is None:
            return False
        # Match by project + step label encoded in job parameters
        for job in running:
            if job.job_type != 'checksum':
                continue
            if not self._is_job_for_project(job, project):
                continue
            job_step = (job.parameters or {}).get('step', '')
            if job_step == step.value:
                return True
        return False

    def _get_step_hash_state(self, step: WorkflowStep, project: Project) -> str:
        """Aggregate hash state across this step's tracked files.

        Returns one of: 'invalid', 'stale', 'validated', 'no-hash', 'mixed'.

        Priority: any 'invalid' → 'invalid'; any 'stale' → 'stale';
        all 'validated' → 'validated'; some validated + some 'no-hash' →
        'mixed' (treated as plain COMPLETE).
        """
        try:
            import validation_log
        except ImportError:
            return 'no-hash'

        files = self._get_step_tracked_files(step, project)
        if not files:
            return 'no-hash'

        log_path = validation_log.get_log_path(files[0])
        states = [validation_log.file_state(p, log_path=log_path) for p in files]

        if 'invalid' in states:
            return 'invalid'
        if 'stale' in states:
            return 'stale'
        if all(s == 'validated' for s in states):
            return 'validated'
        if all(s == 'no-hash' for s in states):
            return 'no-hash'
        return 'mixed'
    
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
            # Requires capture to be complete AND file must be .lds (not already .ldf)
            if not self._is_capture_complete(project):
                return False
            # Only show as ready if capture file is .lds (uncompressed)
            if 'video' in project.capture_files:
                video_file = project.capture_files['video']
                return video_file.endswith('.lds')
            return False
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
        """Check if decode step is complete.

        Beyond file existence + size, also require the most-recent decode
        job (if any is recorded in the queue) to have COMPLETED. A FAILED
        or CANCELLED decode can leave a many-MB partial .tbc behind that
        the bare size check can't distinguish from a real finished decode
        — and a partial like that then incorrectly satisfies prerequisites
        for downstream steps (export, etc.). RUNNING/QUEUED would normally
        be picked up by higher-priority checks in get_step_status, but
        treating them as 'not complete' here is the safer default — the
        file isn't a finished output yet.
        """
        if 'decode' not in project.output_files:
            return False

        tbc_file = project.output_files['decode']
        if not os.path.exists(tbc_file):
            return False

        if os.path.getsize(tbc_file) <= 1024 * 1024:  # Should be at least 1MB
            return False

        if self.job_manager:
            all_jobs = self.job_manager.get_jobs_nonblocking(timeout=0.1)
            if all_jobs is not None:
                matching = [
                    j for j in all_jobs
                    if j.job_type == 'vhs-decode'
                    and self._is_job_for_project(j, project)
                ]
                if matching:
                    latest = max(matching, key=lambda j: j.created_at)
                    if latest.status != JobStatus.COMPLETED:
                        return False

        return True
    
    def _is_compress_complete(self, project: Project) -> bool:
        """Check if compress step is complete (LDS -> LDF compression)"""
        # First check if project discovery found a compress output file
        if 'compress' in project.output_files:
            compress_file = project.output_files['compress']
            if os.path.exists(compress_file):
                compress_size = os.path.getsize(compress_file)
                if compress_size > 1024 * 1024:  # Should be at least 1MB
                    return True

        # Also check directly for .ldf file based on capture file
        if 'video' in project.capture_files:
            video_file = project.capture_files['video']
            if video_file.endswith('.lds'):
                ldf_file = video_file.replace('.lds', '.ldf')
                if os.path.exists(ldf_file):
                    ldf_size = os.path.getsize(ldf_file)
                    if ldf_size > 1024 * 1024:  # Should be at least 1MB
                        return True

        return False
    
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
            WorkflowStep.COMPRESS: "lds-compress",
            WorkflowStep.EXPORT: "tbc-export",
            WorkflowStep.ALIGN: "audio-align",
            WorkflowStep.FINAL: "final-mux",
        }
        return job_type_mapping.get(step)
    
    def _is_job_for_project(self, job: QueuedJob, project: Project) -> bool:
        """Check if a job belongs to a specific project"""
        # Exact match (not substring) so e.g. "Esslemont-Clow" doesn't match
        # "Esslemont-Clow2". Normalize each path to the same basename project
        # discovery would derive from it, so files with extra dotted segments
        # (e.g. "Foo.flac.ldf" → "Foo") still match a project named "Foo".
        project_base = project.name.lower()
        input_basename = self._normalize_to_project_base(job.input_file)
        output_basename = self._normalize_to_project_base(job.output_file)
        return project_base == input_basename or project_base == output_basename

    @staticmethod
    def _normalize_to_project_base(file_path: str) -> str:
        """Reduce a file path to the project basename used by project_discovery.

        Mirrors project_discovery._extract_base_name: strip ALL dotted
        extensions iteratively, then known workflow suffixes. Single-extension
        stripping breaks for inputs like "Ice Skating.flac.ldf", where the
        extra ".flac" segment would otherwise leave the basename stranded.
        """
        name = os.path.basename(file_path).lower()
        while '.' in name:
            name = os.path.splitext(name)[0]
        for suffix in ('_chroma', '_luma', '_aligned', '_ffv1', '_final', '_metadata', '_validation'):
            if name.endswith(suffix):
                name = name[:-len(suffix)]
                break
        return name
    
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
            
        # Hashing is rendered with a 1 Hz flash so the user sees that the
        # validation work is actively running. The flash uses the wall-clock
        # second-bit to alternate between two display states; the calling
        # renderer re-evaluates this every refresh tick.
        if step_status == StepStatus.HASHING:
            import time
            return "Hashing…" if int(time.time()) % 2 == 0 else "Hashing "

        # Standard status display
        status_display = {
            StepStatus.COMPLETE: "Complete",
            StepStatus.FAILED: "Failed",
            StepStatus.VIDEO_ONLY: "Video Only",
            StepStatus.READY: "Ready",
            StepStatus.PROCESSING: "Processing",
            StepStatus.QUEUED: "Queued",
            StepStatus.MISSING: "Missing",
            StepStatus.VALIDATED: "Validated",
            StepStatus.STALE: "Stale",
            StepStatus.INVALID: "INVALID",
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
