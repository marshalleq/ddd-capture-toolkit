#!/usr/bin/env python3
"""
Project Flags Manager
Manages per-project decode and export flags configuration.
"""

import os
import json
from typing import Dict, List, Optional
from dataclasses import dataclass

# Flag definitions for vhs-decode (decode step)
DECODE_FLAGS = {
    'skip_chroma': {
        'cli_flag': '--skip_chroma',
        'label': 'Skip chroma',
        'description': 'Skip chroma decoding (for B&W sources)'
    },
    'no_resample': {
        'cli_flag': '--no_resample',
        'label': 'No resample',
        'description': 'Disable resampling (already enabled by default in workflow)'
    },
    'recheck_phase': {
        'cli_flag': '--recheck_phase',
        'label': 'Recheck phase',
        'description': 'Recheck phase on every frame (already enabled by default)'
    },
    'ire0_adjust': {
        'cli_flag': '--ire0_adjust',
        'label': 'IRE0 adjust',
        'description': 'Adjust black level to IRE 0 (already enabled by default)'
    },
    'high_boost': {
        'cli_flag': '--high_boost',
        'label': 'High boost',
        'description': 'Apply high frequency boost filter'
    },
    'nodd': {
        'cli_flag': '--nodd',
        'label': 'No dropout detect',
        'description': 'Disable dropout detection'
    },
}

# Flag definitions for tbc-video-export (export step)
EXPORT_FLAGS = {
    'luma_only': {
        'cli_flag': '--luma-only',
        'label': 'Luma only',
        'description': 'Output luma (B&W) video only, skip chroma processing'
    },
    'letterbox': {
        'cli_flag': '--letterbox',
        'label': 'Letterbox',
        'description': 'Add letterboxing to output'
    },
    'reverse': {
        'cli_flag': '--reverse',
        'label': 'Reverse field order',
        'description': 'Reverse the field order'
    },
    'bw': {
        'cli_flag': '--bw',
        'label': 'Force B&W',
        'description': 'Force black & white output'
    },
    'no_dropout_correct': {
        'cli_flag': '--no-dropout-correct',
        'label': 'No dropout correction',
        'description': 'Disable dropout correction'
    },
    'oftest': {
        'cli_flag': '--oftest',
        'label': 'Odd field first',
        'description': 'Odd field first (TFF) output'
    },
}

CONFIG_FILE = 'config/project_flags.json'


