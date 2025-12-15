# Per-Project Export Flags - Implementation Design

## Overview

Add a "Flags" column to the Workflow Control Centre matrix that allows users to configure per-project export flags (such as `--luma-only` for black & white sources). Users press 'X' to open a checkbox dialog where they can toggle various export flags for the selected project.

## User Interface

### Workflow Matrix Display

A new "Flags" column is added to the right side of the workflow matrix:

```
┏━━━━━━━━━━━━━━━━━━┳━━━━━━━━━┳━━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━━┳━━━━━━━━━┳━━━━━━━━━┳━━━━━━━━━┓
┃ Project          ┃ Capture ┃ Decode  ┃ Compress ┃ Export  ┃ Align   ┃ Final   ┃ Flags   ┃
┣━━━━━━━━━━━━━━━━━━╋━━━━━━━━━╋━━━━━━━━━╋━━━━━━━━━━╋━━━━━━━━━╋━━━━━━━━━╋━━━━━━━━━╋━━━━━━━━━┫
┃ 1. Family_Video  ┃ ✓       ┃ Ready   ┃ --       ┃ --      ┃ --      ┃ --      ┃   --    ┃
┃ 2. BW_Recording  ┃ ✓       ┃ Ready   ┃ --       ┃ --      ┃ --      ┃ --      ┃   Yes   ┃
┃ 3. Color_Tape    ┃ ✓       ┃ ✓       ┃ Ready    ┃ --      ┃ --      ┃ --      ┃   --    ┃
┗━━━━━━━━━━━━━━━━━━┻━━━━━━━━━┻━━━━━━━━━┻━━━━━━━━━━┻━━━━━━━━━┻━━━━━━━━━┻━━━━━━━━━┻━━━━━━━━━┛
```

- `--` indicates no flags configured
- `Yes` indicates one or more flags are enabled (displayed in a distinct color, e.g., yellow/orange)

### Flag Configuration Dialog

When user presses 'X' with a project selected, a checkbox dialog appears:

```
┌─ Export Flags: BW_Recording ─────────────────────────────────────┐
│                                                                  │
│  Use arrow keys to navigate, SPACE to toggle, ENTER to save     │
│                                                                  │
│  [X] Luma only (--luma-only)                                     │
│      Output luma (B&W) video only, skip chroma processing        │
│                                                                  │
│  [ ] Letterbox (--letterbox)                                     │
│      Add letterboxing to output                                  │
│                                                                  │
│  [ ] Reverse field order (--reverse)                             │
│      Reverse the field order                                     │
│                                                                  │
│  [ ] Force black & white (--bw)                                  │
│      Force black & white output (different from luma-only)       │
│                                                                  │
│  ─────────────────────────────────────────────────────────────── │
│  [ENTER] Save    [ESC] Cancel                                    │
└──────────────────────────────────────────────────────────────────┘
```

## Available Flags

Initial flags to support (from tbc-video-export help):

| Flag | CLI Option | Description |
|------|------------|-------------|
| `luma_only` | `--luma-only` | Only output luma video (for B&W sources) |
| `letterbox` | `--letterbox` | Add letterboxing to output |
| `reverse` | `--reverse` | Reverse the field order |
| `bw` | `--bw` | Force black & white output |
| `no_dropout_correct` | `--no-dropout-correct` | Disable dropout correction |

Additional flags can be added to the configuration as needed.

## Data Storage

### File Location

Per-project flags stored in: `config/project_flags.json`

### Schema

```json
{
  "version": 1,
  "projects": {
    "BW_Recording": {
      "luma_only": true
    },
    "Another_Project": {
      "letterbox": true,
      "reverse": true
    }
  }
}
```

### Flag Definitions

Flag metadata stored in code (not config) to define available options:

```python
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
    }
}
```

## Implementation Details

### Files to Modify

1. **`project_flags.py`** (NEW)
   - `ProjectFlagsManager` class for loading/saving flags
   - Flag definitions constant
   - Helper functions for flag lookup

2. **`project_status_display.py`**
   - Add "Flags" column to `create_project_status_table()`
   - Add "Flags" column to `create_enhanced_project_status_table()`
   - Add flag status display logic

