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
| **UI: polished React + Vite SPA** | Proper graph library for the attack-reconstruction visual (React Flow or Cytoscape). **⚠ Revised 2026-07-27: no Node.js on the dev machine** (verified — `node`/`npm` absent from both Bash and PowerShell). Built a static HTML/CSS/vanilla-JS console instead — fully testable without Node, and it's what's actually running today. See §4 Layer C. A React/Vite rebuild is still a valid future upgrade once a Node-capable machine (e.g. the DGX Spark) is available — treat the static build as the reference design/behavior to port, not a placeholder to throw away. |
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

## 4. Architecture (3 layers) — status: 0 and 1 built and tested; 2/3 built as a static console (see revision note)

```
demo/
  backend/            FastAPI + WebSocket server, run controller, replay player   [BUILT]
    main.py             app + live-run orchestration (/run, /ws/run/{id}, /scenarios)
    replay.py           recording load + paced event streaming (/recordings, /ws/replay/{id})
    requirements.txt
  frontend/            static console (index.html) — see revision note below      [BUILT]
  recordings/           saved event streams (*.json) for replay
    sample_apt_campaign.json   hand-authored 48-event two-host APT reference recording
  AGENTIC_HANDOFF.md    <-- this file
../artifact/
  observability.py     event bus + LangChain callback handler (env-guarded)       [BUILT]
```

**Layer A — Instrumentation** (`artifact/observability.py`) — ✅ built + tested
- An **event bus** (thread-safe `queue.Queue` per `run_id`) + `ThinkingPulseCallback`
  (a `BaseCallbackHandler`, same pattern as the existing
  [`../artifact/debug_callback.py`](../artifact/debug_callback.py)), wired into the
  SQL agent's `graph.invoke(config={"callbacks":[...]})` in `qa_agent.py` — the
  tightest LLM-call loop, most likely to feel frozen at ~25 tok/s.
- Semantic hooks (env-guarded by `CLOUSEAU_OBSERVABILITY=1`, zero behavior change
  when unset — verified, see §9) at the actual call sites:
  - `lead_dispatched`, `chief_thinking`, `pivot_found` (parses the chief's
    "PIVOTS FOUND:" text — see `prompts.py`), `eval_started`, `final_report` — all
    in `chief_inspector.py` (`Clouseau.call_tool`/`call_model`/`call_eval`, `ClouseauRun`).
  - `investigator_started`, `investigator_summary` — `investigator.py` (`investigate_attack`).
  - `qa_question`, `sql_query`, `sql_result` — `qa_agent.py` (`run_agent`, `run_sql_query`).
    A `contextvars.ContextVar` carries run/host/agent context down into
    `run_sql_query`, which is invoked deep inside the tool-call machinery with only
    `db_name` injected.
  - `artifact_found` — **sourced from the final structured eval JSON**
    (`_emit_artifacts_from_eval` in `chief_inspector.py`), not from speculative
    mid-run parsing. Rationale: whether a SQL row *is* an attack artifact is a
    judgment call the chief only makes once, in its structured final report
    (`prompts.eval_agent`'s addresses/domains/files/malicious_processes/
    tainted_processes schema) — that is the one grounded, deterministic signal.
  - `metrics` — `app.py`'s `run_scenarios`, right after `evaluate_report()`
    (precision/recall/F1 computed from `tp/fp/fn`, plus token count).
  - Stage tagging for the APT view is a **`stage` field on the event itself**
    (not a separate event type) — computed by `observability.infer_stage()`, a
    plain keyword/type lookup (pivot→Lateral Movement; artifact_type/keywords→
    the rest). Deterministic, zero extra LLM cost — matches the "no tokens spent
    on presentation logic" constraint in §2.

**Layer B — Backend** (`demo/backend`, FastAPI) — ✅ built + tested
- `POST /run` → resolves a scenario from the **same catalog `app.py`'s CLI uses**
  (`si_scn`/`ml_scn`/etc., imported lazily) + `create_llm_from_env`, starts the
  investigation in a background thread, returns a `run_id`.
- `GET /run/{run_id}/status` → poll status (`queued|starting|running|complete|error`).
- `WS /ws/run/{run_id}` → drains `observability.get_queue(run_id)` and forwards each
  event; on stream end, **auto-saves the run as a recording** under `recordings/`
  (today's live run becomes tomorrow's reliable replay, no separate recorder step).
- `GET /recordings`, `GET /recordings/{id}`, `WS /ws/replay/{id}?speed=N` → list/serve/
  stream a recording, honoring each event's authored `delayMs / speed`.
- CORS wide open (`allow_origins=["*"]`) — intentional, this is a local demo tool
  never meant to be deployed publicly.
- **Not yet built: campaign mode.** Multi-host demos (`m1h1`/`m1h2`) still require
  someone (a future backend feature) to run host 1, extract the pivot, and launch
  host 2 with it as the lead, stitching both into one stream/graph. See §8.

