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
   ```

   ```bash
   pip install -e .
   ```

## Usage

Start the CLI tool:
```bash
automator
```

### Hotkeys:
- **`F9`**: Start recording actions (clicks and keystrokes).
- **`F10`**: Stop recording. This will generate a `workflow.json` file and a `templates/` directory containing image snippets of your clicks.
- **`F11`**: Playback the last recorded workflow.

> **Note for macOS Users:**
> You must grant **Accessibility** and **Screen Recording** permissions to your Terminal application (e.g., iTerm2 or Terminal) in `System Settings > Privacy & Security` for the automation tool to intercept global inputs and capture screen templates.

## Advanced Features
- **Hierarchical Looping:** You can manually edit `workflow.json` to repeat blocks of actions. Use `{"type": "loop", "count": 5, "actions": [...]}` to repeat specific sequences.

## Architecture
- `src/automator/cli`: CLI interface and hotkeys.
- `src/automator/core`: Core logic for recording and playback.
- `src/automator/models`: Pydantic schemas for workflows (e.g. `LoopAction`).
