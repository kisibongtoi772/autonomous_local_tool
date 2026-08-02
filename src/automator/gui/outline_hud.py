import tkinter as tk
import customtkinter as ctk
from typing import Callable, List, Dict

from ..utils.config import T
from ..utils.logger import get_logger

logger = get_logger(__name__)

class OutlineHUD(ctk.CTkToplevel):
    def __init__(self, parent, actions: List[Dict], on_jump: Callable[[int], None]):
        super().__init__(parent)
        self.on_jump = on_jump
        
        self.title("Workflow Outline")
        self.geometry("300x500")
        self.configure(fg_color=T["bg"])
        
        # Make it float on top, but not steal focus completely
        self.attributes("-topmost", True)
        
        # Position it to the right of the main window
        try:
            x = parent.winfo_x() + parent.winfo_width() - 320
            y = parent.winfo_y() + 100
            self.geometry(f"+{x}+{y}")
        except:
            pass
            
        hdr = ctk.CTkFrame(self, fg_color="transparent")
        hdr.pack(fill="x", padx=16, pady=(16, 8))
        ctk.CTkLabel(
            hdr, text="Outline 📑",
            font=ctk.CTkFont("SF Pro Display", 16, "bold"), text_color=T["text"]
        ).pack(side="left")
        
        # Scrollable list
        self.list_frame = ctk.CTkScrollableFrame(
            self, fg_color=T["surface"], corner_radius=8
        )
        self.list_frame.pack(fill="both", expand=True, padx=16, pady=(0, 16))
        
        self._build_tree(actions)
        
    def _build_tree(self, actions: List[Dict]):
        # Destroy old widgets if any
        for w in self.list_frame.winfo_children():
            w.destroy()
            
        count = 0
        for i, action in enumerate(actions):
            atype = action.get("type", "")
            if atype == "comment":
                # It's a header
                text = action.get("text", "---")
                self._add_node(f"💬 {text}", i, is_header=True)
                count += 1
            elif atype == "group":
                label = action.get("label", "Group")
                self._add_node(f"📦 {label}", i, is_header=False)
                count += 1
                
        if count == 0:
            ctk.CTkLabel(
                self.list_frame, text="No comments or groups found.",
                text_color=T["dim"], font=ctk.CTkFont("SF Pro Text", 12)
            ).pack(pady=20)
            
    def _add_node(self, text: str, idx: int, is_header: bool):
        btn = ctk.CTkButton(
            self.list_frame, text=text,
            fg_color="transparent", hover_color=T["hover"],
            text_color=T["accent"] if is_header else T["text"],
            font=ctk.CTkFont("SF Pro Text", 13, "bold" if is_header else "normal"),
            anchor="w", height=32,
            command=lambda: self._jump(idx)
        )
        btn.pack(fill="x", pady=2, padx=4)
        
    def _jump(self, idx: int):
        if self.on_jump:
            self.on_jump(idx)
