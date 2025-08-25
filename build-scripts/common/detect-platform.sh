#!/bin/bash
# detect-platform.sh - Cross-platform OS and architecture detection
# Part of DDD Capture Toolkit build system

set -e

show_usage() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "OPTIONS:"
    echo "  --os        Detect operating system (linux, macos, windows)"
    echo "  --arch      Detect architecture (x86_64, arm64, etc.)"
    echo "  --platform  Detect combined platform (e.g., linux-x64)"
    echo "  --help      Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 --os          # Output: linux"
    echo "  $0 --arch        # Output: x86_64"  
    echo "  $0 --platform    # Output: linux-x64"
}

detect_os() {
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        echo "linux"
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        echo "macos"
    elif [[ "$OSTYPE" == "msys" ]] || [[ "$OSTYPE" == "win32" ]] || [[ "$OSTYPE" == "cygwin" ]]; then
        echo "windows"
    else
        # Fallback detection
        if command -v uname >/dev/null 2>&1; then
            case "$(uname -s)" in
                Linux*)     echo "linux" ;;
                Darwin*)    echo "macos" ;;
                CYGWIN*)    echo "windows" ;;
                MINGW*)     echo "windows" ;;
                MSYS*)      echo "windows" ;;
                *)          echo "unknown" ;;
            esac
        else
            echo "unknown"
        fi
    fi
}

detect_arch() {
    local arch=""
    
    # Try multiple methods to detect architecture
    if command -v uname >/dev/null 2>&1; then
        arch=$(uname -m)
    elif [[ -n "$PROCESSOR_ARCHITECTURE" ]]; then
        # Windows environment variable
        arch="$PROCESSOR_ARCHITECTURE"
    elif [[ -n "$HOSTTYPE" ]]; then
        # Some shells set this
        arch="$HOSTTYPE"
    fi
    
    # Normalise architecture names
    case "$arch" in
        x86_64|amd64|AMD64)
            echo "x86_64"
            ;;
        aarch64|arm64|ARM64)
            echo "arm64"
            ;;
        armv7l|armv7*)
            echo "armv7"
            ;;
        i386|i686|x86)
            echo "x86"
            ;;
        *)
            echo "unknown"
            ;;
    esac
}

detect_platform() {
    local os=$(detect_os)
    local arch=$(detect_arch)
    
    # Convert architecture to short form for platform names
    case "$arch" in
        x86_64) arch_short="x64" ;;
        arm64)  arch_short="arm64" ;;
        armv7)  arch_short="arm" ;;
        x86)    arch_short="x86" ;;
        *)      arch_short="$arch" ;;
    esac
    
    echo "${os}-${arch_short}"
}

# Main execution
if [[ $# -eq 0 ]]; then
    show_usage
    exit 1
fi

case "$1" in
    --os)
        detect_os
        ;;
    --arch)
        detect_arch
        ;;
    --platform)
        detect_platform
        ;;
    --help|-h)
        show_usage
        ;;
    *)
        echo "Error: Unknown option '$1'"
        echo ""
        show_usage
        exit 1
        ;;
esac
