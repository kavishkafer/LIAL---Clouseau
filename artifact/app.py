from langchain_openai import ChatOpenAI
from chief_inspector import investigate_atlas, investigate_optc
from ablation_agent import ablation_atlas, ablation_optc
from evaluation import evaluate_report
from llm_factory import create_llm_from_env, LLMConfigError
from datetime import datetime
from typing import List, Dict
import concurrent.futures
import pandas as pd
import constants
import prompts
import argparse
import time
import os


APP_DIR = os.path.dirname(os.path.abspath(__file__))

si_scn = [
    {'name': 's1', 'path': 'scenarios/S1/', 'poi': [(prompts.atlas_init_ip, 'IP'), (prompts.atlas_init_domain, 'domain'), (prompts.atlas_init_file, 'file')]},
    {'name': 's2', 'path': 'scenarios/S2/', 'poi': [(prompts.atlas_init_ip, 'IP'), (prompts.atlas_init_domain, 'domain'), (prompts.atlas_init_file, 'file')]},
    {'name': 's3', 'path': 'scenarios/S3/', 'poi': [(prompts.atlas_init_ip, 'IP'), (prompts.atlas_init_domain, 'domain'), (prompts.atlas_init_file, 'file')]},
    {'name': 's4', 'path': 'scenarios/S4/', 'poi': [(prompts.atlas_init_ip, 'IP'), (prompts.atlas_init_domain, 'domain'), (prompts.atlas_init_file_py, 'file')]}
]

ml_scn = [
    {'name': 'm1h1', 'path': 'scenarios/M1/h1/', 'poi': [(prompts.atlas_init_ip, 'IP'), (prompts.atlas_init_domain, 'domain'), (prompts.atlas_init_file, 'file')]},
    {'name': 'm1h2', 'path': 'scenarios/M1/h2/', 'poi': [(prompts.atlas_init_ip, 'IP'), (prompts.atlas_init_domain, 'domain'), (prompts.atlas_init_file, 'file')]},
    {'name': 'm2h1', 'path': 'scenarios/M2/h1/', 'poi': [(prompts.atlas_init_ip, 'IP'), (prompts.atlas_init_domain, 'domain'), (prompts.atlas_init_file_py, 'file')]},
    {'name': 'm2h2', 'path': 'scenarios/M2/h2/', 'poi': [(prompts.atlas_init_ip, 'IP'), (prompts.atlas_init_domain, 'domain'), (prompts.atlas_init_file_py, 'file')]},
    {'name': 'm3h1', 'path': 'scenarios/M3/h1/', 'poi': [(prompts.atlas_init_ip, 'IP'), (prompts.atlas_init_domain, 'domain'), (prompts.atlas_init_file_py, 'file')]},
    {'name': 'm3h2', 'path': 'scenarios/M3/h2/', 'poi': [(prompts.atlas_init_ip, 'IP'), (prompts.atlas_init_domain, 'domain'), (prompts.atlas_init_file_py, 'file')]},
    {'name': 'm4h1', 'path': 'scenarios/M4/h1/', 'poi': [(prompts.atlas_init_ip, 'IP'), (prompts.atlas_init_domain, 'domain'), (prompts.atlas_init_file, 'file')]},
    {'name': 'm4h2', 'path': 'scenarios/M4/h2/', 'poi': [(prompts.atlas_init_ip, 'IP'), (prompts.atlas_init_domain, 'domain'), (prompts.atlas_init_file, 'file')]},
    {'name': 'm5h1', 'path': 'scenarios/M5/h1/', 'poi': [(prompts.atlas_init_ip, 'IP'), (prompts.atlas_init_domain, 'domain'), (prompts.atlas_init_file_py, 'file')]},
    {'name': 'm5h2', 'path': 'scenarios/M5/h2/', 'poi': [(prompts.atlas_init_ip, 'IP'), (prompts.atlas_init_domain, 'domain'), (prompts.atlas_init_file_py, 'file')]},
    {'name': 'm6h1', 'path': 'scenarios/M6/h1/', 'poi': [(prompts.atlas_init_ip, 'IP'), (prompts.atlas_init_domain, 'domain'), (prompts.atlas_init_file, 'file')]},
    {'name': 'm6h2', 'path': 'scenarios/M6/h2/', 'poi': [(prompts.atlas_init_ip, 'IP'), (prompts.atlas_init_domain, 'domain'), (prompts.atlas_init_file, 'file')]}
]

