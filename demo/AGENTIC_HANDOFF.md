# Clouseau Live — Agentic Handoff & Build Plan

> **Purpose of this file:** a self-contained handoff surface so any agent (or human)
> can pick up the "Clouseau Live" demo build **cold**, understand the goal, the
> constraints, the architecture, and the exact next task — without re-reading the
> whole codebase. Update the **Status Log** at the bottom after every work session.

---

## 1. What we are building & why

A **real-time observability UI** on top of Clouseau (the hierarchical multi-agent
attack-investigation system in [`../artifact/`](../artifact/)). It lets a live
audience *watch the AI agents reconstruct a multi-stage / APT attack*, step by step,
while everything runs **100% locally** (no cloud).

**Exhibition context:** NCSC (Ireland) Research & Education Exhibition.
We represent the **Nimbus Research Centre** (institutional stand — a *guided,
talked-over* demo, not an unattended 3-day kiosk). Audience is **broad / non-technical**,
so plain-English narration is a first-class requirement, not an afterthought.

**The story we are telling:** an autonomous forensic agent, running on sovereign
local hardware, reconstructs a **multi-stage APT** — from an initial point of
interest, through exploitation and payload delivery, to **lateral movement across
hosts** — and produces a verifiable narrative with measured accuracy.

## 2. Hard constraints (design around these)

| Constraint | Implication for the build |
|---|---|
| **Hardware: DGX Spark, ~25 tokens/sec** | Live runs take **minutes**, not seconds. Token efficiency is load-bearing. Keep Batch-1 optimizations ON. Narration must keep the audience engaged during think-time. |
| **Demo modes: Live + Replay** | Build the event stream **once**; drive it from either a live run or a recorded run. **Replay is the primary showcase** (fast, reliable); **live is the "it's really running locally" proof**. |
| **Booth hardware: presenter's GPU laptop / DGX Spark** | Live local inference is feasible on-site. Assume **no venue internet** — everything offline. |
| **UI: polished React + Vite SPA** | Proper graph library for the attack-reconstruction visual (React Flow or Cytoscape). |
| **Audience: broad / plain English** | Every event carries a human-readable narration string. Technical detail is available but collapsible. |
| **Must not disturb research code** | All new code in `demo/`. Core `artifact/` files get only tiny, **env-guarded** hooks (`CLOUSEAU_OBSERVABILITY=1`). Flag OFF ⇒ behaviour byte-identical to today (eval runs unaffected). |

## 3. Hero scenario & the two demo narratives (both supported, shown one at a time)

The UI must be able to present **either** of two narratives — as **switchable
views/modes**, NOT overlaid simultaneously (keep each screen focused for a broad
audience):

1. **Multi-stage attack reconstruction view** — the causal chain itself: the
   attack-reconstruction graph building node-by-node (entry point → exploited
   process → payload → C2 → pivot to next host), driven by `artifact_found` /
   `pivot_found` events.
2. **APT kill-chain view** — the *strategic* framing: a stage timeline
   (Initial Access → Execution → Command & Control → Lateral Movement →
   Exfiltration) that lights up as findings are classified into stages. Stage
   classification is **deterministic/rule-based** in the narration translator
   (event type + artifact type → stage), NOT an extra LLM call — at 25 tps we
   cannot afford extra tokens for presentation logic.

Both views are fed by the **same event stream** — this is purely a presentation
toggle (a view switcher in the UI), so there is no extra backend cost. The
presenter picks whichever story suits the visitor.

Use a **multi-host M-series scenario (M1–M6)** as the primary demo — lateral
movement is the clearest visual proof of both stories. Keep one fast
**single-host (S-series)** scenario as a short "quick demo" option. Scenarios are
defined in [`../artifact/app.py`](../artifact/app.py) (`ml_scn`, `si_scn`).

