"""Recording load + replay pacing for Clouseau Live.

Replay is the primary showcase mode (see ../AGENTIC_HANDOFF.md) — at ~25
tokens/sec on the presenter's DGX Spark, a live run can take minutes, so a
recorded run is what carries most booth demonstrations. Live mode (main.py's
/run + /ws/run/{run_id}) uses the exact same event schema, so the frontend
does not need to know which mode produced the stream it's rendering.
"""
import asyncio
import json
from pathlib import Path
from typing import Optional

from fastapi import WebSocket, WebSocketDisconnect

RECORDINGS_DIR = Path(__file__).resolve().parent.parent / "recordings"


def list_recordings() -> list[dict]:
    out = []
    for path in sorted(RECORDINGS_DIR.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        out.append({
            "id": data.get("recording_id", path.stem),
            "file": path.stem,
            "title": data.get("title", path.stem),
            "description": data.get("description", ""),
            "poi": data.get("poi", {}),
            "hosts": data.get("hosts", []),
            "event_count": len(data.get("events", [])),
        })
    return out


def load_recording(recording_id: str) -> Optional[dict]:
    direct = RECORDINGS_DIR / f"{recording_id}.json"
    if direct.exists():
        return json.loads(direct.read_text(encoding="utf-8"))
    for path in RECORDINGS_DIR.glob("*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if data.get("recording_id") == recording_id:
            return data
    return None


async def stream_recording(websocket: WebSocket, recording: dict, speed: float = 1.0) -> None:
    """Emit a recording's events over an already-accepted websocket, honoring
    each event's authored `delayMs` (divided by `speed`)."""
    await websocket.send_json({
        "type": "recording_meta",
        "detail": {
            "poi": recording.get("poi"),
            "hosts": recording.get("hosts"),
            "stages": recording.get("stages"),
            "title": recording.get("title"),
        },
    })
    speed = max(speed, 0.1)
    try:
        for event in recording.get("events", []):
            delay_s = event.get("delayMs", 800) / 1000.0 / speed
            await asyncio.sleep(delay_s)
            await websocket.send_json(event)
    except WebSocketDisconnect:
        return
