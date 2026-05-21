# Agentic Handoff

This file is the shared handoff surface for both developer progress and runtime investigation summaries.

## Developer Handoff

### Phase 1: Local LLM Support (Completed)

- Objective: add local OpenAI-compatible LLM support (vLLM first) with fail-fast validation.
- Objective: keep runtime investigation summaries in this document for traceability.
- Status: ✓ local LLM + runtime handoff logging implemented.
- Notes:
  - Local endpoint must expose OpenAI-compatible APIs (for example /v1/models).
  - App should stop immediately with actionable errors when endpoint/model/config is invalid.
  - Added files: `artifact/llm_factory.py`, `artifact/handoff_logger.py`, `artifact/.env.example`.
  - Updated files: `artifact/app.py`, `artifact/chief_inspector.py`, `README.md`.
  - Runtime logs now append start/tool/end summaries for each scenario clue execution.
  - Verified reachable remote vLLM endpoint at `http://172.31.0.94:8000/v1` (DGX).
  - Verified model id from `/v1/models`: `gemma-4-26b-moe`.

### Phase 2: Environment & Dependency Management (Completed)

- Objective: set up isolated environment and verify all dependencies work.
- Status: ✓ environment verified and working.
- Notes:
  - Created isolated repo environment at `.venv-clouseau` (removed duplicate root-level `.venv`).
  - Workspace interpreter set to `.venv-clouseau` (Python 3.12.10).
  - Updated dependency pinning in `artifact/requirements.txt` for Python 3.11+ compatibility.
  - CLI smoke check succeeds: `python app.py --help` works without errors.
  - All core dependencies verified: langchain_core, pandas, langgraph, etc.

### Phase 3: Result Logging & Analysis System (Completed 2026-04-28)

- Objective: comprehensive test logging, analysis, and comparison across environments/models.
- Status: ✓ complete result logging system implemented and documented.
- Added files:
  - `artifact/test_logger.py` - SQLite-backed test execution logger with metric capture.
  - `artifact/results_analyzer.py` - Run comparison tool, identifies improvements/regressions.
  - `artifact/results_visualizer.py` - Generates publication-quality visualization charts (PNG, 300 DPI).
  - `artifact/run_with_logging.py` - Test runner with integrated logging for all claims.
  - `artifact/compare.py` - CLI tool for quick result viewing and comparison.
  - `artifact/run_tests_with_logging.sh` - DGX execution wrapper (checks vLLM, runs tests, analyzes).
  - `artifact/TEST_LOGGING_GUIDE.md` - Complete usage documentation.
  - `RESULT_LOGGING_SETUP.md`, `DGX_EXECUTION_CHECKLIST.md`, `FILES_REFERENCE.md` - Design & execution docs.
  - Updated `.gitignore` to exclude `test_logs/` from version control.
- Data captured per test: precision, recall, F1, FPR, execution duration, token counts, status.
- Data captured per run: model, endpoint, timestamps, success/failure counts, averages.
- Storage: SQLite database (persistent), JSON (human-readable), CSV (analysis), PNG (visualizations).
  - *Update (2026-04-29):* `run_with_logging.py` refactored to route all intermediary `claim_results.csv` outputs directly into the timestamped `test_logs/YYYYMMDD_HHMMSS` directory, completely eliminating scattered CSV files from the root `artifact/` directory.

### Phase 4: Test Evaluation on DGX (Completed 2026-04-28)

- Objective: Execute complete evaluation of Clouseau on ATLAS dataset (Claims 1-3) and measure performance.
- Status: ✓ partial evaluation completed (Claims 1-3 only, 36/63 paper tests).
- Execution Details (Run ID: 20260428_130914):
  - Platform: Linux DGX (aarch64) with NVIDIA GPUs
  - Model: Gemma-4-26B-MoE via local vLLM
  - Duration: 5.5 hours (13:09:14 to 18:39:34 UTC)
  - Tests: 50 total runs (36 unique tests)
  - Success rate: 100% (50/50 tests completed)
