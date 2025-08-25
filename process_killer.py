#!/usr/bin/env python3
"""
Process Killer - Kill Rogue VHS Processing Jobs
Detects and terminates stuck or orphaned processes from VHS workflows
"""

import os
import sys
import time
import subprocess
import signal
from typing import List, Dict, Optional, Tuple

class ProcessInfo:
    """Information about a running process"""
    def __init__(self, pid: int, command: str, cpu_percent: float, memory_mb: float, 
                 runtime_seconds: int, project_name: Optional[str] = None):
        self.pid = pid
        self.command = command
        self.cpu_percent = cpu_percent
        self.memory_mb = memory_mb
        self.runtime_seconds = runtime_seconds
        self.project_name = project_name
    
    def __str__(self):
        runtime_str = self.format_runtime(self.runtime_seconds)
        project_str = f" ({self.project_name})" if self.project_name else ""
        return (f"PID {self.pid}: {self.command[:50]}... | "
                f"CPU: {self.cpu_percent:.1f}% | RAM: {self.memory_mb:.1f}MB | "
                f"Runtime: {runtime_str}{project_str}")
    
    @staticmethod
    def format_runtime(seconds: int) -> str:
        """Format runtime in human readable format"""
        if seconds < 60:
            return f"{seconds}s"
        elif seconds < 3600:
            return f"{seconds//60}m {seconds%60}s"
        else:
            return f"{seconds//3600}h {(seconds%3600)//60}m"

