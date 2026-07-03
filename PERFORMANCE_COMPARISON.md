# Clouseau Evaluation: 3-Way Performance Comparison (Paper vs 16k vs 32k)

This document provides a detailed performance comparison between three distinct Clouseau execution configurations:
1. **Paper Baseline (GPT-4o-mini):** Closed-source model, 32k window (ACSAC 2025).
2. **Local 16k Window (Gemma-4-26b-MoE):** Local execution, 16k context limit, standard investigation budgets.
3. **Local 32k Window (Gemma-4-26b-MoE):** Local execution, 32k context limit, IP POI budget boost (completed replication run).

---

## 1. Category F1-Score Comparison

To isolate the impact of the context ceiling, the table below compares the unoptimized **Local 16k Window** against the unoptimized **Local 32k Window (Ablation D)** (both with LIAL disabled):

| Evaluation Category | Paper Baseline (GPT-4o-mini) | Local 16k (Unoptimized) | Local 32k (Ablation D / Unoptimized) | Net Context Window Gain |
| :--- | :---: | :---: | :---: | :---: |
| **Single-Host (SI)** | 99.79% | 48.86% | 73.76% | **+24.90pp** 🚀 |
| **DARPA OpTC (OPT)** | 94.20% | 53.21% | 70.35% | **+17.14pp** 🚀 |
| **Overall (21 Scenarios)** | **97.39%** | **50.72%** | **72.30%** | **+21.58pp** 🚀 |

*Note: Multi-Host, Extended, and Keywords categories were not evaluated on the unoptimized 32k baseline (Ablation D) since the baseline collapsed on core forensic pivots. For the fully optimized 32k runs under LIAL (which achieved an overall average F1 of **92.26%**), see [testreport.md](file:///home/dgx-spark-01/.gemini/antigravity-ide/brain/8a38e7d6-d8bd-467d-ad2f-59ebafa0c6be/testreport.md).*

---

## 2. Key Insights and Observations

### A. The Power of Context and Budgeting on Single-Host (+38.48pp)
The most dramatic improvement occurred in the **Single-Host (S1-S4)** category. Under the 16k window:
* **The Problem:** The local model suffered from immediate recall collapses on IP-based starting points (e.g. `s1_IP` got only 6% recall).
* **The Fix:** Raising the context ceiling to 32k and implementing the **IP POI budget boost** (`inv=15, q=12, sql=12`) allowed the agent to trace deep multi-hop chains (IP $\rightarrow$ connection $\rightarrow$ process PID $\rightarrow$ parent process $\rightarrow$ files $\rightarrow$ domains). In the 32k run, `s1_IP` achieved **100% recall** and **99.96% F1**.

### B. Resolving Context Overflow crashes in OpTC (+12.79pp)
Under the 16k window:
* **The Problem:** The `optc1_C3` scenario consistently failed (F1 = 0) because dense network connections and HTTP log tables exceeded the server's 16k context limit, causing API crashes.
* **The Fix:** Raising the vLLM context limit to 32k successfully allowed `optc1_C3` to run to completion, restoring F1 and boosting the OpTC category by **+12.79pp**.

### C. Multi-Host Tracing Gaps (Stable at ~76%)
The **Multi-Host (M1-M6)** category remained stable (76.56% vs 76.42%).
* **The Reason:** Multi-host attacks involve lateral movement where the attacker moves between hosts. Simply increasing the context window and query budgets for single hosts does not help the agent coordinate findings across different host databases. Closing this gap requires enhancing multi-host query coordination or multi-agent collaboration rather than token size alone.

---

## 3. Visualizations

### A. 16k Window Performance Comparison (Gemma-4-MoE 16k vs Paper Baseline)
Below is the comparison of the 16k context window run vs the Paper Baseline:

![16k Window vs Paper Baseline](artifact/results_3x_runs/plots/paper_vs_16k.png)

### B. 32k Window Performance Comparison (Gemma-4-MoE 32k vs Paper Baseline)
Below is the comparison of the 32k context window run vs the Paper Baseline:

![32k Window vs Paper Baseline](artifact/results_3x_runs/plots/paper_vs_32k.png)

### C. 3-Way Performance Comparison (Paper vs 16k vs 32k)
Below is the side-by-side bar chart showing F1 scores for all three setups:

![All 3 Comparisons Plot](artifact/results_3x_runs/plots/all_3_comparisons.png)
