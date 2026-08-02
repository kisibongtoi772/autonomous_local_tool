import os
import tkinter as tk
import customtkinter as ctk
from PIL import Image, ImageTk
from typing import Callable

from ..utils.config import T
from ..utils.logger import get_logger

logger = get_logger(__name__)

class TemplateCropper(ctk.CTkToplevel):
    def __init__(self, parent, image_path: str, on_save: Callable[[], None]):
        super().__init__(parent)
        self.image_path = image_path
        self.on_save = on_save
        
        self.title("Crop Template")
        self.geometry("800x600")
        self.transient(parent)
        self.grab_set()
        self.configure(fg_color=T["bg"])
        
        # Header
        hdr = ctk.CTkFrame(self, fg_color="transparent")
        hdr.pack(fill="x", padx=16, pady=(16, 8))
        ctk.CTkLabel(
            hdr, text="Crop Template",
            font=ctk.CTkFont("SF Pro Display", 18, "bold"), text_color=T["text"]
        ).pack(side="left")
        ctk.CTkLabel(
            hdr, text="Drag to select the region to keep.",
            font=ctk.CTkFont("SF Pro Text", 12), text_color=T["dim"]
        ).pack(side="left", padx=16)
        
        # Canvas Frame
        self.canvas_frame = ctk.CTkFrame(self, fg_color=T["raised"])
        self.canvas_frame.pack(fill="both", expand=True, padx=16, pady=8)
        
        self.canvas = tk.Canvas(self.canvas_frame, bg="#1E1E1E", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        
        # Load Image
        try:
            self.original_image = Image.open(image_path).convert("RGB")
        except Exception as e:
            logger.error(f"Cannot open image to crop: {e}")
            self.destroy()
            return
            
        self.img_tk = ImageTk.PhotoImage(self.original_image)
        self.canvas.create_image(0, 0, image=self.img_tk, anchor="nw", tags="image")
        
        # Selection Variables
        self.start_x = 0
        self.start_y = 0
        self.rect_id = None
        self.crop_box = None
        
        self.canvas.bind("<ButtonPress-1>", self._on_press)
        self.canvas.bind("<B1-Motion>", self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)
        
        # Footer
        ftr = ctk.CTkFrame(self, fg_color="transparent")
        ftr.pack(fill="x", padx=16, pady=(8, 16))
        
        ctk.CTkButton(
            ftr, text="Cancel", width=100, height=36,
            fg_color="transparent", hover_color=T["hover"], text_color=T["text"],
            border_width=1, border_color=T["border"],
            command=self.destroy
        ).pack(side="right", padx=(8, 0))
        
        self.save_btn = ctk.CTkButton(
            ftr, text="Crop & Save", width=120, height=36,
            fg_color=T["accent"], hover_color=T["hover"], text_color=T["bg"],
            font=ctk.CTkFont(weight="bold"), state="disabled",
            command=self._save
        )
        self.save_btn.pack(side="right")
        
    def _on_press(self, event):
        self.start_x = event.x
        self.start_y = event.y
        if self.rect_id:
            self.canvas.delete(self.rect_id)
        self.rect_id = self.canvas.create_rectangle(
            self.start_x, self.start_y, self.start_x, self.start_y,
            outline="#FF3B30", width=2, dash=(4, 4)
        )
        self.crop_box = None
        self.save_btn.configure(state="disabled")
        
    def _on_drag(self, event):
        if self.rect_id:
            x = max(0, min(event.x, self.original_image.width))
            y = max(0, min(event.y, self.original_image.height))
            self.canvas.coords(self.rect_id, self.start_x, self.start_y, x, y)
            
    def _on_release(self, event):
        if self.rect_id:
            x0 = min(self.start_x, event.x)
            y0 = min(self.start_y, event.y)
            x1 = max(self.start_x, event.x)
            y1 = max(self.start_y, event.y)
            
            # Constrain to image bounds
            x0 = max(0, x0)
            y0 = max(0, y0)
            x1 = min(self.original_image.width, x1)
            y1 = min(self.original_image.height, y1)
            
            if x1 - x0 > 10 and y1 - y0 > 10:
                self.crop_box = (x0, y0, x1, y1)
                self.save_btn.configure(state="normal")
                # Make solid red box
                self.canvas.itemconfig(self.rect_id, dash=(), outline="#34C759", width=3)
            else:
                self.canvas.delete(self.rect_id)
                self.rect_id = None
                
    def _save(self):
        if self.crop_box:
            try:
                cropped = self.original_image.crop(self.crop_box)
                cropped.save(self.image_path)
                logger.info(f"Cropped template saved: {self.image_path}")
                if self.on_save:
                    self.on_save()
            except Exception as e:
                logger.error(f"Error saving cropped image: {e}")
        self.destroy()
