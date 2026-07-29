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
  - `get_log(run_id)` — a durable, append-only per-run event log (separate from
    the transient delivery queue a slow/absent consumer can leave undrained).
    This is what `graph_assembly.py` reads at end-of-run.

**§9 first-cut (grounded KG) — ✅ built + verified on real scenario data.**
`artifact/graph_assembly.py` implements §9 end-to-end, deterministically (no
LLM call): nodes come only from the Chief's final structured eval JSON (same
schema `_emit_artifacts_from_eval` reads); edges are derived only between two
already-committed node ids, from `sql_result` rows matching a recognized
relationship shape (pid+ppid → spawned, pid+object/ip → connected to,
domain+response → resolves to) or a parsed lateral-movement pivot — a row
referencing an id that isn't already a committed node contributes nothing,
which is the grounding rule enforced by construction, not by a later filter.
Layout is a plain layered-DAG placement (topological layer, host-grouped
track), collision-free, expressed as the same 0–100 `x`/`y` percentages the
frontend already consumes via `graphOp` — no frontend contract change needed.
Called synchronously inside `ClouseauRun` (`chief_inspector.py`) before
`observability.end_run()`, so its `graph_assembled` event reaches the delivery
queue before the `run_complete` sentinel closes it — zero backend changes.
**Verified against real telemetry**, not just structurally: a script drove the
real `qa_agent.run_sql_query` hook against the real ATLAS S1 scenario DB, fed
the real chief output through `graph_assembly.assemble_and_emit`, and captured
the actual resulting event log as `demo/recordings/live_s1_verification.json`.

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
`narration` (plain English), `detail` (technical). Optionally `graphOp` — an array
of `{op:'addNode'|'addEdge', node/edge:{...}}` ops. In the sample recording it's
hand-authored; on a real run it's produced by `graph_assembly.assemble_and_emit()`
on a single `graph_assembled` event at end-of-run (§9, verified on real S1
telemetry — no longer a gap, see §8/§10).

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
- The **reconstruction graph** is driven by `graphOp` on a single `graph_assembled`
  event on a real run (nodes = the Chief's final eval JSON; edges = grounded
  relationships derived from captured `sql_result` rows and parsed pivots — see
  §9), or by `graphOp` spread across events in the hand-authored sample recording.
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
| **3 — Hero visuals** | Attack-reconstruction graph + artifacts board + APT-stage view + view switcher | ✅ **Done**, including live runs — `graph_assembly.py` (§9) now assembles a grounded `graphOp` at end-of-run for both replay AND real live investigations (verified on real S1 telemetry, not just the sample recording). Reconstruction graph has its own zoom (scroll + buttons), drag-to-pan, and content-aware auto-fit, and fills its full panel (was previously capped to a small 640×380 preview). ❌ **Not done:** campaign mode (multi-host live stitching — see §8). |
| **4 — Replay** | Replay player + bundled recordings | ✅ Player done and tested. Only **1** bundled recording so far (`sample_apt_campaign.json`) — plan said 2–3; add more once real scenario runs are available. |
| **5 — Presentation polish** | Plain-English mode, "runs locally" badge, metrics footer, reset, theming | ✅ Badge, metrics footer, light/dark theming, reset-to-setup all done. ❌ Not done: fullscreen/kiosk mode (lower priority now — see §1, this is a guided institutional demo, not unattended). |

**Current phase: Phase 3/4 substantially done for replay; live multi-host (campaign mode) is the main remaining gap — see §8.**

## 7. Conventions for contributors
- New code lives under `demo/`. Do **not** refactor `artifact/` beyond tiny env-guarded hooks.
- Guard every instrumentation hook with `if os.environ.get("CLOUSEAU_OBSERVABILITY") == "1":`.
- Keep the demo **offline-capable** — no external CDNs at runtime for the packaged build.
- Prefer reusing existing budgets/optimizations (Batch-1 token management) — they matter at 25 tps.
- Branch: **`demo/live-observatory`** (off `optimize/batch1-token-management`, so the demo
  inherits token optimizations). Do not commit local research/analysis notes or
  scratch result files — keep them untracked (gitignored).

