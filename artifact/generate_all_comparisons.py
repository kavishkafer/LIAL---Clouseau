#!/usr/bin/env python3
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path

# Set style
sns.set_theme(style="whitegrid")
plt.rcParams['font.sans-serif'] = 'DejaVu Sans'

# Data definition
categories = ['Single-Host (S)', 'Extended (SE)', 'Keywords (SS)', 'Multi-Host (MI)', 'OpTC (OPT)']
paper_f1 = [0.9979, 0.9979, 0.9980, 0.9737, 0.9420]
local_16k_f1 = [0.4886, 0.7991, 0.8965, 0.7656, 0.5321]
local_32k_f1 = [0.8734, 0.9512, 0.9291, 0.7642, 0.6600]

out_dir = Path("artifact/results_3x_runs/plots")
out_dir.mkdir(exist_ok=True)

# Helper function to add value labels
def add_value_labels(ax, fontsize=9.5):
    for p in ax.patches:
        h = p.get_height()
        if h > 0:
            ax.annotate(f'{h*100:.1f}%', (p.get_x() + p.get_width() / 2., h),
                        ha='center', va='center', xytext=(0, 8), textcoords='offset points', 
                        fontsize=fontsize, fontweight='bold')

# 1. Generate 16k vs Paper Baseline Comparison Plot
plt.figure(figsize=(11, 7))
data_16k = []
for cat, p_val, l16_val in zip(categories, paper_f1, local_16k_f1):
    data_16k.append({'Category': cat, 'Setup': 'Paper Baseline (GPT-4o-mini)', 'F1 Score': p_val})
    data_16k.append({'Category': cat, 'Setup': 'Local 16k Window (Gemma-4-MoE)', 'F1 Score': l16_val})
df_16k = pd.DataFrame(data_16k)

ax1 = sns.barplot(
    data=df_16k,
    x='Category',
    y='F1 Score',
    hue='Setup',
    palette=['#1B365D', '#E74C3C'],
    edgecolor='black',
    alpha=0.9
)
plt.title("Clouseau Evaluation: Paper Baseline vs Local 16k Window (3-Run Avg)", fontsize=14, fontweight='bold', pad=15)
plt.xlabel("Evaluation Suite Category", fontsize=12, fontweight='bold')
plt.ylabel("Average F1 Score", fontsize=12, fontweight='bold')
plt.ylim(0, 1.15)
plt.grid(True, axis='y', alpha=0.3)
add_value_labels(ax1, fontsize=10)
plt.tight_layout()
plot_path_16k = out_dir / "paper_vs_16k.png"
plt.savefig(plot_path_16k, dpi=300)
plt.close()
print(f"✓ 16k vs Paper comparison plot generated at: {plot_path_16k}")

# 2. Generate 32k vs Paper Baseline Comparison Plot
plt.figure(figsize=(11, 7))
data_32k = []
for cat, p_val, l32_val in zip(categories, paper_f1, local_32k_f1):
    data_32k.append({'Category': cat, 'Setup': 'Paper Baseline (GPT-4o-mini)', 'F1 Score': p_val})
    data_32k.append({'Category': cat, 'Setup': 'Local 32k Window (Gemma-4-MoE)', 'F1 Score': l32_val})
df_32k = pd.DataFrame(data_32k)

ax2 = sns.barplot(
    data=df_32k,
    x='Category',
    y='F1 Score',
    hue='Setup',
    palette=['#1B365D', '#4A90E2'],
    edgecolor='black',
    alpha=0.9
)
plt.title("Clouseau Evaluation: Paper Baseline vs Local 32k Window (3-Run Avg)", fontsize=14, fontweight='bold', pad=15)
plt.xlabel("Evaluation Suite Category", fontsize=12, fontweight='bold')
plt.ylabel("Average F1 Score", fontsize=12, fontweight='bold')
plt.ylim(0, 1.15)
plt.grid(True, axis='y', alpha=0.3)
add_value_labels(ax2, fontsize=10)
plt.tight_layout()
plot_path_32k = out_dir / "paper_vs_32k.png"
plt.savefig(plot_path_32k, dpi=300)
plt.close()
print(f"✓ 32k vs Paper comparison plot generated at: {plot_path_32k}")

# 3. Generate All 3 Comparisons Plot (Paper vs 16k vs 32k)
plt.figure(figsize=(13, 8))
data_all = []
for cat, p_val, l16_val, l32_val in zip(categories, paper_f1, local_16k_f1, local_32k_f1):
    data_all.append({'Category': cat, 'Setup': 'Paper Baseline (GPT-4o-mini)', 'F1 Score': p_val})
    data_all.append({'Category': cat, 'Setup': 'Local 16k Window (Gemma-4-MoE)', 'F1 Score': l16_val})
    data_all.append({'Category': cat, 'Setup': 'Local 32k Window (Gemma-4-MoE)', 'F1 Score': l32_val})
df_all = pd.DataFrame(data_all)

ax3 = sns.barplot(
    data=df_all,
    x='Category',
    y='F1 Score',
    hue='Setup',
    palette=['#1B365D', '#E74C3C', '#4A90E2'],
    edgecolor='black',
    alpha=0.9
)
plt.title("Clouseau Benchmark: F1 Performance Comparison Across Setup Types", fontsize=15, fontweight='bold', pad=15)
plt.xlabel("Evaluation Suite Category", fontsize=12, fontweight='bold')
plt.ylabel("Average F1 Score", fontsize=12, fontweight='bold')
plt.ylim(0, 1.15)
plt.grid(True, axis='y', alpha=0.3)
add_value_labels(ax3, fontsize=9.5)
plt.tight_layout()
plot_path_all = out_dir / "all_3_comparisons.png"
plt.savefig(plot_path_all, dpi=300)
plt.close()
print(f"✓ All-3 comparisons plot generated at: {plot_path_all}")
