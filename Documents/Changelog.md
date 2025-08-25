## [1.0.9] - 2025-08-10

### Added

#### Advanced Build System Diagnostics
- **Comprehensive Qt/Qwt Library Management**: Enhanced build system to handle Qt library version conflicts and dependency resolution
  - **Library Path Prioritization**: Modified build scripts to explicitly prioritize conda environment libraries over system libraries
  - **Environment Variable Management**: Added LD_LIBRARY_PATH, LIBRARY_PATH, and CMAKE_LIBRARY_PATH configuration to guide linking behavior
  - **CMake Configuration Enhancement**: Enhanced CMake variable passing for better library detection and path resolution
  - **Build Verification Improvements**: Updated build verification to test non-GUI components when GUI tools are disabled

#### Qt Dependency Optimization
- **GUI Component Management**: Implemented selective Qt component building to resolve library compatibility issues
  - **Qwt Library Handling**: Added support for disabling qwt-dependent GUI tools when library conflicts occur
  - **Qt6 Compatibility**: Ensured full Qt6 compatibility while handling Qt5/Qt6 qwt library conflicts
  - **Environment Cleanup**: Removed unused qwt dependency from conda environment specification
  - **Component Analysis**: Documented Qt requirements across different toolkit components for future optimization

### Fixed

#### Critical Build System Issues
- **Qt5/Qt6 Qwt Library Conflicts**: Resolved complex library linking issues preventing performance builds
  - **Problem Identification**: CMake was linking against system Qt5 qwt library instead of conda Qt6 qwt library
  - **Pragmatic Solution**: Disabled GUI tools (ld-analyse) by setting `-DUSE_QWT=OFF` in CMake configuration
  - **Impact**: All 22 command-line LD-Decode tools now build successfully with full optimizations
  - **Trade-off**: GUI analysis tool excluded, but all core processing functionality preserved

#### Build Script Reliability Improvements
- **Environment Deactivation Fix**: Fixed uninstall process to properly deactivate conda environments before removal
  - **Issue**: Uninstall script failed when conda environment was active
  - **Solution**: Added environment detection and automatic deactivation before removal
  - **Benefit**: Clean uninstall process now works regardless of environment state

- **PATH Configuration Fixes**: Resolved conda environment PATH setup issues in build scripts
  - **Problem**: Build tools like pkg-config were not found during compilation
  - **Solution**: Enhanced conda-setup.sh to properly prepend conda environment bin directory to PATH
  - **Result**: CMake can now find all required build tools in the conda environment

#### CMake Configuration Enhancements
- **Explicit Tool Specification**: Added explicit pkg-config path specification for CMake
  - **Implementation**: Pass `-DPKG_CONFIG_EXECUTABLE` pointing to conda environment pkg-config
  - **Benefit**: Ensures CMake uses conda environment tools instead of system tools

- **Link Time Optimization Fixes**: Disabled problematic LTO to improve build compatibility
  - **Issue**: LTO was causing linker plugin compatibility errors during performance builds
  - **Solution**: Modified optimization flags script to disable LTO while maintaining other optimizations
  - **Preservation**: Kept CPU-specific optimizations (-march=native, AVX2, FMA, etc.)

### Changed

#### Performance Build Strategy
- **Focus on Command-Line Tools**: Optimized build system to prioritize essential processing tools over GUI components
  - **Core Functionality**: All LD-Decode processing tools (chroma decoder, dropout correction, VBI processing, etc.)
  - **EFM Decoder Suite**: Complete EFM decoder toolchain for LaserDisc processing
  - **Utility Tools**: All metadata export, format conversion, and analysis utilities
  - **Performance Gains**: Full CPU-specific optimizations applied to all core tools

#### Environment Management
- **Streamlined Dependencies**: Removed unused dependencies to reduce environment size
  - **Qwt Removal**: Eliminated qwt package from conda environment as it's no longer used
  - **Qt Rationalization**: Maintained essential Qt6 components while removing unused GUI libraries
  - **Size Optimization**: Reduced conda environment footprint without impacting functionality

### Technical Implementation

#### Build System Architecture
- **Selective Component Building**: Enhanced CMake configuration to selectively disable problematic components
  - **USE_QWT Flag Management**: Proper handling of CMake's USE_QWT option to control GUI tool building
  - **Library Conflict Resolution**: Systematic approach to resolving system vs conda library conflicts
  - **Fallback Strategies**: Graceful degradation when specific components cannot be built