se_scn = [
    {'name': 'se1', 'path': 'scenarios/SE1/', 'poi': [(prompts.atlas_init_s_ip, 'IP'), (prompts.atlas_init_domain, 'domain'), (prompts.atlas_init_file, 'file')]},
    {'name': 'se2', 'path': 'scenarios/SE2/', 'poi': [(prompts.atlas_init_s_ip, 'IP'), (prompts.atlas_init_domain, 'domain'), (prompts.atlas_init_file, 'file')]},
    {'name': 'se3', 'path': 'scenarios/SE3/', 'poi': [(prompts.atlas_init_s_ip, 'IP'), (prompts.atlas_init_domain, 'domain'), (prompts.atlas_init_file, 'file')]},
    {'name': 'se4', 'path': 'scenarios/SE4/', 'poi': [(prompts.atlas_init_s_ip, 'IP'), (prompts.atlas_init_domain, 'domain'), (prompts.atlas_init_file_py, 'file')]}
]

ss_scn = [{'name': 'ss1', 'path': 'scenarios/SS1/', 'poi': [(prompts.atlas_init_s_ip, 'IP'), (prompts.atlas_init_sb_domain, 'domain'), (prompts.atlas_init_sb_file, 'file')]},
    {'name': 'ss2', 'path': 'scenarios/SS2/', 'poi': [(prompts.atlas_init_s_ip, 'IP'), (prompts.atlas_init_sb_domain, 'domain'), (prompts.atlas_init_sb_file, 'file')]},
    {'name': 'ss3', 'path': 'scenarios/SS3/', 'poi': [(prompts.atlas_init_s_ip, 'IP'), (prompts.atlas_init_sb_domain, 'domain'), (prompts.atlas_init_sb_file, 'file')]},
    {'name': 'ss4', 'path': 'scenarios/SS4/', 'poi': [(prompts.atlas_init_s_ip, 'IP'), (prompts.atlas_init_sb_domain, 'domain'), (prompts.atlas_init_sb_file_py, 'file')]}
]

optc_scn = [
    {'name': 'optc1', 'path': 'scenarios/OPT1/', 'poi': [(prompts.opt1_c1, 'C1'), (prompts.opt1_c2,'C2'), (prompts.opt1_c3, 'C3')]},
    {'name': 'optc2', 'path': 'scenarios/OPT2/', 'poi': [(prompts.opt2_c1, 'C1'), (prompts.opt2_c3, 'C2'), (prompts.opt2_c2, 'C3')]},
    {'name': 'optc3', 'path': 'scenarios/OPT3/', 'poi': [(prompts.opt3_c1, 'C1'), (prompts.opt3_c2, 'C2'), (prompts.opt3_c3, 'C3')]}
]


def save_to_csv(df: pd.DataFrame, results_file: str):
    # save the results to a csv file
    # put headers if it is the first time
    # append to the file, do not overwrite
    if not os.path.exists(results_file):
        df.to_csv(results_file, index=False, header=True)
    else:
        df.to_csv(results_file, index=False, header=False, mode='a')


def already_completed(csv_file: str, test_name: str) -> bool:
    """Check if a test result is already recorded in the CSV (for --resume)."""
    if not os.path.exists(csv_file):
        return False
    try:
        df = pd.read_csv(csv_file)
        return test_name in df['test_name'].values
    except Exception:
        return False


def _run_one_scenario(llm, cfg, ablation, darpa):
    """Run a single scenario investigation and return the result string.
    Isolated into its own function so it can be submitted to a ThreadPoolExecutor."""
    if ablation:
        return ablation_optc(llm=llm, configs=cfg) if darpa else ablation_atlas(llm=llm, configs=cfg)
    else:
        return investigate_optc(llm=llm, configs=cfg) if darpa else investigate_atlas(llm=llm, configs=cfg)