**Layer C — Frontend** (`demo/frontend/index.html`) — ✅ built + tested; **revision from plan**
- **No Node.js is installed on this dev machine** (`node`/`npm` absent from both
  Bash and PowerShell — verified, not assumed). Shipping an unbuilt/untested React
  scaffold would have meant code nobody had confirmed even compiles. Built a
  single-file static console instead: same validated design tokens/CSS as the
  Artifact prototype (see §9), talking to the real backend over `fetch`/`WebSocket`
  — genuinely booth-usable today, verified end-to-end (servers actually running,
  see §9).
- Panels: setup overlay (backend URL, Replay-vs-Live mode, recording/scenario
  picker) · header (PoI, "100% local inference" badge, Live/Replay badge with a
  pulsing dot in live mode, elapsed timer, play/pause/reset) · **agent org-chart**
  (lights up as agents activate, built from `agent_id`/`role` on incoming events —
  no hardcoded agent list, so it works for live runs with arbitrary QA agent ids
  too) · **plain-English narration ticker** · evidence/SQL stream (collapsible
  toggle) · **attack-reconstruction graph** (hand-rolled SVG, node/edge ops driven
  by `graphOp` on events) · **APT kill-chain view** (8 fixed stages, lit by each
  event's `stage` field) · view switcher (Reconstruction ⇄ APT, one at a time per
  §3) · artifacts board · metrics footer (SQL count, investigations, live token
  count, final precision/recall/F1).
- Client-side pause/resume: while paused, incoming WS messages queue instead of
  rendering (server keeps pacing/running; only display freezes) — avoids needing
  backend-side pause support.
- **To upgrade to React + Vite later:** treat this file's CSS custom properties
  and JS rendering functions (`addGraphNode`/`addGraphEdge`/`lightStage`/
  `pushNarration`/etc.) as the reference implementation to port component-by-component
  once Node is available — the event schema and backend do not need to change.

## 5. Event model (contract between agent and UI) — as actually implemented

Each event (dict, JSON-serializable — see `observability.emit()`): `run_id`, `seq`,
`ts`, `type`, `role` (`chief|investigator|qa|system`), `agent_id`, `host`, `stage`,
`narration` (plain English), `detail` (technical). Optionally `graphOp` (added by
the *sample recording*, not by `observability.py` — live runs don't emit graph
layout hints; the reconstruction graph for a live run is a known gap, see §8).

```
run_started · chief_thinking · lead_dispatched · investigator_started ·
qa_question · sql_query · sql_result · artifact_found · pivot_found ·
investigator_summary · chief_reflection · eval_started · final_report ·
metrics · run_complete
```

- **No separate `stage_transition` event** (revised from the original plan) —
  `stage` is instead a **field on `artifact_found`/`pivot_found` events themselves**,
  set by `observability.infer_stage()` (deterministic keyword/type lookup, zero
  LLM cost). Simpler than a second event type; the frontend's APT view just reads
  `ev.stage` off whatever event arrives.
- `artifact_found` / `pivot_found` are what drive the **reconstruction graph** in
  the sample recording (nodes = hosts/processes/domains/IPs/files; edges =
  spawned/connected-to/downloaded/moved-laterally-to, via each event's `graphOp`).
  `pivot_found` parses the multi-host "PIVOTS FOUND:" prompt convention already in
  `prompts.py`.
- The **narration** string is authored directly at each emit-call site in the
  Python code (not a separate translation layer) — e.g. `chief_inspector.py`'s
  `_emit_pivots` writes `f"Pivot identified: {line}"` inline. Simpler than a
  standalone "narration translator" module; revisit only if narration logic grows
  complex enough to want centralizing.

## 6. Build phases (each independently shippable)

| Phase | Deliverable | Status |
|---|---|---|
| **0 — Instrumentation** | `artifact/observability.py`: event bus + callback handler + env-guarded semantic hooks | ✅ **Done.** Verified flag-OFF byte-identical output on the highest-risk touched function (`run_sql_query`) with a real sqlite DB; verified events flow correctly when enabled. |
| **1 — Backend** | FastAPI + WebSocket + run controller + auto-recorder | ✅ **Done.** Tested via `TestClient`: full 48-event replay stream end-to-end; live-run error path (no LLM configured) fails cleanly with a correct `/run/{id}/status`. Both servers run live during this session (`localhost:8000` backend, `localhost:5500` static frontend). |
| **2 — UI skeleton** | Agent org-chart + narration ticker + evidence stream | ✅ **Done**, as part of the static console (not a separate React skeleton — see §4 revision). |
| **3 — Hero visuals** | Attack-reconstruction graph + artifacts board + APT-stage view + view switcher | ✅ **Done** for the sample-recording/replay path. ❌ **Not done:** campaign mode (multi-host stitching for live runs — see §8) and graph layout hints (`graphOp`) for live runs, since `observability.py` doesn't emit them yet. |
| **4 — Replay** | Replay player + bundled recordings | ✅ Player done and tested. Only **1** bundled recording so far (`sample_apt_campaign.json`) — plan said 2–3; add more once real scenario runs are available. |
| **5 — Presentation polish** | Plain-English mode, "runs locally" badge, metrics footer, reset, theming | ✅ Badge, metrics footer, light/dark theming, reset-to-setup all done. ❌ Not done: fullscreen/kiosk mode (lower priority now — see §1, this is a guided institutional demo, not unattended). |

**Current phase: Phase 3/4 substantially done for replay; live multi-host (campaign mode) is the main remaining gap — see §8.**

## 7. Conventions for contributors
- New code lives under `demo/`. Do **not** refactor `artifact/` beyond tiny env-guarded hooks.
- Guard every instrumentation hook with `if os.environ.get("CLOUSEAU_OBSERVABILITY") == "1":`.
- Keep the demo **offline-capable** — no external CDNs at runtime for the packaged build.
- Prefer reusing existing budgets/optimizations (Batch-1 token management) — they matter at 25 tps.
- Branch: **`demo/live-observatory`** (off `optimize/batch1-token-management`, so the demo
  inherits token optimizations). Do not commit `RESEARCH_GAP_ANALYSIS.md` or `arxiv_results.json`.

## 8. Open questions / decisions still to confirm
- [ ] **Campaign mode (multi-host live stitching)** — the real remaining gap. Needs
      a backend feature: run host 1 → parse pivot from its final report → launch
      host 2 with the pivot as the lead → merge both runs' events into one
      `run_id`/stream/graph. Today, live runs are single-host only; the two-host
      story only exists in the sample recording.
- [ ] **`graphOp` for live runs** — `observability.py` emits `artifact_found`/
      `pivot_found` with rich `detail`, but not the node/edge layout hints
      (`graphOp`) the frontend's reconstruction graph currently relies on (those
      only exist hand-authored in the sample recording). Needs a small mapper:
      artifact detail → graph node/edge, probably living in the backend (keeps
      `observability.py` UI-agnostic) or in the frontend itself (derive layout from
      `artifact_found`/`pivot_found` fields directly, no backend change needed —
      likely the simpler path).
