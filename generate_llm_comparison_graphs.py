import numpy as np
import matplotlib.pyplot as plt
import matplotlib as mpl
import seaborn as sns
import os

np.random.seed(42)
os.makedirs("evaluation_graphs", exist_ok=True)

GREEN_DARK   = "#1A5C38"
GREEN_MID    = "#2D7A4F"
GREEN_LIGHT  = "#A8D5B5"
ACCENT_GOLD  = "#F0A500"
ACCENT_RED   = "#C0392B"
ACCENT_BLUE  = "#2471A3"
BACKGROUND   = "#F8FAF9"
GRID_COLOR   = "#D5E8D4"
TEXT_DARK    = "#1C1C1C"
TEXT_LIGHT   = "#555555"
WHITE        = "#FFFFFF"

mpl.rcParams.update({
    "font.family": "DejaVu Sans",
    "axes.facecolor": BACKGROUND,
    "figure.facecolor": BACKGROUND,
    "axes.grid": True,
    "grid.color": GRID_COLOR,
    "grid.linestyle": "--",
    "grid.alpha": 0.7,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.edgecolor": "#CCCCCC",
})

def add_watermark(fig):
    fig.text(0.99, 0.01, "TerraMind © 2025 | Bennett University",
             ha="right", va="bottom", fontsize=7, color="#AAAAAA", style="italic")

systems = ["Vanilla LLM", "BM25 + LLM", "Standard RAG", "TerraMind\nGraph RAG"]
colors   = [ACCENT_RED, ACCENT_BLUE, ACCENT_GOLD, GREEN_DARK]

metrics = ['Response\nCompleteness', 'Factual\nGrounding', 'Hallucination\nAbsence', 'Domain\nRelevance', 'Expert-Rated\nActionability']

data_vanilla = [0.61, 0.29, 0.41, 0.55, 0.48]
data_bm25 = [0.74, 0.53, 0.59, 0.68, 0.62]
data_rag = [0.83, 0.71, 0.74, 0.77, 0.73]
data_terramind = [0.95, 0.93, 0.91, 0.92, 0.89]
all_data = [data_vanilla, data_bm25, data_rag, data_terramind]

# G4 Radar
def plot_g4():
    fig = plt.figure(figsize=(10, 8))
    fig.subplots_adjust(bottom=0.2)
    ax = fig.add_subplot(111, polar=True)
    
    N = len(metrics)
    angles = [n / float(N) * 2 * np.pi for n in range(N)]
    angles += angles[:1]
    
    ax.set_theta_offset(np.pi / 2)
    ax.set_theta_direction(-1)
    
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(metrics, fontsize=10)
    
    ax.set_yticks([0.25, 0.50, 0.75, 1.00])
    ax.set_yticklabels(["0.25", "0.50", "0.75", "1.00"], color=TEXT_LIGHT, size=8)
    ax.set_ylim(0, 1.05)
    
    for i, system in enumerate(systems):
        values = all_data[i].copy()
        values.append(values[0])
        
        lw = 2.5 if i == 3 else 2
        marker = 'o' if i == 3 else None
        
        ax.plot(angles, values, color=colors[i], linewidth=lw, linestyle='solid', label=system.replace("\n", " "), marker=marker)
        ax.fill(angles, values, color=colors[i], alpha=0.15)
        
        if i == 3: # TerraMind
            for j, angle in enumerate(angles[:-1]):
                text_val = f"{values[j]:.2f}"
                ax.text(angle, values[j] + 0.1, text_val, color=GREEN_DARK, fontsize=8, ha='center', va='center', fontweight='bold')
                
    ax.legend(loc='lower right', bbox_to_anchor=(1.35, -0.1))
    
    fig.text(0.5, 0.05, "TerraMind outperforms Vanilla LLM by +34% on Factual Grounding\nand +50% on Hallucination Absence",
             ha="center", va="center", fontsize=10, 
             bbox=dict(facecolor=GREEN_LIGHT, edgecolor=GREEN_DARK, boxstyle="round,pad=0.5", alpha=0.8))
             
    fig.suptitle("LLM Pipeline Comparison — Five-Metric Evaluation Across Systems", fontsize=14, fontweight='bold', y=0.98)
    ax.set_title("TerraMind Graph RAG vs. Vanilla LLM vs. BM25+LLM vs. Standard RAG", fontsize=11, color=TEXT_LIGHT, pad=20)
    
    add_watermark(fig)
    plt.savefig("evaluation_graphs/G4_llm_comparison_five_metric_radar.png", dpi=300, bbox_inches="tight")
    print("✓ Saved: G4_llm_comparison_five_metric_radar.png")
    plt.close()

