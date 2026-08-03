import os
import tkinter as tk
from typing import Callable, Optional
import pyautogui
from PIL import Image, ImageTk
import customtkinter as ctk
from ..utils.config import TEMPLATES_DIR
from ..utils.logger import get_logger

logger = get_logger(__name__)

class SnippingTool(ctk.CTkToplevel):
    def __init__(self, parent, on_capture: Callable[[str], None], on_cancel: Optional[Callable[[], None]] = None, force_filename: Optional[str] = None):
        super().__init__(parent)
        self.on_capture = on_capture
        self.on_cancel = on_cancel
        self.force_filename = force_filename
        self.title("Snipping Tool")
        
        # Take full screen capture
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
        
        # Selection rectangle
        self.rect = None
        self.start_x = None
        self.start_y = None
        
        # Instruction text
        self.canvas.create_text(
            self.winfo_screenwidth() // 2, 50,
            text="Click and drag to capture a template. Press ESC to cancel.",
            fill="white", font=("SF Pro Display", 24, "bold")
        )
        # Drop shadow for text readability
        self.canvas.create_text(
            self.winfo_screenwidth() // 2 + 2, 52,
            text="Click and drag to capture a template. Press ESC to cancel.",
            fill="black", font=("SF Pro Display", 24, "bold")
        )
        
        # Bindings
        self.canvas.bind("<Motion>", self.on_mouse_move)
        self.canvas.bind("<ButtonPress-1>", self.on_press)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        self.bind("<Escape>", self._cancel)

    def _cancel(self, event=None):
        self.destroy()
        if self.on_cancel:
            self.on_cancel()

    def on_press(self, event):
        self.start_x = event.x
        self.start_y = event.y
        if self.rect:
            self.canvas.delete(self.rect)
        self.rect = self.canvas.create_rectangle(
            self.start_x, self.start_y, self.start_x, self.start_y,
            outline="red", width=3
        )
        
    
    def on_mouse_move(self, event):
        self._update_magnifier(event.x, event.y)

    def on_drag(self, event):
        cur_x, cur_y = (event.x, event.y)
        self.canvas.coords(self.rect, self.start_x, self.start_y, cur_x, cur_y)
        
    def on_release(self, event):
        end_x, end_y = (event.x, event.y)
        
        x1 = min(self.start_x, end_x)
        y1 = min(self.start_y, end_y)
        x2 = max(self.start_x, end_x)
        y2 = max(self.start_y, end_y)
        
        self.destroy()
        
        # If selection is too small, ignore
        if (x2 - x1) < 5 or (y2 - y1) < 5:
            if self.on_cancel:
                self.on_cancel()
            return
            
        # Ensure coordinates are within image bounds
        x1 = max(0, x1)
        y1 = max(0, y1)
        x2 = min(self.screenshot.width, x2)
        y2 = min(self.screenshot.height, y2)
        
        cropped = self.screenshot.crop((x1, y1, x2, y2))
        self.prompt_save(cropped)

    def prompt_save(self, image: Image.Image):
        if self.force_filename:
            filename = self.force_filename
        else:
            dialog = ctk.CTkInputDialog(text="Enter filename for template (e.g. icon.png):", title="Save Template")
            filename = dialog.get_input()
            
        if filename:
            filename = filename.strip()
            if not filename.endswith(".png"):
                filename += ".png"
            os.makedirs(TEMPLATES_DIR, exist_ok=True)
            save_path = os.path.join(TEMPLATES_DIR, filename)
            image.save(save_path)
            logger.info(f"Template captured and saved to {save_path}")
            if self.on_capture:
                self.on_capture(filename)
        else:
            if self.on_cancel:
                self.on_cancel()


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
