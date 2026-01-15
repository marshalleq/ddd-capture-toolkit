#!/bin/bash
# Resource monitoring script for benchmarking
# Usage: ./benchmark_monitor.sh [--drop-cache] <output_file> [duration_seconds]
# Press Ctrl+C to stop, or it stops after duration if specified

# Parse arguments
DROP_CACHE=0
if [ "$1" == "--drop-cache" ]; then
    DROP_CACHE=1
    shift
fi

OUTPUT_FILE="${1:-benchmark_results.csv}"
DURATION="${2:-0}"  # 0 = run until Ctrl+C

# Drop ZFS ARC cache if requested
if [ $DROP_CACHE -eq 1 ]; then
    echo "Dropping ZFS ARC cache (requires sudo)..."
    if sudo sh -c 'echo 67108864 > /sys/module/zfs/parameters/zfs_arc_max'; then
        sleep 2
        sudo sh -c 'echo 0 > /sys/module/zfs/parameters/zfs_arc_max'
        echo "ARC cache dropped and restored to auto-sizing"

        # Also drop standard Linux page cache for completeness
        sudo sh -c 'echo 3 > /proc/sys/vm/drop_caches'
        echo "Page cache dropped"
    else
        echo "Warning: Failed to drop ARC cache (are you root?)"
    fi
    echo ""
fi

echo "Starting resource monitor, logging to: $OUTPUT_FILE"
echo "Press Ctrl+C to stop..."

# Get list of disks
DISKS=$(lsblk -d -n -o NAME | grep -E '^(sd|nvme)' | head -10)

# Check for NVIDIA GPU
HAS_GPU=0
if command -v nvidia-smi &> /dev/null; then
    nvidia-smi --query-gpu=name --format=csv,noheader &> /dev/null && HAS_GPU=1
fi

if [ $HAS_GPU -eq 1 ]; then
    GPU_NAME=$(nvidia-smi --query-gpu=name --format=csv,noheader)
    echo "GPU detected: $GPU_NAME"
fi

# Write CSV header
DISK_HEADER=""
for disk in $DISKS; do
    DISK_HEADER="${DISK_HEADER},${disk}_read_mbs,${disk}_write_mbs,${disk}_util"
done

GPU_HEADER=""
if [ $HAS_GPU -eq 1 ]; then
    GPU_HEADER=",gpu_util_percent,gpu_mem_used_mb,gpu_mem_total_mb"
fi

echo "timestamp,cpu_percent,mem_used_mb,mem_available_mb${DISK_HEADER}${GPU_HEADER}" > "$OUTPUT_FILE"

START_TIME=$(date +%s)
COUNTER=0

cleanup() {
    echo ""
    echo "Monitoring stopped after $COUNTER samples"
    echo "Results saved to: $OUTPUT_FILE"

    # Print summary
    echo ""
    echo "=== SUMMARY ==="
    if [ -f "$OUTPUT_FILE" ] && [ $(wc -l < "$OUTPUT_FILE") -gt 1 ]; then
        echo "Samples collected: $COUNTER"
        echo "Duration: $(($(date +%s) - START_TIME)) seconds"

        # Calculate averages using awk
        awk -F',' -v has_gpu=$HAS_GPU 'NR>1 {
            cpu+=$2; mem_used+=$3; count++
            if(has_gpu==1) { gpu+=$(NF-2) }
        } END {
            if(count>0) {
                printf "Avg CPU: %.1f%%\n", cpu/count
                printf "Avg RAM used: %.0f MB\n", mem_used/count
                if(has_gpu==1) printf "Avg GPU: %.1f%%\n", gpu/count
            }
        }' "$OUTPUT_FILE"
    fi
    exit 0
}

trap cleanup SIGINT SIGTERM

while true; do
    TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')

    # CPU usage from top (simpler and more reliable)
    CPU_IDLE=$(top -bn1 | grep "Cpu(s)" | awk '{print $8}' | sed 's/%id,//')
    CPU_PERCENT=$(echo "100 - $CPU_IDLE" | bc 2>/dev/null || echo "0")

    # Memory stats
    MEM_USED=$(free -m | awk 'NR==2 {print $3}')
    MEM_AVAIL=$(free -m | awk 'NR==2 {print $7}')

    # Disk I/O stats from iostat (single call for all disks, 1-second sample)
    IOSTAT_OUTPUT=$(iostat -dx 1 2 2>/dev/null)
    DISK_STATS=""
    for disk in $DISKS; do
        IOSTAT_LINE=$(echo "$IOSTAT_OUTPUT" | grep "^$disk" | tail -1)
        if [ -n "$IOSTAT_LINE" ]; then
            read_kbs=$(echo "$IOSTAT_LINE" | awk '{print $3}')
            write_kbs=$(echo "$IOSTAT_LINE" | awk '{print $9}')
            util=$(echo "$IOSTAT_LINE" | awk '{print $NF}')

            # Convert to MB/s
            read_mbs=$(echo "scale=2; $read_kbs / 1024" | bc 2>/dev/null || echo "0")
            write_mbs=$(echo "scale=2; $write_kbs / 1024" | bc 2>/dev/null || echo "0")

            DISK_STATS="${DISK_STATS},${read_mbs},${write_mbs},${util}"
        else
            DISK_STATS="${DISK_STATS},0,0,0"
        fi
    done

    # GPU stats (if available)
    GPU_STATS=""
    if [ $HAS_GPU -eq 1 ]; then
        GPU_INFO=$(nvidia-smi --query-gpu=utilization.gpu,memory.used,memory.total --format=csv,noheader,nounits 2>/dev/null)
        if [ -n "$GPU_INFO" ]; then
            GPU_UTIL=$(echo "$GPU_INFO" | awk -F',' '{gsub(/ /,"",$1); print $1}')
            GPU_MEM_USED=$(echo "$GPU_INFO" | awk -F',' '{gsub(/ /,"",$2); print $2}')
            GPU_MEM_TOTAL=$(echo "$GPU_INFO" | awk -F',' '{gsub(/ /,"",$3); print $3}')
            GPU_STATS=",${GPU_UTIL},${GPU_MEM_USED},${GPU_MEM_TOTAL}"
        else
            GPU_STATS=",0,0,0"
        fi
    fi

    # Write to CSV
    echo "${TIMESTAMP},${CPU_PERCENT},${MEM_USED},${MEM_AVAIL}${DISK_STATS}${GPU_STATS}" >> "$OUTPUT_FILE"

    COUNTER=$((COUNTER + 1))

    # Progress indicator every 10 samples
    if [ $((COUNTER % 10)) -eq 0 ]; then
        if [ $HAS_GPU -eq 1 ]; then
            echo -ne "\rSamples: $COUNTER, CPU: ${CPU_PERCENT}%, GPU: ${GPU_UTIL}%   "
        else
            echo -ne "\rSamples: $COUNTER, CPU: ${CPU_PERCENT}%   "
        fi
    fi

    # Check duration limit
    if [ "$DURATION" -gt 0 ]; then
        ELAPSED=$(($(date +%s) - START_TIME))
        if [ $ELAPSED -ge $DURATION ]; then
            cleanup
        fi
    fi

    sleep 1
done
