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
| Decode | decode_sata_ssd_uncached.csv | ~12 min | 7.5% | 15 | 25 | 9% | Algorithm-bound |
| Export | export_sata_ssd_uncached.csv | ~1.8 min | 28% | 117 | 30 | 56% | **I/O-bound** |
| Compress | compress_sata_ssd_uncached.csv | ~7 min | 4% | 27 | 22 | 13% | Algorithm-bound |
| Align | align_sata_ssd_uncached.csv | ~8s | 2.5% | 4 | 12 | 4% | Trivial |
| Final Mux | final_mux_sata_ssd_uncached.csv | ~38s | 5% | 110 | 103 | 89% | **I/O-bound** |

### HDD Results

| Step | CSV File | Duration | Avg CPU | Read MB/s | Write MB/s | Disk Util | Notes |
|------|----------|----------|---------|-----------|------------|-----------|-------|
| Decode | decode_hdd.csv | ~16 min | 6.8% | 12 | 19 | 39% | Algorithm-bound, 33% slower than SSD |
| Export | export_hdd.csv | ~1.9 min | 38% | 94 | 39 | 83% | I/O-bound |
| Compress | compress_hdd.csv | ~15 min | 4% | 13 | 11 | 61% | I/O-bound, 2x slower than SSD |
| Align | align_hdd.csv | ~6s | 5% | - | - | 13% | Trivial |
| Final Mux | final_mux_hdd.csv | ~78s | 5% | 48 | 64 | 94% | **I/O-bound**, 2x slower than SSD |

### NVMe Results

| Step | CSV File | Duration | Avg CPU | Read MB/s | Write MB/s | Disk Util | Notes |
|------|----------|----------|---------|-----------|------------|-----------|-------|
| Decode | decode_nvme.csv | ~12 min | 7.3% | 18 | 25 | 1% | Algorithm-bound, NVMe idle |
| Export | export_nvme.csv | ~58s | 77% | 292 | 36 | 9% | **CPU-bound**, 2x faster than SATA |
| Compress | compress_nvme.csv | ~6.5 min | 4% | 30 | 23 | 2% | Algorithm-bound, same as SATA |
| Align | align_nvme.csv | ~8s | 5% | - | - | 1% | Trivial |
| Final Mux | final_mux_nvme.csv | ~8s | 19% | 388 | 379 | 16% | 5x faster than SATA |

## Complete Results Comparison

### Duration by Storage Type

| Step | SATA SSD | HDD | NVMe | HDD vs SSD | NVMe vs SSD |
|------|----------|-----|------|------------|-------------|
| Decode | 12 min | 16.7 min | 12 min | +39% | same |
| Export | 1.8 min | 1.9 min | 58s | +6% | **-46%** |
| Compress | 6.8 min | 15.6 min | 6.5 min | +129% | same |
| Align | 8s | 6s | 8s | same | same |
| Final Mux | 38s | 78s | 8s | +105% | **-79%** |

### CPU Utilization by Storage Type

| Step | SATA SSD | HDD | NVMe | Bottleneck Pattern |
|------|----------|-----|------|-------------------|
| Decode | 7.5% | 6.8% | 7.3% | Algorithm (consistent across all) |
| Export | 28% | 38% | **77%** | I/O→CPU as storage gets faster |
| Compress | 4% | 4% | 4% | Algorithm (consistent across all) |
| Align | 2.5% | 5% | 5% | Trivial |
| Final Mux | 5% | 5% | 19% | I/O→CPU as storage gets faster |

### Disk Utilization by Storage Type

| Step | SATA SSD | HDD | NVMe | Notes |
|------|----------|-----|------|-------|
| Decode | 9% | 39% | 1% | HDD works harder, NVMe idle |
| Export | 56% | 83% | 9% | **I/O-bound on SATA/HDD** |
| Compress | 13% | 61% | 2% | HDD becomes I/O-bound |
| Align | 4% | 13% | 1% | All trivial |
| Final Mux | **89%** | **94%** | 16% | **Heavily I/O-bound on SATA/HDD** |

