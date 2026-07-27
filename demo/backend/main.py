"""Clouseau Live backend — FastAPI + WebSocket server.

Two ways to drive the UI, both emitting the same event schema (see
../../artifact/observability.py):

  * Replay (primary showcase — see ../AGENTIC_HANDOFF.md §1):
      GET  /recordings              list bundled/auto-saved recordings
      GET  /recordings/{id}         full recording (metadata + events)
      WS   /ws/replay/{id}?speed=1  paced event stream from a recording

  * Live (proof it's really running locally, on-site hardware):
      GET  /scenarios               scenario catalog (reused from artifact/app.py)
      POST /run                     start a live investigation, returns run_id
      GET  /run/{run_id}/status     poll status
      WS   /ws/run/{run_id}         live event stream; auto-saved as a
                                     recording under ../recordings/ once done

Local demo tool only — CORS is wide open and this is never meant to be
deployed publicly.
"""
import asyncio
import json
import os
import sys
import threading
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import replay

BACKEND_DIR = Path(__file__).resolve().parent
DEMO_DIR = BACKEND_DIR.parent
REPO_ROOT = DEMO_DIR.parent
ARTIFACT_DIR = REPO_ROOT / "artifact"
RECORDINGS_DIR = DEMO_DIR / "recordings"

sys.path.insert(0, str(ARTIFACT_DIR))
os.environ.setdefault("CLOUSEAU_OBSERVABILITY", "1")  # the backend's whole job is to observe

import observability  # noqa: E402  (must follow sys.path insert)

app = FastAPI(title="Clouseau Live backend")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# run_id -> {"status": "queued"|"starting"|"running"|"complete"|"error",
#            "error": str|None, "result": str|None, "thread": Thread}
_active_runs: dict[str, dict] = {}


@app.get("/health")
def health():
    return {"status": "ok", "observability_enabled": observability.is_enabled()}


# ---------------------------------------------------------------- replay ---

@app.get("/recordings")
def get_recordings():
    return replay.list_recordings()


@app.get("/recordings/{recording_id}")
def get_recording(recording_id: str):
    data = replay.load_recording(recording_id)
    if data is None:
        raise HTTPException(status_code=404, detail=f"Recording '{recording_id}' not found.")
    return data


@app.websocket("/ws/replay/{recording_id}")
async def ws_replay(websocket: WebSocket, recording_id: str, speed: float = 1.0):
    await websocket.accept()
    data = replay.load_recording(recording_id)
    if data is None:
        await websocket.send_json({"type": "error", "detail": f"Recording '{recording_id}' not found."})
        await websocket.close()
        return
    await replay.stream_recording(websocket, data, speed=speed)
    await websocket.close()


# ------------------------------------------------------------ live runs ---

class RunRequest(BaseModel):
    scenario_name: str
    poi_type: str          # "IP" | "domain" | "file" | "C1" | "C2" | "C3"
    darpa: bool = False
    host_label: Optional[str] = None


def _scenario_catalog() -> dict:
    """Reuse the exact scenario definitions the CLI (app.py) uses, so the demo
    never drifts from the research harness's data. Imported lazily — app.py
    pulls in prompts/constants at module scope, which is heavier than
    endpoints that don't need it (e.g. /health, replay-only usage)."""
    import app as clouseau_app
    return {
        "si": clouseau_app.si_scn, "mi": clouseau_app.ml_scn,
        "se": clouseau_app.se_scn, "ss": clouseau_app.ss_scn, "optc": clouseau_app.optc_scn,
    }


@app.get("/scenarios")
def list_scenarios():
    out = []
    for group, scns in _scenario_catalog().items():
        for s in scns:
            out.append({"group": group, "name": s["name"], "poi_types": [p[1] for p in s["poi"]]})
    return out


def _find_scenario(scenario_name: str) -> Optional[dict]:
    for scns in _scenario_catalog().values():
        for s in scns:
            if s["name"] == scenario_name:
                return s
    return None


def _fail(run_id: str, message: str) -> None:
    _active_runs[run_id]["status"] = "error"
    _active_runs[run_id]["error"] = message
    observability.emit(run_id, "run_complete", role="system", agent_id="system", narration=f"Could not start: {message}")
    observability.get_queue(run_id).put(None)