## 8. Open questions / decisions still to confirm
- [ ] **Campaign mode (multi-host live stitching)** — the real remaining gap. Needs
      a backend feature: run host 1 → parse pivot from its final report → launch
      host 2 with the pivot as the lead → merge both runs' events into one
      `run_id`/stream/graph. Today, live runs are single-host only; the two-host
      story only exists in the sample recording.
- [x] **Phase 2 — bounded LLM edge-enrichment pass** (§9.3's "optional later"
      item, scoped down this session — see §10). **Built + structurally/mock
      verified; real-model verification against a live endpoint is the
      remaining gap** (this dev machine has no LLM endpoint configured; a
      local Ollama server happens to be running with `qwen3.5:2b`/
      `qwen3:latest` — NOT `glm-4.6:cloud`, whose name suggests it may proxy
      to a cloud API — that would be the one to test against next).
- [x] ~~**`graphOp` for live runs**~~ **SUPERSEDED by §9 (agreed 2026-07-27),
      then BUILT and verified on real S1 telemetry.** The live reconstruction
      graph is materialized at end-of-run from captured evidence (grounded KG),
      with layout computed deterministically server-side and rendered/zoomed/panned
      client-side. See §9 for the design and §10 for verification notes.
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

## 9. Agreed evolution — grounded knowledge graph + two-act center (design locked 2026-07-27; first-cut scope §9.9 BUILT + verified — see §10)

This section supersedes the earlier "graphOp for live runs" gap (§8). It is the
agreed architecture for making the reconstruction graph real (and grounded) on
*live* runs, worked out in a design discussion. No code written yet.

### 9.1 The grounding principle
**Grounding depends on capturing raw evidence *during* the run (before pruning),
NOT on when the graph is assembled.** Two separate steps:
- **Evidence capture** — MUST happen inside the tool hooks (`run_sql_query`, the
  process-tree tools in `qa_agent.py`), where the *full* rows exist. Pruning
  (`prune_messages`) only trims the LLM's *context window*; the tool functions
  still receive/return full data, and our hooks run there, so capturing a copy
  costs the LLM zero tokens and doesn't alter its context. Flag-gated as usual.
- **KG assembly** — can happen whenever; **doing it once at end-of-run is preferred.**

Why the Chief's final report is NOT a sufficient source: the pipeline is lossy by
design (QA prunes old tool results; investigators return prose summaries; the Chief
only sees summaries). By the end, the row-level evidence is gone from the Chief's
context. Structuring the Chief's narrative with an LLM = ungrounded (it would draw
edges nothing verified). Grounded structure can only come from evidence captured at
the tool layer.

### 9.2 Evidence store → end-of-run KG → verification
1. **Evidence store**: append-only log (JSONL to start) of entities + relationships
   seen in raw tool results, each with provenance `{source_query, source_row, ts}`.
   Grows freely; it's the ground truth / audit trail / time-series record.
2. **End-of-run assembly** (preferred over incremental — better entity resolution
   with all mentions visible at once; simpler, less stateful): materialize a KG
   from the store.
3. **Grounding verification** (only possible in batch, over the *complete* store):
   cross-check every eval-committed finding against captured evidence; **drop or
   flag any node the Chief claimed that no actual query returned.** This is the
   strongest form of grounding available to us.
4. **Render** = eval-committed nodes (clean, denoised) + edges looked up in the KG
   (grounded — an edge shows only if the store has evidence for it). Layout is
   **client-side deterministic** (layered by kill-chain stage or force-directed);
   never ask the LLM for x/y.

### 9.3 Two hard parts (design carefully, don't hand-wave)
- **Entity resolution**: canonical merge keys per type — process = `(host, pid,
  creation_time)` (creation_time because **PIDs get reused**); ip = address;
  domain = FQDN; file = `(host, path)`. Wrong key ⇒ split one entity or merge two.