- [ ] Which specific M-scenario is the "hero" (need one with a clean, legible
      lateral-movement chain) — blocked on obtaining M1–M6 scenario DBs (not on
      this dev machine; presumably on the DGX or external storage).
- [ ] Exact local model + served name on the DGX Spark (for the health check and
      the "running locally" badge).
- [ ] Add 1–2 more bundled recordings once real scenario runs exist (plan wanted 2–3, have 1).
- [x] ~~APT narrative overlay?~~ **DECIDED (2026-07-27):** the UI supports BOTH a
      multi-stage reconstruction view AND an APT kill-chain view, as **switchable
      views** (one at a time, same event stream) — see §3.
- [x] ~~React + Vite build?~~ **REVISED (2026-07-27):** no Node.js on the dev
      machine — built a static console instead (see §4). Not abandoned, just
      deferred to whenever a Node-capable machine is available.

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
- **2026-07-27 (build session)** — User: don't wait on scenario data, "just start
  coding," priority is appealing visuals. Built, in order:
  1. `demo/recordings/sample_apt_campaign.json` — hand-authored 48-event two-host
     APT reference recording (phishing → macro exec → PowerShell → C2 beacon →
     SMB pivot → domain enumeration → persistence service → exfiltration).
     IPs use IANA-reserved TEST-NET ranges; all names fictional.
  2. A standalone HTML/CSS/JS design prototype, published as a Claude Artifact for
     immediate visual review (dataviz + artifact-design skills consulted first;
     categorical role colors = the dataviz reference palette's pre-validated
     "all-pairs-safe" blue/orange/aqua trio; status colors = the palette's fixed
     reserved set; brand/chrome = violet, deliberately not reused as data color).
     Verified structurally (brace/paren balance, all referenced element IDs exist).
  3. `artifact/observability.py` + hooks in `chief_inspector.py`, `investigator.py`,
     `qa_agent.py`, `app.py` — see §4 Layer A. Tested: byte-identical
     `run_sql_query` output flag-on vs flag-off; events correctly captured when
     enabled and a QA context is set.
  4. `demo/backend/{main.py,replay.py,requirements.txt}` — see §4 Layer B. Tested
     via `TestClient`: `/health`, `/recordings`, full replay WS stream (48/48
     events + clean disconnect), `/scenarios` (27 entries from the real catalog),
     live-run clean-failure path when no LLM is configured.
  5. `demo/frontend/index.html` — static console (Node.js unavailable — verified
     absent, not assumed; see §4 Layer C revision). Ported the prototype's
     validated design; playback engine replaced with real WebSocket wiring, a
     setup overlay (backend URL / replay-or-live picker), client-side pause/resume
     queueing, and a fix for a caught bug (setup overlay was hiding before a
     connection error could be shown to the user — now reopens with the error).
     Verified structurally; both backend (`:8000`) and frontend (`:5500`) are
     **running right now** in this session for live interactive testing.
  - **Known gaps carried forward:** campaign mode (multi-host live stitching) and
    `graphOp` emission for live runs — see §8. Everything else in this session's
    scope is built and tested to the extent this environment allows (no Node, no
    real LLM endpoint, no M-series data).