def _run_investigation(run_id: str, scenario_name: str, poi_type: str, darpa: bool, host_label: Optional[str]) -> None:
    from llm_factory import create_llm_from_env, LLMConfigError
    from chief_inspector import investigate_atlas, investigate_optc
    import constants

    _active_runs[run_id]["status"] = "starting"
    try:
        llm, _provider = create_llm_from_env(
            model=os.environ.get("LLM_MODEL"),
            api_key=os.environ.get("API_KEY"),
            base_url=os.environ.get("BASE_URL"),
        )
    except LLMConfigError as exc:
        _fail(run_id, str(exc))
        return

    scenario = _find_scenario(scenario_name)
    if scenario is None:
        _fail(run_id, f"Unknown scenario '{scenario_name}'.")
        return

    clue = next((p[0] for p in scenario["poi"] if p[1] == poi_type), None)
    if clue is None:
        _fail(run_id, f"Scenario '{scenario_name}' has no point of interest of type '{poi_type}'.")
        return

    scenario_path = str((ARTIFACT_DIR / scenario["path"]).resolve())
    configs = {
        "data_path": scenario_path,
        "db_name": os.path.join(scenario_path, "scenario.db"),
        "clue": clue,
        "test_name": f"{scenario['name']}_{poi_type}",
        "run_id": run_id,
        "host_label": host_label or scenario["name"],
        "max_investigations": constants.DEFAULT_INVESTIGATIONS,
        "max_questions": constants.DEFAULT_QUESTIONS,
        "max_queries": constants.DEFAULT_QUERIES,
        "max_tokens": constants.DEFAULT_MAX_TOKENS,
    }

    _active_runs[run_id]["status"] = "running"
    try:
        result = investigate_optc(llm=llm, configs=configs) if darpa else investigate_atlas(llm=llm, configs=configs)
        _active_runs[run_id]["status"] = "complete"
        _active_runs[run_id]["result"] = result
    except Exception as exc:  # noqa: BLE001 — surface any failure to the UI rather than hang it
        _fail(run_id, str(exc))


@app.post("/run")
def start_run(req: RunRequest):
    run_id = observability.new_run_id()
    _active_runs[run_id] = {"status": "queued", "error": None, "result": None}
    thread = threading.Thread(
        target=_run_investigation,
        args=(run_id, req.scenario_name, req.poi_type, req.darpa, req.host_label),
        daemon=True,
    )
    _active_runs[run_id]["thread"] = thread
    thread.start()
    return {"run_id": run_id}


@app.get("/run/{run_id}/status")
def run_status(run_id: str):
    info = _active_runs.get(run_id)
    if info is None:
        raise HTTPException(status_code=404, detail="Unknown run_id.")
    return {"status": info["status"], "error": info.get("error")}


def _save_recording(run_id: str, events: list) -> None:
    """Every live run is automatically saved as a recording — today's live
    demo is tomorrow's reliable replay."""
    if not events:
        return
    RECORDINGS_DIR.mkdir(parents=True, exist_ok=True)
    poi = events[0].get("detail", {}).get("poi", "")
    recording = {
        "recording_id": run_id,
        "title": f"Live run — {poi or run_id}",
        "description": "Auto-recorded from a live investigation.",
        "poi": {"value": poi},
        "hosts": sorted({e["host"] for e in events if e.get("host")}),
        "stages": observability.STAGES,
        "events": events,
    }
    (RECORDINGS_DIR / f"{run_id}.json").write_text(
        json.dumps(recording, ensure_ascii=False, indent=2), encoding="utf-8"
    )


@app.websocket("/ws/run/{run_id}")
async def ws_run(websocket: WebSocket, run_id: str):
    await websocket.accept()
    if run_id not in _active_runs:
        await websocket.send_json({"type": "error", "detail": "Unknown run_id."})
        await websocket.close()
        return

    q = observability.get_queue(run_id)
    recorded: list = []
    loop = asyncio.get_event_loop()
    try:
        while True:
            event = await loop.run_in_executor(None, q.get)
            if event is None:
                break
            recorded.append(event)
            await websocket.send_json(event)
    except WebSocketDisconnect:
        pass
    finally:
        _save_recording(run_id, recorded)
    await websocket.close()