### Read I/O (MB/s) by Storage Type

| Step | SATA SSD | HDD | NVMe |
|------|----------|-----|------|
| Decode | 15 | 12 | 18 |
| Export | 117 | 94 | 292 |
| Compress | 27 | 13 | 30 |
| Align | 4 | - | - |
| Final Mux | 110 | 48 | 388 |

### Write I/O (MB/s) by Storage Type

| Step | SATA SSD | HDD | NVMe |
|------|----------|-----|------|
| Decode | 25 | 19 | 25 |
| Export | 30 | 39 | 36 |
| Compress | 22 | 11 | 23 |
| Align | 12 | - | - |
| Final Mux | 103 | 64 | 379 |

## Bottleneck Analysis

| Step | Primary Bottleneck | Secondary | Notes |
|------|-------------------|-----------|-------|
| **Decode** | Algorithm | None | vhs-decode is single-threaded, ~9.5 FPS regardless of storage |
| **Export** | I/O (SATA/HDD) / CPU (NVMe) | - | Becomes CPU-bound when storage is fast enough |
| **Compress** | Algorithm | I/O (HDD only) | LZ4 compression, HDD can't keep up |
| **Align** | None | None | Trivial workload, completes in seconds |
| **Final Mux** | I/O | None | Read+write intensive, huge NVMe benefit |

## Scheduling Implications

### Parallelization Potential

| Step | Can Parallel? | Limiting Factor | Max Concurrent (est.) |
|------|--------------|-----------------|----------------------|
| Decode | **Yes** | Algorithm (7% CPU) | 10+ jobs |
| Export | Limited | CPU on NVMe, I/O on SATA/HDD | 1-2 on NVMe, 1 on SATA/HDD |
| Compress | **Yes** | Algorithm (4% CPU) | 10+ jobs (except HDD) |
| Align | **Yes** | Nothing | Unlimited |
| Final Mux | Limited | I/O | 1 per storage device |

### Storage Recommendations

| Storage Type | Best For | Avoid |
|--------------|----------|-------|
| **NVMe** | Export, Final Mux | - |
| **SATA SSD** | Decode, Compress, Align | Multiple Final Mux |
| **HDD** | Archive/Storage | Compress, Final Mux |

### Optimal Parallel Combinations

These steps can run together without significant resource contention:
- Multiple Decode jobs (any storage)
- Multiple Compress jobs (except HDD)
- Decode + Compress + Align (same storage)
- Export on NVMe + Decode on SATA/HDD

Avoid running together:
- Multiple Export jobs on same storage
- Multiple Final Mux jobs on same storage
- Export + Final Mux on same SATA/HDD storage

### Implemented Scheduling Rules

The job queue manager (`job_queue_manager.py`) implements storage-aware scheduling:

**Job Categories:**
- **Heavy I/O**: `tbc-export`, `final-mux` (saturate disk bandwidth)
- **Light**: `vhs-decode`, `lds-compress`, `audio-align` (algorithm-bound)

**Scheduling Limits (per storage location):**

| Storage | Scenario | Light Jobs | Heavy Jobs |
|---------|----------|------------|------------|
| **HDD** | No Export/Mux active | 4 | 1 |
| **HDD** | Export/Mux active | 2 | 0 |
| **SSD** | No Export/Mux active | 8 | 1 |
| **SSD** | Export/Mux active | 4 | 0 |

*Light = decode, compress, align (algorithm-bound)*
*Heavy = export, final-mux (I/O-bound, saturates disk)*

**Tested throughput:**
- HDD: 4 parallel decodes @ ~4.0 FPS each = **16 FPS total** (vs 9.5 FPS single)

**Rules:**
1. Only one heavy I/O job (Export OR FinalMux) per storage device at a time
2. When heavy job running, reduce light job limit
3. Jobs on different storage devices are scheduled independently
4. Cross-drive parallelism is unrestricted (e.g., Export on HDD + Export on SSD = OK)

