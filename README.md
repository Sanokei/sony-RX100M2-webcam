# sony-RX100M2-webcam
Using the RX100M2 WiFi feature as a webcam.

## Use it (release zip)
1. Unzip `SonyWebcam.zip` anywhere.
2. Double-click `Install_Driver.bat` once and accept the administrator prompt. This registers the "Unity Video Capture" virtual camera.
3. On the camera, start its Wi-Fi remote control, then join the camera's network from your PC.
4. Double-click `Start_Sony_Webcam.bat`, then pick **Unity Video Capture** as the camera in Zoom, Discord, OBS, your browser, etc.

`Uninstall_Driver.bat` removes the driver.

No Python or other software is needed. If OBS is already installed, the app falls back to its virtual camera when the driver isn't registered.

## Build the release zip
```
pip install pyinstaller numpy opencv-python pyvirtualcam
Build_Release.bat
```
This produces `release\SonyWebcam.zip`.

## Run from source
```
python sony_webcam.py
```

See [THIRD_PARTY.md](THIRD_PARTY.md) for bundled components.
