"""
Player — executes workflow actions with:
  • Retry logic (retry_count / retry_delay on every action)
  • wait_for_template (polls screen up to timeout)
  • run_workflow (subroutine / chaining)
  • Speed multiplier (scales all time_offset and sleep durations)
  • Step callback (interactive step-by-step confirmation from GUI)
  • Run history logging
"""
from __future__ import annotations

import json
import os
import subprocess
import time
from typing import Callable, List, Optional

import pyautogui
import pyperclip
from pydantic import ValidationError

from ..models.workflow import (
    ActionType, AssertTemplateAction, ClickAction, ClipboardAction,
    HotkeyAction, IfTemplateAction, LoopAction, RunCommandAction,
    RunWorkflowAction, ScreenshotAction, ScrollAction, SleepAction,
    TypeAction, WaitForTemplateAction, Workflow, PromptUserAction,
    AppFocusAction, NotificationAction, CommentAction, GroupAction,
    AssertColorAction, IfColorAction
)
from ..utils.config import RUN_HISTORY_FILE, TEMPLATES_DIR, WORKFLOW_FILE, WORKSPACE_DIR, SNAPSHOTS_DIR
from ..utils.logger import get_logger
from .variable_manager import VariableManager
from .vision import locate_template

logger = get_logger(__name__)
pyautogui.FAILSAFE = True


