#!/usr/bin/env python3
"""
DdD Capture Toolkit - Directory Manager

Manages multiple processing locations for file scanning in the project workflow system.
Allows users to configure which directories should be scanned for VHS archival project files.
"""

import os
import json
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import List, Dict, Optional, Set
from datetime import datetime

@dataclass
class ProcessingLocation:
    """Represents a directory location to scan for project files"""
    name: str                   # User-friendly name
    path: str                   # Absolute directory path
    enabled: bool = True        # Whether to scan this location
    priority: int = 1           # Display priority (1 = highest)
    scan_subdirs: bool = False  # Recursive scanning
    last_scanned: Optional[str] = None  # ISO timestamp of last scan
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialisation"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'ProcessingLocation':
        """Create instance from dictionary"""
        return cls(**data)

class DirectoryManager:
    """Manages processing locations for project discovery"""
    
    def __init__(self, config_file: str = "config/processing_locations.json"):
        self.config_file = config_file
        self.processing_locations: List[ProcessingLocation] = []
        self.load_configuration()
    
    def add_location(self, name: str, path: str, enabled: bool = True, 
                    priority: int = 1, scan_subdirs: bool = False) -> bool:
        """Add a new processing location"""
        try:
            # Validate path
            abs_path = Path(path).resolve()
            if not abs_path.exists():
                print(f"Warning: Directory does not exist: {abs_path}")
                create = input("Create directory? (y/N): ").strip().lower()
                if create in ['y', 'yes']:
                    try:
                        abs_path.mkdir(parents=True, exist_ok=True)
                        print(f"Created directory: {abs_path}")
                    except Exception as e:
                        print(f"Error creating directory: {e}")
                        return False
                else:
                    return False
            
            # Check if location already exists
            for location in self.processing_locations:
                if Path(location.path).resolve() == abs_path:
                    print(f"Location already exists: {location.name} -> {location.path}")
                    return False
            
            # Add new location
            new_location = ProcessingLocation(
                name=name,
                path=str(abs_path),
                enabled=enabled,
                priority=priority,
                scan_subdirs=scan_subdirs
            )
            
            self.processing_locations.append(new_location)
            self.save_configuration()
            print(f"Added processing location: {name} -> {abs_path}")
            return True
            
        except Exception as e:
            print(f"Error adding location: {e}")
            return False
    
    def remove_location(self, path: str) -> bool:
        """Remove a processing location by path"""
        try:
            abs_path = str(Path(path).resolve())
            for i, location in enumerate(self.processing_locations):
                if Path(location.path).resolve() == Path(abs_path):
                    removed = self.processing_locations.pop(i)
                    self.save_configuration()
                    print(f"Removed processing location: {removed.name}")
                    return True
            
            print(f"Location not found: {path}")
            return False
            
        except Exception as e:
            print(f"Error removing location: {e}")
            return False
    
    def update_location(self, path: str, **kwargs) -> bool:
        """Update properties of an existing location"""
        try:
            abs_path = str(Path(path).resolve())
            for location in self.processing_locations:
                if Path(location.path).resolve() == Path(abs_path):
                    for key, value in kwargs.items():
                        if hasattr(location, key):
                            setattr(location, key, value)
                    self.save_configuration()
                    return True
            
            print(f"Location not found: {path}")
            return False
            
        except Exception as e:
            print(f"Error updating location: {e}")
            return False
    
    def get_enabled_locations(self) -> List[ProcessingLocation]:
        """Get all enabled processing locations sorted by priority"""
        enabled = [loc for loc in self.processing_locations if loc.enabled]
        return sorted(enabled, key=lambda x: (x.priority, x.name))
    
    def get_all_locations(self) -> List[ProcessingLocation]:
        """Get all processing locations sorted by priority"""
        return sorted(self.processing_locations, key=lambda x: (x.priority, x.name))
    
    def scan_location(self, location: ProcessingLocation) -> Dict[str, List[str]]:
        """Scan a location for project files and return file listing"""
        try:
            if not location.enabled:
                return {}
            
            path = Path(location.path)
            if not path.exists():
                print(f"Warning: Location does not exist: {path}")
                return {}
            
            files_found = {
                'lds_files': [],
                'tbc_files': [],
                'mkv_files': [],
                'wav_files': [],
                'flac_files': [],
                'json_files': []
            }
            
            # Scan directory (recursively if enabled)
            if location.scan_subdirs:
                pattern = "**/*"
            else:
                pattern = "*"
            
            for file_path in path.glob(pattern):
                if file_path.is_file():
                    suffix = file_path.suffix.lower()
                    relative_path = str(file_path.relative_to(path))
                    
                    if suffix == '.lds':
                        files_found['lds_files'].append(relative_path)
                    elif suffix == '.tbc':
                        files_found['tbc_files'].append(relative_path)
                    elif suffix == '.mkv':
                        files_found['mkv_files'].append(relative_path)
                    elif suffix == '.wav':
                        files_found['wav_files'].append(relative_path)
                    elif suffix == '.flac':
                        files_found['flac_files'].append(relative_path)
                    elif suffix == '.json':
                        files_found['json_files'].append(relative_path)
            
            # Update last scanned timestamp
            location.last_scanned = datetime.now().isoformat()
            self.save_configuration()
            
            return files_found
            
        except Exception as e:
            print(f"Error scanning location {location.name}: {e}")
            return {}
    
    def get_unique_project_names(self) -> Set[str]:
        """Get unique project base names from all enabled locations"""
        project_names = set()
        
        for location in self.get_enabled_locations():
            files_found = self.scan_location(location)
            
            # Extract base names from all file types
            for file_list in files_found.values():
                for file_path in file_list:
                    # Get filename without extension
                    base_name = Path(file_path).stem
                    
                    # Remove common suffixes to get project name
                    for suffix in ['_aligned', '_final', '_compressed']:
                        if base_name.endswith(suffix):
                            base_name = base_name[:-len(suffix)]
                    
                    if base_name:
                        project_names.add(base_name)
        
        return project_names
    
    def save_configuration(self) -> bool:
        """Save configuration to JSON file"""
        try:
            # Ensure config directory exists
            config_path = Path(self.config_file)
            config_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Convert to serialisable format
            config_data = {
                "processing_locations": [loc.to_dict() for loc in self.processing_locations],
                "last_updated": datetime.now().isoformat(),
                "version": "1.0"
            }
            
            with open(self.config_file, 'w') as f:
                json.dump(config_data, f, indent=4)
            
            return True
            
        except Exception as e:
            print(f"Error saving configuration: {e}")
            return False
    
    def load_configuration(self) -> bool:
        """Load configuration from JSON file"""
        try:
            if not Path(self.config_file).exists():
                # First time - create default configuration with capture directory
                self._create_default_configuration()
                return True
            
            with open(self.config_file, 'r') as f:
                config_data = json.load(f)
            
            # Load processing locations
            self.processing_locations = []
            for loc_data in config_data.get("processing_locations", []):
                location = ProcessingLocation.from_dict(loc_data)
                self.processing_locations.append(location)
            
            return True
            
        except Exception as e:
            print(f"Error loading configuration: {e}")
            self._create_default_configuration()
            return False
    
    def _create_default_configuration(self):
        """Create default configuration including capture directory"""
        try:
            # Import config to get current capture directory
            from config import get_capture_directory
            
            capture_dir = get_capture_directory()
            
            # Add capture directory as first processing location
            self.processing_locations = [
                ProcessingLocation(
                    name="Capture Directory",
                    path=capture_dir,
                    enabled=True,
                    priority=1,
                    scan_subdirs=False
                )
            ]
            
            self.save_configuration()
            print(f"Created default configuration with capture directory: {capture_dir}")
            
        except Exception as e:
            print(f"Warning: Could not create default configuration: {e}")
            self.processing_locations = []
    
    def get_configuration_summary(self) -> str:
        """Get formatted summary of current configuration"""
        lines = [
            "PROCESSING LOCATIONS CONFIGURATION",
            "=" * 50
        ]
        
        if not self.processing_locations:
            lines.append("No processing locations configured.")
            return "\n".join(lines)
        
        enabled_count = len(self.get_enabled_locations())
        total_count = len(self.processing_locations)
        
        lines.append(f"Total locations: {total_count} ({enabled_count} enabled)")
        lines.append("")
        
        for i, location in enumerate(self.get_all_locations(), 1):
            status = "ENABLED" if location.enabled else "disabled"
            recursive = " (recursive)" if location.scan_subdirs else ""
            
            lines.append(f"{i}. {location.name} [{status}]")
            lines.append(f"   Path: {location.path}{recursive}")
            lines.append(f"   Priority: {location.priority}")
            
            if location.last_scanned:
                try:
                    last_scan = datetime.fromisoformat(location.last_scanned)
                    lines.append(f"   Last scanned: {last_scan.strftime('%Y-%m-%d %H:%M')}")
                except:
                    lines.append(f"   Last scanned: {location.last_scanned}")
            else:
                lines.append("   Last scanned: Never")
            
            lines.append("")
        
        return "\n".join(lines)

# Convenience functions for external use
_directory_manager = None

def get_directory_manager() -> DirectoryManager:
    """Get singleton directory manager instance"""
    global _directory_manager
    if _directory_manager is None:
        _directory_manager = DirectoryManager()
    return _directory_manager

def get_processing_locations() -> List[ProcessingLocation]:
    """Get all enabled processing locations"""
    return get_directory_manager().get_enabled_locations()

def add_processing_location(name: str, path: str, **kwargs) -> bool:
    """Add a new processing location"""
    return get_directory_manager().add_location(name, path, **kwargs)

if __name__ == "__main__":
    # Quick test
    dm = DirectoryManager()
    print(dm.get_configuration_summary())
