
def get_clean_env_for_system_tools():
    """Get a clean environment without conda library paths.

    This is needed for system tools like DomesdayDuplicator that are linked
    against system Qt libraries, which conflict with conda's Qt version.
    """
    clean_env = os.environ.copy()
    # Remove conda library paths that could conflict with system Qt
    for var in ['LD_LIBRARY_PATH', 'LIBRARY_PATH']:
        if var in clean_env:
            # Keep only non-conda paths
            paths = clean_env[var].split(':')
            clean_paths = [p for p in paths if 'conda' not in p.lower() and 'anaconda' not in p.lower()]
            if clean_paths:
                clean_env[var] = ':'.join(clean_paths)
            else:
                del clean_env[var]
    return clean_env


def release_audio_device_before_capture():
    """
    Release the audio device from PipeWire/PulseAudio immediately before starting sox.
    This must be called right before subprocess.Popen(sox_command) to prevent
    PipeWire from reclaiming the device between release and capture start.
    """
    try:
        from config import release_audio_device_linux
        if release_audio_device_linux('hw:0,0'):  # device_id doesn't matter, it matches by name
            time.sleep(0.2)  # Brief pause to ensure device is released
    except ImportError:
        pass


def _can_use_realtime_audio():
    """Check whether `chrt -r 50` is permitted (needs CAP_SYS_NICE on chrt).

    Granted persistently via menu option 11 (`sudo setcap cap_sys_nice+ep
    $(which chrt)`). Result is cached since the capability state doesn't
    change between captures within a single process run.
    """
    if hasattr(_can_use_realtime_audio, '_cached'):
        return _can_use_realtime_audio._cached
    try:
        result = subprocess.run(
            ['chrt', '-r', '50', 'true'],
            capture_output=True, timeout=2,
        )
        _can_use_realtime_audio._cached = (result.returncode == 0)
    except Exception:
        _can_use_realtime_audio._cached = False
    return _can_use_realtime_audio._cached


def _wrap_for_realtime(cmd):
    """Prepend `chrt -r 50` to a command if realtime audio priority is
    available. Prints a one-time hint pointing at menu option 11 otherwise."""
    if _can_use_realtime_audio():
        return ['chrt', '-r', '50'] + cmd
    if not getattr(_wrap_for_realtime, '_warned', False):
        print("Note: sox running without realtime priority.")
        print("      Enable via Capture menu option 11 to reduce ALSA over-runs.")
        _wrap_for_realtime._warned = True
    return cmd


def verify_capture_environment():
    """Pre-capture environment check. Returns a list of dicts:
        {'name': str, 'status': 'PASS'|'WARN'|'SKIP', 'expected': str, 'actual': str, 'hint': str}

    Verifies the load-bearing kernel/system settings that affect capture
    reliability. Distro-portable: each check probes for its tool with
    shutil.which() and SKIPs gracefully if the tool isn't installed
    (e.g. tuned isn't ubiquitous outside Fedora/RHEL).

    Read-only: no sudo, no state changes. Caller decides what to do with
    the results.
    """
    import shutil
    checks = []

    # 1. usbcore.usbfs_memory_mb (libusb URB buffer cap)
    try:
        with open('/sys/module/usbcore/parameters/usbfs_memory_mb') as f:
            v = f.read().strip()
        status = 'PASS' if v == '1000' else 'WARN'
        checks.append({
            'name': 'usbfs_memory_mb',
            'status': status,
            'expected': '1000',
            'actual': v,
            'hint': 'Menu option 5 (re-apply USB buffer fix)',
        })
    except Exception:
        checks.append({
            'name': 'usbfs_memory_mb',
            'status': 'SKIP',
            'expected': '1000',
            'actual': 'unreadable',
            'hint': '',
        })

    # 2. vm.swappiness
    if shutil.which('sysctl'):
        try:
            r = subprocess.run(['sysctl', '-n', 'vm.swappiness'],
                               capture_output=True, text=True, timeout=2)
            v = r.stdout.strip()
            status = 'PASS' if v == '10' else 'WARN'
            checks.append({
                'name': 'vm.swappiness',
                'status': status,
                'expected': '10',
                'actual': v,
                'hint': 'Menu option 6 (re-apply swappiness fix)',
            })
        except Exception:
            pass

    # 3. chrt realtime capability (sox runs at SCHED_FIFO if granted)
    if shutil.which('chrt'):
        rt_ok = _can_use_realtime_audio()
        checks.append({
            'name': 'chrt cap_sys_nice',
            'status': 'PASS' if rt_ok else 'WARN',
            'expected': 'granted',
            'actual': 'granted' if rt_ok else 'denied',
            'hint': 'Menu option 11 (enable realtime audio priority)',
        })

    # 4. tuned active profile (only meaningful if tuned-adm exists)
    if shutil.which('tuned-adm'):
        try:
            r = subprocess.run(['tuned-adm', 'active'],
                               capture_output=True, text=True, timeout=5)
            line = r.stdout.strip()
            actual = line.split(':', 1)[1].strip() if ':' in line else line
            status = 'PASS' if actual == 'latency-performance' else 'WARN'
            checks.append({
                'name': 'tuned profile',
                'status': status,
                'expected': 'latency-performance',
                'actual': actual or 'unknown',
                'hint': 'Menu option 12 (apply low-latency CPU profile)',
            })
        except Exception:
            pass

    # 5. tuned-ppd disabled (would otherwise revert option 12 on boot)
    if shutil.which('systemctl'):
        try:
            r = subprocess.run(['systemctl', 'is-enabled', 'tuned-ppd'],
                               capture_output=True, text=True, timeout=3)
            v = r.stdout.strip()
            if v in ('enabled', 'enabled-runtime'):
                checks.append({
                    'name': 'tuned-ppd',
                    'status': 'WARN',
                    'expected': 'disabled',
                    'actual': v,
                    'hint': 'Menu option 13 (override desktop power mgmt)',
                })
            elif v in ('disabled', 'masked'):
                checks.append({
                    'name': 'tuned-ppd',
                    'status': 'PASS',
                    'expected': 'disabled',
                    'actual': v,
                    'hint': '',
                })
            # not-found / other: skip silently (no tuned-ppd on this system)
        except Exception:
            pass

    return checks


def _print_environment_check_table(checks):
    """Render the verify_capture_environment() result as a small table.

    PASS rows render in green, WARN rows in bright yellow/orange. ANSI
    escapes are emitted only when stdout is a tty so logs/redirected
    output stay plain.
    """
    if not checks:
        return

    use_color = sys.stdout.isatty()
    GREEN = '\033[92m' if use_color else ''
    ORANGE = '\033[93m' if use_color else ''
    BOLD = '\033[1m' if use_color else ''
    RESET = '\033[0m' if use_color else ''

    def colorise(status):
        if status == 'PASS':
            return f'{GREEN}{BOLD}{status:<4}{RESET}'
        if status == 'WARN':
            return f'{ORANGE}{BOLD}{status:<4}{RESET}'
        return f'{status:<4}'

    print()
    print("PRE-CAPTURE ENVIRONMENT CHECK")
    print("-" * 70)
    name_w = max(len(c['name']) for c in checks)
    for c in checks:
        line = f"  {c['name']:<{name_w}}  {colorise(c['status'])}  expected={c['expected']:<22} actual={c['actual']}"
        print(line)
        if c['status'] == 'WARN' and c['hint']:
            print(f"  {'':<{name_w}}        -> fix: {c['hint']}")
    print("-" * 70)


def build_audio_pipeline_with_device(output_filename, device_info):
    """Build (sox_args, flac_args) for the sox|flac capture pipeline.

    Why a pipeline instead of plain sox writing .flac directly:
    Sox doing inline FLAC encoding holds up its own ALSA reads when an
    encode frame takes a few extra ms. That stall lets the ALSA ring
    buffer fill and samples get dropped (silent in sox's terminal
    output, accumulating to seconds of audio drift over a multi-hour
    capture - see SKILL.md "Sox often shows over-runs that aren't there"
    + "Verifying gain on past captures"). Splitting the work across two
    processes (sox reads + remixes, flac compresses) lets the kernel
    schedule them on different cores; the encoding spike no longer
    starves the read path.

    Returns (sox_args, flac_args). Caller wires sox.stdout into flac.stdin.
    """
    import shutil as _shutil
    device = device_info['device_id']
    sample_rate = str(device_info.get('sample_rate', 78125))
    bit_depth = str(device_info.get('bit_depth', 24))

    if sys.platform == 'win32':
        driver = 'waveaudio'
    elif sys.platform == 'darwin':
        driver = 'coreaudio'
    else:
        driver = 'alsa'

    # Prefer system sox on Linux for ALSA support; conda sox is built without it
    sox_cmd = 'sox'
    if sys.platform == 'linux' and driver == 'alsa':
        system_sox = '/usr/bin/sox'
        if os.path.exists(system_sox):
            sox_cmd = system_sox

    flac_cmd = _shutil.which('flac')
    if not flac_cmd:
        raise RuntimeError(
            "flac binary not found. Ensure the conda env is activated "
            "(conda activate ddd-capture-toolkit) or install via your "
            "package manager (Fedora: dnf install flac)."
        )

    # sox: ALSA in -> remix down to stereo -> raw 24-bit signed LE PCM on stdout
    sox_args = [
        sox_cmd,
        '-t', driver,
        '-r', sample_rate,
        '-b', bit_depth,
        '-c', '2',
        device,
        '--buffer', '8192',
        '-t', 'raw',
        '-L',
        '-e', 'signed-integer',
        '-b', '24',
        '-c', '2',
        '-',
        'remix', '1', '2',
    ]

    # flac: raw PCM on stdin -> compressed .flac on disk.
    # --lax is required because the clockgen-Lite rate (78125 Hz) is outside
    # the FLAC Subset (which only specifies standard rates like 44.1k/48k/96k).
    # The resulting file is still a valid FLAC; --lax just opts out of the
    # hardware-playback compatibility constraint, which doesn't matter for
    # archival captures decoded in software.
    flac_args = [
        flac_cmd,
        '--silent',
        '--force',
        '--lax',
        '--channels=2',
        '--bps=24',
        f'--sample-rate={sample_rate}',
        '--sign=signed',
        '--endian=little',
        '-o', output_filename,
        '-',
    ]
    return sox_args, flac_args