def run_scenarios(scns: List, llm: ChatOpenAI, configs: Dict, ablation: bool, darpa: bool,
                  csv_file: str, resume: bool = False):
    """Run a list of scenarios, one POI at a time.

    Key behaviours added over the original:
    - IP POI budget boost: IP investigations get extra depth to trace multi-hop
      chains (IP → process → domain), targeting the observed recall gap.
    - Resume: if --resume is set, tests already present in the CSV are skipped.
    - Timestamped progress logging on every test start/finish.
    - 12-hour safety-net timeout per scenario via ThreadPoolExecutor (dead-man
      switch only — fires only if the error_count guards somehow still fail).
    """
    # Count total POIs for progress display
    total = sum(len(i['poi']) for i in scns)
    completed = 0

    for i in scns:
        scenario_path = os.path.normpath(os.path.join(APP_DIR, i['path']))
        base_cfg = configs.copy()
        base_cfg['data_path'] = scenario_path
        base_cfg['db_name'] = os.path.join(scenario_path, 'scenario.db')

        for p in i['poi']:
            completed += 1
            poi_cfg = base_cfg.copy()
            poi_cfg['clue'] = p[0]
            poi_cfg['test_name'] = f"{i['name']}_{p[1]}"

            # --- Resume: skip tests already in the output CSV ---
            if resume and already_completed(csv_file, poi_cfg['test_name']):
                ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                print(f"[{ts}] [SKIP] {poi_cfg['test_name']} already in CSV — skipping.")
                continue

            # --- IP POI budget boost ---
            # IP-based investigations require tracing multi-hop chains and
            # historically have the worst recall (6% and 1.15% on s1/se2).
            # Giving them more iterations directly targets this gap.
            if p[1] == 'IP':
                poi_cfg['max_investigations'] = constants.IP_MAX_INVESTIGATIONS
                poi_cfg['max_questions']      = constants.IP_MAX_QUESTIONS
                poi_cfg['max_queries']        = constants.IP_MAX_QUERIES
                budget_tag = (f"inv={constants.IP_MAX_INVESTIGATIONS}, "
                              f"q={constants.IP_MAX_QUESTIONS}, "
                              f"sql={constants.IP_MAX_QUERIES} [IP BOOST]")
            else:
                budget_tag = (f"inv={poi_cfg['max_investigations']}, "
                              f"q={poi_cfg['max_questions']}, "
                              f"sql={poi_cfg['max_queries']}")

            ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            print(f"\n[{ts}] ▶ Starting {poi_cfg['test_name']} ({completed}/{total}) — {budget_tag}")
            t_start = time.time()

            # --- 12-hour safety-net timeout (dead-man switch) ---
            results = None
            timed_out = False
            try:
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                    future = executor.submit(_run_one_scenario, llm, poi_cfg.copy(), ablation, darpa)
                    try:
                        results = future.result(timeout=constants.DEFAULT_SCENARIO_TIMEOUT)
                    except concurrent.futures.TimeoutError:
                        timed_out = True
                        future.cancel()
            except Exception as e:
                ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                print(f"[{ts}] ✗ EXCEPTION in {poi_cfg['test_name']}: {e}")

            duration_min = (time.time() - t_start) / 60
            ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            if timed_out:
                timeout_hrs = constants.DEFAULT_SCENARIO_TIMEOUT / 3600
                print(f"[{ts}] ⚠ TIMEOUT: {poi_cfg['test_name']} exceeded {timeout_hrs:.0f}h "
                      f"safety limit after {duration_min:.1f} min — recording zeros and continuing.")

            # Evaluate and save (empty string on timeout/error → all-zero metrics)
            er = evaluate_report(poi_cfg, results if results is not None else "")
            save_to_csv(er.get_pd(), csv_file)

            status = "TIMEOUT" if timed_out else ("✓" if results is not None else "✗ ERROR")
            print(f"[{ts}] {status} {poi_cfg['test_name']} — {duration_min:.1f} min — saved to CSV")


