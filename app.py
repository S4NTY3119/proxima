"""
Proxima - Software Backlight Controller
An ultra-fast software overlay and native hotkey tool to control screen brightness.
"""

import os
import sys
import subprocess
import threading
import traceback
import tempfile
import ctypes
import tkinter as tk
import winreg

try:
    import keyboard
except ImportError:
    keyboard = None

# --- Constants & Windows API Flags ---
LOG_FILE = os.path.join(os.path.expanduser("~"), "Desktop", "proxima_crash.log")
MUTEX_NAME = "Global\\ProximaSingleInstance"

WS_EX_LAYERED = 0x00080000
WS_EX_TRANSPARENT = 0x00000020
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_NOACTIVATE = 0x08000000

SM_XVIRTUALSCREEN = 76
SM_YVIRTUALSCREEN = 77
SM_CXVIRTUALSCREEN = 78
SM_CYVIRTUALSCREEN = 79

# --- Logging Setup ---
def log(message: str):
    """Write messages to a log file on the Desktop for debugging."""
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"{message}\n")
            f.flush()
    except Exception:
        pass

# Initialize log file
with open(LOG_FILE, "w", encoding="utf-8") as f:
    pass
log("START Proxima v5.0 - Professional Refactor")

# --- Startup Registration ---
def register_startup():
    """Register the application to run at Windows startup."""
    if not getattr(sys, 'frozen', False):
        return  # Only register if running as a compiled .exe

    try:
        exe_path = sys.executable
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            0,
            winreg.KEY_SET_VALUE
        )
        winreg.SetValueEx(key, "proxima", 0, winreg.REG_SZ, exe_path)
        winreg.CloseKey(key)
        log("Startup registered successfully.")
    except Exception as e:
        log(f"Failed to register startup: {e}")

