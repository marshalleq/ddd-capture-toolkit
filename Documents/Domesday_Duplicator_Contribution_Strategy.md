# Domesday Duplicator - Fork Management & Upstream Contribution Strategy

## Overview

This document outlines the strategy for managing the custom Domesday Duplicator fork with CLI enhancements, preparing for eventual upstream contribution while maintaining competitive advantage.

## Repository Structure

### Current Setup
- **Upstream Original**: `https://github.com/simoninns/DomesdayDuplicator.git`
- **Your Enhanced Fork**: `https://gitea.electropositive.net/Media-Restoration/domesday-duplicator-cmdline.git`
- **Submodule Location**: `external/DomesdayDuplicator/`

### Remote Configuration
```bash
# Your submodule has three important remotes:
origin    https://gitea.electropositive.net/Media-Restoration/domesday-duplicator-cmdline.git
upstream  https://github.com/simoninns/DomesdayDuplicator.git
```

## Your CLI Enhancements Analysis

### Changes Made (3 commits ahead of upstream)
```bash
fadbf1c Fix Path Code
138722d Working Copy  
8d0e175 Initial cmdline added
```

### Key Files Modified
Based on `git diff --name-only upstream/master..HEAD`:

**Core CLI Implementation:**
- `Linux-Application/DomesdayDuplicator/main.cpp` - CLI argument parsing
- `Linux-Application/DomesdayDuplicator/mainwindow.cpp` - Headless operation support
- `Linux-Application/DomesdayDuplicator/mainwindow.h` - Header modifications

**Documentation:**
- `COMMAND_LINE_CAPTURE.md` - CLI usage documentation
- `Documentation/COMMAND_LINE_ARCHITECTURE.md` - Architecture documentation
- `USB_PERMISSIONS_LINUX.md` - Linux-specific USB setup
- `BUILDING.md` - Enhanced build instructions

**System Integration:**
- `Linux-Application/99-domesday-duplicator.rules` - udev rules
- `Linux-Application/start.sh` - Launch script

**Development/Testing:**
- Various log files and test artifacts
- `.github/workflows/tests.yml` - CI/CD pipeline

## CLI Features Added

Based on the build.txt documentation, your CLI enhancements include:

### Command Line Options
```bash
--headless           # Run without showing GUI (requires --start-capture)
--start-capture      # Start capture automatically
--stop-capture       # Stop any running capture and exit
--output-file <name> # Specify output filename or path
# Capture directory is implemented but missing here and should be added
```

### Additional Features
- **Real-time RMS amplitude display** in console for monitoring
- **Automated capture initiation** for scripted workflows
- **Headless operation** for server/automated environments

## Competitive Advantage Strategy

### Phase 1: Internal Advantage (Current)
- **Submodule Integration**: Your toolkit uses the enhanced fork exclusively
- **Competitive Edge**: CLI automation capabilities not available upstream
- **User Experience**: Seamless automated capture workflows
- **Documentation**: Comprehensive usage guides in your toolkit

### Phase 2: Community Contribution (Future)
When ready to contribute upstream:
- **Clean Pull Request**: Well-documented, tested changes
- **Community Benefit**: Enhanced automation capabilities for all users
- **Upstream Ownership**: Reduced maintenance burden for you
- **Industry Standard**: Your innovations become the standard

## Git Workflow for Contribution Preparation

### 1. Create Clean Feature Branch
```bash
cd external/DomesdayDuplicator

# Create a clean feature branch based on upstream master
git checkout -b feature/cli-automation upstream/master

# Cherry-pick your changes (cleaning up commit history)
git cherry-pick 8d0e175  # Initial cmdline added
git cherry-pick 138722d  # Working Copy  
git cherry-pick fadbf1c  # Fix Path Code

# Or alternatively, create clean commits by applying diffs:
# git diff upstream/master..main > cli-enhancements.patch
# Apply and commit cleanly
```

### 2. Prepare for Pull Request
```bash
# Create clean, focused commits
git reset --soft upstream/master
git add Linux-Application/DomesdayDuplicator/main.cpp \
        Linux-Application/DomesdayDuplicator/mainwindow.cpp \
        Linux-Application/DomesdayDuplicator/mainwindow.h
git commit -m "Add command-line interface support

- Add --headless option for GUI-less operation
- Add --start-capture for automated capture initiation  
- Add --stop-capture for programmatic capture termination
- Add --output-file for custom output file specification
- Display real-time RMS amplitude in console for monitoring

This enables automated capture workflows and server-side operation
while maintaining full backward compatibility with existing GUI usage."

# Add documentation in separate commit
git add COMMAND_LINE_CAPTURE.md \
        Documentation/COMMAND_LINE_ARCHITECTURE.md \
        BUILDING.md \
        USB_PERMISSIONS_LINUX.md
git commit -m "Add CLI documentation and usage guides

- Document all command-line options and usage patterns
- Add architecture documentation for CLI implementation
- Enhance building instructions for new features
- Add Linux USB permissions setup guide"

# Add system integration files
git add Linux-Application/99-domesday-duplicator.rules \
        Linux-Application/start.sh \
        .github/workflows/tests.yml
git commit -m "Add system integration and testing infrastructure

- Add udev rules for proper USB device permissions
- Add launch script for easy CLI usage
- Add CI/CD pipeline for automated testing"
```

### 3. Maintain Upstream Sync
```bash
# Regular upstream synchronization (monthly or when needed)
git fetch upstream

# Check for upstream changes
git log --oneline HEAD..upstream/master

# If upstream has changes, rebase your feature branch
git checkout feature/cli-automation
git rebase upstream/master

# Update your main branch to incorporate upstream changes
git checkout main
git merge upstream/master
git push origin main
```

## Commands Reference

### Daily Development
```bash
# Update your toolkit's submodule to latest fork version
cd external/DomesdayDuplicator
git pull origin main
cd ../..
git add external/DomesdayDuplicator
git commit -m "Update Domesday Duplicator submodule"

# Check for upstream changes
cd external/DomesdayDuplicator
git fetch upstream
git log --oneline HEAD..upstream/master  # Shows new upstream commits
```

### Preparing for Contribution
```bash
# Create clean feature branch for PR
cd external/DomesdayDuplicator
git checkout -b feature/cli-automation upstream/master
git diff main > ../domesday-cli-enhancements.patch
# Review and apply patches cleanly with proper commit messages
```

### Emergency Upstream Sync
```bash
# If upstream makes breaking changes
cd external/DomesdayDuplicator
git fetch upstream
git checkout main
git merge upstream/master
# Resolve any conflicts, test your CLI enhancements still work
git push origin main
```

## Summary

✅ **Submodule configured** - Your enhanced fork ready for use  
✅ **Upstream tracking** - Ready to monitor and sync with original  
✅ **Contribution pathway** - Clean process for eventual PR  
✅ **Competitive advantage** - CLI features exclusive to your toolkit initially

This strategy gives you the best of both worlds: immediate competitive advantage through your enhanced fork while preparing for eventual upstream contribution when the timing is strategically optimal.
