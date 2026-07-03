#!/usr/bin/env python3
"""
Non-Determinism Analyzer (E5)
Computes per-scenario F1 standard deviations across the three runs and
classifies tests into Stable, Variable, and Volatile.
"""

import os
import sys
import argparse
import json
import pandas as pd
import numpy as np
from pathlib import Path

def calculate_metrics(df):
    """Calculate precision, recall, and F1 from TP, FP, TN, FN columns."""
    df = df.copy()
    
    # Fill missing values
    for col in ["tp", "fp", "tn", "fn"]:
        if col not in df.columns:
            df[col] = 0
        df[col] = pd.to_numeric(df[col]).fillna(0)
        
    # Calculate precision, recall, FPR, F1
    precision = df["tp"] / (df["tp"] + df["fp"])
    recall = df["tp"] / (df["tp"] + df["fn"])
    fpr = df["fp"] / (df["fp"] + df["tn"])
    
    df["precision"] = precision.fillna(0)
    df["recall"] = recall.fillna(0)
    df["fpr"] = fpr.fillna(0)
    
    f1 = 2 * df["precision"] * df["recall"] / (df["precision"] + df["recall"])
    df["f1"] = f1.fillna(0)
    
    return df

def categorize_scenario(test_name):
    """Categorize scenario based on its test name prefix."""
    if test_name.startswith("se"):
        return "ATLAS Extended"
    elif test_name.startswith("ss"):
        return "ATLAS Keywords"
    elif test_name.startswith("s"):
        return "ATLAS Single Host"
    elif test_name.startswith("m"):
        return "ATLAS Multi-Host"
    elif test_name.startswith("optc"):
        return "DARPA OpTC"
    else:
        return "Unknown"

