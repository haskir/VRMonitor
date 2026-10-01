# Head Tilt Control
A PySide6 desktop application that connects to a camera,
monitors head tilt angles, and simulates key presses based on the detected tilt angle.
This project is designed for use with shooter games that have "peek mechanics" like in PUBG.

[![IMAGE ALT TEXT HERE](https://img.youtube.com/vi/WPQFUlv4Rc4/0.jpg)](https://youtu.be/WPQFUlv4Rc4)


## Features
- **Head tilt detection**: Real-time monitoring of head angles via a webcam or external camera.
- **User-friendly GUI**: Built with PySide6 for a clean and intuitive interface.
- **Lightweight and fast**: Efficient detection with minimal resource usage.

## Prerequisites
- Windows
- [uv](https://docs.astral.sh/uv/) (Python 3.14 will be installed automatically)

## Getting Started
You can run the application by downloading compiled binaries or
from the command line using the following steps:
1. Clone the repository: `git clone https://github.com/haskir/VRMonitor`
2. Run the application: `uv run src/main.py`

The face landmark model (`src/static/face_landmarker.task`) is shipped with the repository.
If it is missing, it is downloaded automatically on the first start of detection.

## Build
Standalone build with Nuitka (requires MSVC / Visual Studio Build Tools). Run `build.bat` (double-click) or:
```powershell
./build.ps1
```
The result is `compiled/main.dist/VRMonitor.exe` — distribute the whole `main.dist` folder.

## Usage
- **Camera Selection**: Select the camera to use for head tilt detection.
- **Camera Mode**: Select resolution and frame rate (e.g. 1920x1080 @ 60 fps MJPG). Higher fps means lower latency.
- **Select Threshold**: Set the threshold for head tilt detection (default: 20).
- **Start/Stop**: Start or stop the head tilt detection.
- **Key Presses**: Simulate key presses based on head tilt angles.
- **Only in PUBG** (default on, "Только в PUBG"): keys are sent only while PUBG (`TslGame.exe`) is the foreground window; on alt-tab held keys are released, and the current head position is re-applied when you return to the game.
- **Exit**: Close the application.
- **Stance awareness** (default on, "Учитывать позу"): the character's stance is read from the HUD icon left of the health bar. While prone, crouching from the camera is ignored; if you change stance manually (toggle crouch), the app takes the game's stance as the truth and brings it back in line with your head.
- **Sit Auto-calibration** (optional, "Авто"): if the head stays still for 20 seconds while standing, its position becomes the new top position and the sit line moves with it.
- **OBS output** (optional, "Вывод в OBS"): VRMonitor keeps the physical camera and sends the image (optionally with the face mesh) to OBS Virtual Camera. In OBS add a "Video Capture Device" source with "OBS Virtual Camera"; the "Start Virtual Camera" button in OBS itself must be off. Requires OBS Studio installed.

Settings are saved to `%APPDATA%\VRMonitor\settings.json`.

## Development
Run tests: `uv run pytest`. Lint: `uv run ruff check src tests`.

The code in `src/` is split into layers; dependencies point inwards only:
- `domain/` — plain Python models and rules: key bindings, settings, head pose, lean/sit detection with auto-calibration, stance smoothing. No third-party imports.
- `application/` — use cases: `InputController` (desired vs actual key state, game focus, stance), `HeadTracking` (pose → gestures), `App` (facade for the UI: applies and persists settings). External world is reached through interfaces in `ports.py`.
- `infrastructure/` — adapters: camera capture and MediaPipe, preview and OBS output, DirectInput keys, WinAPI foreground window, HUD stance detector, JSON settings.
- `ui/` — PySide6 widgets; `bridge.py` delivers application events to the GUI thread.
- `main.py` — composition root that wires concrete implementations together.
