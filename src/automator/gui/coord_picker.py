import tkinter as tk
from typing import Callable, Optional
import pyautogui
from PIL import ImageTk
import customtkinter as ctk

class CoordinatePicker(ctk.CTkToplevel):
    def __init__(self, parent, on_pick: Callable[[int, int], None], on_cancel: Optional[Callable[[], None]] = None):
        super().__init__(parent)
        self.on_pick = on_pick
        self.on_cancel = on_cancel
        self.title("Coordinate Picker")
        
        # Take full screen capture to use as background
        self.screenshot = pyautogui.screenshot()
        self.photo = ImageTk.PhotoImage(self.screenshot)
        
        # Make fullscreen and borderless
        self.attributes('-fullscreen', True)
        self.attributes('-topmost', True)
        self.configure(cursor="crosshair")
        
        # Setup Canvas
        self.canvas = tk.Canvas(self, cursor="crosshair", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        self.canvas.create_image(0, 0, image=self.photo, anchor="nw")
        
        # Create crosshair lines
        self.vline = self.canvas.create_line(0, 0, 0, 0, fill="red", dash=(4, 4), width=2)
        self.hline = self.canvas.create_line(0, 0, 0, 0, fill="red", dash=(4, 4), width=2)
        
        # Create drop shadow text for readability against any background
        self.shadow_text = self.canvas.create_text(0, 0, text="", fill="black", font=("SF Pro Display", 24, "bold"), anchor="nw")
        self.coord_text = self.canvas.create_text(0, 0, text="", fill="#ff3333", font=("SF Pro Display", 24, "bold"), anchor="nw")
        
        # Instruction text
        self.canvas.create_text(
            self.winfo_screenwidth() // 2, 50,
            text="Move mouse to see coordinates. Click to select. ESC to cancel.",
            fill="black", font=("SF Pro Display", 24, "bold")
        )
        self.canvas.create_text(
            self.winfo_screenwidth() // 2 - 2, 48,
            text="Move mouse to see coordinates. Click to select. ESC to cancel.",
            fill="white", font=("SF Pro Display", 24, "bold")
        )
        
        # Bindings
        self.canvas.bind("<Motion>", self.on_mouse_move)
        self.canvas.bind("<ButtonRelease-1>", self.on_click)
        self.bind("<Escape>", self._cancel)

    def _cancel(self, event=None):
        self.destroy()
        if self.on_cancel:
            self.on_cancel()

    def _get_hex_color(self, x, y):
        try:
            # Pillow image getpixel returns (r, g, b) or (r, g, b, a)
            pixel = self.screenshot.getpixel((x, y))
            return f"#{pixel[0]:02X}{pixel[1]:02X}{pixel[2]:02X}"
        except Exception:
            return "#000000"

    def on_mouse_move(self, event):
        x, y = event.x, event.y
        w = self.winfo_screenwidth()
        h = self.winfo_screenheight()
        
        # Update crosshair
        self.canvas.coords(self.vline, x, 0, x, h)
        self.canvas.coords(self.hline, 0, y, w, y)
        
        # Keep text within bounds
        text_x = x + 20
        text_y = y + 20
        if text_x > w - 150:
            text_x = x - 150
        if text_y > h - 80:
            text_y = y - 80
            
        hex_col = self._get_hex_color(x, y)
        coord_str = f"X: {x}\nY: {y}\nC: {hex_col}"
        self.canvas.coords(self.shadow_text, text_x + 2, text_y + 2)
        self.canvas.itemconfig(self.shadow_text, text=coord_str)
        
        self.canvas.coords(self.coord_text, text_x, text_y)
        self.canvas.itemconfig(self.coord_text, text=coord_str, fill=hex_col if hex_col != "#000000" else "#FFFFFF")

    def on_click(self, event):
        x, y = event.x, event.y
        hex_col = self._get_hex_color(x, y)
        self.destroy()
        if self.on_pick:
            self.on_pick(x, y, hex_col)