**⚠ Validation findings (2026-07-27):**
- **M-scenario data is NOT on this dev machine** — `artifact/scenarios/` contains
  only S/SE/SS dirs. M1–M6 DBs must be obtained/built (they live on the DGX or
  external storage; `scenario.csv`/`*.db` are gitignored). Blocker for Phase 3+
  hero-demo testing; S-series is sufficient for Phases 0–2.
- **Clouseau runs each host separately** (`m1h1`, `m1h2` are independent runs
  against separate DBs — see `ml_scn` in app.py). Cross-host reconstruction is
  therefore a *demo-orchestration* concern: the backend needs a **campaign mode**
  that runs h1, extracts pivot artifacts from its report, feeds them as the lead
  for h2, and stitches both runs into ONE reconstruction graph in the UI.

## 4. Architecture (3 layers)

```
demo/
  backend/            FastAPI + WebSocket server, run controller, recorder, replay player
  frontend/           React + Vite SPA (the booth UI)
  recordings/         Saved event streams (*.json) for replay
  AGENTIC_HANDOFF.md  <-- this file
../artifact/
  observability.py    NEW: event bus + LangChain callback handler (env-guarded)
```

**Layer A — Instrumentation** (`artifact/observability.py`)
- An **event bus** + a LangChain `BaseCallbackHandler` (same pattern as the existing
  [`../artifact/debug_callback.py`](../artifact/debug_callback.py)). Attach via
  `graph.invoke(..., config={"callbacks":[handler]})` to capture LLM/tool start-end
  at every graph node with **near-zero edits**.
- A few **semantic hooks** (~5–10 lines each, guarded by `CLOUSEAU_OBSERVABILITY=1`)
  at points that already exist, to emit *meaningful* events (which agent, which host,
  which artifact) instead of raw tokens:
  - `investigate_lead` dispatch — [`../artifact/chief_inspector.py`](../artifact/chief_inspector.py) (~L40 / `call_tool`)
  - `run_sql_query` — [`../artifact/qa_agent.py`](../artifact/qa_agent.py)
  - final report emission — `ClouseauRun` in chief_inspector.py
  - reuse existing `log_tool_event` points in [`../artifact/handoff_logger.py`](../artifact/handoff_logger.py)

**Layer B — Backend** (`demo/backend`, FastAPI)
- `POST /run` → starts a scenario in a background thread; streams events over **WebSocket**.
- **Campaign mode** → for multi-host demos: run host 1, parse pivot artifacts from
  its final report, launch host 2 with the pivot as the lead, emit both runs into
  one continuous event stream (one graph, one timeline).
- **Recorder** → writes every live run's event stream to `recordings/*.json`.
- **Replay player** → re-emits a recorded stream with realistic pacing (booth safety net + instant reset).
- `GET /scenarios`, `GET /recordings`, `GET /health` (model reachable, DB present). Fully offline.

**Layer C — Frontend** (`demo/frontend`, React + Vite)
- Panels: PoI header · **agent org-chart** (lights up as agents activate) ·
  **plain-English narration ticker** · evidence/SQL stream (collapsible) ·
  **attack-reconstruction graph** (hero, React Flow) · artifacts board ·
  kill-chain / APT-stage timeline · metrics footer.
- Metrics footer: **"Running 100% locally — no cloud"** badge, live token count,
  and final **F1 vs ground truth** (wire in [`../artifact/evaluation.py`](../artifact/evaluation.py)).
- Fullscreen presentation mode, one-key reset, large readable type, light/dark.

## 5. Event model (contract between agent and UI)

Typed events, each with: `agent_id`, `role` (`chief|investigator|qa`), `timestamp`,
plain-English `narration`, technical `detail`.

```
run_started · chief_thinking · lead_dispatched · investigator_started ·
qa_question · sql_query · sql_result · artifact_found · pivot_found ·
stage_transition · investigator_summary · chief_reflection · eval_started ·
final_report · metrics · run_complete
```

