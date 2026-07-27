"""Event bus for the Clouseau Live demo UI (see ../demo/).

Streams a structured play-by-play of what the Chief Inspector, Investigators,
and QA agents are doing so a real-time UI can render it. Entirely inert unless
CLOUSEAU_OBSERVABILITY=1 is set — every public function is a no-op otherwise,
so normal evaluation runs (claims/, app.py) are unaffected.

Event shape (dict, JSON-serializable):
    run_id, seq, ts, type, role, agent_id, host, stage, narration, detail

`type` is one of: run_started, chief_thinking, lead_dispatched,
investigator_started, qa_question, sql_query, sql_result, artifact_found,
pivot_found, investigator_summary, chief_reflection, eval_started,
final_report, metrics, run_complete.
"""
import os
import queue
import threading
import time
import uuid
from typing import Any, Dict, List, Optional

from langchain_core.callbacks import BaseCallbackHandler

STAGES = [
    "Initial Access", "Execution", "Command & Control", "Discovery",
    "Lateral Movement", "Persistence", "Collection", "Exfiltration",
]

_lock = threading.Lock()
_queues: Dict[str, "queue.Queue[Optional[dict]]"] = {}
_seq_counters: Dict[str, int] = {}


def is_enabled() -> bool:
    return os.environ.get("CLOUSEAU_OBSERVABILITY") == "1"


def new_run_id() -> str:
    return uuid.uuid4().hex[:12]


def get_queue(run_id: str) -> "queue.Queue[Optional[dict]]":
    """Consumer-side handle (used by demo/backend). Creating a queue here does
    not enable emission — that still requires CLOUSEAU_OBSERVABILITY=1."""
    with _lock:
        return _queues.setdefault(run_id, queue.Queue())


def emit(run_id: Optional[str], type_: str, role: str, agent_id: str,
         host: Optional[str] = None, stage: Optional[str] = None,
         narration: str = "", detail: Optional[dict] = None) -> None:
    if not is_enabled() or not run_id:
        return
    with _lock:
        seq = _seq_counters.get(run_id, 0) + 1
        _seq_counters[run_id] = seq
        q = _queues.setdefault(run_id, queue.Queue())
    q.put({
        "run_id": run_id,
        "seq": seq,
        "ts": time.time(),
        "type": type_,
        "role": role,
        "agent_id": agent_id,
        "host": host,
        "stage": stage,
        "narration": narration,
        "detail": detail or {},
    })


def start_run(run_id: str, poi: str, poi_type: str = "", hosts: Optional[List[str]] = None) -> None:
    label = f"{poi_type + ' ' if poi_type else ''}{poi}".strip()
    emit(run_id, "run_started", role="system", agent_id="system",
         narration=f"Investigation started. Point of interest: {label}.",
         detail={"poi": poi, "poi_type": poi_type, "hosts": hosts or []})


def end_run(run_id: str) -> None:
    emit(run_id, "run_complete", role="system", agent_id="system",
         narration="Investigation complete.")
    if not is_enabled():
        return
    q = _queues.get(run_id)
    if q is not None:
        q.put(None)  # sentinel: signals a streaming consumer that the run has ended


def infer_stage(event_type: str, detail: dict) -> Optional[str]:
    """Deterministic, rule-based APT kill-chain classifier — no extra LLM call.
    At ~25 tok/s on-site, spending model tokens on presentation metadata isn't
    affordable, so this is a plain keyword/type lookup, not a judgment call."""
    if event_type == "pivot_found":
        return "Lateral Movement"
    if event_type != "artifact_found":
        return None
    text = " ".join(str(v) for v in detail.values()).lower()
    artifact_type = detail.get("artifact_type", "")
    if any(k in text for k in ("service", "scheduled task", "registry run", "startup")):
        return "Persistence"
    if any(k in text for k in ("zip", "archive", "7z", "rar", "staged", "compressed")):
        return "Collection"
    if any(k in text for k in ("exfil", "uploaded", "transferred", "sent to")):
        return "Exfiltration"
    if artifact_type in ("address", "ip") or any(k in text for k in ("beacon", "c2", "command and control")):
        return "Command & Control"
    if artifact_type == "domain" or any(k in text for k in ("phish", "download")):
        return "Initial Access"
    if artifact_type == "process":
        return "Execution"
    return "Discovery"


class ThinkingPulseCallback(BaseCallbackHandler):
    """Attach via graph.invoke(config={"callbacks": [...]}) to emit a
    lightweight 'thinking' pulse the instant a model call starts. At ~25 tok/s
    a single generation can take many seconds; without this the UI looks
    frozen between semantic events emitted after a call returns."""

    def __init__(self, run_id: str, role: str, agent_id: str, host: Optional[str] = None):
        self.run_id = run_id
        self.role = role
        self.agent_id = agent_id
        self.host = host

    def on_llm_start(self, serialized: Dict[str, Any], prompts: List[str], **kwargs: Any) -> None:
        emit(self.run_id, f"{self.role}_thinking", role=self.role, agent_id=self.agent_id,
             host=self.host, narration=f"{self.agent_id} is thinking…")
