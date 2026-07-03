import sys
import os
import subprocess
import time
from pathlib import Path

def run_cmd(cmd, env):
    print(f"Running: {' '.join(cmd)}", flush=True)
    res = subprocess.run(cmd, env=env)
    return res.returncode == 0

def main():
    ablation = os.environ.get("ABLATION")
    if not ablation:
        print("Please set ABLATION env var (A, B, C, or D)", flush=True)
        sys.exit(1)
        
    env = os.environ.copy()
    env.setdefault("BASE_URL", "http://127.0.0.1:8000/v1")
    env.setdefault("LLM_MODEL", "gemma4")
    env.setdefault("API_KEY", "local")
    env.setdefault("no_proxy", "*")
    
    # Configure toggles based on ablation
    if ablation == "A":
        env["DISABLE_T5"] = "1"
        scenarios = ["--scenarios-si"]
        file_suffix = "ablation_a"
    elif ablation == "B":
        env["DISABLE_T6"] = "1"
        scenarios = ["--scenarios-optc"]
        file_suffix = "ablation_b"
    elif ablation == "C":
        env["DISABLE_T7"] = "1"
        scenarios = ["--scenarios-si"]
        file_suffix = "ablation_c"
    elif ablation == "D":
        scenarios = ["--scenarios-si", "--scenarios-optc"]
        file_suffix = "ablation_d"
    else:
        print(f"Unknown ablation type: {ablation}", flush=True)
        sys.exit(1)

    print(f"=== Starting Ablation-{ablation} 3x evaluation ===", flush=True)
    for run in range(1, 4):
        csv_file = f"results/gemma4_26b_bf16/{file_suffix}_run{run}.csv"
        print(f"\n--- Run {run}/3 for Ablation-{ablation} (Output: {csv_file}) ---", flush=True)
        cmd = [
            sys.executable,
            "app.py",
            *scenarios,
            "--csv-file", csv_file,
            "--no-warn"
        ]
        success = run_cmd(cmd, env=env)
        if not success:
            print(f"ERROR: Run {run} failed!", flush=True)
            sys.exit(1)
            
    print(f"=== Ablation-{ablation} completed successfully! ===", flush=True)

if __name__ == "__main__":
    main()
