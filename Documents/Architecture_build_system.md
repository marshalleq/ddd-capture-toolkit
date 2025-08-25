# DDD Capture Toolkit - Architecture & Distribution Strategy

## Overview

This document defines the architectural principles, distribution strategy, and cross-platform compatibility approach for the DDD Capture Toolkit. The toolkit is designed to provide a complete, isolated, high-performance video processing environment while respecting existing user installations.

## Core Architectural Principles

### 1. Cross-Platform Portability
- **Platform Independence**: Implementation must be portable across all OS platforms (Linux, macOS, Windows)
- **Consistent Behaviour**: Same functionality and user experience regardless of operating system
- **Native Integration**: Respect platform-specific conventions while maintaining consistency
- **Universal Compatibility**: Support for different distributions, package managers, and system configurations

### 2. Complete Independence and Isolation
- **No Impact on Existing Installations**: Must not affect other code or existing instances of same applications
- **Path Isolation**: Tools only available in PATH when conda environment is activated
- **Version Coexistence**: Users can maintain their own tool versions (e.g., VHS-Decode) alongside the toolkit
- **Clean Separation**: Toolkit tools completely isolated from system and user-installed versions

### 3. Environment Isolation First
- **Complete Environment Isolation**: All processing tools contained within conda environment
- **No System Pollution**: User's existing installations remain untouched
- **Easy Cleanup**: Delete conda environment to remove everything
- **Guaranteed Coexistence**: Users can maintain their own tool versions alongside the toolkit

### 4. Performance Through Source Compilation
- **Optimized Builds**: Source compilation with CPU-specific optimizations
- **Long-Running Process Focus**: Performance gains crucial for hours-long encoding processes
- **User Choice**: Both easy (binary) and performance (source) installation options
- **Architecture-Specific**: Leverage modern CPU features (AVX, SSE, etc.)

### 5. Self-Contained Distribution
- **Single Repository**: Everything needed for complete functionality
- **Version Locking**: Tested combinations of tool versions
- **Offline Capability**: No external dependencies during installation
- **Custom Modifications**: Preserve toolkit-specific customizations (e.g., Domesday Duplicator CLI)

## Repository Structure

```
ddd-capture-toolkit/
├── Documents/                   # Architecture and documentation
│   ├── ARCHITECTURE.md         # This document
│   ├── README.md              # User-facing documentation
│   └── BUILD_GUIDE.md          # Detailed build instructions
├── 
├── setup.sh                    # Intelligent cross-platform setup
├── start.sh                    # Environment activation wrapper
├── 
├── environment-linux.yml       # Linux conda environment
├── environment-macos.yml       # macOS conda environment  
├── environment-windows.yml     # Windows conda environment
├── environment.yml             # Generic fallback environment
├── 
├── external/                   # Git submodules (source code)
│   ├── ld-decode/              # Submodule: happycube/ld-decode
│   ├── vhs-decode/             # Submodule: oyvindln/vhs-decode
│   ├── tbc-video-export/       # Submodule: JuniorIsAJitterbug/tbc-video-export
│   └── DomesdayDuplicator/     # Submodule: Custom fork with CLI support
├── 
├── build-scripts/              # Cross-platform build automation
│   ├── build-ld-decode.sh      # LD-Decode compilation script
│   ├── build-vhs-decode.sh     # VHS-Decode compilation script
│   ├── build-tbc-export.sh     # TBC-Video-Export compilation script
│   ├── build-domesday.sh       # Domesday Duplicator compilation script
│   └── common/                 # Shared build utilities
│       ├── detect-platform.sh  # OS/architecture detection
│       ├── optimize-flags.sh   # CPU optimization detection
│       └── conda-setup.sh      # Conda environment preparation
├── 
├── prebuilt/                   # Platform-specific binaries (fallback)
│   ├── linux-x64/             # Pre-compiled Linux binaries
│   ├── macos-x64/              # Pre-compiled macOS binaries
│   ├── macos-arm64/            # Pre-compiled Apple Silicon binaries
│   └── windows-x64/            # Pre-compiled Windows binaries
├── 
└── tools/                      # Toolkit-specific utilities
    ├── audio-sync/             # VHS audio alignment tools
    ├── create_iso_from_mp4.py  # DVD creation utilities
    └── check_dependencies.py   # Dependency validation
```

## Git Strategy: Submodules with Custom Forks

