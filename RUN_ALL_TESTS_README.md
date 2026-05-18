# Automated Test Runner Scripts

## Overview

Two Python scripts automate running all 63 Clouseau tests:

1. **`run_all_tests_1x.py`** - Run all 63 tests once (10 hours) - *FAST VALIDATION*
2. **`run_all_tests_3x.py`** - Run all 63 tests 3 times (30 hours) - *PUBLICATION QUALITY*

Both scripts automatically:
- ✅ Run all 5 test types (S1-S4, SE1-SE4, SS1-SS4, M1-M6, OpTC1-3)
- ✅ Save results with timestamps
- ✅ Track progress and timing
- ✅ Aggregate and average results
- ✅ Show final metrics comparison

---

## Quick Start

### Option 1: Fast Validation (10 hours)

```bash
cd c:\Research\Coding\Research\After\ 1st\ Experiement\Clouseau-with-Local-LLM-support

# Set environment variables first
$env:LLM_MODEL = "gemma-4-26b-moe"
$env:API_KEY = "local"
$env:BASE_URL = "http://172.31.0.94:8000/v1"

# Run once
python run_all_tests_1x.py
```

**What happens:**
- Runs 63 tests sequentially
- Takes ~10 hours
- Saves results to `artifact/results_1x_run/`
- Shows summary at the end
- **Good for:** Validating everything works before 3x run

---

### Option 2: Publication Quality (30 hours)

```bash
cd c:\Research\Coding\Research\After\ 1st\ Experiement\Clouseau-with-Local-LLM-support

# Set environment variables first
$env:LLM_MODEL = "gemma-4-26b-moe"
$env:API_KEY = "local"
$env:BASE_URL = "http://172.31.0.94:8000/v1"

# Run 3 times with averaging
python run_all_tests_3x.py
```

**What happens:**
- Runs 63 tests × 3 times = 189 total executions
- Takes ~30 hours over 2-3 days
- Saves all results to `artifact/results_3x_runs/`
- Automatically aggregates and averages
- Shows comparison to paper baseline
- **Good for:** Final evaluation for paper/publication

---

## Detailed Usage

### Before Running

1. **Activate virtual environment:**
   ```bash
   .\win_venv\Scripts\Activate.ps1
   ```

2. **Set LLM environment variables (choose one):**

   **For OpenAI (GPT-4):**
   ```bash
   $env:LLM_MODEL = "gpt-4-turbo"
   $env:API_KEY = "sk-..."
   $env:BASE_URL = "https://api.openai.com/v1"
   ```

   **For Local vLLM (Gemma, Llama, etc):**
   ```bash
   $env:LLM_MODEL = "meta-llama/Llama-2-7b-chat"
   $env:API_KEY = "local"
   $env:BASE_URL = "http://localhost:8000/v1"
   ```

   **For DGX (NVIDIA):**
   ```bash
   $env:LLM_MODEL = "gemma-4-26b-moe"
   $env:API_KEY = "local"
   $env:BASE_URL = "http://172.31.0.94:8000/v1"
   ```

3. **Verify LLM connectivity:**
   ```bash
   cd artifact
   python -c "from llm_factory import create_llm_from_env; print('✓ LLM OK')"
   ```

### Running the 1x Script

```bash
python run_all_tests_1x.py
```

**Output:**
```
================================================================================
  CLOUSEAU FULL EVALUATION: 63 Tests (1 Run)
================================================================================

Test Breakdown:
  • S1-S4 (Single-host): 12 tests
  • SE1-SE4 (Extended semantic gap): 12 tests
  • SS1-SS4 (Keyword sensitivity): 12 tests
  • M1-M6 (Multi-host lateral movement): 18 tests
  • OpTC1-3 (DARPA generalization): 9 tests

Total: 63 unique tests
Estimated time: ~10 hours
Start time: 2026-05-07 14:30:00
Run ID: 20260507_143000

Press ENTER to start testing (or Ctrl+C to cancel)...

>>> Testing S1-S4 (Single-host) (12 tests)
Command: python app.py --scenarios-si --csv-file artifact/results_1x_run/20260507_143000_single_host.csv --no-warn
Output: 20260507_143000_single_host.csv
✓ S1-S4 completed in 108.5 minutes

[... continues for SE1-SE4, SS1-SS4, M1-M6, OpTC1-3 ...]

================================================================================
  EXECUTION SUMMARY
================================================================================

Test Results:
  • Successful: 5/5
  • Failed: 0/5
  • Total duration: 10.2 hours

Results saved to: artifact/results_1x_run/
Run ID for reference: 20260507_143000

Next Steps:
1. Review results: python compare.py show 20260507_143000
2. View details: ls -la artifact/results_1x_run/
3. Ready for 3x runs? Run: python run_all_tests_3x.py
```

### Running the 3x Script

```bash
python run_all_tests_3x.py
```

**Similar output, but for 3 runs with aggregation at the end:**

```
================================================================================
  AGGREGATING RESULTS
================================================================================

Found 15 CSV files to aggregate
  ✓ run1_single_host.csv
  ✓ run1_extended.csv
  [... continues ...]

✓ Saved aggregated results to: artifact/results_3x_runs/AGGREGATED_RESULTS_3X.csv

================================================================================
  FINAL RESULTS (3-Run Average)
================================================================================

Overall Metrics:
  • Average F1 Score: 0.8856 (±0.0234)
  • Average Precision: 0.9810 (±0.0089)
  • Average Recall: 0.8843 (±0.0267)
  • Average FPR: 0.0190

Per-Test-Type Average F1:
  • Claim 1: 0.8804 (±0.0312)
  • Claim 2: 0.8599 (±0.0487)
  • Claim 3: 0.8418 (±0.0456)
  • Multi-Host: 0.9237 (±0.0156)
  • DARPA OpTC: 0.9125 (±0.0189)

Best Performing Test:
  • ss4_file: F1=0.9939

Worst Performing Test:
  • se2_IP: F1=0.0227

Comparison to Paper Baseline:
  • Paper F1: 0.9979 (GPT-4.1-Mini)
  • Your F1: 0.8856
  • Gap: -11.23 percentage points
```

