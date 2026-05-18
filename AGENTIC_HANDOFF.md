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

### Next Actions (Priority Order)

**Priority 1: Complete IT Baseline (Estimated 4-5 hours)**
- Run Multi-Host scenarios: `python app.py --scenarios-mi`
- Run DARPA OpTC scenarios: `python app.py --scenarios-optc`
- This brings coverage to 63/63 (100%) and validates against paper

**Priority 2: Optimize IP-Based Investigation (Estimated 2-3 hours)**
- Debug why S1_IP and SE2_IP fail catastrophically (6% recall)
- Increase hyperparameters for IP POI investigation
- Retest: `python app.py --scenarios-si --max-investigations 15 --max-questions 15`

**Priority 3: Plan OT Extension (Estimated 2-3 weeks total)**
- Phase A (Days 1-3): Profile DataSense dataset, design OT schema
- Phase B (Days 4-7): Implement OT preprocessing + QA agents
- Phase C (Days 8-14): Test on DataSense, tune hyperparameters
- Phase D (Days 15-20): Write Clouseau-OT paper with full IT+OT evaluation
- Expected outcome: Novel paper on first LLM-based IT+OT attack investigation system

### Environment Notes (Current Status: 2026-05-07)

- Python: 3.12.10 in `.venv-clouseau` (verified working)
- vLLM endpoint (DGX): `http://172.31.0.94:8000/v1` with `gemma-4-26b-moe` model (verified)
- All dependencies: installed and verified working ✅
- Last test execution: 2026-04-28 (Run ID: 20260428_130914)
  - Duration: 5.5 hours (3 claims, 50 total tests, 36 unique)
  - Coverage: 57% (Claims 1-3 only, missing M1-M6 and OpTC)
  - Success rate: 100%
  - Performance: 88.56% average F1 (Gemma-4-26B vs paper's 99.79% with GPT-4.1)
- Test results: automatically logged in `artifact/test_logs/YYYYMMDD_HHMMSS/` with run metadata
- Latest comparison: See `PERFORMANCE_COMPARISON.md` for detailed baseline analysis

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
- Coverage: 57% (missing M1-M6 and OpTC)
- Average F1: 88.56% | Precision: 98.10% | Recall: 88.43%

**Next full run target:** 63 tests × 3 runs = 189 executions (~30 hours) on DGX Spark using `run_all_tests_3x.py`.
