#!/usr/bin/env python3
"""
Project Flags Manager
Manages per-project decode and export flags configuration.
"""

import os
import json
from typing import Dict, List, Optional
from dataclasses import dataclass

# Decode settings. One list for every decoder (see decoder_backends.py): each setting says,
# per decoder, how that decoder takes it:
#   '--flag'      the command-line flag that decoder uses
#   'forced'      that decoder always behaves this way; shown on and locked
#   'structural'  the decoder backend applies it itself (not a plain flag)
#   missing       that decoder does not have it; shown greyed out and not applied
# 'cli_flag' is vhs-decode's spelling, kept for anything that still reads it.
# Flags with 'default': True are enabled by default and can be disabled per-project.
# (vhs-decode does not support --reverse; field order reversal is done during export with
# the 'fix_reverse' export flag, which uses ld-dropout-correct.)
def _decode_flag(vhs, tape, label, description, default=False, **extra):
    engines = {}
    if vhs:
        engines['vhs-decode'] = vhs
    if tape:
        engines['tape-decode'] = tape
    flag = {'cli_flag': vhs, 'engines': engines, 'label': label,
            'description': description, 'default': default}
    flag.update(extra)
    return flag


DECODE_FLAGS = {
    'no_resample': _decode_flag(
        '--no_resample', 'forced', 'No resample', 'Disable resampling', True),
    'ire0_adjust': _decode_flag(
        '--ire0_adjust', '--ire0-adjust', 'IRE0 adjust', 'Adjust black level to IRE 0', True),
    'skip_chroma': _decode_flag(
        '--skip_chroma', 'structural', 'Skip chroma', 'Skip chroma decoding (for B&W sources)'),
    'non_linear_deemphasis': _decode_flag(
        '--non_linear_deemphasis', '--nldeemp', 'Non-linear deemphasis (NLD)',
        'Anti-ringing: clip luma overshoots after demod. Reduces ringing on sharp edges; can soften luma slightly.'),
    'sub_deemphasis': _decode_flag(
        '--sub_deemphasis', '--subdeemp', 'Sub deemphasis (SD)',
        'Anti-ringing: alternative non-linear deemph mechanism. Often cleaner chroma side-effects than NLD on consumer 80s sources.'),
    'high_boost': _decode_flag(
        '--high_boost', '--high-boost', 'High frequency boost',
        'Multiplier for luma HF boost during demod. Default (off) uses the tape-format profile value. Set 0 to disable boost; >1 sharpens (more ringing); <1 softens (less ringing).',
        value_type='float'),
    'sharpness': _decode_flag(
        '--sharpness', '--sharpness', 'Sharpness filter (0-100)',
        'Crude post-demod sharpness filter. Off by default; experiment with low values (10-30) if the picture needs subtle detail enhancement.',
        value_type='int'),
    'nodd': _decode_flag(
        '--nodd', '--no-dod', 'No dropout detect', 'Disable dropout detection'),
    'chroma_trap': _decode_flag(
        '--chroma_trap', '--chroma-trap', 'Chroma trap',
        'Apply a chroma trap to the luma path, removing leftover colour-carrier dots from the luma.'),
    'y_comb': _decode_flag(
        '--y_comb', '--y-comb', 'Luma comb filter',
        'Luma Y comb filtering with the decoder\'s default clamp (1.5 IRE). Can reduce vertical chroma crawl in the luma.'),
    'no_comb': _decode_flag(
        '--no_comb', '--no-comb', 'No chroma comb',
        'Disable the chroma comb filter.'),
    'fm_audio_notch': _decode_flag(
        '--fm_audio_notch', '--fm-audio-notch', 'FM audio notch',
        'Notch out the FM audio carriers from the video signal, which removes wave-like patterns some decks leave.'),
    'enable_dc_offset': _decode_flag(
        '--enable_dc_offset', '--enable-dc-offset', 'DC offset correction',
        'Apply detected RF DC-offset correction to the decoded video.'),
    'disable_phase_correction': _decode_flag(
        '--disable_phase_correction', '--disable-phase-correction', 'No chroma phase correction',
        'Disable chroma phase correction.'),
    'disable_burst_hsync': _decode_flag(
        '--disable_burst_hsync', '--disable-burst-hsync', 'No burst hsync correction',
        'Disable burst-based horizontal sync correction.'),
    'ntscj': _decode_flag(
        '--ntscj', '--ntscj', 'NTSC-J black level',
        'Treat NTSC black level as 0 IRE instead of 7.5 IRE (Japanese NTSC).'),
}


def decode_flag_state(flag_def: Dict, backend_key: str) -> str:
    """'supported', 'forced' or 'unsupported' for the given decoder."""
    spec = flag_def.get('engines', {}).get(backend_key)
    if spec is None:
        return 'unsupported'
    return 'forced' if spec == 'forced' else 'supported'


def decode_flag_option(flag_def: Dict, backend_key: str) -> str:
    """The command-line text the given decoder uses for this setting, for display."""
    spec = flag_def.get('engines', {}).get(backend_key)
    if spec is None:
        return 'not available'
    if spec in ('forced', 'structural'):
        return {'forced': 'always on', 'structural': 'built in'}[spec]
    return spec


