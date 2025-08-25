# DDD Capture Toolkit - Architectural Principles

## Overview

This document establishes the fundamental architectural principles that govern all development and implementation decisions within the DDD Capture Toolkit. These principles ensure consistency, maintainability, cross-platform compatibility, and a cohesive user experience across all components of the system.

## Core Architectural Principles

### 0. AI Assistant Principles (For AI coding assistants reading this document)
- Always use UK English
- If you make a change, update the documentation
- If you update documentation, I don't need a status update, just update the changes in the appropriate (existing if possible) section
- If you update documentation, check that it hasn't superceded other documentation, which you should remove
- Make sure you update any coding principles, class names etc in here that you might have added
- No icons, do not put icons anywhere in the code


### 1. Platform Independence First

**Principle**: The toolkit must be truly cross-platform, working identically on Windows, macOS, and all major Linux distributions without platform-specific compromises.

**Implementation Requirements**:
- Use cross-platform libraries and frameworks (Python, conda, Rich, etc.)
- Platform-specific code must be clearly isolated with fallback implementations
- All file operations use `os.path` or `pathlib` for proper path handling
- System calls must use appropriate abstractions (subprocess, shutil, etc.)
- Hardware access (USB, audio) must work consistently across platforms

**Validation Criteria**:
- ✅ Same functionality available on all supported platforms
- ✅ Same user interface appearance and behaviour
- ✅ Same performance characteristics within platform limitations
- ✅ Same file formats and compatibility

### 2. No Hardcoded Paths Policy

**Principle**: The system shall contain absolutely no hardcoded paths. Any occurrence of `/home/username` or similar user-specific paths in code is a critical architectural violation.

**Implementation Requirements**:
- All paths must be determined dynamically using proper path resolution:
  - `os.path.expanduser('~')` for user home directory
  - `pathlib.Path.home()` for modern path handling
  - `os.getcwd()` or `Path.cwd()` for current working directory
  - Environment variables for system paths
- Use relative paths within the project structure
- Configuration-driven path management through `config.json`
- Processing locations managed via the settings system

**Forbidden Patterns**:
- ❌ `/home/username/...`
- ❌ `C:\Users\username\...`
- ❌ `/Users/username/...`
- ❌ Any absolute path containing usernames
- ❌ Hardcoded drive letters or mount points

**Required Patterns**:
- ✅ `Path.home() / 'Videos' / 'VHS_Captures'`
- ✅ `os.path.join(os.path.expanduser('~'), 'Documents')`
- ✅ Configuration-based directory management
- ✅ Dynamic path resolution at runtime

### 3. Complete Environment Isolation

**Principle**: The toolkit must be completely self-contained within its conda environment without affecting or depending on system installations.

**Implementation Requirements**:
- All processing tools contained within conda environment
- No modification of system PATH or environment variables outside conda
- Tools only available when conda environment is activated
- Complete separation from user's existing tool installations
- Clean uninstall by simply deleting the conda environment

**Coexistence Guarantee**:
```bash
# User's existing tools (unaffected)
/usr/bin/vhs-decode              # System installation
~/.local/bin/ld-analyse          # pip --user installation

# Toolkit tools (isolated)
conda activate ddd-capture-toolkit
which vhs-decode  # → $CONDA_PREFIX/bin/vhs-decode
conda deactivate
which vhs-decode  # → /usr/bin/vhs-decode (user's version restored)
```

### 4. Upstream Tools Preference

**Principle**: Use upstream, standard tools wherever possible. Only fork or create custom tools when absolutely necessary for missing functionality.

**Implementation Requirements**:
- Prefer conda packages over custom builds where available
- Use official releases and stable versions
- Document any deviations from upstream in `build.txt`
- Maintain clear contribution pathways for custom enhancements
- Track upstream changes and synchronise regularly

**Current Exceptions** (documented in build.txt):
- **Domesday Duplicator**: Custom fork with CLI enhancements for automation
- **VHS-Decode**: Source compilation for performance optimisation

**Contribution Strategy**:
- Prepare clean feature branches for upstream contribution
- Maintain dual capability during transition periods

### 5. Self-Contained Distribution

**Principle**: Everything needed for complete functionality must be included in the repository or automatically installable through the setup process.

