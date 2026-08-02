import tkinter as tk
import customtkinter as ctk
from typing import Callable, Optional
from ..utils.config import T

class CommandPalette(ctk.CTkToplevel):
    def __init__(self, parent, on_submit: Callable[[dict], None]):
        super().__init__(parent)
        self.on_submit = on_submit
        
        self.title("")
        self.geometry("600x120")
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.configure(fg_color=T["bg"])
        
        # Center on parent
        x = parent.winfo_rootx() + (parent.winfo_width() // 2) - 300
        y = parent.winfo_rooty() + (parent.winfo_height() // 2) - 150
        self.geometry(f"+{x}+{y}")
        
        # Optional border for visibility
        self.border_frame = ctk.CTkFrame(self, fg_color=T["border"], corner_radius=10)
        self.border_frame.pack(fill="both", expand=True, padx=2, pady=2)
        
        self.inner_frame = ctk.CTkFrame(self.border_frame, fg_color=T["bg"], corner_radius=8)
        self.inner_frame.pack(fill="both", expand=True, padx=1, pady=1)
        
        # Search entry
        self.entry_var = ctk.StringVar()
        self.entry = ctk.CTkEntry(
            self.inner_frame, textvariable=self.entry_var,
            font=ctk.CTkFont("SF Pro Display", 24),
            fg_color=T["raised"], border_color=T["accent"], border_width=2,
            text_color=T["text"], placeholder_text="Type command (e.g. sleep 2, click 100,200)...",
            height=60
        )
        self.entry.pack(fill="x", padx=10, pady=10)
        
        # Preview label
        self.preview = ctk.CTkLabel(
            self.inner_frame, text="Preview: ...", font=ctk.CTkFont("SF Pro Text", 14, slant="italic"),
            text_color=T["dim"]
        )
        self.preview.pack(fill="x", padx=15, pady=(0, 10), anchor="w")
        
        self.entry.bind("<Return>", self._on_enter)
        self.entry.bind("<Escape>", lambda e: self.destroy())
        self.entry_var.trace_add("write", self._on_type)
        
        # Bind focus out to destroy if we want it to act like a true palette
        self.bind("<FocusOut>", lambda e: self.destroy())
        
        self.entry.focus_set()
        
    def _parse(self, text: str) -> Optional[dict]:
        text = text.strip()
        if not text: return None
        parts = text.split(" ", 1)
        cmd = parts[0].lower()
        val = parts[1] if len(parts) > 1 else ""
        
        if cmd == "sleep":
            try: return {"type": "sleep", "duration": float(val or 1), "time_offset": 0.5}
            except ValueError: return None
        elif cmd == "type":
            return {"type": "type", "key": val, "time_offset": 0.5}
        elif cmd == "click":
            try:
                coords = [v.strip() for v in val.split(",")]
                return {"type": "click", "x": int(coords[0]), "y": int(coords[1]), "time_offset": 0.5}
            except Exception: return None
        elif cmd == "find":
            return {"type": "wait_for_template", "template": val, "time_offset": 0.5}
        elif cmd == "run":
            return {"type": "run_command", "command": val, "wait": True, "time_offset": 0.5}
        elif cmd == "scroll":
            try: return {"type": "scroll", "amount": int(val or -3), "time_offset": 0.5}
            except ValueError: return None
        elif cmd == "key" or cmd == "hotkey":
            keys = [k.strip() for k in val.split(",")]
            return {"type": "hotkey", "keys": keys, "time_offset": 0.5}
        elif cmd == "group":
            return {"type": "group", "name": val or "New Group", "actions": []}
            
        return None

    def _on_type(self, *args):
        parsed = self._parse(self.entry_var.get())
        if parsed:
            desc = f"{parsed['type'].upper()} " + str({k:v for k,v in parsed.items() if k not in ('type', 'time_offset', 'actions')})
            self.preview.configure(text=f"Press Enter ➔ {desc}", text_color=T["ok"])
        else:
            self.preview.configure(text="Preview: (invalid or typing...)", text_color=T["dim"])
            
    def _on_enter(self, event):
        parsed = self._parse(self.entry_var.get())
        if parsed:
            self.on_submit(parsed)
            self.destroy()
