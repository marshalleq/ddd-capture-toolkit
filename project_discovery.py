#!/usr/bin/env python3
"""
Project Discovery Module
Scans multiple processing directories to identify VHS archival projects by base name
and groups related files together for workflow status analysis.
"""

import os
import json
from datetime import datetime
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Set
from pathlib import Path
import re

@dataclass
class Project:
    """Represents a VHS archival project with related files"""
    name: str                           # Base name (e.g., "Movie_Night_1985")
    source_directory: str               # Directory containing files
    capture_files: Dict[str, str] = field(default_factory=dict)      # video, audio, metadata paths
    output_files: Dict[str, str] = field(default_factory=dict)       # decode, export, align, final paths
    file_sizes: Dict[str, int] = field(default_factory=dict)         # File sizes for validation
    timestamps: Dict[str, datetime] = field(default_factory=dict)    # File creation/modification times
    
    def __post_init__(self):
        """Initialize empty dicts if not provided"""
        if not self.capture_files:
            self.capture_files = {}
        if not self.output_files:
            self.output_files = {}
        if not self.file_sizes:
            self.file_sizes = {}
        if not self.timestamps:
            self.timestamps = {}

@dataclass
class ProjectValidation:
    """Validation results for a project"""
    is_valid: bool
    issues: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    