if __name__ == '__main__':
    
    parser = argparse.ArgumentParser(description='Attack investigation tool backed by LLMs')
    parser.add_argument('--max-investigations', type=int, help='Maximum number of investigations for the chief inspector')
    parser.add_argument('--max-questions', type=int, help='Maximum number of questions to ask for the investigator')
    parser.add_argument('--max-queries', type=int, help='Maximum number of SQL queries to run')
    parser.add_argument('--max-tokens', type=int, help='Maximum number of tokens per LLM response')
    parser.add_argument('--ablation-agent', action='store_true', help='Run ablation agent instead of Clouseau')
    parser.add_argument('--scenarios-si', action='store_true', help='Run ATLAS scenarios S1-S4')
    parser.add_argument('--scenarios-mi', '--scenarios-ml', action='store_true',
                        dest='scenarios_mi',
                        help='Run ATLAS scenarios M1-M6 (multi-host lateral movement)')
    parser.add_argument('--scenarios-se', action='store_true', help='Run ATLAS scenarios SE1-SE4')
    parser.add_argument('--scenarios-ss', action='store_true', help='Run ATLAS scenarios SS1-SS4')
    parser.add_argument('--scenarios-optc', action='store_true', help='Run generalizability scenarios OPTC1-OPTC3')
    parser.add_argument('--no-warn', action='store_true', help='Suppress warnings about tracing not being set up')
    parser.add_argument('--csv-file', type=str, help='CSV file to store evaluation results')
    parser.add_argument('--resume', action='store_true',
                        help='Skip tests already present in the output CSV (useful for resuming interrupted runs)')
    args = parser.parse_args()

    # get system configs first
    ablation_agent = False
    scenarios_si = False
    scenarios_mi = False   # multi-host M1-M6
    scenarios_se = False
    scenarios_ss = False
    scenarios_optc = False
    no_warn = False
    resume = False
    current_time = datetime.now().strftime('%Y-%m-%d-%H')
    configs = {}
    configs['max_investigations'] = args.max_investigations if args.max_investigations else constants.DEFAULT_INVESTIGATIONS
    configs['max_questions'] = args.max_questions if args.max_questions else constants.DEFAULT_QUESTIONS
    configs['max_queries'] = args.max_queries if args.max_queries else constants.DEFAULT_QUERIES
    configs['max_tokens'] = args.max_tokens if args.max_tokens else constants.DEFAULT_MAX_TOKENS
    csv_file = args.csv_file if args.csv_file else f"results_{current_time}.csv"

    if args.ablation_agent:
        ablation_agent = True
        configs['max_queries'] = args.max_queries if args.max_queries else constants.DEFAULT_QUERIES_ABLATION

    if args.scenarios_si:
        scenarios_si = True
    if args.scenarios_mi:
        scenarios_mi = True
    if args.scenarios_se:
        scenarios_se = True
    if args.scenarios_ss:
        scenarios_ss = True
    if args.scenarios_optc:
        scenarios_optc = True
    if args.no_warn:
        no_warn = True
    if args.resume:
        resume = True

    if not (scenarios_si or scenarios_mi or scenarios_se or scenarios_optc or scenarios_ss):
        print("No scenarios selected. Use --scenarios-si, --scenarios-mi, --scenarios-se, --scenarios-ss, or --scenarios-optc to select scenarios.")
        exit(1)
    

    # get LLM
    model = os.environ.get('LLM_MODEL', None)
    api_key = os.environ.get('API_KEY', None)
    base_url = os.environ.get('BASE_URL', None)

    if base_url is not None:
        print("Using custom base URL:", base_url)

    try:
        llm, provider = create_llm_from_env(model=model, api_key=api_key, base_url=base_url)
    except LLMConfigError as exc:
        print("LLM configuration error:", str(exc))
        exit(1)

    print("Using model:", model)
    print("Provider type:", provider)
    print('Saving results to:', csv_file)
    print(f"Error loop guard: investigator max_errors={constants.DEFAULT_MAX_ERRORS}, "
          f"chief max_errors={constants.DEFAULT_CHIEF_MAX_ERRORS}")
    print(f"IP POI budget boost: inv={constants.IP_MAX_INVESTIGATIONS}, "
          f"q={constants.IP_MAX_QUESTIONS}, sql={constants.IP_MAX_QUERIES}")
    print(f"Safety-net timeout per scenario: {constants.DEFAULT_SCENARIO_TIMEOUT/3600:.0f}h")
    if resume:
        print("Resume mode: ON — tests already in CSV will be skipped.")
    print("This may take a while (up to several days for the full suite)...")

    if not no_warn:
        print("Make sure you have enough quota in your provider account.")

        if os.environ.get('LANGSMITH_TRACING', None) is None:
            print("Make sure tracing is set up using LangSmith or another provider.")
            print("It is super easy to set up: https://docs.langchain.com/langsmith/observability-quickstart")

        # confirm user wants to proceed
        proceed = input("Do you want to proceed? (y/n): ")
        if proceed.lower() != 'y':
            print("Exiting...")
            exit(0)

    if scenarios_si:
        print("\nRunning ATLAS SI scenarios")
        run_scenarios(si_scn, llm, configs, ablation_agent, False, csv_file, resume=resume)
    
    if scenarios_mi:
        print("\nRunning ATLAS MI scenarios (M1-M6 multi-host)")
        run_scenarios(ml_scn, llm, configs, ablation_agent, False, csv_file, resume=resume)
    
    if scenarios_se:
        print("\nRunning ATLAS SE scenarios")
        run_scenarios(se_scn, llm, configs, ablation_agent, False, csv_file, resume=resume)
    
    if scenarios_ss:
        print("\nRunning ATLAS SS scenarios")
        run_scenarios(ss_scn, llm, configs, ablation_agent, False, csv_file, resume=resume)
    
    if scenarios_optc:
        print("\nRunning OPTC scenarios")
        run_scenarios(optc_scn, llm, configs, ablation_agent, True, csv_file, resume=resume)

    print("\nDone")
    exit(0)
