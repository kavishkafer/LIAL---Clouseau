#!/usr/bin/env python3
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path

# Set style
sns.set_theme(style="whitegrid")
plt.rcParams['figure.figsize'] = (12, 7)
plt.rcParams['font.sans-serif'] = 'DejaVu Sans'

# Data for comparison (from the paper Tables 2, 3, and 4)
categories = ['Single-Host (S)', 'Extended (SE)', 'Keywords (SS)', 'Multi-Host (MI)', 'OpTC (OPT)']
paper_f1 = [0.9979, 0.9979, 0.9980, 0.9737, 0.9420]
local_f1 = [0.8734, 0.9512, 0.9291, 0.7642, 0.6600]

data = []
for cat, p_val, l_val in zip(categories, paper_f1, local_f1):
    data.append({'Category': cat, 'Setup': 'Paper Baseline (GPT-4.1-Mini)', 'F1 Score': p_val})
    data.append({'Category': cat, 'Setup': 'Our Local Run (Gemma-4-26b-MoE)', 'F1 Score': l_val})

df_comp = pd.DataFrame(data)

# Create Output Folder
out_dir = Path("artifact/results_3x_runs/plots")
out_dir.mkdir(exist_ok=True)

# Plotting
plt.figure(figsize=(11, 7))
ax = sns.barplot(
    data=df_comp, 
    x='Category', 
    y='F1 Score', 
    hue='Setup', 
    palette=['#1B365D', '#4A90E2'], 
    edgecolor='black', 
    alpha=0.9
)

plt.title("Clouseau Evaluation: Paper Baseline vs Our Local DGX Run (3-Run Avg)", fontsize=14, fontweight='bold', pad=15)
plt.xlabel("Evaluation Suite Category", fontsize=12, fontweight='bold')
plt.ylabel("Average F1 Score", fontsize=12, fontweight='bold')
plt.ylim(0, 1.15)
plt.grid(True, axis='y', alpha=0.3)

# Add value labels
for p in ax.patches:
    h = p.get_height()
    if h > 0:
        ax.annotate(f'{h*100:.1f}%', (p.get_x() + p.get_width() / 2., h),
                    ha='center', va='center', xytext=(0, 8), textcoords='offset points', fontsize=10, fontweight='bold')

plt.tight_layout()
plot_path = out_dir / "paper_vs_local.png"
plt.savefig(plot_path, dpi=300)
plt.close()

print(f"✓ Side-by-side comparison plot generated successfully at: {plot_path}")
