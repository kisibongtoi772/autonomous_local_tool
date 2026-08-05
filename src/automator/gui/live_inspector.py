import customtkinter as ctk
import pyautogui
from PIL import ImageGrab
import platform

class LiveInspector(ctk.CTkToplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Live Inspector")
        self.geometry("200x120+50+50")
        
        self.attributes("-topmost", True)
        # Attempt to make it borderless if desired
        try:
            if platform.system() == "Windows":
                self.overrideredirect(True)
        except:
            pass
            
        self.configure(fg_color="#0A0C10")
        
        self.is_running = True
        
        # Border Frame
        border = ctk.CTkFrame(self, fg_color="#3A3F4A", corner_radius=8)
        border.pack(fill="both", expand=True, padx=2, pady=2)
        
        inner = ctk.CTkFrame(border, fg_color="#181C22", corner_radius=6)
        inner.pack(fill="both", expand=True, padx=2, pady=2)
        
        # Header (Drag handle if borderless)
        header = ctk.CTkFrame(inner, fg_color="transparent", height=24)
        header.pack(fill="x", pady=(2, 0))
        header.pack_propagate(False)
        
        title = ctk.CTkLabel(header, text="🔍 Live Inspector", font=ctk.CTkFont("SF Pro Text", 12, "bold"), text_color="#D1D5DB")
        title.pack(side="left", padx=8)
        
        close_btn = ctk.CTkButton(header, text="✕", width=20, height=20, fg_color="transparent", hover_color="#7F1D1D", text_color="#9CA3AF", command=self.close)
        close_btn.pack(side="right", padx=4)
        
        # Make draggable
        def start_move(event):
            self.x = event.x
            self.y = event.y
        def stop_move(event):
            self.x = None
            self.y = None
        def do_move(event):
            deltax = event.x - self.x
            deltay = event.y - self.y
            x = self.winfo_x() + deltax
            y = self.winfo_y() + deltay
            self.geometry(f"+{x}+{y}")

        for w in (header, title):
            w.bind("<ButtonPress-1>", start_move)
            w.bind("<ButtonRelease-1>", stop_move)
            w.bind("<B1-Motion>", do_move)
            
        # Data Display
        self.coord_lbl = ctk.CTkLabel(inner, text="X: 0, Y: 0", font=ctk.CTkFont("SF Pro Text", 16, "bold"), text_color="white")
        self.coord_lbl.pack(anchor="w", padx=12, pady=(10, 0))
        
        self.color_box = ctk.CTkFrame(inner, width=16, height=16, corner_radius=4, fg_color="#000000", border_width=1, border_color="gray")
        self.color_box.pack(side="left", padx=(12, 6), pady=(5, 12))
        
        self.color_lbl = ctk.CTkLabel(inner, text="HEX: #000000", font=ctk.CTkFont("SF Pro Text", 13), text_color="#A1A1AA")
        self.color_lbl.pack(side="left", pady=(5, 12))
        
        self.protocol("WM_DELETE_WINDOW", self.close)
        self.update_loop()

    def update_loop(self):
        if not self.is_running:
            return
            
        try:
            # 1. Get Mouse Pos
            x, y = pyautogui.position()
            self.coord_lbl.configure(text=f"X: {x}, Y: {y}")
            
            # 2. Get Pixel Color (Throttle this as it can be heavy)
            # ImageGrab on macOS can be slow for single pixels, use a small bbox
            # Bounding box is (left, top, right, bottom)
            # Make sure it stays within bounds
            try:
                screen_width, screen_height = pyautogui.size()
                if 0 <= x < screen_width and 0 <= y < screen_height:
                    img = ImageGrab.grab(bbox=(x, y, x+1, y+1))
                    rgb = img.getpixel((0, 0))
                    hex_color = "#{:02x}{:02x}{:02x}".format(rgb[0], rgb[1], rgb[2]).upper()
                    self.color_lbl.configure(text=f"HEX: {hex_color}  RGB: {rgb}")
                    self.color_box.configure(fg_color=hex_color)
            except Exception as e:
                pass # Ignore grab errors (e.g. edge of screen, permissions)
        except Exception:
            pass
            
        self.after(150, self.update_loop)
        
    def close(self):
        self.is_running = False
        self.destroy()