**Implementation Requirements**:
- Git submodules for external source dependencies
- Version locking for tested combinations
- Offline installation capability where possible
- All custom modifications preserved in version control
- Complete dependency chain documentation

**Distribution Structure**:
```
ddd-capture-toolkit/
├── external/                    # Git submodules for source dependencies
├── build-scripts/              # Cross-platform build automation
├── prebuilt/                   # Platform-specific fallback binaries
├── environment-*.yml           # Platform-specific conda environments
└── Documents/                  # Complete documentation set
```

### 6. Configuration-Driven Architecture

**Principle**: System behaviour must be controllable through configuration files rather than code modifications.

**Implementation Requirements**:
- All user preferences stored in `config.json`
- Processing locations managed through settings menu
- No configuration scattered across multiple files
- Sensible defaults that work out of the box
- Migration strategies for configuration format changes

**Configuration Hierarchy**:
1. **User Configuration**: `config.json` (user-modifiable)
2. **System Defaults**: Embedded in code with clear override mechanisms
3. **Environment Variables**: For advanced users and automation
4. **Command Line Arguments**: For scripting and testing

## Visual Design Principles

### 7. Retro Terminal Aesthetic

**Principle**: The user interface should evoke classic terminal computing aesthetics while remaining functional and accessible.

**Visual Design Standards**:

#### Colour Schemes

**Default Multi-Colour Palette**
```
┌─ RETRO TERMINAL COLOUR PALETTE ─┐
│                                  │
│ PRIMARY:                         │
│ • Amber:     #FFB000 (warnings) │
│ • Green:     #00FF41 (success)  │
│ • Dark Grey: #1E1E1E (background)│
│ • Light Grey:#B0B0B0 (text)     │
│                                  │
│ ACCENT:                          │
│ • Cyan:      #00FFFF (info)     │
│ • Red:       #FF4444 (errors)   │
│ • Yellow:    #FFFF00 (caution)  │
│ • White:     #FFFFFF (emphasis) │
└──────────────────────────────────┘
```

**Optional Amber Monochrome Palette**
```
┌─ AMBER TERMINAL COLOUR PALETTE ──┐
│                                   │
│ MONOCHROME AMBER THEME:           │
│ • Background: #000000 (black)     │
│ • Text Base:  #FF8000 (amber)     │
│ • Dim Text:   #CC6600 (dark amber)│
│ • Bright:     #FFAA00 (bright)    │
│ • Emphasis:   #FFCC33 (highlight) │
│                                   │
│ TEXT STYLING:                     │
│ • Bold:       Bright amber        │
│ • Italic:     Dim amber           │
│ • Underline:  Standard amber      │
│ • Blink:      Alternating bright  │
│ • Reverse:    Black on amber      │
└───────────────────────────────────┘
```

#### Typography and Layout
- Use monospace fonts for all interface elements
- ASCII art and box drawing characters for visual separation
- Consistent spacing and alignment
- Progressive disclosure of complex information
- Clear visual hierarchy through colour and typography

#### Interface Standards
```
MAIN MENU HEADER EXAMPLE:
╭─────────────────────────────────╮
│  DDD CAPTURE TOOLKIT v2.1.0     │
│  VHS Archival Processing Suite   │
╰─────────────────────────────────╯

MENU ITEM FORMAT:
 1. ▶ VHS Capture Management
 2. ▶ Processing Queue Status  
 3. ▶ Settings & Configuration
```

#### Colour Usage Guidelines

**Default Multi-Colour Theme:**
- **Green**: Successful operations, available actions, ready states
- **Amber/Yellow**: Warnings, important information, processing states
- **Red**: Errors, failed operations, blocked states
- **Cyan**: Informational text, secondary actions, metadata
- **White**: Critical information, current selection, emphasis

