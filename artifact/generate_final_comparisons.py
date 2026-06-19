#!/usr/bin/env python3
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path

# Set style
sns.set_theme(style="whitegrid")
plt.rcParams['font.sans-serif'] = 'DejaVu Sans'

# Load our final aggregated results
csv_path = Path("artifact/artifact/results_3x_runs/AGGREGATED_RESULTS_3X.csv")
df = pd.read_csv(csv_path)

# Extract scenario type
def extract_type(name):
    if not isinstance(name, str): return "Other"
    name_lower = name.lower()
    if name_lower.startswith("se"): return "Extended"
    elif name_lower.startswith("ss"): return "Keywords"
    elif name_lower.startswith("s"): return "Single-Host"
    elif name_lower.startswith("m"): return "Multi-Host"
    elif name_lower.startswith("opt"): return "OpTC"
    return "Other"

df["category"] = df["test_name"].apply(extract_type)

# Calculate our category means (in fraction form 0-1)
optimized_means = df.groupby("category")["f1"].mean()

# Map to the specific order we want to plot
cat_map = {
    'Single-Host (S)': 'Single-Host',
    'Extended (SE)': 'Extended',
    'Keywords (SS)': 'Keywords',
    'Multi-Host (MI)': 'Multi-Host',
    'OpTC (OPT)': 'OpTC'
}

categories = ['Single-Host (S)', 'Extended (SE)', 'Keywords (SS)', 'Multi-Host (MI)', 'OpTC (OPT)']

# F1 values
paper_f1 = [0.9979, 0.9979, 0.9980, 0.9737, 0.9420]
local_32k_baseline_f1 = [0.8734, 0.9512, 0.9291, 0.7642, 0.6600]
local_32k_optimized_f1 = [optimized_means.get(cat_map[c], 0.0) for c in categories]

print("Category averages:")
for c, p, b, o in zip(categories, paper_f1, local_32k_baseline_f1, local_32k_optimized_f1):
    print(f"  {c}: Paper={p*100:.2f}%, Baseline={b*100:.2f}%, Optimized={o*100:.2f}%")

out_dir = Path("artifact/artifact/results_3x_runs/plots")
out_dir.mkdir(exist_ok=True)

# Helper function to add value labels
def add_value_labels(ax, fontsize=9.5):
    for p in ax.patches:
        h = p.get_height()
        if h > 0:
            ax.annotate(f'{h*100:.1f}%', (p.get_x() + p.get_width() / 2., h),
                        ha='center', va='center', xytext=(0, 8), textcoords='offset points', 
                        fontsize=fontsize, fontweight='bold')

# 1. Plot: Paper Baseline vs Our Local Optimized
plt.figure(figsize=(11, 7))
data_comp = []
for cat, p_val, lo_val in zip(categories, paper_f1, local_32k_optimized_f1):
    data_comp.append({'Category': cat, 'Setup': 'Paper Baseline (GPT-4.1-Mini / GPT-4o-mini)', 'F1 Score': p_val})
    data_comp.append({'Category': cat, 'Setup': 'Our Local Optimized Run (Gemma-4-MoE)', 'F1 Score': lo_val})
df_comp = pd.DataFrame(data_comp)

ax1 = sns.barplot(
    data=df_comp,
    x='Category',
    y='F1 Score',
    hue='Setup',
    palette=['#1B365D', '#2ECC71'],
    edgecolor='black',
    alpha=0.9
)
plt.title("Clouseau Performance: GPT-4o-mini Paper Baseline vs Our Local Optimized Run (3-Run Avg)", fontsize=13, fontweight='bold', pad=15)
plt.xlabel("Evaluation Suite Category", fontsize=12, fontweight='bold')
plt.ylabel("Average F1 Score", fontsize=12, fontweight='bold')
plt.ylim(0, 1.15)
plt.grid(True, axis='y', alpha=0.3)
add_value_labels(ax1, fontsize=10)
plt.tight_layout()
plot_path_comp = out_dir / "paper_vs_local.png"
plt.savefig(plot_path_comp, dpi=300)
plt.close()
print(f"✓ Paper vs Local Optimized plot generated at: {plot_path_comp}")

# 2. Plot: 3-Way Comparison (Paper vs Baseline vs Optimized)
plt.figure(figsize=(13, 8))
data_all = []
for cat, p_val, l32b_val, l32o_val in zip(categories, paper_f1, local_32k_baseline_f1, local_32k_optimized_f1):
    data_all.append({'Category': cat, 'Setup': 'Paper Baseline (GPT-4o-mini)', 'F1 Score': p_val})
    data_all.append({'Category': cat, 'Setup': 'Local 32k Baseline (Gemma-4-MoE)', 'F1 Score': l32b_val})
    data_all.append({'Category': cat, 'Setup': 'Our Local Optimized (Gemma-4-MoE)', 'F1 Score': l32o_val})
df_all = pd.DataFrame(data_all)

ax2 = sns.barplot(
    data=df_all,
    x='Category',
    y='F1 Score',
    hue='Setup',
    palette=['#1B365D', '#E74C3C', '#2ECC71'],
    edgecolor='black',
    alpha=0.9
)
plt.title("Clouseau Benchmark: F1 Performance Comparison Across Setup Configurations", fontsize=14, fontweight='bold', pad=15)
plt.xlabel("Evaluation Suite Category", fontsize=12, fontweight='bold')
plt.ylabel("Average F1 Score", fontsize=12, fontweight='bold')
plt.ylim(0, 1.15)
plt.grid(True, axis='y', alpha=0.3)
add_value_labels(ax2, fontsize=9.5)
plt.tight_layout()
plot_path_all = out_dir / "all_3_comparisons.png"
plt.savefig(plot_path_all, dpi=300)
plt.close()
print(f"✓ All 3 configurations comparison plot generated at: {plot_path_all}")