class ProjectDiscovery:
    """Discovers and analyzes VHS archival projects in directories"""
    
    # File extensions for different types
    RF_EXTENSIONS = {'.lds', '.ldf', '.s16'}  # RF capture files
    AUDIO_EXTENSIONS = {'.wav', '.flac'}       # Audio files
    VIDEO_EXTENSIONS = {'.tbc'}                # TBC files (decoded video)
    EXPORT_EXTENSIONS = {'.mkv', '.mp4', '.avi'} # Exported video files
    METADATA_EXTENSIONS = {'.json', '.txt'}     # Metadata files
    
    def __init__(self):
        """Initialize project discovery"""
        self.projects: List[Project] = []
        
    def discover_projects(self, directories: List[str]) -> List[Project]:
        """
        Scan directories and group related files by base name
        
        Args:
            directories: List of directory paths to scan
            
        Returns:
            List of discovered Project objects
        """
        all_projects = []
        
        for directory in directories:
            if not os.path.exists(directory) or not os.path.isdir(directory):
                continue
                
            directory_projects = self._scan_directory(directory)
            all_projects.extend(directory_projects)
        
        # Remove duplicates (same project name from different directories)
        unique_projects = {}
        for project in all_projects:
            key = f"{project.name}_{project.source_directory}"
            unique_projects[key] = project
            
        self.projects = list(unique_projects.values())
        return self.projects
    
    def _scan_directory(self, directory: str) -> List[Project]:
        """
        Scan a single directory for projects
        
        Args:
            directory: Directory path to scan
            
        Returns:
            List of projects found in directory
        """
        projects = {}
        
        try:
            for filename in os.listdir(directory):
                filepath = os.path.join(directory, filename)
                if not os.path.isfile(filepath):
                    continue
                    
                # Get base name (filename without extension)
                base_name = self._extract_base_name(filename)
                if not base_name:
                    continue
                
                # Create or get project
                if base_name not in projects:
                    projects[base_name] = Project(
                        name=base_name,
                        source_directory=directory
                    )
                
                project = projects[base_name]
                
                # Categorize file by extension and naming pattern
                self._categorize_file(project, filename, filepath)
        
        except PermissionError:
            print(f"Warning: Permission denied accessing directory {directory}")
        except Exception as e:
            print(f"Error scanning directory {directory}: {e}")
            
        return list(projects.values())
    
    def _extract_base_name(self, filename: str) -> Optional[str]:
        """
        Extract base project name from filename
        
        Args:
            filename: Name of the file
            
        Returns:
            Base name or None if not a relevant file
        """
        # Skip obviously non-project files first
        skip_patterns = [
            r'^\..*',           # Hidden files (._filename)
            r'.*_temp.*',       # Temporary files
            r'.*_backup.*',     # Backup files
            r'^log.*',          # Log files
            r'^config.*',       # Config files
        ]
        
        for pattern in skip_patterns:
            if re.match(pattern, filename, re.IGNORECASE):
                return None
        
        # Remove all extensions first (handles .tbc.json, etc.)
        name_without_ext = filename
        while '.' in name_without_ext:
            name_without_ext = os.path.splitext(name_without_ext)[0]
        
        # Handle workflow output suffixes - ordered from most specific to least specific
        workflow_suffixes = [
            '_chroma',          # TBC chroma decode
            '_luma',            # TBC luma decode  
            '_aligned',         # Audio alignment output
            '_ffv1',            # FFV1 export
            '_final',           # Final muxed output
            '_metadata',        # Metadata files
        ]
        
        base_name = name_without_ext
        
        # Remove workflow suffixes
        for suffix in workflow_suffixes:
            if base_name.endswith(suffix):
                base_name = base_name[:-len(suffix)]
                break
        
        # Handle compressed TBC files
        if base_name.endswith('.compressed'):
            base_name = base_name[:-len('.compressed')]
        
        return base_name if base_name else None
    
    def _categorize_file(self, project: Project, filename: str, filepath: str):
        """
        Categorize a file and add it to the appropriate project category
        
        Args:
            project: Project to add file to
            filename: Name of the file
            filepath: Full path to the file
        """
        file_ext = os.path.splitext(filename)[1].lower()
        file_size = os.path.getsize(filepath)
        file_mtime = datetime.fromtimestamp(os.path.getmtime(filepath))
        
        # Store file size and timestamp
        project.file_sizes[filename] = file_size
        project.timestamps[filename] = file_mtime
        
        # Categorize by extension and naming patterns
        if file_ext in self.RF_EXTENSIONS:
            project.capture_files['video'] = filepath
        elif file_ext in self.AUDIO_EXTENSIONS and not filename.endswith('_aligned.wav'):
            project.capture_files['audio'] = filepath
        elif filename.endswith('_aligned.wav'):
            project.output_files['align'] = filepath
        elif file_ext == '.tbc':
            # Skip chroma TBC files - these are handled internally by tbc-video-export
            if '_chroma.tbc' in filename:
                return  # Don't process chroma TBC files at all
            elif '.compressed' in filename:
                project.output_files['compress'] = filepath
            else:
                project.output_files['decode'] = filepath
        elif file_ext in self.EXPORT_EXTENSIONS:
            if '_final' in filename:
                project.output_files['final'] = filepath
            else:
                project.output_files['export'] = filepath
        elif file_ext in self.METADATA_EXTENSIONS:
            project.capture_files['metadata'] = filepath
    
    def get_project_base_names(self, directory: str) -> Set[str]:
        """
        Extract unique base names from files in directory
        
        Args:
            directory: Directory to scan
            
        Returns:
            Set of unique base names found
        """
        base_names = set()
        
        try:
            for filename in os.listdir(directory):
                if os.path.isfile(os.path.join(directory, filename)):
                    base_name = self._extract_base_name(filename)
                    if base_name:
                        base_names.add(base_name)
        except (PermissionError, FileNotFoundError):
            pass
            
        return base_names
    
    def validate_project_files(self, project: Project) -> ProjectValidation:
        """
        Verify file integrity and detect corruption
        
        Args:
            project: Project to validate
            
        Returns:
            ProjectValidation object with results
        """
        validation = ProjectValidation(is_valid=True)
        
        # Check if video capture file exists
        if 'video' not in project.capture_files:
            validation.issues.append("No video capture file (.lds) found")
            validation.is_valid = False
        else:
            video_file = project.capture_files['video']
            if not os.path.exists(video_file):
                validation.issues.append(f"Video file missing: {video_file}")
                validation.is_valid = False
            else:
                # Check minimum file size (RF files should be large)
                video_size = project.file_sizes.get(os.path.basename(video_file), 0)
                if video_size < 1024 * 1024:  # Less than 1MB is suspicious
                    validation.warnings.append(f"Video file suspiciously small: {video_size} bytes")
        
        # Check audio file if present
        if 'audio' in project.capture_files:
            audio_file = project.capture_files['audio']
            if not os.path.exists(audio_file):
                validation.issues.append(f"Audio file missing: {audio_file}")
                validation.is_valid = False
        
        # Check TBC file if present
        if 'decode' in project.output_files:
            tbc_file = project.output_files['decode']
            if not os.path.exists(tbc_file):
                validation.issues.append(f"TBC file missing: {tbc_file}")
                validation.is_valid = False
            else:
                # TBC files should also be reasonably large
                tbc_size = project.file_sizes.get(os.path.basename(tbc_file), 0)
                if tbc_size < 1024 * 1024:  # Less than 1MB is suspicious
                    validation.warnings.append(f"TBC file suspiciously small: {tbc_size} bytes")
        
        # Check exported video files if present
        for output_type in ['export', 'final']:
            if output_type in project.output_files:
                output_file = project.output_files[output_type]
                if not os.path.exists(output_file):
                    validation.issues.append(f"{output_type.title()} file missing: {output_file}")
                    validation.is_valid = False
        
        return validation
    
    def get_project_statistics(self) -> Dict[str, int]:
        """
        Get statistics about discovered projects
        
        Returns:
            Dictionary with project statistics
        """
        stats = {
            'total_projects': len(self.projects),
            'with_video_capture': 0,
            'with_audio_capture': 0,
            'with_decoded_video': 0,
            'with_exported_video': 0,
            'with_aligned_audio': 0,
            'complete_workflows': 0,
            'video_only_projects': 0,
        }
        
        for project in self.projects:
            if 'video' in project.capture_files:
                stats['with_video_capture'] += 1
                
            if 'audio' in project.capture_files:
                stats['with_audio_capture'] += 1
            else:
                stats['video_only_projects'] += 1
                
            if 'decode' in project.output_files:
                stats['with_decoded_video'] += 1
                
            if 'export' in project.output_files:
                stats['with_exported_video'] += 1
                
            if 'align' in project.output_files:
                stats['with_aligned_audio'] += 1
                
            # Complete workflow: has video, decode, export, and either no audio or aligned audio
            has_video = 'video' in project.capture_files
            has_decode = 'decode' in project.output_files
            has_export = 'export' in project.output_files
            audio_complete = ('audio' not in project.capture_files or 
                            'align' in project.output_files)
            
            if has_video and has_decode and has_export and audio_complete:
                if 'final' in project.output_files:
                    stats['complete_workflows'] += 1
        
        return stats

def main():
    """Test the project discovery system"""
    discovery = ProjectDiscovery()
    
    # Example usage
    directories = ["/path/to/captures"]  # Replace with actual directories
    projects = discovery.discover_projects(directories)
    
    print(f"Found {len(projects)} projects:")
    for project in projects:
        print(f"\nProject: {project.name}")
        print(f"  Directory: {project.source_directory}")
        print(f"  Capture files: {list(project.capture_files.keys())}")
        print(f"  Output files: {list(project.output_files.keys())}")
        
        validation = discovery.validate_project_files(project)
        if not validation.is_valid:
            print(f"  Issues: {validation.issues}")
        if validation.warnings:
            print(f"  Warnings: {validation.warnings}")
    
    stats = discovery.get_project_statistics()
    print(f"\nProject Statistics:")
    for key, value in stats.items():
        print(f"  {key}: {value}")

if __name__ == "__main__":
    main()
