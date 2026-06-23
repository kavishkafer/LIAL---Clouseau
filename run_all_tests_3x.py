#!/usr/bin/env python3
"""
Master test runner: Execute all 63 tests 3 times and aggregate results
Usage: python run_all_tests_3x.py
"""

import subprocess
import sys
import os
import time
from pathlib import Path
from datetime import datetime
import pandas as pd

class MasterTestRunner:
    """Run all 63 Clouseau tests 3 times and aggregate results"""
    
    def __init__(self):
        self.artifact_dir = Path("artifact")
        
        # Determine results directory
        results_dir_env = os.environ.get("RESULTS_DIR")
        if results_dir_env:
            self.results_dir = Path(results_dir_env).resolve()
            print(f"--> Using RESULTS_DIR from environment: {self.results_dir}")
        else:
            # Resolve model ID dynamically to determine target directory
            env = os.environ.copy()
            base_url = env.get('BASE_URL', 'http://127.0.0.1:8000/v1')
            resolved_model = env.get('LLM_MODEL', None)
            
            if not resolved_model:
                import urllib.request
                import json
                try:
                    req = urllib.request.Request(f"{base_url}/models")
                    with urllib.request.urlopen(req, timeout=3) as response:
                        data = json.loads(response.read().decode())
                        if data and "data" in data and len(data["data"]) > 0:
                            resolved_model = data["data"][0]["id"]
                except Exception:
                    pass
            
            if resolved_model:
                model_basename = os.path.basename(resolved_model.rstrip("/"))
                model_slug = model_basename.lower().replace("-", "_").replace(".", "_")
                if "gemma_4" in model_slug or "gemma-4" in resolved_model:
                    model_slug = "gemma4_26b_bf16"
                elif "nemotron_3" in model_slug or "nemotron" in resolved_model.lower():
                    model_slug = "nemotron3_super_nvfp4"
                elif "qwen3_6" in model_slug or "qwen3.6" in resolved_model.lower():
                    model_slug = "qwen3_6_35b_a3b_instruct"
                elif "qwen3_5" in model_slug or "qwen3.5" in resolved_model.lower():
                    model_slug = "qwen3_5_9b_instruct"
                elif "deepseek" in model_slug or "deepseek" in resolved_model.lower():
                    model_slug = "deepseek_v4_flash"
            else:
                model_slug = "unknown_model"
                
            self.results_dir = (self.artifact_dir / "results" / model_slug).resolve()
            
        self.results_dir.mkdir(parents=True, exist_ok=True)
        print(f"--> Selected results directory based on model/configuration: {self.results_dir}")
        
        # Test configurations
        self.test_configs = [
            ("--scenarios-si", "single_host", "S1-S4 (Single-host)"),
            ("--scenarios-se", "extended", "SE1-SE4 (Extended semantic gap)"),
            ("--scenarios-ss", "keywords", "SS1-SS4 (Keyword sensitivity)"),
            ("--scenarios-mi", "multihost", "M1-M6 (Multi-host)"),
            ("--scenarios-optc", "optc", "OpTC (Generalizability)"),
        ]
        
        self.total_tests = 81  # 12 S + 12 SE + 12 SS + 36 MI + 9 OpTC
        self.num_runs = 3
        self.start_time = None
        
    def print_header(self, text):
        """Print formatted header"""
        print("\n" + "="*80)
        print(f"  {text}")
        print("="*80 + "\n")
    
    def print_section(self, text):
        """Print formatted section"""
        print(f"\n>>> {text}")
    
    def get_time_estimate(self, tests_per_hour=6.3):
        """Calculate time estimate for full run"""
        hours_per_run = self.total_tests / tests_per_hour
        total_hours = hours_per_run * self.num_runs
        return hours_per_run, total_hours
    
    def wait_for_vllm(self, base_url, timeout_minutes=60):
        """Wait for the vLLM server to be online and responsive."""
        print(f"Checking if vLLM server at {base_url} is online...")
        import urllib.request
        import json
        start_time = time.time()
        while True:
            try:
                req = urllib.request.Request(f"{base_url}/models")
                with urllib.request.urlopen(req, timeout=5) as response:
                    data = json.loads(response.read().decode())
                    if data and "data" in data and len(data["data"]) > 0:
                        print("--> vLLM server is online and responsive.")
                        return True
            except Exception as e:
                elapsed = (time.time() - start_time) / 60
                if elapsed > timeout_minutes:
                    print(f"--> vLLM server remains offline after {timeout_minutes} minutes. Giving up.")
                    return False
                print(f"--> vLLM server is offline/unreachable ({e}). Waiting 60 seconds to retry... (Elapsed: {elapsed:.1f}/{timeout_minutes} min)")
                time.sleep(60)

    def run_test_config(self, scenario_flag, config_name, display_name, run_num):
        """Run a single test configuration with retry logic and vLLM health check"""
        output_csv = self.results_dir / f"run{run_num}_{config_name}.csv"
        
        cmd = [
            sys.executable,
            "app.py",
            scenario_flag,
            "--csv-file", str(output_csv),
            "--no-warn"
        ]
        
        # Pass --resume if the outer script was called with it
        if "--resume" in sys.argv:
            cmd.append("--resume")
        
        # Ensure LLM env vars are resolved
        env = os.environ.copy()
        base_url = env.get('BASE_URL', 'http://127.0.0.1:8000/v1')
        env.setdefault('BASE_URL', base_url)
        env.setdefault('API_KEY', 'local')

        # Ensure LLM server is online before launching
        if not self.wait_for_vllm(base_url, timeout_minutes=60):
            print(f"✗ Cannot start {display_name}: LLM endpoint is offline.")
            return False

        max_attempts = 3
        attempt = 0
        while attempt < max_attempts:
            attempt += 1
            if attempt > 1:
                print(f"\n--- Retrying {display_name} (Attempt {attempt}/{max_attempts}) ---")
                if "--resume" not in cmd:
                    cmd.append("--resume")
            
            self.print_section(f"[Run {run_num}/3] Testing {display_name} (Attempt {attempt}/{max_attempts})")
            print(f"Command: {' '.join(cmd)}")
            print(f"Output: {output_csv}")
            
            try:
                start = time.time()
                
                # Resolve LLM_MODEL dynamically (on first check or retry)
                if 'LLM_MODEL' not in env or attempt > 1:
                    import urllib.request
                    import json
                    resolved_model = None
                    try:
                        req = urllib.request.Request(f"{base_url}/models")
                        with urllib.request.urlopen(req, timeout=5) as response:
                            data = json.loads(response.read().decode())
                            if data and "data" in data and len(data["data"]) > 0:
                                resolved_model = data["data"][0]["id"]
                    except Exception:
                        pass

                    if resolved_model:
                        env['LLM_MODEL'] = resolved_model
                        print(f"--> Dynamically resolved LLM_MODEL: {resolved_model}")
                    else:
                        env.setdefault('LLM_MODEL', 'gemma4')
                
                result = subprocess.run(
                    cmd,
                    cwd=self.artifact_dir,
                    timeout=43200,  # 12 hour timeout per test type
                    capture_output=False,
                    env=env
                )
                duration = time.time() - start
                
                if result.returncode == 0:
                    print(f"✓ {display_name} completed in {duration/60:.1f} minutes")
                    return True
                else:
                    print(f"✗ {display_name} failed with return code {result.returncode}")
                    if attempt < max_attempts:
                        print("Checking LLM endpoint health before retrying...")
                        if not self.wait_for_vllm(base_url, timeout_minutes=60):
                            print("LLM endpoint is completely offline. Giving up.")
                            return False
                        time.sleep(10)
                        
            except subprocess.TimeoutExpired:
                print(f"✗ {display_name} timed out after 4 hours")
                return False
            except Exception as e:
                print(f"✗ {display_name} error: {e}")
                if attempt < max_attempts:
                    print("Checking LLM endpoint health before retrying...")
                    self.wait_for_vllm(base_url, timeout_minutes=60)
                    time.sleep(10)
                else:
                    return False
        
        return False
    
    def run_all_3x(self):
        """Execute all tests 3 times"""
        self.start_time = time.time()
        hour_per_run, total_hours = self.get_time_estimate()
        
        self.print_header("CLOUSEAU FULL EVALUATION: 63 Tests × 3 Runs")
        
        print(f"Test Coverage:")
        print(f"  • Single-Host (S1-S4): 12 tests")
        print(f"  • Extended (SE1-SE4): 12 tests")
        print(f"  • Keywords (SS1-SS4): 12 tests")
        print(f"  • Multi-Host (M1-M6): 18 tests")
        print(f"  • DARPA OpTC (OpTC1-3): 9 tests")
        print(f"  • TOTAL: {self.total_tests} unique tests")
        print(f"\nExecution Plan:")
        print(f"  • {self.num_runs} complete runs")
        print(f"  • {self.num_runs * self.total_tests} total test executions")
        print(f"  • Estimated time per run: {hour_per_run:.1f} hours")
        print(f"  • Total estimated time: {total_hours:.1f} hours")
        print(f"\nStart time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Estimated completion: {datetime.now().strftime('%Y-%m-%d')} + {int(total_hours)} hours")
        
        results = {
            "run": [],
            "test_type": [],
            "status": [],
            "duration": [],
            "tests": []
        }
        
        # Run 3 times
        for run_num in range(1, self.num_runs + 1):
            self.print_header(f"RUN {run_num} of {self.num_runs}")
            run_start = time.time()
            
            for scenario_flag, config_name, display_name in self.test_configs:
                success = self.run_test_config(scenario_flag, config_name, display_name, run_num)
                results["run"].append(run_num)
                results["test_type"].append(display_name)
                results["status"].append("✓" if success else "✗")
                
            run_duration = (time.time() - run_start) / 3600
            print(f"\nRun {run_num} completed in {run_duration:.1f} hours")
        
        total_duration = (time.time() - self.start_time) / 3600
        self.print_header("EXECUTION COMPLETE")
        print(f"Total time: {total_duration:.1f} hours")
        print(f"Results directory: {self.results_dir}/")
        
        return True
    
    def aggregate_results(self):
        """Aggregate and average results from 3 runs"""
        self.print_header("AGGREGATING RESULTS")
        
        # Find all result CSVs
        all_csvs = list(self.results_dir.glob("run*_*.csv"))
        
        if not all_csvs:
            print("[WARNING] No result CSVs found to aggregate")
            return None
        
        print(f"Found {len(all_csvs)} CSV files to aggregate")
        
        all_data = []
        for csv_file in sorted(all_csvs):
            try:
                df = pd.read_csv(csv_file)
                all_data.append(df)
                print(f"  [OK] {csv_file.name}")
            except Exception as e:
                print(f"  [X] {csv_file.name}: {e}")
        
        if not all_data:
            print("No valid CSVs to aggregate")
            return None
        
        # Combine all data
        combined = pd.concat(all_data, ignore_index=True)
        
        # Calculate metrics dynamically
        combined["precision"] = combined["tp"] / (combined["tp"] + combined["fp"])
        combined["recall"]    = combined["tp"] / (combined["tp"] + combined["fn"])
        combined["fpr"]       = combined["fp"] / (combined["fp"] + combined["tn"])
        combined["f1"]        = 2 * combined["precision"] * combined["recall"] / (combined["precision"] + combined["recall"])
        combined["scenario_name"] = combined["test_name"].apply(lambda x: x.split("_")[0] if isinstance(x, str) else "")
        combined.fillna(0, inplace=True)
        if "duration_seconds" not in combined.columns:
            combined["duration_seconds"] = 0

        # Group by test_name and calculate statistics
        print("\nCalculating averages by test...")
        grouped = combined.groupby('test_name').agg({
            'precision': ['mean', 'std'],
            'recall': ['mean', 'std'],
            'f1': ['mean', 'std'],
            'fpr': ['mean', 'std'],
            'duration_seconds': 'mean'
        }).round(4)
        
        # Flatten column names
        grouped.columns = ['_'.join(col).strip() for col in grouped.columns.values]
        grouped = grouped.rename(columns={
            'precision_mean': 'precision', 'precision_std': 'precision_std',
            'recall_mean': 'recall', 'recall_std': 'recall_std',
            'f1_mean': 'f1', 'f1_std': 'f1_std',
            'fpr_mean': 'fpr', 'fpr_std': 'fpr_std',
            'duration_seconds_mean': 'avg_duration_sec'
        })
        
        # Save aggregated results
        output_file = self.results_dir / "AGGREGATED_RESULTS_3X.csv"
        grouped.to_csv(output_file)
        print(f"\n✓ Saved aggregated results to: {output_file}")
        
        # Calculate overall metrics
        overall_f1 = combined['f1'].mean()
        overall_precision = combined['precision'].mean()
        overall_recall = combined['recall'].mean()
        
        self.print_header("FINAL RESULTS (3-Run Average)")
        print(f"Overall Metrics:")
        print(f"  • Average F1 Score: {overall_f1:.4f} (±{combined['f1'].std():.4f})")
        print(f"  • Average Precision: {overall_precision:.4f} (±{combined['precision'].std():.4f})")
        print(f"  • Average Recall: {overall_recall:.4f} (±{combined['recall'].std():.4f})")
        print(f"  • Average FPR: {combined['fpr'].mean():.4f}")
        
        print(f"\nPer-Test-Type Average F1:")
        by_scenario = combined.groupby('scenario_name')['f1'].agg(['mean', 'std'])
        for scenario, row in by_scenario.iterrows():
            print(f"  • {scenario}: {row['mean']:.4f} (±{row['std']:.4f})")
        
        # Best and worst performers
        best_test = combined.nlargest(1, 'f1').iloc[0]
        worst_test = combined.nsmallest(1, 'f1').iloc[0]
        
        print(f"\nBest Performing Test:")
        print(f"  • {best_test['test_name']}: F1={best_test['f1']:.4f}")
        print(f"\nWorst Performing Test:")
        print(f"  • {worst_test['test_name']}: F1={worst_test['f1']:.4f}")
        
        # Comparison to paper
        paper_f1 = 0.9979
        gap = (paper_f1 - overall_f1) * 100
        print(f"\nComparison to Paper Baseline:")
        print(f"  • Paper F1: {paper_f1:.4f} (GPT-4.1-Mini)")
        print(f"  • Your F1: {overall_f1:.4f}")
        print(f"  • Gap: {gap:+.2f} percentage points")
        
        return output_file

def main():
    """Main entry point"""
    runner = MasterTestRunner()
    
    # Check if in correct directory
    if not runner.artifact_dir.exists():
        print("ERROR: artifact/ directory not found")
        print("Please run this script from the Clouseau root directory")
        sys.exit(1)
        
    # Pre-flight dataset availability check
    import subprocess
    print("Running pre-flight dataset availability check...")
    flags = [config[0] for config in runner.test_configs]
    check_cmd = [sys.executable, "artifact/check_datasets.py"] + flags
    res = subprocess.run(check_cmd)
    if res.returncode != 0:
        print("\n[X] Pre-flight check failed: Some required datasets are missing.")
        print("Please download/preprocess them before starting the 3x evaluation suite.")
        sys.exit(1)
    print("[OK] All datasets verified. Starting tests.")
    
    # Run all tests 3x
    if runner.run_all_3x():
        # Aggregate results
        runner.aggregate_results()
        print("\n[OK] Full evaluation complete!")
    else:
        print("\n[X] Evaluation failed")
        sys.exit(1)

if __name__ == "__main__":
    main()
