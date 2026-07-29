import json
import time
import os
import pyautogui
from pydantic import ValidationError

from ..models.workflow import Workflow, ClickAction, TypeAction
from ..utils.logger import get_logger
from ..utils.config import WORKFLOW_FILE
from .vision import locate_template

logger = get_logger(__name__)

pyautogui.FAILSAFE = True

class Player:
    def __init__(self):
        self.workflow_file = WORKFLOW_FILE
        
    def play(self):
        if not os.path.exists(self.workflow_file):
            logger.error(f"Workflow file {self.workflow_file} not found.")
            return
            
        try:
            with open(self.workflow_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            workflow = Workflow.model_validate(data)
        except ValidationError as e:
            logger.error(f"Invalid workflow format: {e}")
            return
        except Exception as e:
            logger.error(f"Error reading workflow: {e}")
            return
            
        logger.info(f"Starting playback of {len(workflow.actions)} actions...")
        
        for action in workflow.actions:
            time.sleep(action.time_offset)
            
            if isinstance(action, ClickAction):
                self._do_click(action)
            elif isinstance(action, TypeAction):
                self._do_type(action)
                
        logger.info("Playback finished.")
        
    def _do_click(self, action: ClickAction):
        click_x, click_y = action.x, action.y
        
        if action.template_image:
            location = locate_template(action.template_image)
            if location:
                click_x, click_y = location
                logger.info(f"Found template on screen at ({click_x}, {click_y})")
            else:
                logger.warning(f"Template not found, falling back to ({action.x}, {action.y})")
                
        logger.info(f"Clicking at ({click_x}, {click_y}) with {action.button} button")
        try:
            pyautogui.click(x=click_x, y=click_y, button=action.button)
        except Exception as e:
            logger.error(f"Error clicking: {e}")
            
    def _do_type(self, action: TypeAction):
        key = action.key
        logger.info(f"Typing/Pressing: {key}")
        
        if key.startswith('Key.'):
            pyautogui_key = key.replace('Key.', '')
            try:
                pyautogui.press(pyautogui_key)
            except ValueError:
                logger.error(f"Key {pyautogui_key} not supported by pyautogui.")
        else:
            try:
                if len(key) == 1:
                    pyautogui.write(key)
                else:
                    pyautogui.press(key)
            except Exception as e:
                logger.error(f"Error typing: {e}")
