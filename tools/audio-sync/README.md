# VHS Audio Alignment Tools

This directory contains tools for aligning VHS audio captures with RF timing data from the VHS decode project.

## What This Does

The VHS decode process captures both RF (video) and audio data separately. Due to hardware timing differences, the audio often needs to be aligned with the RF timing to achieve perfect synchronization.

## Required Dependencies

### System Tools
- **SOX** - Audio processing toolkit
- **mono** - .NET runtime (Unix/macOS only)

### VHS Decode Tool
- **VhsDecodeAutoAudioAlign.exe** - From the [vhs-decode-auto-audio-align](https://github.com/oyvindln/vhs-decode) project

## Installation

### 1. Install System Dependencies

**macOS:**
```bash
brew install sox mono
```

**Linux (Ubuntu/Debian):**
```bash
sudo apt update
sudo apt install sox mono-runtime
```

**Windows:**
- Download SOX from http://sox.sourceforge.net/
- mono is not required on Windows

### 2. Install VhsDecodeAutoAudioAlign.exe

Option A: Copy to this directory
```bash
# Copy the .exe file to:
tools/audio-sync/VhsDecodeAutoAudioAlign.exe
```

Option B: Use existing installation
The script will automatically find it if it's in:
- `~/projects/vhs-decode-auto-audio-align/VhsDecodeAutoAudioAlign.exe`
- Current working directory

## Usage

### Basic Usage
```bash
python3 vhs_audio_align.py input.wav timing.tbc.json aligned_output.wav
```

### Check Dependencies
```bash
python3 vhs_audio_align.py --check-deps
```

### Custom Sample Rate
```bash
python3 vhs_audio_align.py --sample-rate 96000 input.wav timing.json output.wav
```

## Example Workflow

1. **Capture VHS with RF and audio:**
   ```bash
   # Your VHS capture process creates:
   # - RF-Sample_2025-07-21.tbc (RF data)
   # - RF-Sample_2025-07-21.tbc.json (timing data)
   # - my_vhs_capture.wav (audio data)
   ```

2. **Align the audio:**
   ```bash
   python3 tools/audio-sync/vhs_audio_align.py \
     my_vhs_capture.wav \
     RF-Sample_2025-07-21.tbc.json \
     my_vhs_capture_aligned.wav
   ```

3. **Result:**
   - `my_vhs_capture_aligned.wav` - Audio aligned with RF timing

## Pipeline Details

The script implements this complex SOX/mono pipeline:

```bash
sox -D input.wav -t raw -b 24 -c 2 -L -e signed-integer - | \
mono VhsDecodeAutoAudioAlign.exe stream-align \
  --sample-size-bytes 6 \
  --stream-sample-rate-hz 78125 \
  --json timing.tbc.json | \
sox -D -t raw -r 78125 -b 24 -c 2 -L -e signed-integer - output.wav
```

This:
1. **Converts WAV to raw audio stream** using SOX
2. **Processes alignment** using VhsDecodeAutoAudioAlign.exe  
3. **Converts back to WAV** with proper timing

## Integration with Main Project

This audio sync step fits into the overall VHS archival workflow:

1. **Generate sync test patterns** (main project tools)
2. **Create DVD-Video ISOs** (tools/create_iso_from_mp4.py)
3. **Burn DVDs and record to VHS**
4. **Capture VHS with RF + audio** (Domesday Duplicator)
5. **Align audio with RF timing** ← **This tool**
6. **Analyze sync offset** (simple_audio_analyzer.py)
7. **Apply corrections to main captures**

## Troubleshooting

### "VhsDecodeAutoAudioAlign.exe not found"
- Download from the vhs-decode project
- Copy to `tools/audio-sync/` directory
- Or ensure it's in `~/projects/vhs-decode-auto-audio-align/`

### "mono: command not found" (Unix/macOS)
```bash
# macOS
brew install mono

# Linux
sudo apt install mono-runtime
```

### Pipeline failures
- Check that input WAV file exists and is valid
- Verify TBC JSON file matches the RF capture
- Ensure sample rates are correct (default: 78125 Hz)
