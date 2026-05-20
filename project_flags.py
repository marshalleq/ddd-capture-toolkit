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
# Note: vhs-decode does NOT support --reverse. Field order reversal must be done
# during export using the 'fix_reverse' export flag (which uses ld-dropout-correct).
# Flags with 'default': True are enabled by default and can be disabled per-project.
DECODE_FLAGS = {
    'no_resample': {
        'cli_flag': '--no_resample',
        'label': 'No resample',
        'description': 'Disable resampling',
        'default': True
    },
    'recheck_phase': {
        'cli_flag': '--recheck_phase',
        'label': 'Recheck phase',
        'description': 'Recheck phase on every frame',
        'default': True
    },
    'ire0_adjust': {
        'cli_flag': '--ire0_adjust',
        'label': 'IRE0 adjust',
        'description': 'Adjust black level to IRE 0',
        'default': True
    },
    'skip_chroma': {
        'cli_flag': '--skip_chroma',
        'label': 'Skip chroma',
        'description': 'Skip chroma decoding (for B&W sources)',
        'default': False
    },
    'non_linear_deemphasis': {
        'cli_flag': '--non_linear_deemphasis',
        'label': 'Non-linear deemphasis (NLD)',
        'description': 'Anti-ringing: clip luma overshoots after demod. Reduces ringing on sharp edges; can soften luma slightly.',
        'default': False
    },
    'sub_deemphasis': {
        'cli_flag': '--sub_deemphasis',
        'label': 'Sub deemphasis (SD)',
        'description': 'Anti-ringing: alternative non-linear deemph mechanism. Often cleaner chroma side-effects than NLD on consumer 80s sources.',
        'default': False
    },
    'high_boost': {
        'cli_flag': '--high_boost',
        'value_type': 'float',
        'label': 'High frequency boost',
        'description': 'Multiplier for luma HF boost during demod. Default (off) uses the tape-format profile value. Set 0 to disable boost; >1 sharpens (more ringing); <1 softens (less ringing).',
        'default': False  # off = use tape-format profile default
    },
    'sharpness': {
        'cli_flag': '--sharpness',
        'value_type': 'int',
        'label': 'Sharpness filter (0-100)',
        'description': 'Crude post-demod sharpness filter. Off by default; experiment with low values (10-30) if the picture needs subtle detail enhancement.',
        'default': False
    },
    'nodd': {
        'cli_flag': '--nodd',
        'label': 'No dropout detect',
        'description': 'Disable dropout detection',
        'default': False
    },
}

# Flag definitions for audio processing (final mux step)
# Controls how audio is processed when muxing video and audio together.
#
# The system-wide defaults live in config.json under performance_settings:
#   - default_audio_resample_rate (default '96000')
#   - default_audio_format (default 'flac')
# These per-project flags override the system defaults when set.
AUDIO_FLAGS = {
    'resample_target': {
        'cli_flag': None,  # Internal flag, not a CLI passthrough
        'value_type': 'choice',
        'choices': ['none', '48000', '96000', '192000'],
        'label': 'Resample target rate',
        'description': "Per-project override of the resample rate. SYSTEM DEFAULT IS 96000 (configure via VHS-Decode menu → Performance Settings → Audio Resample Rate). Off (no value) uses the system default. Values: 'none' keeps clockgen-Lite native 78125 Hz; '96000' is the closest standard above 78125 and is recommended.",
        'default': False
    },
    'audio_format': {
        'cli_flag': None,
        'value_type': 'choice',
        'choices': ['flac', 'wav'],
        'label': 'Audio format override',
        'description': "Per-project override of the audio codec. SYSTEM DEFAULT IS flac (configure via VHS-Decode menu → Performance Settings → Audio Format). Off (no value) uses the system default. Values: 'flac' is lossless+compressed (no size limit); 'wav' is lossless+uncompressed (classic 4 GB limit).",
        'default': False
    },
    # ---- Legacy boolean flags ----
    # Kept for backwards compatibility with projects that set them explicitly
    # (e.g. HongKong_Fixed_Audio sets output_wav=true). DO NOT default these to
    # True — that previously caused every project to silently override the
    # system defaults configured in Performance Settings. For new projects use
    # resample_target / audio_format above.
    'resample_48k': {
        'cli_flag': None,
        'label': 'Force 48kHz (legacy)',
        'description': 'Legacy override forcing 48kHz resample. SYSTEM DEFAULT IS 96000 — enabling this downsamples below the captured 78125 Hz, which loses data. Prefer resample_target above. Only honoured if explicitly set on a project.',
        'default': False
    },
    'output_wav': {
        'cli_flag': None,
        'label': 'Force WAV (legacy)',
        'description': 'Legacy override forcing WAV output. SYSTEM DEFAULT IS flac. Prefer audio_format above. Only honoured if explicitly set on a project.',
        'default': False
    },
}

