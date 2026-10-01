@echo off
rem Сборка VRMonitor через Nuitka (см. build.ps1)
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0build.ps1"
pause
