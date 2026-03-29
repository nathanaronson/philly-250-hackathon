"""
Underwater object detector — streams live annotated video over HTTP.

Usage:
    uv run python main.py

Then open a browser on any device on the same network:
    http://<host-ip>:8080

Endpoints:
    /        — annotated live video (MJPEG)
    /debug   — raw foreground mask (MJPEG); white = MOG2 sees something new
    /reset   — re-calibrate (keep scene empty first)
"""

import threading
import time
import random
import cv2
from flask import Flask, Response, redirect, jsonify
import config

from camera.capture import open_camera
from detector.background import BackgroundDetector
from detector.tracker import ObjectTracker
MINE_THRESHOLD = 0.15
CLIPClassifier = None
if config.ENABLE_CLIP:
    from detector.clip_classifier import CLIPClassifier, MINE_THRESHOLD  # noqa: F811
from detector.display import render, _is_mine
import imu as _imu
import geo as _geo

app = Flask(__name__)

_lock = threading.Lock()
_latest_frame: bytes = b""
_latest_mask: bytes = b""
_detector = BackgroundDetector()
_tracker = ObjectTracker()
_clip = None   # CLIPClassifier instance, loaded in background; None until ready
_clip_scores: dict[int, float] = {}
_mine_count: int = 0   # number of confirmed mines in current frame
_object_count: int = 0
_frame_total: int = 0
_capture_fps: float = 0.0
_latest_frame_seq: int = 0
_latest_mask_seq: int = 0
_lat: float = 39.9526
_lon: float = -75.1652
_gps_active: bool = False
_threat_log: dict = {}          # {track_id: {lat, lon, ts}} — one entry per distinct mine


def _load_clip():
    global _clip
    classifier = CLIPClassifier()  # blocks ~30s on first run
    with _lock:
        _clip = classifier


def _gps_loop():
    """Read GPS from serial (Raspberry Pi) or simulate drift as fallback."""
    global _lat, _lon, _gps_active
    try:
        import serial
        import pynmea2
        with serial.Serial("/dev/ttyAMA0", 9600, timeout=1) as ser:
            print("[gps] GPS serial connected")
            _gps_active = True
            while True:
                try:
                    line = ser.readline().decode("ascii", errors="replace").strip()
                    if line.startswith(("$GPRMC", "$GNRMC")):
                        msg = pynmea2.parse(line)
                        if msg.status == "A":
                            with _lock:
                                _lat = msg.latitude
                                _lon = msg.longitude
                            # Nudge IMU yaw from GPS course-over-ground when moving
                            try:
                                cog = float(msg.true_course or 0)
                                spd = float(msg.spd_over_grnd or 0)
                                if spd > 0.3 and cog:
                                    _imu.nudge_yaw(cog)
                            except Exception:
                                pass
                except Exception:
                    pass
    except Exception as e:
        print(f"[gps] No GPS hardware ({e}) — using simulated drift")
        while True:
            with _lock:
                _lat += (random.random() - 0.5) * 0.0002
                _lon += (random.random() - 0.5) * 0.0002
            time.sleep(3)


def _meters_between(lat1, lon1, lat2, lon2):
    import math
    dlat = (lat2 - lat1) * 111320
    dlon = (lon2 - lon1) * 111320 * math.cos(math.radians((lat1 + lat2) / 2))
    return math.sqrt(dlat ** 2 + dlon ** 2)