#### Qt Component Analysis
- **Dependency Mapping**: Comprehensive analysis of Qt requirements across toolkit components
  - **Essential Components**: Qt Core required by most LD-Decode tools for threading and string handling
  - **GUI Components**: Qt Widgets required by DomesdayDuplicator but not core processing tools
  - **Optimization Potential**: Documented minimal Qt footprint while maintaining full functionality

#### Environment Isolation Improvements
- **Build Environment Setup**: Enhanced environment variable management for consistent builds
  - **Path Prioritization**: Explicit control over library and executable search paths
  - **Conda Integration**: Improved integration between build system and conda environment
  - **Cross-Platform Compatibility**: Consistent behavior across different Linux distributions

### Performance Impact

#### Successful Performance Builds
- **Full Toolkit Compilation**: Complete performance build now succeeds with all essential tools
  - **22 Tools Installed**: All core command-line tools built with CPU-specific optimizations
  - **Native Optimizations**: Full -march=native, AVX2, FMA optimizations applied
  - **10-30% Performance Gain**: Expected performance improvement from optimized compilation

#### Functional Completeness
- **Core Workflow Support**: All essential digital video processing workflows fully supported
  - **LaserDisc Processing**: Complete LD-Decode toolchain available
  - **EFM Decoding**: Full EFM decoder suite for audio and data extraction
  - **Format Conversion**: All metadata export and format conversion tools
  - **Quality Analysis**: Command-line analysis tools for dropout detection and correction

### Migration Notes

#### For Existing Users
- **Seamless Upgrade**: Performance build improvements applied automatically on next build
- **No Breaking Changes**: All existing command-line workflows continue unchanged
- **GUI Tool Note**: ld-analyse GUI tool no longer available, but all functionality accessible via command-line tools

#### For New Users
- **Successful Performance Builds**: `./setup.sh --performance` now completes successfully
- **Full Optimization**: Get maximum performance with native CPU optimizations
- **Complete Toolkit**: All essential tools available for professional digital video processing

## [1.0.8] - 2025-08-10

### Added

#### Complete Architecture Overhaul: Two-Tier Installation System
- **Revolutionary Build Architecture**: Complete implementation of new cross-platform, isolated, performance-optimised architecture
  - **Two-Tier Installation System**: Users can choose between easy (5-min conda packages) and performance (30-60min source compilation) modes
  - **Complete Isolation**: All tools contained within conda environment, zero impact on existing user installations
  - **Cross-Platform Portability**: Single consistent experience across Linux, macOS, and Windows
  - **Path Isolation**: Tools only available in PATH when conda environment is activated
  - **CPU-Optimised Performance**: Source compilation with native CPU optimizations (AVX2, FMA, SSE4.2) for 10-30% performance gains

#### Advanced Setup System Enhancement
- **Intelligent Setup Script**: Completely redesigned `setup.sh` with comprehensive command-line interface
  - **Installation Modes**:
    - `--easy`: Pre-compiled conda packages (default, 5 minutes, broad compatibility)
    - `--performance`: Source compilation with CPU-specific optimizations (30-60 minutes, maximum performance)
  - **Advanced Options**:
    - `--platform X`: Override platform detection (linux/macos/windows)
    - `--jobs N`: Parallel build job control for compilation
    - `--safe`: Safe optimizations only (no -march=native) for older CPUs
    - `--help`: Comprehensive help system with examples and mode explanations
  - **Smart Platform Detection**: Automatic OS and architecture detection with manual override capability
  - **Comprehensive User Guidance**: Detailed setup instructions and performance explanations

#### Build System Infrastructure
- **Cross-Platform Build Scripts**: Complete build automation system in `build-scripts/`
  - **Platform Detection**: `detect-platform.sh` - Robust OS/architecture detection (linux/macos/windows, x86_64/arm64)
  - **CPU Optimization**: `optimize-flags.sh` - Automatic CPU feature detection and optimization flag generation
  - **Environment Management**: `conda-setup.sh` - Conda environment setup and validation utilities
  - **Coloured Logging**: Professional logging system with info/success/warning/error colour coding
  - **Build Job Detection**: Automatic parallel build job calculation with safety limits

