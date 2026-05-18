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
        self.results_dir = Path("artifact/results_3x_runs")
        self.results_dir.mkdir(exist_ok=True)
        
        # Test configurations
        self.test_configs = [
            ("--scenarios-si", "single_host", "S1-S4 (Single-host)"),
            ("--scenarios-se", "extended", "SE1-SE4 (Extended semantic gap)"),
            ("--scenarios-ss", "keywords", "SS1-SS4 (Keyword sensitivity)"),
            ("--scenarios-mi", "multi_host", "M1-M6 (Multi-host lateral movement)"),
            ("--scenarios-optc", "optc", "OpTC1-3 (DARPA generalization)"),
        ]
        
        self.total_tests = 63  # 21 scenarios × 3 POIs
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
    
    def run_test_config(self, scenario_flag, config_name, display_name, run_num):
        """Run a single test configuration"""
        output_csv = self.results_dir / f"run{run_num}_{config_name}.csv"
        
        cmd = [
            sys.executable,
            "app.py",
            scenario_flag,
            "--csv-file", str(output_csv),
            "--no-warn"
        ]
        
        self.print_section(f"[Run {run_num}/3] Testing {display_name}")
        print(f"Command: {' '.join(cmd)}")
        print(f"Output: {output_csv}")
        
        try:
            start = time.time()
            result = subprocess.run(
                cmd,
                cwd=self.artifact_dir,
                timeout=14400,  # 4 hour timeout per test type
                capture_output=False
            )
            duration = time.time() - start
            
            if result.returncode == 0:
                print(f"✓ {display_name} completed in {duration/60:.1f} minutes")
                return True
            else:
                print(f"✗ {display_name} failed with return code {result.returncode}")
                return False
                
        except subprocess.TimeoutExpired:
            print(f"✗ {display_name} timed out after 4 hours")
            return False
        except Exception as e:
            print(f"✗ {display_name} error: {e}")
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
            print("⚠ No result CSVs found to aggregate")
            return None
        
        print(f"Found {len(all_csvs)} CSV files to aggregate")
        
        all_data = []
        for csv_file in sorted(all_csvs):
            try:
                df = pd.read_csv(csv_file)
                all_data.append(df)
                print(f"  ✓ {csv_file.name}")
            except Exception as e:
                print(f"  ✗ {csv_file.name}: {e}")
        
        if not all_data:
            print("No valid CSVs to aggregate")
            return None
        
        # Combine all data
        combined = pd.concat(all_data, ignore_index=True)
        
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
    
    # Run all tests 3x
    if runner.run_all_3x():
        # Aggregate results
        runner.aggregate_results()
        print("\n✓ Full evaluation complete!")
    else:
        print("\n✗ Evaluation failed")
        sys.exit(1)

if __name__ == "__main__":
    main()
