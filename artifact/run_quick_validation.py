#!/usr/bin/env python3
"""
Quick Validation Runner: Run 6 targeted high-variance tests (1x) to verify
Batch 1 optimizations (P1+P4+P5) before a full 3x evaluation.

Selected tests cover:
  - s1_IP      (Single-host, high std-dev: 0.57 — binary pass/fail)
  - s2_file    (Single-host, high std-dev: 0.56 — binary pass/fail)
  - se2_domain (Extended, high std-dev: 0.56 — only 2/3 passes in baseline)
  - m3h1_domain (Multi-host, high std-dev: 0.56 — tests pivot handoffs)
  - ss1_file   (Keywords, high std-dev: 0.57 — most sensitive test)
  - optc1_C3   (OpTC, worst category avg 66% — tests cell truncation impact)

Usage:
  cd artifact && ../venv/bin/python3 run_quick_validation.py

Output:
  artifact/results_quick_validation/quick_validation.csv
  Comparison table vs 32k baseline printed to stdout
"""

import os
import sys
import time
import pandas as pd
from datetime import datetime
from pathlib import Path

# ── baseline F1 for these 6 tests from the 32k 3x run (AGGREGATED_RESULTS_3X) ──
BASELINE_F1 = {
    "s1_IP":       0.9998,   # 32k avg F1 across 3 runs (already high — regression check)
    "s2_file":     0.3494,   # binary fail pattern (std dev 0.56) — expect improvement
    "se2_domain":  0.6742,   # borderline (std dev 0.56) — 2/3 passes in baseline
    "m3h1_domain": 0.3588,   # binary fail (std dev 0.56) — multi-host pivot test
    "ss1_file":    0.3454,   # binary fail (std dev 0.57) — most sensitive test
    "optc1_C3":    0.8240,   # OpTC — tests cell truncation impact directly
}

TARGET_TESTS = {
    "s1_IP", "s2_file", "se2_domain", "m3h1_domain", "ss1_file", "optc1_C3"
}

APP_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = Path(APP_DIR).parent / "artifact" / "results_quick_validation"
OUTPUT_DIR.mkdir(exist_ok=True)
OUTPUT_CSV = str(OUTPUT_DIR / "quick_validation.csv")


