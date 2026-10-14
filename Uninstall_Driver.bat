@echo off
net session >nul 2>&1
if errorlevel 1 (
    powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b
)

set "DEST=%ProgramData%\SonyWebcam"
regsvr32 /s /u "%DEST%\UnityCaptureFilter64.dll"
del /q "%DEST%\UnityCaptureFilter64.dll" >nul 2>&1
rmdir "%DEST%" >nul 2>&1
echo Driver removed.
pause
