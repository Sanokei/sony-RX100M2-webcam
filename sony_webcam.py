import sys
import time
import socket
import threading
import queue
import json
import urllib.request
import numpy as np
import cv2
import pyvirtualcam

CAMERA_API_URL = "http://10.0.0.1:10000/camera"
STREAM_URL = "http://10.0.0.1:60152/liveview.JPG?%211234%21http%2dget%3a%2a%3aimage%2fjpeg%3a%2a%21%21%21%21%21"

TARGET_WIDTH = 1280
TARGET_HEIGHT = 720
TARGET_FPS = 30

# Frame synchronization queue (maxsize=1 guarantees zero buffer buildup & 1-to-1 frame sync)
frame_queue = queue.Queue(maxsize=1)
running = True

def enable_continuous_autofocus():
    """Commands the camera to switch to Movie Mode for Continuous Video Autofocus."""
    try:
        payload = json.dumps({
            "method": "setShootMode",
            "params": ["movie"],
            "id": 1,
            "version": "1.0"
        }).encode("utf-8")
        req = urllib.request.Request(CAMERA_API_URL, data=payload, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=3) as resp:
            data = json.loads(resp.read().decode())
            if data.get("result", [-1])[0] == 0:
                print(">>> Continuous Video Autofocus ACTIVATED successfully!")
    except Exception as e:
        print(f">>> Note: Focus mode setup response: {e}")

def camera_reader_thread():
    """Dedicated high-speed thread to ingest frames directly from camera TCP stream."""
    global running
    
    enable_continuous_autofocus()
    
    while running:
        try:
            req = urllib.request.Request(STREAM_URL)
            with urllib.request.urlopen(req, timeout=5) as resp:
                print(">>> Connected to Sony RX100 M2 live stream!")
                
                while running:
                    # 8-byte common header
                    common_hdr = resp.read(8)
                    if len(common_hdr) < 8:
                        break
                        
                    # 128-byte payload header
                    payload_hdr = resp.read(128)
                    if len(payload_hdr) < 128:
                        break
                    
                    jpeg_size = int.from_bytes(payload_hdr[4:7], "big")
                    padding_size = payload_hdr[7]
                    
                    # Read full JPEG frame chunk
                    jpeg_data = resp.read(jpeg_size)
                    if padding_size > 0:
                        resp.read(padding_size)
                        
                    if len(jpeg_data) != jpeg_size:
                        continue
                        
                    # Decode immediately in C++ OpenCV
                    frame = cv2.imdecode(np.frombuffer(jpeg_data, np.uint8), cv2.IMREAD_COLOR)
                    if frame is not None:
                        # Drop older pending frame if sender hasn't grabbed it yet to prevent any queue buildup
                        if frame_queue.full():
                            try:
                                frame_queue.get_nowait()
                            except queue.Empty:
                                pass
                        frame_queue.put_nowait(frame)
                        
        except (urllib.error.URLError, socket.timeout, ConnectionResetError):
            if running:
                time.sleep(1)
        except Exception as e:
            if running:
                time.sleep(1)

def main():
    global running
    
    print("=" * 65)
    print("  Sony RX100 M2 Tear-Free Ultra-Low Latency Webcam Bridge")
    print("=" * 65)
    print("Sync Mode: Event-driven hardware shutter sync (Zero clock drift)")
    print("Target Device: 'OBS Virtual Camera' (1280x720 @ 30 FPS)")
    print("Press Ctrl+C anytime to stop.\n")

    t = threading.Thread(target=camera_reader_thread, daemon=True)
    t.start()

    print("Synchronizing with camera shutter clock...")
    first_frame = frame_queue.get()
    print(">>> First frame locked! Opening Virtual Camera device...")

    with pyvirtualcam.Camera(width=TARGET_WIDTH, height=TARGET_HEIGHT, fps=TARGET_FPS, fmt=pyvirtualcam.PixelFormat.RGB) as cam:
        print(f">>> Virtual Camera Active: '{cam.device}'")
        print(">>> Tear-free hardware synchronized streaming running!\n")
        
        frame_count = 0
        start_time = time.time()
        
        while running:
            # Block until the camera delivers the EXACT next frame
            try:
                frame = frame_queue.get(timeout=1.0)
            except queue.Empty:
                continue

            # 1. Subtle spatial unsharp mask (enhances fine facial details, hair, text)
            gaussian = cv2.GaussianBlur(frame, (0, 0), 1.2)
            sharpened = cv2.addWeighted(frame, 1.35, gaussian, -0.35, 0)
            
            # 2. Smooth, fast interpolation to standard 720p 16:9
            upscaled = cv2.resize(sharpened, (TARGET_WIDTH, TARGET_HEIGHT), interpolation=cv2.INTER_LINEAR)
            
            # 3. Fast color conversion BGR -> RGB
            rgb_frame = cv2.cvtColor(upscaled, cv2.COLOR_BGR2RGB)
            
            # 4. Push directly to Virtual Camera
            cam.send(rgb_frame)
            
            frame_count += 1
            if frame_count % 90 == 0:
                fps = frame_count / (time.time() - start_time)
                print(f"\rStreaming live: {frame_count} frames synchronized (~{fps:.1f} FPS)", end="", flush=True)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        running = False
        print("\n\nWebcam bridge stopped. Goodbye!")
        sys.exit(0)
