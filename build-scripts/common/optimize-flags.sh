#!/bin/bash
# optimize-flags.sh - CPU optimization flags detection
# Part of DDD Capture Toolkit build system

set -e

show_usage() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "OPTIONS:"
    echo "  --cflags    Generate C compiler optimization flags"
    echo "  --cxxflags  Generate C++ compiler optimization flags"
    echo "  --ldflags   Generate linker optimization flags"
    echo "  --all       Generate all flags (default)"
    echo "  --safe      Use safe optimizations only (no -march=native)"
    echo "  --help      Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0                # Output all flags"
    echo "  $0 --cflags       # Output: -O3 -march=native -mtune=native"
    echo "  $0 --safe         # Output: -O3 -mtune=generic"
}

detect_cpu_features() {
    local features=""
    
    # Linux: Check /proc/cpuinfo
    if [[ -r /proc/cpuinfo ]]; then
        if grep -q "avx2" /proc/cpuinfo; then
            features="$features avx2"
        fi
        if grep -q "avx" /proc/cpuinfo; then
            features="$features avx"
        fi
        if grep -q "sse4_2" /proc/cpuinfo; then
            features="$features sse4_2"
        fi
        if grep -q "sse4_1" /proc/cpuinfo; then
            features="$features sse4_1"
        fi
        if grep -q "fma" /proc/cpuinfo; then
            features="$features fma"
        fi
    fi
    
    # macOS: Use sysctl
    if command -v sysctl >/dev/null 2>&1; then
        if sysctl -n machdep.cpu.features 2>/dev/null | grep -q "AVX2"; then
            features="$features avx2"
        fi
        if sysctl -n machdep.cpu.features 2>/dev/null | grep -q "AVX"; then
            features="$features avx"
        fi
        if sysctl -n machdep.cpu.features 2>/dev/null | grep -q "SSE4.2"; then
            features="$features sse4_2"
        fi
    fi
    
    echo "$features"
}

detect_compiler() {
    if command -v gcc >/dev/null 2>&1; then
        echo "gcc"
    elif command -v clang >/dev/null 2>&1; then
        echo "clang"
    elif command -v cc >/dev/null 2>&1; then
        echo "cc"
    else
        echo "unknown"
    fi
}

generate_base_flags() {
    local safe_mode="$1"
    local compiler=$(detect_compiler)
    local flags="-O3"
    
    # Add basic optimization flags
    if [[ "$safe_mode" == "true" ]]; then
        # Safe mode: use generic tuning
        flags="$flags -mtune=generic"
    else
        # Performance mode: use native optimizations
        flags="$flags -march=native -mtune=native"
        
        # Add CPU-specific features if detected
        local cpu_features=$(detect_cpu_features)
        for feature in $cpu_features; do
            case "$feature" in
                avx2)    flags="$flags -mavx2" ;;
                avx)     flags="$flags -mavx" ;;
                sse4_2)  flags="$flags -msse4.2" ;;
                sse4_1)  flags="$flags -msse4.1" ;;
                fma)     flags="$flags -mfma" ;;
            esac
        done
    fi
    
    # Add additional performance flags (LTO disabled for better compatibility)
    flags="$flags -ffast-math -funroll-loops"
    
    # Note: LTO (-flto) disabled for better compatibility with complex builds
    # Still provides significant performance improvements through:
    # - CPU-specific instruction sets (-march=native, -mavx2, etc.)
    # - Fast math optimizations (-ffast-math)
    # - Loop unrolling (-funroll-loops)
    # - Maximum optimization level (-O3)
    
    # Platform-specific optimizations
    local os=$(build-scripts/common/detect-platform.sh --os 2>/dev/null || echo "unknown")
    case "$os" in
        linux)
            flags="$flags -fPIC"
            ;;
        macos)
            # macOS-specific optimizations
            flags="$flags -fPIC"
            ;;
        windows)
            # Windows-specific optimizations (if using MinGW)
            if [[ "$compiler" == "gcc" ]]; then
                flags="$flags -static-libgcc -static-libstdc++"
            fi
            ;;
    esac
    
    echo "$flags"
}

generate_linker_flags() {
    local compiler=$(detect_compiler)
    local flags=""
    
    # Note: LTO disabled for better compatibility
    # Link-time optimization can cause issues with complex builds
    
    # Strip debug symbols in release builds
    flags="$flags -s"
    
    echo "$flags"
}

# Parse command line arguments
SAFE_MODE=false
OUTPUT_TYPE="all"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --cflags)
            OUTPUT_TYPE="cflags"
            shift
            ;;
        --cxxflags)
            OUTPUT_TYPE="cxxflags"
            shift
            ;;
        --ldflags)
            OUTPUT_TYPE="ldflags"
            shift
            ;;
        --all)
            OUTPUT_TYPE="all"
            shift
            ;;
        --safe)
            SAFE_MODE=true
            shift
            ;;
        --help|-h)
            show_usage
            exit 0
            ;;
        *)
            echo "Error: Unknown option '$1'"
            echo ""
            show_usage
            exit 1
            ;;
    esac
done

# Generate and output flags
case "$OUTPUT_TYPE" in
    cflags)
        generate_base_flags "$SAFE_MODE"
        ;;
    cxxflags)
        generate_base_flags "$SAFE_MODE"
        ;;
    ldflags)
        generate_linker_flags
        ;;
    all)
        CFLAGS=$(generate_base_flags "$SAFE_MODE")
        LDFLAGS=$(generate_linker_flags)
        echo "CFLAGS=\"$CFLAGS\""
        echo "CXXFLAGS=\"$CFLAGS\""
        echo "LDFLAGS=\"$LDFLAGS\""
        ;;
esac
