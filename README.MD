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
The window is split into sections; every change is applied and saved immediately.
- **Start/Stop** (big button on top): start or stop head tracking. Chips below show whether a face is found and whether PUBG is in focus (with the character's stance).
- **Camera**: select the camera and mode (e.g. 1920x1080 @ 60 fps MJPG — higher fps means lower latency), open the preview window, toggle overlay on it.
  - **OBS output** ("Вывод в OBS"): VRMonitor keeps the physical camera and sends the image (optionally with the face mesh) to OBS Virtual Camera. In OBS add a "Video Capture Device" source with "OBS Virtual Camera"; the "Start Virtual Camera" button in OBS itself must be off. Requires OBS Studio installed.
- **Leans** ("Наклоны"): drag the threshold (default 20°). While tracking is on, a marker shows your current head tilt and turns orange when a lean is triggered. Set keys by clicking the key button and pressing a key (letters, digits, Ctrl/Shift/Alt/Space/Tab, F1–F12); choose hold or toggle mode.
- **Crouch** ("Приседания", can be switched off): drag the line to just below your head — when the head goes past it, the character crouches. The marker shows the current head position.
  - **Auto-calibration** ("Авто-калибровка"): if the head stays still for 20 seconds while standing, its position becomes the new top position (green tick) and the line moves with it.
- **PUBG**:
  - **Only in PUBG** (default on): keys are sent only while PUBG (`TslGame.exe`) is the foreground window; on alt-tab held keys are released, and the current head position is re-applied when you return to the game.
  - **Stance awareness** (default on, "Учитывать позу персонажа"): the character's stance is read from the HUD icon left of the health bar. While prone, crouching from the camera is ignored; if you change stance manually (toggle crouch), the app takes the game's stance as the truth and brings it back in line with your head.

Settings are saved to `%APPDATA%\VRMonitor\settings.json`.

## Development
Run tests: `uv run pytest`. Lint: `uv run ruff check src tests`.
Tests with the real OBS Virtual Camera are skipped by default; run them with `uv run pytest --obs` (OBS Studio installed, its own virtual camera off; the "OBS Virtual Camera" source in OBS shows a test pattern for a couple of seconds).

The code in `src/` is split into layers; dependencies point inwards only:
- `domain/` — plain Python models and rules: key bindings, settings, head pose, lean/sit detection with auto-calibration, stance smoothing. No third-party imports.
- `application/` — use cases: `InputController` (desired vs actual key state, game focus, stance), `HeadTracking` (pose → gestures), `App` (facade for the UI: applies and persists settings). External world is reached through interfaces in `ports.py`.
- `infrastructure/` — adapters: camera capture and MediaPipe, preview and OBS output, DirectInput keys, WinAPI foreground window, HUD stance detector, JSON settings.
- `ui/` — PySide6 widgets; `bridge.py` delivers application events to the GUI thread.
- `main.py` — composition root that wires concrete implementations together.