**Amber Monochrome Theme:**
- **Standard Amber (#FF8000)**: Normal text, menu items, standard information
- **Dim Amber (#CC6600)**: Secondary text, disabled items, subtle information
  - Use *italic* styling for emphasis
  - Parenthetical information: *(processing locations: 2)*
- **Bright Amber (#FFAA00)**: Active selections, current status, progress bars
  - Use **bold** styling for emphasis
  - Active items: **[Processing Queue Status]**
- **Highlight Amber (#FFCC33)**: Critical alerts, urgent attention required
  - Use **bold** + _underline_ styling
  - Combine with blinking for maximum attention
- **Reverse Video**: Black text on amber background for extreme emphasis
  - Selection indicators: **[█ SELECTED ITEM █]**
  - Error states requiring immediate action

**Amber Theme Status Indicators:**
```
SUCCESS:    ✓ **Complete**     (bright amber, bold)
WARNING:    ⚠ *Attention*      (highlight amber, italic+underline)
ERROR:      ✗ **FAILED**       (highlight amber, bold+blink)
INFO:       ℹ Standard text    (standard amber)
PROGRESS:   ████████░░ 80%     (bright amber blocks, dim amber background)
```

### 8. Information Hierarchy

**Principle**: Present information in clear, logical hierarchies that guide users through complex workflows.

**Implementation Requirements**:
- Progressive disclosure from general to specific
- Consistent navigation patterns across all menus
- Clear status indicators for system state
- Contextual help and guidance
- Logical grouping of related functions

**Menu Structure Standards**:
1. **Primary Categories**: Broad functional areas (Capture, Processing, Settings)
2. **Secondary Functions**: Specific operations within categories
3. **Tertiary Options**: Detailed configuration and advanced features
4. **Status Indicators**: Always visible system and operation status

## Development Standards

### 9. Code Quality and Consistency

**Principle**: All code must meet high standards for readability, maintainability, and consistency.

**Implementation Requirements**:
- Follow PEP 8 Python style guidelines
- Use type hints for function parameters and return values
- Comprehensive docstrings for all public functions and classes
- Consistent naming conventions across the codebase
- Regular code review and refactoring

**Documentation Standards**:
- All public APIs must have comprehensive docstrings
- Complex algorithms require inline comments
- Architecture decisions documented in this principles document
- User-facing documentation kept current with code changes

### 10. Error Handling and User Experience

**Principle**: The system must gracefully handle all error conditions with clear, actionable feedback to users.

**Implementation Requirements**:
- Comprehensive exception handling with specific error messages
- Fallback mechanisms for critical operations
- Clear user guidance for error resolution
- Logging appropriate for debugging without overwhelming users
- Graceful degradation when features are unavailable

**Error Message Standards**:
```
ERROR FORMAT EXAMPLES:

✗ Configuration Error
  Could not load config.json
  → Check file permissions in project directory
  → File location: /path/to/config.json

⚠ Hardware Warning  
  Domesday Duplicator not detected
  → Verify USB connection and permissions
  → See build.txt for setup instructions

ℹ Information
  Processing locations configured: 2
  → Settings → Manage Processing Locations
```

### 11. Performance and Resource Management

**Principle**: The system must be optimised for the long-running, resource-intensive nature of VHS archival processing.

**Implementation Requirements**:
- Source compilation with CPU-specific optimisations where beneficial
- Efficient memory management for large file processing
- Proper resource cleanup and garbage collection
- Monitoring and feedback for long-running operations
- Configurable concurrency based on system capabilities

**Performance Targets**:
- Startup time: < 2 seconds for basic functionality
- Memory usage: Reasonable scaling with file sizes
- CPU utilisation: Efficient use of available cores
- Disk I/O: Optimised for sustained high-bandwidth operations

### 12. Testing and Validation

**Principle**: All functionality must be testable and tested, with particular attention to cross-platform compatibility.

**Implementation Requirements**:
- Unit tests for core functionality
- Integration tests for complete workflows
- Cross-platform testing on Windows, macOS, and Linux
- Performance benchmarking for critical operations
- User acceptance testing for interface changes

**Testing Standards**:
- Automated tests run on all supported platforms
- Manual testing procedures documented
- Performance regression detection
- User workflow validation

## Code Reuse and Shared Components

### 13. Don't Repeat Yourself (DRY) Principle

**Principle**: Any functionality that could be used in multiple places must be implemented as a shared component, not duplicated across the codebase.

**Implementation Requirements**:
- Create shared modules for common functionality
- Use clear, descriptive naming for shared components
- Document all shared components comprehensively
- Establish clear import patterns for shared code
- Prevent AI assistants from re-implementing existing functionality

**Critical Areas Requiring Shared Components**:
- **Validation Logic**: FSK decoding, timecode correlation, audio analysis
- **UI Widgets**: Progress bars, status displays, menu components
- **File Operations**: Path handling, directory scanning, file validation
- **Configuration Management**: Settings loading, validation, persistence
- **Error Handling**: Standardised error messages and recovery patterns

**Shared Component Examples**:
```python
# Shared validation logic (already implemented)
from shared_timecode_robust import SharedTimecodeRobust

# Shared UI components (future implementation)
from ui_components import RetroProgressBar, StatusPanel, MenuWidget

# Shared file operations (future implementation)  
from file_utils import scan_processing_locations, validate_rf_files

# Shared configuration (already implemented)
from config import load_config, get_processing_locations
```

### 14. Shared Component Architecture

**Principle**: All reusable functionality must be organised into well-defined shared modules with clear interfaces and comprehensive documentation.

**Implementation Requirements**:
- **Single Source of Truth**: Each piece of functionality exists in exactly one place
- **Clear Interfaces**: Well-defined APIs with type hints and docstrings
- **Backward Compatibility**: Changes to shared components must not break existing usage
- **Version Management**: Track changes to shared components carefully
- **Testing**: Comprehensive tests for all shared functionality

**Shared Module Organisation**:
```
shared/
├── __init__.py                     # Package initialisation
├── validation/
│   ├── __init__.py
│   ├── timecode_analysis.py        # SharedTimecodeRobust class
│   ├── audio_processing.py         # FSK decoding, audio validation
│   └── file_validation.py          # RF file validation, metadata parsing
├── ui_components/
│   ├── __init__.py
│   ├── progress_displays.py        # RetroProgressBar, status indicators
│   ├── menu_widgets.py            # Standardised menu components
│   ├── colour_themes.py           # Retro terminal colour palette
│   └── layout_managers.py         # Consistent spacing and alignment
├── file_operations/
│   ├── __init__.py
│   ├── directory_scanning.py       # Processing location scanning
│   ├── path_resolution.py         # Cross-platform path handling
│   └── media_file_utils.py        # RF, audio, video file operations
└── workflow/
    ├── __init__.py
    ├── job_management.py           # Common job processing patterns
    ├── dependency_resolution.py   # Workflow dependency logic
    └── status_tracking.py         # Unified status management
```

### 15. AI Assistant Guidance Prevention

**Principle**: The codebase must be structured to guide AI assistants away from reimplementing existing functionality.

**Implementation Requirements**:
- **Clear Documentation**: Every shared component has comprehensive docstrings
- **Usage Examples**: Include practical examples in shared component documentation
- **Import Statements**: Use consistent, obvious import patterns
- **Code Comments**: Include "Use shared_module.function() instead" comments where appropriate
- **Validation Tools**: Automated detection of duplicate functionality

**AI Guidance Patterns**:
```python
# At the top of modules that might duplicate functionality
"""
IMPORTANT: Before implementing new validation logic, check:
- shared.validation.timecode_analysis for FSK decoding
- shared.validation.audio_processing for audio analysis
- shared.validation.file_validation for RF file validation

DO NOT reimplement existing functionality.
"""

# In functions that use shared components
def analyze_vhs_timecode(audio_file):
    """
    Analyze VHS timecode using shared validation logic.
    
    Uses SharedTimecodeRobust from shared.validation.timecode_analysis
    DO NOT reimplement FSK decoding or correlation logic.
    """
    from shared.validation.timecode_analysis import SharedTimecodeRobust
    # ... rest of implementation
```

### 16. Shared Component Documentation Standards

**Principle**: All shared components must have comprehensive documentation that prevents reimplementation and guides proper usage.

**Documentation Requirements**:
- **Purpose Statement**: Clear explanation of what the component does
- **Usage Examples**: Practical code examples for common use cases
- **API Reference**: Complete parameter and return value documentation
- **Integration Notes**: How to integrate with other system components
- **Version History**: Changes and compatibility notes

**Documentation Template**:
```python
class SharedComponent:
    """
    [PURPOSE] One-line description of component purpose
    
    [USAGE] This component provides [specific functionality] and should be used
    whenever [specific situation]. DO NOT reimplement this functionality.
    
    [EXAMPLES]
    Basic usage:
    >>> component = SharedComponent()
    >>> result = component.process_data(input_data)
    
    Advanced usage:
    >>> component = SharedComponent(strict_mode=True)
    >>> result = component.process_data(input_data, options={'flag': True})
    
    [INTEGRATION] 
    This component integrates with:
    - shared.validation.other_component for related functionality
    - config.py for configuration management
    
    [VERSION HISTORY]
    v1.0: Initial implementation
    v1.1: Added strict_mode parameter
    """
```

## Integration Principles

### 17. Modular Architecture

**Principle**: The system must be composed of loosely coupled, highly cohesive modules that can be developed, tested, and maintained independently.

**Implementation Requirements**:
- Clear separation of concerns between modules
- Well-defined interfaces between components
- Minimal dependencies between modules
- Plugin-style architecture for extensibility
- Independent testing of modules

**Module Structure**:
```
Core Modules:
├── config.py              # Configuration management
├── parallel_vhs_decode.py  # Job processing engine
├── ddd_main_menu.py       # User interface
└── directory_manager.py   # Processing location management

External Integration:
├── external/              # Git submodules
├── build-scripts/         # Build automation
└── tools/                 # Utility scripts
```

### 18. Backward Compatibility

**Principle**: Changes must not break existing user workflows or configurations without clear migration paths.

**Implementation Requirements**:
- Configuration file format versioning
- Migration scripts for breaking changes
- Deprecation warnings before removing functionality
- Clear changelog documentation
- User communication for significant changes

## Security and Privacy Principles

### 19. User Privacy and Data Protection

**Principle**: The system must respect user privacy and protect sensitive data throughout all operations.

**Implementation Requirements**:
- No collection or transmission of user data without explicit consent
- Secure handling of configuration data
- No hardcoded credentials or sensitive information
- Local processing without external dependencies
- Clear data retention and cleanup policies

### 20. Secure Development Practices

**Principle**: All code must follow secure development practices to protect users and their systems.

**Implementation Requirements**:
- Input validation and sanitisation
- Safe file operations with proper permissions
- No execution of untrusted code
- Secure temporary file handling
- Regular dependency updates for security patches

### 21. Documentation Synchronisation

**Principle**: Architecture documentation must be updated immediately following any code changes that affect system structure, module relationships, or public interfaces.

**Implementation Requirements**:
- All new modules, classes, or functions require corresponding updates to `Architecture_comprehensive.md`
- Changes to data structures, enums, or configuration formats trigger documentation updates
- Module inventory tables, class definitions, and function inventories must remain current
- Data flow descriptions updated when component relationships change
- Dependency lists maintained for both internal modules and external libraries

**AI Assistant Implementation**:
- After making code changes, AI assistants must update relevant architecture documentation sections
- New components added to appropriate inventory tables with purpose descriptions
- Modified components have their documentation updated to reflect current state
- Cross-references between related components maintained and updated
- No code changes complete without corresponding documentation updates

**Update Scope**:
```
Code Change Types Requiring Documentation Updates:
├── New Python modules → Module inventory table
├── New classes/dataclasses → Class definitions section
├── New public functions → Function inventory by module
├── Modified data structures → Data structure documentation
├── Changed dependencies → System dependencies section
├── Altered data flow → Data flow diagrams and descriptions
└── Configuration changes → File organisation section
```

## Compliance and Standards

### 22. British English Spelling Standard

**Principle**: All user-facing text, documentation, and code comments must use British or New Zealand English spelling conventions.

**Implementation Requirements**:
- Use "colour" not "color"
- Use "summarising" not "summarizing"
- Use "optimisation" not "optimization"
- Use "centre" not "center"
- Remove the word "professional" from naming conventions

**Validation**:
- Spell checking with British English dictionaries
- Code review for spelling consistency
- Documentation review for language standards

### 23. No Exclusionary Language

**Principle**: All terminology must be welcoming and accessible, avoiding exclusionary language related to skill level.

**Implementation Requirements**:
- Remove the word "professional" from any naming conventions
- Use "advanced" instead of "professional" where needed
- Use "specialised" instead of "professional" for specific contexts
- Focus on functionality rather than user categorisation

### 24. Consistent Menu Navigation

**Principle**: Menu navigation must be consistent across the entire application to provide predictable user experience.

**Implementation Requirements**:
- **"0" (Zero) always returns to Main Menu** from any submenu or subsystem
- **"Q" or "ESC" returns to parent menu** (one level up) within subsystems
- **Menu option numbers** should be consistent for similar functions across different menus
- **Navigation hints** should be displayed consistently (e.g., "Press 0 to return to Main Menu")
- **Exit confirmation** should be consistent when leaving the application entirely

**Standard Navigation Pattern**:
```
Any Menu:
1. Option One
2. Option Two
...
9. Last Functional Option
0. Return to Main Menu

Within Subsystems:
[Q]uit to parent menu
[ESC] to cancel/back
[0] Return to Main Menu (skip intermediate levels)
```

### 25. Workflow Control Centre Interface Standard

**Principle**: The Workflow Control Centre uses exclusively Rich-based enhanced interface mode for all features and functionality.

**Implementation Requirements**:
- **No Simple Mode**: The Workflow Control Centre does not implement or support a simple text-based mode
- **Rich Interface Only**: All features are implemented using the Rich library for enhanced terminal UI
- **Fallback Handling**: Systems without Rich support receive clear error messages directing users to install Rich
- **Consistent Experience**: All workflow management features use the same Rich-based interface paradigm
- **No Mode Switching**: Users cannot switch between interface modes - only the enhanced mode is available

**Interface Architecture**:
```
Workflow Control Centre:
├── Enhanced Rich Interface (ONLY mode)
│   ├── Live updating layout
│   ├── Real-time project matrix
│   ├── Interactive command input
│   ├── System status panels
│   └── Resource monitoring
└── Error handling for missing Rich library
    └── Clear installation instructions
```

**Implementation Standards**:
- All workflow control functionality integrated into enhanced mode
- No legacy simple mode code or references
- Rich library required dependency for workflow features
- Consistent command interface across all workflow operations

## Implementation Validation

### Principle Compliance Checklist

Before any code is merged or released, it must pass this compliance checklist:

#### Platform Independence
- [ ] Runs identically on Windows, macOS, and Linux
- [ ] No platform-specific code without proper abstractions
- [ ] All file operations use cross-platform path handling

#### Path Management  
- [ ] No hardcoded paths anywhere in code
- [ ] All paths determined dynamically
- [ ] Configuration-driven directory management

#### Environment Isolation
- [ ] All tools contained in conda environment
- [ ] No system modifications required
- [ ] Clean uninstall process available

#### Visual Standards
- [ ] Retro terminal aesthetic maintained
- [ ] Consistent colour palette usage
- [ ] Clear information hierarchy

#### Code Quality
- [ ] Comprehensive error handling
- [ ] Performance optimised for long-running operations
- [ ] Complete documentation

#### Shared Components and Code Reuse
- [ ] No duplicate functionality - existing shared components used
- [ ] New reusable functionality implemented as shared components
- [ ] Clear documentation and examples for any new shared components
- [ ] AI guidance comments included where appropriate
- [ ] Import patterns follow established conventions

#### Language Standards
- [ ] British English spelling throughout
- [ ] No exclusionary terminology
- [ ] Professional, welcoming tone

## Evolution and Maintenance

### 26. Principle Evolution

**Principle**: These architectural principles are living guidelines that may evolve based on project needs and community feedback.

**Change Management**:
- Principle changes require community discussion
- Breaking changes need clear migration strategies  
- Evolution documented in changelog
- Regular review and refinement

### 27. Compliance Monitoring

**Principle**: Adherence to these principles must be monitored and enforced through development processes.

**Enforcement Mechanisms**:
- Code review requirements
- Automated testing for compliance
- Documentation review processes
- Regular architectural assessments

---

## Summary

These architectural principles form the foundation for all development decisions in the DDD Capture Toolkit. They ensure the system remains:

- **Cross-platform compatible** without compromise
- **User-friendly** with consistent interfaces
- **Maintainable** through clear standards
- **Performant** for long-running archival tasks
- **Professional** in appearance and behaviour
- **Respectful** of user privacy and system integrity

All contributors must understand and follow these principles. When in doubt, refer to these guidelines or seek clarification through the project's communication channels.

*Document Version*: 1.0  
*Last Updated*: 2025-08-10  
*Next Review*: 2025-11-10