# --- Application Class ---
class ProximaApp:
    def __init__(self):
        self.user32 = ctypes.windll.user32
        self.dim_level = 0
        self.target_dim_level = 0
        
        self._setup_dpi()
        self._check_single_instance()
        
        self.root = tk.Tk()
        self.root.withdraw()
        
        self._setup_overlay()
        self._register_hotkeys()
        self._launch_tray_icon()
        
        # Start the polling loop for thread-safe UI updates
        self._poll_ui_updates()

    def _setup_dpi(self):
        """Enable DPI awareness so the overlay covers high-res screens correctly."""
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except AttributeError:
            try:
                self.user32.SetProcessDPIAware()
            except AttributeError:
                pass

    def _check_single_instance(self):
        """Prevent multiple instances of Proxima from running simultaneously."""
        kernel32 = ctypes.windll.kernel32
        kernel32.CreateMutexW(None, True, MUTEX_NAME)
        if kernel32.GetLastError() == 183:
            log("Duplicate instance detected. Exiting.")
            sys.exit(0)

    def _setup_overlay(self):
        """Create the full-screen transparent click-through overlay."""
        vx = self.user32.GetSystemMetrics(SM_XVIRTUALSCREEN)
        vy = self.user32.GetSystemMetrics(SM_YVIRTUALSCREEN)
        vw = self.user32.GetSystemMetrics(SM_CXVIRTUALSCREEN)
        vh = self.user32.GetSystemMetrics(SM_CYVIRTUALSCREEN)
        
        # Fallback for older systems
        if vw == 0:
            vw = self.user32.GetSystemMetrics(0)
            vh = self.user32.GetSystemMetrics(1)

        self.overlay = tk.Toplevel(self.root)
        self.overlay.overrideredirect(True)
        self.overlay.attributes("-topmost", True)
        self.overlay.configure(bg="black")
        self.overlay.geometry(f"{vw}x{vh}+{vx}+{vy}")
        self.overlay.withdraw()
        self.overlay.attributes("-alpha", 0.0)
        self.overlay.update_idletasks()

        # Apply Windows Extended Styles to make it click-through and invisible to Alt-Tab
        hwnd = self.user32.GetParent(self.overlay.winfo_id())
        if hwnd:
            style = self.user32.GetWindowLongW(hwnd, -20)
            self.user32.SetWindowLongW(
                hwnd, -20,
                style | WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE
            )
        log("Overlay initialized successfully.")

    def _register_hotkeys(self):
        """Register global hotkeys using the keyboard module."""
        if keyboard is None:
            log("Error: keyboard module not found. Hotkeys disabled.")
            return

        def increase_dim():
            self.target_dim_level = min(90, self.target_dim_level + 10)
            log(f"Dim increased -> target {self.target_dim_level}%")

        def decrease_dim():
            self.target_dim_level = max(0, self.target_dim_level - 10)
            log(f"Dim decreased -> target {self.target_dim_level}%")

        try:
            # Primary hotkeys
            keyboard.add_hotkey('ctrl+f7', increase_dim, suppress=False)
            keyboard.add_hotkey('ctrl+f8', decrease_dim, suppress=False)
            
            # Alternative fallbacks
            keyboard.add_hotkey('ctrl+shift+down', increase_dim, suppress=False)
            keyboard.add_hotkey('ctrl+shift+up', decrease_dim, suppress=False)
            
            log("Global hotkeys registered.")
        except Exception as e:
            log(f"Failed to register hotkeys: {e}")

    def _poll_ui_updates(self):
        """Thread-safe polling loop to update the Tkinter overlay alpha."""
        if self.dim_level != self.target_dim_level:
            self.dim_level = self.target_dim_level
            if self.dim_level > 0:
                alpha = max(0.01, min(0.90, self.dim_level / 100.0))
                self.overlay.attributes("-alpha", alpha)
                self.overlay.deiconify()
                self.overlay.lift()
                self.overlay.attributes("-topmost", True)
            else:
                self.overlay.withdraw()
                
        self.root.after(50, self._poll_ui_updates)

    def _launch_tray_icon(self):
        """Launch a hidden PowerShell script to manage the system tray icon."""
        icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icon.ico")
        if getattr(sys, 'frozen', False):
            icon_path = os.path.join(sys._MEIPASS, "icon.ico")
            
        if not os.path.exists(icon_path):
            icon_path = ""

        tray_script = f"""
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

$icoPath = "{icon_path}"
if ($icoPath -ne "" -and (Test-Path $icoPath)) {{
    $icon = New-Object System.Drawing.Icon($icoPath)
}} else {{
    $icon = [System.Drawing.SystemIcons]::Application
}}

$notifyIcon = New-Object System.Windows.Forms.NotifyIcon
$notifyIcon.Icon = $icon
$notifyIcon.Visible = $true
$notifyIcon.Text = "Proxima"

$contextMenu = New-Object System.Windows.Forms.ContextMenu
$menuItemExit = New-Object System.Windows.Forms.MenuItem
$menuItemExit.Text = "Exit"
$menuItemExit.add_Click({{
    Stop-Process -Name proxima -ErrorAction SilentlyContinue
    $notifyIcon.Visible = $false
    [System.Windows.Forms.Application]::ExitThread()
}})
$contextMenu.MenuItems.Add($menuItemExit)
$notifyIcon.ContextMenu = $contextMenu

$notifyIcon.BalloonTipTitle = "Proxima Active"
$notifyIcon.BalloonTipText = "Dim: Ctrl+F7 (or Ctrl+Shift+Down)`nBright: Ctrl+F8 (or Ctrl+Shift+Up)"
$notifyIcon.BalloonTipIcon = [System.Windows.Forms.ToolTipIcon]::Info
$notifyIcon.ShowBalloonTip(5000)

$timer = New-Object System.Windows.Forms.Timer
$timer.Interval = 3000
$timer.add_Tick({{
    if (-not (Get-Process -Name proxima -ErrorAction SilentlyContinue)) {{
        $notifyIcon.Visible = $false
        [System.Windows.Forms.Application]::ExitThread()
    }}
}})
$timer.Start()

[System.Windows.Forms.Application]::Run()
"""
        tray_ps1 = os.path.join(tempfile.gettempdir(), "proxima_tray.ps1")
        try:
            with open(tray_ps1, "w", encoding="utf-8") as f:
                f.write(tray_script)
                
            startup_info = subprocess.STARTUPINFO()
            startup_info.dwFlags = subprocess.STARTF_USESHOWWINDOW
            startup_info.wShowWindow = 0
            
            subprocess.Popen(
                ["powershell", "-NoProfile", "-WindowStyle", "Hidden",
                 "-ExecutionPolicy", "Bypass", "-File", tray_ps1],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                startupinfo=startup_info, creationflags=0x08000000
            )
            log("System tray initialized.")
        except Exception as e:
            log(f"Failed to launch system tray: {e}")

    def run(self):
        """Start the application main loop."""
        log("Running application main loop.")
        self.root.mainloop()
        log("Application exited normally.")

# --- Main Execution ---
if __name__ == "__main__":
    try:
        register_startup()
        app = ProximaApp()
        app.run()
    except Exception:
        log("FATAL ERROR:\n" + traceback.format_exc())
        sys.exit(1)
