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


    def _update_magnifier(self, x, y):
        zoom = 4
        size = 120
        src_size = size // zoom
        
        x1 = max(0, x - src_size // 2)
        y1 = max(0, y - src_size // 2)
        x2 = min(self.screenshot.width, x1 + src_size)
        y2 = min(self.screenshot.height, y1 + src_size)
        
        from PIL import Image, ImageTk
        crop = self.screenshot.crop((x1, y1, x2, y2))
        if crop.size[0] < src_size or crop.size[1] < src_size:
            bg = Image.new('RGB', (src_size, src_size), (0, 0, 0))
            bg.paste(crop, (0, 0))
            crop = bg
            
        mag_img = crop.resize((size, size), Image.NEAREST)
        self.mag_photo = ImageTk.PhotoImage(mag_img)
        
        mag_x = x + 30
        mag_y = y + 30
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        if mag_x + size > sw:
            mag_x = x - size - 30
        if mag_y + size > sh:
            mag_y = y - size - 30
            
        if not hasattr(self, 'mag_canvas_item'):
            self.mag_canvas_item = self.canvas.create_image(mag_x, mag_y, image=self.mag_photo, anchor="nw")
            cx = mag_x + size // 2
            cy = mag_y + size // 2
            self.mag_cross_v = self.canvas.create_line(cx, mag_y, cx, mag_y + size, fill="#ff3333", width=1)
            self.mag_cross_h = self.canvas.create_line(mag_x, cy, mag_x + size, cy, fill="#ff3333", width=1)
            self.mag_rect = self.canvas.create_rectangle(mag_x, mag_y, mag_x + size, mag_y + size, outline="#333333", width=2)
        else:
            self.canvas.coords(self.mag_canvas_item, mag_x, mag_y)
            self.canvas.itemconfig(self.mag_canvas_item, image=self.mag_photo)
            cx = mag_x + size // 2
            cy = mag_y + size // 2
            self.canvas.coords(self.mag_cross_v, cx, mag_y, cx, mag_y + size)
            self.canvas.coords(self.mag_cross_h, mag_x, cy, mag_x + size, cy)
            self.canvas.coords(self.mag_rect, mag_x, mag_y, mag_x + size, mag_y + size)
            
            self.canvas.tag_raise(self.mag_canvas_item)
            self.canvas.tag_raise(self.mag_cross_v)
            self.canvas.tag_raise(self.mag_cross_h)
            self.canvas.tag_raise(self.mag_rect)
            
            # also raise text shadows to be on top of magnifier
            if hasattr(self, "shadow_text"):
                self.canvas.tag_raise(self.shadow_text)
                self.canvas.tag_raise(self.coord_text)