# Flag definitions for tbc-video-export (export step)
# All export flags default to False (off).
EXPORT_FLAGS = {
    'luma_only': {
        'cli_flag': '--luma-only',
        'label': 'Luma only',
        'description': 'Output luma (B&W) video only, skip chroma processing',
        'default': False
    },
    'letterbox': {
        'cli_flag': '--letterbox',
        'label': 'Letterbox',
        'description': 'Add letterboxing to output',
        'default': False
    },
    'field_order_bff': {
        'cli_flag': '--field-order',
        'cli_value': 'bff',
        'label': 'Reverse fields (fast, metadata only)',
        'description': 'Tag output as BFF so players/NLEs present fields in correct order. No temp file, works with dropout correction.',
        'default': False
    },
    'fix_reverse': {
        'cli_flag': '--reverse',
        'label': 'Reverse fields (slow, rewrites file)',
        'description': 'Byte-level field-order swap via ld-dropout-correct pre-pass. Creates temp file ~size of source. Use only if a downstream tool ignores BFF metadata.',
        'default': False
    },
    'bw': {
        'cli_flag': '--bw',
        'label': 'Force B&W',
        'description': 'Force black & white output',
        'default': False
    },
    'no_dropout_correct': {
        'cli_flag': '--no-dropout-correct',
        'label': 'No dropout correction',
        'description': 'Disable dropout correction',
        'default': False
    },
    'chroma_decoder': {
        'cli_flag': '--chroma-decoder',
        'value_type': 'choice',
        'choices': ['PAL2D', 'TRANSFORM2D', 'TRANSFORM3D',
                    'NTSC1D', 'NTSC2D', 'NTSC3D', 'NTSC3DNOADAPT'],
        'label': 'Chroma decoder override',
        'description': 'Override the chroma decoder. Default (off) uses PAL2D for PAL S-Video / NTSC2D for NTSC S-Video. TRANSFORM2D/3D give cleaner chroma in some cases but can expose mottling in saturated reds.',
        'default': False
    },
    'chroma_gain': {
        'cli_flag': '--chroma-gain',
        'value_type': 'float',
        'label': 'Chroma gain multiplier',
        'description': 'Pre-encoding chroma gain. Default (off) uses 1.0. Saturation tweaks are usually better done in your NLE / colour grader; this is useful mainly for normalising saturation across decoder comparisons.',
        'default': False
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
        elif flag_type == 'audio':
            return AUDIO_FLAGS
        else:
            raise ValueError(f"Unknown flag type: {flag_type}")

    def get_project_flags(self, project_name: str, flag_type: str = 'export') -> Dict[str, bool]:
        """
        Get all flags for a project of a specific type.

        Args:
            project_name: Name of the project
            flag_type: 'decode' or 'export'

        Returns:
            Dictionary of flag_key -> enabled status (considering defaults)
        """
        flag_defs = self._get_flag_defs(flag_type)
        project_data = self.flags_data.get('projects', {}).get(project_name, {})
        type_flags = project_data.get(flag_type, {})

        # Return all flags with their effective state (explicit setting or default)
        result = {}
        for flag_key, flag_def in flag_defs.items():
            default_value = flag_def.get('default', False)
            # If explicitly set in config, use that; otherwise use default
            if flag_key in type_flags:
                result[flag_key] = type_flags[flag_key]
            else:
                result[flag_key] = default_value
        return result

    def set_project_flags(self, project_name: str, flags: Dict[str, bool], flag_type: str = 'export') -> None:
        """
        Set multiple flags for a project at once.

        Only stores flags that differ from their default values.
        - For default=False flags: stores True if enabled
        - For default=True flags: stores False if disabled

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

        # Build the new flags dict with only non-default values
        non_default_flags = {}
        for flag_key, enabled in flags.items():
            if flag_key not in flag_defs:
                continue
            default_value = flag_defs[flag_key].get('default', False)
            # Only store if different from default
            if enabled != default_value:
                non_default_flags[flag_key] = enabled

        if non_default_flags:
            self.flags_data['projects'][project_name][flag_type] = non_default_flags
        else:
            # Remove flag type entry if all flags are at defaults
            self.flags_data['projects'][project_name].pop(flag_type, None)
            # Clean up empty project entries
            if not self.flags_data['projects'][project_name]:
                del self.flags_data['projects'][project_name]

        self._save_flags()

    def has_any_flags(self, project_name: str, flag_type: str = None) -> bool:
        """
        Check if project has any flags that differ from defaults.

        This returns True only when flags have been explicitly changed from their
        default values. Flags at their default state do not count.

        Args:
            project_name: Name of the project
            flag_type: 'decode', 'export', 'audio', or None for any type

        Returns:
            True if any flags differ from their defaults
        """
        project_data = self.flags_data.get('projects', {}).get(project_name, {})

        if flag_type:
            # Check only the specified type - if there's any stored data, it means non-default
            return bool(project_data.get(flag_type, {}))
        else:
            # Check all types - stored data means non-default
            return (bool(project_data.get('decode', {})) or
                    bool(project_data.get('export', {})) or
                    bool(project_data.get('audio', {})))

    def get_cli_flags(self, project_name: str, flag_type: str = 'export') -> List[str]:
        """
        Get list of CLI flag strings for a project.

        Returns all flags that should be enabled, considering:
        - Default-on flags (unless explicitly disabled)
        - Explicitly enabled flags

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
        for flag_key, flag_def in flag_defs.items():
            value_type = flag_def.get('value_type', 'bool')
            default = flag_def.get('default', False)

            # Per-project setting overrides the schema default
            setting = type_flags.get(flag_key, default)

            cli_flag = flag_def.get('cli_flag')
            if not cli_flag:
                continue  # internal-only flag (no CLI passthrough)

            if value_type == 'bool':
                # Binary toggle. Static cli_value (if any) is the second arg.
                if setting:
                    cli_flags.append(cli_flag)
                    static_value = flag_def.get('cli_value')
                    if static_value is not None:
                        cli_flags.append(str(static_value))
            else:
                # Value-bearing flag (float / int / choice). The setting is the
                # value to pass; False/None/empty disables. A bare True from a
                # toggle UI without a value is treated as "no-op" rather than
                # emitting an invalid 'True' argument — set the value in
                # project_flags.json directly (e.g. "high_boost": 1.5).
                if setting is False or setting is None or setting == '' or setting is True:
                    continue
                cli_flags.append(cli_flag)
                cli_flags.append(str(setting))
        return cli_flags

    def get_enabled_flag_labels(self, project_name: str, flag_type: str = 'export') -> List[str]:
        """
        Get list of human-readable labels for enabled flags.

        Returns labels for all enabled flags, considering defaults.

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
        for flag_key, flag_def in flag_defs.items():
            default_value = flag_def.get('default', False)
            # Check explicit setting, fall back to default
            if flag_key in type_flags:
                enabled = type_flags[flag_key]
            else:
                enabled = default_value

            if enabled:
                labels.append(flag_def['label'])
        return labels


def get_flag_definitions(flag_type: str = 'export') -> Dict:
    """
    Get available flag definitions.

    Args:
        flag_type: 'decode', 'export', or 'audio'

    Returns:
        Dictionary of flag definitions
    """
    if flag_type == 'decode':
        return DECODE_FLAGS.copy()
    elif flag_type == 'audio':
        return AUDIO_FLAGS.copy()
    else:
        return EXPORT_FLAGS.copy()