class ProcessKiller:
    """Main process killer for VHS workflows"""
    
    # Process patterns to look for
    VHS_PROCESS_PATTERNS = [
        'ld-decode',
        'vhs-decode', 
        'tbc-video-export',
        'ld-dropout-correct',
        'ld-chroma-decoder',
        'ld-chroma-encoder',
        'ld-ldf-reader',
        'ffmpeg.*\.tbc',  # ffmpeg processes working on TBC files
        'ffmpeg.*_ffv1\.mkv',  # ffmpeg processes creating FFV1 files
        'python.*vhs.*decode',  # Python VHS decode scripts
        'python.*tbc.*export',  # Python TBC export scripts
    ]
    
    def __init__(self):
        self.current_user = os.getenv('USER', 'unknown')
    
    def scan_processes(self) -> List[ProcessInfo]:
        """Scan for VHS-related processes"""
        processes = []
        
        try:
            # Use ps to get detailed process information
            cmd = ['ps', 'aux', '--sort=-pcpu']  # Sort by CPU usage (highest first)
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            
            if result.returncode != 0:
                print(f"Warning: ps command failed: {result.stderr}")
                return processes
            
            lines = result.stdout.strip().split('\n')
            if len(lines) < 2:
                return processes
            
            # Skip header line
            for line in lines[1:]:
                parts = line.split(None, 10)  # Split into max 11 parts
                if len(parts) < 11:
                    continue
                
                user, pid_str, cpu_str, mem_str = parts[0], parts[1], parts[2], parts[3]
                command = parts[10] if len(parts) > 10 else ""
                
                # Only look at processes from current user
                if user != self.current_user:
                    continue
                
                # Check if this matches our VHS process patterns
                if not self._is_vhs_process(command):
                    continue
                
                try:
                    pid = int(pid_str)
                    cpu_percent = float(cpu_str)
                    memory_percent = float(mem_str)
                    
                    # Get runtime and memory info
                    runtime_seconds = self._get_process_runtime(pid)
                    memory_mb = self._calculate_memory_mb(memory_percent)
                    project_name = self._extract_project_name(command)
                    
                    process_info = ProcessInfo(
                        pid=pid,
                        command=command,
                        cpu_percent=cpu_percent,
                        memory_mb=memory_mb,
                        runtime_seconds=runtime_seconds,
                        project_name=project_name
                    )
                    
                    processes.append(process_info)
                    
                except (ValueError, OSError):
                    continue
            
        except Exception as e:
            print(f"Error scanning processes: {e}")
        
        return processes
    
    def _is_vhs_process(self, command: str) -> bool:
        """Check if command matches VHS process patterns"""
        import re
        command_lower = command.lower()
        
        for pattern in self.VHS_PROCESS_PATTERNS:
            if re.search(pattern.lower(), command_lower):
                return True
        return False
    
    def _get_process_runtime(self, pid: int) -> int:
        """Get process runtime in seconds"""
        try:
            # Get process start time using stat
            with open(f'/proc/{pid}/stat', 'r') as f:
                stats = f.read().split()
                # Field 22 is starttime in jiffies since system boot
                start_jiffies = int(stats[21])
                
            # Get system boot time and clock ticks per second
            with open('/proc/uptime', 'r') as f:
                uptime_seconds = float(f.read().split()[0])
                
            # Get clock ticks per second
            clock_ticks = os.sysconf(os.sysconf_names['SC_CLK_TCK'])
            
            # Calculate process start time and runtime
            process_start_seconds = start_jiffies / clock_ticks
            runtime_seconds = int(uptime_seconds - process_start_seconds)
            
            return max(0, runtime_seconds)
            
        except (OSError, IOError, ValueError, KeyError):
            return 0
    
    def _calculate_memory_mb(self, memory_percent: float) -> float:
        """Calculate memory usage in MB from percentage"""
        try:
            with open('/proc/meminfo', 'r') as f:
                for line in f:
                    if line.startswith('MemTotal:'):
                        total_kb = int(line.split()[1])
                        total_mb = total_kb / 1024
                        return (memory_percent / 100.0) * total_mb
        except (OSError, IOError, ValueError):
            pass
        return 0.0
    
    def _extract_project_name(self, command: str) -> Optional[str]:
        """Try to extract project name from command line"""
        import re
        
        # Look for common patterns in file paths
        patterns = [
            r'/([^/]+)\.(?:lds|ldf|tbc)(?:\s|$)',  # /path/ProjectName.lds
            r'/([^/]+)_ffv1\.mkv',  # /path/ProjectName_ffv1.mkv
            r'/([^/]+)\.tbc\.json',  # /path/ProjectName.tbc.json
            r'--input[^=]*=?[^\s]*?/([^/\s]+)\.(?:lds|ldf|tbc)',  # --input=/path/ProjectName.ext
        ]
        
        for pattern in patterns:
            match = re.search(pattern, command)
            if match:
                return match.group(1)
        
        return None
    
    def identify_rogue_processes(self, processes: List[ProcessInfo], 
                                min_runtime_minutes: int = 30,
                                max_cpu_threshold: float = 0.1,
                                max_memory_mb: float = 16000) -> List[ProcessInfo]:
        """Identify processes that might be rogue/stuck"""
        rogue_processes = []
        
        for process in processes:
            # Check if process has been running for a long time with low CPU
            long_running = process.runtime_seconds > (min_runtime_minutes * 60)
            low_cpu = process.cpu_percent < max_cpu_threshold
            high_memory = process.memory_mb > max_memory_mb
            
            # Different criteria for different process types
            is_rogue = False
            reason = []
            
            if 'ffmpeg' in process.command.lower():
                # FFmpeg should be actively using CPU when encoding
                if long_running and low_cpu:
                    is_rogue = True
                    reason.append(f"FFmpeg idle for {process.runtime_seconds//60}+ minutes")
            
            elif any(pattern in process.command.lower() for pattern in ['ld-decode', 'tbc-video-export']):
                # Decode/export processes should be actively working
                if long_running and low_cpu:
                    is_rogue = True
                    reason.append(f"Decode/export idle for {process.runtime_seconds//60}+ minutes")
            
            elif 'dropout-correct' in process.command.lower() or 'chroma-decoder' in process.command.lower():
                # These can be legitimately long-running, but shouldn't consume excessive memory
                if high_memory:
                    is_rogue = True
                    reason.append(f"Excessive memory usage: {process.memory_mb:.0f}MB")
            
            # General check for any process consuming too much memory
            if high_memory and process.runtime_seconds > 300:  # 5+ minutes
                is_rogue = True
                reason.append(f"Memory leak suspected: {process.memory_mb:.0f}MB for {process.runtime_seconds//60}+ minutes")
            
            if is_rogue:
                process.rogue_reason = "; ".join(reason)
                rogue_processes.append(process)
        
        return rogue_processes
    
    def kill_process(self, pid: int, force: bool = False) -> Tuple[bool, str]:
        """Kill a single process"""
        try:
            # Check if process exists
            os.kill(pid, 0)
        except OSError:
            return True, f"Process {pid} no longer exists"
        
        try:
            if force:
                # Force kill with SIGKILL
                os.kill(pid, signal.SIGKILL)
                message = f"Force killed process {pid}"
            else:
                # Graceful termination with SIGTERM
                os.kill(pid, signal.SIGTERM)
                message = f"Sent termination signal to process {pid}"
            
            return True, message
            
        except OSError as e:
            return False, f"Failed to kill process {pid}: {e}"
    
    def kill_process_tree(self, pid: int, force: bool = False) -> Tuple[bool, str]:
        """Kill a process and all its children"""
        messages = []
        success = True
        
        try:
            # Get all child processes first
            child_pids = self._get_child_processes(pid)
            
            # Kill children first (bottom-up approach)
            for child_pid in reversed(child_pids):  # Reverse to kill deepest children first
                child_success, child_msg = self.kill_process(child_pid, force)
                messages.append(child_msg)
                if not child_success:
                    success = False
            
            # Kill the parent process
            parent_success, parent_msg = self.kill_process(pid, force)
            messages.append(parent_msg)
            if not parent_success:
                success = False
            
            return success, "; ".join(messages)
            
        except Exception as e:
            return False, f"Error killing process tree for {pid}: {e}"
    
    def _get_child_processes(self, parent_pid: int) -> List[int]:
        """Get all child processes recursively"""
        children = []
        
        try:
            # Use pgrep to find children
            result = subprocess.run(['pgrep', '-P', str(parent_pid)], 
                                  capture_output=True, text=True, timeout=5)
            
            if result.returncode == 0:
                direct_children = [int(pid.strip()) for pid in result.stdout.strip().split('\n') if pid.strip()]
                
                for child_pid in direct_children:
                    children.append(child_pid)
                    # Recursively get grandchildren
                    children.extend(self._get_child_processes(child_pid))
            
        except Exception:
            pass
        
        return children

