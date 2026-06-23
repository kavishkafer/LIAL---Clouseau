import pandas as pd
import json
import re
import os
import sqlite3
from sklearn.metrics import confusion_matrix
from langchain_core.callbacks import UsageMetadataCallbackHandler

class EvaluationResults:
    def extract_artifacts_from_text(self, text: str) -> dict:
        """Fallback parser to extract forensic artifacts from plain text if JSON parsing fails."""
        # Extract IP addresses
        ips = list(set(re.findall(r'\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b', text)))
        
        # Extract domains and files using suffix checks
        words_with_dot = re.findall(r'\b[a-zA-Z0-9.-]+\.[a-zA-Z]{2,6}\b', text)
        domains = []
        files = []
        for w in words_with_dot:
            w_lower = w.lower()
            if w_lower.endswith(('.exe', '.dll', '.bat', '.vbs', '.tmp', '.doc', '.docx', '.pdf', '.txt', '.rtf', '.db', '.csv', '.py', '.sh')):
                files.append(w)
            else:
                if not re.match(r'^(?:[0-9]{1,3}\.){3}[0-9]{1,3}$', w):
                    domains.append(w)
        
        domains = list(set(domains))
        files = list(set(files))
        
        # Extract PIDs and associate with closest process name
        all_procs = list(set(re.findall(r'\b\w+\.(?:exe|vbs|bat|sh|py)\b', text, re.IGNORECASE)))
        pids = re.findall(r'\b\d{3,6}\b', text)
        
        mal_procs = []
        for pid in pids:
            pid_pos = text.find(pid)
            # check a window of 60 characters before and after the PID
            window = text[max(0, pid_pos - 60):min(len(text), pid_pos + 60)]
            found_proc = ""
            for proc in all_procs:
                if proc.lower() in window.lower():
                    found_proc = proc
                    break
            mal_procs.append({
                "pid": int(pid),
                "name": found_proc
            })
            
        # Deduplicate processes by PID
        unique_procs = {}
        for p in mal_procs:
            unique_procs[p["pid"]] = p["name"]
            
        malicious_processes = [{"pid": pid, "name": name} for pid, name in unique_procs.items()]
        
        return {
            "addresses": ips,
            "domains": domains,
            "files": files,
            "malicious_processes": malicious_processes,
            "tainted_processes": []
        }

    def parse_report(self, json_report: str) -> dict:
        # Regular expression to match JSON array structures
        json_report_clean = json_report.replace("\n", "").replace(",}```", "}```")
        json_pattern = r"```json(.*?)```"  # Extract JSON content within code block markers

        # Search for JSON structures in the text
        match = re.search(json_pattern, json_report_clean, re.DOTALL)
        if match:
            # Extract JSON content and clean it
            json_content = match.group(1).strip()

            # Replace single quotes with double quotes for JSON compatibility
            json_content = re.sub(r"'", '"', json_content)

            # Escape backslashes for JSON compatibility
            json_content = json_content.replace("\\", "\\\\")

            try:
                # Parse the cleaned JSON string
                parsed_data = json.loads(json_content)
                return parsed_data
            except json.JSONDecodeError:
                print("Failed to parse JSON. Falling back to intelligent text extraction.")
                return self.extract_artifacts_from_text(json_report)
        else:
            try:
                parsed_data = json.loads(json_report)
                return parsed_data
            except json.JSONDecodeError:
                print("Failed to parse JSON. Falling back to intelligent text extraction.")
                return self.extract_artifacts_from_text(json_report)

    def evaluate_atlas(self):

        y_true, y_pred = [], []
        pred_artifacts = self.predicted

        # Handle case where parsing failed and returned None
        if pred_artifacts is None:
            pred_artifacts = {}

        if type(pred_artifacts) == list:
            pred_artifacts = pred_artifacts[0] if pred_artifacts else {}

        # Set of common benign process names in ATLAS logs to exclude from name-only matching
        # as matching them by name triggers massive false positives due to substring checks.
        COMMON_BENIGN_PROCESSES = {
            'cmd.exe', 'cmd', 'firefox.exe', 'firefox', 'plugin-container.exe', 
            'searchprotocolhost.exe', 'werfault.exe', 'svchost.exe', 'explorer.exe', 
            'iexplore.exe', 'chrome.exe', 'powershell.exe', 'powershell', 'wscript.exe', 
            'cscript.exe', 'services.exe', 'lsass.exe', 'taskhost.exe', 'searchindexer.exe',
            'svchost', 'explorer', 'chrome', 'python.exe', 'python',
            'winword.exe', 'winword', 'eqnedt32.exe', 'eqnedt32', 'acrord32.exe', 'acrord32',
            'excel.exe', 'excel'
        }

        file_path = os.path.join(self.data_path, 'scenario.csv')
        with open(file_path) as f:
            for line in f:
                line_lower = line.lower()
                parts = line.strip().split(',')
                event_t = 1 if '+' in parts[-1] else 0

                event_p = 0
                # Normalize both sides for path/domain matching (lowercase + backslash→slash)
                line_norm = line_lower.replace('\\', '/')

                if any(addr in line for addr in pred_artifacts.get("addresses", [])):
                    event_p = 1
                elif any(f.lower().replace('\\', '/') in line_norm
                         and not f.lower().replace('\\', '/').startswith('c:/windows/system32/')
                         for f in pred_artifacts.get("files", [])):
                    event_p = 1
                elif any(d.lower() in line_lower
                         for d in pred_artifacts.get("domains", [])):
                    event_p = 1
                # Check malicious_processes only (NOT tainted_processes).
                # Tainted processes (e.g. firefox.exe, cmd.exe) are hijacked benign
                # processes with a large history of benign events before the attack.
                # Scoring them causes massive FPs. The agent prompt is updated so that
                # any process that performs malicious actions is listed in
                # malicious_processes regardless of whether it was originally benign.
                else:
                    for proc in pred_artifacts.get("malicious_processes", []):
                        proc_name = proc.get('name', '').lower().strip()
                        if proc_name and proc_name not in COMMON_BENIGN_PROCESSES:
                            if proc_name in line_lower:
                                event_p = 1

                y_true.append(event_t)
                y_pred.append(event_p)

        self.y_true = y_true
        self.y_pred = y_pred

    def evaluate_optc(self):
        y_true, y_pred = [], []
        pred_artifacts = self.predicted
        
        # Handle case where parsing failed and returned None
        if pred_artifacts is None:
            pred_artifacts = {}
        
        if type(pred_artifacts) == list:
            pred_artifacts = pred_artifacts[0] if pred_artifacts else {}
        
        # Step 1: Build the initial set of predicted root malicious process IDs.
        # We convert them to strings for consistency.
        initial_pids = []
        # Only use malicious_processes (NOT tainted_processes).
        # Tainted processes are hijacked benign processes whose descendant trees include
        # many pre-attack benign children, inflating FPs in the propagation step.
        for key in ["malicious_processes"]:
            for proc in pred_artifacts.get(key, []):
                pid = proc.get("pid")
                if pid is not None:
                    initial_pids.append(str(pid))
        pred_pids = set(initial_pids)

                
        file_path = os.path.join(self.data_path, 'scenario.db')
        # Step 2: Propagate the predictions to include all descendant process IDs.
        with sqlite3.connect(file_path) as conn:
            cursor = conn.cursor()
            # We iterate until no new descendants are found.
            new_found = True
            iteration = 0
            while new_found:
                iteration += 1
                # Create parameter placeholders for the current set.
                placeholders = ",".join("?" for _ in pred_pids)
                query = f"SELECT DISTINCT pid FROM processes_logs WHERE ppid IN ({placeholders})"
                cursor.execute(query, tuple(pred_pids))
                rows = cursor.fetchall()
                # Extract descendant pids from the query result.
                descendant_pids = set(str(row[0]) for row in rows)
                # Only keep new ones.
                new_descendants = descendant_pids - pred_pids
                
                #print(f"Iteration {iteration}: Found {len(new_descendants)} new descendant pids.")
                if new_descendants:
                    pred_pids.update(new_descendants)
                else:
                    new_found = False

            #print("Total predicted malicious process ids (root + descendants):", len(pred_pids))
            
            # Step 3: Query all_logs and assign event labels.
            cursor.execute("SELECT pid, mal FROM all_logs ORDER BY ts ASC")
            rows = cursor.fetchall()
        
            # For each event record in all_logs, we mark the event as malicious (prediction==1)
            # if its pid is in our predicted malicious process ids.
            for row in rows:
                pid, mal = row  # ts is only used for ordering
                true_label = 1 if mal == 1 else 0  # Ground truth from the 'mal' column.
                pred_label = 1 if str(pid) in pred_pids else 0
                y_true.append(true_label)
                y_pred.append(pred_label)
        
        self.y_true = y_true
        self.y_pred = y_pred
        
    def __init__(self, configs: dict, json_report: str, usage: UsageMetadataCallbackHandler = None):
        self.test_name = configs.get('test_name', 'default_test')
        self.data_path = configs.get('data_path', 'default_path')
        self.json_report = json_report
        self.predicted = self.parse_report(json_report)

        # open data path and read ground truth
        # extract artifacts from json report
        # calculate metrics
        self.y_true = []
        self.y_pred = []
        self.input_tokens = 0
        self.output_tokens = 0
        self.total_tokens = 0
        self.model_name = configs.get('model_name', "None")

        if usage is not None and usage.usage_metadata:
            self.model_name = next(iter(usage.usage_metadata)) 
            self.input_tokens = usage.usage_metadata[self.model_name]['input_tokens']
            self.output_tokens = usage.usage_metadata[self.model_name]['output_tokens']
            self.total_tokens = usage.usage_metadata[self.model_name]['total_tokens']

        try:
            if configs.get('is_darpa', False):
                self.evaluate_optc()
            else:
                self.evaluate_atlas()
        except Exception as e:
            print(f"{self.test_name}: Error evaluating results: {e}")
            print(self.json_report)
        
        # Confusion matrix in the order [[TN, FP], [FN, TP]]
        self.tn, self.fp, self.fn, self.tp = confusion_matrix(self.y_true, self.y_pred, labels=[0, 1]).ravel()    
        self.P = self.tp + self.fn      # total positives in the data
        self.N = self.tn + self.fp      # total negatives in the data
            
    def get_pd(self):
        # return a pandas dataframe of the results
        data = {
            'test_name': self.test_name,
            'P': self.P,
            'N': self.N,
            'tp': self.tp,
            'tn': self.tn,
            'fp': self.fp,
            'fn': self.fn,
            'total_tokens': self.total_tokens,
            'input_tokens': self.input_tokens,
            'output_tokens': self.output_tokens,
            'model_name': self.model_name
        }
        df = pd.DataFrame(data, index=[0])
        return df
    
    def __str__(self):
        return f"P = {self.P}, N = {self.N}, tp = {self.tp}, tn = {self.tn}, fp = {self.fp}, fn = {self.fn}"

    def pretty_str(self):
        s = f"""Test name = {self.test_name}, P = {self.P}, N = {self.N}, tp = {self.tp}, tn = {self.tn}, fp = {self.fp}, fn = {self.fn}"""
        s += f"""\ninput tokens = {self.input_tokens}, output tokens = {self.output_tokens}, model = {self.model_name}"""
        return s

def evaluate_report(configs: dict, report: str, usage: UsageMetadataCallbackHandler = None):
    
    # prompt llm to produce json report

    # pass json report for calculation
    results = EvaluationResults(configs, report, usage)
    return results