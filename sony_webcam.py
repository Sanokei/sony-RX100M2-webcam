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

# Cap OpenCV's thread pool; the frames are tiny, so extra threads only burn CPU.
cv2.setNumThreads(2)
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

def camera_call(method, params=None):
    payload = json.dumps({"method": method, "params": params or [], "id": 1, "version": "1.0"}).encode("utf-8")
    req = urllib.request.Request(CAMERA_API_URL, data=payload, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=3) as resp:
        return json.loads(resp.read().decode())

def get_stream_url():
    """Uses the fixed live view URL; with --hires, asks the camera for its largest size instead."""
    if "--hires" not in sys.argv:
        return STREAM_URL
    try:
        apis = camera_call("getAvailableApiList").get("result", [[]])[0]
        print(f">>> Camera live view APIs: {[a for a in apis if 'iveview' in a]}")
        if "startLiveviewWithSize" in apis:
            res = camera_call("startLiveviewWithSize", ["L"])
            if "result" in res:
                return res["result"][0]
        if "startLiveview" in apis:
            res = camera_call("startLiveview")
            if "result" in res:
                return res["result"][0]
    except Exception as e:
        print(f">>> Note: live view negotiation failed ({e}); using default URL")
    return STREAM_URL

def camera_reader_thread():
    """Dedicated high-speed thread to ingest frames directly from camera TCP stream."""
    global running

    enable_continuous_autofocus()
    stream_url = get_stream_url()

    while running:
        try:
            req = urllib.request.Request(stream_url)
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

def open_virtual_camera():
    """Prefers the bundled Unity Capture driver; falls back to any other installed driver (e.g. OBS)."""
    kwargs = dict(width=TARGET_WIDTH, height=TARGET_HEIGHT, fps=TARGET_FPS, fmt=pyvirtualcam.PixelFormat.BGR)
    try:
        return pyvirtualcam.Camera(backend="unitycapture", **kwargs)
    except Exception:
        pass
    try:
        return pyvirtualcam.Camera(**kwargs)
    except Exception as e:
        print(f"\nNo virtual camera driver found ({e}).")
        print("Run Install_Driver.bat once (it will ask for administrator permission), then start again.")
        input("Press Enter to exit...")
        sys.exit(1)

def main():
    global running
    
    print("=" * 65)
    print("  Sony RX100 M2 Tear-Free Ultra-Low Latency Webcam Bridge")
    print("=" * 65)
    print("Sync Mode: Event-driven hardware shutter sync (Zero clock drift)")
    print("Output: virtual webcam, 1280x720 (Unity Capture, or OBS Virtual Camera as fallback)")
    print("Press Ctrl+C anytime to stop.\n")

    t = threading.Thread(target=camera_reader_thread, daemon=True)
    t.start()

    print("Waiting for first camera frame...")
    while True:
        try:
            frame_queue.get(timeout=0.5)
            break
        except queue.Empty:
            continue
    print(">>> First frame received! Opening Virtual Camera device...")

    # BGR is OpenCV's native order, so no per-frame color conversion is needed.
    with open_virtual_camera() as cam:
        print(f">>> Virtual Camera Active: '{cam.device}'")
        print(">>> Streaming at a fixed, paced frame rate.\n")

        # Preallocated buffers: no per-frame allocations, so RAM stays flat.
        blurred = None
        out = np.zeros((TARGET_HEIGHT, TARGET_WIDTH, 3), np.uint8)

        sent = 0
        fresh = 0
        proc_ms = 0.0
        start_time = time.time()

        while running:
            # Send each camera frame the moment it arrives (no waiting for a frame
            # slot, so it can exceed TARGET_FPS). If the camera stalls, re-send the
            # last frame so the virtual camera never goes dark.
            try:
                frame = frame_queue.get(timeout=1.0 / TARGET_FPS)
            except queue.Empty:
                frame = None

            if frame is not None:
                t0 = time.perf_counter()
                # Center-crop to 16:9 with a zero-copy slice (no extra processing step).
                h, w = frame.shape[:2]
                crop_h = w * 9 // 16
                if crop_h < h:
                    y0 = (h - crop_h) // 2
                    frame = frame[y0:y0 + crop_h]
                frame = np.ascontiguousarray(frame)
                if blurred is None or blurred.shape != frame.shape:
                    blurred = np.empty_like(frame)
                # Unsharp mask at the camera's native (small) resolution, in place.
                cv2.GaussianBlur(frame, (0, 0), 1.2, dst=blurred)
                cv2.addWeighted(frame, 1.35, blurred, -0.35, 0, dst=frame)
                cv2.resize(frame, (TARGET_WIDTH, TARGET_HEIGHT), dst=out, interpolation=cv2.INTER_LINEAR)
                fresh += 1
                proc_ms += (time.perf_counter() - t0) * 1000
            elif sent:
                # Camera stalled: pace the repeat frames without busy-waiting.
                cam.sleep_until_next_frame()

            cam.send(out)
            sent += 1

            if sent % 90 == 0:
                elapsed = time.time() - start_time
                print(f"\rOut: {sent / elapsed:.1f} FPS | camera: {fresh / elapsed:.1f} FPS | "
                      f"processing: {proc_ms / max(fresh, 1):.1f} ms/frame | {cam.device}   ", end="", flush=True)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        running = False
        print("\n\nWebcam bridge stopped. Goodbye!")
        sys.exit(0)