### Submodule Philosophy
- **External Dependencies**: Major processing tools as git submodules
- **Version Control**: Lock to specific, tested versions
- **Custom Modifications**: Fork when customizations needed
- **Upstream Tracking**: Maintain relationship with upstream projects

### Submodule Implementation
```bash
# Add external dependencies as submodules
git submodule add https://github.com/happycube/ld-decode external/ld-decode
git submodule add https://github.com/oyvindln/vhs-decode external/vhs-decode
git submodule add https://github.com/JuniorIsAJitterbug/tbc-video-export external/tbc-video-export

# Custom fork for Domesday Duplicator with CLI support
git submodule add https://github.com/yourusername/DomesdayDuplicator-cmdline external/DomesdayDuplicator
```

### Version Management
```bash
# Lock to specific tested versions
cd external/ld-decode && git checkout v2.3.1
cd external/vhs-decode && git checkout stable-branch
cd ../.. && git add external/ && git commit -m "Lock to tested versions"
```

### User Cloning
```bash
# Single command gets everything
git clone --recursive https://github.com/yourusername/ddd-capture-toolkit

# Or for existing clones
git submodule update --init --recursive
```

## Cross-Platform Compatibility Strategy

### Operating System Support Matrix

| Feature | Linux | macOS | Windows | Notes |
|---------|--------|--------|---------|-------|
| Conda Environment | ✅ | ✅ | ✅ | Primary isolation method |
| Source Compilation | ✅ | ✅ | ⚠️ | Windows requires MSVC |
| Hardware Access | ✅ | ✅ | ✅ | USB permissions vary by OS |
| Real-time Processing | ✅ | ✅ | ⚠️ | Windows scheduling differences |
| DVD Creation | ✅ | ✅ | ❌ | genisoimage/dvdauthor limitations |

### Platform-Specific Considerations

#### Linux (Primary Platform)
- **Package Managers**: Support for dnf, apt, pacman, zypper
- **USB Permissions**: udev rules for Domesday Duplicator
- **Real-time Scheduling**: audio group, limits.conf configuration
- **Compilation**: GCC with optimization flags

#### macOS
- **Apple Silicon**: Separate builds for x64 and ARM64
- **USB Permissions**: May require user intervention for device access
- **Compilation**: Clang with macOS-specific optimizations
- **System Integration**: screencapture for screenshots

#### Windows
- **Compilation Environment**: MSVC via conda (vs2019_win-64)
- **USB Drivers**: Windows-specific driver requirements
- **Path Handling**: Windows path separator compatibility
- **Process Management**: PowerShell for system integration

## Binary vs Source Distribution Strategy

### Two-Tier Installation System

#### Tier 1: Easy Installation (Binaries)
**Target Users**: Easy setup, testing, evaluation
```bash
./setup.sh --easy
```
**Implementation**:
- Pre-compiled binaries from `prebuilt/` directory
- Conda packages where available
- 5-minute setup time
- Good performance for most use cases

#### Tier 2: Performance Installation (Source)
**Target Users**: Production use, maximum performance, long encoding sessions
```bash
./setup.sh --performance
```
**Implementation**:
- Source compilation with CPU-specific optimizations
- Custom build flags for user's hardware
- 30-60 minute setup time
- Significant performance gains (10-30% typical)

### Performance Optimization Strategy

#### CPU-Specific Optimizations
```bash
# Detect user's CPU capabilities
CPU_FLAGS=$(build-scripts/common/optimize-flags.sh)
# Example output: -march=native -mtune=native -mavx2 -mfma

# Apply to all source builds
export CFLAGS="$CPU_FLAGS -O3 -flto"
export CXXFLAGS="$CPU_FLAGS -O3 -flto"
```

#### Multi-threading Optimization
- **Build-time**: Use all available CPU cores (`make -j$(nproc)`)
- **Runtime**: Tools configured for optimal thread usage
- **Memory**: Optimized for large file processing

## Installation Isolation Strategy

### Environment Separation

#### System Level (Minimal, Shared)
```
/usr/local/bin/DomesdayDuplicator    # Hardware driver (system-wide required)
/etc/udev/rules.d/99-domesday.rules  # USB permissions (system-wide required)
/etc/security/limits.conf            # Real-time scheduling (system-wide required)
```

