import json
import time
import os
import pyautogui
from pydantic import ValidationError

import subprocess
from ..models.workflow import Workflow, ClickAction, TypeAction, LoopAction, RunCommandAction, HotkeyAction, SleepAction, ScrollAction, ScreenshotAction, AssertTemplateAction, ActionType
from ..utils.logger import get_logger
from ..utils.config import WORKFLOW_FILE, TEMPLATES_DIR
from .vision import locate_template

logger = get_logger(__name__)

pyautogui.FAILSAFE = True

class Player:
    def __init__(self, workflow_path=None):
        self.workflow_path = workflow_path or WORKFLOW_FILE
        self.workflow: Optional[Workflow] = None
        
    def play(self) -> bool:
        if not os.path.exists(self.workflow_path):
            logger.error(f"Workflow file not found: {self.workflow_path}")
            return False
            
        try:
            with open(self.workflow_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            self.workflow = Workflow.model_validate(data)
            return True
        except ValidationError as e:
            logger.error(f"Invalid workflow format: {e}")
            return False
        except Exception as e:
            logger.error(f"Error reading workflow: {e}")
            return
            
        logger.info(f"Starting playback of {len(self.workflow.actions)} actions...")
        self._play_actions(self.workflow.actions)
        logger.info("Playback finished.")
        
    def play_single_action(self, action_dict: dict):
        """Helper to test a single action dictionary without loading a file."""
        try:
            workflow = Workflow.model_validate({"workflow_name": "temp", "actions": [action_dict]})
            logger.info("Testing single action playback...")
            self._play_actions(workflow.actions)
        except ValidationError as e:
            logger.error(f"Invalid action format: {e}")
        except Exception as e:
            logger.error(f"Error playing single action: {e}")
        
    def _play_actions(self, actions: list['ActionType']):
        for action in actions:
            time.sleep(action.time_offset)
            
            if isinstance(action, ClickAction):
                self._do_click(action)
            elif isinstance(action, TypeAction):
                self._do_type(action)
            elif isinstance(action, LoopAction):
                self._do_loop(action)
            elif isinstance(action, RunCommandAction):
                self._do_run_command(action)
            elif isinstance(action, HotkeyAction):
                self._do_hotkey(action)
            elif isinstance(action, SleepAction):
                self._do_sleep(action)
            elif isinstance(action, ScrollAction):
                self._do_scroll(action)
            elif isinstance(action, ScreenshotAction):
                self._do_screenshot(action)
            elif isinstance(action, AssertTemplateAction):
                self._do_assert_template(action)
                
    def _do_assert_template(self, action: AssertTemplateAction):
        logger.info(f"Asserting template exists: {action.template}")
        template_path = os.path.join(TEMPLATES_DIR, action.template)
        location = locate_template(template_path)
        if location is None:
            logger.error(f"Assertion failed! Template {action.template} not found on screen.")
            raise RuntimeError(f"Assertion failed: Template {action.template} not found.")
        logger.info(f"Assertion passed: Template {action.template} found at {location}")
                
    def _do_screenshot(self, action: ScreenshotAction):
        logger.info(f"Taking screenshot and saving to {action.filename}")
        try:
            pyautogui.screenshot(action.filename)
        except Exception as e:
            logger.error(f"Error taking screenshot: {e}")
                
    def _do_scroll(self, action: ScrollAction):
        logger.info(f"Scrolling {action.amount} units")
        try:
            pyautogui.scroll(action.amount)
        except Exception as e:
            logger.error(f"Error scrolling: {e}")
                
    def _do_sleep(self, action: SleepAction):
        logger.info(f"Sleeping for {action.duration} seconds...")
        time.sleep(action.duration)
                
    def _do_hotkey(self, action: HotkeyAction):
        logger.info(f"Pressing hotkey: {' + '.join(action.keys)}")
        try:
            pyautogui.hotkey(*action.keys)
        except Exception as e:
            logger.error(f"Error pressing hotkey: {e}")
                
    def _do_run_command(self, action: RunCommandAction):
        logger.info(f"Executing command: {action.command} (wait={action.wait})")
        try:
            if action.wait:
                subprocess.run(action.command, shell=True, check=True)
            else:
                subprocess.Popen(action.command, shell=True)
        except Exception as e:
            logger.error(f"Error executing command: {e}")

    def _do_loop(self, action: LoopAction):
        logger.info(f"Starting loop of {action.count} iterations for {len(action.actions)} actions...")
        for i in range(action.count):
            logger.info(f"  Loop iteration {i + 1}/{action.count}")
            self._play_actions(action.actions)
        logger.info("Loop finished.")
        
    def _do_click(self, action: ClickAction):
        click_x, click_y = action.x, action.y
        
        if action.template_image:
            location = locate_template(action.template_image)
            if location:
                click_x, click_y = location
                logger.info(f"Found template on screen at ({click_x}, {click_y})")
            else:
                logger.warning(f"Template not found, falling back to ({action.x}, {action.y})")
                
        logger.info(f"Clicking at ({click_x}, {click_y}) with {action.button} button ({action.clicks} clicks)")
        try:
            pyautogui.click(x=click_x, y=click_y, button=action.button, clicks=action.clicks)
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
