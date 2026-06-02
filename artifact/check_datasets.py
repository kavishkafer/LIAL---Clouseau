#!/usr/bin/env python3
"""
Dataset availability checker for Clouseau scenarios.
Verifies if all 21 required scenario databases are preprocessed and available.
"""

import sys
import os
from pathlib import Path

# Scenarios configurations (flag, name, type)
EXPECTED_SCENARIOS = [
    # SI (Single Host)
    ("S1", "scenarios/S1/scenario.db", "ATLAS Single Host"),
    ("S2", "scenarios/S2/scenario.db", "ATLAS Single Host"),
    ("S3", "scenarios/S3/scenario.db", "ATLAS Single Host"),
    ("S4", "scenarios/S4/scenario.db", "ATLAS Single Host"),
    # SE (Extended)
    ("SE1", "scenarios/SE1/scenario.db", "ATLAS Extended"),
    ("SE2", "scenarios/SE2/scenario.db", "ATLAS Extended"),
    ("SE3", "scenarios/SE3/scenario.db", "ATLAS Extended"),
    ("SE4", "scenarios/SE4/scenario.db", "ATLAS Extended"),
    # SS (Keywords)
    ("SS1", "scenarios/SS1/scenario.db", "ATLAS Sensitivity"),
    ("SS2", "scenarios/SS2/scenario.db", "ATLAS Sensitivity"),
    ("SS3", "scenarios/SS3/scenario.db", "ATLAS Sensitivity"),
    ("SS4", "scenarios/SS4/scenario.db", "ATLAS Sensitivity"),
    # MI (Multi Host)
    ("m1h1", "scenarios/M1/h1/scenario.db", "ATLAS Multi Host"),
    ("m1h2", "scenarios/M1/h2/scenario.db", "ATLAS Multi Host"),
    ("m2h1", "scenarios/M2/h1/scenario.db", "ATLAS Multi Host"),
    ("m2h2", "scenarios/M2/h2/scenario.db", "ATLAS Multi Host"),
    ("m3h1", "scenarios/M3/h1/scenario.db", "ATLAS Multi Host"),
    ("m3h2", "scenarios/M3/h2/scenario.db", "ATLAS Multi Host"),
    ("m4h1", "scenarios/M4/h1/scenario.db", "ATLAS Multi Host"),
    ("m4h2", "scenarios/M4/h2/scenario.db", "ATLAS Multi Host"),
    ("m5h1", "scenarios/M5/h1/scenario.db", "ATLAS Multi Host"),
    ("m5h2", "scenarios/M5/h2/scenario.db", "ATLAS Multi Host"),
    ("m6h1", "scenarios/M6/h1/scenario.db", "ATLAS Multi Host"),
    ("m6h2", "scenarios/M6/h2/scenario.db", "ATLAS Multi Host"),
    # OPTC (Generalization)
    ("optc1", "scenarios/OPT1/scenario.db", "DARPA OpTC"),
    ("optc2", "scenarios/OPT2/scenario.db", "DARPA OpTC"),
    ("optc3", "scenarios/OPT3/scenario.db", "DARPA OpTC"),
]

def check_datasets(base_dir=None, groups=None):
    """Check existence of expected database files."""
    if base_dir is None:
        # Resolve relative to this script's directory
        base_dir = Path(__file__).parent.resolve()
    else:
        base_dir = Path(base_dir).resolve()
        
    results = []
    missing_count = 0
    available_count = 0
    
    for name, rel_path, group in EXPECTED_SCENARIOS:
        if groups is not None and group not in groups:
            continue
        db_path = base_dir / rel_path
        status = "Available [OK]" if db_path.exists() else "Missing [X]"
        if db_path.exists():
            available_count += 1
        else:
            missing_count += 1
        results.append([name, group, rel_path, status])
        
    return results, available_count, missing_count

def print_report(results, available, missing):
    """Print ASCII table or plain-text report of scenario availability."""
    headers = ["Scenario", "Dataset Group", "Database Path", "Status"]
    
    print("\n" + "="*80)
    print("  CLOUSEAU DATASET AVAILABILITY REPORT")
    print("="*80)
    
    try:
        from tabulate import tabulate
        print(tabulate(results, headers=headers, tablefmt="grid"))
    except ImportError:
        # Simple text formatting fallback
        print(f"\n{'Scenario':<10} | {'Dataset Group':<20} | {'Status':<12} | Path")
        print("-" * 80)
        for r in results:
            print(f"{r[0]:<10} | {r[1]:<20} | {r[3]:<12} | {r[2]}")
        print("-" * 80)
        
    print(f"\nSummary:")
    print(f"  - Total Scenarios: {len(results)}")
    print(f"  - Available:       {available}")
    print(f"  - Missing:         {missing}")
    
    if missing > 0:
        print("\n>>> [WARNING] One or more datasets are missing! To fix this:")
        print("  1. Verify datasets are downloaded and preprocessed on your system.")
        print("  2. If running on DGX Spark, ensure raw data is cloned and preprocessed.")
        print("  3. For missing Multi-Host or OpTC datasets, use the scripts in preprocessing/:")
        print("     cd Clouseau/artifact/preprocessing")
        print("     # For ATLAS Multi-Host scenarios:")
        print("     bash download.sh --download atlas --preprocess atlas --foreground")
        print("     # For DARPA OpTC scenarios (requires 'optc' rclone config):")
        print("     bash download.sh --download optc --preprocess optc --foreground\n")
    else:
        print("\n>>> [SUCCESS] All datasets are fully preprocessed and available! Ready to execute test suites.\n")

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Verify that all scenario datasets are preprocessed and available.")
    parser.add_argument("--silent", action="store_true", help="Do not print any report to stdout.")
    parser.add_argument('--scenarios-si', action='store_true', help='Check ATLAS Single Host scenarios')
    parser.add_argument('--scenarios-se', action='store_true', help='Check ATLAS Extended scenarios')
    parser.add_argument('--scenarios-ss', action='store_true', help='Check ATLAS Sensitivity scenarios')
    parser.add_argument('--scenarios-mi', '--scenarios-ml', action='store_true', dest='scenarios_mi', help='Check ATLAS Multi Host scenarios')
    parser.add_argument('--scenarios-optc', action='store_true', help='Check DARPA OpTC scenarios')
    args = parser.parse_args()
    
    groups = []
    if args.scenarios_si:
        groups.append("ATLAS Single Host")
    if args.scenarios_se:
        groups.append("ATLAS Extended")
    if args.scenarios_ss:
        groups.append("ATLAS Sensitivity")
    if args.scenarios_mi:
        groups.append("ATLAS Multi Host")
    if args.scenarios_optc:
        groups.append("DARPA OpTC")
        
    # If no groups are specified, check all
    if not groups:
        groups = None
        
    results, available, missing = check_datasets(groups=groups)
    
    if not args.silent:
        print_report(results, available, missing)
        
    if missing > 0:
        sys.exit(1)
    sys.exit(0)

if __name__ == "__main__":
    main()