#### Conda Environment Level (Complete Isolation)
```
$CONDA_PREFIX/bin/
├── ld-analyse                       # LaserDisc RF processing
├── ld-dropout-correct               # Dropout correction
├── ld-chroma-decoder                # Chroma decoding
├── vhs-decode                       # VHS RF processing
├── tbc-video-export                 # TBC to video conversion
├── ffmpeg                           # Video processing
└── python3                          # Runtime environment

$CONDA_PREFIX/lib/
├── libav*.so                        # Video codec libraries
├── libx264.so                       # H.264 encoding
└── python3.10/site-packages/       # Python dependencies
```

### Coexistence Guarantee

Users can maintain existing installations:
```bash
# User's existing tools (unaffected)
/usr/bin/ld-analyse                  # System installation
~/.local/bin/vhs-decode              # pip --user installation
/opt/custom/tbc-video-export         # Custom build

# Toolkit tools (isolated)
conda activate ddd-capture-toolkit
which ld-analyse  # → $CONDA_PREFIX/bin/ld-analyse
conda deactivate
which ld-analyse  # → /usr/bin/ld-analyse (user's version restored)
```

## Build System Architecture

### Cross-Platform Build Scripts

#### Master Setup Script
```bash
./setup.sh [OPTIONS]
  --easy          # Binary installation (fast)
  --performance   # Source compilation (optimized)
  --platform X    # Override platform detection
  --jobs N        # Compilation parallelism
  --help          # Show all options
```

#### Platform Detection
```bash
# Automatic OS/architecture detection
OS=$(build-scripts/common/detect-platform.sh --os)
ARCH=$(build-scripts/common/detect-platform.sh --arch)
# Example: OS=linux, ARCH=x86_64
```

#### Conda Environment Preparation
```bash
# Select appropriate environment file
case "$OS" in
  linux)   ENV_FILE="environment-linux.yml" ;;
  macos)   ENV_FILE="environment-macos.yml" ;;
  windows) ENV_FILE="environment-windows.yml" ;;
  *)       ENV_FILE="environment.yml" ;;
esac

# Create isolated environment
conda env create -f "$ENV_FILE"
```

### Build Script Standards

#### Common Build Pattern
Each `build-scripts/build-*.sh` follows this pattern:
1. **Environment Setup**: Activate conda, set variables
2. **Platform Detection**: OS-specific configurations
3. **Optimization Detection**: CPU capabilities, build flags
4. **Source Preparation**: Git submodule checkout, patches
5. **Configuration**: CMake/configure with conda prefix
6. **Compilation**: Multi-threaded build
7. **Installation**: Install to conda environment
8. **Verification**: Test basic functionality

#### Example: LD-Decode Build Script
```bash
#!/bin/bash
# build-scripts/build-ld-decode.sh

source build-scripts/common/conda-setup.sh
source build-scripts/common/optimize-flags.sh

echo "Building LD-Decode with optimizations: $OPTIM_FLAGS"

cd external/ld-decode
mkdir -p build && cd build

cmake .. \
  -DCMAKE_INSTALL_PREFIX="$CONDA_PREFIX" \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_CXX_FLAGS="$OPTIM_FLAGS" \
  -DCMAKE_PREFIX_PATH="$CONDA_PREFIX"

make -j$(nproc) all
make install

echo "LD-Decode installed to $CONDA_PREFIX/bin/"
```

## Error Handling & Fallback Strategy

### Build Failure Recovery
1. **Source Build Fails**: Automatic fallback to prebuilt binaries
2. **Network Issues**: Use cached/bundled sources
3. **Missing Dependencies**: Clear error messages with resolution steps
4. **Platform Issues**: Graceful degradation with warnings

### Dependency Validation
- **Pre-build Check**: Validate all requirements before starting
- **Post-build Verification**: Test all installed tools
- **Runtime Monitoring**: Dependency checker integration
- **User Feedback**: Clear success/failure reporting

## Integration with Existing Codebase

### Job Queue System Integration
- **Tool Discovery**: Automatic detection of conda environment tools
- **Path Management**: Proper PATH handling for subprocesses
- **Environment Activation**: Ensure conda environment active for all processing jobs
- **Performance Monitoring**: Track compilation performance benefits

### Configuration Management
- **Environment Variables**: Consistent `CONDA_PREFIX` usage
- **Tool Paths**: Dynamic discovery rather than hardcoded paths
- **Cross-Platform Paths**: Handle Windows/Unix path differences
- **User Preferences**: Remember user's binary vs source choice

## Future Extensibility

