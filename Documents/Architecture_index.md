# DDD Capture Toolkit - Architecture Documentation

This directory contains multiple architecture documents that cover different aspects of the system:

## Current Architecture Documents

### `Architecture_comprehensive.md` ⭐ **Primary Reference**
**Complete system architecture covering the current workflow management platform**
- All modules, classes, and functions with their purposes
- Data flow and system integration patterns
- Job queue system and background processing
- Workflow control centre and project management
- External dependencies and libraries
- **Use this for**: Understanding the complete system before making changes

### `Architecture_build_system.md` 📦 **Build System Focus**
**Original architecture document focusing on build system and installation**
- Cross-platform build strategy and conda environment isolation
- Git submodule management and version control
- Binary vs source installation modes
- Platform-specific build considerations
- **Use this for**: Understanding the build system, installation process, and cross-platform support

## Which Document to Use

**For Development Work**: Start with `Architecture_comprehensive.md`
- Modifying workflow management components
- Adding new features to the UI
- Understanding module relationships
- Job queue or project discovery changes

**For Build System Work**: Refer to `Architecture_build_system.md`
- Setting up development environments
- Cross-platform build issues
- Adding new external dependencies
- Installation and packaging concerns

**For Complete Understanding**: Read both documents
- The comprehensive document covers the runtime system
- The build system document covers installation and environment setup
- Together they provide complete coverage of the entire toolkit

## Document Evolution

The system has evolved significantly from its original build-tool concept into a complete workflow management platform. The comprehensive architecture document reflects this evolution, while the build system document preserves the important foundational architecture decisions that still apply today.