def _capture_loop():
    global _latest_frame, _latest_mask, _detector, _tracker, _clip_scores, _mine_count, _object_count
    global _frame_total, _capture_fps, _latest_frame_seq, _latest_mask_seq
    global _threat_log
    import traceback

    camera = open_camera()
    _calibration_announced = False
    fps_counter = 0
    fps_window_start = time.monotonic()
    measured_fps = 0.0

    while True:
        try:
            ok, frame = camera.read()
            if not ok or frame is None:
                time.sleep(0.01)
                continue

            with _lock:
                det = _detector
                trk = _tracker
                clip = _clip

            detections = det.process(frame)

            # Announce once when calibration finishes
            if det.is_calibrated and not _calibration_announced:
                print("[detector] Calibration complete — show object now")
                _calibration_announced = True

            objects = trk.update(detections)

            # Offload CLIP scoring to a background thread so it never blocks the capture loop
            for obj in objects:
                if obj.is_confirmed and obj.id not in _clip_scores and clip is not None and __import__('config').ENABLE_CLIP:
                    _clip_scores[obj.id] = None  # reserve slot so we don't spawn twice
                    frame_copy = frame.copy()
                    obj_id, d = obj.id, obj.detection
                    def _score(fc=frame_copy, oid=obj_id, dx=d.x, dy=d.y, dw=d.w, dh=d.h):
                        score = clip.score(fc, dx, dy, dw, dh)
                        label = "MINE" if score >= MINE_THRESHOLD else "non-mine"
                        print(f"[CLIP] track={oid}  score={score:.2f}  → {label}")
                        with _lock:
                            _clip_scores[oid] = score
                    threading.Thread(target=_score, daemon=True).start()

            display = render(
                frame,
                objects,
                clip_scores=_clip_scores,
                is_calibrated=det.is_calibrated,
                calibration_progress=det.calibration_progress,
            )

            _, frame_jpeg = cv2.imencode(
                ".jpg",
                display,
                [cv2.IMWRITE_JPEG_QUALITY, config.STREAM_JPEG_QUALITY],
            )

            mask = det.debug_mask
            if mask is not None:
                _, mask_jpeg = cv2.imencode(".jpg", mask)
                mask_bytes = mask_jpeg.tobytes()
            else:
                mask_bytes = b""

            mines = [o for o in objects if _is_mine(o, _clip_scores, MINE_THRESHOLD)]

            fps_counter += 1
            now = time.monotonic()
            if now - fps_window_start >= 1.0:
                measured_fps = fps_counter / (now - fps_window_start)
                fps_counter = 0
                fps_window_start = now

            with _lock:
                _latest_frame = frame_jpeg.tobytes()
                _latest_mask = mask_bytes
                _latest_frame_seq += 1
                _latest_mask_seq += 1
                _mine_count = len(mines)
                _object_count = len(objects)
                _frame_total += 1
                _capture_fps = measured_fps
                for mine_obj in mines:
                    tid = mine_obj.id
                    if tid not in _threat_log:
                        # Project pixel centroid through camera model to get mine GPS
                        d = mine_obj.detection
                        pitch, roll, yaw = _imu.get_orientation()
                        projected = _geo.project(
                            d.x + d.w / 2, d.y + d.h / 2,
                            _lat, _lon,
                            pitch + config.CAMERA_MOUNT_PITCH_DEG,
                            roll  + config.CAMERA_MOUNT_ROLL_DEG,
                            yaw,
                            config.CAMERA_HEIGHT_M,
                            config.CAMERA_HFOV_DEG,
                            config.CAMERA_VFOV_DEG,
                            config.FRAME_WIDTH,
                            config.FRAME_HEIGHT,
                        )
                        mine_lat, mine_lon = projected if projected else (_lat, _lon)
                        # Proximity check: same physical mine with a new track ID
                        too_close = any(
                            _meters_between(mine_lat, mine_lon, e["lat"], e["lon"]) < 8.0
                            for e in _threat_log.values()
                        )
                        if not too_close:
                            _threat_log[tid] = {"lat": mine_lat, "lon": mine_lon, "ts": time.time()}

        except Exception:
            traceback.print_exc()
            time.sleep(0.1)


def _mjpeg(get_payload):
    last_seq = -1
    while True:
        seq, data = get_payload()
        if not data or seq == last_seq:
            time.sleep(0.01)
            continue
        last_seq = seq
        yield (
            b"--frame\r\n"
            b"Content-Type: image/jpeg\r\n\r\n" + data + b"\r\n"
        )


