import time
import os
from typing import List, Union
from pynput import mouse, keyboard
import mss
from PIL import Image

from ..models.workflow import Workflow, ClickAction, TypeAction, ActionType
from ..utils.logger import get_logger
from ..utils.config import TEMPLATES_DIR, TEMPLATE_SIZE, WORKFLOW_FILE

logger = get_logger(__name__)

class Recorder:
    def __init__(self, workflow_path=None):
        self.workflow_path = workflow_path or WORKFLOW_FILE
        self.actions: List[ActionType] = []
        self.start_time = None
        self.last_action_time = None
        self.recording = False
        
        self.mouse_listener = None
        self.keyboard_listener = None
        
        if not os.path.exists(TEMPLATES_DIR):
            os.makedirs(TEMPLATES_DIR)
            
        self.sct = mss.mss()
        
    def _get_time_offset(self) -> float:
        now = time.time()
        if self.last_action_time is None:
            self.last_action_time = now
            return 0.5
        offset = now - self.last_action_time
        self.last_action_time = now
        return round(offset, 3)

    def _capture_template(self, x: float, y: float) -> str:
        size = TEMPLATE_SIZE
        monitor = {"top": int(y - size/2), "left": int(x - size/2), "width": size, "height": size}
        try:
            sct_img = self.sct.grab(monitor)
            img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
            timestamp = int(time.time() * 1000)
            filename = f"template_{timestamp}.png"
            filepath = os.path.join(TEMPLATES_DIR, filename)
            img.save(filepath)
            return filepath
        except Exception as e:
            logger.error(f"Error capturing template: {e}")
            return ""

    def on_click(self, x, y, button, pressed):
        if not self.recording or not pressed:
            return
            
        time_offset = self._get_time_offset()
        template_path = self._capture_template(x, y)
        
        action = ClickAction(
            type="click",
            button=button.name,
            x=int(x),
            y=int(y),
            time_offset=time_offset,
            template_image=template_path if template_path else None
        )
        self.actions.append(action)
        logger.info(f"Recorded click at ({int(x)}, {int(y)})")

    def on_press(self, key):
        if not self.recording:
            return
            
        if key in [keyboard.Key.f9, keyboard.Key.f10, keyboard.Key.f11]:
            return
            
        time_offset = self._get_time_offset()
        try:
            key_name = key.char
        except AttributeError:
            key_name = str(key)
            
        action = TypeAction(
            type="type",
            key=key_name,
            time_offset=time_offset
        )
        self.actions.append(action)
        logger.info(f"Recorded key: {key_name}")

    def start(self):
        self.recording = True
        self.actions = []
        self.start_time = time.time()
        self.last_action_time = None
        logger.info("Started recording... Do your actions now!")

    def stop(self, save: bool = True):
        if not self.recording:
            return
        self.recording = False
        logger.info("Stopped recording.")
        if save:
            self.save()

    def save(self):
        workflow = Workflow(
            workflow_name=os.path.basename(self.workflow_path).replace(".json", ""),
            created_at=time.strftime("%Y-%m-%dT%H:%M:%S"),
            actions=self.actions
        )
        with open(self.workflow_path, 'w', encoding='utf-8') as f:
            f.write(workflow.model_dump_json(indent=2))
        logger.info(f"Workflow saved to {self.workflow_path}")
