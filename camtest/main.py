"""
Bare-bones camera test — streams raw camera feed over HTTP.
No detection, no processing, just the camera.

Usage:
    cd camtest && uv run python main.py

Then open:  http://<ip>:8081
"""

import subprocess
import threading
import time

import cv2
import numpy as np
from flask import Flask, Response

FRAME_WIDTH = 1280
FRAME_HEIGHT = 720
FRAME_RATE = 30
PORT = 8081

app = Flask(__name__)
_lock = threading.Lock()
_latest_frame: bytes = b""


# ── Camera ──────────────────────────────────────────────

def _is_raspberry_pi() -> bool:
    try:
        with open("/proc/device-tree/model") as f:
            return "Raspberry Pi" in f.read()
    except FileNotFoundError:
        return False


class PiCamera:
    def __init__(self):
        self._w = FRAME_WIDTH
        self._h = FRAME_HEIGHT
        self._frame_bytes = self._w * self._h * 3 // 2

        for cmd in ("rpicam-vid", "libcamera-vid"):
            try:
                self._proc = subprocess.Popen(
                    [
                        cmd,
                        "--width", str(self._w),
                        "--height", str(self._h),
                        "--framerate", str(FRAME_RATE),
                        "--codec", "yuv420",
                        "--output", "-",
                        "--nopreview",
                        "--timeout", "0",
                    ],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL,
                )
                print(f"[camera] Started {cmd}")
                time.sleep(2)
                return
            except FileNotFoundError:
                continue
        raise RuntimeError("rpicam-vid / libcamera-vid not found")

    def read(self):
        raw = self._proc.stdout.read(self._frame_bytes)
        if len(raw) < self._frame_bytes:
            return False, None
        yuv = np.frombuffer(raw, dtype=np.uint8).reshape((self._h * 3 // 2, self._w))
        return True, cv2.cvtColor(yuv, cv2.COLOR_YUV2BGR_I420)


class WebcamCamera:
    def __init__(self):
        self._cap = cv2.VideoCapture(0)
        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, FRAME_WIDTH)
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, FRAME_HEIGHT)
        self._cap.set(cv2.CAP_PROP_FPS, FRAME_RATE)
        if not self._cap.isOpened():
            raise RuntimeError("Could not open webcam")
        print("[camera] Opened webcam")

    def read(self):
        return self._cap.read()


def open_camera():
    if _is_raspberry_pi():
        return PiCamera()
    return WebcamCamera()


# ── Capture loop ────────────────────────────────────────

def _capture_loop():
    global _latest_frame
    import traceback

    camera = open_camera()
    frame_num = 0

    while True:
        try:
            ok, frame = camera.read()
            if not ok or frame is None:
                time.sleep(0.01)
                continue

            frame_num += 1
            _, jpeg = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 80])

            with _lock:
                _latest_frame = jpeg.tobytes()

            if frame_num % 100 == 0:
                print(f"[camera] {frame_num} frames captured")

        except Exception:
            traceback.print_exc()
            time.sleep(0.1)


# ── Routes ──────────────────────────────────────────────

@app.route("/")
def index():
    return """<!DOCTYPE html>
<html>
<head>
  <title>Camera Test</title>
  <style>
    body { margin:0; background:#000; display:flex; align-items:center;
           justify-content:center; height:100vh; font-family:monospace; }
    img  { max-width:100%; max-height:100vh; }
    #info { position:fixed; top:10px; left:10px; color:#0f0; font-size:14px; }
  </style>
</head>
<body>
  <div id="info">FPS: <span id="fps">--</span></div>
  <img id="feed" />
  <script>
    const feed = document.getElementById('feed');
    const fpsEl = document.getElementById('fps');
    let count = 0, last = Date.now();
    function poll() {
      const img = new Image();
      img.onload = function() {
        feed.src = img.src;
        count++;
        const now = Date.now();
        if (now - last >= 1000) {
          fpsEl.textContent = Math.round(count * 1000 / (now - last));
          count = 0;
          last = now;
        }
        poll();
      };
      img.onerror = function() { setTimeout(poll, 200); };
      img.src = '/frame?t=' + Date.now();
    }
    poll();
  </script>
</body>
</html>"""


@app.route("/frame")
def frame():
    with _lock:
        data = _latest_frame
    if not data:
        return Response(status=204)
    return Response(data, mimetype="image/jpeg")


@app.route("/stream")
def stream():
    def gen():
        while True:
            with _lock:
                data = _latest_frame
            if not data:
                time.sleep(0.05)
                continue
            yield (b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + data + b"\r\n")
    return Response(gen(), mimetype="multipart/x-mixed-replace; boundary=frame")


if __name__ == "__main__":
    threading.Thread(target=_capture_loop, daemon=True).start()
    print(f"[camtest] Open http://localhost:{PORT}")
    app.run(host="0.0.0.0", port=PORT, threaded=True)