class ProjectFlagsManager:
    """Manages per-project decode and export flags"""

    def __init__(self, config_file: str = None):
        """
        Initialize the flags manager.

        Args:
            config_file: Optional path to config file. Defaults to CONFIG_FILE.
        """
        self.config_file = config_file or CONFIG_FILE
        self.flags_data = self._load_flags()

    def _load_flags(self) -> Dict:
        """Load flags from config file"""
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # Ensure we have the expected structure
                    if 'projects' not in data:
                        data['projects'] = {}
                    return data
            except (json.JSONDecodeError, IOError) as e:
                print(f"Warning: Could not load project flags: {e}")
                return {'version': 1, 'projects': {}}
        return {'version': 1, 'projects': {}}

    def _save_flags(self) -> None:
        """Save flags to config file"""
        # Ensure config directory exists
        config_dir = os.path.dirname(self.config_file)
        if config_dir and not os.path.exists(config_dir):
            os.makedirs(config_dir, exist_ok=True)

        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.flags_data, f, indent=2)
        except IOError as e:
            print(f"Error saving project flags: {e}")

    def _get_flag_defs(self, flag_type: str) -> Dict:
        """Get flag definitions for a type"""
        if flag_type == 'decode':
            return DECODE_FLAGS
        elif flag_type == 'export':
            return EXPORT_FLAGS
        else:
            raise ValueError(f"Unknown flag type: {flag_type}")

    def get_project_flags(self, project_name: str, flag_type: str = 'export') -> Dict[str, bool]:
        """
        Get all flags for a project of a specific type.

        Args:
            project_name: Name of the project
            flag_type: 'decode' or 'export'

        Returns:
            Dictionary of flag_key -> enabled status
        """
        flag_defs = self._get_flag_defs(flag_type)
        project_data = self.flags_data.get('projects', {}).get(project_name, {})
        type_flags = project_data.get(flag_type, {})

        # Return all flags with their current state (default False if not set)
        result = {}
        for flag_key in flag_defs:
            result[flag_key] = type_flags.get(flag_key, False)
        return result

    def set_project_flags(self, project_name: str, flags: Dict[str, bool], flag_type: str = 'export') -> None:
        """
        Set multiple flags for a project at once.

        Args:
            project_name: Name of the project
            flags: Dictionary of flag_key -> enabled status
            flag_type: 'decode' or 'export'
        """
        flag_defs = self._get_flag_defs(flag_type)

        if 'projects' not in self.flags_data:
            self.flags_data['projects'] = {}

        if project_name not in self.flags_data['projects']:
            self.flags_data['projects'][project_name] = {}

        # Build the new flags dict with only enabled flags
        enabled_flags = {k: True for k, v in flags.items() if v and k in flag_defs}

        if enabled_flags:
            self.flags_data['projects'][project_name][flag_type] = enabled_flags
        else:
            # Remove flag type entry if no flags enabled
            self.flags_data['projects'][project_name].pop(flag_type, None)
            # Clean up empty project entries
            if not self.flags_data['projects'][project_name]:
                del self.flags_data['projects'][project_name]

        self._save_flags()

    def has_any_flags(self, project_name: str, flag_type: str = None) -> bool:
        """
        Check if project has any flags enabled.

        Args:
            project_name: Name of the project
            flag_type: 'decode', 'export', or None for any type

        Returns:
            True if any flags are enabled
        """
        project_data = self.flags_data.get('projects', {}).get(project_name, {})

        if flag_type:
            return bool(project_data.get(flag_type, {}))
        else:
            # Check both types
            return bool(project_data.get('decode', {})) or bool(project_data.get('export', {}))

    def get_cli_flags(self, project_name: str, flag_type: str = 'export') -> List[str]:
        """
        Get list of CLI flag strings for a project.

        Args:
            project_name: Name of the project
            flag_type: 'decode' or 'export'

        Returns:
            List of CLI flag strings (e.g., ['--luma-only', '--letterbox'])
        """
        flag_defs = self._get_flag_defs(flag_type)
        project_data = self.flags_data.get('projects', {}).get(project_name, {})
        type_flags = project_data.get(flag_type, {})

        cli_flags = []
        for flag_key, enabled in type_flags.items():
            if enabled and flag_key in flag_defs:
                cli_flags.append(flag_defs[flag_key]['cli_flag'])
        return cli_flags

    def get_enabled_flag_labels(self, project_name: str, flag_type: str = 'export') -> List[str]:
        """
        Get list of human-readable labels for enabled flags.

        Args:
            project_name: Name of the project
            flag_type: 'decode' or 'export'

        Returns:
            List of flag labels (e.g., ['Luma only', 'Letterbox'])
        """
        flag_defs = self._get_flag_defs(flag_type)
        project_data = self.flags_data.get('projects', {}).get(project_name, {})
        type_flags = project_data.get(flag_type, {})

        labels = []
        for flag_key, enabled in type_flags.items():
            if enabled and flag_key in flag_defs:
                labels.append(flag_defs[flag_key]['label'])
        return labels


def get_flag_definitions(flag_type: str = 'export') -> Dict:
    """
    Get available flag definitions.

    Args:
        flag_type: 'decode' or 'export'

    Returns:
        Dictionary of flag definitions
    """
    if flag_type == 'decode':
        return DECODE_FLAGS.copy()
    else:
        return EXPORT_FLAGS.copy()
