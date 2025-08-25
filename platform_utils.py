#!/usr/bin/env python3
"""
Platform Utils - Cross-Platform Compatibility Module
Handles OS-specific operations and tool detection for DDD Capture Toolkit
"""

import sys
import os
import platform
import subprocess
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Tuple

class PlatformDetector:
    """Detect and provide platform-specific information"""
    
    def __init__(self):
        self.system = platform.system().lower()
        self.is_windows = self.system == 'windows'
        self.is_macos = self.system == 'darwin'  
        self.is_linux = self.system == 'linux'
        self.is_unix = self.is_macos or self.is_linux
    
    @property
    def platform_name(self) -> str:
        """Get human-readable platform name"""
        if self.is_windows:
            return 'Windows'
        elif self.is_macos:
            return 'macOS'
        elif self.is_linux:
            return 'Linux'
        else:
            return platform.system()
    
    @property
    def shell_executable(self) -> str:
        """Get appropriate shell executable"""
        if self.is_windows:
            return 'cmd'
        else:
            return '/bin/bash'

class ToolManager:
    """Manage platform-specific tool paths and commands"""
    
    def __init__(self, detector: PlatformDetector):
        self.detector = detector
        self._tool_cache = {}
    
    def get_tool_variants(self, base_tool: str) -> List[str]:
        """Get platform-specific variants of a tool"""
        variants = [base_tool]
        
        if self.detector.is_windows:
            variants.extend([f"{base_tool}.exe", f"{base_tool}.cmd", f"{base_tool}.bat"])
        
        return variants
    
    def find_tool(self, tool_name: str, search_paths: Optional[List[str]] = None) -> Optional[str]:
        """Find a tool in PATH or specified paths"""
        if tool_name in self._tool_cache:
            return self._tool_cache[tool_name]
        
        variants = self.get_tool_variants(tool_name)
        
        # Check standard PATH first
        for variant in variants:
            path = shutil.which(variant)
            if path:
                self._tool_cache[tool_name] = path
                return path
        
        # Check additional search paths
        if search_paths:
            for search_path in search_paths:
                search_dir = Path(search_path)
                if search_dir.exists():
                    for variant in variants:
                        tool_path = search_dir / variant
                        if tool_path.exists() and tool_path.is_file():
                            full_path = str(tool_path.absolute())
                            self._tool_cache[tool_name] = full_path
                            return full_path
        
        return None
    
    def get_screenshot_command(self) -> Optional[List[str]]:
        """Get platform-specific screenshot command"""
        if self.detector.is_windows:
            # Windows - use PowerShell with .NET
            return ['powershell', '-Command', 
                   'Add-Type -AssemblyName System.Windows.Forms; '
                   '[System.Windows.Forms.Screen]::PrimaryScreen.Bounds']
        elif self.detector.is_macos:
            # macOS - use screencapture
            return ['screencapture']
        elif self.detector.is_linux:
            # Linux - try various tools in order of preference
            for tool in ['spectacle', 'gnome-screenshot', 'scrot', 'import']:
                if self.find_tool(tool):
                    if tool == 'spectacle':
                        return ['spectacle', '--background', '--nonotify']
                    elif tool == 'gnome-screenshot':
                        return ['gnome-screenshot', '--file']
                    elif tool == 'scrot':
                        return ['scrot']
                    elif tool == 'import':  # ImageMagick
                        return ['import', '-window', 'root']
        return None
    
    def get_clipboard_commands(self) -> Dict[str, Optional[List[str]]]:
        """Get platform-specific clipboard commands"""
        if self.detector.is_windows:
            return {
                'copy': ['clip'],
                'paste': ['powershell', '-Command', 'Get-Clipboard']
            }
        elif self.detector.is_macos:
            return {
                'copy': ['pbcopy'],
                'paste': ['pbpaste']
            }
        elif self.detector.is_linux:
            # Try xclip first, then xsel
            if self.find_tool('xclip'):
                return {
                    'copy': ['xclip', '-selection', 'clipboard'],
                    'paste': ['xclip', '-selection', 'clipboard', '-o']
                }
            elif self.find_tool('xsel'):
                return {
                    'copy': ['xsel', '--clipboard', '--input'],
                    'paste': ['xsel', '--clipboard', '--output']
                }
        
        return {'copy': None, 'paste': None}

