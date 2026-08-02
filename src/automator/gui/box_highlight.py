import tkinter as tk
from typing import Callable, Optional
import customtkinter as ctk

class BoxHighlight(ctk.CTkToplevel):
    def __init__(self, parent, x: int, y: int, w: int, h: int, on_complete: Optional[Callable[[], None]] = None):
        super().__init__(parent)
        self.on_complete = on_complete
        
        # Add a little padding to the box
        pad = 4
        self.geometry(f"{w + pad*2}x{h + pad*2}+{x - pad}+{y - pad}")
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        
        # Transparent background setup for macOS
        try:
            self.attributes("-transparent", True)
            self.config(bg="systemTransparent")
            canvas_bg = "systemTransparent"
        except Exception:
            # Fallback for other OS
            self.attributes("-alpha", 0.8)
            canvas_bg = "black"
            self.wm_attributes("-transparentcolor", "black")
            
        self.canvas = tk.Canvas(self, bg=canvas_bg, highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        
        # Draw a lime green bounding box
        self.rect = self.canvas.create_rectangle(
            pad, pad,
            w + pad, h + pad,
            outline="#39FF14", width=4
        )
        
        # Fade out timer (500ms)
        self.after(500, self._finish)
        
    def _finish(self):
        self.destroy()
        if self.on_complete:
            self.on_complete()
