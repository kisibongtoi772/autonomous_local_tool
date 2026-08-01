import tkinter as tk
from typing import Callable
import customtkinter as ctk

class CountdownOverlay(ctk.CTkToplevel):
    def __init__(self, parent, on_complete: Callable[[], None], countdown_seconds: int = 3):
        super().__init__(parent)
        self.on_complete = on_complete
        self.seconds_left = countdown_seconds
        
        self.title("Recording Starts In...")
        
        # Fullscreen and borderless
        self.attributes('-fullscreen', True)
        self.attributes('-topmost', True)
        
        # Transparent dark background
        self.attributes('-alpha', 0.6)
        
        self.canvas = tk.Canvas(self, bg="black", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        
        self.text_id = self.canvas.create_text(
            self.winfo_screenwidth() // 2, self.winfo_screenheight() // 2 - 50,
            text=str(self.seconds_left),
            fill="white", font=("SF Pro Display", 200, "bold"),
            justify="center"
        )
        
        self.sub_text_id = self.canvas.create_text(
            self.winfo_screenwidth() // 2, self.winfo_screenheight() // 2 + 100,
            text="Get ready! Recording will start automatically...",
            fill="#dddddd", font=("SF Pro Text", 36),
            justify="center"
        )
        
        # Force window to update before starting the timer to avoid white flashes
        self.update()
        
        # Start countdown
        self.after(1000, self._tick)
        
    def _tick(self):
        self.seconds_left -= 1
        if self.seconds_left > 0:
            self.canvas.itemconfig(self.text_id, text=str(self.seconds_left))
            self.after(1000, self._tick)
        else:
            self.canvas.itemconfig(self.text_id, text="REC", fill="#ff3333")
            self.canvas.itemconfig(self.sub_text_id, text="")
            self.update_idletasks()
            self.after(300, self._finish)
            
    def _finish(self):
        self.destroy()
        if self.on_complete:
            self.on_complete()