def main():
    # ── bootstrap the same LLM + configs as app.py ──────────────────────────
    # We import app.py internals rather than shelling out so we get Python-level
    # error reporting if something goes wrong.
    sys.path.insert(0, APP_DIR)
    from llm_factory import create_llm_from_env
    from chief_inspector import investigate_atlas, investigate_optc
    from evaluation import evaluate_report
    import constants
    import prompts
    import app as app_module

    # Resolve LLM
    model = os.environ.get('LLM_MODEL', None)
    api_key = os.environ.get('API_KEY', None)
    base_url = os.environ.get('BASE_URL', None)
    try:
        llm, provider = create_llm_from_env(model=model, api_key=api_key, base_url=base_url)
    except Exception as exc:
        print("LLM configuration error:", str(exc))
        sys.exit(1)

    configs = {
        "max_investigations": constants.DEFAULT_INVESTIGATIONS,
        "max_questions":      constants.DEFAULT_QUESTIONS,
        "max_queries":        constants.DEFAULT_QUERIES,
        "max_tokens":         constants.DEFAULT_MAX_TOKENS,
    }

    # ── build the full scenario × POI list the same way app.py does ──────────
    all_scenarios = [
        # (scenario_list, is_darpa)
        (app_module.si_scn,   False),
        (app_module.ml_scn,   False),
        (app_module.se_scn,   False),
        (app_module.ss_scn,   False),
        (app_module.optc_scn, True),
    ]

    rows = []
    skipped = 0
    print(f"\n{'='*70}")
    print(f"  QUICK VALIDATION — Batch 1 (P1+P4+P5)  |  {datetime.now():%Y-%m-%d %H:%M}")
    print(f"  Tests: {', '.join(sorted(TARGET_TESTS))}")
    print(f"{'='*70}\n")

    for scn_list, is_darpa in all_scenarios:
        for scn in scn_list:
            scenario_path = os.path.normpath(os.path.join(APP_DIR, scn["path"]))
            base_cfg = configs.copy()
            base_cfg["data_path"] = scenario_path
            base_cfg["db_name"]   = os.path.join(scenario_path, "scenario.db")
            base_cfg["is_darpa"]  = is_darpa

            for clue, poi_type in scn["poi"]:
                test_name = f"{scn['name']}_{poi_type}"
                if test_name not in TARGET_TESTS:
                    skipped += 1
                    continue

                poi_cfg = base_cfg.copy()
                poi_cfg["clue"]      = clue
                poi_cfg["test_name"] = test_name
                poi_cfg["environment"] = (
                    prompts.opt_env_context if is_darpa else prompts.atlas_env_context
                )

                print(f"[{datetime.now():%H:%M:%S}] Running: {test_name}")
                t0 = time.time()
                try:
                    if is_darpa:
                        report = investigate_optc(llm=llm, configs=poi_cfg)
                    else:
                        report = investigate_atlas(llm=llm, configs=poi_cfg)

                    result = evaluate_report(poi_cfg, report)
                    duration = time.time() - t0

                    tp, fp, fn, tn = result.tp, result.fp, result.fn, result.tn
                    prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
                    rec  = tp / (tp + fn) if (tp + fn) > 0 else 0.0
                    f1   = (2 * prec * rec / (prec + rec)) if (prec + rec) > 0 else 0.0

                    baseline = BASELINE_F1.get(test_name, None)
                    delta = (f1 - baseline) if baseline is not None else None
                    delta_str = f"{delta:+.4f}" if delta is not None else "N/A"

                    print(f"  ✓ F1={f1:.4f}  (baseline={baseline:.4f}, Δ={delta_str})  [{duration/60:.1f} min]")

                    rows.append({
                        "test_name":       test_name,
                        "f1":              round(f1, 4),
                        "precision":       round(prec, 4),
                        "recall":          round(rec, 4),
                        "tp":              tp, "fp": fp, "fn": fn, "tn": tn,
                        "baseline_f1":     baseline,
                        "delta_f1":        round(delta, 4) if delta is not None else None,
                        "duration_sec":    round(duration, 1),
                        "input_tokens":    result.input_tokens,
                        "output_tokens":   result.output_tokens,
                    })

                except Exception as e:
                    duration = time.time() - t0
                    print(f"  ✗ ERROR: {e}  [{duration/60:.1f} min]")
                    rows.append({
                        "test_name": test_name, "f1": 0, "error": str(e),
                        "duration_sec": round(duration, 1),
                    })

    # ── Save results ─────────────────────────────────────────────────────────
    if rows:
        df = pd.DataFrame(rows)
        df.to_csv(OUTPUT_CSV, index=False)
        print(f"\n✓ Results saved to: {OUTPUT_CSV}")

        # Summary table
        print(f"\n{'='*70}")
        print(f"  QUICK VALIDATION SUMMARY")
        print(f"{'='*70}")
        print(f"{'Test':<18} {'F1':>8} {'Baseline':>10} {'Δ F1':>10} {'Tokens In':>12}")
        print(f"{'-'*18} {'-'*8} {'-'*10} {'-'*10} {'-'*12}")
        for _, row in df.iterrows():
            delta_str = f"{row.get('delta_f1', 0):+.4f}" if pd.notna(row.get("delta_f1")) else "N/A"
            tok_str   = str(int(row.get("input_tokens", 0))) if pd.notna(row.get("input_tokens")) else "N/A"
            print(f"{row['test_name']:<18} {row.get('f1', 0):>8.4f} "
                  f"{row.get('baseline_f1', 0):>10.4f} {delta_str:>10} {tok_str:>12}")

        improved = df[df.get("delta_f1", pd.Series([], dtype=float)) > 0].shape[0] if "delta_f1" in df else 0
        regressed = df[df.get("delta_f1", pd.Series([], dtype=float)) < -0.05].shape[0] if "delta_f1" in df else 0
        avg_delta = df["delta_f1"].mean() if "delta_f1" in df else 0

        print(f"\n  Avg F1 delta vs 32k baseline: {avg_delta:+.4f}")
        print(f"  Tests improved: {improved}  |  Tests regressed (>5pp): {regressed}")

        if regressed == 0:
            print("\n  ✅ No regressions detected. Safe to proceed to full 3x run.")
        else:
            print(f"\n  ⚠️  {regressed} test(s) regressed significantly. Review before full 3x run.")
    else:
        print(f"\n  No tests ran (skipped {skipped} — check TARGET_TESTS names match app.py POI labels).")

if __name__ == "__main__":
    main()