- **Edge selection**: process trees give `spawned` and flow logs give
  `connected-to` for free (fully grounded). Softer edges (`delivered`, `opened-by`)
  aren't purely mechanical. First cut: **deterministic/grounded edges only**
  (sparser but 100% provable). Optional later: a *bounded* LLM pass that may only
  connect/label nodes the KG already established (can mislabel, **cannot fabricate
  a node**) — kept as a separate, flag-gated call, **never folded into `call_eval`**
  (that call feeds precision/recall/F1; touching its prompt/schema perturbs the
  research metric and breaks flag-OFF-byte-identical).

### 9.4 Observer KG vs agent-memory — keep separate
- **(A) Observer KG**: capture → side store → KG, agent unaffected, flag-gated,
  byte-identical when off. **Build this first.** Zero behavioral risk.
- **(B) Working-memory re-injection**: feed a compacted "key findings" store *back*
  into the agent's context so it doesn't forget early findings.
  Changes investigation behavior; bigger swing; **separate research experiment.**
- Both write to the **same KG** — the KG is the shared substrate; the demo reads it
  (viz), and optionally the agent also reads it (memory). Do A now, B later.

### 9.5 Two-act center with three switchable tabs
The center panel is no longer empty-until-the-end. It has **three tabs the presenter
can switch freely** — **Agents · Reconstruction graph · APT kill-chain** — plus an
automatic default:
- **Default to "Agents"** during the run (live from the first event).
- **Auto-advance to "Reconstruction graph" on `run_complete`** (the payoff reveal)
  — **unless the presenter has manually pinned a tab**, then don't override.
- **APT kill-chain** fills live during the run (from `stage` tags).
- **Reconstruction graph** during the run shows a quiet placeholder ("assembles when
  the investigation completes"); the grounded KG populates it at the end.

**Act 1 = the investigation** (live agent topology): "how the AI works."
**Act 2 = the reconstruction** (grounded evidence graph): "what it found."
Two distinct acts, two audiences (agentic/AI crowd vs security crowd).

### 9.6 Live agent-topology honesty constraints
The "Agents" view is a faithful rendering of Clouseau's real lifecycle (Chief
long-lived; investigators short-lived; QA agents ephemeral), driven by events we
already emit (`lead_dispatched`, `investigator_started`, `qa_question`,
`investigator_summary`, `pivot_found`; teardown inferred or a small explicit event).
**Honesty caveat:** at any instant it's a *small tree* (Chief → 1 active investigator
→ 1 active QA agent — tool calls run sequentially), NOT a swarm. The drama is churn +
fan-out over time. Design truthfully: highlight the active path, let finished agents
linger as fading "ghosts" briefly, show a cumulative tally ("Investigators: 3 · QA
agents: 11"). Do not animate 15 concurrent agents — technical viewers will catch it.

### 9.7 Pydantic + persistence (now load-bearing, not nice-to-haves)
- **Pydantic** `Node` / `Edge` models with required `source_query` fields make
  grounding *enforceable* — an ungrounded edge won't validate.
- **Persistence**: the evidence stream is timestamped, so append-only **JSONL is the
  time-series log**, and the **KG is a materialized view** over it. Start in-memory
  (plain dicts, or `networkx` for layout/pathfinding) + JSONL; graduate to SQLite →
  graph DB (Neo4j) / TSDB later. Get schema + provenance right first; infra later.

### 9.8 Why grounding matters for the demo
Truthfulness, not rigor for its own sake: at an official venue, every node and edge
on screen must reflect something the investigation actually observed. Carrying
`source_query`/`source_row` on each node/edge is simply how we guarantee we never
render a claim the data doesn't support. The pitch is "watch it reconstruct the
attack — and every claim traces to real evidence, not a guess."

### 9.9 First-cut build scope (agreed) — status per item, see §10 for verification
- ✅ Observer KG only (A, not B) — `graph_assembly.py` is a pure read of captured
  evidence; agent behavior is unaffected (flag-gated as usual).
- ✅ Deterministic/grounded edges only — enforced by construction (`add_edge`
  requires both endpoints already committed), not by a later filter.
- ✅ Capture-live + assemble-at-end — built and verified on real telemetry.
- ⚠️ **Deviates from plan:** evidence capture is the existing **in-memory
  per-run event log** (`observability.get_log`/`_event_log`), not a JSONL file
  on disk. Serves end-of-run assembly fine; the time-series/audit-trail framing
  in §9.2/§9.7 is not yet realized as durable storage.
- ⚠️ **Deviates from plan:** nodes/edges are plain dicts, not Pydantic models.
  Grounding is enforced by the assembly code's control flow (see above), not by
  schema validation — works today, but §9.7's "ungrounded edge won't validate"
  guarantee is not literally in place.
- ✅ Three-tab center with auto-default, plus zoom/pan/auto-fit on the
  reconstruction graph (not in the original plan, added in response to the
  graph looking lost/uneditable at both small and large scales).
- ✅ **Bounded LLM edge-enrichment pass — built** (§10), scoped down from
  §9.3's original "connect/label" wording to **new edges only**: it never
  rewrites a deterministic edge's label. Structurally/mock-verified; real-model
  verification still open (see §8).
- **Still deferred:** true incremental live-tracking (nodes/edges still
  materialize once, at end-of-run, not progressively during the run).

## 10. Status Log
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
- **2026-07-27 (design session — grounded KG + two-act center)** — Worked out the
  architecture for making the reconstruction graph real & grounded on live runs;
  written up as §9. Key decisions: capture raw evidence at the tool layer *before*
  pruning → assemble a grounded KG at end-of-run → verify committed findings against
  captured evidence; the Chief's report alone is NOT a grounded source (post-prune
  prose). Center becomes a three-tab view (Agents / Reconstruction / APT) — live
  agent topology during the run (Act 1), grounded reconstruction graph revealed at
  completion (Act 2). First-cut scope locked in §9.9. **No code written this
  session — design only.** Also, in the same session, fixed several frontend UI bugs
  (grid mis-placement putting the graph in the wrong column; a mistargeted centering
  selector leaving dead space; added reactive expand, clickable agent nodes,
  spin-up animation, and "QA Agent (<specialization>)" naming) — all committed &
  pushed (`cd0d6f5`, `07cfbf2`, `ca03f55`, and earlier).
  **Next: implement §9** — Pydantic Node/Edge + evidence capture hooks + end-of-run
  KG assembler + verification + the three-tab center + live agent-topology view.
