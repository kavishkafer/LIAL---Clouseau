# Clouseau Test Execution Guide

**Complete guide for running tests on your Clouseau implementation**

---

## Table of Contents

1. [Quick Start (5 minutes)](#quick-start)
2. [Environment Setup](#environment-setup)
3. [Running Individual Tests](#running-individual-tests)
4. [Running All Claims](#running-all-claims)
5. [Running with Logging](#running-with-logging)
6. [Interpreting Results](#interpreting-results)
7. [Troubleshooting](#troubleshooting)
8. [Advanced Options](#advanced-options)

---

## Quick Start

### Prerequisite: Virtual Environment

```bash
# Activate your virtual environment
cd c:\Research\Coding\Research\After\ 1st\ Experiement\Clouseau-with-Local-LLM-support

# Windows (PowerShell)
.\win_venv\Scripts\Activate.ps1

# Windows (Command Prompt)
win_venv\Scripts\activate.bat

# Or if using conda
conda activate clouseau-env

# Verify Python
python --version  # Should be 3.12+
```

### Step 1: Set LLM Environment Variables

```bash
# Option A: Use OpenAI (GPT-4.1-Mini)
$env:LLM_MODEL = "gpt-4-turbo"
$env:API_KEY = "your-openai-api-key"
$env:BASE_URL = "https://api.openai.com/v1"

# Option B: Use Local vLLM (Gemma, Llama, etc.)
$env:LLM_MODEL = "meta-llama/Llama-2-7b-chat"
$env:API_KEY = "local"
$env:BASE_URL = "http://localhost:8000/v1"

# Option C: Use DGX vLLM
$env:LLM_MODEL = "gemma-4-26b-moe"
$env:API_KEY = "local"
$env:BASE_URL = "http://172.31.0.94:8000/v1"  # DGX IP
```

### Step 2: Run a Single Scenario (60 seconds)

```bash
cd artifact

# Run single-host scenarios (S1-S4) - Quick test
python app.py --scenarios-si --no-warn

# Expected output:
# Investigating s1
#   Clue: IP
#   ... execution ...
#   Investigating s2
#   ... etc
```

### Step 3: View Results

```bash
# Quick summary
python compare.py latest

# Or detailed analysis
python compare.py show 20260506_143022
```

---

## Environment Setup

### Option 1: Local Machine (Windows/Mac/Linux)

#### 1a. Install Dependencies

```bash
cd artifact
pip install -r requirements.txt
```

#### 1b. Start Local LLM (Optional)

If using Ollama or similar local LLM:

```bash
# Terminal 1: Start LLM server
ollama serve

# Or vLLM
python -m vllm.entrypoints.openai.api_server \
  --model meta-llama/Llama-2-7b-chat \
  --port 8000

# Terminal 2: Verify it's running
curl http://localhost:8000/v1/models
```

#### 1c. Test Connection

```bash
python -c "
from llm_factory import create_llm_from_env
llm = create_llm_from_env()
print('✓ LLM connection successful')
"
```

---

### Option 2: DGX Remote Setup

#### 2a. SSH to DGX

```bash
ssh user@172.31.0.94

# Or with key
ssh -i /path/to/key.pem user@172.31.0.94
```

#### 2b. Verify vLLM is Running

```bash
# Check if vLLM service is active
systemctl status vllm

# Or manually start it
python -m vllm.entrypoints.openai.api_server \
  --model /home/dgx-spark-01/ai_data/models/gemma-4-26b-moe \
  --tensor-parallel-size 4 \
  --gpu-memory-utilization 0.9
```

#### 2c. Run Tests on DGX

```bash
# Transfer code (if not already there)
scp -r artifact/* user@172.31.0.94:/path/to/clouseau/artifact/

# SSH in and run
ssh user@172.31.0.94

cd /path/to/clouseau/artifact

export LLM_MODEL="gemma-4-26b-moe"
export BASE_URL="http://localhost:8000/v1"
export API_KEY="local"

# Run tests
python run_with_logging.py
```

---

## Running Individual Tests

### Test 1: Single-Host Scenarios (S1-S4)

```bash
cd artifact

# Run all single-host scenarios
python app.py --scenarios-si --no-warn

# With custom parameters
python app.py --scenarios-si \
  --max-investigations 15 \
  --max-questions 20 \
  --max-queries 15

# Output to specific CSV
python app.py --scenarios-si \
  --csv-file results/s1-s4.csv
```

**Expected output:**
```
Investigating s1
  Clue: IP
    Query 1: Find processes connecting to IP...
    Query 2: Check DNS for IP...
    ... investigation continues ...
    Final Report: Attack artifacts found: {...}
  Clue: domain
    ... similar investigation ...
  Clue: file
    ... similar investigation ...

Investigating s2
  ... (repeats for S2, S3, S4)
```

**Approximate runtime:** 5-10 minutes per scenario

---

### Test 2: Extended Scenarios (SE1-SE4) - Semantic Gap Test

```bash
cd artifact

# Run extended single-host scenarios
python app.py --scenarios-se --no-warn

# These test robustness to:
# - Different C2 IP addresses
# - Larger semantic gaps between artifacts
# - More realistic attack setup
```

**Expected output:** Similar to S1-S4, but with 4 scenarios (SE1-SE4)

**Approximate runtime:** 5-10 minutes per scenario

---

### Test 3: Keyword Sensitivity (SS1-SS4)

```bash
cd artifact

# Run keyword sensitivity scenarios
python app.py --scenarios-ss --no-warn

# These test robustness to artifact renaming:
# - Domain: 0xalsaheel.com → official-system-monitoring.xyz
# - Executable: payload.exe → systempatch.exe
```

**Expected output:** Same format as others

**Approximate runtime:** 5-10 minutes per scenario

---

### Test 4: Multi-Host Scenarios (M1-M6)

```bash
cd artifact

# Run multi-host (lateral movement) scenarios
python app.py --scenarios-mi --no-warn

# More complex: involves multiple machines
```

**Approximate runtime:** 10-15 minutes per scenario

---

### Test 5: OpTC Scenarios (DARPA Dataset)

```bash
cd artifact

# Run DARPA OpTC scenarios
python app.py --scenarios-optc --no-warn

# These are:
# - OpTC1: PowerShell Empire (plain)
# - OpTC2: PowerShell Empire (custom)
# - OpTC3: Malicious upgrade
```

**Approximate runtime:** 15-20 minutes per scenario

---

### Test 6: Single Scenario + Single POI

```bash
cd artifact

# Run just scenario S1, just the "IP" point of interest
python app.py --scenarios-si \
  --target-scenario S1 \
  --target-poi IP

# Run just scenario S2, file POI
python app.py --scenarios-si \
  --target-scenario S2 \
  --target-poi file

# Available POI types:
# - IP (network address)
# - domain (domain name)
# - file (file path)
```

**Approximate runtime:** 30-60 seconds

---

## Running All Claims

### Claim 1: Single-Host (S1-S4)

```bash
cd artifact

# Manual run
python app.py --scenarios-si --csv-file ../claims/claim1/results.csv

# Or use the claim script
cd ../claims/claim1
bash run.sh

# Expected output in: average.csv
# Columns: scenario, recall, precision, f1
# Expected: recall>0.95, precision>0.95, f1>0.95
```

---

### Claim 2: Extended Single-Host (SE1-SE4)

```bash
cd artifact

# Manual run
python app.py --scenarios-se --csv-file ../claims/claim2/results.csv

# Or use the claim script
cd ../claims/claim2
bash run.sh

# Expected output in: average.csv
# Same expectations as Claim 1 (should be robust to semantic gap)
```

---

### Claim 3: Keyword Sensitivity (SS1-SS4)

```bash
cd artifact

# Manual run
python app.py --scenarios-ss --csv-file ../claims/claim3/results.csv

# Or use the claim script
cd ../claims/claim3
bash run.sh

# Expected output in: average.csv
# Same expectations (should be robust to renaming)
```

---

### Run All Claims (Comprehensive)

```bash
cd artifact

# Option 1: Run with logging (recommended)
python run_with_logging.py

# This runs all three claims and logs results to test_logs/

# Option 2: Run manually one by one
python app.py --scenarios-si --csv-file ../claims/claim1/results.csv
python app.py --scenarios-se --csv-file ../claims/claim2/results.csv
python app.py --scenarios-ss --csv-file ../claims/claim3/results.csv

# Expected total runtime: 3-5 hours (depends on scenario complexity)
```

---

## Running with Logging

### Automatic Logging (Recommended)

```bash
cd artifact

# Run all tests with automatic logging
python run_with_logging.py

# This will:
# 1. Create a test_logs/TIMESTAMP/ directory
# 2. Run all claims
# 3. Log each test result (precision, recall, F1, duration)
# 4. Store in SQLite database
# 5. Export CSV and JSON
# 6. Generate analysis and visualizations

# Output structure:
# test_logs/
# ├── 20260506_143022/
# │   ├── run_metadata.json (test info)
# │   ├── test_results.csv (detailed metrics)
# │   └── analysis_summary.json
# ├── test_runs.db (SQLite database)
# └── visualizations/
#     ├── precision_comparison.png
#     ├── recall_comparison.png
#     └── f1_comparison.png
```

---

### View Test Results

```bash
cd artifact

# List all test runs
python compare.py list

# Output:
# Run ID            | Start Time          | Model        | Avg F1  | Status
# 20260506_143022   | 2026-05-06 14:30:22 | gemma-4-26b  | 88.56%  | ✓
# 20260505_091155   | 2026-05-05 09:11:55 | gpt-4-turbo  | 99.78%  | ✓

# Compare two runs
python compare.py compare 20260506_143022 20260505_091155

# Show single run details
python compare.py show 20260506_143022

# Output:
# Run: 20260506_143022
# Model: gemma-4-26b-moe
# Duration: 5.5 hours
# Tests: 50
# Success rate: 100%
# 
# Metrics:
#   Precision: 98.10%
#   Recall: 88.43%
#   F1: 88.56%
```

---

### Generate Visualizations

```bash
cd artifact

# Auto-generate charts
python results_visualizer.py

# This creates PNG files in test_logs/visualizations/:
# - precision_comparison.png (box plot)
# - recall_comparison.png (box plot)
# - f1_comparison.png (box plot)
# - scenario_breakdown.png (bar chart by scenario)
```

---

## Interpreting Results

### Output CSV Format

```csv
scenario_name,test_name,start_time,end_time,duration_seconds,tp,tn,fp,fn,precision,recall,fpr,f1,status
Claim 1,s1_IP,2026-04-28T15:01:29,2026-04-28T15:01:30,1.2,276,90488,2,4322,0.9928,0.06,0.0,0.1132,success
Claim 1,s1_domain,2026-04-28T15:01:30,2026-04-28T15:01:31,0.8,4598,90490,0,0,1.0,1.0,0.0,1.0,success
```

### Understanding Metrics

```
TP (True Positive):   Malicious events correctly flagged ✓
TN (True Negative):   Benign events correctly accepted ✓
FP (False Positive):  Benign events incorrectly flagged ✗ (analyst burden)
FN (False Negative):  Malicious events missed ✗ (security gap)

Precision = TP / (TP + FP)     → Accuracy of malicious flagging (0-100%)
Recall = TP / (TP + FN)        → Coverage of malicious events (0-100%)
FPR = FP / (FP + TN)           → False alarm rate (0-100%, lower is better)
F1 = 2 × (Precision × Recall) / (Precision + Recall)  → Harmonic mean

Example (s1_domain from above):
  TP=4598 (found 4598 malicious events)
  FP=0 (no false alarms)
  FN=0 (missed 0 events)
  Precision=1.0 (100% - perfect!)
  Recall=1.0 (100% - found everything!)
  F1=1.0 (100% - perfect score!)

Example (s1_IP from above - this one fails):
  TP=276 (only found 276 out of many)
  FP=2 (2 false alarms)
  FN=4322 (missed 4322 events!)
  Precision=0.9928 (99% precise)
  Recall=0.06 (only 6% - catastrophic miss rate!)
  F1=0.1132 (very poor)
```

### What "Good" Performance Looks Like

```
Excellent:  F1 > 95%  (Precision > 95%, Recall > 95%)
Good:       F1 > 85%  (Precision > 80%, Recall > 80%)
Acceptable: F1 > 70%  (Precision > 70%, Recall > 60%)
Poor:       F1 < 70%  (Needs investigation)

Your baseline:
  Average F1: 88.56% → GOOD (not excellent, but solid)
  Precision: 98.10%  → EXCELLENT (few false alarms)
  Recall: 88.43%     → GOOD (missing ~11% of events)

Paper baseline:
  Average F1: 99.79% → EXCELLENT
  Precision: 99.93%  → EXCELLENT
  Recall: 99.65%     → EXCELLENT
```

---

## Troubleshooting

### Problem 1: "No module named 'langchain_openai'"

**Solution:**
```bash
pip install -r artifact/requirements.txt
# Or manually:
pip install langchain-openai langchain-core langgraph pandas
```

---

### Problem 2: "LLMConfigError: Invalid LLM configuration"

**Cause:** Missing or incorrect environment variables

**Solution:**
```bash
# Check variables are set
echo $env:LLM_MODEL
echo $env:API_KEY
echo $env:BASE_URL

# Set them correctly
$env:LLM_MODEL = "gpt-4-turbo"
$env:API_KEY = "sk-..."
$env:BASE_URL = "https://api.openai.com/v1"

# Then test
python -c "from llm_factory import create_llm_from_env; print('OK')"
```

---

### Problem 3: "Connection refused" when connecting to vLLM

**Cause:** Local LLM server not running

**Solution:**
```bash
# Terminal 1: Start vLLM
python -m vllm.entrypoints.openai.api_server --model meta-llama/Llama-2-7b-chat

# Terminal 2: Test connection
curl http://localhost:8000/v1/models

# If successful, you'll see:
# {"data": [{"id": "meta-llama/Llama-2-7b-chat", ...}]}
```

---

### Problem 4: Tests running extremely slowly (or timing out)

**Cause:** Model is overloaded or context window exceeded

**Solution:**
```bash
# Reduce investigation depth
python app.py --scenarios-si \
  --max-investigations 5 \
  --max-questions 5 \
  --max-queries 5

# Or increase timeout
export TIMEOUT_SECONDS=3600  # 1 hour
python app.py --scenarios-si
```

---

### Problem 5: "Database is locked" error

**Cause:** Multiple processes writing to SQLite simultaneously

**Solution:**
```bash
# Don't run multiple instances simultaneously
# Run them sequentially instead

python app.py --scenarios-si
# Wait for completion

python app.py --scenarios-se
# Wait for completion

python app.py --scenarios-ss
```

---

### Problem 6: Results show 0% F1 on specific scenario

**Cause:** Investigation failed, empty results

**Solution:**
```bash
# Run in debug mode to see error messages
python app.py --scenarios-si --target-scenario S1 --target-poi IP -v

# Check logs
cat test_logs/LATEST/test_results.csv

# If error_message column has content, LLM had issues
```

---

### Problem 7: API quota exceeded (OpenAI)

**Solution:**
```bash
# Switch to local LLM instead
$env:LLM_MODEL = "meta-llama/Llama-2-7b-chat"
$env:BASE_URL = "http://localhost:8000/v1"
$env:API_KEY = "local"

python app.py --scenarios-si
```

---

## Advanced Options

### Custom Hyperparameters

```bash
cd artifact

# Increase investigation depth for hard scenarios
python app.py --scenarios-si \
  --max-investigations 20 \
  --max-questions 25 \
  --max-queries 20 \
  --max-tokens 3000

# Reduce for faster iteration (testing only)
python app.py --scenarios-si \
  --max-investigations 3 \
  --max-questions 3 \
  --max-queries 3
```

### Ablation Studies

```bash
# Test single-agent vs multi-agent
python app.py --scenarios-si --ablation-single-agent

# Disable specific QA agents
python app.py --scenarios-si --disable-browser-agent

# Use different LLM temperature (0=deterministic, 1=random)
$env:LLM_TEMPERATURE = "0.5"
python app.py --scenarios-si
```

### Export for Analysis

```bash
# Export results as JSON for custom analysis
python results_analyzer.py --export-json results.json

# Export as Pandas DataFrame
python -c "
import pandas as pd
df = pd.read_csv('test_logs/LATEST/test_results.csv')
df.to_json('analysis.json', orient='records')
df.describe()  # Summary statistics
"
```

### Parallel Testing (Advanced)

```bash
# Use GNU Parallel (Linux/Mac) to run multiple scenarios
cat > test_scenarios.txt << EOF
--scenarios-si --target-scenario S1
--scenarios-si --target-scenario S2
--scenarios-si --target-scenario S3
--scenarios-si --target-scenario S4
EOF

parallel --pipe python app.py < test_scenarios.txt

# Or Python's multiprocessing (Windows-compatible)
python -c "
from multiprocessing import Pool
import subprocess
scenarios = ['S1', 'S2', 'S3', 'S4']
with Pool(2) as p:
    p.map(lambda s: subprocess.run(['python', 'app.py', 
           '--scenarios-si', '--target-scenario', s]), scenarios)
"
```

---

## Typical Workflows

### Workflow 1: Quick Test (5 minutes)

```bash
# Just verify everything works
cd artifact
python app.py --scenarios-si --target-scenario S1 --target-poi IP
# Check output for errors
```

---

### Workflow 2: Full Evaluation (5-6 hours)

```bash
cd artifact
python run_with_logging.py
# Runs all 3 claims (S1-S4, SE1-SE4, SS1-SS4)
# Generates logs, analysis, visualizations

# View results
python compare.py latest
```

---

### Workflow 3: Continuous Development (iterative)

```bash
# Test individual scenarios as you make code changes
cd artifact

# Make code change in investigator.py
nano investigator.py

# Quick test
python app.py --scenarios-si --target-scenario S1 --target-poi IP

# Check if F1 improved
python compare.py show LATEST

# Iterate...
```

---

### Workflow 4: Compare Models

```bash
# Test with Model A (GPT-4-Turbo)
$env:LLM_MODEL = "gpt-4-turbo"
$env:API_KEY = "sk-..."
python run_with_logging.py
# Store run ID: 20260506_143000

# Switch to Model B (Gemma-4)
$env:LLM_MODEL = "gemma-4-26b-moe"
$env:BASE_URL = "http://localhost:8000/v1"
$env:API_KEY = "local"
python run_with_logging.py
# Store run ID: 20260506_150000

# Compare
python compare.py compare 20260506_143000 20260506_150000
```

---

## Performance Expectations

| Test Type | Avg Runtime | Expected F1 | Machine |
|-----------|-------------|-------------|---------|
| Single POI (S1 IP) | 30-60s | 80-99% | Local |
| Single Scenario (S1) | 2-5 min | 85-99% | Local |
| All Single-Host (S1-S4) | 10-20 min | 88-99% | Local |
| All Extended (SE1-SE4) | 10-20 min | 85-99% | Local |
| All Keywords (SS1-SS4) | 10-20 min | 84-99% | Local |
| All Claims (3×12 tests) | 3-5 hours | 88-99% | DGX |

---

## Monitoring Test Progress

### While Tests are Running

```bash
# Terminal 1: Run tests
python run_with_logging.py

# Terminal 2: Monitor logs in real-time
tail -f test_logs/LATEST/test_results.csv

# Terminal 3: Check system resources (if on DGX)
watch -n 5 'nvidia-smi'  # GPU usage
watch -n 5 'free -h'     # Memory usage
```

---

## Next Steps

After running tests:

1. **View Results:** `python compare.py latest`
2. **Analyze:** Check PERFORMANCE_COMPARISON.md for your baseline
3. **Optimize:** Use Advanced Options to tune hyperparameters
4. **Extend:** Ready to add OT testing? See next guide.

---

**Questions?** Check TEST_LOGGING_GUIDE.md for logging details.
