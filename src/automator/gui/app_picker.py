import tkinter as tk
import subprocess
from typing import Callable, Optional
import customtkinter as ctk

from ..utils.config import T
from ..utils.logger import get_logger

logger = get_logger(__name__)

class AppPicker(ctk.CTkToplevel):
    def __init__(self, parent, on_pick: Callable[[str], None], on_cancel: Optional[Callable[[], None]] = None):
        super().__init__(parent)
        self.on_pick = on_pick
        self.on_cancel = on_cancel
        self.title("Running Applications")
        self.geometry("400x480")
        self.transient(parent)
        self.grab_set()
        self.configure(fg_color=T["bg"])
        
        # Header
        hdr = ctk.CTkFrame(self, fg_color="transparent")
        hdr.pack(fill="x", padx=16, pady=(16, 8))
        ctk.CTkLabel(
            hdr, text="Select an App",
            font=ctk.CTkFont("SF Pro Display", 18, "bold"), text_color=T["text"]
        ).pack(side="left")
        
        if self.on_cancel:
            self.protocol("WM_DELETE_WINDOW", self._cancel)
            
        scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=16, pady=(0, 16))
        
        apps = self._get_running_apps()
        if not apps:
            ctk.CTkLabel(scroll, text="No running GUI apps found.", text_color=T["dim"]).pack(anchor="w")
        else:
            for app in apps:
                self._render_app_row(scroll, app)

    def _get_running_apps(self):
        try:
            # Uses AppleScript to fetch names of applications that have GUI (background only is false)
            cmd = ['osascript', '-e', 'tell application "System Events" to get name of every application process whose background only is false']
            res = subprocess.run(cmd, capture_output=True, text=True)
            if res.returncode == 0:
                apps = [a.strip() for a in res.stdout.split(',')]
                return sorted(list(set(apps)), key=str.lower)
        except Exception as e:
            logger.error(f"Error fetching running apps: {e}")
        return ["Finder", "Google Chrome", "Safari", "Terminal", "System Settings"]

    def _render_app_row(self, parent, name):
        row = ctk.CTkFrame(parent, fg_color=T["raised"], corner_radius=6)
        row.pack(fill="x", pady=2)
        
        info = ctk.CTkFrame(row, fg_color="transparent")
        info.pack(side="left", fill="both", expand=True, padx=12, pady=10)
        
        ctk.CTkLabel(info, text=name, font=ctk.CTkFont("SF Pro Text", 13, "bold"), text_color=T["accent"]).pack(anchor="w")
        
        # Bind clicks to select the app
        for w in [row, info] + info.winfo_children():
            w.bind("<Button-1>", lambda e, n=name: self._pick(n))
            w.configure(cursor="hand2")

    def _pick(self, name: str):
        self.on_pick(name)
        self.destroy()
        
    def _cancel(self):
        if self.on_cancel:
            self.on_cancel()
        self.destroy()
