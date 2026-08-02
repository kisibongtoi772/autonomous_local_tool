import tkinter as tk
import customtkinter as ctk
from typing import Callable, List
import os

from ..utils.config import T

class FileSwitcher(ctk.CTkToplevel):
    def __init__(self, parent, files: List[str], current_file: str, on_select: Callable[[str], None]):
        super().__init__(parent)
        self.files = sorted(files, key=str.lower)
        self.current_file = current_file
        self.on_select = on_select
        
        self.title("")
        self.geometry("500x350")
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.configure(fg_color=T["bg"])
        
        # Center on parent
        x = parent.winfo_rootx() + (parent.winfo_width() // 2) - 250
        y = parent.winfo_rooty() + (parent.winfo_height() // 2) - 175
        self.geometry(f"+{x}+{y}")
        
        # Border frame
        self.border_frame = ctk.CTkFrame(self, fg_color=T["border"], corner_radius=10)
        self.border_frame.pack(fill="both", expand=True, padx=2, pady=2)
        
        self.inner_frame = ctk.CTkFrame(self.border_frame, fg_color=T["bg"], corner_radius=8)
        self.inner_frame.pack(fill="both", expand=True, padx=1, pady=1)
        
        # Search Entry
        self.search_var = ctk.StringVar()
        self.entry = ctk.CTkEntry(
            self.inner_frame, textvariable=self.search_var,
            font=ctk.CTkFont("SF Pro Display", 18),
            fg_color=T["raised"], border_color=T["accent"], border_width=2,
            text_color=T["text"], placeholder_text="Type to find workflow file (e.g. login)...",
            height=45
        )
        self.entry.pack(fill="x", padx=10, pady=(10, 5))
        
        # Scrollable List
        self.list_frame = ctk.CTkScrollableFrame(self.inner_frame, fg_color="transparent")
        self.list_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        
        self.buttons: List[ctk.CTkButton] = []
        self._selected_index = 0
        self._matching_files = self.files.copy()
        
        self.search_var.trace_add("write", self._on_search)
        self.entry.bind("<Return>", self._on_enter)
        self.entry.bind("<Escape>", lambda e: self.destroy())
        self.entry.bind("<Up>", self._on_up)
        self.entry.bind("<Down>", self._on_down)
        
        self.bind("<FocusOut>", lambda e: self.destroy())
        self.entry.focus_set()
        
        self._render_list()

    def _render_list(self):
        for btn in self.buttons:
            btn.destroy()
        self.buttons.clear()
        
        if not self._matching_files:
            lbl = ctk.CTkLabel(self.list_frame, text="No matching files found.", text_color=T["dim"])
            lbl.pack(pady=20)
            return

        for i, f in enumerate(self._matching_files):
            # Highlight matching part? Not easily in standard CTkButton without complex canvas.
            btn = ctk.CTkButton(
                self.list_frame, text=f, height=36, anchor="w",
                font=ctk.CTkFont("SF Pro Text", 14),
                fg_color="transparent", hover_color=T["raised"],
                text_color=T["text"], corner_radius=6,
                command=lambda f_name=f: self._select_file(f_name)
            )
            btn.pack(fill="x", pady=1)
            # Hover bindings for mouse interaction
            btn.bind("<Enter>", lambda e, idx=i: self._update_selection(idx))
            self.buttons.append(btn)
            
        # Select first item if available
        self._update_selection(0)

    def _on_search(self, *args):
        query = self.search_var.get().lower().strip()
        if not query:
            self._matching_files = self.files.copy()
        else:
            self._matching_files = [f for f in self.files if query in f.lower()]
        self._render_list()

    def _update_selection(self, idx: int):
        if not self.buttons: return
        
        if 0 <= self._selected_index < len(self.buttons):
            self.buttons[self._selected_index].configure(fg_color="transparent")
            
        self._selected_index = max(0, min(idx, len(self.buttons) - 1))
        self.buttons[self._selected_index].configure(fg_color=T["accent"])
        
        # Ensure visible
        # CTkScrollableFrame doesn't have an easy scroll-to-widget method without reaching into _parent_canvas
        try:
            total = len(self.buttons)
            if total > 5:
                scroll_fraction = max(0.0, (self._selected_index / total) - 0.1)
                self.list_frame._parent_canvas.yview_moveto(scroll_fraction)
        except Exception:
            pass

    def _on_up(self, event):
        self._update_selection(self._selected_index - 1)
        return "break" # Prevent default Entry behavior

    def _on_down(self, event):
        self._update_selection(self._selected_index + 1)
        return "break"

    def _on_enter(self, event):
        if self._matching_files and 0 <= self._selected_index < len(self._matching_files):
            self._select_file(self._matching_files[self._selected_index])
            
    def _select_file(self, filename: str):
        self.on_select(filename)
        self.destroy()