class CommandRunner:
    """Run commands with platform-specific handling"""
    
    def __init__(self, detector: PlatformDetector):
        self.detector = detector
    
    def clear_screen(self):
        """Clear terminal screen in platform-appropriate way"""
        if self.detector.is_windows:
            os.system('cls')
        else:
            os.system('clear')
    
    def run_command(self, cmd: List[str], **kwargs) -> subprocess.CompletedProcess:
        """Run command with platform-specific adjustments"""
        # Default kwargs
        default_kwargs = {
            'capture_output': True,
            'text': True,
            'timeout': 60
        }
        default_kwargs.update(kwargs)
        
        # Windows-specific adjustments
        if self.detector.is_windows:
            # Use shell=True for Windows for better compatibility
            if 'shell' not in default_kwargs:
                default_kwargs['shell'] = True
        
        try:
            return subprocess.run(cmd, **default_kwargs)
        except FileNotFoundError as e:
            # Provide helpful error message
            tool_name = cmd[0] if cmd else "command"
            raise FileNotFoundError(f"Tool '{tool_name}' not found. "
                                  f"Please ensure it's installed and in PATH.") from e

class PathManager:
    """Handle platform-specific path operations"""
    
    def __init__(self, detector: PlatformDetector):
        self.detector = detector
    
    def get_config_dir(self, app_name: str = "ddd-capture-toolkit") -> Path:
        """Get platform-appropriate configuration directory"""
        if self.detector.is_windows:
            base = Path(os.environ.get('APPDATA', Path.home() / 'AppData' / 'Roaming'))
        elif self.detector.is_macos:
            base = Path.home() / 'Library' / 'Application Support'
        else:  # Linux and others
            base = Path(os.environ.get('XDG_CONFIG_HOME', Path.home() / '.config'))
        
        return base / app_name
    
    def get_data_dir(self, app_name: str = "ddd-capture-toolkit") -> Path:
        """Get platform-appropriate data directory"""
        if self.detector.is_windows:
            base = Path(os.environ.get('LOCALAPPDATA', Path.home() / 'AppData' / 'Local'))
        elif self.detector.is_macos:
            base = Path.home() / 'Library' / 'Application Support'
        else:  # Linux and others
            base = Path(os.environ.get('XDG_DATA_HOME', Path.home() / '.local' / 'share'))
        
        return base / app_name
    
    def get_temp_dir(self) -> Path:
        """Get platform-appropriate temporary directory"""
        import tempfile
        return Path(tempfile.gettempdir())
    
    def make_executable(self, file_path: Path):
        """Make file executable (Unix only)"""
        if self.detector.is_unix:
            import stat
            file_path.chmod(file_path.stat().st_mode | stat.S_IEXEC)

# Global instances for easy access
detector = PlatformDetector()
tools = ToolManager(detector)
runner = CommandRunner(detector)
paths = PathManager(detector)

def get_platform_info() -> Dict[str, str]:
    """Get comprehensive platform information"""
    return {
        'platform': detector.platform_name,
        'system': detector.system,
        'python_version': f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        'architecture': platform.machine(),
        'conda_env': os.environ.get('CONDA_DEFAULT_ENV', 'not in conda'),
        'shell': paths.get_temp_dir().name  # Quick shell test
    }

def check_critical_tools() -> Dict[str, bool]:
    """Check availability of critical cross-platform tools"""
    critical_tools = [
        sys.executable,
        'ffmpeg',
        'sox'
    ]
    
    results = {}
    for tool in critical_tools:
        results[tool] = tools.find_tool(tool) is not None
    
    return results

if __name__ == "__main__":
    # Quick test of platform detection
    print(f"Platform: {detector.platform_name}")
    print(f"Python: {sys.version}")
    
    info = get_platform_info()
    for key, value in info.items():
        print(f"{key}: {value}")
    
    print("\nCritical tools:")
    tool_status = check_critical_tools()
    for tool, available in tool_status.items():
        status = "✓" if available else "✗"
        print(f"  {status} {tool}")
