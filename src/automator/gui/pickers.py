
class ConfidenceTuner(ctk.CTkToplevel):
    """
    Live Visual Tuner for Image Confidence.
    Takes a screenshot, and dynamically draws bounding boxes as the user drags the confidence slider.
    """
    def __init__(self, app, template_name: str, initial_conf: float, on_apply, on_cancel):
        super().__init__(app)
        self.app = app
        self.template_name = template_name
        self.on_apply = on_apply
        self.on_cancel = on_cancel
        self.title("Live Confidence Tuner")
        
        # Make it full screen or large enough
        w, h = self.winfo_screenwidth() - 100, self.winfo_screenheight() - 100
        self.geometry(f"{w}x{h}+50+50")
        self.protocol("WM_DELETE_WINDOW", self._cancel)
        self.attributes("-topmost", True)
        self.focus_force()
        
        # Layout
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)
        
        # Header
        hdr = ctk.CTkFrame(self, fg_color=T["surface"], height=60, corner_radius=0)
        hdr.grid(row=0, column=0, sticky="ew")
        hdr.grid_columnconfigure(1, weight=1)
        
        from .components import _label, _btn
        _label(hdr, f"Tuning: {template_name}", size=14, colour=T["text"], weight="bold").grid(row=0, column=0, padx=20, pady=16, sticky="w")
        
        # Controls
        ctrl = ctk.CTkFrame(hdr, fg_color="transparent")
        ctrl.grid(row=0, column=1, sticky="e", padx=20)
        
        _label(ctrl, "Confidence:", size=12, colour=T["dim"]).pack(side="left", padx=10)
        self.val_lbl = _label(ctrl, f"{initial_conf:.2f}", size=12, colour=T["accent"], weight="bold", width=40)
        self.val_lbl.pack(side="left", padx=(0, 10))
        
        self.slider = ctk.CTkSlider(ctrl, from_=0.1, to=1.0, number_of_steps=90, width=200, command=self._on_slide)
        self.slider.set(initial_conf)
        self.slider.pack(side="left", padx=10)
        
        _btn(ctrl, "Cancel", self._cancel, fg_color="transparent", border_width=1, border_color=T["border"]).pack(side="left", padx=(20, 10))
        _btn(ctrl, "Apply", self._apply, primary=True).pack(side="left")
        
        # Canvas for Image
        self.canvas = tk.Canvas(self, bg=T["bg"], highlightthickness=0)
        self.canvas.grid(row=1, column=0, sticky="nsew", padx=20, pady=20)
        
        # Status Label
        self.status = _label(self, "Initializing...", size=11, colour=T["warn"])
        self.status.grid(row=2, column=0, pady=(0, 10))
        
        # Load Image in background to not block UI
        import threading
        threading.Thread(target=self._init_cv, daemon=True).start()

    def _init_cv(self):
        try:
            import pyautogui
            import cv2
            import numpy as np
            from PIL import Image, ImageTk
            import os
            from ..utils.config import TEMPLATES_DIR
            
            tpl_path = os.path.join(TEMPLATES_DIR, self.template_name)
            if not os.path.exists(tpl_path):
                self.after(0, lambda: self.status.configure(text=f"Template not found: {tpl_path}", text_color="#EF4444"))
                return
                
            self.after(0, lambda: self.status.configure(text="Capturing screen...", text_color=T["dim"]))
            
            # Take full screenshot
            self.screenshot = pyautogui.screenshot()
            self.screenshot_cv = cv2.cvtColor(np.array(self.screenshot), cv2.COLOR_RGB2BGR)
            
            # Load template
            self.template_cv = cv2.imread(tpl_path)
            self.tw, self.th = self.template_cv.shape[1], self.template_cv.shape[0]
            
            self.after(0, lambda: self.status.configure(text="Drawing preview...", text_color=T["dim"]))
            
            # Resize screenshot to fit canvas
            cw = self.winfo_screenwidth() - 140
            ch = self.winfo_screenheight() - 200
            
            sw, sh = self.screenshot.size
            self.scale = min(cw/sw, ch/sh)
            
            # Create PhotoImage
            new_w, new_h = int(sw * self.scale), int(sh * self.scale)
            resized = self.screenshot.resize((new_w, new_h), Image.Resampling.LANCZOS)
            self.tk_img = ImageTk.PhotoImage(resized)
            
            self.after(0, self._render_initial)
        except Exception as e:
            self.after(0, lambda: self.status.configure(text=f"Error: {e}", text_color="#EF4444"))

    def _render_initial(self):
        self.canvas.create_image(0, 0, anchor="nw", image=self.tk_img)
        self.canvas.config(scrollregion=self.canvas.bbox("all"))
        self._on_slide(self.slider.get())
        
    def _on_slide(self, val):
        self.val_lbl.configure(text=f"{val:.2f}")
        # Run matching in background
        if hasattr(self, 'screenshot_cv'):
            import threading
            threading.Thread(target=self._do_match, args=(val,), daemon=True).start()
            
    def _do_match(self, confidence):
        try:
            import cv2
            import numpy as np
            
            res = cv2.matchTemplate(self.screenshot_cv, self.template_cv, cv2.TM_CCOEFF_NORMED)
            loc = np.where(res >= confidence)
            
            matches = []
            # Apply NMS (Non-Maximum Suppression) simplified
            for pt in zip(*loc[::-1]):
                matches.append(pt)
                
            self.after(0, lambda: self._draw_matches(matches, confidence))
        except Exception:
            pass
            
    def _draw_matches(self, matches, confidence):
        self.canvas.delete("match_box")
        drawn = 0
        
        # Simple NMS to avoid drawing 1000 boxes
        filtered = []
        for pt in matches:
            overlap = False
            for fpt in filtered:
                if abs(pt[0] - fpt[0]) < self.tw/2 and abs(pt[1] - fpt[1]) < self.th/2:
                    overlap = True
                    break
            if not overlap:
                filtered.append(pt)
                
        for pt in filtered:
            x1 = int(pt[0] * self.scale)
            y1 = int(pt[1] * self.scale)
            x2 = int((pt[0] + self.tw) * self.scale)
            y2 = int((pt[1] + self.th) * self.scale)
            self.canvas.create_rectangle(x1, y1, x2, y2, outline="#EF4444", width=3, tags="match_box")
            drawn += 1
            
        color = T["ok"] if drawn > 0 else T["warn"]
        text = f"Found {drawn} match(es) at {confidence:.2f} confidence."
        self.status.configure(text=text, text_color=color)

    def _apply(self):
        val = self.slider.get()
        self.destroy()
        self.on_apply(val)

    def _cancel(self):
        self.destroy()
        self.on_cancel()