class Player:
    def __init__(
        self,
        workflow_path: str | None = None,
        speed: float = 1.0,
        step_callback: Callable[[dict], str] | None = None,
        progress_callback: Callable[[int, int, dict], None] | None = None,
        prompt_callback: Callable[[dict], str] | None = None,
        ripple_callback: Callable[[int, int], None] | None = None,
        highlight_callback: Callable[[int, int, int, int], None] | None = None,
        breakpoint_callback: Callable[[int], None] | None = None,
        _depth: int = 0,
    ):
        """
        Args:
            workflow_path:     Path to the workflow JSON file.
            speed:             Multiplier applied to all time_offset and sleep durations.
            step_callback:     Optional callable for interactive step-by-step mode.
                               Must return: "run" | "skip" | "stop"
            progress_callback: Optional callable for real-time progress update.
                               Called as progress_callback(step_index_1_based, total_steps, raw_action_dict)
            prompt_callback:   Optional callable for interactive PromptUserAction.
                               Must return user input string, or '!CANCEL!'.
            highlight_callback: Optional callable to visually indicate a template match area.
                               Called as highlight_callback(left, top, width, height)
            _depth:            Internal recursion guard for run_workflow (max 10 levels).
        """
        self.workflow_path = workflow_path or WORKFLOW_FILE
        self.workflow: Optional[Workflow] = None
        self.speed = max(0.1, speed)
        self.step_callback = step_callback
        self.progress_callback = progress_callback
        self.prompt_callback = prompt_callback
        self.ripple_callback = ripple_callback
        self._depth = _depth
        self.ripple_callback = ripple_callback
        self._depth = _depth
        self.var_manager = VariableManager()
        self._stop_requested = False
        self._paused = False
        self._last_snapshot = ""

    # ── Public API ────────────────────────────────────────────────────────────

    def stop(self):
        self._stop_requested = True
        self._paused = False
        logger.info("Player: Stop requested.")

    def pause(self):
        self._paused = True
        logger.info("Player: Playback paused.")

    def resume(self):
        self._paused = False
        logger.info("Player: Playback resumed.")

    def play(self, start_idx: int = 0, end_idx: int = None) -> bool:
        if not os.path.exists(self.workflow_path):
            logger.error(f"Workflow not found: {self.workflow_path}")
            return False

        start = time.time()
        action_count = 0
        success = False

        try:
            with open(self.workflow_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.workflow = Workflow.model_validate(data)
        except (ValidationError, Exception) as e:
            logger.error(f"Cannot load workflow: {e}")
            self._log_run(False, 0, 0, str(e), snapshot="")
            return False

        try:
            self.var_manager.load()
            action_count = len(self.workflow.actions)
            logger.info(
                f"Starting playback: '{self.workflow.workflow_name}' "
                f"({action_count} actions, start={start_idx+1}, speed={self.speed}x)"
            )
            self._play_actions(self.workflow.actions, start_idx=start_idx, end_idx=end_idx)
            if self._stop_requested:
                logger.info("Playback stopped by user.")
            else:
                logger.info("Playback finished successfully.")
            success = not self._stop_requested
        except Exception as e:
            logger.error(f"Playback error: {e}")

        duration = round(time.time() - start, 2)
        duration = round(time.time() - start, 2)
        if self._depth == 0:  # Only log for top-level workflows
            self._log_run(success, action_count, duration, snapshot=self._last_snapshot)
        return success

    def play_single_action(self, action_dict: dict):
        """Test a single action without loading a file."""
        try:
            self.var_manager.load()
            resolved = self.var_manager.resolve_action(action_dict)
            wf = Workflow.model_validate(
                {"workflow_name": "test", "created_at": "", "actions": [resolved]}
            )
            logger.info("Testing single action...")
            self._play_actions(wf.actions)
        except ValidationError as e:
            logger.error(f"Invalid action format: {e}")
        except Exception as e:
            logger.error(f"Single action error: {e}")

    # ── Core execution loop ───────────────────────────────────────────────────

    def _play_actions(self, actions: List[ActionType], start_idx: int = 0, end_idx: int = None):
        total_steps = len(actions)
        if end_idx is not None:
            total_steps = min(total_steps, end_idx)
            
        for i in range(start_idx, total_steps):
            if self._stop_requested:
                return

            action = actions[i]
            idx_1_based = i + 1

            if getattr(action, "breakpoint", False):
                logger.info(f"⏸ Breakpoint hit at action {idx_1_based}")
                if self.breakpoint_callback:
                    self.breakpoint_callback(idx_1_based)
                self.pause()

            while self._paused and not self._stop_requested:
                time.sleep(0.1)

            if not getattr(action, "enabled", True):
                continue

            if self.progress_callback is not None:
                try:
                    import inspect
                    sig = inspect.signature(self.progress_callback)
                    if len(sig.parameters) >= 4:
                        self.progress_callback(idx_1_based, total_steps, action.model_dump(), self._depth)
                    else:
                        self.progress_callback(idx_1_based, total_steps, action.model_dump())
                except Exception:
                    pass

            # ── Step-by-step confirmation ────────────────────────────────────
            if self.step_callback is not None:
                raw = action.model_dump()
                decision = self.step_callback(raw)
                if decision == "stop":
                    self._stop_requested = True
                    logger.info("Step-by-step: user stopped playback.")
                    return
                if decision == "skip":
                    logger.info(f"Step-by-step: skipped {action.type}")
                    continue

            # ── Time offset (scaled by speed) ────────────────────────────────
            scaled_offset = action.time_offset / self.speed
            if scaled_offset > 0:
                if not self._chunked_sleep(scaled_offset):
                    return

            # ── Execute with optional retry ──────────────────────────────────
            self._execute_with_retry(action)

    def _execute_with_retry(self, action: ActionType):
        max_attempts = 1 + max(0, action.retry_count)
        delay = action.retry_delay

        for attempt in range(max_attempts):
            if self._stop_requested:
                return
            try:
                self._dispatch(action)
                return  # Success — stop retrying
            except Exception as e:
                remaining = max_attempts - attempt - 1
                if remaining > 0:
                    logger.warning(
                        f"[Retry {attempt+1}/{action.retry_count}] {action.type} failed: {e} "
                        f"— retrying in {delay}s"
                    )
                    if not self._chunked_sleep(delay):
                        return
                else:
                    # Final attempt failed - capture failure snapshot
                    try:
                        timestamp = time.strftime("%Y%m%d_%H%M%S")
                        snap_name = f"fail_{timestamp}.png"
                        snap_path = os.path.join(SNAPSHOTS_DIR, snap_name)
                        pyautogui.screenshot(snap_path)
                        self._last_snapshot = snap_name
                        logger.info(f"Failure snapshot saved to {snap_name}")
                    except Exception as snap_e:
                        logger.error(f"Failed to capture snapshot: {snap_e}")
                    raise

    def _dispatch(self, action: ActionType):
        if isinstance(action, ClickAction):           self._do_click(action)
        elif isinstance(action, TypeAction):          self._do_type(action)
        elif isinstance(action, LoopAction):          self._do_loop(action)
        elif isinstance(action, RunCommandAction):    self._do_run_command(action)
        elif isinstance(action, HotkeyAction):        self._do_hotkey(action)
        elif isinstance(action, SleepAction):         self._do_sleep(action)
        elif isinstance(action, ScrollAction):        self._do_scroll(action)
        elif isinstance(action, ScreenshotAction):    self._do_screenshot(action)
        elif isinstance(action, AssertTemplateAction):self._do_assert_template(action)
        elif isinstance(action, ClipboardAction):     self._do_clipboard(action)
        elif isinstance(action, IfTemplateAction):    self._do_if_template(action)
        elif isinstance(action, WaitForTemplateAction):self._do_wait_for_template(action)
        elif isinstance(action, RunWorkflowAction):   self._do_run_workflow(action)
        elif isinstance(action, PromptUserAction):    self._do_prompt_user(action)
        elif isinstance(action, AppFocusAction):      self._do_app_focus(action)
        elif isinstance(action, NotificationAction):  self._do_notification(action)
        elif isinstance(action, CommentAction):       self._do_comment(action)

    # ── Action handlers ───────────────────────────────────────────────────────
    
    def _do_comment(self, a: CommentAction):
        logger.info(f"--- {a.text} ---")

    def _do_app_focus(self, a: AppFocusAction):
        logger.info(f"App Focus: {a.app_name}")
        app_name = self.var_manager.resolve(a.app_name)
        if a.launch_if_closed:
            # Tell application to activate (will launch if not running)
            subprocess.run(["osascript", "-e", f'tell application "{app_name}" to activate'])
        else:
            # Check if running first
            res = subprocess.run(["osascript", "-e", f'application "{app_name}" is running'], capture_output=True, text=True)
            if "true" in res.stdout.lower():
                subprocess.run(["osascript", "-e", f'tell application "{app_name}" to activate'])
            else:
                logger.warning(f"AppFocus: {app_name} is not running and launch_if_closed is False.")

    def _do_notification(self, a: NotificationAction):
        title = self.var_manager.resolve(a.title)
        msg = self.var_manager.resolve(a.message)
        logger.info(f"Notification: {title} - {msg}")
        # Escape quotes for applescript
        title = title.replace('"', '\\"')
        msg = msg.replace('"', '\\"')
        subprocess.run(["osascript", "-e", f'display notification "{msg}" with title "{title}"'])

    def _do_click(self, a: ClickAction):
        x, y = a.x, a.y
        if a.template_image:
            loc = locate_template(a.template_image, confidence=a.confidence)
            if loc:
                left, top, w, h = loc
                if self.highlight_callback:
                    self.highlight_callback(left, top, w, h)
                x = left + w // 2 + a.offset_x
                y = top + h // 2 + a.offset_y
                logger.info(f"Template matched. Target set to ({x}, {y}) [offset: {a.offset_x}, {a.offset_y}]")
            else:
                logger.warning(f"Template not found — falling back to ({a.x}, {a.y})")
        logger.info(f"Click ({x}, {y})  button={a.button}  ×{a.clicks}")
        if a.move_duration > 0:
            pyautogui.moveTo(x, y, duration=a.move_duration)
        if self.ripple_callback:
            self.ripple_callback(x, y)
        pyautogui.click(x=x, y=y, button=a.button, clicks=a.clicks)

    def _do_type(self, a: TypeAction):
        key = self.var_manager.resolve(a.key)
        logger.info(f"Type: {key!r}")
        if key.startswith("Key."):
            k = key.replace("Key.", "")
            try:
                pyautogui.press(k)
            except ValueError:
                logger.error(f"Unsupported key: {k}")
        else:
            pyautogui.write(key) if len(key) == 1 else pyautogui.press(key)

    def _chunked_sleep(self, seconds: float) -> bool:
        """Sleeps in small chunks to allow immediate cancellation or pausing."""
        end_time = time.time() + seconds
        while time.time() < end_time:
            if self._stop_requested:
                return False
            while self._paused and not self._stop_requested:
                time.sleep(0.1)
                end_time += 0.1  # Extend end_time while paused
            
            if self._stop_requested:
                return False
            time.sleep(min(0.1, end_time - time.time()))
        return True

    def _do_sleep(self, a: SleepAction):
        duration = a.duration / self.speed
        logger.info(f"Sleep {duration:.2f}s  (original={a.duration}s, speed={self.speed}x)")
        self._chunked_sleep(duration)

    def _do_hotkey(self, a: HotkeyAction):
        keys = [self.var_manager.resolve(k) for k in a.keys]
        logger.info(f"Hotkey: {' + '.join(keys)}")
        pyautogui.hotkey(*keys)

    def _do_scroll(self, a: ScrollAction):
        logger.info(f"Scroll {a.amount}")
        pyautogui.scroll(a.amount)

    def _do_screenshot(self, a: ScreenshotAction):
        filename = self.var_manager.resolve(a.filename)
        logger.info(f"Screenshot → {filename}")
        pyautogui.screenshot(filename)

    def _do_run_command(self, a: RunCommandAction):
        cmd = self.var_manager.resolve(a.command)
        logger.info(f"Command: {cmd!r}  (wait={a.wait})")
        if a.wait:
            subprocess.run(cmd, shell=True, check=True)
        else:
            subprocess.Popen(cmd, shell=True)

    def _do_loop(self, a: LoopAction):
        logger.info(f"Loop ×{a.count}  ({len(a.actions)} actions per iteration)")
        for i in range(a.count):
            if self._stop_requested:
                return
            
            # Expose loop index
            self.var_manager.variables["loop_index"] = str(i + 1)
            self.var_manager.variables[f"loop_index_{self._depth}"] = str(i + 1)
            
            logger.info(f"  Iteration {i+1}/{a.count}")
            self._play_actions(a.actions)
        logger.info("Loop done.")

    def _do_group(self, a: GroupAction):
        logger.info(f"Group: {a.name} ({len(a.actions)} actions)")
        self._play_actions(a.actions)

    def _do_assert_template(self, a: AssertTemplateAction):
        path = os.path.join(TEMPLATES_DIR, a.template)
        loc  = locate_template(path, confidence=a.confidence)
        if loc is None:
            raise RuntimeError(f"Assertion failed: '{a.template}' not found on screen.")
        if self.highlight_callback:
            self.highlight_callback(*loc)
        logger.info(f"Assert OK: '{a.template}' at {loc}")

    def _do_clipboard(self, a: ClipboardAction):
        if a.action == "set":
            text = self.var_manager.resolve(a.text)
            pyperclip.copy(text)
            logger.info(f"Clipboard set: {text!r}")
        elif a.action == "copy":
            key = "command" if os.name == "posix" else "ctrl"
            pyautogui.hotkey(key, "c")
            logger.info("Clipboard copy triggered")
        elif a.action == "paste":
            key = "command" if os.name == "posix" else "ctrl"
            pyautogui.hotkey(key, "v")
            logger.info("Clipboard paste triggered")

    def _do_if_template(self, a: IfTemplateAction):
        path = os.path.join(TEMPLATES_DIR, a.template)
        loc  = locate_template(path, confidence=a.confidence)
        if loc:
            if self.highlight_callback:
                self.highlight_callback(*loc)
            logger.info(f"Conditional: '{a.template}' FOUND → then ({len(a.then_actions)} actions)")
            self._play_actions(a.then_actions)
        else:
            logger.info(f"Conditional: '{a.template}' NOT FOUND → else ({len(a.else_actions)} actions)")
            self._play_actions(a.else_actions)

    def _hex_to_rgb(self, h: str):
        h = h.lstrip('#')
        if len(h) != 6: return (0,0,0)
        return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))

    def _check_color(self, x, y, target_hex, tolerance):
        try:
            r, g, b = pyautogui.pixel(x, y)
        except Exception as e:
            # Fallback if pyautogui.pixel fails on some OS configurations
            from PIL import ImageGrab
            r, g, b = ImageGrab.grab(bbox=(x, y, x+1, y+1)).getpixel((0, 0))[:3]
            
        tr, tg, tb = self._hex_to_rgb(target_hex)
        diff = max(abs(r - tr), abs(g - tg), abs(b - tb))
        return diff <= tolerance, (r, g, b)

    def _do_assert_color(self, a: AssertColorAction):
        match, actual = self._check_color(a.x, a.y, a.color, a.tolerance)
        if not match:
            actual_hex = f"#{actual[0]:02X}{actual[1]:02X}{actual[2]:02X}"
            raise RuntimeError(f"Color assertion failed at ({a.x},{a.y}): expected {a.color} ±{a.tolerance}, got {actual_hex}")
        logger.info(f"Assert Color OK: ({a.x},{a.y}) matched {a.color}")

    def _do_if_color(self, a: IfColorAction):
        match, actual = self._check_color(a.x, a.y, a.color, a.tolerance)
        if match:
            logger.info(f"Conditional: Color {a.color} MATCHED at ({a.x},{a.y}) → then ({len(a.then_actions)} actions)")
            self._play_actions(a.then_actions)
        else:
            actual_hex = f"#{actual[0]:02X}{actual[1]:02X}{actual[2]:02X}"
            logger.info(f"Conditional: Color mismatch ({actual_hex} != {a.color}) → else ({len(a.else_actions)} actions)")
            self._play_actions(a.else_actions)

    # ── New action handlers ───────────────────────────────────────────────────

    def _do_wait_for_template(self, a: WaitForTemplateAction):
        """Poll screen at `interval` seconds until template appears or `timeout` expires."""
        path     = os.path.join(TEMPLATES_DIR, a.template)
        deadline = time.time() + a.timeout
        elapsed  = 0.0

        logger.info(f"Waiting for '{a.template}' (timeout={a.timeout}s, interval={a.interval}s)...")

        while time.time() < deadline:
            if self._stop_requested:
                return
            loc = locate_template(path, confidence=a.confidence)
            if loc:
                if self.highlight_callback:
                    self.highlight_callback(*loc)
                elapsed = round(time.time() - (deadline - a.timeout), 2)
                logger.info(f"  Found '{a.template}' at {loc} after {elapsed}s")
                return
            time.sleep(a.interval)

        msg = f"wait_for_template timed out after {a.timeout}s: '{a.template}' not found."
        if a.on_timeout == "error":
            raise RuntimeError(msg)
        else:
            logger.warning(msg + "  Continuing (on_timeout=continue).")

    def _do_run_workflow(self, a: RunWorkflowAction):
        """Invoke another workflow as a synchronous subroutine."""
        if self._depth >= 10:
            raise RuntimeError("run_workflow: max nesting depth (10) exceeded.")

        wf_path = os.path.join(WORKSPACE_DIR, a.workflow_file)
        if not os.path.exists(wf_path):
            raise FileNotFoundError(f"run_workflow: '{a.workflow_file}' not found in workspace/.")

        logger.info(f">>> Entering sub-workflow: {a.workflow_file}")
        sub = Player(
            workflow_path=wf_path,
            speed=self.speed,
            step_callback=self.step_callback,
            progress_callback=self.progress_callback,
            _depth=self._depth + 1,
        )
        sub.var_manager = self.var_manager   # Share variables
        ok = sub.play()
        if not ok:
            raise RuntimeError(f"Sub-workflow '{a.workflow_file}' failed or was stopped.")
        logger.info(f"<<< Returned from sub-workflow: {a.workflow_file}")

    def _do_prompt_user(self, a: PromptUserAction):
        logger.info(f"Prompting user: {a.message}")
        if self.prompt_callback:
            result = self.prompt_callback(a.model_dump())
            if result == "!CANCEL!":
                self.stop()
                logger.info("User cancelled at prompt. Workflow stopped.")
                return
            if a.save_to_variable:
                self.var_manager.variables[a.save_to_variable] = result
                logger.info(f"Saved user input to variable '{a.save_to_variable}'")
        else:
            logger.warning("No prompt_callback defined. Skipping prompt.")

    # ── Run History ───────────────────────────────────────────────────────────

    def _log_run(self, success: bool, action_count: int, duration: float, error: str = "", snapshot: str = ""):
        entry = {
            "workflow":     os.path.basename(self.workflow_path),
            "timestamp":    time.strftime("%Y-%m-%d %H:%M:%S"),
            "success":      success,
            "action_count": action_count,
            "duration_sec": duration,
            "speed":        self.speed,
            "error":        error,
            "snapshot":     snapshot,
        }
        history: list = []
        if os.path.exists(RUN_HISTORY_FILE):
            try:
                with open(RUN_HISTORY_FILE, "r", encoding="utf-8") as f:
                    history = json.load(f)
            except Exception:
                history = []

        history.insert(0, entry)
        history = history[:100]
        try:
            with open(RUN_HISTORY_FILE, "w", encoding="utf-8") as f:
                json.dump(history, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Failed to write run history: {e}")