3. **`workflow_control_centre.py`**
   - Add 'X' key handler in key processing
   - Implement `_show_flags_dialog()` method
   - Integrate with project selection system

4. **`job_queue_manager.py`**
   - Modify `_execute_tbc_export_job()` to read project flags
   - Add flags to export command construction

### New Module: project_flags.py

```python
#!/usr/bin/env python3
"""
Project Flags Manager
Manages per-project export flags configuration.
"""

import os
import json
from typing import Dict, List, Optional
from dataclasses import dataclass

# Flag definitions - CLI options and metadata
EXPORT_FLAGS = {
    'luma_only': {
        'cli_flag': '--luma-only',
        'label': 'Luma only',
        'description': 'Output luma (B&W) video only, skip chroma processing'
    },
    # ... additional flags
}

CONFIG_FILE = 'config/project_flags.json'

class ProjectFlagsManager:
    """Manages per-project export flags"""

    def __init__(self):
        self.config_file = CONFIG_FILE
        self.flags_data = self._load_flags()

    def _load_flags(self) -> Dict:
        """Load flags from config file"""
        ...

    def _save_flags(self) -> None:
        """Save flags to config file"""
        ...

    def get_project_flags(self, project_name: str) -> Dict[str, bool]:
        """Get all flags for a project"""
        ...

    def set_project_flag(self, project_name: str, flag_key: str, enabled: bool) -> None:
        """Set a specific flag for a project"""
        ...

    def has_any_flags(self, project_name: str) -> bool:
        """Check if project has any flags enabled"""
        ...

    def get_cli_flags(self, project_name: str) -> List[str]:
        """Get list of CLI flag strings for a project"""
        ...
```

### Workflow Control Centre Changes

Key handler addition:
```python
elif key.lower() == 'x':
    # Open flags dialog for selected project
    if self.selected_project_idx is not None:
        project = self.current_projects[self.selected_project_idx]
        self._show_flags_dialog(project)
```

Dialog implementation using Rich:
```python
def _show_flags_dialog(self, project: Project) -> None:
    """Show checkbox dialog for export flags"""
    from project_flags import ProjectFlagsManager, EXPORT_FLAGS

    flags_manager = ProjectFlagsManager()
    current_flags = flags_manager.get_project_flags(project.name)

    # Build interactive checkbox UI
    # Handle navigation with arrow keys
    # Toggle with space
    # Save with enter, cancel with escape
    ...
```

### Job Queue Manager Changes

In `_execute_tbc_export_job()`:
```python
# After building base command, add project-specific flags
from project_flags import ProjectFlagsManager

flags_manager = ProjectFlagsManager()
cli_flags = flags_manager.get_cli_flags(job.project_name)
cmd.extend(cli_flags)
```

### Project Status Display Changes

Add column in table creation:
```python
table.add_column("Flags", width=7, justify="center")
```

Add cell data in row building:
```python
# Get flags status
from project_flags import ProjectFlagsManager
flags_manager = ProjectFlagsManager()
has_flags = flags_manager.has_any_flags(project.name)
flags_display = Text("Yes", style="yellow") if has_flags else Text("--", style="bright_black")
row_data.append(flags_display)
```

## Keyboard Controls Summary

| Key | Action |
|-----|--------|
| `X` | Open flags dialog for selected project |
| `↑/↓` | Navigate flags in dialog |
| `SPACE` | Toggle selected flag |
| `ENTER` | Save and close dialog |
| `ESC` | Cancel and close dialog |

## Future Enhancements

1. **Flag presets** - Save named flag combinations (e.g., "B&W Preset")
2. **Bulk flag application** - Apply flags to multiple projects at once
3. **Decode flags** - Extend system to support vhs-decode flags as well
4. **Flag templates** - Auto-detect B&W sources and suggest appropriate flags
5. **Export to Advanced Settings** - Make flags available in menu 2→6 as global defaults

## Testing Plan

1. Create new `config/project_flags.json` with test data
2. Verify "Flags" column appears in workflow matrix
3. Test 'X' key opens dialog for selected project
4. Test flag toggling and persistence
5. Submit export job and verify CLI flags are included
6. Test with actual B&W source using `--luma-only`
