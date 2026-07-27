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
- [x] ~~**`graphOp` for live runs**~~ **SUPERSEDED by §9 (agreed 2026-07-27).** The
      live reconstruction graph is no longer built from per-event `graphOp` layout
      hints. It is materialized at end-of-run from a captured evidence store
      (grounded KG), with layout computed client-side. See §9 for the full design.
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

## 9. Agreed evolution — grounded knowledge graph + two-act center (design locked 2026-07-27, NOT yet built)

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
context. Structuring the Chief's narrative with an LLM = ungrounded (reproduces
Gap 7). Grounded structure can only come from evidence captured at the tool layer.

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
   Gap-7 check and it's the strongest form of grounding.
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
  into the agent's context so it doesn't forget early findings (Gap 3 proper).
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

### 9.8 Research convergence (why this is thesis, not scaffolding)
One design instantiates three gaps from `RESEARCH_GAP_ANALYSIS.md`: **Gap 3**
(the KG is the long-term tier of hierarchical memory), **Gap 7** (nodes/edges carry
`source_query_id`/`source_row_id` — Grounded Findings), **Gap 8** (the KG *is* the
Evidence Graph / audit trail). "Watch it reconstruct the attack — and every claim is
evidence-linked, not hallucinated" is the pitch.

### 9.9 First-cut build scope (agreed)
Observer KG only (A, not B) · deterministic/grounded edges only (defer the bounded
LLM edge-labeling pass) · capture-live + assemble-at-end + animated reveal (defer
true incremental live-tracking) · in-memory KG + JSONL log · Pydantic Node/Edge with
provenance · three-tab center with auto-default. Everything deferred layers on top
without rework.

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
