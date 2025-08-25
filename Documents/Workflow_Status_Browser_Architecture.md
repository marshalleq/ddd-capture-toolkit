# Workflow Status Browser Architecture Documentation

## ⚠️ DOCUMENT STATUS: SUPERSEDED

**This document has been superseded by the Job Management System Architecture.**

**Primary functionality (project discovery, status detection, workflow management) has been moved to the Job Management System as it provides a more comprehensive solution.**

**This document now covers only the remaining unique features that may be preserved or integrated.**

---

## Overview

The Workflow Status Browser was originally designed as a project-centric status dashboard. **Most of its core functionality has been moved to the Job Management System.** This document now covers only the specific features that are unique and not covered by the Job Management System.

## Unique Features Remaining

**Note:** Core project discovery, status detection, and workflow management have been moved to the Job Management System.

### Features Unique to Workflow Status Browser

The following features are unique to this implementation and not covered by the Job Management System:

### 1. Processing Locations Management Interface

**Unique Feature:** Dedicated UI for managing multiple processing directories

**Functionality:**
- Add new processing locations with validation
- Remove existing locations with confirmation
- Enable/disable locations without deletion
- Display location status (exists/missing)
- Path expansion and validation
- Configuration persistence

**Implementation:** `_configure_processing_locations()` function in the browser

**Status:** ✅ Implemented and working
**Integration Path:** Could be incorporated into Job Management System Phase 2.4 (Configuration & Settings)

### 2. JSON Status Export Feature

**Unique Feature:** Export project status reports to JSON files

**Functionality:**
- Export complete project status data to timestamped JSON files
- Include project metadata, file paths, workflow status, and generation timestamp
- Useful for external analysis, reporting, or automation integration
- Structured data format for programmatic access

**Implementation:** `_export_project_report()` function

**Status:** ✅ Implemented and working
**Integration Path:** Could be added to Job Management System as an additional feature

### 3. Display Configuration Interface

**Unique Feature:** Granular display customisation options

**Functionality:**
- Toggle status legend on/off
- Toggle summary statistics on/off
- Toggle colour display on/off
- Configurable auto-refresh intervals (1-60 seconds)
- Persistent display preferences

**Implementation:** `_show_filter_display_options()` function

**Status:** ✅ Implemented and working
**Integration Path:** Could be incorporated into Job Management System Phase 2.4 (UI Customization)

## Migration to Job Management System

**The following functionality has been moved to the Job Management System:**

- ❌ **Project Discovery & Grouping** → Job Management System Phase 1.1
- ❌ **Workflow Status Detection** → Job Management System Phase 1.2
- ❌ **Project Status Matrix Display** → Job Management System Phase 1.3
- ❌ **Batch Operations** → Job Management System Phase 1.5
- ❌ **Job Queue Integration** → Job Management System Phase 1.2
- ❌ **Dependency Management** → Job Management System Phase 1.2

**Existing code serves as implementation reference for Job Management System development.**

## Implementation Status

### Completed Unique Features

1. **✅ Processing Locations Management UI**
   - File: `project_workflow_browser.py:_configure_processing_locations()`
   - Fully implemented and working
   - Should be integrated into Job Management System Phase 2.4

2. **✅ JSON Status Export**
   - File: `project_workflow_browser.py:_export_project_report()`
   - Fully implemented and working
   - Should be added to Job Management System as additional feature

3. **✅ Display Configuration Interface**
   - File: `project_workflow_browser.py:_show_filter_display_options()`
   - Fully implemented and working
   - Should be integrated into Job Management System Phase 2.4

## Integration Points

### Menu System Integration

**Main Menu Addition**:
```
VHS-Decode Menu:
1. Add VHS decode jobs to queue
2. Add TBC export jobs to queue  
3. → View Project Workflow Status ← [NEW]
4. View job queue status & progress
5. Configure job queue settings
...
```

**Settings Menu Addition**:
```
Settings Menu:
1. Set Capture Directory
2. → Manage Processing Locations ← [NEW]
3. Configure A/V Settings
...
```

### Job Queue Integration

**Unified Status System**: Project workflow status and job queue status use identical status types and detection logic.

**Prevention of Duplicates**: Before allowing job submission, check if project/step combination already exists in queue.

**Real-time Updates**: Project status display updates automatically as jobs progress in the background.

### Configuration Integration

**Extended config.json**:
```json
{
  "capture_directory": "/path/to/captures",
  "processing_locations": [
    {
      "name": "Primary Captures",
      "path": "/path/to/captures", 
      "enabled": true,
      "priority": 1,
      "scan_subdirs": false
    },
    {
      "name": "Archive Drive",
      "path": "/media/archive/vhs",
      "enabled": true, 
      "priority": 2,
      "scan_subdirs": true
    }
  ]
}
```

