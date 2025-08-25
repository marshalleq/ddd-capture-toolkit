#!/bin/bash
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

show_usage() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "DDD Capture Toolkit Setup - Cross-platform installation"
    echo ""
    echo "INSTALLATION MODES:"
    echo "  --easy          Easy installation using pre-compiled binaries (default, 5 mins)"
    echo "  --performance   Performance installation with source compilation (30-60 mins)"
    echo "  --uninstall     Complete uninstallation of the toolkit"
    echo ""
    echo "OPTIONS:"
    echo "  --platform X    Override platform detection (linux/macos/windows)"
    echo "  --jobs N        Number of parallel build jobs for --performance mode"
    echo "  --safe          Use safe optimizations only (no -march=native)"
    echo "  --force         Skip confirmation prompts (for scripting)"
    echo "  --help          Show this help message"
    echo ""
    echo "EXAMPLES:"
    echo "  $0                    # Easy installation with conda packages"
    echo "  $0 --easy            # Same as above (explicit)"
    echo "  $0 --performance      # Performance installation with source compilation"
    echo "  $0 --performance --jobs 4  # Performance with 4 parallel build jobs"
    echo "  $0 --uninstall        # Remove the toolkit completely"
    echo "  $0 --uninstall --force # Remove without confirmation"
    echo ""
    echo "INSTALLATION MODES:"
    echo "  Easy Mode (--easy):"
    echo "    • Uses pre-compiled conda packages"
    echo "    • 5-minute setup time"
    echo "    • Good performance for most users"
    echo "    • Recommended for testing and evaluation"
    echo ""
    echo "  Performance Mode (--performance):"
    echo "    • Compiles from source with CPU-specific optimizations"
    echo "    • 30-60 minute setup time"
    echo "    • 10-30% performance improvement typical"
    echo "    • Recommended for production use"
    echo ""
    echo "  Uninstall Mode (--uninstall):"
    echo "    • Completely removes the 'ddd-capture-toolkit' conda environment"
    echo "    • Removes all installed tools and dependencies"
    echo "    • Preserves user data and project files"
    echo "    • Clean removal following isolation principles"
    echo "    • No impact on system or other conda environments"
}

echo "=== DDD Capture Toolkit Setup ==="

# Parse command line arguments
INSTALL_MODE="easy"  # default mode
OVERRIDE_PLATFORM=""
BUILD_JOBS=""
SAFE_MODE=false
FORCE_MODE=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        --easy)
            INSTALL_MODE="easy"
            shift
            ;;
        --performance)
            INSTALL_MODE="performance"
            shift
            ;;
        --uninstall)
            INSTALL_MODE="uninstall"
            shift
            ;;
        --platform)
            if [[ -z "$2" ]] || [[ "$2" =~ ^- ]]; then
                log_error "--platform requires a value (linux/macos/windows)"
                exit 1
            fi
            OVERRIDE_PLATFORM="$2"
            shift 2
            ;;
        --jobs)
            if [[ -z "$2" ]] || [[ "$2" =~ ^- ]]; then
                log_error "--jobs requires a number"
                exit 1
            fi
            BUILD_JOBS="$2"
            shift 2
            ;;
        --safe)
            SAFE_MODE=true
            shift
            ;;
        --force)
            FORCE_MODE=true
            shift
            ;;
        --help|-h)
            show_usage
            exit 0
            ;;
        *)
            log_error "Unknown option: $1"
            show_usage
            exit 1
            ;;
    esac
done

# Detect operating system
if [[ -n "$OVERRIDE_PLATFORM" ]]; then
    OS="$OVERRIDE_PLATFORM"
    log_info "Using override platform: $OS"
else
    # Use our platform detection script if available, fallback to old method
    if [[ -x "build-scripts/common/detect-platform.sh" ]]; then
        OS=$(build-scripts/common/detect-platform.sh --os)
    else
        # Fallback detection
        if [[ "$OSTYPE" == "linux-gnu"* ]]; then
            OS="linux"
        elif [[ "$OSTYPE" == "darwin"* ]]; then
            OS="macos"
        elif [[ "$OSTYPE" == "msys" ]] || [[ "$OSTYPE" == "win32" ]] || [[ "$OSTYPE" == "cygwin" ]]; then
            OS="windows"
        else
            log_warning "Unknown OS type: $OSTYPE, using generic environment"
            OS="generic"
        fi
    fi