- **2026-07-28 (§9 first-cut build)** — Implemented and verified the grounded KG
  end-to-end (see §9.9 for exact scope/deviations): durable per-run event log
  (`observability.get_log`), richer `sql_result` detail (`col_names`/`table`) so
  edges can be derived, a pivot-line parser in `chief_inspector.py`, and the new
  `artifact/graph_assembly.py` (nodes from the Chief's final eval JSON only, edges
  grounded-by-construction, layered-DAG layout matching the frontend's node-size
  constants exactly). Wired synchronously into `ClouseauRun` before `end_run()` —
  no backend changes needed. **Verified against real data, not just structurally**:
  drove the real `qa_agent.run_sql_query` hook against the real ATLAS S1 scenario
  DB, captured the actual resulting event log as
  `demo/recordings/live_s1_verification.json` (routine Firefox captive-portal
  traffic, explicitly not a claimed attack finding — an engineering verification
  recording). Confirmed the negative case too: a row referencing an id with no
  committed node contributes no edge.
- **2026-07-29 (reconstruction-graph zoom/pan + bug fixes)** — Added zoom
  (scroll wheel + buttons), drag-to-pan, and content-aware auto-fit to the
  reconstruction graph, in response to feedback that a small graph looked lost
  in the fixed canvas and a large one would have no way to explore. Found and
  fixed three real bugs during that work, each verified against actual behavior
  rather than assumed fixed: (1) scroll-wheel zoom was anchored to the cursor
  position, so scrolling while hovering off-center pushed other nodes past the
  edge — switched to view-center anchoring, matching the +/- buttons; (2) the
  auto-fit "don't zoom in past default" safeguard compared fitted width against
  the *full* 1500-wide canvas, which is wider than almost any real graph, so it
  fired on nearly every run and silently canceled the fit — now reuses the
  existing manual-zoom floor instead, confirmed by hand-computing the real S1
  graph's fit (984×407, ~88% of panel width, vs. the old behavior's ~0%); (3)
  `#recon-svg` was capped at `max-width:640px/max-height:380px` (a leftover from
  when it was a small teaser preview), so even a correctly-fitted graph rendered
  small in a mostly-empty panel — removed the cap so it fills the panel exactly
  like the Agents view already did. Also fixed the "Technical evidence" toggle,
  which flipped its own switch but never actually revealed the SQL panel — the
  click handler was toggling `.on` on the wrong element (the section wrapper
  instead of the `.panel-body` the CSS selector checks). All fixes ported to
  both the real console (`demo/frontend/index.html`) and the design-review
  Artifact prototype, and committed to `demo/live-observatory`.
  **Next: Phase 2** — the bounded LLM edge-labeling/track-assignment pass
  (§8, §9.3, §9.9), the one piece of §9's design intentionally deferred from
  the first cut.
