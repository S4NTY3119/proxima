"""
███████╗       ██╗██╗ ███╗   ██╗ ████████╗ ██╗   ██╗
██╔════╝     ██╔╝ ██║ ████╗  ██║ ╚══██╔══╝ ╚██╗ ██╔╝
███████╗   ██╔╝   ██║ ██╔██╗ ██║    ██║     ╚████╔╝ 
╚════██║  ██████████║ ██║╚██╗██║    ██║      ╚██╔╝  
███████║  ╚═══════██║ ██║ ╚████║    ██║       ██║   
╚══════╝          ╚═╝ ╚═╝  ╚═══╝    ╚═╝       ╚═╝
proxima, go crazy every night >3<
"""

import os, sys, subprocess, threading, time, traceback, tempfile, ctypes
import tkinter as tk

LOG = os.path.join(os.path.expanduser("~"), "Desktop", "crash.log")
def log(m):
    try:
        with open(LOG, "a") as f: f.write(f"{m}\n"); f.flush()
    except: pass

open(LOG, "w").close()
log("START v4.0 - Proxima + Startup")

def register_startup():
    try:
        import winreg
        exe_path = sys.executable
        if getattr(sys, 'frozen', False):
            # We only register if running as a frozen exe
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_SET_VALUE)
            winreg.SetValueEx(key, "proxima", 0, winreg.REG_SZ, exe_path)
            winreg.CloseKey(key)
            log("startup registered")
    except Exception as e:
        log(f"startup err: {e}")