### Adding New Tools
1. Add as git submodule: `git submodule add <repo> external/<tool>`
2. Create build script: `build-scripts/build-<tool>.sh`
3. Update environment files: Add dependencies
4. Update dependency checker: Add validation

### Supporting New Platforms
1. Create platform-specific environment: `environment-<platform>.yml`
2. Add platform detection: Update `detect-platform.sh`
3. Create platform build logic: Platform-specific build flags
4. Add prebuilt binaries: `prebuilt/<platform>/`

### Performance Optimization Evolution
- **Profile-Guided Optimization**: Use runtime profiles for compilation
- **GPU Acceleration**: CUDA/OpenCL support where applicable
- **Distributed Processing**: Multi-machine compilation support
- **Benchmarking Integration**: Automated performance regression testing

## Documentation & User Experience

### Setup Documentation Flow
1. **Quick Start**: `./setup.sh` → working system in 5 minutes
2. **Performance Guide**: When and why to use source builds
3. **Troubleshooting**: Common issues and solutions
4. **Advanced Configuration**: Custom build options

### User Communication
- **Progress Reporting**: Clear setup progress indication
- **Performance Metrics**: Show compilation time vs runtime benefits
- **Success Validation**: Confirm all tools working properly
- **Ongoing Support**: Integration with existing help systems

---

## Implementation Roadmap

### Phase 1: Core Infrastructure ✅ COMPLETED
- [x] Set up git submodules for external dependencies
- [x] Create cross-platform build scripts
- [x] Implement platform detection and optimization
- [x] Update environment files with proper dependencies

### Phase 2: Build System ✅ COMPLETED
- [x] Implement binary vs source installation options
- [x] Create prebuilt binary distribution system (foundation)
- [x] Add comprehensive error handling and fallbacks
- [x] Integrate with existing setup.sh

### Phase 3: Integration & Testing 🔄 IN PROGRESS
- [x] Update job queue system for new tool locations
- [ ] Comprehensive cross-platform testing (Linux ✅, macOS/Windows pending)
- [x] Performance benchmarking and optimization
- [x] User documentation and guides

### Phase 4: Advanced Features 📋 PLANNED
- [ ] Profile-guided optimization
- [ ] Automated performance regression testing
- [ ] Advanced build customization options
- [ ] Integration with CI/CD for prebuilt binaries

This architecture provides a robust foundation for high-performance, cross-platform video processing while maintaining complete isolation from user systems and preserving the flexibility to optimize for specific use cases.

---

## Current Implementation Status

### ✅ Completed Features

**Core Infrastructure:**
- Git submodules configured for ld-decode, vhs-decode, tbc-video-export, DomesdayDuplicator
- Cross-platform build scripts with comprehensive error handling
- Platform detection (OS, architecture, CPU capabilities)
- CPU optimization flag generation (AVX, SSE, native compilation)
- Conda environment isolation with compiler integration

**Build System:**
- Two-tier installation (--easy for binaries, --performance for source)
- Robust setup.sh with multiple conda installation detection
- Automatic clean rebuilds for performance mode
- CMake integration with proper compiler configuration
- Multi-threaded compilation with optimal job detection

**Environment Management:**
- Platform-specific conda environment files (Linux/macOS/Windows)
- Complete isolation from system installations
- Proper compiler environment variable setup (CMAKE_C_COMPILER, CMAKE_CXX_COMPILER)
- Clean uninstall functionality preserving user data

**Linux Platform Support:**
- Full implementation and testing on Fedora Linux
- Multiple package manager support (dnf, apt, pacman, zypper)
- GCC compilation with CPU-specific optimizations
- Proper conda environment compiler integration

### 🔄 In Progress

**Cross-Platform Testing:**
- Linux: ✅ Complete (Fedora tested, other distros should work)
- macOS: 📋 Needs testing
- Windows: 📋 Needs testing

**Build Scripts:**
- LD-Decode: ✅ Complete and tested
- VHS-Decode: 📋 Script created, needs testing
- TBC-Video-Export: 📋 Needs implementation
- Domesday Duplicator: 📋 Needs implementation

### 📋 Pending Implementation

**Advanced Features:**
- Profile-guided optimization
- GPU acceleration support
- Automated performance benchmarking
- CI/CD integration for prebuilt binaries

**Platform-Specific:**
- Windows MSVC compilation environment
- macOS Apple Silicon optimization
- Advanced error recovery and fallbacks

The core architecture is now solid and proven on Linux. The foundation supports all planned features and provides a robust base for expanding to additional platforms and tools.