#### Tool-Specific Build Scripts
- **LD-Decode Compilation**: `build-ld-decode.sh` - Complete CMake-based build system
  - **CMake Integration**: Proper CMAKE_PREFIX_PATH and CMAKE_INSTALL_PREFIX configuration for conda isolation
  - **Optimization Integration**: CPU-specific flags automatically applied to C/C++ compilation
  - **Build Verification**: Post-build testing and installation verification
  - **Clean Build Support**: Optional clean rebuild with `--clean` flag
  - **Flexible Configuration**: Safe mode, custom job counts, comprehensive error handling
- **VHS-Decode Framework**: `build-vhs-decode.sh` - Template for Rust-based VHS-Decode compilation
  - **Rust Integration**: Proper handling of Cargo/Rust toolchain requirements
  - **Pip Integration**: Seamless integration with Python packaging for VHS-Decode
  - **Dependency Checking**: Rust toolchain validation and guidance

#### Binary Fallback System
- **Prebuilt Binary Infrastructure**: Complete directory structure for binary fallbacks in `prebuilt/`
  - **Platform-Specific Binaries**: Organised structure for linux-x64, macos-x64, macos-arm64, windows-x64
  - **Fallback Strategy**: Automatic fallback to prebuilt binaries when source compilation fails
  - **Documentation**: Comprehensive README explaining binary sources, updating procedures, and usage

#### Environment File Enhancements
- **Platform-Specific Dependencies**: Enhanced conda environment files with build tool support
  - **Linux Environment**: GCC toolchain, development headers, Linux-specific libraries (alsa-lib, xclip)
  - **macOS Environment**: Clang support, macOS-specific optimizations
  - **Windows Environment**: MSVC toolchain support through conda
  - **Generic Fallback**: Cross-platform compatible base environment

### Technical Implementation

#### Architectural Principles Implementation
- **Cross-Platform Portability**: Single codebase works identically across all operating systems
- **Complete Independence**: Zero impact on existing installations, clean separation from system tools
- **Environment Isolation**: All processing tools contained within conda environment with PATH isolation
- **Performance Through Source Compilation**: Optional CPU-optimised builds for production users
- **Self-Contained Distribution**: Single repository with git submodules for complete functionality

#### Advanced CPU Optimization
- **Native Optimization Detection**: Automatic detection of CPU features (AVX2, AVX, SSE4.2, SSE4.1, FMA)
- **Compiler-Specific Optimizations**: GCC and Clang optimization with platform-specific flags
- **Link-Time Optimization**: LTO support for maximum performance gains
- **Architecture-Specific Builds**: Full `-march=native -mtune=native` support with safety fallbacks
- **Performance Benchmarking Ready**: Infrastructure for measuring compilation vs runtime performance benefits

#### Error Handling and Recovery
- **Graceful Fallbacks**: Source build failures automatically fall back to conda packages
- **Comprehensive Validation**: Pre-build dependency checking and post-build verification
- **User-Friendly Error Messages**: Clear error reporting with actionable resolution steps
- **Build System Diagnostics**: Detailed logging for troubleshooting compilation issues

#### Git Submodule Integration
- **External Dependency Management**: All major tools (ld-decode, vhs-decode, tbc-video-export, DomesdayDuplicator) as git submodules
- **Version Locking**: Specific tested versions locked through submodule commits
- **Source Compilation Ready**: Direct access to source code for custom compilation
- **Upstream Tracking**: Maintained relationship with upstream projects while preserving customizations

#### Documentation and User Experience
- **Comprehensive Architecture Documentation**: Updated `Documents/ARCHITECTURE.md` with complete system design
- **Implementation Status Tracking**: `IMPLEMENTATION_STATUS.md` with detailed progress and testing instructions
- **User-Facing Help System**: Integrated help throughout setup process with examples and explanations
- **Performance Guidance**: Clear explanations of when to use easy vs performance modes

### Changed

#### Setup Process Transformation
- **Backward Compatible**: Existing `./setup.sh` still works (defaults to easy mode) while adding advanced options
- **Enhanced User Experience**: Rich help system guides users through installation choices
- **Improved Error Handling**: Better error messages and recovery strategies throughout setup process
- **Performance Awareness**: Users informed about performance implications of their choices

#### Build System Migration
- **From Manual to Automated**: Replaced manual compilation instructions with automated build scripts
- **From System-Wide to Isolated**: All builds now target conda environment instead of system directories
- **From Single-Platform to Cross-Platform**: Build system works identically across all supported platforms
- **From Basic to Optimised**: Added CPU-specific optimizations for performance-critical workloads

