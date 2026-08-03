import tkinter as tk
from typing import Callable, Optional
import customtkinter as ctk

class BoundingBoxOverlay(ctk.CTkToplevel):
    def __init__(self, parent, x: int, y: int, w: int, h: int, duration_ms: int = 1500, on_complete: Optional[Callable[[], None]] = None, color: str = "#ff3333", alt_color: str = "#ff9999"):
        super().__init__(parent)
        self.on_complete = on_complete
        self.color = color
        self.alt_color = alt_color
        
        # Add a bit of padding for the border
        pad = 6
        self.geometry(f"{w + pad*2}x{h + pad*2}+{x - pad}+{y - pad}")
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        
        # Transparent background setup for macOS
        try:
            self.attributes("-transparent", True)
            self.config(bg="systemTransparent")
            canvas_bg = "systemTransparent"
        except Exception:
            self.attributes("-alpha", 0.8)
            canvas_bg = "black"
            self.wm_attributes("-transparentcolor", "black")
            
        self.canvas = tk.Canvas(self, bg=canvas_bg, highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        
        # Draw a thick glowing red box
        self.box = self.canvas.create_rectangle(
            pad, pad, w + pad, h + pad,
            outline=self.color, width=4, dash=(10, 5)
        )
        
        # Draw corners
        c_len = max(5, min(15, w//4, h//4))
        self.canvas.create_line(pad, pad, pad + c_len, pad, fill=self.color, width=6)
        self.canvas.create_line(pad, pad, pad, pad + c_len, fill=self.color, width=6)
        
        self.canvas.create_line(w + pad, pad, w + pad - c_len, pad, fill=self.color, width=6)
        self.canvas.create_line(w + pad, pad, w + pad, pad + c_len, fill=self.color, width=6)
        
        self.canvas.create_line(pad, h + pad, pad + c_len, h + pad, fill=self.color, width=6)
        self.canvas.create_line(pad, h + pad, pad, h + pad - c_len, fill=self.color, width=6)
        
        self.canvas.create_line(w + pad, h + pad, w + pad - c_len, h + pad, fill=self.color, width=6)
        self.canvas.create_line(w + pad, h + pad, w + pad, h + pad - c_len, fill=self.color, width=6)
        
        # Flash animation state
        self.flash_state = True
        self.after(150, self._animate)
        
        # Auto destroy
        self.after(duration_ms, self._finish)
        
    def _animate(self):
        if not self.winfo_exists(): return
        self.flash_state = not self.flash_state
        color = self.color if self.flash_state else self.alt_color
        self.canvas.itemconfig(self.box, outline=color)
        self.after(150, self._animate)
        
    def _finish(self):
        self.destroy()
        if self.on_complete:
            self.on_complete()
