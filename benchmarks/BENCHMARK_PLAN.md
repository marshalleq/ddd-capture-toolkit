# DDD Capture Toolkit Resource Benchmarking Plan

## Goal
Characterize resource usage (CPU, RAM, disk I/O, throughput) for each workflow step
on each storage type to enable intelligent parallel job scheduling.

## Test System
- **CPU**: AMD Ryzen 9950X3D
- **RAM**: ~126 GB
- **Test File**: Mercer_Tearooms_New2 on SATA SSD (intel1tb pool)
- **Note**: Initial tests run from ZFS ARC cache (file fits in RAM) - this gives CPU-bound baseline without storage bottleneck

## Workflow Steps to Benchmark

| Step | Input | Output | Description |
|------|-------|--------|-------------|
| **Decode** | `.lds` (RF capture) | `.tbc` | vhs-decode: RF to TBC conversion |
| **Decode (compressed)** | `.lds.lz4` or similar | `.tbc` | Decode from compressed source |
| **Compress** | `.tbc` | `.tbc.lz4` | LZ4 compression of TBC |
| **Export** | `.tbc` | `_ffv1.mkv` | tbc-video-export: TBC to FFV1 video |
| **Export (reverse field)** | `.tbc` | `_ffv1.mkv` | Export with reverse field (duplicates TBC reads) |
| **Align** | `.flac` | `_aligned.wav` | Audio alignment processing |
| **Final Mux** | `_ffv1.mkv` + `_aligned.wav` | `_final.mkv` | Final muxing |

## Storage Types

| Type | Expected Characteristics |
|------|-------------------------|
| **HDD** | High latency, sequential ~150-200 MB/s, poor random I/O |
| **SATA SSD** | Low latency, ~500-550 MB/s sequential |
| **NVMe** | Very low latency, ~3000+ MB/s sequential |

## Test Matrix

Each cell = one benchmark run:

| Step | HDD | SATA SSD | NVMe |
|------|-----|----------|------|
| Decode | | | |
| Decode (compressed) | | | |
| Compress | | | |
| Export | | | |
| Export (reverse field) | | | |
| Align | | | |
| Final Mux | | | |

**Total tests**: 7 steps × 3 storage types = 21 benchmark runs

## Metrics to Capture

- **CPU**: Average %, peak %
- **RAM**: Usage growth, peak usage
- **Disk Read**: MB/s average (when not ARC-cached)
- **Disk Write**: MB/s average
- **FPS**: Frames per second (calculated from duration and frame count)
- **Duration**: Total wall-clock time
- **Bottleneck**: Identify limiting factor (CPU/RAM/read I/O/write I/O)

## Important Considerations

### ZFS ARC Cache
- **Problem**: First test ran entirely from ARC cache (all disk I/O showed 0)
- **Solution**: Either:
  1. Drop caches before each test: `echo 3 > /proc/sys/vm/drop_caches` (requires root)
  2. Use `arc_summary` to monitor ARC hits vs disk reads
  3. Use files larger than available ARC space
  4. Monitor ZFS-specific I/O stats from `/proc/spl/kstat/zfs/`

### Cross-storage I/O patterns
- Source and destination may be on different storage types
- Need to track I/O per device, not just total

### Parallel execution interactions
- Some steps may compete for same resources
- Memory pressure affects all steps
- NVMe may become CPU-bound rather than I/O-bound

## Storage Configuration

### ZFS Pools

| Pool | Type | Mount | Used | Avail |
|------|------|-------|------|-------|
| hdd1bpool | HDD (2x 16TB) | /mnt/hdd1bpool | 4.70T | 9.72T |
| intel1tb | SATA SSD (Intel 960GB) | /mnt/intel1tb | 192G | 668G |
| nvme2tb | NVMe (Kingston 2TB) | /mnt/nvme2tb | 1.67T | 136G |

### Test Files

| Storage | Mount | File | Size |
|---------|-------|------|------|
| HDD | /mnt/hdd1bpool/captures | Inside_Hong_Kong_1987.lds | ~16GB (has .tbc) |
| HDD | /mnt/hdd1bpool/captures | SpecialFX.lds | (has .tbc) |
| SATA SSD | /mnt/intel1tb/captures | Mercer_Tearooms_New2.lds | 16GB (has .tbc) |
| SATA SSD | /mnt/intel1tb/captures | Robert_Fixed_Audio2.lds | 168GB |
| NVMe | /mnt/nvme2tb/captures | HongKong_Fixed_Audio.lds | (has .tbc) |

### System RAM
- Total: ~126 GB
- ZFS ARC can cache entire 16GB files easily
- For valid I/O benchmarks, must bypass or account for ARC

## Results Summary

### Mercer_Tearooms_New2 on SATA SSD (ARC-cached)

### ARC-Cached Results (baseline CPU performance)

| Step | CSV File | FPS | Duration | Avg CPU | Peak CPU | RAM Growth | Notes |
|------|----------|-----|----------|---------|----------|------------|-------|
| Decode | decode_sata_ssd.csv | ~9.5 | ~14 min | ~7-8% | ~22% | +13 GB | ARC-cached, low CPU |
| Decode (run 2) | decode2_sata_ssd.csv | ~9.5 | ~12 min | 7% | 68%* | +23 GB | ARC-cached, consistent with run 1 |
| Export | export_sata_ssd.csv | ~170 | ~47s | 68% | 100% | +20 GB | ARC-cached, CPU-bound |
| Align | align_sata_ssd.csv | N/A | ~15s | 7% | 14% | ~0 | Very lightweight |
| Final Mux | final_mux_sata_ssd.csv | N/A | ~14s | 13% | 54% | +7.5 GB | Lightweight, brief CPU spike |
| Compress | compress_sata_ssd.csv | N/A | ~6.5 min | 10% | 33% | +12.7 GB | CPU-only (GPU not used), low CPU |

*Peak 68% was brief startup spike, sustained ~7%

### Uncached Results (SATA SSD - real disk I/O)

| Step | CSV File | Duration | Avg CPU | Read MB/s | Write MB/s | Disk Util | Notes |
|------|----------|----------|---------|-----------|------------|-----------|-------|
| Decode | decode_sata_ssd_uncached.csv | ~12 min | 7.5% | 15 | 25 | 9% | Algorithm-bound, not I/O-bound |
| Export | export_sata_ssd_uncached.csv | ~2.5 min | 28% | 117 | 30 | 56% | **I/O-bound** (3x slower than cached) |
| Compress | | | | | | | |

## Scheduling Implications

(To be filled after analysis)

- Which steps can run in parallel?
- What are the limiting factors for each combination?
- Recommended concurrent job limits per storage type