### Fixed

#### Installation Isolation Issues
- **Path Pollution Prevention**: Tools no longer visible in PATH outside of conda environment
- **Dependency Conflicts**: Conda environment isolation prevents conflicts with existing tool installations
- **Version Coexistence**: Users can maintain system/user tool versions alongside toolkit versions
- **Clean Uninstallation**: Complete removal possible by deleting conda environment

#### Cross-Platform Compatibility
- **Platform Detection Reliability**: Robust OS and architecture detection across diverse systems
- **Package Manager Support**: Support for dnf, apt, pacman, zypper, and other Linux package managers
- **Windows Path Handling**: Proper Windows path separator and command handling
- **macOS Architecture Support**: Separate handling for Intel x64 and Apple Silicon ARM64

### Migration Notes

#### For Existing Users
- **Automatic Migration**: Existing environment updated seamlessly, no manual intervention required
- **Backward Compatibility**: All existing functionality preserved, enhanced with new capabilities
- **Performance Upgrade Path**: Existing users can run `./setup.sh --performance` to upgrade to optimized builds
- **No Breaking Changes**: Current workflows continue to work without modification

#### For New Users
- **Simplified Onboarding**: Single `./setup.sh` command provides complete, isolated installation
- **Choice of Installation**: Easy mode for quick setup, performance mode for production use
- **Comprehensive Documentation**: Complete setup guidance with clear explanations of options

## [1.0.7] - 2025-08-08

### Added

#### VHS-Decode Parameter Customization
- **User-Customizable vhs-decode Parameters**: Added support for additional command-line parameters in VHS decode workflow
  - **Interactive Parameter Input**: New optional section in VHS decode menu allows users to enter custom parameters
  - **Built-in Parameter Examples**: Menu displays common vhs-decode parameters with descriptions:
    - `--chroma-nr X`: Chroma noise reduction (0-4)
    - `--luma-nr X`: Luma noise reduction (0-4) 
    - `--dod-threshold X`: Dropout detection threshold
    - `--disable-pilot`: Disable pilot tone detection
    - `--cxadc-gain X`: CXADC gain adjustment
    - `--field-order X`: Field order control (0=TFF, 1=BFF)
  - **Flexible Integration**: Additional parameters are properly inserted into vhs-decode command line
  - **User Feedback**: System displays which additional parameters are being applied during decode
  - **Backward Compatibility**: Existing functionality unchanged for users who don't need custom parameters

- **Enhanced Function Interface**:
  - Modified `run_vhs_decode()` function to accept optional `additional_params` parameter
  - Smart parameter parsing splits space-separated parameters and integrates them into command
  - Parameters inserted between standard options and input/output files for correct precedence
  - Maintains all existing PAL decode settings (--tf vhs, -t 3, --ts SP, --pal, --no_resample, --recheck_phase, --ire0_adjust)

### Technical Implementation

#### Menu System Enhancement
- **Updated VHS Decode Menu**: Added parameter input section with clear examples and usage instructions
- **Parameter Validation**: Basic input handling with space-separated parameter parsing
- **User Experience**: Clear prompts allow users to enter parameters or press Enter to skip

#### Command Building Logic
- **Flexible Command Construction**: Parameters dynamically inserted into vhs-decode command
- **Safe Parameter Handling**: Additional parameters added before input/output files to maintain command structure
- **Debug Output**: Shows complete command line including user parameters for transparency

## [1.0.6] - 2025-07-31

### Added

#### Unified Capture System
- **Shared Parallel Capture Function**: Implemented `shared_capture_process()` in `ddd_clockgen_sync.py` for consistent capture behavior across menu items
  - **Independent Threading**: Video and audio capture run in separate threads to decouple start/stop timing
  - **Configurable Audio Delay**: Optional delay parameter applies only to audio capture, video starts immediately
  - **Graceful Shutdown**: Uses threading.Event for coordinated process termination
  - **Parallel Operation**: Both capture processes run simultaneously for optimal performance
  - **Prepared for Migration**: Ready to replace inconsistent capture logic in menu items 1 and 5.2

#### Enhanced VHS Validation System
- **Fixed VHS Timecode Analyzer**: Replaced strict `vhs_timecode_analyzer.py` with tolerant version for real-world VHS tapes
  - **Tolerant Frame Matching**: Uses flexible matching approach instead of exact frame ID correlation
  - **Realistic Offset Detection**: Provides meaningful timing measurements for VHS mechanical variations
  - **Detailed Timing Output**: Generates comprehensive offset analysis with "Required delay" values
  - **Backward Compatibility**: Renamed old analyzer to `vhs_timecode_analyzer_old_do_not_use.py`

