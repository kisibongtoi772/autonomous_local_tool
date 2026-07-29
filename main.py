import sys
import time
from pynput import keyboard
from recorder import Recorder
from player import Player

recorder = None
recording = False

def on_press(key):
    global recorder, recording
    
    try:
        if key == keyboard.Key.f9:
            if not recording:
                print("\n[Hotkey] F9 pressed: Starting recording...")
                recording = True
                recorder = Recorder()
                recorder.start()
            else:
                print("\n[Hotkey] Already recording!")
                
        elif key == keyboard.Key.f10:
            if recording and recorder:
                print("\n[Hotkey] F10 pressed: Stopping recording...")
                recorder.stop()
                recording = False
            else:
                print("\n[Hotkey] Not currently recording.")
                
        elif key == keyboard.Key.f11:
            if not recording:
                print("\n[Hotkey] F11 pressed: Playing back...")
                player = Player()
                player.play()
            else:
                print("\n[Hotkey] Cannot play while recording!")
                
    except Exception as e:
        print(f"Error handling hotkey: {e}")

def main():
    print("=========================================")
    print("         Desktop Automator CLI           ")
    print("=========================================")
    print(" 🔴 Press F9 to start recording.")
    print(" ⏹  Press F10 to stop recording.")
    print(" ▶️  Press F11 to playback the last recording.")
    print(" ❌ Press Ctrl+C in this terminal to exit.")
    print("=========================================")
    
    # Start the hotkey listener
    listener = keyboard.Listener(on_press=on_press)
    listener.start()
    
    try:
        while True:
            time.sleep(0.1)
    except KeyboardInterrupt:
        print("\nExiting...")
        sys.exit(0)

if __name__ == "__main__":
    main()
