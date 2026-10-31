#!/usr/bin/env python3
"""
Capture backends: how the toolkit starts and stops the RF half of a capture.

A capture is two things started together: the RF capture (this module) and the
audio capture (sox | flac, in ddd_clockgen_sync.py). The audio side and the
calibration that lines the two up stay in the toolkit; only the RF program is
pluggable.

A backend answers five questions:
  - is it installed, and how is it run?        (available / argv_prefix)
  - what command starts a capture?             (start_command)
  - what command stops it?                     (stop_command)
  - what file does it write?                   (rf_suffix / rf_path)
  - which running processes belong to it?      (process_pattern)

To add a backend (for example a MISRC device), subclass CaptureBackend, set
`key`, `label` and `rf_suffix`, implement the methods and call
register_backend() at import time. Select it with "capture_backend" in
config/config.json; "auto" picks one from the attached hardware.

Calibration note: the calibrated audio delay includes the RF program's start-up
latency, so it is only valid for the backend it was measured with. See
config.get_audio_delay_backend().
"""

import glob
import os
import shutil
import subprocess
import sys

# Real USB IDs of the Domesday Duplicator board
DDD_USB_ID_ORIGINAL = ('1d50', '603b')   # original firmware
DDD_USB_ID_CURRENT = ('1209', '2347')    # current firmware (gui-v3.x / fw-v3.x)

FLATPAK_APP_ID = 'io.github.simoninns.DddGui'

# Folders a Flatpak install of ddd-gui can write to (from its permissions)
FLATPAK_WRITABLE_ROOTS = ('/media', '/run/media', '/mnt')


class CaptureBackend:
    """Base class. Subclasses fill in the class attributes and methods."""

    key = None           # name used in config.json
    label = None         # human-readable name
    rf_suffix = None     # extension of the RF file this backend writes
    process_pattern = None   # regex for pgrep -f / pkill -f

    def argv_prefix(self):
        """Return the argv list that runs the program, or None if not found."""
        raise NotImplementedError

    def available(self):
        return self.argv_prefix() is not None

    def start_command(self, capture_folder, capture_name):
        raise NotImplementedError

    def stop_command(self):
        raise NotImplementedError

    def rf_path(self, capture_folder, capture_name):
        return os.path.join(capture_folder, f"{capture_name}{self.rf_suffix}")

    def check_folder(self, capture_folder):
        """Return a warning string if capture_folder may not be writable, else None."""
        return None

    def extra_env(self):
        """Extra environment variables for the capture process."""
        return {}


def _configured_binary(config_key='capture_binary'):
    """A user-set override of the program to run (path, or a command line)."""
    try:
        from config import load_config
        value = load_config().get(config_key)
    except Exception:
        return None
    if not value:
        return None
    return value.split() if isinstance(value, str) else list(value)


class LegacyDomesdayBackend(CaptureBackend):
    """The forked Domesday Duplicator Qt application (original firmware, .lds)."""

    key = 'ddd-legacy'
    label = 'Domesday Duplicator (forked app, original firmware)'
    rf_suffix = '.lds'
    process_pattern = 'DomesdayDuplicator'

    def argv_prefix(self):
        override = _configured_binary()
        if override and os.path.basename(override[0]).lower().startswith('domesdayduplicator'):
            return override
        path = shutil.which('DomesdayDuplicator')
        return [path] if path else None

    def start_command(self, capture_folder, capture_name):
        return self.argv_prefix() + ['--start-capture', '--headless',
                                     '--capture-directory', capture_folder,
                                     '--output-file', capture_name]

    def stop_command(self):
        return self.argv_prefix() + ['--stop-capture']