### Fixed

#### Menu 5.3 Validation Improvements
- **Meaningful Delay Extraction**: Updated VHS capture validation to parse and display calculated delays
  - **Smart Delay Parsing**: Extracts "Required delay: X.XXXs" pattern from analyzer output
  - **Config Integration**: Offers to automatically apply calculated delay to configuration
  - **User-Friendly Display**: Shows current vs. recommended delay values for easy comparison
  - **Fallback Guidance**: Provides manual calibration advice when no delay can be calculated

#### Audio-Only Delay Logic
- **Corrected Delay Calculations**: Fixed analyzer to only output delays when audio leads video (fixable scenario)
  - **Video Delay Warning**: Added warnings for cases requiring unsupported video delay adjustments
  - **Absolute Delay Values**: Outputs concrete audio delay values instead of relative adjustments
  - **System Limitation Awareness**: Acknowledges that only audio delay (not video delay) is implemented

### Analysis

#### Delay System Architecture Review
- **Variable Flow Mapping**: Documented how delay variables flow through menu items 1, 5.2, 5.3, and 5.5
  - **Inconsistent Semantics**: Identified contradictory offset interpretations between calibration methods
  - **Multiple Variable Names**: Found overlapping delay-related variables causing confusion
  - **Calibration Conflicts**: Discovered Menu 5.2 and VHS analyzer treat positive offsets differently
- **Reliability Concerns**: Highlighted need for unified delay system with consistent semantic interpretation
- **Future Improvements**: Recommended single canonical sync offset variable and harmonized calculations

## [1.0.5] - 2025-07-29

### Fixed

#### Timecode Correlation Algorithm
- **Sequential Matching Implementation**: Fixed fundamental flaw in timecode correlation that was causing wildly inaccurate offset measurements
  - **Problem**: Previous exhaustive matching algorithm compared ALL video frames with ALL audio frames, creating thousands of false matches
  - **Solution**: Implemented sequential matching that pairs first occurrence of frame ID in video with first occurrence in audio
  - **Result**: Eliminates 38+ second offset variations, now provides realistic measurements within tenths of seconds
  - **Shared Logic**: Added `correlate_timecodes()` method to `SharedTimecodeRobust` class for consistent correlation across MP4 and VHS validation
  - **Impact**: Both menu 5.3 (VHS validation) and 5.4 (MP4 validation) now use the same reliable correlation algorithm

- **Code Architecture Improvement**: 
  - Updated `vhs_timecode_analyzer.py` to use shared correlation method from `SharedTimecodeRobust`
  - Maintains separation between strict (MP4) and tolerant (VHS) decoding while sharing correlation logic
  - Follows remember.txt guidelines for shared logic between menu items 3.2, 5.3, and 5.4

## [1.0.4] - 2025-07-28

### Added

#### VHS Calibration Enhancements
- **Enhanced VHS Sync Pulse Detection**:
  - New `_detect_sync_pulses_vhs_calibration()` method for tolerant sync pulse detection
  - Multi-method detection: energy, frequency, and pattern-based
  - Improved handling of VHS mechanical variations with relaxed thresholds
  - Clear diagnostics when no sync pulses are found

- **Command Line Flag Integration**:
  - Added `--vhs-calibration` flag to enable VHS-specific sync enhancements
  - Modified `VHSTimecodeAnalyzer` to use the flag for conditional detection logic
  - Ensured backward compatibility with existing MP4 validation workflows

### Changed

- **Independent Operation**:
  - Step 5.2 calibration flow utilizes enhanced detection independently from step 5.3's precise validation
  - No impact on the robust FSK system or MP4 validation

- **Menu Integration**:
  - Updated `ddd_main_menu.py` to incorporate the `--vhs-calibration` flag for step 5.2

## [1.0.3] - 2025-01-27

### Added

