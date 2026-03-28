"""
Underwater object detector — streams live annotated video over HTTP.

Usage:
    uv run python main.py

Then open a browser on any device on the same network:
    http://<pi-ip>:5000

Controls (keyboard not available in browser — use these endpoints):
    GET /reset   — re-calibrate (keep tank empty first)
"""

import threading
import cv2
from flask import Flask, Response, redirect

from camera.capture import open_camera
from detector.background import BackgroundDetector
from detector.display import render

app = Flask(__name__)

# Shared state between the capture thread and Flask
_lock = threading.Lock()
_latest_frame: bytes = b""
_detector = BackgroundDetector()


def _capture_loop():
    global _latest_frame, _detector
    camera = open_camera()
    while True:
        ok, frame = camera.read()
        if not ok or frame is None:
            continue

        with _lock:
            det = _detector
        detections = det.process(frame)
        display = render(
            frame,
            detections,
            is_calibrated=det.is_calibrated,
            calibration_progress=det.calibration_progress,
        )

        _, jpeg = cv2.imencode(".jpg", display, [cv2.IMWRITE_JPEG_QUALITY, 70])
        with _lock:
            _latest_frame = jpeg.tobytes()



@app.route("/")
def index():
    return """
    <html>
    <head>
        <title>Underwater Detector</title>
        <style>
            body { background:#111; display:flex; flex-direction:column;
                   align-items:center; justify-content:center; min-height:100vh; margin:0; }
            img  { max-width:100%; border:2px solid #333; }
            a    { color:#aaa; margin-top:16px; font-family:monospace; font-size:18px; }
        </style>
    </head>
    <body>
        <img id="feed" src="/frame" />
        <a href="/reset">&#8635; Reset calibration</a>
        <script>
            const img = document.getElementById('feed');
            setInterval(() => {
                img.src = '/frame?t=' + Date.now();
            }, 100);
        </script>
    </body>
    </html>
    """


@app.route("/frame")
def frame():
    with _lock:
        data = _latest_frame
    if not data:
        return Response(status=204)
    return Response(data, mimetype="image/jpeg")


@app.route("/reset")
def reset():
    global _detector
    with _lock:
        _detector = BackgroundDetector()
    print("[main] Background model reset — keep tank empty.")
    return redirect("/")


if __name__ == "__main__":
    t = threading.Thread(target=_capture_loop, daemon=True)
    t.start()
    print("[main] Starting — open http://<this-device-ip>:5000 in a browser")
    app.run(host="0.0.0.0", port=5000, threaded=True)