plot_g4()

# G5 Bar
def plot_g5():
    fig, ax = plt.subplots(figsize=(12, 8))
    
    y = np.arange(len(metrics))
    height = 0.2
    
    for i, system in enumerate(systems):
        values = [row[i] for row in np.array(all_data).T]
        offsets = [-1.5, -0.5, 0.5, 1.5]
        offset = offsets[i] * height
        bars = ax.barh(y - offset, values, height, label=system.replace("\n", " "), color=colors[i])
        
        for j, bar in enumerate(bars):
            val = values[j]
            ax.text(val + 0.01, bar.get_y() + bar.get_height()/2, f"{val:.2f}", 
                    va='center', ha='left', fontsize=9, color=TEXT_DARK)
            if i == 3:
                ax.text(val + 0.06, bar.get_y() + bar.get_height()/2, "★", 
                        va='center', ha='left', fontsize=12, color=ACCENT_GOLD)

    ax.set_yticks(y)
    ax.set_yticklabels(metrics, fontsize=11)
    ax.invert_yaxis()
    
    ax.set_xlim(0, 1.1)
    ax.axvline(0.80, color=ACCENT_RED, linestyle='--', alpha=0.8, zorder=0)
    ax.text(0.81, -0.6, "Production Quality Threshold", color=ACCENT_RED, fontsize=9, va='top', rotation=90)
    
    ax.legend(loc='upper right')
    ax.set_xlabel("Score (0.0 to 1.0)", fontsize=11)
    
    for j in range(len(metrics)):
        diff = all_data[3][j] - all_data[0][j]
        ax.text(1.05, y[j], f"Δ +{diff:.2f}", va='center', ha='left', fontsize=10, 
                fontweight='bold', color=GREEN_DARK)
                
    plt.title("LLM Pipeline Comparison — Metric-wise Performance Across All Systems", 
              fontsize=14, fontweight='bold', pad=20)
              
    add_watermark(fig)
    plt.tight_layout()
    plt.savefig("evaluation_graphs/G5_llm_comparison_grouped_bar_all_metrics.png", dpi=300, bbox_inches="tight")
    print("✓ Saved: G5_llm_comparison_grouped_bar_all_metrics.png")
    plt.close()

plot_g5()

# G6 Scatter
def plot_g6():
    fig, ax = plt.subplots(figsize=(10, 10))
    
    xs = [row[1] for row in all_data] 
    ys = [row[2] for row in all_data] 
    
    for i in range(len(systems)):
        ax.scatter(xs[i], ys[i], s=280, color=colors[i], label=systems[i].replace("\n", " "), zorder=5)
        x_off = 0.02
        y_off = -0.02
        if i == 2: 
            x_off = -0.06
            y_off = 0.03
        elif i == 0: 
            x_off = -0.08
            y_off = -0.03
        ax.text(xs[i] + x_off, ys[i] + y_off, systems[i].replace("\n", " "), fontsize=10, fontweight='bold', color=TEXT_DARK)

    ax.axvline(0.60, color='gray', linestyle='--', alpha=0.4, zorder=1)
    ax.axhline(0.60, color='gray', linestyle='--', alpha=0.4, zorder=1)
    ax.set_xlim(0, 1.05)
    ax.set_ylim(0, 1.05)
    
    ax.text(1.02, 1.02, "Ideal Zone — Grounded & Reliable", color=GREEN_DARK, fontsize=9, style='italic', ha='right', va='top')
    ax.text(0.03, 0.03, "High Risk — Ungrounded & Unreliable", color=ACCENT_RED, fontsize=9, style='italic', ha='left', va='bottom')
    ax.text(0.03, 1.02, "Reliable but Ungrounded", color=TEXT_LIGHT, fontsize=8, ha='left', va='top')
    ax.text(1.02, 0.03, "Grounded but Hallucinates", color=TEXT_LIGHT, fontsize=8, ha='right', va='bottom')
    
    ax.fill_between([0.60, 1.05], [0.60, 0.60], [1.05, 1.05], color=GREEN_LIGHT, alpha=0.12, zorder=0)

    ax.annotate("", xy=(xs[3] - 0.02, ys[3] - 0.02), xytext=(xs[0] + 0.02, ys[0] + 0.02),
                arrowprops=dict(arrowstyle="->", color=ACCENT_GOLD, linewidth=1.5, ls='dashed'))
    
    mid_x, mid_y = (xs[0] + xs[3])/2, (ys[0] + ys[3])/2
    ax.text(mid_x - 0.08, mid_y + 0.05, "RAG + KG + AGRIS pipeline improvement", 
            rotation=36, color=ACCENT_GOLD, fontweight='bold', fontsize=9, 
            bbox=dict(facecolor=BACKGROUND, edgecolor='none', alpha=0.8, pad=1))
            
    ax.plot([0, 1.05], [0, 1.05], color='gray', linestyle='dashed', alpha=0.5, zorder=1)
    ax.text(0.6, 0.58, "Equal Grounding & Reliability", rotation=45, color='gray', fontsize=9, ha='center', va='center')
    
    ax.set_xlabel("Factual Grounding Score", fontsize=11)
    ax.set_ylabel("Hallucination Absence Score", fontsize=11)
    
    plt.suptitle("Factual Grounding vs. Hallucination Absence — LLM System Positioning", fontsize=14, fontweight='bold', y=0.95)
    plt.title("Higher on both axes = more reliable and scientifically traceable output", fontsize=11, color=TEXT_LIGHT, pad=10)
    
    add_watermark(fig)
    plt.savefig("evaluation_graphs/G6_llm_comparison_hallucination_vs_grounding.png", dpi=300, bbox_inches="tight")
    print("✓ Saved: G6_llm_comparison_hallucination_vs_grounding.png")
    plt.close()

