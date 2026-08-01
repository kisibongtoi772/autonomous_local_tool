import tkinter as tk
from typing import Callable, Optional
import customtkinter as ctk

class ClickRipple(ctk.CTkToplevel):
    def __init__(self, parent, x: int, y: int, on_complete: Optional[Callable[[], None]] = None):
        super().__init__(parent)
        self.on_complete = on_complete
        
        size = 80
        self.geometry(f"{size}x{size}+{x - size//2}+{y - size//2}")
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        
        # Transparent background setup for macOS
        try:
            self.attributes("-transparent", True)
            self.config(bg="systemTransparent")
            canvas_bg = "systemTransparent"
        except Exception:
            # Fallback for other OS if needed
            self.attributes("-alpha", 0.8)
            canvas_bg = "black"
            self.wm_attributes("-transparentcolor", "black")
            
        self.canvas = tk.Canvas(self, bg=canvas_bg, highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        
        self.radius = 5
        self.max_radius = size // 2 - 2
        
        # Draw a red target
        self.circle = self.canvas.create_oval(
            size//2 - self.radius, size//2 - self.radius,
            size//2 + self.radius, size//2 + self.radius,
            outline="#ff3333", width=4
        )
        
        # Crosshair in the middle
        self.canvas.create_line(size//2 - 10, size//2, size//2 + 10, size//2, fill="#ff3333", width=2)
        self.canvas.create_line(size//2, size//2 - 10, size//2, size//2 + 10, fill="#ff3333", width=2)
        
        self.after(20, self._animate)
        
    def _animate(self):
        self.radius += 4
        if self.radius <= self.max_radius:
            size = 80
            self.canvas.coords(
                self.circle,
                size//2 - self.radius, size//2 - self.radius,
                size//2 + self.radius, size//2 + self.radius
            )
            # Fade out by changing color or just keep expanding
            self.after(20, self._animate)
        else:
            self.destroy()
            if self.on_complete:
                self.on_complete()
