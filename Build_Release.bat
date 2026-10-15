@echo off
rem Builds release\SonyWebcam\ (and a zip) that runs on a PC with nothing installed.
rem Build machine needs Python 3.10+; run once: pip install pyinstaller numpy opencv-python pyvirtualcam
cd /d "%~dp0"
python -m PyInstaller --noconfirm --clean --onedir --name SonyWebcam ^
    --collect-all pyvirtualcam ^
    --exclude-module tkinter --exclude-module matplotlib --exclude-module pandas ^
    sony_webcam.py
if errorlevel 1 (
    echo Build failed.
    pause
    exit /b 1
)

rmdir /s /q release >nul 2>&1
mkdir release
xcopy /e /i /q dist\SonyWebcam release\SonyWebcam >nul
copy /y UnityCaptureFilter64.dll release\SonyWebcam\ >nul
copy /y Install_Driver.bat release\SonyWebcam\ >nul
copy /y Uninstall_Driver.bat release\SonyWebcam\ >nul
copy /y LICENSE release\SonyWebcam\ >nul
copy /y THIRD_PARTY.md release\SonyWebcam\ >nul
(
    echo @echo off
    echo title Sony RX100 M2 Webcam
    echo SonyWebcam.exe %%*
    echo pause
) > release\SonyWebcam\Start_Sony_Webcam.bat

powershell -NoProfile -Command "Compress-Archive -Force -Path release\SonyWebcam -DestinationPath release\SonyWebcam.zip"
echo.
echo Done: release\SonyWebcam.zip
pause