def run_interactive_process_killer():
    """Interactive process killer interface"""
    killer = ProcessKiller()
    
    while True:
        try:
            # Clear screen and show header
            os.system('cls' if os.name == 'nt' else 'clear')
            print("=" * 70)
            print("    VHS PROCESS KILLER - Kill Rogue/Stuck Processes")
            print("=" * 70)
            print()
            
            print("Scanning for VHS-related processes...")
            processes = killer.scan_processes()
            
            if not processes:
                print("✓ No VHS-related processes found.")
                print("\nPress Enter to rescan or 'q' to quit: ", end='')
                choice = input().strip().lower()
                if choice == 'q':
                    break
                continue
            
            print(f"\nFound {len(processes)} VHS-related processes:")
            print("-" * 70)
            
            # Show all processes with numbers
            for i, process in enumerate(processes, 1):
                print(f"{i:2}. {process}")
            
            print()
            
            # Identify potentially rogue processes
            rogue_processes = killer.identify_rogue_processes(processes)
            
            if rogue_processes:
                print(f"⚠️  {len(rogue_processes)} potentially rogue processes detected:")
                print("-" * 70)
                for process in rogue_processes:
                    print(f"⚠️  PID {process.pid}: {getattr(process, 'rogue_reason', 'Unknown issue')}")
                print()
            else:
                print("✓ No obviously rogue processes detected.")
                print()
            
            # Show options
            print("CONTROLS:")
            print("=" * 70)
            print("  1-99  - Kill specific process by number")
            print("  all   - Kill ALL VHS processes")
            print("  rogue - Kill only potentially rogue processes")
            print("  force - Use next kill command with SIGKILL (force)")
            print("  tree  - Kill process tree (parent + children)")
            print("  r     - Refresh/rescan processes")
            print("  q     - Quit process killer")
            print("=" * 70)
            print()
            
            choice = input("Enter choice: ").strip().lower()
            
            if choice == 'q':
                break
            elif choice == 'r':
                continue
            elif choice == 'all':
                print("\n⚠️  WARNING: This will kill ALL VHS-related processes!")
                confirm = input("Type 'yes' to confirm: ").strip().lower()
                if confirm == 'yes':
                    killed_count = 0
                    for process in processes:
                        success, message = killer.kill_process(process.pid)
                        print(f"  {message}")
                        if success:
                            killed_count += 1
                    print(f"\n✓ Attempted to kill {killed_count} processes")
                else:
                    print("Cancelled.")
            elif choice == 'rogue':
                if not rogue_processes:
                    print("No rogue processes to kill.")
                else:
                    print(f"\nKilling {len(rogue_processes)} rogue processes...")
                    killed_count = 0
                    for process in rogue_processes:
                        success, message = killer.kill_process(process.pid)
                        print(f"  {message}")
                        if success:
                            killed_count += 1
                    print(f"\n✓ Attempted to kill {killed_count} rogue processes")
            elif choice.isdigit():
                process_num = int(choice)
                if 1 <= process_num <= len(processes):
                    process = processes[process_num - 1]
                    print(f"\nKilling process {process.pid}...")
                    success, message = killer.kill_process(process.pid)
                    print(f"  {message}")
                else:
                    print("Invalid process number.")
            else:
                print("Invalid choice.")
            
            if choice != 'r':
                input("\nPress Enter to continue...")
                
        except KeyboardInterrupt:
            print("\n\nExiting...")
            break
        except Exception as e:
            print(f"\nError: {e}")
            input("Press Enter to continue...")

def kill_all_vhs_processes() -> Tuple[int, int]:
    """Kill all VHS processes - returns (killed_count, total_count)"""
    killer = ProcessKiller()
    processes = killer.scan_processes()
    
    killed_count = 0
    for process in processes:
        success, _ = killer.kill_process(process.pid)
        if success:
            killed_count += 1
    
    return killed_count, len(processes)

def kill_rogue_vhs_processes() -> Tuple[int, int]:
    """Kill only rogue VHS processes - returns (killed_count, total_rogue_count)"""
    killer = ProcessKiller()
    processes = killer.scan_processes()
    rogue_processes = killer.identify_rogue_processes(processes)
    
    killed_count = 0
    for process in rogue_processes:
        success, _ = killer.kill_process(process.pid)
        if success:
            killed_count += 1
    
    return killed_count, len(rogue_processes)

if __name__ == "__main__":
    if len(sys.argv) > 1:
        if sys.argv[1] == "--kill-all":
            killed, total = kill_all_vhs_processes()
            print(f"Killed {killed} out of {total} VHS processes")
        elif sys.argv[1] == "--kill-rogue":
            killed, total = kill_rogue_vhs_processes()
            print(f"Killed {killed} out of {total} rogue VHS processes")
        else:
            print("Usage: python3 process_killer.py [--kill-all|--kill-rogue]")
    else:
        run_interactive_process_killer()