fi

# Select environment file based on OS
case "$OS" in
    linux)   ENV_FILE="environment-linux.yml" ;;
    macos)   ENV_FILE="environment-macos.yml" ;;
    windows) ENV_FILE="environment-windows.yml" ;;
    *)       ENV_FILE="environment.yml" ;;
esac

log_info "Installation mode: $INSTALL_MODE"
log_info "Detected OS: $OS"
log_info "Using environment file: $ENV_FILE"

# Detect and validate conda installation
detect_conda_installation() {
    local conda_cmd
    local conda_base
    local conda_version
    
    # Check if conda is available
    if ! command -v conda &> /dev/null; then
        log_error "conda is not installed or not in PATH"
        echo "Please install Miniconda or Anaconda first:"
        echo "  Linux/Mac: https://docs.conda.io/en/latest/miniconda.html"
        echo "  Windows: https://docs.conda.io/en/latest/miniconda.html"
        exit 1
    fi
    
    # Get conda information
    conda_cmd=$(which conda 2>/dev/null || echo "conda function")
    conda_base=$(conda info --base 2>/dev/null || echo "unknown")
    conda_version=$(conda --version 2>/dev/null || echo "unknown")
    
    log_info "Conda detection results:"
    log_info "  Command: $conda_cmd"
    log_info "  Base environment: $conda_base"
    log_info "  Version: $conda_version"
    
    # Check for multiple conda installations
    local conda_paths=()
    if [[ -f "/usr/bin/conda" ]]; then
        conda_paths+=("System conda: /usr/bin/conda")
    fi
    if [[ -f "$HOME/anaconda3/bin/conda" ]]; then
        conda_paths+=("User anaconda3: $HOME/anaconda3/bin/conda")
    fi
    if [[ -f "$HOME/miniconda3/bin/conda" ]]; then
        conda_paths+=("User miniconda3: $HOME/miniconda3/bin/conda")
    fi
    
    if [[ ${#conda_paths[@]} -gt 1 ]]; then
        log_warning "Multiple conda installations detected:"
        for path in "${conda_paths[@]}"; do
            echo "    - $path"
        done
        log_warning "Using: $conda_cmd (base: $conda_base)"
        log_warning "If you experience issues, consider removing unused conda installations"
    fi
    
    # Verify conda is functional
    if ! conda info &> /dev/null; then
        log_error "conda command is available but not functional"
        log_error "Try restarting your shell or running: conda init"
        exit 1
    fi
    
    return 0
}

# Call conda detection
detect_conda_installation

# Check for conda environment corruption and clean up if needed
check_conda_corruption() {
    # Check for signs of conda environment corruption
    local corruption_detected=false
    
    # Check for high CONDA_SHLVL (indicates nested environment issues)
    if [[ -n "${CONDA_SHLVL}" ]] && [[ "${CONDA_SHLVL}" -gt 2 ]]; then
        log_warning "Deep conda environment nesting detected (SHLVL=${CONDA_SHLVL})"
        corruption_detected=true
    fi
    
    # Check for CONDA_PREFIX pointing to non-existent path
    if [[ -n "${CONDA_PREFIX}" ]] && [[ ! -d "${CONDA_PREFIX}" ]]; then
        log_warning "CONDA_PREFIX points to non-existent directory: ${CONDA_PREFIX}"
        corruption_detected=true
    fi
    
    # Check for mismatched CONDA_DEFAULT_ENV and actual conda state
    if [[ -n "${CONDA_DEFAULT_ENV}" ]] && ! conda env list | grep -q "^${CONDA_DEFAULT_ENV}[[:space:]]"; then
        log_warning "CONDA_DEFAULT_ENV references non-existent environment: ${CONDA_DEFAULT_ENV}"
        corruption_detected=true
    fi
    
    if [[ "$corruption_detected" == "true" ]]; then
        log_warning "Conda environment corruption detected. Cleaning up..."
        
        # Clear problematic environment variables
        unset CONDA_DEFAULT_ENV CONDA_PREFIX CONDA_PREFIX_1 CONDA_PREFIX_2 CONDA_PREFIX_3
        unset CONDA_SHLVL CONDA_PROMPT_MODIFIER CONDA_BUILD_SYSROOT
        unset CMAKE_PREFIX_PATH PKG_CONFIG_PATH LD_LIBRARY_PATH LIBRARY_PATH CMAKE_LIBRARY_PATH
        
        log_info "Environment variables cleaned. Restarting with clean state..."
        
        # Re-initialize conda cleanly
        eval "$(conda shell.bash hook)" 2>/dev/null || true
        
        return 0
    fi
    
    return 1
}

# Initialize conda for bash if not already done
if ! check_conda_corruption; then
    eval "$(conda shell.bash hook)"
fi

# Handle uninstall mode
if [[ "$INSTALL_MODE" == "uninstall" ]]; then
    echo ""
    log_info "=== Uninstall Mode: Removing DDD Capture Toolkit ==="
    echo ""
    
    # Check if environment exists (more robust detection)
    if ! conda env list | grep -q "^ddd-capture-toolkit[[:space:]]"; then
        log_warning "Environment 'ddd-capture-toolkit' does not exist."
        log_info "Nothing to uninstall."
        exit 0
    fi
    
    # Show what will be removed
    log_info "This will completely remove:"
    echo "  • The 'ddd-capture-toolkit' conda environment"
    echo "  • All installed tools (ld-decode, vhs-decode, ffmpeg, etc.)"
    echo "  • All Python packages and dependencies"
    echo ""
    log_info "This will be preserved:"
    echo "  • Your project source code and files"
    echo "  • Any captures, videos, or data you've created"
    echo "  • Configuration files and settings"
    echo "  • Other conda environments"
    echo ""
    
    # Confirmation prompt (unless --force)
    if [[ "$FORCE_MODE" != "true" ]]; then
        read -p "Are you sure you want to uninstall the DDD Capture Toolkit? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            log_info "Uninstall cancelled."
            exit 0
        fi
    fi
    
    # Check if the environment is currently active and deactivate if needed
    if [[ "$CONDA_DEFAULT_ENV" == "ddd-capture-toolkit" ]]; then
        log_info "Deactivating current environment before removal..."
        conda deactivate
    fi
    
    # Perform the uninstall
    log_info "Removing conda environment 'ddd-capture-toolkit'..."
    if conda remove -n ddd-capture-toolkit --all -y; then
        echo ""
        log_success "=== Uninstall Complete ==="
        echo ""
        log_success "The DDD Capture Toolkit has been completely removed."
        log_info "Your project files and source code are preserved."
        log_info "To reinstall, run: ./setup.sh"
    else
        log_error "Failed to remove conda environment."
        log_error "You may need to remove it manually with:"
        echo "  conda remove -n ddd-capture-toolkit --all"
        exit 1
    fi
    
    exit 0
fi

# Check if environment already exists (more robust detection)
# Use conda env list to check environments managed by current conda installation
if conda env list | grep -q "^ddd-capture-toolkit[[:space:]]"; then
    echo "Environment 'ddd-capture-toolkit' already exists."
    
    if [[ "$INSTALL_MODE" == "performance" ]]; then
        log_info "Performance mode: Clean environment required for optimal builds."
        log_info "Automatically removing existing environment for clean rebuild..."
        
        # Check if the environment is currently active and deactivate if needed
        if [[ "$CONDA_DEFAULT_ENV" == "ddd-capture-toolkit" ]]; then
            log_info "Deactivating current environment before removal..."
            conda deactivate
        fi
        
        conda remove -n ddd-capture-toolkit --all -y
        log_info "Creating new conda environment from $ENV_FILE..."
        conda env create -f "$ENV_FILE"
    else
        # Easy mode - just offer to update
        read -p "Do you want to update it? (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            conda env update -f "$ENV_FILE"
        fi
    fi
else
    echo "Creating new conda environment from $ENV_FILE..."
    conda env create -f "$ENV_FILE"
fi

echo "Installing Python dependencies..."
# Don't activate in the script - let the user do it
# Instead, install requirements into the environment directly
if command -v conda &> /dev/null; then
    echo "Installing requirements into conda environment..."
    conda run -n ddd-capture-toolkit pip install -r requirements.txt 2>/dev/null || {
        echo "Warning: Could not install requirements automatically."
        echo "After activating the environment, run: pip install -r requirements.txt"
    }
else
    echo "Warning: Could not install requirements automatically."
    echo "After activating the environment, run: pip install -r requirements.txt"
fi

# Performance mode: build from source
if [[ "$INSTALL_MODE" == "performance" ]]; then
    echo ""
    log_info "=== Performance Mode: Building from Source ==="
    
    # Check if build scripts are available
    if [[ ! -d "build-scripts" ]]; then
        log_error "Build scripts not found. Performance mode requires build-scripts directory."
        log_error "Falling back to easy mode."
        INSTALL_MODE="easy"
    else
        log_info "Starting source compilation with optimizations..."
        
        # Set default build jobs if not specified
        if [[ -z "$BUILD_JOBS" ]]; then
            if [[ -x "build-scripts/common/conda-setup.sh" ]]; then
                # Use the build system's job detection
                source build-scripts/common/conda-setup.sh
                BUILD_JOBS=$(get_build_jobs)
            else
                # Fallback detection
                if command -v nproc >/dev/null 2>&1; then
                    BUILD_JOBS=$(nproc)
                elif command -v sysctl >/dev/null 2>&1; then
                    BUILD_JOBS=$(sysctl -n hw.ncpu 2>/dev/null || echo "4")
                else
                    BUILD_JOBS=4
                fi
            fi
        fi
        
        log_info "Building with $BUILD_JOBS parallel jobs"
        if [[ "$SAFE_MODE" == "true" ]]; then
            log_info "Using safe optimization mode"
        else
            log_info "Using native optimization mode"
        fi
        
        echo ""
        log_info "This will take 30-60 minutes depending on your system..."
        echo ""
        
        # Build LD-Decode
        if [[ -x "build-scripts/build-ld-decode.sh" ]]; then
            log_info "Building LD-Decode..."
            build_args="--jobs $BUILD_JOBS"
            if [[ "$SAFE_MODE" == "true" ]]; then
                build_args="$build_args --safe"
            fi
            
            # Export conda environment info for build script
            # Get the correct conda environment path using conda env list
            CONDA_ENV_PATH=$(conda env list | awk '/^ddd-capture-toolkit[[:space:]]/ {print $2}' | head -n1)
            
            # If that didn't work, try alternative method
            if [[ -z "$CONDA_ENV_PATH" ]]; then
                CONDA_ENV_PATH=$(conda info --envs | grep ddd-capture-toolkit | awk '{print $NF}')
            fi
            
            # If still empty, try conda info base + envs
            if [[ -z "$CONDA_ENV_PATH" ]]; then
                CONDA_BASE=$(conda info --base)
                CONDA_ENV_PATH="${CONDA_BASE}/envs/ddd-capture-toolkit"
            fi
            
            # Verify the path exists
            if [[ ! -d "$CONDA_ENV_PATH" ]]; then
                log_error "Could not determine conda environment path: $CONDA_ENV_PATH"
                log_error "Manual check: conda info --envs"
                exit 1
            fi
            
            log_info "Using conda environment: $CONDA_ENV_PATH"
            export CONDA_PREFIX="$CONDA_ENV_PATH"
            
            if ! build-scripts/build-ld-decode.sh $build_args; then
                log_error "LD-Decode build failed"
                log_warning "Continuing with conda packages for remaining tools"
            else
                log_success "LD-Decode built successfully"
            fi
        else
            log_warning "LD-Decode build script not found, using conda package"
        fi
        
        # Add more build scripts here as they're created
        # TODO: Add VHS-Decode, TBC-Video-Export, etc.
        
        log_success "Source compilation completed"
    fi
fi

echo ""
if [[ "$INSTALL_MODE" == "performance" ]]; then
    log_success "=== Performance Setup Complete ==="
    echo ""
    log_info "Your toolkit is optimised for your specific CPU architecture."
    log_info "You should see 10-30% performance improvement in processing times."
else
    log_success "=== Easy Setup Complete ==="
    echo ""
    log_info "Your toolkit is ready to use with pre-compiled packages."
    log_info "For maximum performance, consider running: ./setup.sh --performance"
fi

echo ""
log_info "To use the toolkit:"
echo "  1. Run: conda activate ddd-capture-toolkit"
echo "  2. Run: python3 ddd_main_menu.py"
echo ""
echo "Or simply use: ./start.sh"
echo ""

# Install system packages that aren't available in conda
echo "Checking for required system packages..."
case "$OS" in
    "linux")
        # Check which package manager is available
        if command -v dnf &> /dev/null; then
            PKG_MGR="dnf"
        elif command -v yum &> /dev/null; then
            PKG_MGR="yum"
        elif command -v apt &> /dev/null; then
            PKG_MGR="apt"
        elif command -v pacman &> /dev/null; then
            PKG_MGR="pacman"
        elif command -v zypper &> /dev/null; then
            PKG_MGR="zypper"
        else
            PKG_MGR="none"
        fi

        # Install DVD creation tools
        if [[ "$PKG_MGR" == "dnf" ]] || [[ "$PKG_MGR" == "yum" ]]; then
            echo "Installing system packages with $PKG_MGR..."
            if ! rpm -q genisoimage dvdauthor &> /dev/null; then
                echo "Installing genisoimage and dvdauthor..."
                sudo $PKG_MGR install -y genisoimage dvdauthor || echo "Warning: Could not install DVD creation tools. Install manually: sudo $PKG_MGR install genisoimage dvdauthor"
            fi
        elif [[ "$PKG_MGR" == "apt" ]]; then
            echo "Installing system packages with apt..."
            if ! dpkg -l | grep -q "genisoimage\|dvdauthor"; then
                echo "Installing genisoimage and dvdauthor..."
                sudo apt update && sudo apt install -y genisoimage dvdauthor || echo "Warning: Could not install DVD creation tools. Install manually: sudo apt install genisoimage dvdauthor"
            fi
        elif [[ "$PKG_MGR" == "pacman" ]]; then
            echo "Installing system packages with pacman..."
            if ! pacman -Q cdrtools dvdauthor &> /dev/null; then
                echo "Installing cdrtools and dvdauthor..."
                sudo pacman -S --needed --noconfirm cdrtools dvdauthor || echo "Warning: Could not install DVD creation tools. Install manually: sudo pacman -S cdrtools dvdauthor"
            fi
        elif [[ "$PKG_MGR" == "zypper" ]]; then
            echo "Installing system packages with zypper..."
            if ! rpm -q cdrtools dvdauthor &> /dev/null; then
                echo "Installing cdrtools and dvdauthor..."
                sudo zypper install -y cdrtools dvdauthor || echo "Warning: Could not install DVD creation tools. Install manually: sudo zypper install cdrtools dvdauthor"
            fi
        else
            echo "Warning: Unknown package manager. Please install these packages manually:"
            echo "  - cdrtools (or genisoimage on Ubuntu/Debian)"
            echo "  - dvdauthor"
        fi

        echo ""
        echo "Linux-specific setup notes:"
        echo "  - You may need to set up udev rules for USB devices"
        echo "  - Run the toolkit with ./start.sh or python3 ddd_main_menu.py"
        if [[ "$PKG_MGR" == "none" ]]; then
            echo "  - Install DVD creation tools manually: cdrtools/genisoimage and dvdauthor"
        fi
        ;;
    "macos")
        echo "macOS-specific setup notes:"
        echo "  - You may need to grant permissions for USB device access"
        echo "  - Some system security features may require additional setup"
        echo "  - Install DVD creation tools with: brew install cdrtools dvdauthor"
        ;;
    "windows")
        echo "Windows-specific setup notes:"
        echo "  - Ensure USB drivers are properly installed"
        echo "  - You may need to run as administrator for device access"
        echo "  - DVD creation tools may need to be installed separately"
        ;;
esac
