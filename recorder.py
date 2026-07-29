import json
import time
import os
from pynput import mouse, keyboard
import mss
from PIL import Image

class Recorder:
    def __init__(self, output_file="workflow.json", templates_dir="templates"):
        self.output_file = output_file
        self.templates_dir = templates_dir
        self.actions = []
        self.start_time = None
        self.last_action_time = None
        
        self.mouse_listener = None
        self.keyboard_listener = None
        self.recording = False
        
        if not os.path.exists(self.templates_dir):
            os.makedirs(self.templates_dir)
            
        self.sct = mss.mss()
        
    def _get_time_offset(self):
        now = time.time()
        if self.last_action_time is None:
            self.last_action_time = now
            return 0.5 # Start with a small delay for the first action
        offset = now - self.last_action_time
        self.last_action_time = now
        return round(offset, 3)

    def _capture_template(self, x, y, size=60):
        # Capture a small box around the click
        monitor = {"top": int(y - size/2), "left": int(x - size/2), "width": size, "height": size}
        try:
            sct_img = self.sct.grab(monitor)
            img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
            timestamp = int(time.time() * 1000)
            filename = f"template_{timestamp}.png"
            filepath = os.path.join(self.templates_dir, filename)
            img.save(filepath)
            return filepath
        except Exception as e:
            print(f"Error capturing template: {e}")
            return None

    def on_click(self, x, y, button, pressed):
        if not self.recording or not pressed:
            return
            
        time_offset = self._get_time_offset()
        template_path = self._capture_template(x, y)
        
        action = {
            "type": "click",
            "button": button.name,
            "x": int(x),
            "y": int(y),
            "time_offset": time_offset,
            "template_image": template_path
        }
        self.actions.append(action)
        print(f"Recorded click at ({int(x)}, {int(y)})")

    def on_press(self, key):
        if not self.recording:
            return
            
        # Ignore F-keys used for control
        if key in [keyboard.Key.f9, keyboard.Key.f10, keyboard.Key.f11]:
            return
            
        time_offset = self._get_time_offset()
        
        try:
            key_name = key.char
        except AttributeError:
            key_name = str(key)
            
        action = {
            "type": "type",
            "key": key_name,
            "time_offset": time_offset
        }
        self.actions.append(action)
        print(f"Recorded key: {key_name}")

    def start(self):
        self.recording = True
        self.actions = []
        self.start_time = time.time()
        self.last_action_time = None
        print("Started recording... Do your actions now!")
        
        self.mouse_listener = mouse.Listener(on_click=self.on_click)
        self.keyboard_listener = keyboard.Listener(on_press=self.on_press)
        
        self.mouse_listener.start()
        self.keyboard_listener.start()

    def stop(self):
        if not self.recording:
            return
        self.recording = False
        print("Stopped recording.")
        if self.mouse_listener:
            self.mouse_listener.stop()
        if self.keyboard_listener:
            self.keyboard_listener.stop()
            
        self.save()

    def save(self):
        data = {
            "workflow_name": "recorded_workflow",
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "actions": self.actions
        }
        with open(self.output_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
        print(f"Workflow saved to {self.output_file}")