- Results Summary:
  - **Average F1:** 88.56% (vs paper's 99.79%)
  - **Average Precision:** 98.10% (excellent, vs paper's 99.93%)
  - **Average Recall:** 88.43% (vs paper's 99.65%)
  - **Performance Gap:** -11.23pp F1 (due to Gemma-4 vs GPT-4.1-Mini model difference)
- Coverage Analysis:
  - ✅ Claim 1 (S1-S4): 12 tests completed
  - ✅ Claim 2 (SE1-SE4): 12 tests completed
  - ✅ Claim 3 (SS1-SS4): 12 tests completed
  - ❌ Multi-Host (M1-M6): 18 tests MISSING
  - ❌ DARPA OpTC (OpTC1-3): 9 tests MISSING
  - **Total Coverage: 36/63 (57%) of paper's evaluation**
- Key Findings:
  - Domain-based investigation: 96%+ F1 ✅
  - File-based investigation: 97%+ F1 ✅
  - IP-based investigation: highly variable (1-99% F1) ⚠️
  - Semantic gap test: passes with 3pp F1 degradation ⚠️
  - Keyword sensitivity: has 1.8pp F1 degradation ⚠️
- Documentation Added:
  - `PERFORMANCE_COMPARISON.md` - Detailed comparison vs paper baseline
  - `TEST_EXECUTION_GUIDE.md` - Complete guide to running tests
  - `COMMANDS_CHEAT_SHEET.md` - Quick reference for common commands

### Phase 5: Hang Fix + Accuracy Improvements (Completed 2026-05-21)

- Objective: Fix the 22-hour infinite hang observed on the 2nd DGX full-suite run, and
  improve recall on IP-based investigations without reducing depth or accuracy.
- Status: ✓ all fixes implemented, syntax-verified, committed and pushed (commit `9510556`).
- Root Cause of Hang: Two compounding bugs caused the process to block indefinitely:
  1. **Infinite error loop** — Gemma 4 natively emits `<tool_call>` XML instead of structured
     function calls. Both `investigator.py` and `chief_inspector.py` caught this and routed to
     an "error" node, but `current_iteration` only incremented on *successful* tool calls. The
     error loop therefore spun forever without ever hitting the exit condition.
  2. **No LLM call timeout** — every `llm.invoke()` across all three agent tiers had zero
     timeout. If vLLM stalled (OOM, GPU pressure, context overflow), the process blocked
     indefinitely with no recovery path.
- Changes Made:

  **`artifact/constants.py`** — new constants added (all existing defaults preserved):
  - `DEFAULT_MAX_ERRORS = 10` — investigator max malformed `<tool_call>` XML responses
  - `DEFAULT_CHIEF_MAX_ERRORS = 8` — chief inspector max malformed responses
  - `IP_MAX_INVESTIGATIONS = 15` — deeper budget for IP POI (was 10)
  - `IP_MAX_QUESTIONS = 12` — deeper budget for IP POI (was 10)
  - `IP_MAX_QUERIES = 12` — deeper budget for IP POI (was 10)
  - `DEFAULT_SCENARIO_TIMEOUT = 43200` — 12-hour dead-man switch per scenario

  **`artifact/llm_factory.py`** — both `ChatOpenAI` clients updated:
  - `timeout=600` — 10-minute per-call ceiling (at 35 tok/sec, 2048 tokens = ~58s; 600s
    only fires on genuine vLLM stalls)
  - `max_retries=1` — allows one transient-error retry; never loops

  **`artifact/investigator.py`** — `InvestigateAgent` class:
  - Added `self.error_count = 0` and `self.max_errors` to `__init__`
  - `agent_router()`: increments `error_count` on every `<tool_call>` XML response (not just
    when `current_iteration` is over budget); exits to `END` when `error_count > max_errors`
  - Prevents the infinite error loop regardless of iteration budget state

  **`artifact/chief_inspector.py`** — `Clouseau` class:
  - Same `error_count` guard with `max_errors = DEFAULT_CHIEF_MAX_ERRORS = 8`
  - On error limit exceeded, routes to `"eval"` (not `END`) so the chief always produces a
    final report from whatever evidence it gathered before giving up

  **`artifact/app.py`** — `run_scenarios()` rewritten, new helpers added:
  - **IP POI budget boost**: when `poi_type == 'IP'`, uses `IP_MAX_*` constants instead of
    defaults; directly targets the 11pp recall gap observed on s1_IP (6%) and se2_IP (1%)
  - **`--resume` flag**: reads existing CSV output and skips tests already recorded; critical
    for a 3-day run that may be interrupted — allows restart from checkpoint
  - **Timestamped progress logging**: every test prints `[HH:MM:SS] ▶ Starting X (N/total)`
    at start and `[HH:MM:SS] ✓ X — N min — saved to CSV` at completion; visible in tmux
  - **12-hour safety-net timeout**: each individual scenario runs inside a
    `ThreadPoolExecutor` with `timeout=DEFAULT_SCENARIO_TIMEOUT`; if the error_count guards
    somehow still fail, the scenario is cancelled, zeros are written to CSV, and execution
    continues to the next test (dead-man switch, not a performance target)
  - **Startup summary**: prints all active settings (error limits, IP boost values, timeout)
    at launch so the configuration is visible in logs

  **`run_all_tests_1x.py`**:
  - `timeout` per batch: `14400` (4h) → `259200` (72h); safe for a 3-day window
  - `--resume` passthrough: if outer script is called with `--resume`, it forwards the flag
    to each `app.py` subprocess
  - Estimated time comment updated to reflect Gemma 4 at 35 tok/sec reality

- How to Run on DGX:
  ```bash
  git pull
  # Fresh full run
  python run_all_tests_1x.py --no-prompt

  # Resume an interrupted run
  python run_all_tests_1x.py --no-prompt --resume
  ```
- Expected Accuracy Impact:
  - IP POI failures (s1_IP: 6%, se2_IP: 1%) should improve with inv=15/q=12/sql=12 budget
  - Multi-host M1-M6 and OpTC scenarios will now complete for the first time
  - Overall F1 target: 90-95% (vs current 88.56% from 50/63 tests)
  - Precision should remain stable (~98%)

### Next Actions (Priority Order)

**Priority 1: Re-run Full 63-Test Suite on DGX (Estimated 24-72 hours)**
- Pull latest (`git pull`) on DGX, then:
  ```bash
  cd artifact && source /path/to/venv/bin/activate
  python ../run_all_tests_1x.py --no-prompt
  ```
- Monitor via tmux: progress lines print every few minutes
- If interrupted: re-run with `--resume` to continue from checkpoint

**Priority 2: Analyze Full Results**
- After completion: `python compare.py latest` to view all 63 tests
- Focus on M1-M6 multi-host and OpTC (first-ever run of these scenarios)
- Check if IP POI recall improved from the budget boost

**Priority 3: Plan OT Extension (Estimated 2-3 weeks total)**
- Phase A (Days 1-3): Profile DataSense dataset, design OT schema
- Phase B (Days 4-7): Implement OT preprocessing + QA agents
- Phase C (Days 8-14): Test on DataSense, tune hyperparameters
- Phase D (Days 15-20): Write Clouseau-OT paper with full IT+OT evaluation
- Expected outcome: Novel paper on first LLM-based IT+OT attack investigation system

### Environment Notes (Current Status: 2026-05-21)

- Python: 3.12.10 in `.venv-clouseau` (verified working)
- vLLM endpoint (DGX): `http://172.31.0.94:8000/v1` with `gemma-4-26b-moe` model
- Hardware: 2× DGX Spark, ~35 tok/sec with Gemma-4-26B-MoE
- All dependencies: installed and verified working ✅
- Last successful test execution: 2026-04-28 (Run ID: 20260428_130914)
  - Duration: 5.5 hours (Claims 1-3, 50 total tests, 36 unique)
  - Coverage: 57% (missing M1-M6 and OpTC — these hung on the 2nd attempt)
  - Performance: 88.56% average F1 (Gemma-4-26B vs paper's 99.79% with GPT-4.1)
- Test results: automatically logged in `artifact/test_logs/YYYYMMDD_HHMMSS/`
- Latest comparison: See `PERFORMANCE_COMPARISON.md` for detailed baseline analysis
- Hang fix: committed `9510556` on 2026-05-21 — pull before next DGX run

## Runtime Log

Runtime logs from previous test executions have been archived. They are no longer stored in this file to keep it focused on developer handoff context.

**To view test execution results:**
- Latest results: `cd artifact && python compare.py latest`
- All runs: `cd artifact && python compare.py list`
- Detailed CSV: `artifact/test_logs/YYYYMMDD_HHMMSS/test_results.csv`
- SQLite database: `artifact/test_logs/test_runs.db`

**Previous execution summary (2026-04-28, Run ID: 20260428_130914):**
- Platform: Linux DGX (aarch64) with NVIDIA GPUs
- Model: Gemma-4-26B-MoE via local vLLM
- Duration: 5.5 hours
- Tests: 50 total (36 unique, Claims 1-3 only)
- Coverage: 57% (missing M1-M6 and OpTC — hung on 2nd attempt, now fixed)
- Average F1: 88.56% | Precision: 98.10% | Recall: 88.43%

**Next full run target:** 63 tests (1x) to validate hang fix and IP boost, then 63 × 3 = 189
executions using `run_all_tests_3x.py` for publication-quality statistics.
