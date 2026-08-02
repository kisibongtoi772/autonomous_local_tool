import tkinter as tk
from typing import Callable, Optional
import customtkinter as ctk

from ..utils.config import T
from ..utils.logger import get_logger

logger = get_logger(__name__)

BUILTIN_VARS = [
    ("TIME", "Current time (HH:MM:SS)"),
    ("DATE", "Current date (YYYY-MM-DD)"),
    ("DATETIME", "Current date and time"),
    ("CLIPBOARD", "Current clipboard text"),
    ("loop_index", "Index of the current loop iteration (0, 1, 2...)")
]

class VariablePicker(ctk.CTkToplevel):
    def __init__(self, parent, var_manager, on_pick: Callable[[str], None], on_cancel: Optional[Callable[[], None]] = None):
        super().__init__(parent)
        self.on_pick = on_pick
        self.on_cancel = on_cancel
        self.title("Pick a Variable")
        self.geometry("400x480")
        self.transient(parent)
        self.grab_set()
        self.configure(fg_color=T["bg"])
        
        # Header
        hdr = ctk.CTkFrame(self, fg_color="transparent")
        hdr.pack(fill="x", padx=16, pady=(16, 8))
        ctk.CTkLabel(
            hdr, text="Select a Variable",
            font=ctk.CTkFont("SF Pro Display", 18, "bold"), text_color=T["text"]
        ).pack(side="left")
        
        if self.on_cancel:
            self.protocol("WM_DELETE_WINDOW", self._cancel)
            
        scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=16, pady=(0, 16))
        
        # Built-ins Section
        ctk.CTkLabel(
            scroll, text="System Built-ins",
            font=ctk.CTkFont("SF Pro Display", 14, "bold"), text_color=T["dim"]
        ).pack(anchor="w", pady=(10, 5))
        
        for v_name, v_desc in BUILTIN_VARS:
            self._render_var_row(scroll, v_name, v_desc)
            
        self.var_manager = var_manager
        
        # User Variables Section
        ctk.CTkLabel(
            scroll, text="User Variables",
            font=ctk.CTkFont("SF Pro Display", 14, "bold"), text_color=T["dim"]
        ).pack(anchor="w", pady=(20, 5))
        
        # Quick Add Row
        add_frame = ctk.CTkFrame(scroll, fg_color="transparent")
        add_frame.pack(fill="x", pady=(0, 10))
        
        self.new_var_name = ctk.CTkEntry(add_frame, placeholder_text="Name (e.g. url)", width=120, height=28, fg_color=T["raised"], border_color=T["border"])
        self.new_var_name.pack(side="left", padx=(0, 4))
        
        self.new_var_val = ctk.CTkEntry(add_frame, placeholder_text="Value", width=160, height=28, fg_color=T["raised"], border_color=T["border"])
        self.new_var_val.pack(side="left", fill="x", expand=True, padx=(0, 4))
        
        add_btn = ctk.CTkButton(add_frame, text="+", width=28, height=28, fg_color=T["accent"], text_color=T["text"], command=self._quick_add)
        add_btn.pack(side="right")
        
        self.user_vars_container = ctk.CTkFrame(scroll, fg_color="transparent")
        self.user_vars_container.pack(fill="x")
        
        self._refresh_user_vars()
        
    def _quick_add(self):
        k = self.new_var_name.get().strip()
        v = self.new_var_val.get()
        if k:
            self.var_manager.set(k, v)
            self.new_var_name.delete(0, "end")
            self.new_var_val.delete(0, "end")
            self._refresh_user_vars()
            
    def _refresh_user_vars(self):
        for w in self.user_vars_container.winfo_children():
            w.destroy()
            
        self.var_manager.load()
        if not self.var_manager.variables:
            ctk.CTkLabel(self.user_vars_container, text="No user variables defined.", text_color=T["dim"]).pack(anchor="w")
        else:
            for k, v in self.var_manager.variables.items():
                self._render_var_row(self.user_vars_container, k, f"Current value: {v}")

    def _render_var_row(self, parent, name, desc):
        row = ctk.CTkFrame(parent, fg_color=T["raised"], corner_radius=6)
        row.pack(fill="x", pady=2)
        
        info = ctk.CTkFrame(row, fg_color="transparent")
        info.pack(side="left", fill="both", expand=True, padx=12, pady=8)
        
        ctk.CTkLabel(info, text=f"{{{{{name}}}}}", font=ctk.CTkFont("SF Pro Text", 12, "bold"), text_color=T["accent"]).pack(anchor="w")
        ctk.CTkLabel(info, text=desc, font=ctk.CTkFont("SF Pro Text", 10), text_color=T["dim"]).pack(anchor="w")
        
        # Bind clicks
        for w in [row, info] + info.winfo_children():
            w.bind("<Button-1>", lambda e, n=name: self._pick(n))
            w.configure(cursor="hand2")

    def _pick(self, var_name: str):
        self.on_pick(f"{{{{{var_name}}}}}")
        self.destroy()
        
    def _cancel(self):
        if self.on_cancel:
            self.on_cancel()
        self.destroy()
