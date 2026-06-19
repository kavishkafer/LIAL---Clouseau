#!/usr/bin/env python3
import os
import sys
import re
import sqlite3
import pandas as pd
from pathlib import Path

# Add artifact to sys.path so we can import evaluation
sys.path.append(str(Path(__file__).resolve().parent))
from evaluation import EvaluationResults

def parse_log(log_path):
    with open(log_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Find runs
    run_blocks = re.split(r'={80}\n\s*RUN (\d) of \d\n={80}', content)
    runs = {}
    if len(run_blocks) > 1:
        for i in range(1, len(run_blocks), 2):
            run_num = int(run_blocks[i])
            run_content = run_blocks[i+1]
            runs[run_num] = run_content
    else:
        # Fallback to entire log as Run 1
        runs[1] = content

    parsed_runs_data = {}
    for run_num, run_content in runs.items():
        # Find start of tests in this run
        test_starts = list(re.finditer(r'▶ Starting (optc\d_[A-Z0-9]+)', run_content))
        test_reports = {}
        for idx, start_match in enumerate(test_starts):
            test_name = start_match.group(1)
            start_pos = start_match.start()
            end_pos = test_starts[idx+1].start() if idx+1 < len(test_starts) else len(run_content)
            test_block = run_content[start_pos:end_pos]

            # Look for JSON block in this test's output
            json_match = re.search(r'```json\n(.*?)\n```', test_block, re.DOTALL)
            if json_match:
                json_report = f"```json\n{json_match.group(1)}\n```"
                test_reports[test_name] = json_report
            else:
                # If exception or no JSON, it's empty string
                test_reports[test_name] = ""
        parsed_runs_data[run_num] = test_reports

    return parsed_runs_data

def repair_run_csv(run_num, test_reports, results_dir):
    csv_file = results_dir / f"run{run_num}_optc.csv"
    if not csv_file.exists():
        print(f"CSV for run {run_num} does not exist: {csv_file}")
        return

    print(f"Repairing {csv_file.name}...")
    df = pd.read_csv(csv_file)

    for test_name, json_report in test_reports.items():
        # Match scenario name (e.g. optc1, optc2, optc3)
        scenario_num = test_name.split('_')[0]  # optc1
        opt_dir = scenario_num.upper().replace('OPTC', 'OPT')  # OPT1
        
        configs = {
            'test_name': test_name,
            'data_path': str(Path(__file__).resolve().parent / "scenarios" / opt_dir),
            'is_darpa': True
        }

        print(f"  Evaluating {test_name} with db in {configs['data_path']}...")
        try:
            er = EvaluationResults(configs, json_report)
            
            # Find the row in DataFrame
            idx = df[df['test_name'] == test_name].index
            if len(idx) > 0:
                idx = idx[0]
                df.at[idx, 'P'] = er.P
                df.at[idx, 'N'] = er.N
                df.at[idx, 'tp'] = er.tp
                df.at[idx, 'tn'] = er.tn
                df.at[idx, 'fp'] = er.fp
                df.at[idx, 'fn'] = er.fn
                print(f"    Updated: P={er.P}, N={er.N}, tp={er.tp}, tn={er.tn}, fp={er.fp}, fn={er.fn}")
            else:
                print(f"    [WARNING] Test {test_name} not found in CSV row!")
        except Exception as e:
            print(f"    [ERROR] Failed to evaluate {test_name}: {e}")

    df.to_csv(csv_file, index=False)
    print(f"✓ Saved repaired CSV: {csv_file}")

def main():
    log_path = Path("/home/dgx-spark-01/.gemini/antigravity-ide/brain/4fc459d6-2aff-4a46-8747-b669f705d836/.system_generated/tasks/task-1179.log")
    results_dir = Path(__file__).resolve().parent / "results_3x_runs"

    if not log_path.exists():
        print(f"Log file not found: {log_path}")
        sys.exit(1)

    print("Parsing log file...")
    parsed_data = parse_log(log_path)

    for run_num, test_reports in parsed_data.items():
        print(f"\n--- Run {run_num} ({len(test_reports)} tests) ---")
        repair_run_csv(run_num, test_reports, results_dir)

if __name__ == '__main__':
    main()