**Configuration:** Edit `SCHEDULING_RULES` in `job_queue_manager.py` to adjust limits.

## Raw Storage I/O Benchmarks

Tested with `fio` through ZFS (not raw device). These represent realistic performance for the VHS workflow.

### Sequential I/O (1MB block size)

| Storage | Seq Read (MB/s) | Seq Write (MB/s) | Notes |
|---------|-----------------|------------------|-------|
| **HDD** (mirror) | 92 | 65 | Limited by spindle speed |
| **SATA SSD** | 383 | 159 | SATA III ~550 MB/s theoretical max |
| **NVMe** | 3043 | 187* | *Write limited - pool 89% full |

### Random 4K I/O (IOPS)

| Storage | Read IOPS | Write IOPS | Notes |
|---------|-----------|------------|-------|
| **HDD** | 76 | 79 | Typical for 7200 RPM |
| **SATA SSD** | 450 | 452 | ZFS overhead reduces from raw ~90K |
| **NVMe** | 7773 | 7759 | ZFS overhead reduces from raw ~500K |

**Note on 4K IOPS:** ZFS recordsize affects these numbers significantly. The NVMe pool uses 1M recordsize (vs 128K for others), so 4K random I/O is not directly comparable. However, the VHS workflow is primarily sequential I/O, making these numbers less relevant for scheduling decisions.

### Observed vs Theoretical Bandwidth

| Storage | Theoretical Max | Observed Seq Read | Utilization |
|---------|-----------------|-------------------|-------------|
| HDD | ~200 MB/s | 92 MB/s | 46% (mirror overhead) |
| SATA SSD | ~550 MB/s | 383 MB/s | 70% |
| NVMe | ~3500 MB/s | 3043 MB/s | 87% |

### Workflow I/O vs Storage Capacity

| Step | Peak Read | Peak Write | HDD Headroom | SATA Headroom | NVMe Headroom |
|------|-----------|------------|--------------|---------------|---------------|
| Decode | 18 MB/s | 25 MB/s | 74 MB/s | 365 MB/s | 3025 MB/s |
| Export | 292 MB/s | 36 MB/s | **-200 MB/s** | 91 MB/s | 2751 MB/s |
| Compress | 30 MB/s | 23 MB/s | 62 MB/s | 353 MB/s | 3013 MB/s |
| Final Mux | 388 MB/s | 379 MB/s | **-296 MB/s** | **-5 MB/s** | 2655 MB/s |

**Negative headroom = storage bottleneck**

## Test Configuration

- **Test File**: Mercer_Tearooms_New2 (16GB .lds, PAL)
- **ZFS ARC**: Limited to 8GB for uncached tests
- **Monitoring**: 2-second sample intervals
- **fio version**: 3.37
- **Date**: 2026-01-15

### ZFS Pool Configuration

| Pool | Recordsize | Compression | Capacity Used | Free Space |
|------|------------|-------------|---------------|------------|
| **hdd1bpool** (HDD) | 128K | zstd-3 | ~32% | 9.72 TB |
| **intel1tb** (SATA SSD) | 128K | zstd-3 | ~22% | 701 GB |
| **nvme2tb** (NVMe) | 1M | zstd-3 | **89%** | 79.4 GB |

**Configuration Notes:**
- All pools have `atime=off` for reduced metadata writes
- **NVMe recordsize difference**: The 1M recordsize on NVMe (vs 128K on others) means:
  - Sequential I/O benefits from larger block sizes
  - Random 4K benchmark results are less comparable (ZFS still uses 1M records internally)
  - Actual workflow uses large sequential I/O, so recordsize difference is favorable for NVMe
- **NVMe pool nearly full**: At 89% capacity, ZFS write performance may be degraded due to:
  - Less space for copy-on-write operations
  - Potential fragmentation
  - The 187 MB/s sequential write (vs 3043 MB/s read) likely reflects this
- **Compression overhead**: zstd-3 compression adds CPU overhead but reduces I/O for compressible data
