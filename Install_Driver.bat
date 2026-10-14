@echo off
rem One-time setup: registers the Unity Capture virtual camera driver.
rem Needs administrator rights; it asks for them itself.
net session >nul 2>&1
if errorlevel 1 (
    powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b
)

set "DEST=%ProgramData%\SonyWebcam"
if not exist "%DEST%" mkdir "%DEST%"
copy /y "%~dp0UnityCaptureFilter64.dll" "%DEST%\" >nul
if errorlevel 1 (
    echo Could not find UnityCaptureFilter64.dll next to this file.
    pause
    exit /b 1
)

regsvr32 /s "%DEST%\UnityCaptureFilter64.dll"
if errorlevel 1 (
    echo Driver registration failed.
    pause
    exit /b 1
)
echo Done. "Unity Video Capture" now appears as a camera in Zoom, Discord, OBS, browsers, etc.
pause