- `stage_transition` — emitted by the **deterministic kill-chain mapper** in the
  narration translator when a finding is classified into an APT stage
  (Initial Access / Execution / C2 / Lateral Movement / Exfiltration). Drives the
  APT timeline panel. Rule-based, zero LLM cost.

- `artifact_found` / `pivot_found` drive the **reconstruction graph**
  (nodes = hosts/processes/domains/IPs/files; edges = spawned / connected-to /
  downloaded / moved-laterally-to). `pivot_found` maps to the multi-host
  "PIVOTS FOUND" prompt logic already added in `prompts.py`.
- A **narration translator** converts raw events → broad-audience sentences.

## 6. Build phases (each independently shippable)

| Phase | Deliverable | Done when |
|---|---|---|
| **0 — Instrumentation** | `artifact/observability.py`: event bus + callback handler + env-guarded semantic hooks | Eval run with flag OFF is byte-identical to `main`; flag ON prints a structured event stream |
| **1 — Backend** | FastAPI + WebSocket + run controller + recorder | Can start a run and watch the raw event stream in a browser/terminal |
| **2 — UI skeleton** | React app: agent org-chart + narration ticker + evidence stream | First "it's alive" milestone |
| **3 — Hero visuals** | Attack-reconstruction graph + artifacts board + APT-stage timeline view + view switcher + campaign mode | Graph builds node-by-node from `artifact_found`/`pivot_found`; APT view lights up from `stage_transition`; presenter can switch views; one stitched graph across both hosts |
| **4 — Replay** | Recorder + replay player + 2–3 bundled known-good recordings | Demo runs entirely from a recording with no model |
| **5 — Presentation polish** | Plain-English mode, "runs locally" badge, F1/metrics footer, fullscreen, reset, theming | Presentable and talked-over end-to-end |

**Current phase: Phase 0 (not started).**

## 7. Conventions for contributors
- New code lives under `demo/`. Do **not** refactor `artifact/` beyond tiny env-guarded hooks.
- Guard every instrumentation hook with `if os.environ.get("CLOUSEAU_OBSERVABILITY") == "1":`.
- Keep the demo **offline-capable** — no external CDNs at runtime for the packaged build.
- Prefer reusing existing budgets/optimizations (Batch-1 token management) — they matter at 25 tps.
- Branch: **`demo/live-observatory`** (off `optimize/batch1-token-management`, so the demo
  inherits token optimizations). Do not commit `RESEARCH_GAP_ANALYSIS.md` or `arxiv_results.json`.

## 8. Open questions / decisions still to confirm
- [ ] Which specific M-scenario is the "hero" (need one with a clean, legible lateral-movement chain)?
- [ ] Exact local model + served name on the DGX Spark (for the health check and the "running locally" badge).
- [ ] **Obtain M1–M6 scenario databases** — not present on the dev machine (see §3
      validation findings). Needed before Phase 3 hero-demo testing.
- [x] ~~APT narrative overlay?~~ **DECIDED (2026-07-27):** the UI supports BOTH a
      multi-stage reconstruction view AND an APT kill-chain view, as **switchable
      views** (one at a time, same event stream) — see §3.

## 9. Status Log
- **2026-07-27** — Plan approved. Branch `demo/live-observatory` created off
  `optimize/batch1-token-management`. This handoff file authored. No code written yet.
  Next: Phase 0 — `artifact/observability.py` (event bus + callback handler + env-guarded hooks).
- **2026-07-27 (plan validation)** — Plan validated against the codebase. Findings:
  (1) M-scenario data missing on dev machine — S-series suffices for Phases 0–2,
  M-data needed by Phase 3; (2) multi-host runs are per-host in `app.py`, so the
  backend gains a **campaign mode** to chain h1→h2 and stitch one graph;
  (3) added `stage_transition` event + deterministic kill-chain mapper (zero LLM
  cost at 25 tps); (4) decided: multi-stage view and APT kill-chain view are
  switchable, not simultaneous. Plan is otherwise sound; Phase 0 unblocked.
