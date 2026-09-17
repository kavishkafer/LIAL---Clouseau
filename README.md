# LIAL + Clouseau: Hierarchical Multi-Agent Attack Investigation System

Clouseau is a hierarchical multi-agent system for iterative cyber attack investigation. Starting from a point of interest (e.g., a suspicious domain), it autonomously explores incident data sources, issues targeted queries, analyzes evidence, and incrementally reconstructs an attack narrative. Clouseau operates without training or predefined heuristics, instead leveraging LLMs' inherent understanding of systems and security to correlate and reason about incident data I am using the initial code base and extend it to work with local LLM and testing .


## Repository High-Level Structure

- `artifact` — source code for Clouseau, including prompts and processed scenarios for testing.
- `claims` — instructions and scripts to reproduce paper's main claims.

## Installation

Create a virtual environment first with conda or any other alternatives. We tested this with Python 3.12.11.

```bash
pip install -r artifact/requirements.txt
```

## Local LLM Support (vLLM)

Clouseau now supports local OpenAI-compatible endpoints, including vLLM.

1. Start a vLLM server with an OpenAI-compatible API.
2. Copy `artifact/.env.example` values into your shell environment.
3. Set at least:

```bash
export LLM_MODEL="meta-llama/Llama-3.1-8B-Instruct"
export BASE_URL="http://localhost:8000/v1"
export API_KEY="local"
```

Then run as usual:

```bash
cd artifact
python app.py --scenarios-si --no-warn
```

The app validates endpoint and model reachability before running and fails fast with a clear error if configuration is invalid.

## Agentic Handoff

Clouseau now writes run-level investigation summaries to `AGENTIC_HANDOFF.md`.

- `Developer Handoff` section tracks implementation status and working assumptions.
- `Runtime Log` section is appended during scenario execution with run start, tool outcomes, and final summary.

## Reproduction Notes
You need a reachable LLM endpoint before running scripts.

- OpenAI path: set `API_KEY` and `LLM_MODEL`.
- Local vLLM path: set `BASE_URL`, `LLM_MODEL`, and `API_KEY` (for example `local`).

### Claim 1: Single Host Scenarios
A run of clouseau to reproduce results for Single Host scenarios (Section 6.1). Run:

```bash
./claims/claim1/run.sh
```

Then inspect `claims/claim1/average.csv`, recall, precision and f1 should above 95%.


### Claim 2: Single Host Extended Scenarios
A run of clouseau to reproduce results for Single Host Extended scenarios (Section 6.1). Run:

```bash
./claims/claim2/run.sh
```

Then inspect `claims/claim2/average.csv`, recall, precision and f1 should above 95%.


### Claim 3: Keyword Sensitivity Scenarios
A run of clouseau to reproduce results for Keyword Sensitivity scenarios (Section 6.2). Run:

```bash
./claims/claim3/run.sh
```

Then inspect `claims/claim3/average.csv`, recall, precision and f1 should above 95%.

### Other Experiments and Claims
Want to go beyond the paper claims? Use the CLI to explore, tweak, and run targeted experiments:

```bash
cd artifact
python app.py --help
```

This shows how to:
- switch the underlying LLM model.
- enable single‑agent mode.
- evaluate on OpTC datasets.

To run single exeperiments, you can utilize the notebook `artifact/clouseau.ipynb`.