class ScreenLocator(ctk.CTkToplevel):
    """
    Live X-Ray Screen Locator.
    Takes a template and confidence, searches the screen, and draws a red box at the exact location
    directly over the screen (transparent window) for 2 seconds.
    """
    def __init__(self, app, template_name: str, confidence: float, on_close):
        super().__init__(app)
        self.app = app
        self.on_close = on_close
        
        # Hide window initially
        self.withdraw()
        
        import threading
        threading.Thread(target=self._locate, args=(template_name, confidence), daemon=True).start()
        
    def _locate(self, template_name, confidence):
        try:
            import os
            from ..utils.config import TEMPLATES_DIR
            from ..core.vision import locate_template
            
            tpl_path = os.path.join(TEMPLATES_DIR, template_name)
            if not os.path.exists(tpl_path):
                self.after(0, self._fail, "Template not found")
                return
                
            x, y, w, h, val = locate_template(tpl_path, confidence)
            if x is not None:
                self.after(0, self._show_highlight, x, y, w, h, val)
            else:
                self.after(0, self._fail, f"Not found at {confidence:.2f} confidence")
                
        except Exception as e:
            self.after(0, self._fail, str(e))
            
    def _fail(self, msg):
        self.app.show_toast(f"❌ {msg}", "#EF4444")
        self.on_close()
        self.destroy()
        
    def _show_highlight(self, x, y, w, h, val):
        self.title("X-Ray")
        self.geometry(f"{w+8}x{h+8}+{x-4}+{y-4}")
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        
        import platform
        if platform.system() == "Windows":
            self.attributes("-transparentcolor", "black")
            self.configure(fg_color="black")
            canvas = tk.Canvas(self, bg="black", highlightthickness=0)
            canvas.pack(fill="both", expand=True)
            canvas.create_rectangle(2, 2, w+6, h+6, outline="#EF4444", width=4)
        else: # Mac/Linux
            self.attributes("-transparent", True)
            self.configure(fg_color="systemTransparent")
            canvas = tk.Canvas(self, bg="systemTransparent", highlightthickness=0)
            canvas.pack(fill="both", expand=True)
            canvas.create_rectangle(2, 2, w+6, h+6, outline="#EF4444", width=4)
            
        self.app.show_toast(f"🎯 Found at ({x}, {y}) [Conf: {val:.2f}]", "#10B981")
        self.deiconify()
        
        # Destroy after 2 seconds
        self.after(2000, self._close)
        
    def _close(self):
        self.on_close()
        self.destroy()

