# Prebuilt Binaries

This directory contains pre-compiled binaries for different platforms as fallback options when source compilation fails.

## Directory Structure

```
prebuilt/
├── linux-x64/          # Linux x86_64 binaries
├── macos-x64/           # macOS Intel x86_64 binaries
├── macos-arm64/         # macOS Apple Silicon ARM64 binaries
└── windows-x64/         # Windows x86_64 binaries
```

## Usage

These binaries are automatically used by the build system when:
1. Source compilation fails
2. User requests fallback mode
3. Build tools are not available

## Binary Sources

All binaries are compiled from the exact same source code as found in the `external/` submodules, with standard optimizations suitable for broad compatibility.

## Updating Binaries

Prebuilt binaries should be updated when:
- Major version updates of external tools
- Security updates
- Performance improvements in compilation flags

## Architecture Support

- **linux-x64**: Linux x86_64 (compatible with most Linux distributions)
- **macos-x64**: macOS Intel (10.15+ recommended)
- **macos-arm64**: macOS Apple Silicon (11.0+ required)
- **windows-x64**: Windows x86_64 (Windows 10+ recommended)

## Installation

These binaries are automatically installed to the conda environment by the build system. Manual installation is not recommended.
