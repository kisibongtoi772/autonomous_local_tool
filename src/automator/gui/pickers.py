
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
