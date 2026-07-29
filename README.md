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

The GUI provides a complete control center for your automation tasks:
- **Dashboard Tab**: Allows you to Record, Stop, and Playback workflows. It features a Live Log Console that displays the execution details (e.g., clicking coordinates, finding templates) in real-time. You can also manage multiple workflows using the dropdown menu and the "New" button.
- **Workflow Editor Tab**: A visual editor to view and modify all recorded steps without editing raw JSON files. Available operations include:
  - **Thumbnail Previews**: Visually inspect the exact image template captured for click actions right inside the editor row.
  - **Reorder**: Move actions up or down.
  - **Edit**: Modify action properties (e.g., coordinates, durations, command strings).
  - **Duplicate**: Clone an existing action.
  - **Test**: Perform a partial playback of a single action.
  - **Delete / Clear**: Remove specific actions or clear the entire workflow.
  - **Manual Insertion**: Add complex actions (like sleep delays or terminal commands) directly from the GUI.

### Hotkeys
Alternatively, you can control the core functions using physical hotkeys:
- **`F9` (Record)**: Start capturing global mouse clicks and keystrokes.
- **`F10` (Stop)**: Stop recording. The workflow is automatically saved to your `workspace/` directory along with any generated image templates.
- **`F11` (Playback)**: Playback the currently selected workflow.

> **Note for macOS Users:**
> You must grant **Accessibility** and **Screen Recording** permissions to your Terminal application (e.g., iTerm2 or Terminal) in `System Settings > Privacy & Security` for the automation tool to intercept global inputs and capture screen templates.

## Advanced Features
- **Hierarchical Looping:** Repeat specific blocks of actions by editing the workflow to use the `LoopAction` structure (`{"type": "loop", "count": 5, "actions": [...]}`).
- **Subprocess Execution:** Launch applications or shell scripts as part of your workflow via the `run_command` action type.
- **Global Hotkeys:** Trigger multi-key shortcuts seamlessly (e.g., `{"type": "hotkey", "keys": ["cmd", "space"]}`).
- **Explicit Delays:** Insert precise sleep intervals (e.g., `{"type": "sleep", "duration": 3.5}`).
- **Scroll Simulation:** Control the mouse scroll wheel (e.g., `{"type": "scroll", "amount": -10}`).
- **State Capture:** Take screenshots during workflow execution (e.g., `{"type": "screenshot", "filename": "state.png"}`).
- **Robust Verification:** Assert the presence of UI elements. If the specified template is not found, the workflow safely halts (e.g., `{"type": "assert_template", "template": "btn.png"}`).
- **Advanced Clicks:** Full support for custom click behaviors including right-clicks and double-clicks.

## Architecture
- `src/automator/cli`: CLI interface and hotkeys.
- `src/automator/core`: Core logic for recording and playback.
- `src/automator/models`: Pydantic schemas for workflows (e.g. `LoopAction`).