## User Experience Flow

### Typical Usage Scenarios

**Scenario 1: New User with Multiple Captures**
1. User accesses "View Project Workflow Status"
2. Sees table showing multiple projects, most at "Ready" for decode
3. Selects "Queue all ready decodes" batch operation
4. Returns to view progress, sees status change to "Queued" then "Running"

**Scenario 2: Managing Mixed-State Projects**
1. User sees overview: some complete, some failed, some in progress
2. Filters to show only failed projects
3. Reviews failed projects, retries selected ones
4. Checks job status screen for detailed error information

**Scenario 3: Multi-Directory Workflow**
1. User adds multiple processing locations in settings
2. Project browser shows combined view of all locations
3. Files from different drives/projects appear together
4. User can process efficiently without moving files

### Interactive Controls

**Table Navigation**:
- Arrow keys for row/column navigation
- Enter to select project for detailed view
- Space for multi-selection checkboxes
- Ctrl+A for select all
- ESC to return to menu

**Batch Operations Menu**:
```
BATCH OPERATIONS:
1. Queue selected projects for decode
2. Queue selected projects for export  
3. Retry all failed jobs
4. Clean up completed projects
5. Export project status report
6. Return to project browser
```

**Filter Options**:
```
FILTER OPTIONS:
1. Show all projects
2. Show only complete workflows
3. Show only projects with errors
4. Show only projects ready for processing
5. Show only running/queued projects
6. Custom filter...
```

## Performance Considerations

### Scanning Optimization

**Caching Strategy**:
- Cache project discovery results for 30 seconds
- Invalidate cache when files change (inotify/file watchers)
- Lazy loading for large directory structures

**Multi-Threading**:
- Scan multiple directories concurrently
- Background status analysis while displaying results
- Non-blocking UI updates

### Memory Management

**Large Project Sets**:
- Pagination for >100 projects
- Lazy loading of detailed file information
- Efficient data structures for status tracking

## Error Handling

### File System Errors

**Missing Directories**: Graceful handling with user notification
**Permission Issues**: Clear error messages with suggested solutions
**Network Drives**: Timeout handling and retry logic
**Corrupted Files**: File validation with recovery suggestions

### Job Queue Integration Errors

**Queue Unavailable**: Fallback to file-based status detection only
**Stale Job Data**: Automatic cleanup and synchronization
**Concurrent Access**: Thread-safe operations and locking

## Future Enhancements

### Phase 1 Extensions (Planned)

**Advanced Filtering**:
- Date range filters (created, modified)
- File size filters (large/small projects)
- Complex multi-criteria filtering

**Enhanced Batch Operations**:
- Conditional operations (if X then Y)
- Scheduling (process at specific times)
- Dependency chains (process A, then B, then C)

### Phase 2 Extensions (Future)

**Project Templates**:
- Save common workflow configurations
- Apply templates to new projects
- Template sharing between users

**Progress Predictions**:
- Estimate completion times based on file sizes
- Historical performance analysis
- Resource usage optimization

**Mobile Companion**:
- Web interface for remote monitoring
- Mobile app for status notifications
- Remote control capabilities

## Development Implementation Plan

### ✅ Phase 1: Core Framework (COMPLETED - 2025-08-10)
1. ✅ Visual design specification (complete)
2. ✅ Create project discovery module (`project_discovery.py`)
3. ✅ Implement workflow status analyzer (`workflow_analyzer.py`)
4. ✅ Build Rich-based status display (`project_status_display.py`)
5. ✅ Integrate with existing job queue system

**Implementation Details:**
- **Main Interface**: `project_workflow_browser.py` - Complete browser implementation
- **Menu Integration**: VHS-Decode Menu → "Manage Project (jobs, workflow, status)"
- **Status Detection**: Full workflow analysis with 6 stages (Capture → Decode → Compress → Export → Align → Final)
- **Rich Display**: Coloured horizontal status table with retro terminal aesthetic
- **Job Integration**: Real-time job queue status with duplicate prevention

### ✅ Phase 2: Multi-Directory Support (COMPLETED - 2025-08-10)
1. ✅ Directory manager implementation (`directory_manager.py`)
2. ✅ Configuration management updates (JSON-based processing locations)
3. ✅ Menu system integration (accessible via Main Menu → VHS-Decode → Manage Project)
4. ✅ User interface for location management (Add/Remove/Configure processing locations)

