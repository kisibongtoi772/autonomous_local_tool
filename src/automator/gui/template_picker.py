import os
import glob
from typing import Callable, Optional
from PIL import Image
import customtkinter as ctk

from ..utils.config import TEMPLATES_DIR, T
from ..utils.logger import get_logger

logger = get_logger(__name__)

class TemplatePicker(ctk.CTkToplevel):
    def __init__(self, parent, on_pick: Callable[[str], None], on_cancel: Optional[Callable[[], None]] = None):
        super().__init__(parent)
        self.on_pick = on_pick
        self.on_cancel = on_cancel
        self.title("Pick a Template")
        self.geometry("640x480")
        self.transient(parent)
        self.grab_set()
        self.configure(fg_color=T["bg"])
        
        # Header
        hdr = ctk.CTkFrame(self, fg_color="transparent")
        hdr.pack(fill="x", padx=16, pady=(16, 8))
        ctk.CTkLabel(
            hdr, text="Select a Template",
            font=ctk.CTkFont("SF Pro Display", 18, "bold"), text_color=T["text"]
        ).pack(side="left")
        
        if self.on_cancel:
            self.protocol("WM_DELETE_WINDOW", self._cancel)
            
        files = glob.glob(os.path.join(TEMPLATES_DIR, "*.png"))
        if not files:
            ctk.CTkLabel(self, text="No templates found in workspace/templates/.", text_color=T["dim"]).pack(pady=40)
            return
            
        scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=16, pady=16)
        
        # Grid layout for images (e.g., 3 columns)
        cols = 3
        for i, path in enumerate(files):
            row = i // cols
            col = i % cols
            fname = os.path.basename(path)
            
            card = ctk.CTkFrame(scroll, fg_color=T["raised"], corner_radius=6)
            card.grid(row=row, column=col, padx=8, pady=8, sticky="nsew")
            
            try:
                pil_img = Image.open(path)
                w, h = pil_img.size
                preview = pil_img.copy()
                preview.thumbnail((80, 80))
                ctk_img = ctk.CTkImage(light_image=preview, dark_image=preview, size=preview.size)
                
                img_lbl = ctk.CTkLabel(card, image=ctk_img, text="")
                img_lbl.pack(padx=8, pady=8)
                
                txt_lbl = ctk.CTkLabel(card, text=f"{fname}\n{w}x{h} px", font=ctk.CTkFont("SF Pro Text", 10), text_color=T["text"])
                txt_lbl.pack(padx=8, pady=(0, 8))
                
                # Bind click events
                for w_elem in [card, img_lbl, txt_lbl]:
                    w_elem.bind("<Button-1>", lambda e, f=fname: self._pick(f))
                    w_elem.configure(cursor="hand2")
                    
            except Exception:
                lbl = ctk.CTkLabel(card, text=fname, font=ctk.CTkFont("SF Pro Text", 11), text_color=T["text"])
                lbl.pack(padx=8, pady=24)
                lbl.bind("<Button-1>", lambda e, f=fname: self._pick(f))
                lbl.configure(cursor="hand2")
                card.bind("<Button-1>", lambda e, f=fname: self._pick(f))
                card.configure(cursor="hand2")

    def _pick(self, filename: str):
        self.on_pick(filename)
        self.destroy()
        
    def _cancel(self):
        if self.on_cancel:
            self.on_cancel()
        self.destroy()
