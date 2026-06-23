import sqlite3
import os
import sys
import json

# Add the artifact directory to the path so we can import qa_agent
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from qa_agent import format_cell

def run_query_benchmark(db_path, query):
    if not os.path.exists(db_path):
        return None
    
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(query)
            rows = cursor.fetchall()
            if not rows:
                return None
            
            col_names = [desc[0] for desc in cursor.description]
            
            # Scenario 1: Without T6 (no cell truncation)
            untruncated_rows = []
            for row in rows:
                untruncated_rows.append('\t'.join(str(val) for val in row))
            untruncated_str = '\n'.join(untruncated_rows)
            
            # Scenario 2: With T6 (using format_cell)
            truncated_rows = []
            for row in rows:
                formatted_row = [format_cell(col_names[i], row[i]) for i in range(len(row))]
                truncated_rows.append('\t'.join(formatted_row))
            truncated_str = '\n'.join(truncated_rows)
            
            raw_len = len(untruncated_str)
            trunc_len = len(truncated_str)
            reduction = (1 - (trunc_len / raw_len)) * 100 if raw_len > 0 else 0
            
            # Get samples of long rows
            sample_raw = ""
            sample_truncated = ""
            for row in rows:
                for val_idx, val in enumerate(row):
                    if isinstance(val, str) and len(val) > 150:
                        sample_raw = val
                        sample_truncated = format_cell(col_names[val_idx], val)
                        break
                if sample_raw:
                    break
            
            return {
                'raw_char_count': raw_len,
                'truncated_char_count': trunc_len,
                'reduction_pct': reduction,
                'row_count': len(rows),
                'sample_raw': sample_raw,
                'sample_truncated': sample_truncated
            }
    except Exception as e:
        print(f"Error running benchmark on query: {e}")
        return None

def main():
    print("======================================================================")
    print("          CLOUSEAU TOKEN MICRO-BENCHMARK (T6 OPTIMISATION)")
    print("======================================================================")
    
    benchmarks = [
        {
            'id': 'micro_1_optc_all',
            'name': 'Micro-1 (DARPA OpTC http_logs - all rows)',
            'db': 'scenarios/OPT1/scenario.db',
            'query': 'SELECT * FROM http_logs LIMIT 30'
        },
        {
            'id': 'micro_2_atlas_audit',
            'name': 'Micro-2 (ATLAS S1 audit_logs - all rows)',
            'db': 'scenarios/S1/scenario.db',
            'query': 'SELECT * FROM audit_logs LIMIT 30'
        },
        {
            'id': 'micro_3_atlas_browser',
            'name': 'Micro-3 (ATLAS S1 browser_history - all rows)',
            'db': 'scenarios/S1/scenario.db',
            'query': 'SELECT * FROM browser_history LIMIT 30'
        },
        {
            'id': 'micro_4_atlas_browser_long',
            'name': 'Micro-4 (ATLAS S1 browser_history - long cookies/headers only)',
            'db': 'scenarios/S1/scenario.db',
            'query': 'SELECT * FROM browser_history WHERE length(headers) > 150 LIMIT 30'
        }
    ]
    
    artifact_dir = os.path.dirname(os.path.abspath(__file__))
    results = {}
    
    for bm in benchmarks:
        print(f"\nRunning {bm['name']}...")
        db_path = os.path.join(artifact_dir, bm['db'])
        res = run_query_benchmark(db_path, bm['query'])
        
        if res:
            print(f"  Rows retrieved: {res['row_count']}")
            print(f"  Raw character count (without T6): {res['raw_char_count']:,} chars")
            print(f"  Truncated character count (with T6): {res['truncated_char_count']:,} chars")
            print(f"  Character volume reduction: {res['reduction_pct']:.2f}%")
            
            raw_tokens = res['raw_char_count'] // 4
            trunc_tokens = res['truncated_char_count'] // 4
            print(f"  Approximate token savings: {raw_tokens - trunc_tokens:,} tokens ({raw_tokens:,} -> {trunc_tokens:,})")
            
            if res['sample_raw']:
                print("\n  Sample Raw Value (trunc to 80 chars):")
                print(f"    {res['sample_raw'][:80]}...")
                print("  Sample Truncated Value:")
                print(f"    {res['sample_truncated']}")
            
            results[bm['id']] = {
                'name': bm['name'],
                'row_count': res['row_count'],
                'raw_char_count': res['raw_char_count'],
                'truncated_char_count': res['truncated_char_count'],
                'reduction_pct': res['reduction_pct'],
                'raw_tokens': raw_tokens,
                'truncated_tokens': trunc_tokens,
                'token_savings': raw_tokens - trunc_tokens
            }
    
    # Save the results to artifact/results/token_micro_benchmark.json
    results_dir = os.path.join(artifact_dir, 'results')
    os.makedirs(results_dir, exist_ok=True)
    out_path = os.path.join(results_dir, 'token_micro_benchmark.json')
    with open(out_path, 'w') as f:
        json.dump(results, f, indent=2)
    print(f"\n✓ Saved micro-benchmark results to: {out_path}")

if __name__ == '__main__':
    main()
