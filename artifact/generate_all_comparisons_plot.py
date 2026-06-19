#!/usr/bin/env python3
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path

# Set style
sns.set_theme(style="whitegrid")
plt.rcParams['figure.figsize'] = (14, 8)
plt.rcParams['font.sans-serif'] = 'DejaVu Sans'

# Data for the 3 setups
categories = ['Single-Host (S)', 'Extended (SE)', 'Keywords (SS)', 'Multi-Host (MI)', 'OpTC (OPT)']

paper_f1 = [0.9979, 0.9979, 0.9980, 0.9737, 0.9420]
local_16k_f1 = [0.4886, 0.7991, 0.8965, 0.7656, 0.5321]
local_32k_f1 = [0.8734, 0.9512, 0.9291, 0.7642, 0.6600]

data = []
for cat, p_val, l16_val, l32_val in zip(categories, paper_f1, local_16k_f1, local_32k_f1):
    data.append({'Category': cat, 'Setup': 'Paper Baseline (GPT-4.o-mini)', 'F1 Score': p_val})
    data.append({'Category': cat, 'Setup': 'Local 16k Window (Gemma-4-MoE)', 'F1 Score': l16_val})
    data.append({'Category': cat, 'Setup': 'Local 32k Window (Gemma-4-MoE)', 'F1 Score': l32_val})

df_comp = pd.DataFrame(data)

# Create Output Folder
out_dir = Path("artifact/results_3x_runs/plots")
out_dir.mkdir(exist_ok=True)

# Plotting
plt.figure(figsize=(13, 8))
ax = sns.barplot(
    data=df_comp, 
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

# Add value labels
for p in ax.patches:
    h = p.get_height()
    if h > 0:
        ax.annotate(f'{h*100:.1f}%', (p.get_x() + p.get_width() / 2., h),
                    ha='center', va='center', xytext=(0, 8), textcoords='offset points', fontsize=9.5, fontweight='bold')

plt.tight_layout()
plot_path = out_dir / "all_3_comparisons.png"
plt.savefig(plot_path, dpi=300)
plt.close()

print(f"✓ All-3 comparison plot generated successfully at: {plot_path}")