**Implementation Features:**
- **Multi-Location Scanning**: Configurable processing directories with enable/disable
- **Dynamic Path Resolution**: No hardcoded paths, follows architectural principles
- **Processing Location Management**: Add, remove, and configure scan directories
- **Default Setup**: Automatically configures capture directory as first location

### ✅ Phase 3: Interactive Features (COMPLETED - 2025-08-10)
1. ✅ Batch operations framework (Queue decode/export jobs for multiple projects)
2. ✅ Interactive selection system (Project details menu with navigation)
3. ⚠️ Advanced filtering capabilities (Basic implementation - extensible for future)
4. ✅ Status update automation (Real-time refresh and auto-refresh mode)

**Interactive Features Implemented:**
- **Batch Operations Menu**: Queue multiple decode/export jobs simultaneously
- **Project Details View**: Detailed status for individual projects with file information
- **Display Configuration**: Toggle legend, summary, colours, auto-refresh settings
- **Status Export**: JSON reports of project status for external analysis
- **Processing Location Management**: Full CRUD interface for scan directories

### Phase 4: Polish & Performance (Future)
1. Performance optimisation (caching, multi-threading)
2. Error handling robustness (network drives, corrupted files)
3. User experience refinements (keyboard shortcuts, advanced filtering)
4. Documentation and help system (integrated help screens)

## Technical Dependencies

### Required Libraries
```python
# Core dependencies
from rich.console import Console
from rich.table import Table
from rich.text import Text
from rich.live import Live

# Standard library
import os, json, threading, time
from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import List, Dict, Optional, Set
from pathlib import Path
from enum import Enum
```

### Integration Dependencies
```python
# Existing system integration
from job_queue_manager import JobQueueManager, JobStatus
from config import load_config, save_config
from parallel_vhs_decode import ParallelVHSDecoder
```

### File System Requirements
- Read access to processing directories
- Write access to config directory
- Sufficient disk space for status caching
- Optional: inotify support for real-time updates

## Testing Strategy

### Unit Testing
- Project discovery accuracy
- Status detection logic
- File validation algorithms
- Job queue integration

### Integration Testing  
- Multi-directory scanning
- Real job queue interaction
- Configuration persistence
- Menu system integration

### User Experience Testing
- Large project set performance
- Interactive control responsiveness
- Color display across terminals
- Error handling user flows

## Deployment Considerations

### Backward Compatibility
- Existing job queue system unchanged
- Configuration file backward compatible
- Menu structure additions, no removals
- Graceful fallback if Rich unavailable

### Migration Strategy
- Gradual rollout with feature flags
- Side-by-side operation with existing system
- User preference for old vs new interface
- Training/documentation for transition

---

**Document Created**: 2025-01-09  
**Last Updated**: 2025-08-10  
**Version**: 1.1  
**Author**: AI Assistant via Claude 3.5 Sonnet  
**Status**: ✅ IMPLEMENTATION COMPLETE - Phases 1-3 Deployed

## Implementation Summary (2025-08-10)

**✅ SUCCESSFULLY IMPLEMENTED:**
- **Core Framework**: Complete project-centric workflow browser with Rich terminal interface
- **Multi-Directory Support**: Dynamic processing location management with configuration UI
- **Interactive Features**: Batch operations, project details, real-time status updates
- **Menu Integration**: Accessible via Main Menu → VHS-Decode → "Manage Project (jobs, workflow, status)"
- **Architecture Compliance**: Uses existing shared components, British English, no hardcoded paths

**📁 KEY FILES CREATED/MODIFIED:**
- `project_workflow_browser.py` - Main browser implementation (NEW)
- `project_workflow.py` - Compatibility wrapper (UPDATED)
- `project_discovery.py` - Project detection (EXISTING - REUSED)
- `workflow_analyzer.py` - Status analysis (EXISTING - REUSED)
- `project_status_display.py` - Rich display (EXISTING - REUSED)
- `directory_manager.py` - Location management (EXISTING - REUSED)
- `job_queue_manager.py` - Job integration (EXISTING - REUSED)

**🎯 USER ACCESS PATH:**
```
Main Menu → 2 (VHS-Decode) → 1 (Manage Project) → Project Workflow Status Browser
```

**✨ FEATURES WORKING:**
- Project-centric horizontal workflow status table with colours
- Real-time analysis of 6 workflow stages (Capture → Decode → Compress → Export → Align → Final)
- Multi-directory scanning with configurable processing locations
- Batch operations for queueing multiple projects
- Project details view with comprehensive file information
- Auto-refresh mode and display customisation
- Export status reports in JSON format
- Full integration with existing job queue system

This document now serves as both architectural specification and implementation record. The Project Workflow Status Browser is fully operational and ready for production use.