class RegionPicker(ctk.CTkToplevel):
    """Translucent overlay to select a screen region. Returns (x, y, w, h)."""
    def __init__(self, parent, on_complete):
        super().__init__(parent)
        self.on_complete = on_complete
        self.title("Select Region")
        
        self.attributes('-fullscreen', True)
        self.attributes('-topmost', True)
        self.overrideredirect(True)
        self.configure(cursor="cross")
        
        try:
            self.attributes('-alpha', 0.3)
            self.config(bg="black")
            canvas_bg = "black"
        except Exception:
            self.attributes("-alpha", 0.3)
            canvas_bg = "black"
            
        self.canvas = tk.Canvas(self, bg=canvas_bg, highlightthickness=0, cursor="cross")
        self.canvas.pack(fill="both", expand=True)
        
        self.start_x = None
        self.start_y = None
        self.rect = None
        
        # Instruction text
        self.canvas.create_text(
            self.winfo_screenwidth()//2, 50,
            text="Click and drag to select region. Press ESC to cancel.",
            fill="white", font=("Arial", 24, "bold")
        )
        
        self.canvas.bind("<ButtonPress-1>", self.on_press)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        self.bind("<Escape>", lambda e: self.cancel())
        
    def on_press(self, event):
        self.start_x = event.x
        self.start_y = event.y
        if self.rect:
            self.canvas.delete(self.rect)
        self.rect = self.canvas.create_rectangle(
            self.start_x, self.start_y, self.start_x, self.start_y,
            outline="#10B981", width=3, fill="#047857", stipple="gray25"
        )
        
    def on_drag(self, event):
        if self.rect:
            self.canvas.coords(self.rect, self.start_x, self.start_y, event.x, event.y)
            
    def on_release(self, event):
        if self.start_x is None: return
        x1, y1 = min(self.start_x, event.x), min(self.start_y, event.y)
        x2, y2 = max(self.start_x, event.x), max(self.start_y, event.y)
        
        w = x2 - x1
        h = y2 - y1
        
        self.destroy()
        if w > 10 and h > 10:
            self.on_complete([x1, y1, w, h])
        else:
            self.on_complete(None)
            
    def cancel(self):
        self.destroy()
        self.on_complete(None)



class ColorPicker(ctk.CTkToplevel):
    def __init__(self, parent, on_complete, on_cancel):
        super().__init__(parent)
        self.on_complete = on_complete
        self.on_cancel = on_cancel
        self.title("Pick Color")
        
        self.attributes('-fullscreen', True)
        self.attributes('-topmost', True)
        self.overrideredirect(True)
        self.configure(cursor="cross")
        
        try:
            self.attributes('-alpha', 0.3)
            self.config(bg="black")
            canvas_bg = "black"
        except Exception:
            self.attributes("-alpha", 0.3)
            canvas_bg = "black"
            
        self.canvas = tk.Canvas(self, bg=canvas_bg, highlightthickness=0, cursor="cross")
        self.canvas.pack(fill="both", expand=True)
        
        self.canvas.create_text(
            self.winfo_screenwidth()//2, 50,
            text="Click anywhere to pick a color. Press ESC to cancel.",
            fill="white", font=("Arial", 24, "bold")
        )
        
        self.bind("<ButtonRelease-1>", self.on_click)
        self.bind("<Escape>", lambda e: self.cancel())
        
    def on_click(self, event):
        x, y = event.x_root, event.y_root
        import pyautogui
        try:
            r, g, b = pyautogui.pixel(x, y)
            hex_color = f"#{r:02x}{g:02x}{b:02x}".upper()
        except Exception:
            hex_color = "#000000"
        self.destroy()
        self.on_complete(x, y, hex_color)
        
    def cancel(self):
        self.destroy()
        self.on_cancel()