# Flag definitions for the lds-compress step (.lds → .ldf).
# These control how the toolkit validates a successful compress; the actual
# ld-compress invocation has no per-project flags currently.
COMPRESS_FLAGS = {
    'flac_integrity_check': {
        'cli_flag': None,  # Internal flag, drives post-compress validation
        'label': 'FLAC integrity check after compress',
        'description': "After compress completes, stream the .ldf through ld-ldf-reader to verify every FLAC frame's CRC decodes cleanly end-to-end. Catches silent partial-compress failures that the basic exit-code check misses. Slow (minutes to tens of minutes depending on capture length) but on by default because losing your source .lds to a bad compress is much worse.",
        'default': True
    },
    'auto_tier3_validate': {
        'cli_flag': None,  # Internal flag, drives post-compress auto-Tier-3
        'label': 'Auto Tier 3 validate after compress (auto-deletable .lds)',
        'description': "Per-project override for the auto Tier 3 validation. SYSTEM DEFAULT IS ON (configure via VHS-Decode menu → Performance Settings → Toggle Auto Tier 3 validate). When on, the toolkit auto-runs Tier 3 (.ldf vs .lds sample-count comparison) immediately after a successful compress — the same check 1mv runs — and on PASS writes the .ldf.validated sidecar that gates safe .lds deletion. Tier 3 is a strict superset of Tier 2 (FLAC integrity), so when active it supersedes 'flac_integrity_check'. If the source .lds is missing when compress finishes, Tier 3 is skipped with a loud warning in the project's _validation.log — there is no silent fallback to a lesser check.",
        'default': None,  # None = inherit the global default (set via Performance Settings)
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
        elif flag_type == 'compress':
            return COMPRESS_FLAGS
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

    def get_decode_args(self, project_name, backend_key: str):
        """
        Decode settings for one decoder: (tokens, structural).

        tokens      command-line arguments in that decoder's own spelling
        structural  keys of settings the decoder backend applies itself (e.g. skip_chroma)
        Settings the decoder does not have are left out; forced ones need no argument.
        project_name None gives the defaults only.
        """
        project_data = self.flags_data.get('projects', {}).get(project_name, {}) if project_name else {}
        stored = project_data.get('decode', {})
        tokens, structural = [], set()
        for key, flag_def in DECODE_FLAGS.items():
            spec = flag_def['engines'].get(backend_key)
            if spec is None or spec == 'forced':
                continue
            setting = stored.get(key, flag_def.get('default', False))
            if flag_def.get('value_type'):
                # a bare on/off toggle has no value to pass; set values in project_flags.json
                if setting is False or setting is None or setting == '' or setting is True:
                    continue
            elif not setting:
                continue
            if spec == 'structural':
                structural.add(key)
                continue
            tokens.append(spec)
            if flag_def.get('value_type'):
                tokens.append(str(setting))
        return tokens, structural

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


def translate_decode_extras(text: str, backend_key: str):
    """
    Free-form decode parameters, written in either decoder's spelling, for one decoder.

    Returns (tokens, structural, problems). A setting the toolkit knows is rewritten into
    the chosen decoder's spelling; one that decoder does not have is a problem. Anything
    else is passed through unchanged for the decoder itself to accept or refuse.
    """
    spellings = {}
    for key, flag_def in DECODE_FLAGS.items():
        for spec in flag_def['engines'].values():
            if spec not in ('forced', 'structural'):
                spellings[spec] = key
    words = (text or '').split()
    tokens, structural, problems = [], set(), []
    i = 0
    while i < len(words):
        word = words[i]
        key = spellings.get(word)
        if key is None:
            tokens.append(word)
            i += 1
            continue
        flag_def = DECODE_FLAGS[key]
        spec = flag_def['engines'].get(backend_key)
        takes_value = bool(flag_def.get('value_type'))
        value = words[i + 1] if takes_value and i + 1 < len(words) else None
        i += 2 if takes_value else 1
        if spec is None:
            problems.append(f"{word} is not available in {backend_key}")
        elif spec == 'structural':
            structural.add(key)
        elif spec != 'forced':
            tokens.append(spec)
            if value is not None:
                tokens.append(value)
    return tokens, structural, problems


def decode_arguments(project_name, backend_key: str, extra_text: str = ''):
    """Everything a decoder is told by the project's decode settings plus free-form
    parameters: (tokens, structural, problems)."""
    tokens, structural = ProjectFlagsManager().get_decode_args(project_name, backend_key)
    extra_tokens, extra_structural, problems = translate_decode_extras(extra_text, backend_key)
    return tokens + extra_tokens, structural | extra_structural, problems


def get_flag_definitions(flag_type: str = 'export') -> Dict:
    """
    Get available flag definitions.

    Args:
        flag_type: 'decode', 'export', 'audio', or 'compress'

    Returns:
        Dictionary of flag definitions
    """
    if flag_type == 'decode':
        return DECODE_FLAGS.copy()
    elif flag_type == 'audio':
        return AUDIO_FLAGS.copy()
    elif flag_type == 'compress':
        return COMPRESS_FLAGS.copy()
    else:
        return EXPORT_FLAGS.copy()
