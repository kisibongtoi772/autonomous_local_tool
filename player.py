import json
import time
import pyautogui
import os

# PyAutoGUI safety settings - move mouse to corner to abort
pyautogui.FAILSAFE = True

class Player:
    def __init__(self, workflow_file="workflow.json"):
        self.workflow_file = workflow_file
        
    def play(self):
        if not os.path.exists(self.workflow_file):
            print(f"Workflow file {self.workflow_file} not found.")
            return
            
        with open(self.workflow_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        actions = data.get("actions", [])
        print(f"Starting playback of {len(actions)} actions...")
        
        for action in actions:
            delay = action.get("time_offset", 0)
            time.sleep(delay)
            
            if action["type"] == "click":
                self._do_click(action)
            elif action["type"] == "type":
                self._do_type(action)
                
        print("Playback finished.")
        
    def _do_click(self, action):
        template_path = action.get("template_image")
        x, y = action.get("x"), action.get("y")
        button = action.get("button", "left")
        
        click_x, click_y = x, y
        
        if template_path and os.path.exists(template_path):
            try:
                # Try to locate the image on screen using OpenCV (confidence parameter)
                # This requires opencv-python installed
                location = pyautogui.locateCenterOnScreen(template_path, confidence=0.8)
                if location:
                    # On Mac Retina, pyautogui.locateCenterOnScreen might return logical coordinates
                    # or physical depending on pyscreeze. Usually, we can just click it directly.
                    click_x, click_y = location
                    print(f"Found template on screen at ({click_x}, {click_y})")
                else:
                    print(f"Template not found, falling back to original coordinates ({x}, {y})")
            except Exception as e:
                # If locateCenterOnScreen throws ImageNotFoundException or fails
                print(f"Template matching failed: {e}. Falling back to ({x}, {y})")
        else:
             print(f"No template available, using original coordinates ({x}, {y})")
             
        print(f"Clicking at ({click_x}, {click_y}) with {button} button")
        
        # On macOS, coordinates might need scaling if using dual monitor, but let's try direct first.
        # Also pyautogui sometimes struggles with right click on Mac without specific delays, but it's generally fine.
        try:
            pyautogui.click(x=click_x, y=click_y, button=button)
        except Exception as e:
            print(f"Error clicking: {e}")
        
    def _do_type(self, action):
        key = action.get("key")
        if not key:
            return
            
        print(f"Typing/Pressing: {key}")
        
        if key.startswith('Key.'):
            pyautogui_key = key.replace('Key.', '')
            try:
                pyautogui.press(pyautogui_key)
            except ValueError:
                print(f"Key {pyautogui_key} not supported by pyautogui.")
        else:
            # write handles a string of characters, press handles a single key like 'enter'
            # pynput character keys are often single chars (e.g., 'a', '1') but could be longer.
            # pyautogui.write simulates typing.
            try:
                if len(key) == 1:
                    pyautogui.write(key)
                else:
                    pyautogui.press(key)
            except Exception as e:
                print(f"Error typing: {e}")
