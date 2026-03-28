#!/usr/bin/env python3
from __future__ import annotations

import datetime as dt
import os
from typing import Any

from flask import Flask, jsonify, request

app = Flask(__name__)
MESSAGES: list[dict[str, Any]] = []


@app.get("/health")
def health() -> tuple[dict[str, str], int]:
    return {"status": "ok"}, 200


@app.post("/ingest")
def ingest() -> tuple[dict[str, Any], int]:
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return {"ok": False, "error": "Expected JSON object"}, 400

    line = str(data.get("line", ""))
    device = str(data.get("device", "unknown"))
    source = str(data.get("source", "unknown"))
    millis = data.get("millis")

    entry = {
        "received_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "remote_addr": request.remote_addr,
        "device": device,
        "source": source,
        "millis": millis,
        "line": line,
    }
    MESSAGES.append(entry)

    print(
        f"[INGEST] device={device} source={source} remote={request.remote_addr} "
        f"millis={millis} line={line}"
    )

    return {"ok": True, "stored": len(MESSAGES)}, 200


@app.get("/messages")
def messages() -> tuple[dict[str, Any], int]:
    limit_raw = request.args.get("limit", "50")
    try:
        limit = max(1, min(500, int(limit_raw)))
    except ValueError:
        return {"ok": False, "error": "limit must be an integer"}, 400

    return {"ok": True, "count": len(MESSAGES), "messages": MESSAGES[-limit:]}, 200


if __name__ == "__main__":
    host = os.environ.get("FLASK_HOST", "0.0.0.0")
    port = int(os.environ.get("FLASK_PORT", "5000"))
    app.run(host=host, port=port, debug=False)