plot_g6()

# G7 1x2 panel
def plot_g7():
    fig, axes = plt.subplots(1, 2, figsize=(15, 6))
    
    ax1 = axes[0]
    vals = [43, 61, 74, 79]
    bars = ax1.bar([s.replace("\n", " ") for s in systems], vals, color=colors)
    ax1.set_ylim(0, 100)
    ax1.set_ylabel("% of responses with all 5 mandatory sections")
    ax1.set_title("First-Attempt 5-Section Completeness Rate", fontsize=12, pad=15)
    
    for bar in bars:
        height = bar.get_height()
        ax1.text(bar.get_x() + bar.get_width()/2, height + 2, f"{height}%", ha='center', va='bottom', fontweight='bold')
    
    ax1.axhline(75, color=ACCENT_RED, linestyle='--', alpha=0.8)
    ax1.text(3.4, 77, "Acceptable Threshold", color=ACCENT_RED, fontsize=9, va='bottom', ha='right')
    
    ax2 = axes[1]
    attempts = [1, 2, 3]
    y_vanilla = [43, 54, 61]
    y_bm25 = [61, 73, 79]
    y_rag = [74, 84, 89]
    y_tm = [79, 95, 98]
    ally = [y_vanilla, y_bm25, y_rag, y_tm]
    
    for i in range(len(systems)):
        lw = 2.5 if i == 3 else 2
        marker = 'o' if i == 3 else None
        ax2.plot(attempts, ally[i], color=colors[i], linewidth=lw, marker=marker, label=systems[i].replace("\n", " "))
        
    ax2.fill_between(attempts, y_tm[0], y_tm, color=GREEN_LIGHT, alpha=0.2)

    ax2.set_xticks(attempts)
    ax2.set_xticklabels(["Attempt 1\n(First Try)", "Attempt 2\n(+400 Tokens)", "Attempt 3\n(Fallback Model)"])
    ax2.set_ylim(0, 105)
    ax2.set_ylabel("Cumulative % complete responses")
    ax2.set_title("Cumulative Completeness After Each Retry Attempt", fontsize=12, pad=15)
    
    ax2.text(2, y_tm[1] - 4, "95% — Production Target Met", color=GREEN_DARK, ha='right', fontsize=9, fontweight='bold')
    ax2.text(3, y_tm[2] + 2, "98%", color=GREEN_DARK, ha='center', fontsize=9, fontweight='bold')
    ax2.legend(loc='lower right')
    
    plt.suptitle("TerraMind Graph RAG achieves 98% complete response rate after retry — highest across all systems", fontsize=14, fontweight='bold', y=1.05)
    
    add_watermark(fig)
    plt.tight_layout()
    plt.savefig("evaluation_graphs/G7_llm_comparison_response_completeness_retry.png", dpi=300, bbox_inches="tight")
    print("✓ Saved: G7_llm_comparison_response_completeness_retry.png")
    plt.close()

plot_g7()

print("\n✅ All 4 LLM comparison graphs saved to evaluation_graphs/")
print("Total evaluation graphs in folder: 29")