---

## Understanding the Output

### Result Files

**1x run creates:**
```
artifact/results_1x_run/
├── 20260507_143000_single_host.csv     # S1-S4 results
├── 20260507_143000_extended.csv        # SE1-SE4 results
├── 20260507_143000_keywords.csv        # SS1-SS4 results
├── 20260507_143000_multi_host.csv      # M1-M6 results
└── 20260507_143000_optc.csv            # OpTC1-3 results
```

**3x runs create:**
```
artifact/results_3x_runs/
├── run1_single_host.csv, run2_single_host.csv, run3_single_host.csv
├── run1_extended.csv, run2_extended.csv, run3_extended.csv
├── run1_keywords.csv, run2_keywords.csv, run3_keywords.csv
├── run1_multi_host.csv, run2_multi_host.csv, run3_multi_host.csv
├── run1_optc.csv, run2_optc.csv, run3_optc.csv
└── AGGREGATED_RESULTS_3X.csv            # Final averaged results
```

### CSV Columns

Each result CSV contains:
- `scenario_name` - Claim 1, Claim 2, Claim 3, Multi-Host, OpTC
- `test_name` - s1_IP, s1_domain, etc.
- `precision` - % correct positive predictions
- `recall` - % malicious events caught
- `f1` - Harmonic mean (main metric)
- `fpr` - False positive rate
- `duration_seconds` - Test execution time

---

## Monitoring Progress

### While script is running:

```bash
# In another terminal, monitor the results directory
Get-ChildItem artifact/results_1x_run/ -File | Sort-Object LastWriteTime | Select-Object Name,Length,LastWriteTime

# Or track the CSV growth
Get-Content artifact/results_1x_run/*/csv | Measure-Object -Line
```

### Check DGX GPU usage (if on DGX):

```bash
ssh user@172.31.0.94
watch -n 5 nvidia-smi  # GPU usage
watch -n 5 free -h     # Memory usage
```

---

## Troubleshooting

### Script hangs / No progress

**Solution:**
```bash
# Check if app.py is running
Get-Process python

# Monitor network to DGX
ping 172.31.0.94

# Check LLM endpoint
curl http://172.31.0.94:8000/v1/models
```

### Out of disk space

**Solution:**
```bash
# Clear old test logs
Remove-Item artifact/test_logs/20260426* -Recurse  # Remove old runs

# Or move to external drive
robocopy artifact\results_1x_run\ D:\backup\ /S
```

### Script interrupted

**To resume from where it stopped:**
```bash
# Scripts create timestamped results, so re-run from same test type
# Manual approach:
python app.py --scenarios-mi --csv-file artifact/results_1x_run/20260507_resume_multi_host.csv
python app.py --scenarios-optc --csv-file artifact/results_1x_run/20260507_resume_optc.csv
```

---

## Recommended Workflow

### Day 1: Validation
```bash
# Run 1x to verify everything works
python run_all_tests_1x.py    # ~10 hours

# Check if results look good
python compare.py show LATEST
```

### Day 2-3: Publication Quality
```bash
# If Day 1 looks good, commit to 3x
python run_all_tests_3x.py    # ~30 hours

# Automatic aggregation and averaging happens at the end
```

### Analyze Results
```bash
# View aggregated results
python compare.py show LATEST

# Export for paper
copy artifact/results_3x_runs/AGGREGATED_RESULTS_3X.csv results_for_paper.csv
```

---

## Environment Variables (Persistent)

To make environment variables persist across sessions:

```powershell
# Set permanently in PowerShell
[Environment]::SetEnvironmentVariable("LLM_MODEL", "gemma-4-26b-moe", "User")
[Environment]::SetEnvironmentVariable("API_KEY", "local", "User")
[Environment]::SetEnvironmentVariable("BASE_URL", "http://172.31.0.94:8000/v1", "User")

# Restart PowerShell to take effect
```

---

## FAQ

**Q: Can I stop the script and resume?**
A: Yes, each test type saves its own CSV. If interrupted, rerun and it will append more results.

**Q: How do I use results for the paper?**
A: Use `AGGREGATED_RESULTS_3X.csv` for final metrics. Paste into paper's Table 2 (your results vs paper).

**Q: What if a single test times out?**
A: Script will skip it and continue. Check that test's CSV - it will have fewer rows.

**Q: Can I run on multiple machines simultaneously?**
A: Yes, use different output directories. Then manually aggregate CSVs afterward.

**Q: How do I compare 1x vs 3x results?**
A: Use `python compare.py compare RUN_ID_1X RUN_ID_3X`

---

## Next Steps After Testing

1. **View results:** `python compare.py latest`
2. **Compare to paper:** Check `PERFORMANCE_COMPARISON.md`
3. **Identify issues:** Look for low F1 tests (< 70%)
4. **Optimize:** Adjust hyperparameters and retest
5. **Write paper:** Use final metrics in Clouseau-OT paper

---

**Need help?** Check TEST_EXECUTION_GUIDE.md or COMMANDS_CHEAT_SHEET.md for more details.