- **2026-07-29 (Phase 2 — bounded LLM edge-enrichment)** — Planned (via
  EnterPlanMode) and built the §9.3 "optional later" pass, scoped down after
  user clarification to **new edges only** — it never rewrites a
  deterministic edge's label, so "connected to"/"resolves to" stay exactly
  the mechanical wording `graph_assembly.py` already produces, forever.
  Added `_llm_enrichment_enabled()` (new `CLOUSEAU_GRAPH_LLM=1` flag,
  independent of `CLOUSEAU_OBSERVABILITY`, default OFF so a flaky/slow model
  on-site can never take the deterministic graph down with it),
  `_build_enrichment_prompt`/`_propose_edges_with_llm` (JSON-mode call
  mirroring `call_eval`'s own `.bind(response_format=...)` + fallback
  pattern, but built from the small deterministic node/edge list plus a
  short narration digest — not a full transcript replay — and a 512-token
  output cap, since the expected output is a short edge list, not a report),
  and `enrich_and_emit` (mirrors `assemble_and_emit`'s shape; wrapped in a
  blanket `try/except` so any failure — disabled flag, no LLM, timeout,
  malformed output — leaves the already-emitted deterministic graph
  completely unaffected). Wired into `ClouseauRun` right after
  `assemble_and_emit`, before `end_run()`. **Grounding gate enforced by
  validation, not prompt instruction**: every proposed edge must reference
  two ids already in the deterministic node set and must not duplicate an
  existing `(from, to)` pair, or it's silently dropped.
  **Verified with a 13-case mocked-LLM script** (`verify_graph_enrichment.py`,
  scratch, not committed) covering: valid new edge accepted; edge referencing
  an unknown id dropped; edge duplicating an existing pair dropped; self-loop
  dropped; markdown-fenced JSON parsed; malformed JSON / empty edge list
  handled without raising; `.bind()` failing falls back to plain `.invoke()`;
  two same-pair edges in one response de-duped; and end-to-end
  `enrich_and_emit` checks — flag off is a true no-op, `llm=None` is a
  no-op, an LLM that raises on every call path is caught without crashing,
  and the happy path emits a `graph_enriched` event with the edge correctly
  tagged `llm: True`. All 13 passed. Frontend: `.g-edge path.llm-inferred`
  (dashed, muted `--ink-3`, distinct from both plain deterministic edges and
  the brand-colored pivot dashes) plus an " · inferred" label suffix, so an
  LLM-derived edge is visually distinguishable from hard evidence at a
  glance — ported to both the real console and the prototype Artifact.
  **Known gap, called out explicitly rather than glossed over:** no live LLM
  endpoint is configured on this dev machine, so this is verified against
  mocked responses only — real-model behavior (does a real model actually
  propose sensible, useful edges, and does it respect the "never invent an
  id" instruction under real conditions rather than just in a canned test) is
  still unverified. A local Ollama server happens to be running
  (`qwen3.5:2b`, `qwen3:latest`, and `glm-4.6:cloud` — the last one's name
  suggests it may proxy to a cloud API, so it should NOT be used here or for
  the demo's "100% local inference" claim generally) and would be the
  natural next step to close that gap, the same way the S1 recording script
  closed the equivalent gap for Phase 1.
