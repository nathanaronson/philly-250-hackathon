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


def _mjpeg_stream():
    import time
    while True:
        with _lock:
            frame = _latest_frame
        if not frame:
            time.sleep(0.05)  # wait for camera to produce first frame
            continue
        yield (
            b"--frame\r\n"
            b"Content-Type: image/jpeg\r\n\r\n" + frame + b"\r\n"
        )


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
            a    { color:#aaa; margin-top:16px; font-family:monospace; }
        </style>
    </head>
    <body>
        <img src="/stream" />
        <a href="/reset">&#8635; Reset calibration</a>
    </body>
    </html>
    """


@app.route("/stream")
def stream():
    return Response(
        _mjpeg_stream(),
        mimetype="multipart/x-mixed-replace; boundary=frame",
    )


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