@app.route("/")
def index():
    return """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>PHILLY 250 // BOTTOM MINE DETECTION</title>
  <style>
    :root {
      --green:  #00ff88;
      --red:    #ff2244;
      --blue:   #00aaff;
      --dim:    #060f1e;
      --panel:  #0b1a2e;
      --border: #163352;
      --mono:   'Courier New', Courier, monospace;
    }
    * { margin: 0; padding: 0; box-sizing: border-box; }

    body {
      background: var(--dim);
      color: var(--green);
      font-family: var(--mono);
      height: 100vh;
      display: grid;
      grid-template-rows: 44px 1fr 28px;
      overflow: hidden;
    }

    /* Scanline overlay */
    body::after {
      content: '';
      position: fixed; inset: 0;
      background: repeating-linear-gradient(
        to bottom,
        transparent 0px, transparent 3px,
        rgba(0,0,0,0.07) 3px, rgba(0,0,0,0.07) 4px
      );
      pointer-events: none;
      z-index: 999;
    }

    /* ── HEADER ── */
    header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 0 20px;
      background: var(--panel);
      border-bottom: 1px solid var(--border);
      flex-shrink: 0;
    }
    .logo {
      font-size: 0.95rem;
      font-weight: bold;
      letter-spacing: 0.25em;
      color: var(--blue);
      text-shadow: 0 0 10px rgba(0,170,255,0.5);
    }
    .logo em { color: var(--green); font-style: normal; }
    .header-right {
      display: flex;
      gap: 20px;
      font-size: 0.65rem;
      color: #3a6080;
      letter-spacing: 0.1em;
    }
    .header-right .val { color: var(--green); }
    #clock { color: var(--blue); }

    /* ── MAIN LAYOUT ── */
    main {
      display: grid;
      grid-template-columns: 1fr 200px;
      gap: 10px;
      padding: 10px;
      min-height: 0;
      overflow: hidden;
    }

    /* ── FEED PANEL ── */
    .feed-wrap {
      position: relative;
      background: #000;
      border: 1px solid var(--border);
      display: flex;
      align-items: center;
      justify-content: center;
      overflow: hidden;
      width: 100%;
      height: 100%;
      transition: border-color 0.2s, box-shadow 0.2s;
    }
    .feed-wrap.threat {
      border-color: var(--red);
      box-shadow: 0 0 0 2px rgba(255,34,68,0.4), inset 0 0 30px rgba(255,34,68,0.08);
      animation: border-pulse 0.5s ease-in-out infinite;
    }
    @keyframes border-pulse {
      0%,100% { box-shadow: 0 0 0 2px rgba(255,34,68,0.5), inset 0 0 30px rgba(255,34,68,0.08); }
      50%      { box-shadow: 0 0 0 4px rgba(255,34,68,0.2), inset 0 0 10px rgba(255,34,68,0.04); }
    }

    .feed-wrap img {
      width: 100%;
      height: 100%;
      object-fit: fill;
      display: block;
    }

    /* Corner brackets */
    .corner {
      position: absolute;
      width: 18px; height: 18px;
      border-color: var(--blue);
      border-style: solid;
      opacity: 0.6;
      pointer-events: none;
      z-index: 2;
    }
    .corner.tl { top:6px;    left:6px;   border-width: 2px 0 0 2px; }
    .corner.tr { top:6px;    right:6px;  border-width: 2px 2px 0 0; }
    .corner.bl { bottom:6px; left:6px;   border-width: 0 0 2px 2px; }
    .corner.br { bottom:6px; right:6px;  border-width: 0 2px 2px 0; }

    /* Status badge on video */
    .feed-badge {
      position: absolute;
      top: 10px; left: 50%;
      transform: translateX(-50%);
      font-size: 0.7rem;
      font-weight: bold;
      letter-spacing: 0.2em;
      padding: 3px 14px;
      border: 1px solid currentColor;
      white-space: nowrap;
      z-index: 3;
      pointer-events: none;
    }
    .feed-badge.clear { color: rgba(0,255,136,0.7); border-color: rgba(0,255,136,0.3); background: rgba(0,255,136,0.04); }
    .feed-badge.mine  { color: var(--red); border-color: var(--red); background: rgba(255,34,68,0.12);
                        animation: badge-flash 0.35s ease-in-out infinite; }
    @keyframes badge-flash { 0%,100% { opacity: 1; } 50% { opacity: 0.6; } }

    /* ── SIDEBAR ── */
    .sidebar {
      display: flex;
      flex-direction: column;
      gap: 8px;
      min-height: 0;
      overflow: hidden;
    }

    .panel {
      background: var(--panel);
      border: 1px solid var(--border);
      padding: 10px;
      flex-shrink: 0;
    }
    .panel.grow { flex: 1; min-height: 0; display: flex; flex-direction: column; }

    .panel-title {
      font-size: 0.58rem;
      letter-spacing: 0.25em;
      color: #2d5070;
      margin-bottom: 8px;
      border-bottom: 1px solid var(--border);
      padding-bottom: 5px;
    }

    /* Threat status */
    .threat-label {
      font-size: 1.4rem;
      font-weight: bold;
      letter-spacing: 0.12em;
      margin-bottom: 8px;
      transition: color 0.3s, text-shadow 0.3s;
    }
    .threat-label.clear { color: var(--green); text-shadow: 0 0 8px rgba(0,255,136,0.4); }
    .threat-label.mine  { color: var(--red);   text-shadow: 0 0 12px rgba(255,34,68,0.7);
                          animation: pulse-label 0.5s ease-in-out infinite; }
    @keyframes pulse-label { 0%,100% { opacity:1; } 50% { opacity:0.55; } }

    .meter-track {
      height: 5px;
      background: rgba(0,0,0,0.4);
      border: 1px solid var(--border);
      margin-bottom: 4px;
      overflow: hidden;
    }
    #meter-fill {
      height: 100%;
      width: 0%;
      background: var(--green);
      transition: width 0.4s, background 0.4s;
    }
    .meter-label { font-size: 0.58rem; color: #2d5070; letter-spacing: 0.1em; }

    /* Stats */
    .stat-row {
      display: flex;
      justify-content: space-between;
      align-items: center;
      font-size: 0.65rem;
      padding: 3px 0;
      border-bottom: 1px solid rgba(22,51,82,0.6);
      color: #2d5070;
      letter-spacing: 0.05em;
    }
    .stat-row:last-child { border-bottom: none; }
    .stat-row .v { color: var(--green); }
    .stat-row.warn .v { color: var(--red); }

    /* Log */
    .log-body {
      flex: 1;
      overflow-y: auto;
      font-size: 0.6rem;
      line-height: 1.7;
      color: #2d5070;
    }
    .log-body .e     { color: #3a6a8a; }
    .log-body .e.thr { color: var(--red); }
    .log-body .e.ok  { color: var(--green); }
    .log-body::-webkit-scrollbar { width: 2px; }
    .log-body::-webkit-scrollbar-thumb { background: var(--border); }

    /* Minimap */
    #minimap {
      display: block;
      width: 100%;
      height: auto;
      background: #020a12;
      border: 1px solid var(--border);
      image-rendering: pixelated;
    }

    /* Reset button */
    #reset-btn {
      background: transparent;
      border: 1px solid var(--border);
      color: #2d5070;
      font-family: var(--mono);
      font-size: 0.65rem;
      letter-spacing: 0.12em;
      padding: 7px;
      width: 100%;
      cursor: pointer;
      transition: all 0.2s;
      flex-shrink: 0;
    }
    #reset-btn:hover { border-color: var(--blue); color: var(--blue); background: rgba(0,170,255,0.04); }

    /* ── FOOTER ── */
    footer {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 0 20px;
      background: var(--panel);
      border-top: 1px solid var(--border);
      font-size: 0.58rem;
      color: #1e3a52;
      letter-spacing: 0.1em;
      flex-shrink: 0;
    }
  </style>
</head>
<body>

<header>
  <div class="logo">PHILLY <em>250</em> &nbsp;//&nbsp; BOTTOM MINE DETECTION</div>
  <div class="header-right">
    <span>SYS&nbsp;<span class="val">ONLINE</span></span>
    <span>FEED&nbsp;<span class="val">LIVE</span></span>
    <span id="clock">--:--:--</span>
  </div>
</header>

<main>
  <div class="feed-wrap" id="feed-wrap">
    <div class="corner tl"></div>
    <div class="corner tr"></div>
    <div class="corner bl"></div>
    <div class="corner br"></div>
    <div class="feed-badge clear" id="feed-badge">SCANNING</div>
    <img id="feed" src="/stream" alt="feed" />
  </div>

  <div class="sidebar">

    <div class="panel">
      <div class="panel-title">// THREAT STATUS</div>
      <div class="threat-label clear" id="threat-label">CLEAR</div>
      <div class="meter-track"><div id="meter-fill"></div></div>
      <div class="meter-label">CONFIDENCE</div>
    </div>

    <div class="panel">
      <div class="panel-title">// TELEMETRY</div>
      <div class="stat-row"><span>OBJECTS</span><span class="v" id="stat-objects">0</span></div>
      <div class="stat-row"><span>THREATS</span><span class="v" id="stat-threats">0</span></div>
      <div class="stat-row"><span>FRAMES</span><span class="v" id="stat-frames">0</span></div>
      <div class="stat-row"><span>FPS</span><span class="v" id="stat-fps">--</span></div>
    </div>

    <div class="panel">
      <div class="panel-title">// POSITION MAP</div>
      <canvas id="minimap" width="180" height="120"></canvas>
    </div>

    <div class="panel grow">
      <div class="panel-title">// EVENT LOG</div>
      <div class="log-body" id="log"></div>
    </div>

    <button id="reset-btn" onclick="resetScan()">[ RECALIBRATE ]</button>

  </div>
</main>

<footer>
  <span>PHILLY 250 HACKATHON</span>
  <span id="coords">LAT: ---.---- &nbsp; LON: ---.----</span>
</footer>

<script>
  const feedImg     = document.getElementById('feed');
  const feedWrap    = document.getElementById('feed-wrap');
  const badge       = document.getElementById('feed-badge');
  const threatLabel = document.getElementById('threat-label');
  const meterFill   = document.getElementById('meter-fill');
  const statObjects = document.getElementById('stat-objects');
  const statThreats = document.getElementById('stat-threats');
  const statFrames  = document.getElementById('stat-frames');
  const statFps     = document.getElementById('stat-fps');
  const log         = document.getElementById('log');
  const clock       = document.getElementById('clock');
  const minimap     = document.getElementById('minimap');
  const mmCtx       = minimap.getContext('2d');
  const MW = minimap.width, MH = minimap.height;

  // Audio
  const actx = new (window.AudioContext || window.webkitAudioContext)();
  let beeping = false;
  function beep() {
    if (beeping) return;
    beeping = true;
    const osc = actx.createOscillator();
    const gain = actx.createGain();
    osc.connect(gain); gain.connect(actx.destination);
    osc.type = 'square';
    osc.frequency.value = 880;
    gain.gain.setValueAtTime(0.12, actx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.001, actx.currentTime + 0.25);
    osc.start(); osc.stop(actx.currentTime + 0.25);
    osc.onended = () => { beeping = false; };
  }

  // Clock
  setInterval(() => { clock.textContent = new Date().toTimeString().slice(0,8); }, 1000);

  // Minimap state
  let currentPos = null;
  let threatPoints = [];

  function drawMinimap() {
    mmCtx.fillStyle = '#020a12';
    mmCtx.fillRect(0, 0, MW, MH);

    const allPts = currentPos ? [...threatPoints, currentPos] : [...threatPoints];
    if (allPts.length === 0) {
      mmCtx.fillStyle = 'rgba(45,80,112,0.4)';
      mmCtx.font = '9px Courier New';
      mmCtx.textAlign = 'center';
      mmCtx.fillText('NO FIX', MW/2, MH/2);
      return;
    }

    // Compute bounds
    let minLat = Infinity, maxLat = -Infinity, minLon = Infinity, maxLon = -Infinity;
    for (const p of allPts) {
      minLat = Math.min(minLat, p.lat); maxLat = Math.max(maxLat, p.lat);
      minLon = Math.min(minLon, p.lon); maxLon = Math.max(maxLon, p.lon);
    }
    // Ensure a minimum range (~100m) so single-point view isn't degenerate
    const minRange = 0.0009;
    if (maxLat - minLat < minRange) { const m = (maxLat+minLat)/2; minLat=m-minRange/2; maxLat=m+minRange/2; }
    if (maxLon - minLon < minRange) { const m = (maxLon+minLon)/2; minLon=m-minRange/2; maxLon=m+minRange/2; }
    // Padding
    const pl = (maxLat-minLat)*0.18, pn = (maxLon-minLon)*0.18;
    minLat-=pl; maxLat+=pl; minLon-=pn; maxLon+=pn;

    function toXY(lat, lon) {
      return [
        (lon-minLon)/(maxLon-minLon)*MW,
        MH - (lat-minLat)/(maxLat-minLat)*MH,
      ];
    }

    // Grid
    mmCtx.strokeStyle = 'rgba(22,51,82,0.5)';
    mmCtx.lineWidth = 0.5;
    for (let i=1; i<4; i++) {
      mmCtx.beginPath(); mmCtx.moveTo(MW*i/4,0); mmCtx.lineTo(MW*i/4,MH); mmCtx.stroke();
      mmCtx.beginPath(); mmCtx.moveTo(0,MH*i/4); mmCtx.lineTo(MW,MH*i/4); mmCtx.stroke();
    }

    // Threat dots (red, persist)
    for (const p of threatPoints) {
      const [x, y] = toXY(p.lat, p.lon);
      mmCtx.beginPath(); mmCtx.arc(x, y, 6, 0, Math.PI*2);
      mmCtx.strokeStyle = 'rgba(255,34,68,0.35)'; mmCtx.lineWidth = 4; mmCtx.stroke();
      mmCtx.beginPath(); mmCtx.arc(x, y, 3.5, 0, Math.PI*2);
      mmCtx.fillStyle = '#ff2244'; mmCtx.fill();
    }

    // Current position (green)
    if (currentPos) {
      const [x, y] = toXY(currentPos.lat, currentPos.lon);
      mmCtx.beginPath(); mmCtx.arc(x, y, 8, 0, Math.PI*2);
      mmCtx.strokeStyle = 'rgba(0,255,136,0.3)'; mmCtx.lineWidth = 3; mmCtx.stroke();
      mmCtx.beginPath(); mmCtx.arc(x, y, 4, 0, Math.PI*2);
      mmCtx.fillStyle = '#00ff88'; mmCtx.fill();
    }
  }

  // Fetch persisted threats from server every 2s
  function refreshThreats() {
    fetch('/threats').then(r => r.json()).then(data => {
      threatPoints = data;
      drawMinimap();
    }).catch(() => {});
  }
  setInterval(refreshThreats, 2000);
  refreshThreats();

  // Log
  let logCount = 0;
  function addLog(msg, cls='') {
    const ts = new Date().toTimeString().slice(0,8);
    const el = document.createElement('div');
    el.className = 'e ' + cls;
    el.textContent = '[' + ts + '] ' + msg;
    log.prepend(el);
    if (++logCount > 40) log.lastChild?.remove();
  }

  // Use MJPEG stream for smoother playback and lower Pi overhead.
  function startStream() {
    feedImg.src = '/stream?t=' + Date.now();
  }
  feedImg.onerror = () => { setTimeout(startStream, 300); };
  startStream();

  // Status polling
  let prevMines = 0, prevCalibrated = false;
  setInterval(() => {
    fetch('/status').then(r => r.json()).then(data => {
      const objects    = data.objects    || 0;
      const mines      = data.mines      || 0;
      const frames     = data.frames     || 0;
      const fps        = data.fps        || 0;
      const calibrated = data.calibrated || false;
      const progress   = data.progress   || 0;
      const lat        = data.lat;
      const lon        = data.lon;

      if (lat != null && lon != null) {
        document.getElementById('coords').textContent =
          'LAT: ' + lat.toFixed(4) + '   LON: ' + lon.toFixed(4);
        currentPos = { lat, lon };
        drawMinimap();
      }

      statObjects.textContent = objects;
      statFrames.textContent = frames;
      statFps.textContent = fps > 0 ? fps.toFixed(1) : '--';

      if (!calibrated) {
        const pct = Math.round(progress * 100);
        badge.textContent       = 'CALIBRATING ' + pct + '%';
        badge.className         = 'feed-badge clear';
        feedWrap.className      = 'feed-wrap';
        threatLabel.textContent = 'STANDBY';
        threatLabel.className   = 'threat-label clear';
        meterFill.style.width      = pct + '%';
        meterFill.style.background = 'var(--blue)';
        prevMines = 0;
        return;
      }

      if (!prevCalibrated) {
        addLog('Calibration complete — scanning', 'ok');
        prevCalibrated = true;
      }

      statThreats.textContent = mines;

      const conf = mines > 0 ? Math.min(55 + mines * 22, 100) : 0;
      meterFill.style.width      = conf + '%';
      meterFill.style.background = mines > 0 ? 'var(--red)' : 'var(--green)';

      if (mines > 0) {
        badge.textContent       = '!! THREAT DETECTED !!';
        badge.className         = 'feed-badge mine';
        feedWrap.className      = 'feed-wrap threat';
        threatLabel.textContent = 'THREAT';
        threatLabel.className   = 'threat-label mine';
        if (prevMines === 0) {
          addLog('THREAT DETECTED — ' + mines + ' object(s)', 'thr');
          beep();
          if (navigator.vibrate) navigator.vibrate([200, 100, 200]);
        }
      } else {
        badge.textContent       = 'SCANNING';
        badge.className         = 'feed-badge clear';
        feedWrap.className      = 'feed-wrap';
        threatLabel.textContent = 'CLEAR';
        threatLabel.className   = 'threat-label clear';
        if (prevMines > 0) addLog('Zone clear', 'ok');
      }
      prevMines = mines;
    }).catch(() => {});
  }, 300);

  function resetScan() {
    fetch('/reset').then(() => {
      addLog('Recalibration initiated — keep scene empty');
      badge.textContent = 'CALIBRATING...';
      badge.className   = 'feed-badge clear';
      feedWrap.className = 'feed-wrap';
    });
  }

  addLog('System online — awaiting calibration');
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


@app.route("/status")
def status():
    with _lock:
        mines = _mine_count
        objects = _object_count
        frames = _frame_total
        fps = _capture_fps
        det = _detector
        lat = _lat
        lon = _lon
    return jsonify({
        "objects": objects,
        "mines": mines,
        "frames": frames,
        "fps": fps,
        "calibrated": det.is_calibrated,
        "progress": det.calibration_progress,
        "lat": lat,
        "lon": lon,
    })


@app.route("/threats")
def threats():
    with _lock:
        log = list(_threat_log.values())
    return jsonify(log)


@app.route("/stream")
def stream():
    return Response(
        _mjpeg(lambda: (_latest_frame_seq, _latest_frame)),
        mimetype="multipart/x-mixed-replace; boundary=frame",
    )


@app.route("/debug")
def debug():
    return Response(
        _mjpeg(lambda: (_latest_mask_seq, _latest_mask)),
        mimetype="multipart/x-mixed-replace; boundary=frame",
    )


@app.route("/reset")
def reset():
    global _detector, _tracker, _clip_scores, _object_count, _mine_count, _frame_total, _capture_fps
    global _latest_frame_seq, _latest_mask_seq
    with _lock:
        _detector = BackgroundDetector()
        _tracker = ObjectTracker()
        _clip_scores = {}
        _object_count = 0
        _mine_count = 0
        _frame_total = 0
        _capture_fps = 0.0
        _latest_frame_seq = 0
        _latest_mask_seq = 0
    print("[main] Reset — tracker cleared.")
    return redirect("/")


if __name__ == "__main__":
    import config as _cfg
    if _cfg.ENABLE_CLIP:
        threading.Thread(target=_load_clip, daemon=True).start()
    else:
        print("[main] CLIP disabled (set ENABLE_CLIP=True in config.py to enable)")
    threading.Thread(target=_imu.imu_loop, daemon=True).start()
    threading.Thread(target=_gps_loop, daemon=True).start()
    threading.Thread(target=_capture_loop, daemon=True).start()
    port = 8080
    print(f"[main] Starting — open http://localhost:{port}")
    if _cfg.ENABLE_CLIP:
        print("[main] CLIP loading in background (~30s on first run)...")
    app.run(host="0.0.0.0", port=port, threaded=True)
