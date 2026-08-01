import tkinter as tk
from pynput import keyboard
import customtkinter as ctk

class HotkeyPicker(ctk.CTkToplevel):
    def __init__(self, parent, on_capture, on_cancel):
        super().__init__(parent)
        self.on_capture = on_capture
        self.on_cancel = on_cancel
        self.keys_pressed = set()
        self.key_names = []
        
        self.title("Hotkey Recorder")
        self.attributes('-fullscreen', True)
        self.attributes('-topmost', True)
        
        try:
            self.attributes("-alpha", 0.85)
        except Exception:
            pass
            
        self.configure(fg_color="#1a1a1a")
        
        self.label = ctk.CTkLabel(
            self, text="Press a hotkey combination (e.g., Cmd + C)\n\nRelease all keys to save.\nPress ESC to cancel.",
            font=ctk.CTkFont("SF Pro Display", 28), text_color="white", justify="center"
        )
        self.label.place(relx=0.5, rely=0.5, anchor="center")
        
        # Start keyboard listener
        self.listener = keyboard.Listener(on_press=self.on_press, on_release=self.on_release)
        self.listener.start()
        
    def _normalize_key(self, key):
        """Normalize pynput keys to pyautogui style keys"""
        if hasattr(key, 'name'):
            name = key.name
            if name in ('cmd_r', 'cmd_l', 'cmd'): return 'cmd'
            if name in ('ctrl_r', 'ctrl_l', 'ctrl'): return 'ctrl'
            if name in ('shift_r', 'shift_l', 'shift'): return 'shift'
            if name in ('alt_r', 'alt_l', 'alt', 'option'): return 'alt'
            return name
        elif hasattr(key, 'char') and key.char:
            return key.char.lower()
        else:
            return str(key).replace("'", "").replace("Key.", "")

    def on_press(self, key):
        name = self._normalize_key(key)
        # Avoid duplicate modifiers if held down
        if name not in self.key_names:
            self.key_names.append(name)
        self.keys_pressed.add(name)
        
        display_text = " + ".join([k.upper() for k in self.key_names])
        self.label.configure(text=f"Captured:\n\n{display_text}\n\n\nRelease all keys to finish.")
        
    def on_release(self, key):
        name = self._normalize_key(key)
        if name in self.keys_pressed:
            self.keys_pressed.remove(name)
            
        if name == "esc":
            self.after(0, self.cancel)
            return False
            
        # If all physical keys are released and we have captured something
        if len(self.keys_pressed) == 0 and len(self.key_names) > 0:
            combo = ",".join(self.key_names)
            self.after(0, lambda: self.finish(combo))
            return False # stop listener
            
    def finish(self, combo):
        self.listener.stop()
        self.destroy()
        self.on_capture(combo)
        
    def cancel(self):
        self.listener.stop()
        self.destroy()
        self.on_cancel()
