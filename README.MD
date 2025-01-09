# Head Tilt Control
A PySide6 desktop application that connects to a camera,
monitors head tilt angles, and simulates key presses based on the detected tilt angle.
This project is designed for use with shooter games that have "peek mechanics" like in PUBG.

## Features
- **Head tilt detection**: Real-time monitoring of head angles via a webcam or external camera.
- **User-friendly GUI**: Built with PySide6 for a clean and intuitive interface.
- **Lightweight and fast**: Efficient detection with minimal resource usage.

## Prerequisites
- Python 3.10+

## Getting Started
You can run the application by downloading compiled binaries or
from the command line using the following steps:
1. Clone the repository: `git clone https://github.com/haskir/VRMonitor`
2. Create a virtual environment: `python -m venv venv`
3. Activate the virtual environment: `source venv/bin/activate`
4. Install dependencies: `pip install -r requirements.txt`
5. Download the .dat file from Italojs: https://github.com/italojs/facial-landmarks-recognition
and put it in the same folder as the application.
6. Run the application: `python main.py`

## Usage
- **Camera Selection**: Select the camera to use for head tilt detection.
- **Select Threshold**: Set the threshold for head tilt detection (default: 20).
- **Start/Stop**: Start or stop the head tilt detection.
- **Key Presses**: Simulate key presses based on head tilt angles.
- **Exit**: Close the application.

** Thanks a lot to Italojs and his .dat file.**
https://github.com/italojs/