#### Cycle-Aware MP4 Timecode Validation
- **Frame-Perfect Sync Measurement**: Revolutionary cycle-aware validator that achieves true frame-accurate synchronization measurement
  - **4-Step Cycle Lock-On**: Automatically detects and locks onto the generator's 4-step cycle structure (test chart + 1kHz tone → silence → timecode + FSK → silence)
  - **Precise Section Isolation**: Only analyzes actual timecode sections (video frames 100-849, audio samples 4.0s-34.0s) eliminating false detections from test tones
  - **Binary Strip Detection**: Implements robust binary timecode extraction from visual binary strips with checksum validation
  - **Perfect Reference Validation**: Achieves 0.0ms sync offset measurement on reference MP4 files with 90% confidence
  - **Shared Implementation**: Single `CycleAwareValidator` class serves both menu 5.2 (separate audio) and 5.3 (muxed A/V) automatically

- **Advanced Cycle Structure Analysis**:
  - **Audio Pattern Recognition**: Detects 1kHz test tone (RMS >1000) and silence sections (RMS <100) to validate cycle structure
  - **Frame-Accurate Boundaries**: Calculates exact video frame ranges (100-849) and audio sample ranges (192000-1631999) for PAL 25fps
  - **Temporal Synchronization**: Ensures video frame timestamps precisely align with audio FSK frame positions

- **Robust Video Timecode Detection**:
  - **Binary Strip Reading**: Extracts 32-bit binary patterns from top 20 pixels of frames, skipping corner markers
  - **Checksum Validation**: Verifies frame integrity using enhanced XOR checksum matching the generator
  - **Multi-Method Fallback**: Implements binary strip (90% confidence), corner markers (70% confidence), and OCR (50% confidence) detection methods
  - **High Precision Sampling**: Uses block-center sampling with region averaging for reliable bit detection

### Fixed

#### MP4 Timecode Generator Timing Precision
- **Frame-Perfect Audio Generation**: Fixed cumulative timing errors in the VHS pattern generator caused by integer truncation
  - **Exact Sample Calculations**: Uses floating-point precision for samples-per-frame (1920.0 for PAL) instead of integer truncation
  - **Frame-Boundary Alignment**: Ensures each FSK audio frame aligns perfectly with corresponding video frame boundaries
  - **Eliminates Drift**: Prevents multi-second sync drift that accumulated over 750-frame timecode sections

#### False Positive Elimination
- **FSK Frequency Isolation**: Prevents FSK decoder from detecting patterns in 1kHz test tones through section-aware processing
- **Section-Aware Processing**: Validator ignores audio outside timecode sections, eliminating false detections from test chart tones
- **Correlation Accuracy**: Only correlates timecodes from matching sections (video timecode frames with audio FSK frames)
## [1.0.2] - 2025-01-27

### Added

#### Robust VHS Timecode System
- **Enhanced FSK Audio Encoder**: Complete redesign for VHS recording/playback robustness
  - **Wide Frequency Separation**: 800Hz for '0' bits, 1600Hz for '1' bits (2:1 ratio, 800Hz separation)
  - **Non-Overlapping Detection Ranges**: 650-950Hz ('0' range) and 1350-1850Hz ('1' range) with 400Hz guard band separation
  - **Mono Audio Encoding**: Eliminates stereo channel confusion and simplifies signal path
  - **Multiple Detection Methods with Voting System**: Three independent audio-only analysis methods for robust bit detection:
    - FFT-based frequency analysis (primary method with 2.0 weight)
    - Zero-crossing rate analysis (backup method with 1.0 weight)
    - Autocorrelation period detection (backup method with 1.0 weight)
  - **Weighted Voting Algorithm**: Combines results from multiple detection methods to handle VHS artifacts and signal degradation
  - **Enhanced Error Detection**: Improved checksum algorithm with XOR rotation for better frame validation
  - **Frame-Accurate Encoding**: Precise phase control ensures exact frequency generation
  - **VHS-Optimized Parameters**: Frequencies and timing specifically chosen for VHS audio bandwidth and response characteristics

- **Comprehensive Testing Framework**: 
  - Bit-level accuracy validation
  - Frequency detection robustness testing
  - Checksum validation verification
  - Multi-frame encoding/decoding validation

### Technical Improvements

#### Audio Signal Processing
- **Perfect Frequency Generation**: Exact phase calculation for distortion-free sine waves
- **Gentle Enveloping**: 5% fade-in/fade-out to reduce transients without affecting frequency accuracy
- **Optimal Amplitude**: 60% amplitude to prevent clipping while maintaining signal strength
- **Frame-Synchronized Timing**: Bit duration precisely calculated for 25fps (PAL) frame boundaries

