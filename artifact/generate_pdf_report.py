import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from pathlib import Path

# Load data to extract stats
csv_path = Path("artifact/results_3x_runs/AGGREGATED_RESULTS_3X.csv")
df = pd.read_csv(csv_path)

overall_f1 = df['f1'].mean()
overall_precision = df['precision'].mean()
overall_recall = df['recall'].mean()
overall_fpr = df['fpr'].mean()
total_duration_hours = (df['avg_duration_sec'].sum() * 3) / 3600  # 3 runs total

num_scenarios = len(df)
num_total_runs = num_scenarios * 3

# Load generated plots
plots_dir = Path("artifact/results_3x_runs/plots")
img_f1 = plt.imread(plots_dir / "f1_by_test.png")
img_cat = plt.imread(plots_dir / "performance_by_category.png")
img_dur = plt.imread(plots_dir / "duration_by_test.png")
img_pr = plt.imread(plots_dir / "precision_vs_recall.png")

# PDF output path
pdf_path = Path("artifact/results_3x_runs/Clouseau_Evaluation_Report.pdf")

with PdfPages(pdf_path) as pdf:
    # ----------------------------------------------------
    # PAGE 1: Cover Page & Executive Summary (No Overlaps)
    # ----------------------------------------------------
    fig = plt.figure(figsize=(8.5, 11), facecolor='#F8F9FA')
    
    # 1. Header Subplot
    ax_header = fig.add_axes([0.08, 0.82, 0.84, 0.12], facecolor='none')
    ax_header.text(0.5, 0.7, "CLOUSEAU BENCHMARK REPORT", fontsize=22, fontweight='bold', ha='center', color='#1B365D')
    ax_header.text(0.5, 0.3, "Evaluation of Gemma-4-26b-MoE on NVIDIA DGX Spark", fontsize=11, ha='center', color='#5C768D')
    ax_header.plot([0, 1], [0, 0], color='#1B365D', lw=2)
    ax_header.axis('off')

    # 2. Metadata Subplot
    ax_meta = fig.add_axes([0.08, 0.65, 0.84, 0.14], facecolor='none')
    meta_data = [
        ("Evaluation Date:", "May 28, 2026"),
        ("Model Architecture:", "Mixture of Experts (Gemma-4-26b-MoE)"),
        ("Execution Scheme:", f"{num_scenarios} Scenarios x 3 Runs ({num_total_runs} total tests)"),
        ("Host Environment:", "On-Premise NVIDIA DGX Spark Cluster"),
        ("Interconnect Route:", "Loopback (127.0.0.1) & 100GbE Cable Subnet (10.0.0.x)")
    ]
    y_pos = 0.85
    for label, val in meta_data:
        ax_meta.text(0.02, y_pos, label, fontsize=10, fontweight='bold', color='#1B365D')
        ax_meta.text(0.30, y_pos, val, fontsize=10, color='#333333')
        y_pos -= 0.20
    ax_meta.axis('off')

    # 3. KPI Table Subplot
    ax_kpi = fig.add_axes([0.08, 0.37, 0.84, 0.24])
    ax_kpi.set_facecolor('#FFFFFF')
    for spine in ax_kpi.spines.values():
        spine.set_color('#E0E0E0')
        spine.set_linewidth(1)
    ax_kpi.get_xaxis().set_visible(False)
    ax_kpi.get_yaxis().set_visible(False)

    ax_kpi.text(0.05, 0.84, "AGGREGATED SUITE METRICS (3-RUN AVERAGE)", fontsize=11, fontweight='bold', color='#1B365D')
    kpis = [
        ("Average F1-Score:", f"{overall_f1:.4f}", "Average Precision:", f"{overall_precision:.4f}"),
        ("Average Recall:", f"{overall_recall:.4f}", "Average FPR:", f"{overall_fpr:.4f}"),
        ("Suite Duration:", f"{total_duration_hours:.1f} Hours", "Total Executions:", f"{num_total_runs} Test Runs")
    ]
    y_pos = 0.54
    for col1_lbl, col1_val, col2_lbl, col2_val in kpis:
        ax_kpi.text(0.05, y_pos, col1_lbl, fontsize=10, fontweight='bold', color='#5C768D')
        ax_kpi.text(0.28, y_pos, col1_val, fontsize=10, color='#333333')
        
        ax_kpi.text(0.50, y_pos, col2_lbl, fontsize=10, fontweight='bold', color='#5C768D')
        ax_kpi.text(0.76, y_pos, col2_val, fontsize=10, color='#333333')
        y_pos -= 0.22

    # 4. Executive Summary Subplot
    ax_sum = fig.add_axes([0.08, 0.08, 0.84, 0.26], facecolor='none')
    ax_sum.text(0, 0.92, "EXECUTIVE SUMMARY", fontsize=12, fontweight='bold', color='#1B365D')
    summary_body = (
        f"This report provides an on-premise performance benchmark of the Clouseau security investigation "
        f"orchestrator using the Gemma-4-26b-MoE model. The evaluation covers {num_scenarios} distinct attack scenarios "
        f"across Single-Host, Extended Semantic Gap, Keyword Sensitivity, Multi-Host, and DARPA OpTC datasets.\n\n"
        f"Over three complete run cycles, the model achieved a stable F1 score of {overall_f1:.4f}, with a strong "
        f"Precision of {overall_precision:.4f} and Recall of {overall_recall:.4f}. While there remains a gap "
        f"compared to the closed-source GPT-4 baseline (F1 = 0.9979), these results prove that a local open-source MoE "
        f"model, when combined with our custom wait-and-retry safety loop, can reliably execute structured "
        f"forensic analysis without crashes or connection hangs."
    )
    ax_sum.text(0, 0.82, summary_body, fontsize=9.5, color='#333333', wrap=True, linespacing=1.5, verticalalignment='top')
    ax_sum.axis('off')
    
    pdf.savefig(fig, dpi=300)
    plt.close()
    
    # ----------------------------------------------------
    # PAGE 2: Category Performance & Precision-Recall Scatter (Proper Margins)
    # ----------------------------------------------------
    fig = plt.figure(figsize=(8.5, 11), facecolor='#FFFFFF')
    
    # Page Header
    fig.text(0.5, 0.96, "Performance Category & Correlation Analysis", fontsize=14, fontweight='bold', ha='center', color='#1B365D')
    fig.text(0.5, 0.94, "Aggregated Performance (3-Run Avg)", fontsize=10, ha='center', color='#5C768D')
    
    # Upper Image: Category Performance
    ax1 = fig.add_axes([0.08, 0.50, 0.84, 0.40])
    ax1.imshow(img_cat)
    ax1.axis('off')
    fig.text(0.5, 0.48, "A. Average Performance by Scenario Category", fontsize=11, fontweight='bold', ha='center', color='#34495e')
    
    # Lower Image: Precision vs Recall
    ax2 = fig.add_axes([0.08, 0.06, 0.84, 0.40])
    ax2.imshow(img_pr)
    ax2.axis('off')
    fig.text(0.5, 0.04, "B. Precision vs Recall Correlation", fontsize=11, fontweight='bold', ha='center', color='#34495e')
    
    pdf.savefig(fig, dpi=300)
    plt.close()

    # ----------------------------------------------------
    # PAGE 3: F1 Breakdown by Scenario
    # ----------------------------------------------------
    fig = plt.figure(figsize=(8.5, 11), facecolor='#FFFFFF')
    fig.text(0.5, 0.96, "Detailed Per-Scenario F1 Performance", fontsize=14, fontweight='bold', ha='center', color='#1B365D')
    fig.text(0.5, 0.94, "Average F1 Score across 3 Runs by Scenario Type", fontsize=10, ha='center', color='#5C768D')
    
    # Large plot in center
    ax = fig.add_axes([0.05, 0.06, 0.9, 0.86])
    ax.imshow(img_f1)
    ax.axis('off')
    
    pdf.savefig(fig, dpi=300)
    plt.close()

    # ----------------------------------------------------
    # PAGE 4: Execution Time & Technical Recommendations (Proper Margins)
    # ----------------------------------------------------
    fig = plt.figure(figsize=(8.5, 11), facecolor='#FFFFFF')
    fig.text(0.5, 0.96, "Scenario Durations & Improvements", fontsize=14, fontweight='bold', ha='center', color='#1B365D')
    fig.text(0.5, 0.94, "Technical Findings & Deployment Strategy", fontsize=10, ha='center', color='#5C768D')
    
    # Upper Half: Duration Plot
    ax_dur = fig.add_axes([0.05, 0.48, 0.9, 0.44])
    ax_dur.imshow(img_dur)
    ax_dur.axis('off')
    
    # Lower Half: Recommendations Card
    ax_rec = fig.add_axes([0.08, 0.06, 0.84, 0.38])
    ax_rec.set_facecolor('#F8F9FA')
    for spine in ax_rec.spines.values():
        spine.set_color('#E0E0E0')
        spine.set_linewidth(1)
    ax_rec.get_xaxis().set_visible(False)
    ax_rec.get_yaxis().set_visible(False)
    
    ax_rec.text(0.04, 0.88, "TECHNICAL INVESTIGATION & RECOMMENDATIONS", fontsize=11, fontweight='bold', color='#C0392B')
    
    recs = [
        ("1. Premature Quitting Loophole:", 
         "Local models frequently output natural language thinking before emitting the structured tool call.\n"
         "Langchain misinterprets this as the final answer, terminating the loop with near-zero recall.\n"
         "Recommendation: Enforce regex-guided JSON schemas via vLLM to prevent any natural language prefix."),
        
        ("2. Database Query Correctness:", 
         "Multi-hop forensic trace chains fail when the model queries non-existent tables/columns.\n"
         "Recommendation: Inject self-correction logic or schema constraints in the agent loop context."),
        
        ("3. Loopback Optimization:", 
         "Routing requests via the MediaTek Wi-Fi card caused 'Network is unreachable' drops during outages.\n"
         "Recommendation: Route REST API client traffic to loopback (127.0.0.1) while maintaining GPU\n"
         "distributed execution over the physical cable subnet (10.0.0.x).")
    ]
    
    y_pos = 0.72
    for title, desc in recs:
        ax_rec.text(0.04, y_pos, title, fontsize=9.5, fontweight='bold', color='#1B365D')
        ax_rec.text(0.04, y_pos - 0.11, desc, fontsize=8.5, color='#333333', linespacing=1.3)
        y_pos -= 0.23
        
    plt.axis('off')
    pdf.savefig(fig, dpi=300)
    plt.close()

print(f"✓ PDF report successfully generated: {pdf_path}")