def main():
    parser = argparse.ArgumentParser(description="Analyze non-determinism across 3 evaluation runs.")
    parser.add_argument("--model", type=str, default="gemma4_26b_bf16",
                        help="Model directory name under artifact/results (default: gemma4_26b_bf16)")
    parser.add_argument("--results-dir", type=str, default="results",
                        help="Base directory for results relative to artifact/ (default: results)")
    parser.add_argument("--stable-threshold", type=float, default=0.0001,
                        help="Standard deviation threshold for Stable classification (default: 0.0001)")
    parser.add_argument("--volatile-threshold", type=float, default=0.05,
                        help="Standard deviation threshold for Volatile classification (default: 0.05)")
    args = parser.parse_args()

    # Determine paths
    artifact_dir = Path(__file__).resolve().parent
    model_dir = (artifact_dir / args.results_dir / args.model).resolve()
    
    if not model_dir.exists():
        print(f"ERROR: Model results directory not found at {model_dir}")
        sys.exit(1)
        
    print(f"--> Analyzing non-determinism for model: {args.model}")
    print(f"--> Reading from: {model_dir}")
    
    # We expect run1_*.csv, run2_*.csv, run3_*.csv
    # Config names corresponding to the files
    configs = ["single_host", "extended", "keywords", "multihost", "optc"]
    
    all_runs_data = []
    
    # Read runs 1, 2, 3
    for run_num in [1, 2, 3]:
        for config in configs:
            csv_path = model_dir / f"run{run_num}_{config}.csv"
            if not csv_path.exists():
                print(f"Warning: {csv_path.name} not found, skipping.")
                continue
                
            try:
                df = pd.read_csv(csv_path)
                if df.empty:
                    continue
                df = calculate_metrics(df)
                df["run"] = run_num
                df["suite"] = config
                all_runs_data.append(df[["test_name", "run", "suite", "precision", "recall", "fpr", "f1", "duration_seconds"]])
            except Exception as e:
                print(f"Error reading {csv_path.name}: {e}")
                
    if not all_runs_data:
        print("ERROR: No run data could be loaded. Ensure the CSV files are present.")
        sys.exit(1)
        
    # Combine everything
    combined_df = pd.concat(all_runs_data, ignore_index=True)
    
    # Group by test_name and calculate std dev and mean across runs
    stats = combined_df.groupby("test_name").agg(
        f1_mean=("f1", "mean"),
        f1_std=("f1", "std"),
        f1_min=("f1", "min"),
        f1_max=("f1", "max"),
        f1_run1=("f1", lambda x: x[combined_df.loc[x.index, "run"] == 1].values[0] if len(x[combined_df.loc[x.index, "run"] == 1]) > 0 else np.nan),
        f1_run2=("f1", lambda x: x[combined_df.loc[x.index, "run"] == 2].values[0] if len(x[combined_df.loc[x.index, "run"] == 2]) > 0 else np.nan),
        f1_run3=("f1", lambda x: x[combined_df.loc[x.index, "run"] == 3].values[0] if len(x[combined_df.loc[x.index, "run"] == 3]) > 0 else np.nan),
        avg_duration=("duration_seconds", "mean")
    ).reset_index()
    
    # Fill missing std devs (occurs if less than 3 runs exist for a test)
    stats["f1_std"] = stats["f1_std"].fillna(0.0)
    
    # Classify stability
    def classify_stability(row):
        std = row["f1_std"]
        if std <= args.stable_threshold:
            return "Stable"
        elif std <= args.volatile_threshold:
            return "Variable"
        else:
            return "Volatile"
            
    stats["stability"] = stats.apply(classify_stability, axis=1)
    stats["suite"] = stats["test_name"].apply(categorize_scenario)
    
    # Sort by standard deviation descending
    stats = stats.sort_values(by="f1_std", ascending=False).reset_index(drop=True)
    
    # Count stability statuses
    counts = stats["stability"].value_counts().to_dict()
    counts.setdefault("Stable", 0)
    counts.setdefault("Variable", 0)
    counts.setdefault("Volatile", 0)
    
    total_tests = len(stats)
    
    # Output markdown report and JSON
    markdown_path = model_dir / "non_determinism_report.md"
    json_path = model_dir / "non_determinism_report.json"
    csv_path = model_dir / "non_determinism_report.csv"
    
    # Save CSV
    stats.to_csv(csv_path, index=False)
    
    # Construct JSON summary
    summary_json = {
        "model": args.model,
        "total_scenarios": total_tests,
        "classification_thresholds": {
            "stable_max_std": args.stable_threshold,
            "volatile_min_std": args.volatile_threshold
        },
        "counts": counts,
        "percentages": {
            k: round((v / total_tests) * 100, 2) for k, v in counts.items()
        },
        "volatile_scenarios": stats[stats["stability"] == "Volatile"][["test_name", "suite", "f1_run1", "f1_run2", "f1_run3", "f1_mean", "f1_std"]].to_dict("records"),
        "variable_scenarios": stats[stats["stability"] == "Variable"][["test_name", "suite", "f1_run1", "f1_run2", "f1_run3", "f1_mean", "f1_std"]].to_dict("records"),
        "stable_scenarios": stats[stats["stability"] == "Stable"][["test_name", "suite", "f1_mean"]].to_dict("records")
    }
    
    with open(json_path, "w") as f:
        json.dump(summary_json, f, indent=2)
        
    # Write Markdown Report
    with open(markdown_path, "w") as f:
        f.write(f"# Non-Determinism Analysis Report: {args.model}\n\n")
        f.write(f"This report evaluates the run-to-run variance and reproducibility of the Clouseau system on local LLM deployment with **{args.model}** across 3 full evaluation runs at temperature = 0.\n\n")
        
        f.write("## 1. Summary Statistics\n\n")
        f.write(f"- **Total Scenarios Analyzed**: {total_tests} / 63\n")
        f.write(f"- **Stable** ($\sigma_{{F1}} \\le {args.stable_threshold}$): {counts['Stable']} ({summary_json['percentages']['Stable']}%)\n")
        f.write(f"- **Variable** (${args.stable_threshold} < \\sigma_{{F1}} \\le {args.volatile_threshold}$): {counts['Variable']} ({summary_json['percentages']['Variable']}%)\n")
        f.write(f"- **Volatile** ($\\sigma_{{F1}} > {args.volatile_threshold}$): {counts['Volatile']} ({summary_json['percentages']['Volatile']}%)\n\n")
        
        # Breakdown by suite
        f.write("### Breakdown by Scenario Suite\n\n")
        f.write("| Suite | Total | Stable | Variable | Volatile | % Stable |\n")
        f.write("|---|---|---|---|---|---|\n")
        
        suite_groups = stats.groupby("suite")
        for suite, group in suite_groups:
            s_total = len(group)
            s_counts = group["stability"].value_counts().to_dict()
            s_stable = s_counts.get("Stable", 0)
            s_var = s_counts.get("Variable", 0)
            s_vol = s_counts.get("Volatile", 0)
            pct_stable = (s_stable / s_total) * 100
            f.write(f"| {suite} | {s_total} | {s_stable} | {s_var} | {s_vol} | {pct_stable:.1f}% |\n")
        f.write("\n")
        
        # Volatile Scenarios Table
        f.write("## 2. Volatile Scenarios (High Variance)\n\n")
        f.write("These scenarios show significant variance across runs ($\sigma > 0.05$), indicating high sensitivity to non-determinism during inference:\n\n")
        if counts["Volatile"] > 0:
            f.write("| Scenario | Suite | Run 1 F1 | Run 2 F1 | Run 3 F1 | Mean F1 | Std Dev |\n")
            f.write("|---|---|---|---|---|---|---|\n")
            for _, row in stats[stats["stability"] == "Volatile"].iterrows():
                f.write(f"| `{row['test_name']}` | {row['suite']} | {row['f1_run1']:.4f} | {row['f1_run2']:.4f} | {row['f1_run3']:.4f} | **{row['f1_mean']:.4f}** | `{row['f1_std']:.4f}` |\n")
        else:
            f.write("*No volatile scenarios detected.*\n")
        f.write("\n")
        
        # Variable Scenarios Table
        f.write("## 3. Variable Scenarios (Low-to-Medium Variance)\n\n")
        f.write(f"These scenarios show minor fluctuations across runs ($0 < \\sigma \\le {args.volatile_threshold}$):\n\n")
        if counts["Variable"] > 0:
            f.write("| Scenario | Suite | Run 1 F1 | Run 2 F1 | Run 3 F1 | Mean F1 | Std Dev |\n")
            f.write("|---|---|---|---|---|---|---|\n")
            for _, row in stats[stats["stability"] == "Variable"].iterrows():
                f.write(f"| `{row['test_name']}` | {row['suite']} | {row['f1_run1']:.4f} | {row['f1_run2']:.4f} | {row['f1_run3']:.4f} | **{row['f1_mean']:.4f}** | `{row['f1_std']:.4f}` |\n")
        else:
            f.write("*No variable scenarios detected.*\n")
        f.write("\n")
        
        # Top 10 Stable Scenarios Table
        f.write("## 4. Top 10 Stable Scenarios\n\n")
        f.write("These represent scenarios with perfect reproducibility ($\sigma \\approx 0.0$):\n\n")
        stable_df = stats[stats["stability"] == "Stable"].head(10)
        if not stable_df.empty:
            f.write("| Scenario | Suite | Mean F1 | Avg Duration |\n")
            f.write("|---|---|---|---|\n")
            for _, row in stable_df.iterrows():
                f.write(f"| `{row['test_name']}` | {row['suite']} | **{row['f1_mean']:.4f}** | {row['avg_duration']:.1f}s |\n")
        else:
            f.write("*No stable scenarios detected.*\n")
            
    print(f"✓ Saved CSV report to: {csv_path}")
    print(f"✓ Saved JSON report to: {json_path}")
    print(f"✓ Saved Markdown report to: {markdown_path}")
    
    # Also print summary to terminal
    print("\n" + "="*50)
    print(f"Stability Classification Summary: {args.model}")
    print("="*50)
    print(f"Stable (std <= {args.stable_threshold}): {counts['Stable']} ({summary_json['percentages']['Stable']}%)")
    print(f"Variable (std <= {args.volatile_threshold}): {counts['Variable']} ({summary_json['percentages']['Variable']}%)")
    print(f"Volatile (std > {args.volatile_threshold}): {counts['Volatile']} ({summary_json['percentages']['Volatile']}%)")
    print("="*50)
    
if __name__ == "__main__":
    main()