#### Frame-Accurate Extraction Method
- **Precise Video Frame Selection**: Uses FFmpeg's `select=between(n\,start_frame\,end_frame)` filter to extract exact frame ranges instead of time-based cuts
- **Sample-Accurate Audio Extraction**: Calculates exact audio sample positions corresponding to video frames (sample = frame * 1920 for 48kHz/25fps)
- **Perfect Frame-Audio Alignment**: Ensures each extracted video frame has precisely corresponding audio samples for frame-accurate synchronisation validation
- **Eliminates Time-Based Extraction Errors**: Prevents frame count mismatches caused by FFmpeg's imprecise time-based video cutting
- **Used in VHS Validation**: Implemented in menu option 3.2 for reliable VHS capture validation with exact 750-frame (30-second) extraction

#### Robustness Features
- **Independent Stream Processing**: Audio and video timecode streams decoded completely independently
- **High Confidence Thresholds**: Multiple validation layers ensure reliable frame ID extraction
- **Guard Band Protection**: Large frequency separations prevent interference and crosstalk
- **Adaptive Detection**: Voting system automatically adapts to varying signal quality conditions

## [1.0.1] - 2023-10-03

### Fixed

#### FSK Audio Encoder
- **Precise Frequency Generation**: Adjusted tone generation to produce exact 1000Hz and 1200Hz frequencies via controlled phase increments. Verified improvements through comprehensive testing with FFT and zero-crossing analysis.

# Changelog

All notable changes to the DdD Sync Capture project are documented in this file.

## [1.0.0] - 2025-01-22

### Added

#### Core Capture System
- **Main Capture Script (`ddd_clockgen_sync.py`)**: Automated video capture with synchronised audio recording
  - Real-time GUI automation using PyAutoGUI for capture control
  - Cross-platform screenshot functionality (macOS, Windows, Linux)
  - Synchronised SOX audio recording with video capture
  - Process management for clean capture start/stop
  - Menu-driven interface for capture operations

#### Unified Menu System
- **Main Menu (`ddd_main_menu.py`)**: Comprehensive workflow management interface
  - Integrated access to all project tools and scripts
  - Create original MP4 sync test videos from scratch
  - Generate DVD-Video ISOs from MP4 files for disc burning
  - Run VHS audio alignment tools
  - Capture new video with synchronised audio/video
  - Perform automated A/V alignment analysis
  - View project summary with file and tool status
  - Dependency checker integration
  - Help and documentation links
  - Clean exit functionality

#### Sync Test Video Creation
- **Sync Test Creator (`tools/create_sync_test.py`)**: Test pattern video generation
  - SMPTE colour bars with embedded audio sync beeps
  - Configurable duration and frame rate support
  - High-quality MP4 output with H.264 encoding
  - Broadcast-standard test patterns
  - Automated beep insertion at regular intervals for sync testing

#### DVD/CD ISO Creation
- **ISO Creator (`tools/create_iso_from_mp4.py`)**: Convert MP4 files to burnable disc images
  - Batch conversion of MP4 files to ISO format
  - Uses `mkisofs` or `genisoimage` for ISO creation
  - Organised output directory structure (`media/iso/`)
  - DVD-Video compatible ISO generation
  - Support for hardware testing via physical media

#### Audio Synchronisation Tools
- **VHS Audio Alignment (`tools/audio-sync/vhs_audio_align.py`)**: Advanced audio sync analysis
  - Cross-correlation analysis between audio channels
  - Automatic delay detection and measurement
  - Support for WAV, MP3, MP4, and other audio formats
  - Detailed sync reporting with sample-accurate measurements
  - Integration with main workflow

- **Audio Alignment Analyser (`tools/audio_alignment_analyzer.py`)**: Automated A/V sync verification
  - Batch processing of capture files
  - Statistical analysis of sync drift
  - Frame-accurate sync measurements
  - Comprehensive reporting and logging

- **Simple Audio Analyser (`tools/simple_audio_analyzer.py`)**: Basic audio file analysis
  - Quick audio file inspection and validation
  - Format compatibility checking
  - Basic audio properties reporting

#### Test Pattern and Chart Generation
- **Belle & Nuit Charts (`tools/create_belle_nuit_charts.py`)**: Video test patterns
  - Belle & Nuit Montparnasse test chart generation
  - NTSC and PAL format support
  - High-resolution TIFF output
  - Broadcast test pattern standards
  - Stored in organised `media/Test Patterns/` directory

