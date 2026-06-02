#!/usr/bin/env python3
"""
Quick full evaluation: Run all 63 tests once
Faster version for validation before committing to 3x runs
Usage: python run_all_tests_1x.py
"""

import subprocess
import sys
import os
import time
from pathlib import Path
from datetime import datetime

class FullTestRunner:
    """Run all 63 Clouseau tests once"""
    
    def __init__(self):
        self.artifact_dir = Path("artifact")
        self.results_dir = Path("artifact/results_1x_run").resolve()
        self.results_dir.mkdir(exist_ok=True)
        self.run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Test configurations: (flag, output_name, display_name, test_count)
        self.test_configs = [
            ("--scenarios-si", "single_host", "S1-S4 (Single-host)", 12),
            ("--scenarios-se", "extended", "SE1-SE4 (Extended semantic gap)", 12),
            ("--scenarios-ss", "keywords", "SS1-SS4 (Keyword sensitivity)", 12),
            ("--scenarios-mi", "multi_host", "M1-M6 (Multi-host lateral movement)", 18),
            ("--scenarios-optc", "optc", "OpTC1-3 (DARPA generalization)", 9),
        ]
        
        self.total_tests = sum(config[3] for config in self.test_configs)
        self.start_time = None
        
    def print_header(self, text):
        """Print formatted header"""
        print("\n" + "="*80)
        print(f"  {text}")
        print("="*80 + "\n")
    
    def print_section(self, text):
        """Print formatted section"""
        print(f"\n>>> {text}")
    
    def run_test_config(self, scenario_flag, config_name, display_name, test_count):
        """Run a single test configuration"""
        output_csv = self.results_dir / f"{self.run_id}_{config_name}.csv"
        
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
        
        self.print_section(f"Testing {display_name} ({test_count} tests)")
        print(f"Command: {' '.join(cmd)}")
        print(f"Output: {output_csv.name}")
        
        try:
            start = time.time()
            # Ensure LLM env vars are passed to subprocess with dynamic default model resolution
            env = os.environ.copy()
            base_url = env.get('BASE_URL', 'http://172.31.0.94:8000/v1')
            env.setdefault('BASE_URL', base_url)
            env.setdefault('API_KEY', 'local')

            if 'LLM_MODEL' not in env:
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
                    print(f"--> Dynamically resolved LLM_MODEL from vLLM endpoint: {resolved_model}")
                else:
                    env['LLM_MODEL'] = 'gemma4'
                    print("--> Failed to contact vLLM or list models, defaulting LLM_MODEL to 'gemma4'")

            result = subprocess.run(
                cmd,
                cwd=self.artifact_dir,
                timeout=259200,  # 72-hour timeout per test type (3-day window)
                capture_output=False,
                env=env
            )
            duration = time.time() - start
            
            if result.returncode == 0:
                print(f"✓ {display_name} completed in {duration/60:.1f} minutes")
                return True
            else:
                print(f"✗ {display_name} failed with return code {result.returncode}")
                return False
                
        except subprocess.TimeoutExpired:
            print(f"✗ {display_name} timed out after 72 hours")
            return False
        except Exception as e:
            print(f"✗ {display_name} error: {e}")
            return False
    
    def run_full_suite(self):
        """Execute all tests once"""
        self.start_time = time.time()
        
        self.print_header("CLOUSEAU FULL EVALUATION: 63 Tests (1 Run)")
        
        print(f"Test Breakdown:")
        for _, _, display_name, count in self.test_configs:
            print(f"  • {display_name}: {count} tests")
        
        print(f"\nTotal: {self.total_tests} unique tests")
        print(f"Estimated time: ~24-72 hours at 35 tok/sec (Gemma 4 on DGX Spark)")
        print(f"Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Run ID: {self.run_id}")
        
        if "--no-prompt" not in sys.argv:
            input("\nPress ENTER to start testing (or Ctrl+C to cancel)...")
        
        successful = 0
        failed = 0
        
        for scenario_flag, config_name, display_name, test_count in self.test_configs:
            if self.run_test_config(scenario_flag, config_name, display_name, test_count):
                successful += 1
            else:
                failed += 1
        
        total_duration = (time.time() - self.start_time) / 3600
        
        self.print_header("EXECUTION SUMMARY")
        print(f"Test Results:")
        print(f"  • Successful: {successful}/5")
        print(f"  • Failed: {failed}/5")
        print(f"  • Total duration: {total_duration:.1f} hours")
        print(f"\nResults saved to: {self.results_dir}/")
        print(f"Run ID for reference: {self.run_id}")
        
        print(f"\nNext Steps:")
        print(f"1. Review results: View the output CSV files in {self.results_dir}/ or use average.py")
        print(f"2. View details: ls -la {self.results_dir}/")
        if successful == 5:
            print(f"3. Ready for 3x runs? Run: python run_all_tests_3x.py")
        
        return successful == 5

def main():
    """Main entry point"""
    runner = FullTestRunner()
    
    # Check if in correct directory
    if not runner.artifact_dir.exists():
        print("ERROR: artifact/ directory not found")
        print("Please run this script from the Clouseau root directory")
        sys.exit(1)
        
    # Pre-flight dataset availability check
    import subprocess
    print("Running pre-flight dataset availability check...")
    check_cmd = [sys.executable, "artifact/check_datasets.py"]
    res = subprocess.run(check_cmd)
    if res.returncode != 0:
        print("\n[X] Pre-flight check failed: Some required datasets are missing.")
        print("Please download/preprocess them before starting the evaluation suite.")
        sys.exit(1)
    print("[OK] All datasets verified. Starting tests.")
    
    try:
        if runner.run_full_suite():
            print("\n[OK] Full evaluation complete successfully!")
        else:
            print("\n[WARNING] Some tests failed - check results above")
    except KeyboardInterrupt:
        print("\n\n[WARNING] Testing interrupted by user")
        sys.exit(1)

if __name__ == "__main__":
    main()