def main():
    user32   = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32

    try: ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except:
        try: user32.SetProcessDPIAware()
        except: pass

    # Single instance
    kernel32.CreateMutexW(None, True, "Global\\ProximaSingleInstance")
    if kernel32.GetLastError() == 183:
        log("duplicate, exiting"); sys.exit(0)

    # Register for startup
    register_startup()

    # --- Pure Software Dimming Overlay ---
    WS_EX_LAYERED    = 0x00080000
    WS_EX_TRANSPARENT= 0x00000020
    WS_EX_TOOLWINDOW = 0x00000080
    WS_EX_NOACTIVATE = 0x08000000

    SM_XVIRTUALSCREEN = 76
    SM_YVIRTUALSCREEN = 77
    SM_CXVIRTUALSCREEN = 78
    SM_CYVIRTUALSCREEN = 79

    dim_level = 0
    target_dim_level = 0

    root = tk.Tk()
    root.withdraw()

    vx = user32.GetSystemMetrics(SM_XVIRTUALSCREEN)
    vy = user32.GetSystemMetrics(SM_YVIRTUALSCREEN)
    vw = user32.GetSystemMetrics(SM_CXVIRTUALSCREEN)
    vh = user32.GetSystemMetrics(SM_CYVIRTUALSCREEN)
    if vw == 0:
        vw = user32.GetSystemMetrics(0); vh = user32.GetSystemMetrics(1)

    overlay = tk.Toplevel(root)
    overlay.overrideredirect(True)
    overlay.attributes("-topmost", True)
    overlay.configure(bg="black")
    overlay.geometry(f"{vw}x{vh}+{vx}+{vy}")
    overlay.withdraw()
    overlay.attributes("-alpha", 0.0)
    overlay.update_idletasks()

    hwnd_ov = user32.GetParent(overlay.winfo_id())
    if hwnd_ov:
        s = user32.GetWindowLongW(hwnd_ov, -20)
        user32.SetWindowLongW(hwnd_ov, -20,
            s | WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE)
    log("overlay ok")

    def show_overlay(level):
        a = max(0.01, min(0.90, level / 100.0))
        overlay.attributes("-alpha", a); overlay.deiconify(); overlay.lift()
        overlay.attributes("-topmost", True)

    def hide_overlay(): overlay.withdraw()

    def check_dim():
        nonlocal dim_level
        if dim_level != target_dim_level:
            dim_level = target_dim_level
            log(f"applying dim {dim_level}%")
            if dim_level > 0: show_overlay(dim_level)
            else: hide_overlay()
        root.after(50, check_dim)

    # --- Robust Keyboard Hook ---
    try:
        import keyboard
        log("keyboard module imported")

        def on_dim():
            nonlocal target_dim_level
            target_dim_level = min(90, target_dim_level + 10)
            log(f"DIM PRESSED -> target {target_dim_level}")
            
        def on_bright():
            nonlocal target_dim_level
            target_dim_level = max(0, target_dim_level - 10)
            log(f"BRIGHT PRESSED -> target {target_dim_level}")

        # Primary hotkeys
        keyboard.add_hotkey('ctrl+f7', on_dim, suppress=True)
        keyboard.add_hotkey('ctrl+f8', on_bright, suppress=True)
        
        # Fallback hotkeys
        keyboard.add_hotkey('ctrl+shift+down', on_dim, suppress=True)
        keyboard.add_hotkey('ctrl+shift+up', on_bright, suppress=True)
        
        log("hotkeys registered successfully")
    except Exception as e:
        log(f"keyboard error: {e}")

    # Start Tkinter polling loop (safe UI updates)
    root.after(50, check_dim)

    # --- Tray icon (PowerShell .NET WinForms) ---
    SI = subprocess.STARTUPINFO()
    SI.dwFlags = subprocess.STARTF_USESHOWWINDOW; SI.wShowWindow = 0
    CF = 0x08000000

    icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icon.ico")
    if getattr(sys, 'frozen', False):
        icon_path = os.path.join(sys._MEIPASS, "icon.ico")
    if not os.path.exists(icon_path):
        icon_path = ""

    TRAY_SCRIPT = r"""
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

$icoPath = "__ICON_PATH__"
if ($icoPath -ne "" -and (Test-Path $icoPath)) {
    $icon = New-Object System.Drawing.Icon($icoPath)
} else {
    $icon = [System.Drawing.SystemIcons]::Application
}

$notifyIcon = New-Object System.Windows.Forms.NotifyIcon
$notifyIcon.Icon = $icon
$notifyIcon.Visible = $true
$notifyIcon.Text = "proxima"

$contextMenu = New-Object System.Windows.Forms.ContextMenu
$menuItemExit = New-Object System.Windows.Forms.MenuItem
$menuItemExit.Text = "Exit"
$menuItemExit.add_Click({
    Stop-Process -Name proxima -ErrorAction SilentlyContinue
    $notifyIcon.Visible = $false
    [System.Windows.Forms.Application]::ExitThread()
})
$contextMenu.MenuItems.Add($menuItemExit)
$notifyIcon.ContextMenu = $contextMenu

$notifyIcon.BalloonTipTitle = "proxima Active"
$notifyIcon.BalloonTipText = "Dim: Ctrl+F7 (or Ctrl+Shift+Down)`nBright: Ctrl+F8 (or Ctrl+Shift+Up)"
$notifyIcon.BalloonTipIcon = [System.Windows.Forms.ToolTipIcon]::Info
$notifyIcon.ShowBalloonTip(5000)

$timer = New-Object System.Windows.Forms.Timer
$timer.Interval = 3000
$timer.add_Tick({
    if (-not (Get-Process -Name proxima -ErrorAction SilentlyContinue)) {
        $notifyIcon.Visible = $false
        [System.Windows.Forms.Application]::ExitThread()
    }
})
$timer.Start()

[System.Windows.Forms.Application]::Run()
"""
    tray_script = TRAY_SCRIPT.replace("__ICON_PATH__", icon_path)
    tray_ps1 = os.path.join(tempfile.gettempdir(), "proxima_tray.ps1")
    try:
        with open(tray_ps1, "w") as f:
            f.write(tray_script)
        subprocess.Popen(
            ["powershell", "-NoProfile", "-WindowStyle", "Hidden",
             "-ExecutionPolicy", "Bypass", "-File", tray_ps1],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            startupinfo=SI, creationflags=CF)
        log("tray launched")
    except Exception as e:
        log(f"tray error: {e}")

    log("running mainloop")
    root.mainloop()
    log("mainloop exited")

try:
    main()
except Exception:
    log("FATAL:\n" + traceback.format_exc())
    sys.exit(1)
