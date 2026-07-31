import json
import time
import os
import subprocess
from typing import Optional, List
from pydantic import ValidationError

import pyautogui
import pyperclip

from ..models.workflow import (
    Workflow, ClickAction, TypeAction, LoopAction, RunCommandAction,
    HotkeyAction, SleepAction, ScrollAction, ScreenshotAction,
    AssertTemplateAction, ClipboardAction, IfTemplateAction, ActionType
)
from ..utils.logger import get_logger
from ..utils.config import WORKFLOW_FILE, TEMPLATES_DIR, RUN_HISTORY_FILE
from .vision import locate_template
from .variable_manager import VariableManager

logger = get_logger(__name__)

pyautogui.FAILSAFE = True


class Player:
    def __init__(self, workflow_path=None):
        self.workflow_path = workflow_path or WORKFLOW_FILE
        self.workflow: Optional[Workflow] = None
        self.var_manager = VariableManager()

    def play(self) -> bool:
        if not os.path.exists(self.workflow_path):
            logger.error(f"Workflow file not found: {self.workflow_path}")
            return False

        start_time = time.time()
        success = False
        action_count = 0

        try:
            with open(self.workflow_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            self.workflow = Workflow.model_validate(data)
        except ValidationError as e:
            logger.error(f"Invalid workflow format: {e}")
            self._log_run(success=False, action_count=0, duration=0, error=str(e))
            return False
        except Exception as e:
            logger.error(f"Error reading workflow: {e}")
            self._log_run(success=False, action_count=0, duration=0, error=str(e))
            return False

        try:
            self.var_manager.load()
            action_count = len(self.workflow.actions)
            logger.info(f"Starting playback of {action_count} actions in '{self.workflow.workflow_name}'...")
            self._play_actions(self.workflow.actions)
            logger.info("Playback finished successfully.")
            success = True
        except Exception as e:
            logger.error(f"Playback stopped due to error: {e}")
            success = False

        duration = round(time.time() - start_time, 2)
        self._log_run(success=success, action_count=action_count, duration=duration)
        return success

    def play_single_action(self, action_dict: dict):
        """Helper to test a single action dictionary without loading a file."""
        try:
            self.var_manager.load()
            resolved = self.var_manager.resolve_action(action_dict)
            workflow = Workflow.model_validate({"workflow_name": "temp", "created_at": "", "actions": [resolved]})
            logger.info("Testing single action playback...")
            self._play_actions(workflow.actions)
        except ValidationError as e:
            logger.error(f"Invalid action format: {e}")
        except Exception as e:
            logger.error(f"Error playing single action: {e}")

    def _play_actions(self, actions: List[ActionType]):
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
            elif isinstance(action, ClipboardAction):
                self._do_clipboard(action)
            elif isinstance(action, IfTemplateAction):
                self._do_if_template(action)

    # ── Existing action handlers ─────────────────────────────────────────────

    def _do_assert_template(self, action: AssertTemplateAction):
        logger.info(f"Asserting template exists: {action.template}")
        template_path = os.path.join(TEMPLATES_DIR, action.template)
        location = locate_template(template_path)
        if location is None:
            logger.error(f"Assertion failed! Template {action.template} not found on screen.")
            raise RuntimeError(f"Assertion failed: Template {action.template} not found.")
        logger.info(f"Assertion passed: Template {action.template} found at {location}")

    def _do_screenshot(self, action: ScreenshotAction):
        filename = self.var_manager.resolve(action.filename)
        logger.info(f"Taking screenshot → {filename}")
        try:
            pyautogui.screenshot(filename)
        except Exception as e:
            logger.error(f"Error taking screenshot: {e}")

    def _do_scroll(self, action: ScrollAction):
        logger.info(f"Scrolling {action.amount} units")
        try:
            pyautogui.scroll(action.amount)
        except Exception as e:
            logger.error(f"Error scrolling: {e}")

    def _do_sleep(self, action: SleepAction):
        logger.info(f"Sleeping for {action.duration}s...")
        time.sleep(action.duration)

    def _do_hotkey(self, action: HotkeyAction):
        keys = [self.var_manager.resolve(k) for k in action.keys]
        logger.info(f"Pressing hotkey: {' + '.join(keys)}")
        try:
            pyautogui.hotkey(*keys)
        except Exception as e:
            logger.error(f"Error pressing hotkey: {e}")

    def _do_run_command(self, action: RunCommandAction):
        command = self.var_manager.resolve(action.command)
        logger.info(f"Executing command: {command} (wait={action.wait})")
        try:
            if action.wait:
                subprocess.run(command, shell=True, check=True)
            else:
                subprocess.Popen(command, shell=True)
        except Exception as e:
            logger.error(f"Error executing command: {e}")

    def _do_loop(self, action: LoopAction):
        logger.info(f"Starting loop × {action.count} ({len(action.actions)} actions each)...")
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

        logger.info(f"Clicking at ({click_x}, {click_y}) — {action.button} × {action.clicks}")
        try:
            pyautogui.click(x=click_x, y=click_y, button=action.button, clicks=action.clicks)
        except Exception as e:
            logger.error(f"Error clicking: {e}")

    def _do_type(self, action: TypeAction):
        key = self.var_manager.resolve(action.key)
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

    # ── New action handlers ──────────────────────────────────────────────────

    def _do_clipboard(self, action: ClipboardAction):
        try:
            if action.action == "set":
                text = self.var_manager.resolve(action.text)
                pyperclip.copy(text)
                logger.info(f"Clipboard set to: {text!r}")
            elif action.action == "copy":
                pyautogui.hotkey("ctrl", "c") if os.name != "nt" else pyautogui.hotkey("cmd", "c")
                logger.info("Triggered system copy (Cmd/Ctrl+C)")
            elif action.action == "paste":
                if os.name == "posix":
                    pyautogui.hotkey("command", "v")
                else:
                    pyautogui.hotkey("ctrl", "v")
                logger.info("Triggered system paste (Cmd/Ctrl+V)")
        except Exception as e:
            logger.error(f"Clipboard error: {e}")

    def _do_if_template(self, action: IfTemplateAction):
        template_path = os.path.join(TEMPLATES_DIR, action.template)
        location = locate_template(template_path)
        if location:
            logger.info(f"if_template: '{action.template}' FOUND → running then_actions ({len(action.then_actions)})")
            self._play_actions(action.then_actions)
        else:
            logger.info(f"if_template: '{action.template}' NOT FOUND → running else_actions ({len(action.else_actions)})")
            self._play_actions(action.else_actions)

    # ── Run History ──────────────────────────────────────────────────────────

    def _log_run(self, success: bool, action_count: int, duration: float, error: str = ""):
        entry = {
            "workflow": os.path.basename(self.workflow_path),
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "success": success,
            "action_count": action_count,
            "duration_sec": duration,
            "error": error,
        }
        history = []
        if os.path.exists(RUN_HISTORY_FILE):
            try:
                with open(RUN_HISTORY_FILE, "r", encoding="utf-8") as f:
                    history = json.load(f)
            except Exception:
                history = []
        # Keep last 100 entries
        history.insert(0, entry)
        history = history[:100]
        try:
            with open(RUN_HISTORY_FILE, "w", encoding="utf-8") as f:
                json.dump(history, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Failed to write run history: {e}")
