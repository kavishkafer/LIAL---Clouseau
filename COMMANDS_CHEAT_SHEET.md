# Clouseau Commands Quick Reference

## Setup

```bash
# Activate environment
.\win_venv\Scripts\Activate.ps1

# Set LLM (choose one)
$env:LLM_MODEL = "gpt-4-turbo"                    # OpenAI
$env:API_KEY = "sk-..."
$env:BASE_URL = "https://api.openai.com/v1"

# OR
$env:LLM_MODEL = "meta-llama/Llama-2-7b-chat"     # Local
$env:API_KEY = "local"
$env:BASE_URL = "http://localhost:8000/v1"

# OR (DGX)
$env:LLM_MODEL = "gemma-4-26b-moe"
$env:API_KEY = "local"
$env:BASE_URL = "http://172.31.0.94:8000/v1"
```

---

## Quick Tests

```bash
cd artifact

# Run single scenario type (pick one)
python app.py --scenarios-si --no-warn      # Single-host (S1-S4)
python app.py --scenarios-se --no-warn      # Extended (SE1-SE4)
python app.py --scenarios-ss --no-warn      # Keywords (SS1-SS4)
python app.py --scenarios-mi --no-warn      # Multi-host (M1-M6)
python app.py --scenarios-optc --no-warn    # DARPA OpTC

# Run specific scenario + POI
python app.py --scenarios-si --target-scenario S1 --target-poi IP

# Run all claims with logging
python run_with_logging.py
```

---

## Results & Analysis

```bash
# List all test runs
python compare.py list

# Show latest results
python compare.py latest

# Compare two runs
python compare.py compare RUN_ID_1 RUN_ID_2

# Show specific run
python compare.py show RUN_ID

# Generate visualizations
python results_visualizer.py
```

---

## Advanced Options

```bash
# Adjust investigation depth
python app.py --scenarios-si \
  --max-investigations 15 \
  --max-questions 20 \
  --max-queries 15

# Custom output file
python app.py --scenarios-si --csv-file my_results.csv

# Debug mode (verbose output)
python app.py --scenarios-si -v

# Ablation studies
python app.py --scenarios-si --ablation-single-agent
```

---

## Environment Variables

| Variable | Example | Purpose |
|----------|---------|---------|
| `LLM_MODEL` | `gpt-4-turbo` | Which model to use |
| `API_KEY` | `sk-...` | OpenAI key (or "local") |
| `BASE_URL` | `http://localhost:8000/v1` | LLM endpoint |
| `LLM_TEMPERATURE` | `0.0` | Determinism (0=fixed, 1=random) |
| `TIMEOUT_SECONDS` | `3600` | Query timeout |

---

## Test Types & Runtimes

| Test | Command | Runtime | Scenarios |
|------|---------|---------|-----------|
| Quick test | `--scenarios-si --target-scenario S1 --target-poi IP` | 30-60s | 1 POI |
| Single scenario | `--scenarios-si --target-scenario S1` | 2-5 min | 3 POIs |
| Single-host | `--scenarios-si` | 10-20 min | S1-S4 |
| Extended | `--scenarios-se` | 10-20 min | SE1-SE4 |
| Keywords | `--scenarios-ss` | 10-20 min | SS1-SS4 |
| All claims | `run_with_logging.py` | 3-5 hours | 50 tests |

---

## Interpreting Results

```
F1 > 95%:  EXCELLENT ✅
F1 > 85%:  GOOD ✅
F1 > 70%:  ACCEPTABLE ⚠️
F1 < 70%:  NEEDS INVESTIGATION ❌

Your baseline: 88.56% → GOOD
Paper: 99.79% → EXCELLENT
```

---

## Common Issues & Fixes

```bash
# "No module named..." → Missing dependencies
pip install -r requirements.txt

# "LLMConfigError" → Missing env variables
echo $env:LLM_MODEL  # Check if set

# "Connection refused" → LLM server not running
python -m vllm.entrypoints.openai.api_server --model meta-llama/Llama-2-7b-chat

# Tests too slow → Reduce depth
python app.py --scenarios-si --max-investigations 5 --max-questions 5

# Database locked → Don't run tests in parallel
# Run one at a time, wait for completion
```

---

## Directory Structure

```
artifact/
├── app.py                    # Main CLI entry point
├── run_with_logging.py       # Run all tests + logging
├── compare.py                # View results
├── results_visualizer.py     # Generate charts
├── results_analyzer.py       # Analyze runs
├── investigator.py           # Investigation agent
├── chief_inspector.py        # Orchestrator agent
├── qa_agent.py               # QA agents
├── scenarios/                # Test data
│   ├── S1/, S2/, S3/, S4/   # Single-host
│   ├── SE1/, SE2/, SE3/, SE4/ # Extended
│   ├── SS1/, SS2/, SS3/, SS4/ # Keywords
│   ├── M1/, M2/, ...        # Multi-host
│   └── OPT1/, OPT2/, OPT3/  # DARPA OpTC
└── test_logs/               # Results
    ├── 20260506_143022/     # Test run
    ├── test_runs.db         # Database
    └── visualizations/      # Charts
```

---

## File Locations

```bash
# Navigate to tests
cd artifact

# View results
cat test_logs/LATEST/test_results.csv

# View comparison
cat PERFORMANCE_COMPARISON.md

# Full test guide
cat TEST_EXECUTION_GUIDE.md
```

---

## One-Liners

```bash
# Quick quality check
cd artifact && python app.py --scenarios-si --target-scenario S1 --target-poi domain && echo "✓ System OK"

# Full evaluation
cd artifact && python run_with_logging.py && python compare.py latest

# See all past runs
cd artifact && python compare.py list

# Export results as JSON
cd artifact && python results_analyzer.py --export-json results.json
```

---

## For DGX Execution

```bash
# SSH to DGX
ssh user@172.31.0.94

# Set environment
export LLM_MODEL="gemma-4-26b-moe"
export BASE_URL="http://localhost:8000/v1"
export API_KEY="local"

# Run tests
cd /path/to/clouseau/artifact
python run_with_logging.py

# Monitor progress (in another terminal)
watch -n 5 'tail -20 test_logs/LATEST/test_results.csv'
```

---

**Need help?** See TEST_EXECUTION_GUIDE.md for detailed explanations.