def _launch_audio_pipeline(sox_args, flac_args, log_path):
    """Spawn the sox|flac capture pipeline. Returns (sox_proc, flac_proc, log_file).

    Both processes wrapped in chrt for realtime priority. Each process's stderr
    is read in a small daemon thread that:
      - echoes verbatim to the terminal (preserves sox VU meter + live output)
      - writes a single timestamped line to <log_path> ONLY when the line
        matches WARN/FAIL/over-run/ERROR keywords

    Logging is deliberately minimal: no header, no per-byte work, no logging
    of routine VU meter updates. CPU overhead is dominated by the verbatim
    terminal echo (which would happen anyway in the old single-process path).
    """
    log_file = open(log_path, 'w', buffering=1)  # line buffered

    sox_full = _wrap_for_realtime(sox_args)
    flac_full = _wrap_for_realtime(flac_args)

    sox_proc = subprocess.Popen(
        sox_full,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        bufsize=0,
    )
    flac_proc = subprocess.Popen(
        flac_full,
        stdin=sox_proc.stdout,
        stderr=subprocess.PIPE,
        bufsize=0,
    )
    # Let sox receive SIGPIPE if flac dies first
    sox_proc.stdout.close()

    start_time = time.monotonic()
    log_keywords = (b'WARN', b'FAIL', b'over-run', b'overrun', b'ERROR', b'fatal')

    def _tee_stderr(proc, source):
        buf = bytearray()
        in_fd = proc.stderr.fileno()
        out_fd = sys.stderr.fileno()
        while True:
            try:
                chunk = os.read(in_fd, 1024)
            except OSError:
                break
            if not chunk:
                break
            try:
                os.write(out_fd, chunk)
            except Exception:
                pass
            buf.extend(chunk)
            # Extract complete lines (terminated by \n or \r) for logging
            while True:
                nl = buf.find(b'\n')
                cr = buf.find(b'\r')
                if nl < 0 and cr < 0:
                    break
                if nl < 0:
                    i = cr
                elif cr < 0:
                    i = nl
                else:
                    i = min(nl, cr)
                line = bytes(buf[:i]).strip()
                del buf[:i + 1]
                if line and any(kw in line for kw in log_keywords):
                    elapsed = time.monotonic() - start_time
                    h = int(elapsed // 3600)
                    m = int((elapsed % 3600) // 60)
                    s = elapsed % 60
                    ts = f"{h:02d}:{m:02d}:{s:06.3f}"
                    try:
                        log_file.write(f"[{ts}] [{source}] {line.decode('utf-8', errors='replace')}\n")
                    except Exception:
                        pass

    threading.Thread(target=_tee_stderr, args=(sox_proc, 'sox'), daemon=True).start()
    threading.Thread(target=_tee_stderr, args=(flac_proc, 'flac'), daemon=True).start()

    return sox_proc, flac_proc, log_file


def build_sox_command_with_device(output_filename, device_info):
    """Build sox command using pre-cached device info (no subprocess calls).

    This is the fast version - assumes device_info was already obtained from
    prepare_audio_device() during the preparation phase.
    """
    device = device_info['device_id']
    sample_rate = str(device_info.get('sample_rate', 78125))
    bit_depth = str(device_info.get('bit_depth', 24))
    channels = '2'

    # Determine driver based on platform
    if sys.platform == 'win32':
        driver = 'waveaudio'
    elif sys.platform == 'darwin':
        driver = 'coreaudio'
    else:
        driver = 'alsa'

    # Find sox with ALSA support on Linux
    sox_cmd = 'sox'
    if sys.platform == 'linux' and driver == 'alsa':
        system_sox = '/usr/bin/sox'
        if os.path.exists(system_sox):
            sox_cmd = system_sox

    if sys.platform == 'win32':
        return [
            sox_cmd,
            '-t', driver,
            '-r', sample_rate,
            '-b', bit_depth,
            device,
            output_filename,
            'remix', '1', '2'
        ]
    else:
        return [
            sox_cmd,
            '-t', driver,
            '-r', sample_rate,
            '-b', bit_depth,
            '-c', channels,
            device,
            '--buffer', '8192',
            output_filename,
            'remix', '1', '2'
        ]


def prepare_capture_resources(audio_output_path):
    """
    Pre-prepare all capture resources BEFORE user interaction.

    This does all the slow work (device detection, PipeWire release)
    so that when the user presses Enter, capture can start immediately.

    Returns (sox_command, device_info) or (None, error_message).
    """
    # 1. Clean up existing processes
    cleanup_existing_processes()

    # 2. Detect audio device (without verification - sox will fail fast if device doesn't work)
    from config import get_audio_device, release_audio_device_linux

    device_info = get_audio_device()
    if not device_info:
        return None, "No Clockgen audio device detected. Check USB connection."

    device = device_info['device_id']
    sample_rate = device_info.get('sample_rate', 78125)
    bit_depth = device_info.get('bit_depth', 24)
    device_channels = device_info.get('channels', 2)

    # 3. Release device from PipeWire/PulseAudio (do this BEFORE any verification)
    print(f"Releasing audio device from system audio server...")
    if release_audio_device_linux(device):
        time.sleep(0.3)  # Brief pause for release to complete

    print(f"Audio device ready: {device_info.get('device_name', device)} ({device})")
    print(f"   Sample rate: {sample_rate} Hz, Bit depth: {bit_depth}, Channels: {device_channels}")

    # 4. Build sox|flac pipeline (audio capture spec) with cached device info.
    #    Returned tuple is consumed by shared_capture_process_fast.audio_capture_thread.
    sox_args, flac_args = build_audio_pipeline_with_device(audio_output_path, device_info)
    log_path = os.path.splitext(audio_output_path)[0] + '.capture.log'
    audio_capture_spec = (sox_args, flac_args, log_path)

    return audio_capture_spec, device_info


def shared_capture_process_fast(sox_command, audio_delay, capture_duration, ddd_command):
    """
    Fast version of shared_capture_process - assumes resources pre-prepared.

    Key differences from shared_capture_process():
    - No cleanup (already done in prepare_capture_resources)
    - No audio device release (already done in prepare_capture_resources)
    - Reduced DomesdayDuplicator startup wait (0.3s instead of 1.0s)
    """
    # Clean up any stale stop request file
    stop_request_file = '/tmp/domesday_stop_request'
    if os.path.exists(stop_request_file):
        try:
            os.remove(stop_request_file)
        except Exception:
            pass

    stop_event = threading.Event()

    def video_capture_thread():
        # If audio_delay is negative, video needs to be delayed (audio starts first)
        if audio_delay < 0:
            video_delay = abs(audio_delay)
            time.sleep(video_delay)

        try:
            clean_env = get_clean_env_for_system_tools()
            ddd_process = subprocess.Popen(ddd_command,
                                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                         text=True, bufsize=1, universal_newlines=True,
                                         env=clean_env)

            # FAST: Reduced startup check from 1.0s to 0.3s
            time.sleep(0.3)
            if ddd_process.poll() is not None:
                stdout, _ = ddd_process.communicate()
                print(f"[Video] ERROR: DomesdayDuplicator failed to start!")
                if stdout:
                    print(f"[Video] Output: {stdout.strip()}")
                return

            # Monitor output until stop requested
            import select
            while not stop_event.is_set() and ddd_process.poll() is None:
                ready, _, _ = select.select([ddd_process.stdout], [], [], 0.1)
                if ready:
                    line = ddd_process.stdout.readline()
                    if line:
                        print(f"[DD] {line.rstrip()}", flush=True)
                else:
                    time.sleep(0.1)

            # Stop capture
            stop_result = subprocess.run(['DomesdayDuplicator', '--stop-capture'],
                                       capture_output=True, text=True, timeout=10,
                                       env=clean_env)

            if stop_result.returncode == 0:
                try:
                    ddd_process.wait(timeout=30)
                except subprocess.TimeoutExpired:
                    ddd_process.terminate()
                    try:
                        ddd_process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        ddd_process.kill()
                        ddd_process.wait()
            else:
                ddd_process.terminate()
                ddd_process.wait()

        except Exception as e:
            print(f"[Video] Exception: {e}")

    def audio_capture_thread():
        # If audio_delay is positive, audio needs to be delayed (video starts first)
        if audio_delay > 0:
            time.sleep(audio_delay)

        # sox_command is now an audio_capture_spec tuple from prepare_capture_resources():
        # (sox_args, flac_args, log_path). Launching the sox|flac pipeline puts FLAC
        # encoding into a separate process so encoding CPU spikes can't stall sox's
        # ALSA reads (the underlying cause of the long-capture drift we observed).
        sox_args, flac_args, log_path = sox_command
        # FAST: Skip release_audio_device_before_capture() - already done in prepare_capture_resources
        sox_process, flac_process, capture_log = _launch_audio_pipeline(
            sox_args, flac_args, log_path
        )

        while not stop_event.is_set() and sox_process.poll() is None:
            if stop_event.wait(timeout=60):
                break

        # Use SIGINT (like Ctrl+C) for graceful sox shutdown.
        # flac will then see EOF on its stdin, flush its frame buffer to disk, and exit.
        import signal
        sox_process.send_signal(signal.SIGINT)
        sox_process.wait()
        try:
            flac_process.wait(timeout=30)
        except subprocess.TimeoutExpired:
            flac_process.terminate()
            try:
                flac_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                flac_process.kill()
                flac_process.wait()
        try:
            capture_log.close()
        except Exception:
            pass

    # Start both threads
    video_thread = threading.Thread(target=video_capture_thread)
    audio_thread = threading.Thread(target=audio_capture_thread)
    video_thread.start()
    audio_thread.start()

    # Wait for stop condition
    if capture_duration is not None:
        print(f"Capturing for {capture_duration} seconds...")
        time.sleep(capture_duration)
    else:
        print(f"\033[92mCAPTURING - Press Enter to stop...\033[0m")
        input()

    # Signal threads to stop
    stop_event.set()
    video_thread.join()
    audio_thread.join()
    print("Capture stopped.")


def shared_capture_process(sox_command, audio_delay, capture_duration, ddd_command=None):
    """
    A shared function to start video and audio capture in parallel threads.
    - DomesdayDuplicator (video) and sox (audio) are started in separate threads.
    - The audio thread waits for the specified audio_delay before starting.
    - If capture_duration is provided, capture runs for that duration.
    - If capture_duration is None, capture runs until user presses Enter.
    - If ddd_command is provided, uses that command; otherwise uses default headless command.
    """
    # Clean up any stale DomesdayDuplicator stop request file before starting
    # This prevents the new capture from immediately stopping due to a leftover file
    stop_request_file = '/tmp/domesday_stop_request'
    if os.path.exists(stop_request_file):
        try:
            os.remove(stop_request_file)
            print(f"[Cleanup] Removed stale stop request file: {stop_request_file}")
        except Exception as e:
            print(f"[Cleanup] Warning: Could not remove stale stop file: {e}")

    # Create threading events to signal when to stop
    stop_event = threading.Event()

    # Use default DomesdayDuplicator command if none provided
    if ddd_command is None:
        ddd_command = ['DomesdayDuplicator', '--start-capture', '--headless']

    def video_capture_thread():
        # If audio_delay is negative, video needs to be delayed (audio starts first)
        if audio_delay < 0:
            video_delay = abs(audio_delay)
            print(f"[Video Thread] Delaying video start by {video_delay:.3f}s (audio starts first)")
            time.sleep(video_delay)

        print("[Video Thread] Starting DomesdayDuplicator capture...")
        print(f"[Video Thread] Command: {' '.join(ddd_command)}")
        try:
            # Start DomesdayDuplicator with real-time output monitoring
            # Use clean environment to avoid conda Qt library conflicts with system DomesdayDuplicator
            clean_env = get_clean_env_for_system_tools()

            ddd_process = subprocess.Popen(ddd_command,
                                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                         text=True, bufsize=1, universal_newlines=True,
                                         env=clean_env)
            print("[Video Thread] DomesdayDuplicator process started.")
            
            # Give the process a moment to start 
            time.sleep(1)
            if ddd_process.poll() is not None:
                # Process has already terminated - get the error
                stdout, stderr = ddd_process.communicate()
                print(f"[Video Thread] ERROR: DomesdayDuplicator failed to start!")
                print(f"[Video Thread] Return code: {ddd_process.returncode}")
                if stdout:
                    print(f"[Video Thread] Output: {stdout.strip()}")
                return
            
            print("[Video Thread] DomesdayDuplicator is running successfully")
            print("[Video Thread] --- DomesdayDuplicator Status ---")
            
            # Monitor DomesdayDuplicator output in real-time until stop is requested
            import select
            while not stop_event.is_set() and ddd_process.poll() is None:
                # Use select to check if there's output available (non-blocking)
                ready, _, _ = select.select([ddd_process.stdout], [], [], 0.1)
                if ready:
                    line = ddd_process.stdout.readline()
                    if line:
                        # Prefix DomesdayDuplicator output and display immediately
                        print(f"[DD] {line.rstrip()}", flush=True)
                else:
                    # Short sleep to prevent excessive CPU usage
                    time.sleep(0.1)
            print("[Video Thread] Stopping DomesdayDuplicator capture using file-based method...")

            # Send the stop command - this creates the stop file that DomesdayDuplicator watches for
            # Use clean environment to avoid conda Qt library conflicts
            stop_result = subprocess.run(['DomesdayDuplicator', '--stop-capture'],
                                       capture_output=True, text=True, timeout=10,
                                       env=clean_env)
            
            if stop_result.returncode == 0:
                print("[Video Thread] Stop command sent successfully. Waiting for DomesdayDuplicator to complete shutdown...")
                
                # Wait for the process to exit naturally (this allows JSON generation)
                try:
                    ddd_process.wait(timeout=30)  # Give it 30 seconds to complete shutdown
                    print("[Video Thread] DomesdayDuplicator completed shutdown naturally.")
                except subprocess.TimeoutExpired:
                    print("[Video Thread] DomesdayDuplicator did not exit within 30 seconds. Terminating process...")
                    ddd_process.terminate()
                    try:
                        ddd_process.wait(timeout=5)
                        print("[Video Thread] DomesdayDuplicator process terminated.")
                    except subprocess.TimeoutExpired:
                        print("[Video Thread] Process did not respond to terminate. Killing process...")
                        ddd_process.kill()
                        ddd_process.wait()
                        print("[Video Thread] DomesdayDuplicator process killed.")
            else:
                print(f"[Video Thread] Stop command failed (exit code {stop_result.returncode}). Falling back to process termination.")
                ddd_process.terminate()
                ddd_process.wait()
            
            print("[Video Thread] DomesdayDuplicator capture stopped.")
            
        except Exception as e:
            print(f"[Video Thread] Exception starting DomesdayDuplicator: {e}")

    def audio_capture_thread():
        # If audio_delay is positive, audio needs to be delayed (video starts first)
        if audio_delay > 0:
            print(f"[Audio Thread] Delaying audio start by {audio_delay:.3f}s (video starts first)")
            time.sleep(audio_delay)

        # Release audio device from PipeWire/PulseAudio right before starting sox
        release_audio_device_before_capture()
        # Start SOX with direct console output (preserves VU meters)
        sox_process = subprocess.Popen(_wrap_for_realtime(sox_command))

        # Monitor SOX process status without interfering with its output
        start_time = time.time()
        while not stop_event.is_set() and sox_process.poll() is None:
            # Wait for stop event or check every 60 seconds
            if stop_event.wait(timeout=60):
                break  # Stop event was set

        # Use SIGINT (like Ctrl+C) for graceful sox shutdown instead of SIGTERM
        import signal
        sox_process.send_signal(signal.SIGINT)
        sox_process.wait()

    # Create and start the threads
    video_thread = threading.Thread(target=video_capture_thread)
    audio_thread = threading.Thread(target=audio_capture_thread)

    video_thread.start()
    audio_thread.start()

    # Wait for the appropriate stop condition
    if capture_duration is not None:
        print(f"[Main Thread] Capture in progress for {capture_duration} seconds...")
        time.sleep(capture_duration)
        print("[Main Thread] Capture duration elapsed. Signaling threads to stop...")
    else:
        print(f"[Main Thread] Capture in progress. \033[92mPress Enter to stop...\033[0m")
        input()  # Wait for user to press Enter
        print("[Main Thread] User requested stop. Signaling threads to stop...")

    # Signal the threads to stop
    stop_event.set()

    # Wait for the threads to finish
    video_thread.join()
    audio_thread.join()

    print("[Main Thread] All capture processes stopped.")

#!/usr/bin/env python3 -u
# Domesday Duplicator + Clockgen Lite Sync Capture
#
# This script provides automated audio/video synchronisation for VHS archival workflows
# using the Domesday Duplicator RF capture hardware and Clockgen Lite audio capture mod.
#
# Features:
# - GUI automation for Domesday Duplicator software
# - Synchronised SOX audio recording with platform-specific drivers
# - Automated A/V alignment using precision 1kHz test tones
# - Cross-platform support (Windows, macOS, Linux)
# - Archival-quality FLAC and WAV output
#
# Hardware Requirements:
# - Domesday Duplicator RF capture card
# - Clockgen Lite mod for high-quality audio sampling (78.125kHz/24-bit)
# - VCR or other analog video source
#
# Author: Community Project
# Version: 2.0 (Restructured with automated A/V alignment)
# Support: https://digital-archivist.com/community/

import subprocess
import time
import sys
import os
import threading

# Force unbuffered output for real-time console display
os.environ['PYTHONUNBUFFERED'] = '1'
sys.stdout.reconfigure(line_buffering=True)
sys.stderr.reconfigure(line_buffering=True)

# --- CONFIGURATION ---
# DomesdayDuplicator command line interface
# Commands available:
# - DomesdayDuplicator --start-capture: Start capture with GUI visible
# - DomesdayDuplicator --start-capture --headless: Start capture without GUI
# - DomesdayDuplicator --stop-capture: Stop any running capture
# - DomesdayDuplicator --debug --start-capture: Show debug info while capturing

# 2. Output Filename:
#    This will be set dynamically by prompting the user
#    The script will use this name for both RF (.lds) and audio files
CAPTURE_NAME = 'my_vhs_capture'  # Default fallback

# Import configuration management
from config import get_capture_directory, load_config, save_config

# Get actual temp folder for calibration (always uses project temp directory)
def get_temp_folder():
    """Get the temp folder in project directory for calibration/alignment files"""
    project_root = os.path.dirname(os.path.abspath(__file__))
    temp_folder = os.path.join(project_root, "temp")
    if not os.path.exists(temp_folder):
        os.makedirs(temp_folder)
    return temp_folder

# Get configured capture directory for actual captures
def get_capture_folder():
    """Get the configured capture directory for user captures"""
    return get_capture_directory()

# 3. SOX Command:
#    This is your audio recording command. The script will replace
#    'your_capture_name.flac' with the filename defined above.
#    Platform-specific audio settings are configured below.

def get_sox_command(output_filename):
    """Get platform-specific SOX command with optimised buffer settings.

    Uses auto-detected Clockgen audio device from config.py.
    Verifies device accessibility and releases from PipeWire/PulseAudio if needed.
    Falls back to sensible defaults if device not found.
    """
    # Import audio device detection from config
    try:
        from config import prepare_audio_device, get_sox_device_args

        # Use prepare_audio_device for full detection, verification, and release
        audio_info, error = prepare_audio_device()

        if audio_info:
            device = audio_info['device_id']
            sample_rate = str(audio_info.get('sample_rate', 78125))
            bit_depth = str(audio_info.get('bit_depth', 24))
            # Always record 2 channels (L+R audio) - the 3rd channel on some devices
            # is for head switching signals which most setups don't use.
            # The 'remix 1 2' at the end of the sox command extracts just these channels.
            channels = '2'
            device_channels = audio_info.get('channels', 2)
            print(f"Using audio device: {audio_info.get('device_name', device)} ({device})")
            print(f"   Sample rate: {sample_rate} Hz, Bit depth: {bit_depth}, Device channels: {device_channels}, Recording: 2 (L+R)")

            # Determine driver based on platform
            if sys.platform == 'win32':
                driver = 'waveaudio'
            elif sys.platform == 'darwin':
                driver = 'coreaudio'
            else:
                driver = 'alsa'
        else:
            # Device not found or not accessible
            print(f"Warning: {error}")
            print("Falling back to default audio device...")
            driver, device = get_sox_device_args()
            sample_rate = '78125'
            bit_depth = '24'
            channels = '2'

    except ImportError:
        # Fallback if config module not available
        print("Warning: Could not import config module, using legacy device detection")
        if sys.platform == 'win32':
            driver = 'waveaudio'
            device = 'default'
        elif sys.platform == 'darwin':
            driver = 'coreaudio'
            device = 'default'
        else:
            driver = 'alsa'
            device = 'default'
        sample_rate = '78125'
        bit_depth = '24'
        channels = '2'

    # Find sox with ALSA support on Linux
    # Conda's sox doesn't include ALSA driver, so we prefer system sox if available
    sox_cmd = 'sox'
    if sys.platform == 'linux' and driver == 'alsa':
        # Check if system sox exists and has ALSA support
        system_sox = '/usr/bin/sox'
        if os.path.exists(system_sox):
            try:
                result = subprocess.run([system_sox, '--help'], capture_output=True, text=True)
                if 'alsa' in result.stdout.lower():
                    sox_cmd = system_sox
            except:
                pass

    if sys.platform == 'win32':
        # Windows - use DirectSound or WaveIn
        return [
            sox_cmd,
            '-t', driver,
            '-r', sample_rate,
            '-b', bit_depth,
            device,
            output_filename,
            'remix', '1', '2'
        ]
    else:
        # Linux/macOS - use ALSA (Linux) or coreaudio (macOS)
        return [
            sox_cmd,
            '-t', driver,
            '-r', sample_rate,
            '-b', bit_depth,
            '-c', channels,
            device,
            '--buffer', '8192',        # sox processes audio in blocks of this many bytes; small block = responsive VU/progress display (~60 Hz). chrt -r 50 (via _wrap_for_realtime) is what prevents over-runs, NOT the buffer size.
            output_filename,
            'remix', '1', '2'
        ]

# Create capture file paths in temp folder. These default paths are used by
# offer_wav_conversion() further down; the actual capture paths come from
# the live capture flow (start_capture_and_record -> prepare_capture_resources)
# and are unrelated.
CAPTURE_FLAC_PATH = os.path.join(get_temp_folder(), f'{CAPTURE_NAME}.flac')
CAPTURE_WAV_PATH = os.path.join(get_temp_folder(), f'{CAPTURE_NAME}.wav')
# Note: SOX_COMMAND used to be assigned here via get_sox_command(...) at module
# import time. That call eagerly probed the audio device and could print
# "Falling back to default audio device..." if pipewire/wireplumber hadn't
# released the clockgen yet. The variable was never read, so it's been removed
# along with the misleading import-time warning. The live capture path does its
# own device probe at start-capture time, when the device is actually ready.
# --- SCRIPT LOGIC ---

import tempfile
import shutil
from analyze_test_pattern import analyze_test_pattern_timing
from datetime import datetime
import json

# Generate automated alignment filename with date/time
def get_alignment_filename():
    """Generate automated alignment filename with current date and time"""
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    return f"automated_alignment_{timestamp}"

# Alignment file paths (will be created in temp folder with timestamp)
# These will be updated dynamically in perform_av_alignment()
DEFAULT_ALIGNMENT_DURATION_SECONDS = 30  # Default capture duration for alignment


def get_alignment_duration():
    """
    Prompt user for alignment capture duration
    Returns duration in seconds
    """
    print("\n--- ALIGNMENT CAPTURE DURATION ---")
    print("Set the duration for calibration capture.")
    print("")
    print("Recommendations:")
    print("   • 20-30s: Quick calibration (6-12 measurement pairs)")
    print("   • 30-45s: Standard calibration (12-18 measurement pairs)")
    print("   • 45-60s: High precision (18-24 measurement pairs)")
    print("")
    print("Longer captures provide more measurement pairs for better")
    print("statistical accuracy, but take more time to process.")
    print("")
    
    while True:
        try:
            user_input = input(f"Enter capture duration in seconds (default {DEFAULT_ALIGNMENT_DURATION_SECONDS}s): ").strip()
            
            if not user_input:
                duration = DEFAULT_ALIGNMENT_DURATION_SECONDS
                print(f"Using default duration: {duration}s")
                break
            
            duration = int(user_input)
            
            if duration < 10:
                print("ERROR: Duration must be at least 10 seconds for reliable measurements.")
                continue
            elif duration > 300:  # 5 minutes
                print("WARNING: Duration > 5 minutes may be unnecessarily long.")
                confirm = input("Continue with this duration? (y/N): ").strip().lower()
                if confirm not in ['y', 'yes']:
                    continue
            
            # Estimate measurement pairs
            estimated_audio_cycles = duration // 2  # Rough estimate: 1 cycle per 2 seconds
            estimated_video_cycles = estimated_audio_cycles
            estimated_pairs = max(0, min(estimated_audio_cycles, estimated_video_cycles) - 2)
            
            print(f"\nCapture duration set to: {duration} seconds")
            print(f"Estimated measurement pairs: ~{estimated_pairs}")
            print(f"Expected processing time: ~{duration//10 + 2}-{duration//5 + 5} minutes")
            break
            
        except ValueError:
            print("ERROR: Please enter a valid number.")
        except KeyboardInterrupt:
            print("\nAlignment cancelled by user.")
            return None
        except Exception as e:
            print(f"ERROR: {e}")
    
    return duration


# TODO: REMOVE THIS FUNCTION - No longer used after menu restructure (Jan 2026)
# The robust timecode method in the calibration menu replaces this functionality.
# Keeping commented out until we confirm nothing else calls it.
def perform_av_alignment():
    """
    DEPRECATED: This function is no longer used.
    Use the Robust Timecode Method in the A/V Calibration menu instead.
    """
    raise NotImplementedError(
        "perform_av_alignment() is deprecated and has been removed. "
        "Use the Robust Timecode Method in the A/V Calibration menu instead."
    )

def _perform_av_alignment_DISABLED():
    """
    Perform automated audio/video alignment with proper RF decode workflow
    DISABLED - kept for reference only
    """
    try:
        print("\n=== Automated A/V Alignment ===")
        print("IMPORTANT: This workflow requires:")
        print("   1. RF capture from DomesdayDuplicator")
        print("   2. Audio capture from Clockgen Lite")
        print("   3. RF decode to create TBC JSON timing file")
        print("   4. Audio alignment using timing data")
        print()
        
        # Note: We no longer use fixed duration - user controls when to stop
        print("This capture will run until you press ENTER to stop.")
        print("Recommended capture time: 30-60 seconds for good calibration data.")
        
        # Create temp folder if it doesn't exist
        temp_folder = get_temp_folder()
        if not os.path.exists(temp_folder):
            os.makedirs(temp_folder)
            print(f"Created temp folder: {temp_folder}")
        
        # Generate automated filename with timestamp
        alignment_base_name = get_alignment_filename()
        print(f"Using automated calibration filename: {alignment_base_name}")
        
        # Create alignment file paths with timestamp
        alignment_capture_filename = os.path.join(temp_folder, f"{alignment_base_name}.flac")
        alignment_rf_filename = os.path.join(temp_folder, f"{alignment_base_name}.lds")
        alignment_tbc_filename = os.path.join(temp_folder, f"{alignment_base_name}.tbc")
        alignment_tbc_json_filename = os.path.join(temp_folder, f"{alignment_base_name}.tbc.json")
        alignment_video_filename = os.path.join(temp_folder, f"{alignment_base_name}_ffv1.mkv")
        
        print(f"Output directory: {os.path.abspath(temp_folder)}")
        print(f"Output filename: {alignment_base_name}")
        print()

        input("Make sure you've recorded at least 5 minutes of the included test pattern files onto a VHS tape. Press any key to continue or Ctrl-C to stop.")
        input("Ensure your Domesday duplicator is plugged in and powered on and your clockgen lite is connected and working. Press any key to continue.")
        input("Insert your VHS tape into your VCR and press play. It's very important to be playing this alignment tape before calibration. Press any key to start Alignment Capture.")

        # Capture alignment using command line DomesdayDuplicator
        print("\nStarting RF + Audio capture...")
        alignment_sox_command = get_sox_command(alignment_capture_filename)

        try:
            # 1. Start audio capture using command line with zero delay as baseline
            print("Starting SOX audio recording (calibration baseline with 0.0s delay)...")
            time.sleep(0.0)  # Calibration baseline - zero delay
            alignment_sox_command = get_sox_command(alignment_capture_filename)
            release_audio_device_before_capture()  # Release from PipeWire right before starting
            capture_process = subprocess.Popen(alignment_sox_command)
            print("SOX audio recording started")

            # 2. Start video capture using command line with headless mode for minimal latency
            print("Starting DomesdayDuplicator capture (headless mode for minimal latency)...")
            ddd_process = subprocess.Popen(['DomesdayDuplicator', '--start-capture', '--headless',
                                           '--capture-directory', os.path.abspath(temp_folder),
                                           '--output-file', alignment_base_name],
                                      stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

            # Check if process is still running (successful start)
            if ddd_process.poll() is None:
                print("DomesdayDuplicator capture started successfully")
                
                print("\nCAPTURE IN PROGRESS")
                print("Both RF and audio recording are now active")
                print("DO NOT STOP THE VCR YET - let it continue playing!")
                print("\n" + "=" * 50)
                print("  WHEN READY TO STOP CAPTURE:")
                print("  Press ENTER to stop recording safely...")
                print("  (Recommended: 30-60 seconds for good calibration)")
                print("=" * 50)
                
                # Wait for user to press ENTER to stop capture
                try:
                    input()  # Wait for ENTER key
                    print("\nStopping capture...")
                    
                    # Stop SOX audio recording
                    print("Stopping audio recording...")
                    capture_process.terminate()
                    capture_process.wait()
                    print("Audio recording stopped")
                except KeyboardInterrupt:
                    print("\nCtrl+C detected. Stopping capture...")
                    capture_process.terminate()
                    capture_process.wait()
                    print("Audio recording stopped.")

                # 3. Stop video capture using command line with fallback
                print("\nStopping DomesdayDuplicator capture...")

                # First try the command line stop (use clean env to avoid Qt conflicts)
                stop_result = subprocess.run(['DomesdayDuplicator', '--stop-capture'],
                                           capture_output=True, text=True, timeout=10,
                                           env=get_clean_env_for_system_tools())
                
                if stop_result.returncode == 0:
                    print("DomesdayDuplicator capture stopped successfully")
                else:
                    print(f"Warning: DomesdayDuplicator stop returned code {stop_result.returncode}")
                    print("Attempting to terminate DomesdayDuplicator process directly...")
                    
                    # Fallback: terminate the process we started
                    try:
                        ddd_process.terminate()
                        ddd_process.wait(timeout=5)
                        print("DomesdayDuplicator process terminated successfully")
                    except subprocess.TimeoutExpired:
                        print("Process termination timed out, forcing kill...")
                        ddd_process.kill()
                        ddd_process.wait()
                        print("DomesdayDuplicator process killed")
                    except Exception as e:
                        print(f"Error terminating process: {e}")
                        print("You may need to manually stop DomesdayDuplicator")
                
                # Important user message after capture stops
                print("\n" + "="*50)
                print("CAPTURE COMPLETED - IMPORTANT MESSAGE")
                print("="*50)
                print("RF and audio capture has finished successfully!")
                print("")
                print("You can now STOP your VCR/alignment tape.")
                print("   The capture is complete and no longer recording.")
                print("")
                print("Next: RF decode and audio alignment analysis will begin...")
                print("   This will take a few minutes to process the captured data.")
                print("="*50)
                print()
                
                # Give user a moment to see this message
                time.sleep(2)

            else:
                # Process has terminated, get output and error
                stdout, stderr = ddd_process.communicate()
                return_code = ddd_process.returncode
                
                print(f"ERROR: Could not start DomesdayDuplicator capture!")
                print(f"Command failed with return code: {return_code}")
                print(f"Error output: {stderr}")
                print("Please ensure:")
                print("1. DomesdayDuplicator is installed and in your PATH")
                print("2. The hardware is connected properly")
                print("3. No other instance is already running")
                print("\nAlignment capture cancelled.")
                return

        except subprocess.TimeoutExpired:
            print("ERROR: DomesdayDuplicator command timed out")
            print("This might indicate the command is hanging or waiting for user input")
            return
        except FileNotFoundError:
            print("ERROR: DomesdayDuplicator command not found!")
            print("Please ensure DomesdayDuplicator is installed and available in your PATH")
            return
        except Exception as e:
            print(f"Capture error: {e}")
            return

        # 5. RF Decode step
        print("\nSTARTING RF DECODE WORKFLOW")
        print("Looking for RF capture file in temp folder...")
        
        # Find the most recent .lds file (RF capture) in temp folder
        if not os.path.exists(temp_folder):
            print(f"Temp folder {temp_folder} does not exist!")
            print("Please ensure the DomesdayDuplicator output location is configured correctly.")
            return
            
        lds_files = [f for f in os.listdir(temp_folder) if f.endswith('.lds')]
        if not lds_files:
            print(f"No RF capture files (.lds) found in {temp_folder}!")
            print("Please ensure the Domesday Duplicator created an RF capture file in the temp folder.")
            return
        
        # Get the most recent RF file (with full path)
        lds_paths = [os.path.join(temp_folder, f) for f in lds_files]
        rf_file = max(lds_paths, key=os.path.getmtime)
        print(f"Found RF capture: {rf_file}")
        
        # Check if we already have decoded files
        tbc_file = rf_file.replace('.lds', '.tbc')
        tbc_json_file = rf_file.replace('.lds', '.tbc.json')
        
        if os.path.exists(tbc_json_file):
            print(f"TBC JSON already exists: {tbc_json_file}")
        else:
            print("\nRunning vhs-decode...")
            if not run_vhs_decode_with_params(rf_file, tbc_file, 'pal', 'SP'):
                print("RF decode failed")
                return
        
        # Check if we need to export video
        video_file = rf_file.replace('.lds', '_ffv1.mkv')
        if os.path.exists(video_file):
            print(f"Video export already exists: {video_file}")
        else:
            print("\nRunning tbc-video-export...")
            if not run_tbc_video_export(tbc_file, video_file):
                print("Video export failed, but continuing with audio alignment...")
        
        print("\nRF decode workflow complete!")
        
        # 6. Audio timing analysis (using raw audio)
        print(f"\nUsing TBC JSON file: {tbc_json_file}")
        
        print("\nSkipping mechanical alignment - analyzing raw audio directly for calibration")
        print("(This eliminates alignment-induced measurement errors)")
        
        # Check if captured audio file exists
        if os.path.exists(alignment_capture_filename):
            print(f"\nUsing raw audio file: {alignment_capture_filename}")
            
            # Show file details for verification
            file_size = os.path.getsize(alignment_capture_filename) / (1024*1024)  # MB
            file_time = time.ctime(os.path.getmtime(alignment_capture_filename))
            print(f"   File size: {file_size:.1f} MB")
            print(f"   Modified: {file_time}")
            
            # Run test pattern timing analysis on raw audio and video
            print("\nRunning test pattern timing analysis on raw audio...")
            offset_seconds = analyze_test_pattern_timing(alignment_capture_filename, video_file)
            
            if offset_seconds is not None:
                print(f"\n" + "="*60)
                print(f"CALIBRATION MEASUREMENT RESULTS")
                print(f"="*60)
                print(f"\nTIMING ANALYSIS:")
                print(f"   Measured timing offset: {offset_seconds:+.3f} seconds")
                print(f"   Measurement consistency: Good (multi-cycle average)")
                print(f"   Baseline reference: 0.000s (no GUI delay)")
                
                # Read current delay from configuration for comparison
                config = load_config()
                current_delay = config.get('audio_delay', 0.000)
                
                # Direct measurement - no hardcoded delays
                # The measured offset directly represents the timing difference
                if offset_seconds > 0:
                    # Audio starts AFTER video - need to delay audio less or start it earlier
                    required_delay = current_delay - offset_seconds
                    if required_delay < 0:
                        required_delay = 0.0
                        timing_explanation = "Audio starts too late - reduce audio delay to minimum (0.0s)"
                    else:
                        timing_explanation = "Audio starts too late - reduce audio delay"
                    
                    print(f"\nCALIBRATION RESULTS:")
                    print(f"   Measured offset: {offset_seconds:.3f}s (audio after video)")
                    print(f"   Current configured delay: {current_delay:.3f}s")
                    print(f"   Required delay for sync: {required_delay:.3f}s")
                    print(f"")
                    print(f"   EXPLANATION: {timing_explanation}")
                    print(f"   Audio starts {offset_seconds:.3f}s too late relative to video.")
                    if required_delay == 0.0:
                        print(f"   Solution: Set audio delay to minimum (0.0s).")
                    else:
                        print(f"   Solution: Reduce audio delay by {offset_seconds:.3f}s.")
                elif offset_seconds < 0:
                    # Audio starts BEFORE video - cannot fix with positive delay
                    required_delay = 0.0
                    print(f"\nCALIBRATION RESULTS:")
                    print(f"   Audio starts {abs(offset_seconds):.3f}s TOO EARLY")
                    print(f"   Current configured delay: {current_delay:.3f}s")
                    print(f"   Required delay: {required_delay:.3f}s (minimum possible)")
                    print(f"   WARNING: Cannot fix early audio with positive delay")
                    print(f"   Consider checking hardware timing or connection order")
                else:
                    # Perfect timing
                    print(f"\nPERFECT TIMING:")
                    print(f"   Audio and video are perfectly synchronized")
                    print(f"   Required delay: 0.000s (no delay needed)")
                    required_delay = 0.0
                
                print(f"\nRECOMMENDATION:")
                print(f"   Set script delay to: {required_delay:.3f} seconds")
                print(f"   This should result in ~0.000s offset on next measurement")
                print(f"="*60)
                
                if abs(offset_seconds) > 0.010:  # More than 10ms
                    print(f"\nNEXT STEPS:")
                    print(f"   1. Auto-applying calibration to capture function...")
                    
                    # Automatically update the capture delay (not alignment delay)
                    success = update_capture_delay_only(required_delay)
                    if success:
                        print(f"    Capture delay updated to {required_delay:.3f}s")
                        print(f"   2. Calibration complete - ready for synchronized captures")
                        print(f"   3. Next capture should show ~0.000s offset")
                    else:
                        print(f"    Failed to auto-update delay")
                        print(f"   2. Please manually set delay to {required_delay:.3f}s")
                        print(f"   3. Run another calibration to verify")
                    
                    # Save calibration results to JSON metadata file (no duration since user-controlled)
                    save_calibration_results(alignment_base_name, offset_seconds, required_delay, 
                                           0, temp_folder)  # 0 indicates user-controlled duration
                else:
                    print(f"\nSYSTEM WELL CALIBRATED:")
                    print(f"   Offset < 10ms - no adjustment needed")
                    print(f"   Current capture delay ({current_delay:.3f}s) is optimal")
                    
                    # Save calibration results even if no update needed (no duration since user-controlled)
                    save_calibration_results(alignment_base_name, offset_seconds, current_delay, 
                                           0, temp_folder)  # 0 indicates user-controlled duration
            else:
                print("\nTest pattern timing analysis failed")
                print("This could be due to:")
                print("- Poor audio/video quality in capture")
                print("- Missing test pattern signal")
                print("- Test pattern not detected in video or audio")
        else:
            print("\nRaw audio file not found")
            print("Cannot proceed with test pattern analysis without captured audio file")
        
        print("\nAlignment workflow complete!")
        print("Files created:")
        print(f"   Audio: {alignment_capture_filename}")
        print(f"   TBC data: {tbc_file}")

    except KeyboardInterrupt:
        print("\nA/V Alignment cancelled by user")
    except Exception as e:
        print(f"\nERROR during A/V Alignment: {e}")


def cleanup_existing_processes():
    """
    Check for and clean up any existing vhs-decode, sox, or DomesdayDuplicator processes
    that might interfere with new captures
    """
    try:
        # Check for running sox recording processes (these can hold the audio device)
        result = subprocess.run(['pgrep', '-f', 'sox.*alsa|sox.*hw:'], capture_output=True, text=True)
        if result.returncode == 0 and result.stdout.strip():
            pids = result.stdout.strip().split('\n')
            print(f"\nFound {len(pids)} running sox process(es) that may be holding audio device")
            for pid in pids:
                if pid.strip():
                    print(f"   Terminating sox process (PID: {pid})")
                    try:
                        subprocess.run(['kill', pid.strip()], check=True)
                    except subprocess.CalledProcessError:
                        print(f"   Warning: Could not terminate process {pid}")
            print("   Sox cleanup completed")
            time.sleep(0.5)  # Give time for device to be released

        # Check for running vhs-decode processes
        result = subprocess.run(['pgrep', '-f', 'vhs-decode'], capture_output=True, text=True)
        if result.returncode == 0 and result.stdout.strip():
            pids = result.stdout.strip().split('\n')
            print(f"\nFound {len(pids)} running vhs-decode process(es)")
            for pid in pids:
                if pid.strip():
                    print(f"   Terminating vhs-decode process (PID: {pid})")
                    try:
                        subprocess.run(['kill', pid.strip()], check=True)
                    except subprocess.CalledProcessError:
                        print(f"   Warning: Could not terminate process {pid}")
            print("   Cleanup completed")

        # Check for running DomesdayDuplicator processes (but don't kill them automatically)
        result = subprocess.run(['pgrep', '-f', 'DomesdayDuplicator.*capture'], capture_output=True, text=True)
        if result.returncode == 0 and result.stdout.strip():
            pids = result.stdout.strip().split('\n')
            print(f"\nWarning: Found {len(pids)} running DomesdayDuplicator capture process(es)")
            print("   These may interfere with new captures")
            print("   Consider stopping them manually or use 'Stop Current Capture' menu option")

    except Exception as e:
        print(f"Process cleanup warning: {e}")

def check_command_available(command_name):
    """
    Check if a command is available in the system PATH
    Returns the full path if found, None otherwise
    """
    try:
        result = subprocess.run(['which', command_name], capture_output=True, text=True)
        if result.returncode == 0:
            return result.stdout.strip()
        
        # Try 'where' on Windows
        if sys.platform == 'win32':
            result = subprocess.run(['where', command_name], capture_output=True, text=True)
            if result.returncode == 0:
                return result.stdout.strip().split('\n')[0]  # Get first match
        
        return None
    except Exception:
        return None


def run_vhs_decode(rf_filename, tbc_filename, additional_params=None):
    """
    Run vhs-decode with PAL settings on the RF capture file
    Returns True if successful, False otherwise
    
    Args:
        rf_filename: Input RF (.lds) file path
        tbc_filename: Output TBC file path
        additional_params: Optional string with additional vhs-decode parameters
    """
    # Clean up any existing vhs-decode processes first
    try:
        result = subprocess.run(['pgrep', '-f', 'vhs-decode'], capture_output=True, text=True)
        if result.returncode == 0 and result.stdout.strip():
            pids = result.stdout.strip().split('\n')
            print(f"Found {len(pids)} existing vhs-decode process(es), terminating...")
            for pid in pids:
                if pid.strip():
                    try:
                        subprocess.run(['kill', pid.strip()], check=True)
                        print(f"   Terminated PID: {pid}")
                    except subprocess.CalledProcessError:
                        print(f"   Warning: Could not terminate process {pid}")
    except Exception as e:
        print(f"Process cleanup warning: {e}")
    
    # Check if vhs-decode is available
    vhs_decode_path = check_command_available('vhs-decode')
    if not vhs_decode_path:
        print("ERROR: vhs-decode not found in system PATH")
        print("Please install vhs-decode or ensure it's in your PATH")
        print("Visit: https://github.com/oyvindln/vhs-decode")
        return False
    
    print(f"Using vhs-decode: {vhs_decode_path}")
    
    # Build the vhs-decode command with the specified options
    cmd = [
        'vhs-decode',
        '--tf', 'vhs',          # Format: VHS
        '-t', '3',              # Threads: 3
        '--ts', 'SP',           # Tape speed: SP (standard play)
        '--pal',                # PAL format
        '--no_resample',        # No resampling
        '--recheck_phase',      # Recheck phase
        '--ire0_adjust',        # IRE 0 adjust
    ]
    
    # Add additional user parameters if provided
    if additional_params and additional_params.strip():
        # Split the additional parameters and add them to the command
        extra_params = additional_params.strip().split()
        cmd.extend(extra_params)
        print(f"Adding user parameters: {' '.join(extra_params)}")
    
    # Add input and output files at the end
    cmd.extend([
        rf_filename,            # Input RF file
        tbc_filename.replace('.tbc', '')  # Output base name (without extension)
    ])
    
    print(f"Command: {' '.join(cmd)}")
    print("This may take several minutes depending on capture length...")
    
    try:
        # Use stdbuf to force unbuffered output from vhs-decode
        # Add stdbuf -o0 to disable stdout buffering
        unbuffered_cmd = ['stdbuf', '-o0'] + cmd
        
        # Try with stdbuf first, fall back to regular command if stdbuf not available
        try:
            process = subprocess.Popen(unbuffered_cmd, 
                                     stdout=subprocess.PIPE, 
                                     stderr=subprocess.STDOUT,
                                     universal_newlines=True)
        except FileNotFoundError:
            # stdbuf not available, use regular command
            process = subprocess.Popen(cmd, 
                                     stdout=subprocess.PIPE, 
                                     stderr=subprocess.STDOUT,
                                     universal_newlines=True)
        
        # Read output line by line in real-time
        import sys
        while True:
            output = process.stdout.readline()
            if output == '' and process.poll() is not None:
                break
            if output:
                # Print immediately without buffering
                print(f"  {output.rstrip()}", flush=True)
        
        rc = process.returncode
        
        if rc == 0:
            print("vhs-decode completed successfully")
            
            # Verify output files exist
            tbc_json_file = tbc_filename + '.json'
            if os.path.exists(tbc_filename) and os.path.exists(tbc_json_file):
                print(f"Created: {tbc_filename}")
                print(f"Created: {tbc_json_file}")
                return True
            else:
                print("vhs-decode completed but expected output files not found")
                return False
        else:
            print(f"vhs-decode failed with exit code {rc}")
            return False
            
    except Exception as e:
        print(f"Error running vhs-decode: {e}")
        return False


def run_vhs_decode_ntsc(rf_filename, tbc_filename, additional_params=None):
    """
    Run vhs-decode with NTSC settings on the RF capture file
    Returns True if successful, False otherwise
    
    Args:
        rf_filename: Input RF (.lds) file path
        tbc_filename: Output TBC file path
        additional_params: Optional string with additional vhs-decode parameters
    """
    # Clean up any existing vhs-decode processes first
    try:
        result = subprocess.run(['pgrep', '-f', 'vhs-decode'], capture_output=True, text=True)
        if result.returncode == 0 and result.stdout.strip():
            pids = result.stdout.strip().split('\n')
            print(f"Found {len(pids)} existing vhs-decode process(es), terminating...")
            for pid in pids:
                if pid.strip():
                    try:
                        subprocess.run(['kill', pid.strip()], check=True)
                        print(f"   Terminated PID: {pid}")
                    except subprocess.CalledProcessError:
                        print(f"   Warning: Could not terminate process {pid}")
    except Exception as e:
        print(f"Process cleanup warning: {e}")
    
    # Check if vhs-decode is available
    vhs_decode_path = check_command_available('vhs-decode')
    if not vhs_decode_path:
        print("ERROR: vhs-decode not found in system PATH")
        print("Please install vhs-decode or ensure it's in your PATH")
        print("Visit: https://github.com/oyvindln/vhs-decode")
        return False
    
    print(f"Using vhs-decode: {vhs_decode_path}")
    
    # Build the vhs-decode command with NTSC-specific options
    cmd = [
        'vhs-decode',
        '--tf', 'vhs',          # Format: VHS
        '-t', '3',              # Threads: 3
        '--ts', 'SP',           # Tape speed: SP (standard play)
        '--ntsc',               # NTSC format (different from PAL version)
        '--no_resample',        # No resampling
        '--recheck_phase',      # Recheck phase
        '--ire0_adjust',        # IRE 0 adjust
    ]
    
    # Add additional user parameters if provided
    if additional_params and additional_params.strip():
        # Split the additional parameters and add them to the command
        extra_params = additional_params.strip().split()
        cmd.extend(extra_params)
        print(f"Adding user parameters: {' '.join(extra_params)}")
    
    # Add input and output files at the end
    cmd.extend([
        rf_filename,            # Input RF file
        tbc_filename.replace('.tbc', '')  # Output base name (without extension)
    ])
    
    print(f"Command: {' '.join(cmd)}")
    print("This may take several minutes depending on capture length...")
    
    try:
        # Use stdbuf to force unbuffered output from vhs-decode
        # Add stdbuf -o0 to disable stdout buffering
        unbuffered_cmd = ['stdbuf', '-o0'] + cmd
        
        # Try with stdbuf first, fall back to regular command if stdbuf not available
        try:
            process = subprocess.Popen(unbuffered_cmd, 
                                     stdout=subprocess.PIPE, 
                                     stderr=subprocess.STDOUT,
                                     universal_newlines=True)
        except FileNotFoundError:
            # stdbuf not available, use regular command
            process = subprocess.Popen(cmd, 
                                     stdout=subprocess.PIPE, 
                                     stderr=subprocess.STDOUT,
                                     universal_newlines=True)
        
        # Read output line by line in real-time
        import sys
        while True:
            output = process.stdout.readline()
            if output == '' and process.poll() is not None:
                break
            if output:
                # Print immediately without buffering
                print(f"  {output.rstrip()}", flush=True)
        
        rc = process.returncode
        
        if rc == 0:
            print("vhs-decode completed successfully")
            
            # Verify output files exist
            tbc_json_file = tbc_filename + '.json'
            if os.path.exists(tbc_filename) and os.path.exists(tbc_json_file):
                print(f"Created: {tbc_filename}")
                print(f"Created: {tbc_json_file}")
                return True
            else:
                print("vhs-decode completed but expected output files not found")
                return False
        else:
            print(f"vhs-decode failed with exit code {rc}")
            return False
            
    except Exception as e:
        print(f"Error running vhs-decode: {e}")
        return False


def run_vhs_decode_with_params(rf_filename, tbc_filename, video_standard, tape_speed, additional_params=None):
    """
    Unified VHS decode function with configurable video standard and tape speed
    Returns True if successful, False otherwise
    
    Args:
        rf_filename: Input RF (.lds) file path
        tbc_filename: Output TBC file path
        video_standard: 'pal' or 'ntsc'
        tape_speed: 'SP', 'LP', or 'EP'
        additional_params: Optional string with additional vhs-decode parameters
    """
    # Clean up any existing vhs-decode processes first
    try:
        result = subprocess.run(['pgrep', '-f', 'vhs-decode'], capture_output=True, text=True)
        if result.returncode == 0 and result.stdout.strip():
            pids = result.stdout.strip().split('\n')
            print(f"Found {len(pids)} existing vhs-decode process(es), terminating...")
            for pid in pids:
                if pid.strip():
                    try:
                        subprocess.run(['kill', pid.strip()], check=True)
                        print(f"   Terminated PID: {pid}")
                    except subprocess.CalledProcessError:
                        print(f"   Warning: Could not terminate process {pid}")
    except Exception as e:
        print(f"Process cleanup warning: {e}")
    
    # Check if vhs-decode is available
    vhs_decode_path = check_command_available('vhs-decode')
    if not vhs_decode_path:
        print("ERROR: vhs-decode not found in system PATH")
        print("Please install vhs-decode or ensure it's in your PATH")
        print("Visit: https://github.com/oyvindln/vhs-decode")
        return False
    
    print(f"Using vhs-decode: {vhs_decode_path}")
    
    # Build the vhs-decode command with configurable options
    cmd = [
        'vhs-decode',
        '--tf', 'vhs',          # Format: VHS
        '-t', '3',              # Threads: 3
        '--ts', tape_speed,     # Tape speed: SP, LP, or EP
        '--no_resample',        # No resampling
        '--recheck_phase',      # Recheck phase
        '--ire0_adjust',        # IRE 0 adjust
    ]
    
    # Add video standard (PAL or NTSC)
    if video_standard.lower() == 'pal':
        cmd.append('--pal')
    elif video_standard.lower() == 'ntsc':
        cmd.append('--ntsc')
    else:
        print(f"ERROR: Invalid video standard '{video_standard}'. Must be 'pal' or 'ntsc'.")
        return False
    
    # Add additional user parameters if provided
    if additional_params and additional_params.strip():
        # Split the additional parameters and add them to the command
        extra_params = additional_params.strip().split()
        cmd.extend(extra_params)
        print(f"Adding user parameters: {' '.join(extra_params)}")
    
    # Add input and output files at the end
    cmd.extend([
        rf_filename,            # Input RF file
        tbc_filename.replace('.tbc', '')  # Output base name (without extension)
    ])
    
    print(f"Command: {' '.join(cmd)}")
    print(f"This may take several minutes depending on capture length...")
    
    try:
        # Use stdbuf to force unbuffered output from vhs-decode
        # Add stdbuf -o0 to disable stdout buffering
        unbuffered_cmd = ['stdbuf', '-o0'] + cmd
        
        # Try with stdbuf first, fall back to regular command if stdbuf not available
        try:
            process = subprocess.Popen(unbuffered_cmd, 
                                     stdout=subprocess.PIPE, 
                                     stderr=subprocess.STDOUT,
                                     universal_newlines=True)
        except FileNotFoundError:
            # stdbuf not available, use regular command
            process = subprocess.Popen(cmd, 
                                     stdout=subprocess.PIPE, 
                                     stderr=subprocess.STDOUT,
                                     universal_newlines=True)
        
        # Read output line by line in real-time
        import sys
        while True:
            output = process.stdout.readline()
            if output == '' and process.poll() is not None:
                break
            if output:
                # Print immediately without buffering
                print(f"  {output.rstrip()}", flush=True)
        
        rc = process.returncode
        
        if rc == 0:
            print(f"{video_standard.upper()} {tape_speed} vhs-decode completed successfully")
            
            # Verify output files exist
            tbc_json_file = tbc_filename + '.json'
            if os.path.exists(tbc_filename) and os.path.exists(tbc_json_file):
                print(f"Created: {tbc_filename}")
                print(f"Created: {tbc_json_file}")
                return True
            else:
                print("vhs-decode completed but expected output files not found")
                return False
        else:
            print(f"vhs-decode failed with exit code {rc}")
            return False
            
    except Exception as e:
        print(f"Error running vhs-decode: {e}")
        return False


def run_tbc_video_export(tbc_filename, video_filename):
    """
    Run tbc-video-export to create FFV1 video file with PAL settings
    Returns True if successful, False otherwise
    """
    # Check if tbc-video-export is available
    tbc_export_path = check_command_available('tbc-video-export')
    if not tbc_export_path:
        print("ERROR: tbc-video-export not found in system PATH")
        print("Please install ld-decode tools or ensure tbc-video-export is in your PATH")
        print("Visit: https://github.com/happycube/ld-decode")
        return False
    
    print(f"Using tbc-video-export: {tbc_export_path}")
    
    # Build the tbc-video-export command with PAL video system
    cmd = [
        'tbc-video-export',
        '--video-system', 'pal', # Force PAL video system
        tbc_filename,           # Input TBC file
        video_filename          # Output video file
    ]
    
    print(f"Command: {' '.join(cmd)}")
    print("Exporting video file...")
    
    try:
        # Run with output capture that avoids terminal ioctl issues
        # Use DEVNULL for stdin to prevent ioctl errors
        with subprocess.Popen(cmd, 
                            stdout=subprocess.PIPE, 
                            stderr=subprocess.PIPE,
                            stdin=subprocess.DEVNULL,
                            universal_newlines=True,
                            bufsize=1) as process:
            
            # Capture output line by line from both stdout and stderr
            import select
            import io
            
            # Set up for non-blocking reads
            stdout_lines = []
            stderr_lines = []
            
            # Read all output
            stdout, stderr = process.communicate()
            
            # Print stdout (normal output)
            if stdout:
                for line in stdout.splitlines():
                    if line.strip():  # Skip empty lines
                        print(f"  {line}")
            
            # Handle stderr - filter out the ioctl error but show other errors
            if stderr:
                for line in stderr.splitlines():
                    line_stripped = line.strip()
                    if line_stripped and "Inappropriate ioctl for device" not in line_stripped:
                        print(f"  {line_stripped}")
                    elif "Inappropriate ioctl for device" in line_stripped:
                        # Just note this error but don't show it (it's non-fatal)
                        pass
            
            rc = process.returncode
        
        if rc == 0:
            print("tbc-video-export completed successfully")
            
            # Verify output file exists
            if os.path.exists(video_filename):
                file_size = os.path.getsize(video_filename) / (1024**2)  # MB
                print(f"Created: {video_filename} ({file_size:.1f} MB)")
                return True
            else:
                print("tbc-video-export completed but output file not found")
                return False
        else:
            print(f"tbc-video-export failed with exit code {rc}")
            return False
            
    except Exception as e:
        print(f"Error running tbc-video-export: {e}")
        return False


def run_tbc_video_export_ntsc(tbc_filename, video_filename):
    """
    Run tbc-video-export to create FFV1 video file with NTSC settings
    Returns True if successful, False otherwise
    """
    # Check if tbc-video-export is available
    tbc_export_path = check_command_available('tbc-video-export')
    if not tbc_export_path:
        print("ERROR: tbc-video-export not found in system PATH")
        print("Please install ld-decode tools or ensure tbc-video-export is in your PATH")
        print("Visit: https://github.com/happycube/ld-decode")
        return False
    
    print(f"Using tbc-video-export: {tbc_export_path}")
    
    # Build the tbc-video-export command with NTSC video system
    cmd = [
        'tbc-video-export',
        '--video-system', 'ntsc', # Force NTSC video system
        tbc_filename,           # Input TBC file
        video_filename          # Output video file
    ]
    
    print(f"Command: {' '.join(cmd)}")
    print("Exporting video file...")
    
    try:
        # Run with output capture that avoids terminal ioctl issues
        # Use DEVNULL for stdin to prevent ioctl errors
        with subprocess.Popen(cmd, 
                            stdout=subprocess.PIPE, 
                            stderr=subprocess.PIPE,
                            stdin=subprocess.DEVNULL,
                            universal_newlines=True,
                            bufsize=1) as process:
            
            # Capture output line by line from both stdout and stderr
            import select
            import io
            
            # Set up for non-blocking reads
            stdout_lines = []
            stderr_lines = []
            
            # Read all output
            stdout, stderr = process.communicate()
            
            # Print stdout (normal output)
            if stdout:
                for line in stdout.splitlines():
                    if line.strip():  # Skip empty lines
                        print(f"  {line}")
            
            # Handle stderr - filter out the ioctl error but show other errors
            if stderr:
                for line in stderr.splitlines():
                    line_stripped = line.strip()
                    if line_stripped and "Inappropriate ioctl for device" not in line_stripped:
                        print(f"  {line_stripped}")
                    elif "Inappropriate ioctl for device" in line_stripped:
                        # Just note this error but don't show it (it's non-fatal)
                        pass
            
            rc = process.returncode
        
        if rc == 0:
            print("tbc-video-export completed successfully")
            
            # Verify output file exists
            if os.path.exists(video_filename):
                file_size = os.path.getsize(video_filename) / (1024**2)  # MB
                print(f"Created: {video_filename} ({file_size:.1f} MB)")
                return True
            else:
                print("tbc-video-export completed but output file not found")
                return False
        else:
            print(f"tbc-video-export failed with exit code {rc}")
            return False
            
    except Exception as e:
        print(f"Error running tbc-video-export: {e}")
        return False


def wait_for_file_ready(file_path, max_wait_seconds=30, check_interval=0.5):
    """
    Wait for a file to be fully written and ready for reading
    Returns True if file is ready, False if timeout exceeded
    """
    print(f"Waiting for file to be ready: {os.path.basename(file_path)}")
    
    start_time = time.time()
    last_size = -1
    stable_count = 0
    
    while time.time() - start_time < max_wait_seconds:
        if not os.path.exists(file_path):
            print(f"  File does not exist yet, waiting...")
            time.sleep(check_interval)
            continue
        
        try:
            current_size = os.path.getsize(file_path)
            
            # Check if file size is stable (indicates writing is complete)
            if current_size == last_size and current_size > 0:
                stable_count += 1
                if stable_count >= 3:  # File size stable for 3 checks
                    print(f"   File ready ({current_size} bytes)")
                    return True
            else:
                stable_count = 0
                last_size = current_size
                print(f"  File size: {current_size} bytes (still growing)")
            
        except (OSError, IOError) as e:
            print(f"  File access error: {e}")
        
        time.sleep(check_interval)
    
    print(f"    Timeout waiting for file to be ready ({max_wait_seconds}s)")
    return False


def analyze_alignment_with_tbc(audio_filename, tbc_json_filename):
    """
    Analyse audio alignment using TBC JSON timing data
    This calls the proper vhs-decode-auto-audio-align script
    Returns offset in seconds, or None if analysis fails
    """
    if not os.path.exists(audio_filename):
        print(f"ERROR: Audio file {audio_filename} not found")
        return None
        
    if not os.path.exists(tbc_json_filename):
        print(f"ERROR: TBC JSON file {tbc_json_filename} not found")
        return None
    
    # Look for the audio alignment script
    alignment_script_paths = [
        'tools/audio-sync/vhs_audio_align.py',
        'vhs_audio_align.py',
        'tools/vhs_audio_align.py'
    ]
    
    alignment_script = None
    for script_path in alignment_script_paths:
        if os.path.exists(script_path):
            alignment_script = script_path
            break
    
    if not alignment_script:
        print("ERROR: vhs_audio_align.py script not found!")
        print("Looked in:")
        for path in alignment_script_paths:
            print(f"   - {path}")
        print("\nPlease ensure the audio alignment script is available.")
        return None
    
    print(f"Using alignment script: {alignment_script}")
    print(f"Audio file: {audio_filename}")
    print(f"TBC JSON: {tbc_json_filename}")
    
    try:
        # Run the alignment analysis with proper output file (keep this for test pattern analysis)
        print("Running alignment analysis...")
        # Generate aligned filename based on the input audio filename
        base_name = os.path.splitext(os.path.basename(audio_filename))[0]
        aligned_output = os.path.join(os.path.dirname(audio_filename), f"{base_name}_aligned.flac")
        result = subprocess.run([
            sys.executable, alignment_script, 
            audio_filename, tbc_json_filename, aligned_output
        ], capture_output=True, text=True)  # No timeout - allow long-running alignment processes
            
        if result.returncode == 0:
            print("Alignment analysis completed successfully")
            print("Script output:")
            print(result.stdout)
            
            # Parse the output to extract timing offset
            output_lines = result.stdout.strip().split('\n')
            
            # Look for various timing offset patterns in the output
            import re
            
            # Check if alignment was successful first
            alignment_success = False
            if 'Audio alignment completed successfully!' in result.stdout:
                alignment_success = True
                print("Audio alignment tool completed successfully")
            
            # Look for timing offset information in various formats
            for line in output_lines:
                line_lower = line.lower().strip()
                
                # Pattern 1: "offset: X.XXXs" or "offset: XXXms"
                offset_match = re.search(r'offset:?\s*([+-]?\d+\.?\d*)\s*(s|ms|second|millisecond)', line_lower)
                if offset_match:
                    try:
                        offset_value = float(offset_match.group(1))
                        unit = offset_match.group(2)
                        
                        # Convert to seconds if needed
                        if unit in ['ms', 'millisecond']:
                            offset_value = offset_value / 1000.0
                        
                        print(f"Detected timing offset: {offset_value:.3f}s")
                        return offset_value
                    except (ValueError, AttributeError) as e:
                        print(f"Could not parse offset from line: {line}")
                        continue
                
                # Pattern 2: Look for delay/timing information
                delay_match = re.search(r'delay:?\s*([+-]?\d+\.?\d*)\s*(s|ms|second|millisecond)', line_lower)
                if delay_match:
                    try:
                        delay_value = float(delay_match.group(1))
                        unit = delay_match.group(2)
                        
                        if unit in ['ms', 'millisecond']:
                            delay_value = delay_value / 1000.0
                        
                        print(f"Detected timing delay: {delay_value:.3f}s")
                        return delay_value
                    except (ValueError, AttributeError) as e:
                        continue
                
                # Pattern 3: Check for "no adjustment needed" type messages
                if any(phrase in line_lower for phrase in ['no adjustment', 'already aligned', 'no correction needed', 'perfectly aligned']):
                    print("Audio appears to already be well aligned")
                    return 0.0
            
            # If alignment was successful, return the aligned audio file path
            if alignment_success and os.path.exists(aligned_output):
                print(f"Audio alignment completed successfully: {aligned_output}")
                return aligned_output
            
            print("Could not extract timing offset from analysis output")
            print("This may indicate the analysis couldn't detect timing patterns")
            return None
            
        else:
            print(f"Alignment analysis failed (exit code {result.returncode})")
            print("Error output:")
            print(result.stderr)
            print("Standard output:")
            print(result.stdout)
            return None
            
    except subprocess.TimeoutExpired:
        print("Alignment analysis timed out (>5 minutes)")
        print("This could indicate:")
        print("- Very large audio files")
        print("- Complex analysis requirements")
        print("- Script hanging or waiting for input")
        return None
    except Exception as e:
        print(f"Error running alignment analysis: {e}")
        return None


def analyze_alignment_capture(capture_filename):
    """
    Analyse the captured audio to detect timing offset
    Returns offset in seconds, or None if analysis fails
    """
    if not os.path.exists(capture_filename):
        print(f"ERROR: Capture file {capture_filename} not found")
        return None
    
    print("Running audio pattern analysis...")
    
    # Try the simple analyser first (no external dependencies)
    try:
        result = subprocess.run([
            sys.executable, 'tools/simple_audio_analyzer.py', capture_filename
        ], capture_output=True, text=True, timeout=60)
        
        if result.returncode == 0:
            # Parse the output to extract the offset
            output_lines = result.stdout.strip().split('\n')
            for line in output_lines:
                if 'Detected timing offset:' in line:
                    # Extract offset value
                    try:
                        offset_str = line.split('Detected timing offset:')[1].split('s')[0].strip()
                        offset = float(offset_str)
                        print(f"Analysis complete: {offset:.3f}s offset detected")
                        return offset
                    except (IndexError, ValueError) as e:
                        print(f"Error parsing analysis result: {e}")
                        break
            
            # If we get here, analysis completed but no offset was found
            print("Analysis completed but could not detect timing pattern")
            print("This may mean:")
            print("- The test pattern audio was not recorded")
            print("- The audio quality is too poor for analysis")
            print("- The timing is already perfect (no offset)")
            return 0.0  # Assume no offset needed
        else:
            print(f"Analysis failed: {result.stderr}")
            print("Falling back to manual inspection method...")
            return None
            
    except subprocess.TimeoutExpired:
        print("Analysis timed out")
        return None
    except FileNotFoundError:
        print("Audio analysis script not found")
        print("Using simplified analysis...")
        return simple_analysis_fallback(capture_filename)


def simple_analysis_fallback(capture_filename):
    """
    Simple fallback analysis using just FFmpeg
    """
    print("Performing basic audio level analysis...")

    try:
        # Extract a short segment and analyse audio levels
        cmd = [
            'ffmpeg', '-v', 'quiet', '-stats',
            '-i', capture_filename,
            '-ss', '10', '-t', '30',  # 30s starting from 10s in
            '-vn', '-f', 'null', '-'
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            print("Basic audio analysis completed")
            print("Manual timing adjustment may be needed")
            return 0.0  # No automatic offset calculated
        else:
            print("Could not analyse capture file")
            return None
            
    except Exception as e:
        print(f"Analysis error: {e}")
        return None


def manual_calibration_entry():
    """
    Allow manual entry of calibration delay value
    """
    print("\nMANUAL CALIBRATION VALUE ENTRY")
    print("=" * 40)
    print("\nThis option allows you to manually set the timing delay")
    print("that will be used for A/V synchronization.")
    print("\nTypical delay values:")
    print("- 0.000s - Perfect timing (no delay needed)")
    print("- 0.100s - Audio starts 100ms too early")
    print("- 0.200s - Audio starts 200ms too early")
    print("- Higher values for larger timing offsets")
    print("\nNOTE: This value should come from previous automated")
    print("calibration measurements or external timing analysis.")
    
    # Load current delay from config
    config = load_config()
    current_delay = config.get('audio_delay', 0.000)
    print(f"\nCurrent delay in config: {current_delay:.3f}s")
    
    while True:
        try:
            print("\nEnter calibration delay value:")
            user_input = input("Delay in seconds (e.g., 0.150): ").strip()
            
            if not user_input:
                print("No value entered. Keeping current delay.")
                break
            
            # Parse the input value
            delay_value = float(user_input)
            
            # Validate reasonable range
            if delay_value < 0.0:
                print("ERROR: Delay cannot be negative.")
                print("Enter a positive delay value or 0.000 for no delay.")
                continue
            elif delay_value > 2.0:
                print("WARNING: Delay > 2.0s is unusually large.")
                confirm = input("Are you sure? (y/N): ").strip().lower()
                if confirm not in ['y', 'yes']:
                    continue
            
            # Show the update that would be made
            print(f"\nCALIBRATION UPDATE PREVIEW")
            print(f"   Current delay: {current_delay:.3f}s")
            print(f"   New delay:     {delay_value:.3f}s")
            print(f"   Change:        {delay_value - current_delay:+.3f}s")
            
            print(f"\nIMPORTANT: This will update the configuration file")
            print(f"   The delay value will be saved to config.json")
            print(f"   Alignment/calibration will remain at 0.000s for accurate measurement")
            
            confirm = input("\nApply this calibration? (y/N): ").strip().lower()
            
            if confirm in ['y', 'yes']:
                # Update only the capture delay (not alignment delay)
                success = update_capture_delay_only(delay_value)
                if success:
                    print(f"\nCALIBRATION APPLIED SUCCESSFULLY!")
                    print(f"   Capture delay updated to: {delay_value:.3f}s")
                    print(f"   Alignment delay kept at: 0.000s (for accurate measurement)")
                    print(f"   Changes will take effect on next capture.")
                else:
                    print(f"\nFailed to update capture delay.")
                    print(f"   You may need to manually edit the delay in the script.")
            else:
                print("\nCalibration update cancelled.")
            
            break
            
        except ValueError:
            print("ERROR: Invalid number format.")
            print("Please enter a decimal number (e.g., 0.150)")
        except KeyboardInterrupt:
            print("\nManual calibration cancelled.")
            break
        except Exception as e:
            print(f"ERROR: {e}")
            break


def update_script_delay_values(new_delay):
    """
    Update the delay values in the script file (both capture and alignment)
    Returns True if successful, False otherwise
    """
    script_file = __file__  # Current script file
    
    try:
        # Read the current script content
        with open(script_file, 'r') as f:
            content = f.read()
        
        # Find and replace the delay values
        import re
        
        # Pattern 1: audio_delay = X.XX in start_capture_and_record function  
        pattern1 = r'(audio_delay = )([0-9]+\.[0-9]+)(\s*#\s*Calibrated delay for audio/video synchronization)'
        
        # Pattern 2: time.sleep(X.XX) in perform_av_alignment function (alignment baseline)
        pattern2 = r'(time\.sleep\()([0-9]+\.[0-9]+)(\)\s*#\s*Calibration baseline - no delay for measurement)'
        
        # Apply replacements
        new_content = content
        
        # Replace main capture delay
        matches1 = re.findall(pattern1, new_content)
        if matches1:
            old_delay = float(matches1[0][1])
            new_content = re.sub(pattern1, f'\\1{new_delay:.3f}\\3', new_content)
            print(f"   Updated main capture delay: {old_delay:.3f}s → {new_delay:.3f}s")
        else:
            print("   Warning: Could not find main capture delay to update")
        
        # Keep alignment baseline at 0.0 (for measurement accuracy)
        alignment_delay = 0.0
        matches2 = re.findall(pattern2, new_content)
        if matches2:
            new_content = re.sub(pattern2, f'\\1{alignment_delay:.3f}\\3', new_content)
            print(f"   Alignment baseline kept at: {alignment_delay:.3f}s")
        
        # Write the updated content back
        with open(script_file, 'w') as f:
            f.write(new_content)
        
        return True
        
    except Exception as e:
        print(f"Error updating script: {e}")
        return False


def update_capture_delay_only(new_delay):
    """
    Update the audio delay in configuration file
    Returns True if successful, False otherwise
    """
    try:
        # Load current configuration
        config = load_config()
        old_delay = config.get('audio_delay', 0.000)
        
        # Update the audio delay value
        config['audio_delay'] = new_delay
        
        # Save the updated configuration
        if save_config(config):
            print(f"   Updated audio delay in config: {old_delay:.3f}s → {new_delay:.3f}s")
            print(f"   Configuration saved to config.json")
            return True
        else:
            print(f"   Error: Could not save configuration file")
            return False
        
    except Exception as e:
        print(f"Error updating audio delay in config: {e}")
        return False


# TODO: REMOVE THIS FUNCTION - No longer used after menu restructure (Jan 2026)
# Validation is now done via the Workflow Control Centre.
# Keeping commented out until we confirm nothing else calls it.
def validate_calibration_with_configured_delay():
    """
    DEPRECATED: This function is no longer used.
    Use the Workflow Control Centre to validate your timing instead.
    """
    raise NotImplementedError(
        "validate_calibration_with_configured_delay() is deprecated and has been removed. "
        "Use the Workflow Control Centre to validate your timing instead."
    )

def _validate_calibration_with_configured_delay_DISABLED():
    """
    Validate calibration results by capturing with configured delay and measuring offset.
    This is identical to perform_av_alignment() but uses the configured delay instead of 0.
    DISABLED - kept for reference only
    """
    try:
        print("\n=== Calibration Validation ===")
        print("IMPORTANT: This workflow will:")
        print("   1. Use your configured delay for capture (not zero)")
        print("   2. Complete RF decode workflow")
        print("   3. Run audio alignment")
        print("   4. Measure final timing offset")
        print("   5. Create debug files for analysis")
        print()
        print("Expected result: Near 0.000s offset if calibration is accurate")
        print()
        
        # Get user-configurable capture duration
        alignment_duration_seconds = get_alignment_duration()
        if alignment_duration_seconds is None:
            return  # User cancelled
        
        # Create temp folder if it doesn't exist
        temp_folder = get_temp_folder()
        if not os.path.exists(temp_folder):
            os.makedirs(temp_folder)
            print(f"Created temp folder: {temp_folder}")
        
        # Generate automated filename with timestamp for validation
        validation_base_name = f"validation_{get_alignment_filename()}"
        print(f"Using validation filename: {validation_base_name}")
        
        # Create validation file paths with timestamp
        validation_capture_filename = os.path.join(temp_folder, f"{validation_base_name}.flac")
        validation_rf_filename = os.path.join(temp_folder, f"{validation_base_name}.lds")
        validation_tbc_filename = os.path.join(temp_folder, f"{validation_base_name}.tbc")
        validation_tbc_json_filename = os.path.join(temp_folder, f"{validation_base_name}.tbc.json")
        validation_video_filename = os.path.join(temp_folder, f"{validation_base_name}_ffv1.mkv")
        
        # Create debug output file
        debug_filename = os.path.join(temp_folder, f"{validation_base_name}_debug.txt")
        
        print(f"Output directory: {os.path.abspath(temp_folder)}")
        print(f"Output filename: {validation_base_name}")
        print(f"Debug output: {validation_base_name}_debug.txt")
        print()

        input("Make sure you've recorded at least 5 minutes of the included test pattern files onto a VHS tape. Press any key to continue or Ctrl-C to stop.")
        input("Ensure your Domesday duplicator is plugged in and powered on and your clockgen lite is connected and working. Press any key to continue.")
        input("Insert your VHS tape into your VCR and press play. It's very important to be playing this alignment tape before validation. Press any key to start Validation Capture.")

        # Read configured delay
        config = load_config()
        audio_delay = config.get('audio_delay', 0.000)
        
        # Start debug log
        debug_log = []
        debug_log.append(f"=== CALIBRATION VALIDATION DEBUG LOG ===")
        debug_log.append(f"Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        debug_log.append(f"Configured delay: {audio_delay:.6f}s")
        debug_log.append(f"Capture duration: {alignment_duration_seconds}s")
        debug_log.append(f"Base filename: {validation_base_name}")
        debug_log.append("")

        # Capture validation using command line DomesdayDuplicator
        print("\nStarting RF + Audio capture with configured delay...")
        validation_sox_command = get_sox_command(validation_capture_filename)

        try:
            # 1. Start audio capture using command line
            print(f"Starting SOX audio recording with {audio_delay:.3f}s delay...")
            time.sleep(audio_delay)  # Apply configured delay
            validation_sox_command = get_sox_command(validation_capture_filename)
            release_audio_device_before_capture()  # Release from PipeWire right before starting
            capture_process = subprocess.Popen(validation_sox_command)
            print("SOX audio recording started")
            debug_log.append(f"Audio capture started at: {time.strftime('%H:%M:%S')} (after {audio_delay:.3f}s delay)")
            debug_log.append(f"Net timing: Audio started {audio_delay:.3f}s before video")

            # 2. Start video capture using command line
            print("Starting DomesdayDuplicator capture...")
            ddd_process = subprocess.Popen(['DomesdayDuplicator', '--start-capture', '--headless',
                                           '--capture-directory', os.path.abspath(temp_folder),
                                           '--output-file', validation_base_name],
                                      stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

            # Check if process is still running (successful start)
            if ddd_process.poll() is None:
                print("DomesdayDuplicator capture started successfully")
                debug_log.append(f"Video capture started at: {time.strftime('%H:%M:%S')} using command line")
                
                print("\nVALIDATION CAPTURE IN PROGRESS")
                print(f"Using configured delay: {audio_delay:.3f}s")
                print(f"Both RF and audio recording for {alignment_duration_seconds} seconds...")
                print("DO NOT STOP THE VCR YET - let it continue playing!")
                
                # Show progress during capture
                print("Progress: ", end="", flush=True)
                for i in range(alignment_duration_seconds):
                    time.sleep(1)
                    if (i + 1) % 5 == 0:  # Show progress every 5 seconds
                        remaining = alignment_duration_seconds - (i + 1)
                        print(f"{i+1}s ", end="", flush=True)
                        if remaining > 0 and (i + 1) % 10 == 0:
                            print(f"({remaining}s remaining) ", end="", flush=True)
                    else:
                        print(".", end="", flush=True)
                
                # 2. Stop audio recording
                print("\nStopping audio recording...")
                capture_process.terminate()
                capture_process.wait()
                print("Audio recording stopped")
                
                debug_log.append(f"Audio capture stopped at: {time.strftime('%H:%M:%S')}")

                # 3. Stop video capture using command line
                print("\nStopping DomesdayDuplicator capture...")
                stop_result = subprocess.run(['DomesdayDuplicator', '--stop-capture'],
                                           capture_output=True, text=True,
                                           env=get_clean_env_for_system_tools())

                if stop_result.returncode == 0:
                    print("DomesdayDuplicator capture stopped successfully")
                    debug_log.append(f"Video capture stopped at: {time.strftime('%H:%M:%S')} using command line")
                else:
                    print(f"Warning: DomesdayDuplicator stop returned code {stop_result.returncode}")
                    print("Please verify capture was stopped properly")
                    debug_log.append(f"Video capture stop warning: return code {stop_result.returncode}")
                
                # Important user message after capture stops
                print("\n" + "="*50)
                print("VALIDATION CAPTURE COMPLETED")
                print("="*50)
                print("RF and audio capture has finished successfully!")
                print("")
                print("You can now STOP your VCR/alignment tape.")
                print("   The capture is complete and no longer recording.")
                print("")
                print("Next: RF decode and audio alignment analysis will begin...")
                print("="*50)
                print()
                
                # Give user a moment to see this message
                time.sleep(2)

            else:
                # Process has terminated, get output and error
                stdout, stderr = ddd_process.communicate()
                return_code = ddd_process.returncode
                
                print(f"ERROR: Could not start DomesdayDuplicator capture!")
                print(f"Command failed with return code: {return_code}")
                print(f"Error output: {stderr}")
                print("Please ensure:")
                print("1. DomesdayDuplicator is installed and in your PATH")
                print("2. The hardware is connected properly")
                print("3. No other instance is already running")
                print("\nValidation capture cancelled.")
                debug_log.append(f"ERROR: DomesdayDuplicator start failed with code {return_code}")
                return

        except subprocess.TimeoutExpired:
            print("ERROR: DomesdayDuplicator command timed out")
            print("This might indicate the command is hanging or waiting for user input")
            debug_log.append("ERROR: DomesdayDuplicator command timed out")
            return
        except FileNotFoundError:
            print("ERROR: DomesdayDuplicator command not found!")
            print("Please ensure DomesdayDuplicator is installed and available in your PATH")
            debug_log.append("ERROR: DomesdayDuplicator command not found")
            return
        except Exception as e:
            print(f"Capture error: {e}")
            debug_log.append(f"Capture error: {e}")
            return

        # 5. RF Decode step
        print("\nSTARTING RF DECODE WORKFLOW")
        debug_log.append("=== RF DECODE PHASE ===")
        debug_log.append(f"RF decode started at: {time.strftime('%H:%M:%S')}")
        print("Looking for RF capture file in temp folder...")
        
        # Find the most recent .lds file (RF capture) in temp folder
        if not os.path.exists(temp_folder):
            print(f"Temp folder {temp_folder} does not exist!")
            debug_log.append(f"ERROR: Temp folder {temp_folder} does not exist")
            return
            
        lds_files = [f for f in os.listdir(temp_folder) if f.endswith('.lds')]
        if not lds_files:
            print(f"No RF capture files (.lds) found in {temp_folder}!")
            debug_log.append(f"ERROR: No RF capture files found in {temp_folder}")
            return
        
        # Get the most recent RF file (with full path)
        lds_paths = [os.path.join(temp_folder, f) for f in lds_files]
        rf_file = max(lds_paths, key=os.path.getmtime)
        print(f"Found RF capture: {rf_file}")
        debug_log.append(f"RF file: {os.path.basename(rf_file)} ({os.path.getsize(rf_file) / (1024**2):.1f} MB)")
        
        # Check if we already have decoded files
        tbc_file = rf_file.replace('.lds', '.tbc')
        tbc_json_file = rf_file.replace('.lds', '.tbc.json')
        
        if os.path.exists(tbc_json_file):
            print(f"TBC JSON already exists: {tbc_json_file}")
            debug_log.append(f"TBC JSON already exists: {os.path.basename(tbc_json_file)}")
        else:
            print("\nRunning vhs-decode...")
            if not run_vhs_decode_with_params(rf_file, tbc_file, 'pal', 'SP'):
                print("RF decode failed")
                debug_log.append("ERROR: RF decode failed")
                return
            debug_log.append(f"RF decode completed: {os.path.basename(tbc_file)}")
        
        # Check if we need to export video
        video_file = rf_file.replace('.lds', '_ffv1.mkv')
        if os.path.exists(video_file):
            print(f"Video export already exists: {video_file}")
            debug_log.append(f"Video export already exists: {os.path.basename(video_file)}")
        else:
            print("\nRunning tbc-video-export...")
            if not run_tbc_video_export(tbc_file, video_file):
                print("Video export failed, but continuing with audio alignment...")
                debug_log.append("WARNING: Video export failed")
            else:
                debug_log.append(f"Video export completed: {os.path.basename(video_file)}")
        
        print("\nRF decode workflow complete!")
        debug_log.append("RF decode workflow completed")
        debug_log.append("")
        
        # 6. Audio alignment analysis
        print(f"\nUsing TBC JSON file: {tbc_json_file}")
        debug_log.append("=== AUDIO ALIGNMENT PHASE ===")
        debug_log.append(f"Audio alignment started at: {time.strftime('%H:%M:%S')}")
        debug_log.append(f"TBC JSON: {os.path.basename(tbc_json_file)}")
        
        print("\nRunning VHS mechanical audio alignment...")
        aligned_audio_file = analyze_alignment_with_tbc(validation_capture_filename, tbc_json_file)
        
        # Wait for aligned file to be fully created
        if aligned_audio_file and aligned_audio_file.endswith(('_aligned.flac', '_aligned.wav')):
            print(f"Waiting for aligned audio file to be ready: {aligned_audio_file}")
            wait_for_file_ready(aligned_audio_file, max_wait_seconds=30)

        if aligned_audio_file and os.path.exists(aligned_audio_file):
            print(f"\nMechanical alignment completed: {aligned_audio_file}")
            debug_log.append(f"Aligned audio file created: {os.path.basename(aligned_audio_file)}")

            # Verify we're using the aligned file (debug info)
            if aligned_audio_file.endswith(('_aligned.flac', '_aligned.wav')):
                print(f"CONFIRMED: Using aligned audio file for analysis")
                debug_log.append("Using aligned audio file for test pattern analysis")
            else:
                print(f"WARNING: Not using aligned audio file - using: {aligned_audio_file}")
                debug_log.append(f"WARNING: Not using aligned audio file - using: {os.path.basename(aligned_audio_file)}")
            
            # Show file details for verification
            file_size = os.path.getsize(aligned_audio_file) / (1024*1024)  # MB
            file_time = time.ctime(os.path.getmtime(aligned_audio_file))
            print(f"   File size: {file_size:.1f} MB")
            print(f"   Modified: {file_time}")
            debug_log.append(f"Aligned audio file size: {file_size:.1f} MB")
            
            # Now run test pattern timing analysis on both aligned audio and video
            print("\nRunning test pattern timing analysis...")
            debug_log.append("")
            debug_log.append("=== TEST PATTERN TIMING ANALYSIS ===")
            debug_log.append(f"Test pattern analysis started at: {time.strftime('%H:%M:%S')}")
            
            offset_seconds = analyze_test_pattern_timing(aligned_audio_file, video_file)
            
            if offset_seconds is not None:
                # Calculate frame offset for better understanding
                fps = 25.0  # Default PAL
                try:
                    if os.path.exists(video_file):
                        import cv2
                        cap = cv2.VideoCapture(video_file)
                        if cap.isOpened():
                            detected_fps = cap.get(cv2.CAP_PROP_FPS)
                            if detected_fps > 0:
                                fps = detected_fps
                            cap.release()
                except:
                    pass
                
                frame_offset = offset_seconds * fps
                
                print(f"\n" + "="*60)
                print(f"VALIDATION RESULTS")
                print(f"="*60)
                print(f"\nTIMING ANALYSIS:")
                print(f"   Measured timing offset: {offset_seconds:+.6f} seconds ({frame_offset:+.2f} frames @ {fps:.1f}fps)")
                print(f"   Configured delay used: {audio_delay:.6f} seconds")
                print(f"   Expected result: ~0.000s if calibration is accurate")
                
                debug_log.append(f"Measured offset: {offset_seconds:+.6f} seconds")
                debug_log.append(f"Configured delay: {audio_delay:.6f} seconds")
                
                # Analyze validation results
                abs_offset = abs(offset_seconds)
                if abs_offset <= 0.010:  # Within 10ms
                    print(f"\nVALIDATION RESULT: EXCELLENT")
                    print(f"   Offset within ±10ms - calibration is highly accurate")
                    print(f"   Your current delay setting ({audio_delay:.3f}s) is working well")
                    debug_log.append("VALIDATION RESULT: EXCELLENT (within ±10ms)")
                elif abs_offset <= 0.050:  # Within 50ms
                    print(f"\nVALIDATION RESULT: GOOD")
                    print(f"   Offset within ±50ms - calibration is reasonably accurate")
                    print(f"   Consider fine-tuning if higher precision is needed")
                    debug_log.append("VALIDATION RESULT: GOOD (within ±50ms)")
                elif abs_offset <= 0.100:  # Within 100ms
                    print(f"\nVALIDATION RESULT: FAIR")
                    print(f"   Offset within ±100ms - calibration may need adjustment")
                    print(f"   Consider running calibration again")
                    debug_log.append("VALIDATION RESULT: FAIR (within ±100ms)")
                else:
                    print(f"\nVALIDATION RESULT: POOR")
                    print(f"   Offset > 100ms - calibration needs attention")
                    print(f"   Recommend running full calibration workflow again")
                    debug_log.append("VALIDATION RESULT: POOR (>100ms offset)")
                
                if offset_seconds > 0:
                    # VALIDATION LOGIC: If audio is too late, we need to REDUCE the delay
                    # (opposite of calibration logic which starts from zero baseline)
                    suggested_delay = max(0.0, audio_delay - offset_seconds)
                    print(f"\nTIMING INTERPRETATION:")
                    print(f"   Positive offset: Audio starts {offset_seconds:.3f}s too late")
                    print(f"   To improve: REDUCE audio delay to {suggested_delay:.3f}s")
                    print(f"   Logic: Current delay ({audio_delay:.3f}s) - measured offset ({offset_seconds:.3f}s)")
                    debug_log.append(f"Recommendation: Reduce delay to {suggested_delay:.6f}s")
                elif offset_seconds < 0:
                    # If audio is too early, we need to INCREASE the delay
                    suggested_delay = audio_delay + abs(offset_seconds)
                    print(f"\nTIMING INTERPRETATION:")
                    print(f"   Negative offset: Audio starts {abs(offset_seconds):.3f}s too early")
                    print(f"   To improve: INCREASE audio delay to {suggested_delay:.3f}s")
                    print(f"   Logic: Current delay ({audio_delay:.3f}s) + measured offset ({abs(offset_seconds):.3f}s)")
                    debug_log.append(f"Recommendation: Increase delay to {suggested_delay:.6f}s")
                else:
                    print(f"\nPERFECT TIMING: Audio and video are perfectly synchronized!")
                    debug_log.append("PERFECT TIMING: No adjustment needed")
                
                print(f"\nDEBUG INFORMATION:")
                print(f"   Debug log saved to: {os.path.basename(debug_filename)}")
                print(f"   Review this file for detailed timing analysis")
                print(f"="*60)
                
                # Save debug log
                debug_log.append("")
                debug_log.append("=== VALIDATION COMPLETED ===")
                debug_log.append(f"Validation completed at: {time.strftime('%Y-%m-%d %H:%M:%S')}")
                debug_log.append(f"Total analysis time: ~{alignment_duration_seconds + 300} seconds")
                
            else:
                print("\nTest pattern timing analysis failed")
                print("This could be due to:")
                print("- Poor audio/video quality in capture")
                print("- Missing test pattern signal")
                print("- Test pattern not detected in video or audio")
                debug_log.append("ERROR: Test pattern timing analysis failed")
        else:
            print("\nVHS mechanical audio alignment failed")
            print("Cannot proceed with test pattern analysis without aligned audio")
            debug_log.append("ERROR: VHS mechanical audio alignment failed")
        
        # Write debug log to file
        try:
            with open(debug_filename, 'w') as f:
                f.write('\n'.join(debug_log))
            print(f"\nDebug log written to: {debug_filename}")
        except Exception as e:
            print(f"\nWarning: Could not write debug log: {e}")
        
        print("\nValidation workflow complete!")
        print("Files created:")
        print(f"   Audio: {os.path.basename(validation_capture_filename)}")
        print(f"   RF: {os.path.basename(rf_file)}")
        print(f"   TBC data: {os.path.basename(tbc_file)}")
        if os.path.exists(aligned_audio_file):
            print(f"   Aligned audio: {os.path.basename(aligned_audio_file)}")
        if os.path.exists(video_file):
            print(f"   Video: {os.path.basename(video_file)}")
        print(f"   Debug log: {os.path.basename(debug_filename)}")

    except KeyboardInterrupt:
        print("\nCalibration validation cancelled by user")
    except Exception as e:
        print(f"\nERROR during calibration validation: {e}")


def take_screenshot(filename):
    """
    Takes a screenshot - works on macOS, Linux, and Windows
    """
    try:
        if sys.platform == 'darwin':
            # macOS
            subprocess.run(['screencapture', '-x', filename], check=True)
            print(f"Screenshot saved to {filename}")
            return True
        elif sys.platform == 'win32':
            # Windows - use built-in PowerShell
            powershell_cmd = f"Add-Type -AssemblyName System.Windows.Forms; [System.Windows.Forms.SendKeys]::SendWait('%{{PRTSC}}'); Start-Sleep -Milliseconds 500; [System.Drawing.Bitmap]([System.Windows.Forms.Clipboard]::GetImage()).Save('{filename}')"
            result = subprocess.run(['powershell', '-Command', powershell_cmd], check=True, capture_output=True)
            print(f"Screenshot saved to {filename}")
            return True
        else:
            # Linux with KDE Spectacle
            env_copy = os.environ.copy()
            if 'LD_LIBRARY_PATH' in env_copy:
                del env_copy['LD_LIBRARY_PATH']

            subprocess.run(
                ['spectacle', '-b', '-n', '-o', filename],
                check=True,
                env=env_copy
            )
            print(f"Screenshot saved to {filename}")
            return True
    except FileNotFoundError:
        if sys.platform == 'darwin':
            print("\nERROR: 'screencapture' command not found.")
        elif sys.platform == 'win32':
            print("\nERROR: PowerShell not found or screenshot failed.")
            print("Please ensure PowerShell is available and try running as administrator.")
        else:
            print("\nERROR: 'spectacle' command not found.")
            print("Please ensure KDE Spectacle is installed (`sudo apt install spectacle`).")
        return False
    except subprocess.CalledProcessError as e:
        print(f"\nERROR: Screenshot failed: {e}")
        return False


def prompt_for_capture_name(target_folder=None):
    """
    Prompt user for capture name to use for both RF and audio files
    Returns the base filename (without extension)
    """
    # Use temp folder if no target folder specified (for backwards compatibility)
    if target_folder is None:
        target_folder = get_temp_folder()
    
    print("\n--- CAPTURE NAMING ---")
    print("Enter a name for this capture session.")
    print("This name will be used for both RF (.lds) and audio (.flac) files.")
    print("")
    print("Examples:")
    print("   VHS_Movie_Title_1985")
    print("   Test_Pattern_Calibration")
    print("   Family_Videos_1990s")
    print("")
    
    while True:
        try:
            capture_name = input("Enter capture name (or press Enter for default): ").strip()
            
            # Use default if nothing entered
            if not capture_name:
                capture_name = "my_vhs_capture"
                print(f"Using default name: {capture_name}")
            
            # Validate filename (basic check for filesystem compatibility)
            invalid_chars = '<>:"/\\|?*'
            if any(char in capture_name for char in invalid_chars):
                print(f"ERROR: Filename contains invalid characters: {invalid_chars}")
                print("Please use only letters, numbers, underscores, and hyphens.")
                continue
            
            # Check if files already exist in the target folder
            lds_path = os.path.join(target_folder, f"{capture_name}.lds")
            flac_path = os.path.join(target_folder, f"{capture_name}.flac")
            
            existing_files = []
            if os.path.exists(lds_path):
                existing_files.append(lds_path)
            if os.path.exists(flac_path):
                existing_files.append(flac_path)
            
            if existing_files:
                print(f"\nWARNING: Files with this name already exist:")
                for file_path in existing_files:
                    file_size = os.path.getsize(file_path) / (1024**2)  # MB
                    print(f"   - {os.path.basename(file_path)} ({file_size:.1f} MB)")
                
                overwrite = input("\nOverwrite existing files? (y/N): ").strip().lower()
                if overwrite not in ['y', 'yes']:
                    print("Please choose a different name.")
                    continue
            
            print(f"\nCapture name set to: {capture_name}")
            print(f"Files will be saved as:")
            print(f"   RF capture: {capture_name}.lds")
            print(f"   Audio: {capture_name}.flac")
            print(f"   Location: {os.path.abspath(target_folder)}/")
            
            return capture_name
            
        except KeyboardInterrupt:
            print("\nCapture cancelled by user.")
            return None
        except Exception as e:
            print(f"ERROR: {e}")
            continue


def start_capture_and_record():
    """
    Starts audio recording with calibrated delay, then immediately starts video capture.

    Uses pre-preparation to minimize startup time after user presses Enter:
    - All device detection and preparation happens BEFORE the prompt
    - Capture starts instantly when user presses Enter
    """
    print("--- Domesday Capture (Fast Start) ---")

    # Pre-capture environment check: print PASS/WARN for each load-bearing
    # kernel/system setting, prompt to proceed if anything is sub-optimal.
    # Read-only; no sudo; portable across distros (each check SKIPs if its
    # tool isn't present).
    if sys.platform == 'linux':
        checks = verify_capture_environment()
        _print_environment_check_table(checks)
        warns = [c for c in checks if c['status'] == 'WARN']
        if warns:
            print(f"\n{len(warns)} setting(s) above will reduce capture reliability.")
            print("You can continue anyway, or quit and apply the menu options listed.")
            choice = input("Continue with capture? (Y/n): ").strip().lower()
            if choice == 'n':
                print("Capture cancelled.")
                return

    # Read configuration
    config = load_config()
    calibration_mode = config.get('calibration_mode', False)

    # Calibration captures always go to the project temp folder so that
    # analyze_v2_calibration() can find them. Normal captures use the
    # user-configured capture directory.
    if calibration_mode:
        capture_folder = get_temp_folder()
    else:
        capture_folder = get_capture_folder()
    if not os.path.exists(capture_folder):
        os.makedirs(capture_folder)
        print(f"Created capture folder: {capture_folder}")

    if calibration_mode:
        # Fixed name for calibration captures
        capture_name = "calibration"
        print("\n" + "="*50)
        print("CALIBRATION MODE ACTIVE")
        print("Audio delay disabled (0.000s) for offset measurement")
        print(f"Using fixed project name: {capture_name}")
        print(f"Output folder (temp): {capture_folder}")
        print("="*50 + "\n")

        # Check for existing calibration files (all stages of workflow)
        existing_files = []
        extensions = [
            '.lds',           # RF capture
            '.flac',          # Audio capture
            '.json',          # Capture metadata
            '.tbc',           # Luma TBC
            '.tbc.chroma',    # Chroma TBC
            '.tbc.json',      # TBC metadata
            '.tbc.lz4',       # Compressed TBC
            '_ffv1.mkv',      # Exported video
            '_aligned.flac',  # Aligned audio (FLAC, current)
            '_aligned.wav',   # Aligned audio (WAV, legacy)
            '_final.mkv'      # Final muxed output
        ]
        for ext in extensions:
            filepath = os.path.join(capture_folder, f"{capture_name}{ext}")
            if os.path.exists(filepath):
                existing_files.append(filepath)

        if existing_files:
            print("Existing calibration files found:")
            for f in existing_files:
                size_mb = os.path.getsize(f) / (1024*1024)
                print(f"   {os.path.basename(f)} ({size_mb:.1f} MB)")
            print()
            overwrite = input("Overwrite existing calibration files? (y/N): ").strip().lower()
            if overwrite != 'y':
                print("Calibration capture cancelled.")
                return
            # Delete existing files
            for f in existing_files:
                try:
                    os.remove(f)
                    print(f"Deleted: {os.path.basename(f)}")
                except Exception as e:
                    print(f"Warning: Could not delete {os.path.basename(f)}: {e}")
            print()

        audio_delay = 0.000
    else:
        # Normal mode - prompt for capture name
        capture_name = prompt_for_capture_name(capture_folder)
        if not capture_name:
            return  # User cancelled
        audio_delay = config.get('audio_delay', 0.000)  # Default to 0.000 if not set
        print(f"Using configured audio delay: {audio_delay:.3f}s")

    # Construct output file paths
    video_output_path = os.path.join(capture_folder, f"{capture_name}.lds")
    audio_output_path = os.path.join(capture_folder, f"{capture_name}.flac")

    # PRE-PREPARE: Do all slow operations NOW (before user presses Enter)
    print("\nPreparing capture resources...")
    sox_command, result = prepare_capture_resources(audio_output_path)
    if sox_command is None:
        print(f"Error preparing capture: {result}")
        return

    # Build DDD command (instant, no subprocess calls)
    ddd_command = ['DomesdayDuplicator', '--start-capture', '--headless',
                  '--capture-directory', capture_folder, '--output-file', capture_name]

    print(f"\nVideo will be saved to: {video_output_path}")
    print(f"Audio will be saved to: {audio_output_path}")

    # FAST START: User presses Enter and capture starts immediately
    print("\n" + "="*50)
    print("  READY - Press Enter to start capture")
    print("="*50)
    input()

    # Start capture immediately (resources already prepared)
    shared_capture_process_fast(sox_command, audio_delay, capture_duration=None, ddd_command=ddd_command)


def offer_wav_conversion(flac_file=None, wav_file=None):
    """
    Offers to convert the FLAC file to WAV format for use with alignment tools.
    Defaults to 'yes' since WAV is needed for most workflows.
    """
    # Use defaults if not provided (for backward compatibility)
    if flac_file is None:
        flac_file = CAPTURE_FLAC_PATH
    if wav_file is None:
        wav_file = CAPTURE_WAV_PATH
    
    if not os.path.exists(flac_file):
        print(f"\nWarning: {flac_file} not found. Cannot offer conversion.")
        return
    
    # Estimate WAV file size (FLAC is typically 50-60% the size of WAV for this type of content)
    flac_size = os.path.getsize(flac_file) / (1024**3)  # GB
    estimated_wav_size = flac_size * 1.8  # Rough estimate
    
    print(f"\n--- CAPTURE COMPLETE ---")
    print(f"FLAC file saved: {flac_file} ({flac_size:.2f} GB)")
    
    conversion_command = f"sox '{flac_file}' '{wav_file}'"
    
    if estimated_wav_size > 4.0:
        print(f"\nWARNING: Estimated WAV size (~{estimated_wav_size:.1f} GB) may exceed 4GB limit")
        print(f"WAV files >4GB may not work with some alignment tools.")
        print(f"Consider using the FLAC file directly in DaVinci Resolve if possible.")
        print(f"\nConversion command: {conversion_command}")
        
        try:
            response = input("\nAttempt WAV conversion anyway? (y/N): ").strip().lower()
            convert_to_wav = response in ['y', 'yes']
        except KeyboardInterrupt:
            print(f"\nConversion cancelled. You can convert later with: {conversion_command}")
            return
    else:
        print(f"\nConverting to WAV for alignment tools and DaVinci Resolve compatibility...")
        print(f"Conversion command: {conversion_command}")
        
        try:
            response = input("\nConvert to WAV now? (Y/n): ").strip().lower()
            convert_to_wav = response not in ['n', 'no']
        except KeyboardInterrupt:
            print(f"\nConversion cancelled. You can convert later with: {conversion_command}")
            return
    
    if convert_to_wav:
        print(f"Converting {flac_file} to {wav_file}...")
        # Preserve exact audio parameters - no resampling or processing
        result = subprocess.run(['sox', flac_file, '-t', 'wav', wav_file], capture_output=True, text=True)
        
        if result.returncode == 0:
            wav_size = os.path.getsize(wav_file) / (1024**3)   # GB
            print(f" Conversion successful: {wav_file} ({wav_size:.2f} GB)")
            
            if wav_size > 4.0:
                print(f"  WAV file is {wav_size:.2f} GB (>4GB limit)")
                print(f"  Some applications may have issues with this file size.")
                print(f"  Keep the FLAC version as backup: {flac_file}")
            else:
                print(f"   WAV file size is within 4GB limit")
        else:
            print(f" Conversion failed: {result.stderr}")
            print(f"You can try the conversion manually: {conversion_command}")
    else:
        print(f"Skipped conversion. You can convert later with: {conversion_command}")


def stop_domesday_duplicator_capture():
    """
    Stop Domesday Duplicator capture using command line
    Returns True if successful, False otherwise
    """
    try:
        # Use command line to stop capture (clean env to avoid Qt conflicts)
        stop_result = subprocess.run(['DomesdayDuplicator', '--stop-capture', '--headless'],
                                   capture_output=True, text=True, timeout=10,
                                   env=get_clean_env_for_system_tools())

        if stop_result.returncode == 0:
            return True
        else:
            print(f"DomesdayDuplicator stop returned code {stop_result.returncode}")
            return False

    except subprocess.TimeoutExpired:
        print("DomesdayDuplicator stop command timed out")
        return False
    except FileNotFoundError:
        print("DomesdayDuplicator command not found")
        return False
    except Exception as e:
        print(f"Error stopping Domesday Duplicator: {e}")
        return False


def rename_rf_files_to_match(desired_name, temp_folder):
    """
    Rename the most recently created RF files to match the desired capture name
    Returns True if successful, False otherwise
    """
    try:
        # Find all .lds files in temp folder
        lds_files = [f for f in os.listdir(temp_folder) if f.lower().endswith('.lds')]
        
        if not lds_files:
            print("No RF files (.lds) found to rename")
            return False
        
        # Get the most recent .lds file (just created)
        lds_paths = [os.path.join(temp_folder, f) for f in lds_files]
        most_recent_lds = max(lds_paths, key=os.path.getmtime)
        
        # Generate target filenames
        new_lds_name = os.path.join(temp_folder, f"{desired_name}.lds")
        new_json_name = os.path.join(temp_folder, f"{desired_name}.json")  # Direct JSON from Domesday Duplicator
        new_tbc_json_name = os.path.join(temp_folder, f"{desired_name}.tbc.json")  # VHS decode JSON
        
        # Rename the RF file
        if most_recent_lds != new_lds_name:  # Only rename if different
            print(f"Renaming: {os.path.basename(most_recent_lds)} → {desired_name}.lds")
            os.rename(most_recent_lds, new_lds_name)
        
        # Find and rename the most recent JSON file (Domesday Duplicator format)
        # Look for files like "RF-Sample_YYYY-MM-DD_HH-MM-SS.json"
        json_files = [f for f in os.listdir(temp_folder) if f.lower().endswith('.json') and not f.endswith('.tbc.json')]
        if json_files:
            json_paths = [os.path.join(temp_folder, f) for f in json_files]
            most_recent_json = max(json_paths, key=os.path.getmtime)
            
            if most_recent_json != new_json_name:
                print(f"Renaming: {os.path.basename(most_recent_json)} → {desired_name}.json")
                os.rename(most_recent_json, new_json_name)
        
        # Check for and rename associated TBC JSON file (from vhs-decode)
        old_tbc_json_file = most_recent_lds.replace('.lds', '.tbc.json')
        if os.path.exists(old_tbc_json_file) and old_tbc_json_file != new_tbc_json_name:
            print(f"Renaming: {os.path.basename(old_tbc_json_file)} → {desired_name}.tbc.json")
            os.rename(old_tbc_json_file, new_tbc_json_name)
        
        # Check for and rename any other associated files (.tbc, etc.)
        old_tbc_file = most_recent_lds.replace('.lds', '.tbc')
        new_tbc_file = os.path.join(temp_folder, f"{desired_name}.tbc")
        if os.path.exists(old_tbc_file) and old_tbc_file != new_tbc_file:
            print(f"Renaming: {os.path.basename(old_tbc_file)} → {desired_name}.tbc")
            os.rename(old_tbc_file, new_tbc_file)
        
        return True
        
    except Exception as e:
        print(f"Error renaming RF files: {e}")
        return False


def save_calibration_results(alignment_base_name, offset_seconds, delay_seconds, 
                            capture_duration_seconds, temp_folder):
    """
    Save calibration measurement results to JSON metadata file
    """
    try:
        # Create metadata filename based on alignment base name
        metadata_filename = os.path.join(temp_folder, f"{alignment_base_name}_calibration.json")
        
        # Collect system and measurement information
        calibration_data = {
            "calibration_metadata": {
                "timestamp": datetime.now().isoformat(),
                "alignment_base_name": alignment_base_name,
                "version": "2.0",
                "script_name": "ddd_clockgen_sync.py"
            },
            "measurement_parameters": {
                "capture_duration_seconds": capture_duration_seconds,
                "baseline_delay_seconds": 0.0,  # Alignment uses no delay for measurement
                "analysis_method": "test_pattern_timing_analysis"
            },
            "timing_results": {
                "measured_offset_seconds": offset_seconds,
                "required_delay_seconds": delay_seconds,
                "measurement_precision": "millisecond",
                "sync_quality": "good" if abs(offset_seconds or 0) < 0.050 else "needs_adjustment"
            },
            "file_references": {
                "audio_file": f"{alignment_base_name}.flac",
                "rf_file": f"{alignment_base_name}.lds",
                "tbc_file": f"{alignment_base_name}.tbc",
                "tbc_json_file": f"{alignment_base_name}.tbc.json",
                "video_file": f"{alignment_base_name}_ffv1.mkv",
                "aligned_audio_file": f"{alignment_base_name}_aligned.flac"
            },
            "calibration_status": {
                "offset_within_tolerance": bool(abs(offset_seconds or 0) < 0.010),  # 10ms tolerance
                "auto_applied": bool(abs(offset_seconds or 0) > 0.010),
                "recommended_action": "none" if abs(offset_seconds or 0) < 0.010 else "applied_automatically"
            }
        }
        
        # Write JSON file with pretty formatting
        with open(metadata_filename, 'w') as f:
            json.dump(calibration_data, f, indent=2, ensure_ascii=False)
        
        print(f"\n Calibration metadata saved: {os.path.basename(metadata_filename)}")
        print(f"   Location: {os.path.abspath(metadata_filename)}")
        print(f"   Contains: Timing measurements, file references, and calibration status")
        
        # Show key results from the saved data
        if offset_seconds is not None:
            print(f"   Measured offset: {offset_seconds:+.3f}s")
            print(f"   Applied delay: {delay_seconds:.3f}s")
            print(f"   Capture duration: {capture_duration_seconds}s")
        
        return True
        
    except Exception as e:
        print(f"WARNING: Could not save calibration metadata: {e}")
        print(f"   Calibration results are still applied to the script")
        print(f"   Metadata file could not be created in: {temp_folder}")
        return False


def stop_current_capture():
    """
    Stop any ongoing Domesday Duplicator and SOX captures.
    """
    try:
        print("\n--- STOPPING CAPTURE ---")
        
        # Stop SOX processes
        try:
            subprocess.run(['pkill', '-f', 'sox'], check=True)
            print("SOX audio recording stopped.")
        except subprocess.CalledProcessError:
            print("No SOX processes found to stop.")
        
        # Stop DomesdayDuplicator using command line (clean env to avoid Qt conflicts)
        try:
            stop_result = subprocess.run(['DomesdayDuplicator', '--stop-capture', '--headless'],
                                       capture_output=True, text=True, timeout=10,
                                       env=get_clean_env_for_system_tools())
            if stop_result.returncode == 0:
                print("DomesdayDuplicator capture stopped via command line.")
            else:
                print(f"DomesdayDuplicator stop returned code {stop_result.returncode}")
                # Fallback to process kill
                subprocess.run(['pkill', '-f', 'DomesdayDuplicator'], check=False)
                print("Attempted to kill DomesdayDuplicator processes.")
        except (subprocess.TimeoutExpired, FileNotFoundError):
            print("Command line stop failed, trying process kill...")
            try:
                subprocess.run(['pkill', '-f', 'DomesdayDuplicator'], check=True)
                print("DomesdayDuplicator processes killed.")
            except subprocess.CalledProcessError:
                print("No DomesdayDuplicator processes found to stop.")
                
    except Exception as e:
        print(f"Error when stopping captures: {e}")
