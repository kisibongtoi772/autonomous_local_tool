# Desktop Automator (Hybrid Record & Playback)

A local desktop automation tool that records mouse and keyboard events and plays them back. It uses a **hybrid approach** to ensure playback reliability: when you click, it captures a small template image around your cursor. During playback, it uses Computer Vision (via OpenCV) to find that exact image on the screen, gracefully falling back to absolute coordinates if the image is not found.

## Tech Stack
- **Python 3**
- `pynput`: For global keyboard and mouse event hooking.
- `pyautogui`: For simulating mouse clicks and keystrokes.
- `opencv-python`: For template matching (Computer Vision).
- `mss` & `Pillow`: For high-speed screen capturing.
- `pydantic`: For strict JSON workflow validation.

## Setup

1. **Clone the repository and cd into it:**
   ```bash
   cd autonomous_local_tool
   ```

2. **Create a virtual environment:**
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -e .
   ```

## Usage

Start the tool to open the **Modern GUI Dashboard**:
```bash
desktop-automator
# or use the shorthand: dauto
```

The GUI allows you to click buttons to Record, Stop, and Playback on the **Dashboard** tab. It features a **Live Log Console** that displays exactly what the automation is doing (e.g., clicking coordinates, finding templates) in real-time. 

You can **manage multiple workflows** using the dropdown menu and the **New** button in the Dashboard.

You can also switch to the **Workflow** tab to view a visual summary of all recorded steps without needing to open the raw JSON file. You can **delete individual steps** by clicking the "❌" button next to them, or **clear the entire workflow** using the "🗑️ Clear All" button. You can also manually inject complex actions (like sleep delays or terminal commands) by clicking the **"➕ Add Action"** button.

Alternatively, you can use the physical hotkeys:

### Hotkeys:
- **`F9` (Record)**: Start recording actions (clicks and keystrokes).
- **`F10` (Stop)**: Stop recording. This will generate a `workflow.json` file and a `templates/` directory containing image snippets of your clicks inside the `workspace/` folder.
- **`F11` (Playback)**: Playback the last recorded workflow.

> **Note for macOS Users:**
> You must grant **Accessibility** and **Screen Recording** permissions to your Terminal application (e.g., iTerm2 or Terminal) in `System Settings > Privacy & Security` for the automation tool to intercept global inputs and capture screen templates.

## Advanced Features
- **Hierarchical Looping:** You can manually edit `workspace/workflow.json` to repeat blocks of actions. Use `{"type": "loop", "count": 5, "actions": [...]}` to repeat specific sequences.
- **Run Subprocesses/Apps:** You can start applications or run shell scripts before executing clicks using `{"type": "run_command", "command": "open -a Calculator", "wait": false}`.
- **Global Hotkeys:** Trigger multi-key shortcuts seamlessly (e.g. `{"type": "hotkey", "keys": ["cmd", "space"]}`).
- **Explicit Sleep:** Insert hardcoded delays directly into your workflow (e.g. `{"type": "sleep", "duration": 3.5}`).
- **Scroll Simulation:** Simulate mouse scroll wheels (e.g. `{"type": "scroll", "amount": -10}`).
- **Take Screenshots:** Capture screen states at any point in your workflow (e.g. `{"type": "screenshot", "filename": "state_1.png"}`).
- **Robust Verification (Assert):** Fail the workflow if an expected image template does not appear on screen (e.g. `{"type": "assert_template", "template": "success_btn.png"}`).
- **Advanced Clicks:** Support for right-click and double-click natively (e.g. `{"type": "click", "x": 100, "y": 200, "button": "right", "clicks": 2}`).

## Architecture
- `src/automator/cli`: CLI interface and hotkeys.
- `src/automator/core`: Core logic for recording and playback.
- `src/automator/models`: Pydantic schemas for workflows (e.g. `LoopAction`).