class DddGuiBackend(CaptureBackend):
    """The current upstream Domesday Duplicator application (ddd-gui, .ddd.flac)."""

    key = 'ddd-gui'
    label = 'Domesday Duplicator (upstream ddd-gui, current firmware)'
    rf_suffix = '.ddd.flac'
    process_pattern = 'ddd-gui'

    def __init__(self):
        self._flatpak = False

    def argv_prefix(self):
        self._flatpak = False
        override = _configured_binary()
        if override and any('ddd-gui' in part.lower() for part in override):
            return override
        path = shutil.which('ddd-gui')
        if path:
            return [path]
        flatpak = shutil.which('flatpak')
        if flatpak:
            probe = subprocess.run([flatpak, 'info', FLATPAK_APP_ID],
                                   capture_output=True, text=True)
            if probe.returncode == 0:
                self._flatpak = True
                prefix = [flatpak, 'run']
                if not _has_display():
                    # --headless needs no window, but Qt still wants a platform
                    prefix.append('--env=QT_QPA_PLATFORM=offscreen')
                return prefix + ['--command=ddd-gui', FLATPAK_APP_ID]
        return None

    def extra_env(self):
        env = {}
        if not _has_display():
            env['QT_QPA_PLATFORM'] = 'offscreen'
        return env

    def start_command(self, capture_folder, capture_name):
        return self.argv_prefix() + ['--headless', '--start-capture',
                                     '--capture-directory', capture_folder,
                                     '--capture-name', capture_name]

    def stop_command(self):
        return self.argv_prefix() + ['--stop-capture']

    def check_folder(self, capture_folder):
        if self.argv_prefix() is None or not self._flatpak:
            return None
        folder = os.path.abspath(os.path.expanduser(capture_folder))
        home = os.path.expanduser('~')
        roots = (home,) + FLATPAK_WRITABLE_ROOTS
        if any(folder == r or folder.startswith(r.rstrip('/') + '/') for r in roots):
            return None
        return (f"{folder} is outside the folders the Flatpak install of ddd-gui can write to "
                f"({', '.join(roots)}). Choose a capture folder under one of them, or grant access "
                f"with: flatpak override --user --filesystem={folder} {FLATPAK_APP_ID}")


def _has_display():
    return bool(os.environ.get('DISPLAY') or os.environ.get('WAYLAND_DISPLAY')
                or sys.platform in ('darwin', 'win32'))


# ---------------------------------------------------------------- registry

_BACKENDS = {}


def register_backend(backend):
    """Register a backend instance under its key."""
    _BACKENDS[backend.key] = backend


def list_backends():
    return list(_BACKENDS.values())


register_backend(DddGuiBackend())
register_backend(LegacyDomesdayBackend())


# ------------------------------------------------------- hardware detection

def detect_board_generation():
    """
    Look at the USB bus (Linux) and report which Duplicator firmware is attached.
    Returns 'original', 'current' or None (not found, or can't tell on this OS).
    """
    if not sys.platform.startswith('linux'):
        return None
    found = set()
    for dev in glob.glob('/sys/bus/usb/devices/*'):
        try:
            with open(os.path.join(dev, 'idVendor')) as f:
                vid = f.read().strip().lower()
            with open(os.path.join(dev, 'idProduct')) as f:
                pid = f.read().strip().lower()
        except OSError:
            continue
        found.add((vid, pid))
    if DDD_USB_ID_CURRENT in found:
        return 'current'
    if DDD_USB_ID_ORIGINAL in found:
        return 'original'
    return None


def select_backend(key=None):
    """
    Return the backend to use.

    key: 'ddd-gui', 'ddd-legacy' or any registered key; None reads the
         "capture_backend" config value, which defaults to "auto".
    'auto' chooses from the attached board: original firmware -> forked app,
    current firmware -> ddd-gui; with no board visible, ddd-gui if installed,
    else the forked app. Returns (backend, reason).
    """
    if key is None:
        try:
            from config import load_config
            key = load_config().get('capture_backend', 'auto')
        except Exception:
            key = 'auto'

    if key != 'auto':
        backend = _BACKENDS.get(key)
        if backend is None:
            raise ValueError(f"Unknown capture backend '{key}'. "
                             f"Known: {', '.join(sorted(_BACKENDS))}, or 'auto'.")
        return backend, f"set in config (capture_backend = {key})"

    generation = detect_board_generation()
    gui = _BACKENDS['ddd-gui']
    legacy = _BACKENDS['ddd-legacy']
    if generation == 'original':
        if legacy.available():
            return legacy, "board is on original firmware (1d50:603b)"
        return legacy, "board is on original firmware (1d50:603b), but the forked app was not found"
    if generation == 'current':
        return gui, "board is on current firmware (1209:2347)"
    if gui.available():
        return gui, "no board visible; using the installed ddd-gui"
    return legacy, "no board visible and ddd-gui not installed; using the forked app"
