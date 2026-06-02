import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path

# Set style
sns.set_theme(style="whitegrid")
plt.rcParams['figure.figsize'] = (14, 8)
plt.rcParams['font.sans-serif'] = 'DejaVu Sans'

# Load data
csv_path = Path("artifact/results_3x_runs/AGGREGATED_RESULTS_3X.csv")
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

df["type"] = df["test_name"].apply(extract_type)

# Create Output Folder
out_dir = Path("artifact/results_3x_runs/plots")
out_dir.mkdir(exist_ok=True)

color_mapping = {
    "Single-Host": "#3498db", 
    "Extended": "#e74c3c", 
    "Keywords": "#2ecc71",
    "Multi-Host": "#9b59b6",
    "OpTC": "#f1c40f",
    "Other": "#95a5a6"
}

# 1. Plot F1 Score by Test Name (Sorted)
plt.figure(figsize=(12, 11))
df_sorted = df.sort_values("f1", ascending=True)
colors = df_sorted["type"].map(color_mapping)
bars = plt.barh(df_sorted["test_name"], df_sorted["f1"], color=colors, height=0.7, edgecolor='black', alpha=0.8)
plt.xlabel("Average F1 Score (3-Run Avg)", fontsize=12, fontweight='bold')
plt.title("Clouseau Test Performance (Gemma-4-26b-MoE)\nAverage F1 Score by Scenario", fontsize=14, fontweight='bold', pad=15)
plt.xlim(0, 1.1)

# Add value labels
for bar in bars:
    width = bar.get_width()
    plt.text(width + 0.01, bar.get_y() + bar.get_height()/2, f'{width:.3f}', 
             va='center', ha='left', fontsize=9, fontweight='bold')

# Create legend
from matplotlib.patches import Patch
legend_elements = [
    Patch(facecolor='#3498db', edgecolor='black', label='Single-Host (S)'),
    Patch(facecolor='#e74c3c', edgecolor='black', label='Extended (SE)'),
    Patch(facecolor='#2ecc71', edgecolor='black', label='Keywords (SS)'),
    Patch(facecolor='#9b59b6', edgecolor='black', label='Multi-Host (MI)'),
    Patch(facecolor='#f1c40f', edgecolor='black', label='OpTC (OPT)')
]
plt.legend(handles=legend_elements, loc='lower right', fontsize=11)
plt.tight_layout()
plt.savefig(out_dir / "f1_by_test.png", dpi=300)
plt.close()

# 2. Plot Scenario Type Performance
plt.figure(figsize=(10, 6))
type_summary = df.groupby("type")[["precision", "recall", "f1"]].mean().reset_index()
df_melt = pd.melt(type_summary, id_vars="type", value_vars=["precision", "recall", "f1"], 
                  var_name="Metric", value_name="Score")

ax = sns.barplot(data=df_melt, x="type", y="Score", hue="Metric", palette="muted", edgecolor="black", alpha=0.9)
plt.title("Performance Metrics by Scenario Category (3-Run Avg)", fontsize=14, fontweight='bold', pad=15)
plt.xlabel("Scenario Category", fontsize=12, fontweight='bold')
plt.ylabel("Score", fontsize=12, fontweight='bold')
plt.ylim(0, 1.15)

# Add value labels
for p in ax.patches:
    h = p.get_height()
    if h > 0:
        ax.annotate(f'{h:.3f}', (p.get_x() + p.get_width() / 2., h),
                    ha='center', va='center', xytext=(0, 8), textcoords='offset points', fontsize=9, fontweight='bold')

plt.tight_layout()
plt.savefig(out_dir / "performance_by_category.png", dpi=300)
plt.close()

# 3. Plot Durations
plt.figure(figsize=(12, 8))
df_dur_sorted = df.sort_values("avg_duration_sec", ascending=False)
colors_dur = df_dur_sorted["type"].map(color_mapping)
plt.bar(df_dur_sorted["test_name"], df_dur_sorted["avg_duration_sec"] / 60, color=colors_dur, edgecolor='black', alpha=0.8)
plt.title("Average Execution Time by Test Scenario", fontsize=14, fontweight='bold', pad=15)
plt.xlabel("Test Scenario", fontsize=12, fontweight='bold')
plt.ylabel("Average Duration (Minutes)", fontsize=12, fontweight='bold')
plt.xticks(rotation=90, fontsize=9)
plt.legend(handles=legend_elements, loc='upper right', fontsize=11)
plt.tight_layout()
plt.savefig(out_dir / "duration_by_test.png", dpi=300)
plt.close()

# 4. Scatter Plot: Precision vs Recall
plt.figure(figsize=(10, 8))
sns.scatterplot(data=df, x="recall", y="precision", hue="type", size="avg_duration_sec",
                palette=color_mapping,
                sizes=(50, 400), alpha=0.7, edgecolor="black")
plt.title("Precision vs Recall (Size proportional to Duration)", fontsize=14, fontweight='bold', pad=15)
plt.xlabel("Recall", fontsize=12, fontweight='bold')
plt.ylabel("Precision", fontsize=12, fontweight='bold')
plt.xlim(-0.05, 1.05)
plt.ylim(-0.05, 1.05)
plt.grid(True, alpha=0.3)
plt.legend(loc='lower left')
plt.tight_layout()
plt.savefig(out_dir / "precision_vs_recall.png", dpi=300)
plt.close()

print("✓ Visualizations successfully generated in artifact/results_3x_runs/plots/")