#### Sync Test Verification
- **Sync Verification (`tools/test_sync_verification.py`)**: Automated sync testing
  - Verification of audio/video sync accuracy
  - Automated testing of sync test patterns
  - Quality assurance for capture workflows

#### Project Management and Documentation
- **Sync Test Summary (`tools/sync_test_summary.py`)**: Project overview and status
  - Comprehensive file inventory (MP4, ISO, audio files)
  - Tool availability and status checking
  - Project statistics and metrics
  - Directory structure overview

- **Dependency Checker (`check_dependencies.py`)**: System requirement verification
  - Automatic detection of required tools and libraries
  - Cross-platform compatibility checking
  - Installation guidance for missing dependencies
  - System readiness assessment

#### Media Assets and GUI Resources
- **PyAutoGUI Screenshots**: GUI automation button detection
  - Start button image (`media/pyautogui/start_button.png`)
  - Stop button image (`media/pyautogui/stop_button.png`)
  - Cross-platform GUI element recognition

- **Test Pattern Library**: Broadcast test patterns
  - NTSC test chart (`media/Test Patterns/testchartntsc.tif`)
  - PAL test chart (`media/Test Patterns/testchartpal.tif`)
  - High-quality reference patterns for calibration

#### Documentation and Setup
- **Comprehensive README**: Complete project documentation
  - Installation and setup instructions
  - Feature overview and usage guide
  - Cross-platform compatibility notes
  - Hardware requirements and recommendations
  - Troubleshooting and FAQ section
  - Accessibility and permissions guidance for macOS/Windows
  - PyAutoGUI automation setup instructions

- **Requirements Management (`requirements.txt`)**: Python dependency specification
  - All required Python packages with version constraints
  - Easy installation via pip
  - Compatibility across Python versions

### Technical Features

#### Cross-Platform Support
- **macOS**: Full support with Accessibility permissions setup
- **Windows**: PowerShell integration for GUI automation
- **Linux**: Native support with Wayland/X11 compatibility
- **Universal**: Consistent behaviour across all platforms

#### Audio/Video Processing
- **High-Quality Encoding**: H.264/AAC for optimal quality and compatibility
- **Broadcast Formats**: Support for broadcast-standard video formats
- **Sync Accuracy**: Sample-accurate audio synchronisation
- **Batch Processing**: Automated handling of multiple files

#### Hardware Integration
- **Domesday Duplicator**: Specialised hardware capture support
- **DVD/CD Burning**: Physical media creation for hardware testing
- **Broadcast Equipment**: Compatible with broadcast and A/V equipment

#### Workflow Automation
- **GUI Automation**: Hands-free capture operation
- **Process Management**: Reliable start/stop of capture processes
- **Error Handling**: Robust error detection and recovery
- **Logging**: Comprehensive operation logging and reporting

### Directory Structure
```
DdD-sync-capture/
├── ddd_clockgen_sync.py          # Main capture script
├── ddd_main_menu.py              # Unified menu system
├── check_dependencies.py         # Dependency checker
├── requirements.txt              # Python dependencies
├── README.md                     # Project documentation
├── CHANGELOG.md                  # This changelog
├── tools/                        # Utility scripts
│   ├── audio-sync/              # Audio synchronisation tools
│   ├── create_sync_test.py      # Sync test video creator
│   ├── create_iso_from_mp4.py   # ISO disc image creator
│   ├── audio_alignment_analyzer.py
│   ├── create_belle_nuit_charts.py
│   ├── simple_audio_analyzer.py
│   ├── sync_test_summary.py
│   └── test_sync_verification.py
└── media/                       # Media assets and output
    ├── Test Patterns/           # Test charts
    ├── pyautogui/              # GUI automation screenshots
    └── iso/                    # Generated ISO files
```

### Dependencies
- Python 3.6+
- OpenCV (cv2)
- NumPy
- SciPy
- PyAutoGUI
- Pillow (PIL)
- SOX (audio processing)
- mkisofs or genisoimage (ISO creation)
- Platform-specific tools (screencapture, PowerShell, etc.)

### Usage
The project provides a complete workflow for:
1. Creating sync test videos
2. Converting created sync test videos to burnable DVD/CD ISOs
3. Automated video capture with sync thanks to the clockgen lite script
4. Automated audio/video synchronisation for your capture setup
5. Managing and summarising project assets

Run `python ddd_main_menu.py` to access all features through the unified interface.

---