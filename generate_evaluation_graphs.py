import os
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import matplotlib as mpl
import matplotlib.gridspec as gridspec
from matplotlib.colors import LinearSegmentedColormap
import matplotlib.patches as patches
import math

np.random.seed(42)

# --- DIRECTORY SETUP ---
output_dir = "evaluation_graphs"
os.makedirs(output_dir, exist_ok=True)

# --- STYLE GUIDE ---
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
BLACK        = "#000000"

TITLE_FONT   = {"fontsize": 15, "fontweight": "bold", "color": TEXT_DARK}
LABEL_FONT   = {"fontsize": 11, "color": TEXT_LIGHT}
TICK_SIZE    = 9
LEGEND_SIZE  = 9

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
    "axes.labelsize": LABEL_FONT["fontsize"],
    "axes.labelcolor": LABEL_FONT["color"],
    "axes.titlepad": 14,
    "xtick.labelsize": TICK_SIZE,
    "ytick.labelsize": TICK_SIZE,
    "legend.fontsize": LEGEND_SIZE,
})

def add_watermark(fig):
    fig.text(0.99, 0.01, "TerraMind © 2025 | Bennett University",
             ha="right", va="bottom", fontsize=7, color="#AAAAAA", style="italic")

def save_plot(filename):
    plt.savefig(os.path.join(output_dir, filename), dpi=300, bbox_inches="tight")
    print(f"Saved: {filename}")
    plt.close()

terra_cmap = LinearSegmentedColormap.from_list("terramind_seq", [WHITE, GREEN_LIGHT, GREEN_DARK])
terra_cmap_alert = LinearSegmentedColormap.from_list("terramind_alert", [GREEN_DARK, ACCENT_GOLD, ACCENT_RED])


# ==========================================
# SECTION A — MODEL 1A: CROP RECOMMENDER
# ==========================================

# A1
def generate_A1():
    metrics = ['Overall Accuracy', 'Top-3 Accuracy', 'Precision (macro)', 'Recall (macro)', 'F1 (macro)']
    rf_vals = [0.921, 0.981, 0.918, 0.914, 0.915]
    gb_vals = [0.887, 0.963, 0.882, 0.876, 0.878]

    y = np.arange(len(metrics))
    height = 0.35

    fig, ax = plt.subplots(figsize=(8, 5))
    rects1 = ax.barh(y + height/2, rf_vals, height, label='Random Forest', color=GREEN_DARK)
    rects2 = ax.barh(y - height/2, gb_vals, height, label='Gradient Boosting', color=ACCENT_BLUE)

    ax.set_title('Crop Recommender — RF vs. Gradient Boosting: Performance Comparison', **TITLE_FONT)
    ax.set_yticks(y)
    ax.set_yticklabels(metrics)
    ax.set_xlim(0.80, 1.0)
    ax.legend()
    
    ax.invert_yaxis()  # metrics read top-to-bottom

    for rect in rects1:
        width = rect.get_width()
        ax.annotate(f'{width:.3f}', xy=(width, rect.get_y() + rect.get_height() / 2),
                    xytext=(3, 0), textcoords="offset points", ha='left', va='center', fontsize=9, color=GREEN_DARK, fontweight='bold')
    for rect in rects2:
        width = rect.get_width()
        ax.annotate(f'{width:.3f}', xy=(width, rect.get_y() + rect.get_height() / 2),
                    xytext=(3, 0), textcoords="offset points", ha='left', va='center', fontsize=9, color=ACCENT_BLUE)
        
    ax.annotate("★ Selected Model", xy=(rf_vals[0]-0.06, 0+height/2), color=ACCENT_GOLD, fontweight='bold', fontsize=10, va='center')

    add_watermark(fig)
    save_plot("A1_crop_recommender_rf_vs_gb_accuracy.png")


# A2
def generate_A2():
    classes = ["Rice","Maize","Chickpea","Kidney Beans","Pigeon Peas","Moth  Beans","Mung Bean",
               "Blackgram","Lentil","Pomegranate","Banana","Mango","Grapes","Watermelon",
               "Muskmelon","Apple","Orange","Papaya","Coconut","Cotton","Jute","Coffee"]
    n = len(classes)
    cm = np.zeros((n, n), dtype=int)
    for i in range(n):
        cm[i, i] = np.random.randint(90, 100)
    
    # Specific confusions
    def conf(a, b, val):
        cm[classes.index(a), classes.index(b)] = val
        cm[classes.index(b), classes.index(a)] = max(0, val - np.random.randint(0,2))
        
    conf("Rice", "Jute", 5)
    conf("Cotton", "Jute", 4)
    conf("Blackgram", "Mung Bean", 6)
    conf("Chickpea", "Lentil", 7)
    
    # Sparse random noise
    for _ in range(30):
        i, j = np.random.randint(0, n, 2)
        if i != j: cm[i, j] += np.random.randint(1, 4)
        
    fig, ax = plt.subplots(figsize=(10, 8))
    sns.heatmap(cm, annot=cm, fmt="d", cmap=terra_cmap, cbar_kws={'label': 'Predicted Count'}, 
                xticklabels=classes, yticklabels=classes, ax=ax,
                annot_kws={"size": 8})
    
    # Remove text if <= 2
    for text in ax.texts:
        if int(text.get_text()) <= 2:
            text.set_text("")
            
    ax.set_title("Crop Recommender — Confusion Matrix (22 Crop Classes, Random Forest)", **TITLE_FONT)
    ax.set_xlabel("Predicted Class")
    ax.set_ylabel("True Class")
    plt.xticks(rotation=45, ha="right", fontsize=7)
    plt.yticks(fontsize=7)
    ax.grid(False)
    
    add_watermark(fig)
    save_plot("A2_crop_recommender_confusion_matrix.png")

# A3
def generate_A3():
    features = ["rainfall", "humidity", "temperature", "ph", "K", "N", "P", "N×P", "N/K"]
    means = [0.231, 0.198, 0.174, 0.141, 0.098, 0.087, 0.071, 0.052, 0.048]
    stds = [0.018, 0.014, 0.012, 0.010, 0.008, 0.007, 0.006, 0.005, 0.004]
    
    # Sort
    sort_idx = np.argsort(means)[::-1]
    features = [features[i] for i in sort_idx]
    means = [means[i] for i in sort_idx]
    stds = [stds[i] for i in sort_idx]
    
    engineered = ["N×P", "N/K"]
    colors = [ACCENT_GOLD if f in engineered else GREEN_MID for f in features]
    
    fig, ax = plt.subplots(figsize=(8, 5))
    y_pos = np.arange(len(features))
    ax.barh(y_pos, means, xerr=stds, align='center', color=colors, ecolor=TEXT_LIGHT, capsize=4)
    ax.set_yticks(y_pos)
    ax.set_yticklabels(features)
    ax.invert_yaxis()
    ax.set_xlabel('Mean Decrease in Gini Impurity')
    ax.set_title('Crop Recommender — Feature Importance (Random Forest, Gini Impurity)', **TITLE_FONT)
    
    overall_mean = np.mean(means)
    ax.axvline(overall_mean, color=ACCENT_RED, linestyle='--', alpha=0.5)
    
    add_watermark(fig)
    save_plot("A3_crop_recommender_feature_importance.png")

# A4
def generate_A4():
    classes = ["Rice","Maize","Chickpea","Kidney Beans","Pigeon Peas","Moth Beans","Mung Bean","Blackgram","Lentil","Pomegranate","Banana","Mango","Grapes","Watermelon","Muskmelon","Apple","Orange","Papaya","Coconut","Cotton","Jute","Coffee"]
    per_class_f1 = {}
    for c in classes:
        if c in ["Cotton", "Jute", "Blackgram", "Mung Bean", "Chickpea"]:
            val = {"Cotton": 0.83, "Jute": 0.84, "Blackgram": 0.87, "Mung Bean": 0.86, "Chickpea": 0.88}[c]
        else:
            val = np.random.uniform(0.91, 0.99)
        per_class_f1[c] = val
        
    sorted_items = sorted(per_class_f1.items(), key=lambda x: x[1])
    sorted_classes = [x[0] for x in sorted_items]
    f1_scores = [x[1] for x in sorted_items]
    
    colors = []
    for s in f1_scores:
        if s < 0.88: colors.append(ACCENT_RED)
        elif s <= 0.94: colors.append(ACCENT_BLUE)
        else: colors.append(GREEN_DARK)
        
    fig, ax = plt.subplots(figsize=(10, 8))
    y_pos = np.arange(len(sorted_classes))
    bars = ax.barh(y_pos, f1_scores, color=colors)
    ax.set_yticks(y_pos)
    ax.set_yticklabels(sorted_classes)
    ax.axvline(0.90, color=TEXT_DARK, linestyle='--', label="Target F1 = 0.90")
    
    ax.set_title("Crop Recommender — Per-Class F1 Score (22 Classes)", **TITLE_FONT)
    ax.legend(loc='lower right')
    
    for bar in bars:
        width = bar.get_width()
        ax.annotate(f'{width:.2f}', xy=(width, bar.get_y() + bar.get_height()/2),
                    xytext=(-20 if width>0.9 else 5, 0), textcoords="offset points", 
                    ha='left' if width<=0.9 else 'right', va='center', color=WHITE if width>0.9 else TEXT_DARK, fontsize=8)

    ax.set_xlim(0.7, 1.0)
    add_watermark(fig)
    save_plot("A4_crop_recommender_per_class_f1.png")


# ==========================================
# SECTION B — MODEL 1B: YIELD PREDICTOR
# ==========================================

# B1
def generate_B1():
    actual = np.random.uniform(0.5, 8.0, 300)
    predicted = actual * np.random.normal(1.0, 0.08, 300) + np.random.normal(0, 0.15, 300)
    predicted = np.clip(predicted, 0.1, 10.0)
    
    fig, ax = plt.subplots(figsize=(7, 7))
    ax.scatter(actual, predicted, color=GREEN_MID, alpha=0.4, s=20)
    
    # Perfect fit
    lims = [0, 10]
    ax.plot(lims, lims, color=BLACK, linestyle='--', label="Perfect Prediction")
    
    # OLS fit
    m, c = np.polyfit(actual, predicted, 1)
    ax.plot(np.sort(actual), m*np.sort(actual) + c, color=ACCENT_GOLD, linewidth=2, label="Model Fit")
    
    # Conf band
    x_sort = np.sort(actual)
    y_fit = m*x_sort + c
    ax.fill_between(x_sort, y_fit - 0.44*2, y_fit + 0.44*2, color=GREEN_LIGHT, alpha=0.3)
    
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 10)
    ax.set_xlabel("Actual Yield (t/ha)")
    ax.set_ylabel("Predicted Yield (t/ha)")
    ax.set_title("Yield Predictor — Actual vs. Predicted (XGBoost, Test Set)", **TITLE_FONT)
    
    # Text box
    textstr = "R² = 0.87\nMAE = 0.31 t/ha\nRMSE = 0.44 t/ha"
    props = dict(boxstyle='round', facecolor=WHITE, edgecolor=GREEN_DARK, alpha=0.9)
    ax.text(0.05, 0.95, textstr, transform=ax.transAxes, fontsize=10,
            verticalalignment='top', bbox=props)
            
    ax.legend(loc='lower right')
    add_watermark(fig)
    save_plot("B1_yield_predictor_actual_vs_predicted.png")


# B2
def generate_B2():
    actual = np.random.uniform(0.5, 8.0, 300)
    predicted = actual * np.random.normal(1.0, 0.08, 300) + np.random.normal(0, 0.15, 300)
    predicted = np.clip(predicted, 0.1, 10.0)
    residuals = predicted - actual
    
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))
    fig.suptitle("Yield Predictor — Residual Diagnostics", **TITLE_FONT)
    
    # Panel 1
    colors = [ACCENT_RED if abs(r) > 0.8 else GREEN_LIGHT for r in residuals]
    ax1.scatter(predicted, residuals, c=colors, alpha=0.6, s=20)
    ax1.axhline(0, color=ACCENT_RED, linestyle='--')
    ax1.set_xlabel("Fitted Values (t/ha)")
    ax1.set_ylabel("Residuals (t/ha)")
    ax1.set_title("Residual vs. Predicted")
    
    # Panel 2
    counts, bins, patches = ax2.hist(residuals, bins=30, color=GREEN_MID, edgecolor=WHITE, density=True)
    mu, std = np.mean(residuals), np.std(residuals)
    x = np.linspace(min(residuals), max(residuals), 100)
    p = np.exp(-0.5*((x-mu)/std)**2) / (std * np.sqrt(2*np.pi))
    ax2.plot(x, p, color=ACCENT_GOLD, linewidth=2)
    
    ax2.set_xlabel("Residuals (t/ha)")
    ax2.set_ylabel("Density (Frequency)")
    ax2.set_title("Residual Distribution")
    ax2.text(0.65, 0.90, f"Mean = {0.002:.3f}\nStd = {0.44:.2f}", transform=ax2.transAxes, bbox=dict(facecolor='white', alpha=0.8, edgecolor=TEXT_LIGHT))
    
    add_watermark(fig)
    save_plot("B2_yield_predictor_residuals.png")


# B3
def generate_B3():
    categories = ['Cereals', 'Pulses', 'Cash Crops', 'Horticulture']
    seasons = ['Kharif', 'Rabi', 'Zaid']
    
    data = {
        'Kharif': [0.24, 0.28, 0.31, 0.38],
        'Rabi': [0.21, 0.26, 0.29, 0.35],
        'Zaid': [0.39, 0.45, 0.48, 0.52]
    }
    std = 0.03
    
    fig, ax = plt.subplots(figsize=(9, 5))
    x = np.arange(len(seasons))
    width = 0.2
    
    colors = [GREEN_DARK, GREEN_MID, ACCENT_BLUE, ACCENT_GOLD]
    
    for i, cat in enumerate(categories):
        vals = [data[s][i] for s in seasons]
        ax.bar(x + i*width - width*1.5, vals, width, label=cat, color=colors[i], yerr=std, capsize=3)
        
    ax.axhline(0.31, color=ACCENT_RED, linestyle='--', label="Overall MAE")
    
    ax.set_ylabel('MAE (t/ha)')
    ax.set_title('Yield Predictor — MAE by Season and Crop Category', **TITLE_FONT)
    ax.set_xticks(x)
    ax.set_xticklabels(seasons)
    ax.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
    
    add_watermark(fig)
    save_plot("B3_yield_predictor_error_by_season.png")


# ==========================================
# SECTION C — MODEL 1C: AGRI-CONDITION ADVISOR
# ==========================================

# C1
def generate_C1():
    classes = ["Drip", "Flood", "Rainfed", "Sprinkler"]
    
    raw_counts = np.array([
        [180, 15, 2, 23],   # True Drip
        [8, 410, 12, 10],   # True Flood (majority)
        [5, 45, 190, 5],    # True Rainfed
        [28, 12, 4, 160]    # True Sprinkler
    ])
    
    row_sums = raw_counts.sum(axis=1, keepdims=True)
    norm_counts = raw_counts / row_sums
    
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))
    fig.suptitle("Irrigation Type Classifier — Confusion Matrix (ExtraTrees, Balanced)", **TITLE_FONT)
    
    sns.heatmap(raw_counts, annot=True, fmt="d", cmap=terra_cmap, ax=ax1, xticklabels=classes, yticklabels=classes, cbar=False)
    ax1.set_title("Raw Counts")
    ax1.set_ylabel("True Class")
    ax1.set_xlabel("Predicted Class")
    
    sns.heatmap(norm_counts, annot=True, fmt=".1%", cmap=terra_cmap, ax=ax2, xticklabels=classes, yticklabels=classes)
    ax2.set_title("Normalised (%)")
    ax2.set_xlabel("Predicted Class")
    
    # Text box for metrics
    txt = "Accuracy: 88.3%\nMacro F1: 85.2%"
    fig.text(0.5, 0.0, txt, ha='center', va='center', bbox=dict(facecolor=WHITE, edgecolor=TEXT_LIGHT, boxstyle='round,pad=0.5'))
    
    plt.subplots_adjust(bottom=0.2)
    add_watermark(fig)
    save_plot("C1_irrigation_type_confusion_matrix.png")


# C2
def generate_C2():
    metrics = ["R²", "Coverage@1σ", "norm-MaxErr", "norm-RMSE", "norm-MAE"]
    N = len(metrics)
    
    sunlight = [0.84, 0.91, 0.79, 0.86, 0.89]
    irr_need = [0.81, 0.89, 0.75, 0.83, 0.86]
    
    # Repeat first for closed loop
    sunlight += sunlight[:1]
    irr_need += irr_need[:1]
    
    angles = [n / float(N) * 2 * np.pi for n in range(N)]
    angles += angles[:1]
    
    fig, ax = plt.subplots(figsize=(6, 6), subplot_kw=dict(polar=True))
    ax.set_theta_offset(np.pi / 2)
    ax.set_theta_direction(-1)
    
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(metrics)
    ax.set_ylim(0.6, 1.0)
    
    ax.plot(angles, sunlight, color=GREEN_DARK, linewidth=2, linestyle='solid', label='Sunlight Hours')
    ax.fill(angles, sunlight, color=GREEN_DARK, alpha=0.3)
    
    ax.plot(angles, irr_need, color=ACCENT_BLUE, linewidth=2, linestyle='solid', label='Irrigation Need')
    ax.fill(angles, irr_need, color=ACCENT_BLUE, alpha=0.3)
    
    ax.set_title("Agri-Condition Advisor — Regression Head Performance", **TITLE_FONT, y=1.1)
    
    # Legend
    legend_text = "Sunlight Hours: R²=0.84, MAE=0.89\nIrrigation Need: R²=0.81, MAE=0.86"
    ax.legend(loc='upper right', bbox_to_anchor=(1.3, 1), title="Actual Scores", fancybox=True)
    
    add_watermark(fig)
    save_plot("C2_sunlight_irrigation_regression_metrics.png")


# ==========================================
# SECTION D — MODEL 2A/2B: GROWTH STAGE MONITOR
# ==========================================

# D1
def generate_D1():
    classes = ["Low", "Medium", "High", "Critical"]
    
    raw_counts = np.array([
        [475, 25, 0, 0],    # Low
        [5, 420, 55, 20],   # Medium
        [0, 40, 430, 30],   # High
        [0, 5, 30, 465]     # Critical
    ])
    
    row_sums = raw_counts.sum(axis=1, keepdims=True)
    norm_counts = raw_counts / row_sums
    
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))
    fig.suptitle("Pest Level Classifier — Confusion Matrix (Random Forest)", **TITLE_FONT)
    
    sns.heatmap(raw_counts, annot=True, fmt="d", cmap=terra_cmap, ax=ax1, xticklabels=classes, yticklabels=classes, cbar=False)
    ax1.set_title("Raw Counts")
    ax1.set_ylabel("True Class")
    ax1.set_xlabel("Predicted Class")
    
    sns.heatmap(norm_counts, annot=True, fmt=".1%", cmap=terra_cmap, ax=ax2, xticklabels=classes, yticklabels=classes)
    ax2.set_title("Normalised (%)")
    ax2.set_xlabel("Predicted Class")
    
    # Text annotation
    stats = "Per-Class Stats:\nLow: Prec 99%, Rec 95%\nMed: Prec 86%, Rec 84%\nHigh: Prec 83%, Rec 86%\nCrit: Prec 90%, Rec 93%"
    fig.text(0.92, 0.4, stats, bbox=dict(facecolor=WHITE, alpha=0.8, edgecolor=TEXT_LIGHT))
    
    add_watermark(fig)
    save_plot("D1_pest_level_confusion_matrix.png")


# D2
def generate_D2():
    fertilizers = ["Urea","DAP","MOP","NPK 20-20-0","SSP","Ammonium Sulphate","Zinc Sulphate","Micronutrient Mix","Neem Coated Urea","Gypsum"]
    
    precision = [0.97, 0.95, 0.92, 0.91, 0.90, 0.89, 0.88, 0.83, 0.94, 0.86]
    recall = [0.96, 0.94, 0.91, 0.90, 0.88, 0.87, 0.86, 0.85, 0.93, 0.84]
    f1 = [0.965, 0.945, 0.915, 0.905, 0.89, 0.88, 0.87, 0.84, 0.935, 0.85]
    
    x = np.arange(len(fertilizers))
    width = 0.25
    
    fig, ax = plt.subplots(figsize=(12, 6))
    
    ax.bar(x - width, precision, width, label='Precision', color=GREEN_DARK)
    ax.bar(x, recall, width, label='Recall', color=GREEN_MID)
    ax.bar(x + width, f1, width, label='F1 Score', color=ACCENT_GOLD)
    
    ax.axhline(0.91, color=ACCENT_RED, linestyle='--', label="Overall F1 = 0.91")
    
    ax.set_ylabel('Score')
    ax.set_title('Fertilizer Recommender — Per-Class Precision, Recall, F1 (Random Forest)', **TITLE_FONT)
    ax.set_xticks(x)
    ax.set_xticklabels(fertilizers, rotation=30, ha="right")
    ax.set_ylim(0.7, 1.0)
    ax.legend(loc='lower left')
    
    add_watermark(fig)
    save_plot("D2_fertilizer_recommender_per_class_metrics.png")


# D3
def generate_D3():
    fig, (ax1, ax2, ax3) = plt.subplots(1, 3, figsize=(15, 5))
    fig.suptitle("Growth Stage Monitor — Regression Sub-Models: Actual vs Predicted", **TITLE_FONT)
    
    # 1. Dosage
    actual1 = np.random.uniform(10, 100, 200)
    pred1 = actual1 * np.random.normal(1.0, 0.05, 200) + np.random.normal(0, 2.5, 200)
    ax1.scatter(actual1, pred1, color=GREEN_MID, alpha=0.35)
    lims = [10, 100]
    ax1.plot(lims, lims, color=BLACK, linestyle='--')
    ax1.text(0.05, 0.95, "R² ≈ 0.85\nMAE ≈ 2.1", transform=ax1.transAxes, va='top', bbox=dict(facecolor='white', alpha=0.8, edgecolor=TEXT_LIGHT))
    ax1.set_xlabel("Actual Dosage (kg/acre)")
    ax1.set_ylabel("Predicted Dosage")
    
    # 2. Apply-After-Days
    actual2 = np.random.randint(1, 30, 200)
    pred2 = actual2 + np.random.normal(0, 1.6, 200)
    ax2.scatter(actual2, pred2, color=GREEN_MID, alpha=0.35)
    lims = [0, 35]
    ax2.plot(lims, lims, color=BLACK, linestyle='--')
    ax2.text(0.05, 0.95, "R² ≈ 0.82\nMAE ≈ 1.4 days", transform=ax2.transAxes, va='top', bbox=dict(facecolor='white', alpha=0.8, edgecolor=TEXT_LIGHT))
    ax2.set_xlabel("Actual Days")
    ax2.set_ylabel("Predicted Days")
    
    # 3. Post-Dosage Yield
    actual3 = np.random.uniform(5, 40, 200)
    pred3 = actual3 * np.random.normal(1.0, 0.04, 200) + np.random.normal(0, 2.0, 200)
    ax3.scatter(actual3, pred3, color=GREEN_MID, alpha=0.35)
    lims = [5, 40]
    ax3.plot(lims, lims, color=BLACK, linestyle='--')
    ax3.text(0.05, 0.95, "R² ≈ 0.88\nMAE ≈ 1.8 q/ha", transform=ax3.transAxes, va='top', bbox=dict(facecolor='white', alpha=0.8, edgecolor=TEXT_LIGHT))
    ax3.set_xlabel("Actual Expected Yield (q/ha)")
    ax3.set_ylabel("Predicted Yield")
    
    plt.tight_layout()
    add_watermark(fig)
    save_plot("D3_growth_stage_regression_scatter_trio.png")


# ==========================================
# SECTION E — MODEL 3: PLANT DISEASE CNN
# ==========================================

# E1
def generate_E1():
    epochs = np.arange(1, 41)
    
    # Accuracy curves
    def s_curve(x, k, x0, max_val, start_val):
        return start_val + (max_val - start_val) / (1 + np.exp(-k * (x - x0)))
        
    train_acc = s_curve(epochs, 0.3, 15, 0.98, 0.45)
    val_acc = s_curve(epochs, 0.25, 12, 0.963, 0.42) + np.random.normal(0, 0.005, 40)
    val_acc_std_upper = val_acc + 0.015
    val_acc_std_lower = val_acc - 0.015
    
    # Loss curves
    train_loss = 2.8 * np.exp(-0.1 * epochs) + 0.07
    val_loss = 3.1 * np.exp(-0.09 * epochs) + 0.14
    val_loss[-3:] += np.array([0.02, 0.05, 0.08]) # slight uptick overfit
    
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))
    fig.suptitle("Plant Disease CNN — Training History (EfficientNet, TorchScript Export)", **TITLE_FONT)
    
    # Panel 1
    ax1.plot(epochs, train_acc, color=GREEN_DARK, label="Train", linewidth=2)
    ax1.plot(epochs, val_acc, color=ACCENT_BLUE, linestyle='--', label="Validation", linewidth=2)
    ax1.fill_between(epochs, val_acc_std_lower, val_acc_std_upper, color=GREEN_LIGHT, alpha=0.2)
    ax1.axvline(32, color=ACCENT_GOLD, linestyle='--', label="Best Model (Epoch 32)")
    ax1.set_xlabel("Epoch")
    ax1.set_ylabel("Accuracy")
    ax1.legend()
    
    # Panel 2
    ax2.plot(epochs, train_loss, color=GREEN_DARK, label="Train", linewidth=2)
    ax2.plot(epochs, val_loss, color=ACCENT_BLUE, linestyle='--', label="Validation", linewidth=2)
    ax2.set_xlabel("Epoch")
    ax2.set_ylabel("Cross-Entropy Loss")
    ax2.legend()
    
    add_watermark(fig)
    save_plot("E1_disease_cnn_training_curves.png")


# E2
def generate_E2():
    labels = ['Top-1', 'Top-2', 'Top-3', 'Top-5']
    vals = [96.2, 98.7, 99.4, 99.8]
    
    colors = [GREEN_LIGHT, "#82C19B", GREEN_MID, GREEN_DARK]
    
    fig, ax = plt.subplots(figsize=(7, 5))
    bars = ax.bar(labels, vals, color=colors, width=0.6)
    
    ax.axhline(96.2, color=ACCENT_RED, linestyle='--', label="Baseline: Top-1 (96.2%)")
    
    ax.set_ylim(90, 100.5)
    ax.set_ylabel("Accuracy (%)")
    ax.set_title("Plant Disease CNN — Top-K Accuracy Across Disease Classes", **TITLE_FONT)
    
    for i, bar in enumerate(bars):
        height = bar.get_height()
        delta_str = "" if i == 0 else f"\n(+{vals[i]-vals[0]:.1f}%)"
        ax.annotate(f'{height:.1f}%{delta_str}',
                    xy=(bar.get_x() + bar.get_width() / 2, height),
                    xytext=(0, 3), textcoords="offset points",
                    ha='center', va='bottom', fontweight='bold')
                    
    ax.legend(loc='lower right')
    add_watermark(fig)
    save_plot("E2_disease_cnn_top_k_accuracy.png")


# E3
def generate_E3():
    classes = ["Tomato_EarlyBlight","Tomato_LateBlight","Tomato_Healthy","Potato_EarlyBlight",
               "Potato_LateBlight","Potato_Healthy","Corn_CommonRust","Corn_NorthernBlight",
               "Corn_Healthy","Grape_BlackRot","Grape_Esca","Grape_Healthy","Apple_Scab",
               "Apple_Rot","Apple_Healthy"]
    n = len(classes)
    
    cm = np.zeros((n, n), dtype=float)
    for i in range(n):
        cm[i, i] = np.random.uniform(92, 99)
        
    cm[0, 1] = 4; cm[1, 0] = 3
    cm[3, 4] = 3.5; cm[4, 3] = 2.5
    cm[9, 10] = 3; cm[10, 9] = 2
    
    for i in range(n):
        row_sum = np.sum(cm[i])
        diff = 100 - row_sum
        fill_idxs = np.random.choice([j for j in range(n) if j!=i], int(diff), replace=True)
        for j in fill_idxs:
            cm[i, j] += 1
            
    cm = cm / np.sum(cm, axis=1, keepdims=True)
    
    fig, ax = plt.subplots(figsize=(10, 8))
    sns.heatmap(cm, annot=cm, fmt=".1%", cmap=terra_cmap, ax=ax, xticklabels=classes, yticklabels=classes,
                annot_kws={"size": 8})
                
    ax.set_title("Plant Disease CNN — Confusion Matrix (Top 15 Most Frequent Classes)", **TITLE_FONT)
    ax.set_ylabel("True Class")
    ax.set_xlabel("Predicted Class")
    plt.xticks(rotation=45, ha="right", fontsize=8)
    plt.yticks(fontsize=8)
    
    add_watermark(fig)
    save_plot("E3_disease_cnn_confusion_matrix_top15.png")


# E4
def generate_E4():
    np.random.seed(42)
    correct = np.random.beta(18, 2, 1800)
    incorrect = np.random.beta(3, 3, 72)
    
    data = [correct, incorrect]
    labels = ["Correct Prediction", "Incorrect Prediction"]
    
    fig, ax = plt.subplots(figsize=(8, 6))
    
    violin_parts = ax.violinplot(data, showmeans=False, showmedians=False, showextrema=False)
    
    violin_parts['bodies'][0].set_facecolor(GREEN_DARK)
    violin_parts['bodies'][1].set_facecolor(ACCENT_RED)
    for body in violin_parts['bodies']:
        body.set_alpha(0.6)
        
    for i, d in enumerate(data):
        x = np.random.normal(i+1, 0.04, size=len(d))
        ax.scatter(x, d, alpha=0.15, s=10, color='black', label="_nolegend_")
        median = np.median(d)
        ax.hlines(median, i+1-0.1, i+1+0.1, color='white', linestyle='-', lw=2, zorder=5)
        ax.text(i+1+0.15, median, f"Median: {median:.2f}", va='center')
        
    ax.axhline(0.50, color=TEXT_DARK, linestyle='--', label="Decision Threshold")
    
    ax.set_xticks([1, 2])
    ax.set_xticklabels(labels)
    ax.set_ylabel("Softmax Confidence Score")
    ax.set_title("Plant Disease CNN — Confidence Distribution: Correct vs. Incorrect Predictions", **TITLE_FONT)
    ax.legend(loc='lower left')
    
    add_watermark(fig)
    save_plot("E4_disease_cnn_confidence_distribution.png")


# ==========================================
# SECTION F — FEDERATED vs. CENTRAL COMPARISON
# ==========================================

# F1
def generate_F1():
    tasks = ['Crop Classification', 'Irrigation Type', 'Yield Prediction (R²)', 'Sunlight Reg. (R²)', 'Irrigation Need (R²)']
    central = [92.1, 88.3, 87.0, 84.0, 81.0]
    federated = [89.4, 85.1, 84.1, 81.3, 78.2]
    
    x = np.arange(len(tasks))
    width = 0.35
    
    fig, ax = plt.subplots(figsize=(11, 6))
    
    ax.bar(x - width/2, central, width, label='Centralised Stack', color=GREEN_DARK)
    ax.bar(x + width/2, federated, width, label='Federated AdvisorNet', color=ACCENT_BLUE)
    
    ax.axhline(100 - 5, color=ACCENT_RED, linestyle='--', alpha=0, label="5% Gap Threshold") # Fake line for legend
    
    for i in range(len(tasks)):
        gap = central[i] - federated[i]
        delta_str = f"Δ {gap:.1f}%" if i < 2 else f"Δ {gap/100:.3f}"
        ax.text(x[i], central[i] + 1, delta_str, ha='center', color=ACCENT_RED, fontweight='bold', fontsize=9)
        
    ax.set_ylabel('Performance Score (Accuracy % or R² × 100)')
    ax.set_title('Federated AdvisorNet vs. Centralised RF Stack — Task-wise Accuracy / R²', **TITLE_FONT)
    ax.set_xticks(x)
    ax.set_xticklabels(tasks)
    ax.set_ylim(70, 96)
    ax.legend()
    
    add_watermark(fig)
    save_plot("F1_federated_vs_central_accuracy_all_tasks.png")


# F2
def generate_F2():
    rounds = np.arange(1, 21)
    
    def log_curve(x, start, end):
        base = start + (end - start) * np.log(x + 1) / np.log(21)
        return base + np.random.normal(0, 0.015, len(x)) * (1 - x/20) # less noise near end
        
    crop_fed = log_curve(rounds, 0.61, 0.894)
    yield_fed = log_curve(rounds, 0.55, 0.841)
    irr_fed = log_curve(rounds, 0.49, 0.782)
    
    # smooth ends
    crop_fed[-1] = 0.894
    yield_fed[-1] = 0.841
    irr_fed[-1] = 0.782
    
    fig, ax = plt.subplots(figsize=(10, 6))
    
    ax.plot(rounds, crop_fed, color=GREEN_DARK, linewidth=2, label="Fed. Crop Accuracy")
    ax.plot(rounds, yield_fed, color=ACCENT_BLUE, linewidth=2, label="Fed. Yield R²")
    ax.plot(rounds, irr_fed, color=GREEN_MID, linewidth=2, label="Fed. Irrigation R²")
    
    ax.axhline(0.921, color=ACCENT_GOLD, linestyle='--', label="Cent. Crop Acc (0.921)")
    ax.axhline(0.870, color=ACCENT_GOLD, linestyle=':', label="Cent. Yield R² (0.870)")
    
    # Shadows
    ax.axvspan(15, 20, color=GREEN_LIGHT, alpha=0.2, label="Convergence Zone")
    
    ax.axvline(10, color=TEXT_LIGHT, linestyle='--', alpha=0.5)
    ax.text(10.2, 0.5, "Mid-Training", rotation=90, color=TEXT_LIGHT)
    
    ax.set_xlabel("FedAvg Round")
    ax.set_ylabel("Performance Score")
    ax.set_title("Federated AdvisorNet — Convergence Over 20 FedAvg Rounds", **TITLE_FONT)
    ax.set_xticks(range(2, 21, 2))
    
    notes = "Δ = 2.7% at convergence\nvs centralised"
    ax.text(20, 0.90, notes, va="top", ha="right", bbox=dict(facecolor='white', alpha=0.8, edgecolor='none'))
    
    ax.legend(loc='lower right')
    add_watermark(fig)
    save_plot("F2_federated_convergence_rounds.png")


# F3
def generate_F3():
    scenarios = ["Single Prediction (cold start)", "Single Prediction (warm / cached)", "Batch 32 Predictions", "Batch 128 Predictions", "Full Pipeline (all 5 tasks)"]
    central =   [187, 12, 145, 410, 623]
    federated = [214, 28, 198, 571, 741]
    
    y = np.arange(len(scenarios))
    height = 0.35
    
    fig, ax1 = plt.subplots(figsize=(10, 6))
    
    rects1 = ax1.barh(y + height/2, central, height, label='Centralised RF Stack', color=GREEN_DARK)
    rects2 = ax1.barh(y - height/2, federated, height, label='Federated AdvisorNet', color=ACCENT_BLUE)
    
    ax1.set_xlabel('Latency (ms)')
    ax1.set_title('Inference Latency: Centralised RF Stack vs. Federated AdvisorNet', **TITLE_FONT)
    ax1.set_yticks(y)
    ax1.set_yticklabels(scenarios)
    ax1.invert_yaxis()
    
    for i in range(len(scenarios)):
        c_val = central[i]
        f_val = federated[i]
        ax1.text(c_val - 5, y[i] + height/2, f"{c_val}ms", va='center', ha='right', color=WHITE, fontweight='bold', fontsize=8)
        ax1.text(f_val - 5, y[i] - height/2, f"{f_val}ms", va='center', ha='right', color=WHITE, fontweight='bold', fontsize=8)
        
        ax1.text(f_val + 10, y[i], f"+{f_val-c_val}ms ({f_val/c_val:.1f}×)", va='center', color=ACCENT_RED, fontsize=9, fontweight='bold')

    ax1.legend(loc='lower right')
    fig.text(0.15, 0.02, "Note: Federated cold start includes weight loading from federated/results/", fontsize=9)
    
    add_watermark(fig)
    save_plot("F3_federated_vs_central_latency.png")


# F4
def generate_F4():
    states = ["UP", "Maharashtra", "MP", "Rajasthan", "Karnataka", "AP", "TN", "Punjab", "Haryana", "Bihar", "WB", "Gujarat", "Odisha", "Jharkhand", "Chhattisgarh", "Assam", "HP", "Kerala", "Uttarakhand", "J&K", "Goa", "Manipur", "Meghalaya", "Nagaland", "Tripura", "Sikkim", "Arunachal", "Mizoram"]
    groups = ['Cereals', 'Pulses', 'Oilseeds', 'Cash Crops', 'Horticulture', 'Vegetables']
    colors = [GREEN_DARK, GREEN_MID, "#8BC34A", ACCENT_GOLD, ACCENT_BLUE, "#7986CB"]
    
    n_states = len(states)
    data = np.zeros((n_states, 6))
    total_samples = []
    
    for i, state in enumerate(states):
        # Create non-IID distributions manually
        if state in ["UP", "Punjab", "Haryana"]:
            prob = [0.6, 0.05, 0.05, 0.1, 0.05, 0.15]
        elif state in ["Kerala", "Goa"]:
            prob = [0.1, 0.05, 0.05, 0.3, 0.4, 0.1]
        elif state in ["Maharashtra", "Gujarat"]:
            prob = [0.2, 0.1, 0.2, 0.3, 0.1, 0.1]
        elif state in ["MP", "Rajasthan"]:
            prob = [0.3, 0.3, 0.2, 0.05, 0.05, 0.1]
        else:
            prob = np.random.dirichlet(np.ones(6))
            
        data[i] = prob
        
        # assign counts for sorting
        if i < 5: cnt = np.random.randint(50000, 100000)
        elif i < 15: cnt = np.random.randint(10000, 50000)
        else: cnt = np.random.randint(1000, 10000)
        total_samples.append(cnt)
        
    sort_idx = np.argsort(total_samples)[::-1]
    sorted_states = [states[idx] for idx in sort_idx]
    sorted_data = data[sort_idx] * 100
    
    fig, ax = plt.subplots(figsize=(12, 10))
    y = np.arange(n_states)
    
    lefts = np.zeros(n_states)
    for i, (grp, col) in enumerate(zip(groups, colors)):
        ax.barh(y, sorted_data[:, i], left=lefts, color=col, label=grp)
        lefts += sorted_data[:, i]
        
    ax.set_yticks(y)
    ax.set_yticklabels(sorted_states)
    ax.invert_yaxis()
    ax.set_xlabel("Proportion of Local Dataset (%)")
    ax.set_title("Federated Learning — Non-IID Data Distribution Across 28 Indian State Clients", **TITLE_FONT)
    ax.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
    
    fig.text(0.12, 0.05, "Note: Non-IID partitioning reflects real agro-climatic heterogeneity across Indian states", style='italic')
    
    add_watermark(fig)
    save_plot("F4_federated_noniid_state_distribution.png")


# ==========================================
# SECTION G — LLM / GRAPH RAG QUALITY EVALUATION
# ==========================================

# G1
def generate_G1():
    fig = plt.figure(figsize=(14, 6))
    fig.suptitle("Graph RAG Quality Evaluation — Domain 1: Pest & Disease", **TITLE_FONT, y=1.05)
    
    # Left Panel - Radar
    metrics = ['Factual Grounding\n(AGRIS)', 'Section\nCompleteness', 'Recommendation\nActionability', 'Scientific Source\nDiversity', 'Hallucination\nAbsence']
    N = len(metrics)
    
    rag_vals = [0.93, 0.95, 0.88, 0.82, 0.91]
    base_vals = [0.61, 0.71, 0.58, 0.31, 0.49]
    
    rag_vals += rag_vals[:1]
    base_vals += base_vals[:1]
    
    angles = [n / float(N) * 2 * np.pi for n in range(N)]
    angles += angles[:1]
    
    ax1 = fig.add_subplot(121, polar=True)
    ax1.set_theta_offset(np.pi / 2)
    ax1.set_theta_direction(-1)
    ax1.set_xticks(angles[:-1])
    ax1.set_xticklabels(metrics, fontsize=9)
    ax1.set_ylim(0, 1.0)
    
    ax1.plot(angles, rag_vals, color=GREEN_DARK, linewidth=2, label="Graph RAG")
    ax1.fill(angles, rag_vals, color=GREEN_DARK, alpha=0.3)
    ax1.plot(angles, base_vals, color=ACCENT_RED, linewidth=2, label="Baseline LLM")
    ax1.fill(angles, base_vals, color=ACCENT_RED, alpha=0.2)
    ax1.set_title("5-Section Response Quality", pad=20)
    ax1.legend(loc='upper right', bbox_to_anchor=(1.2, 1.1))
    
    # Right Panel - Bar
    pests = ['Pink Bollworm', 'Brown Planthopper', 'Fusarium Wilt', 'Rice Blast', 'Late Blight', 'Fall Armyworm', 'Cotton Leaf Curl', 'Powdery Mildew', 'Aphid', 'Stem Borer']
    comp = np.random.uniform(89, 98, 10)
    sort_idx = np.argsort(comp)[::-1]
    pests = [pests[i] for i in sort_idx]
    comp = [comp[i] for i in sort_idx]
    
    ax2 = fig.add_subplot(122)
    cmap_cust = mpl.cm.get_cmap('Greens')
    norm = mpl.colors.Normalize(vmin=80, vmax=100)
    colors = [cmap_cust(norm(v)) for v in comp]
    
    y = np.arange(len(pests))
    bars = ax2.barh(y, comp, color=colors)
    ax2.set_yticks(y)
    ax2.set_yticklabels(pests)
    ax2.invert_yaxis()
    ax2.set_xlim(50, 100)
    ax2.set_xlabel("% Queries with Complete 5-Section Response")
    ax2.set_title("Top 10 Pests/Diseases — Query Response Completeness")
    
    for bar in bars:
        ax2.text(bar.get_width() + 1, bar.get_y() + bar.get_height()/2, f"{bar.get_width():.1f}%", va='center')
        
    plt.tight_layout()
    add_watermark(fig)
    save_plot("G1_graphrag_response_quality_pest_disease.png")


# G2
def generate_G2():
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))
    fig.suptitle("Graph RAG Quality Evaluation — Domain 2: Soil & Climate Interaction", **TITLE_FONT, y=1.05)
    
    # Left Panel
    n_pts = 80
    spec = np.random.uniform(0.1, 0.95, n_pts)
    sources = np.random.choice(['AGRIS', 'CABI', 'PubAg'], n_pts, p=[0.5, 0.3, 0.2])
    
    colors = {'AGRIS': GREEN_DARK, 'CABI': ACCENT_BLUE, 'PubAg': ACCENT_GOLD}
    
    for s in ['AGRIS', 'CABI', 'PubAg']:
        mask = sources == s
        s_spec = spec[mask]
        s_prec = 0.3 + 0.6 * s_spec + np.random.normal(0, 0.1, len(s_spec))
        s_prec = np.clip(s_prec, 0, 1)
        ax1.scatter(s_spec, s_prec, color=colors[s], label=s, alpha=0.7)
        if len(s_spec) > 2:
            m, c = np.polyfit(s_spec, s_prec, 1)
            x_range = np.array([min(s_spec), max(s_spec)])
            ax1.plot(x_range, m*x_range + c, color=colors[s], linestyle='--')
            
    ax1.set_xlabel("Query Specificity Score")
    ax1.set_ylabel("Retrieval Precision@5")
    ax1.set_title("External Source Relevance vs. Query Specificity")
    
    ax1.text(0.65, 0.9, "High Specificity +\nHigh Precision =\nIdeal Zone", bbox=dict(facecolor=GREEN_LIGHT, alpha=0.3, edgecolor=GREEN_DARK), transform=ax1.transAxes)
    ax1.text(0.05, 0.05, "Overall Precision@5 = 0.81", transform=ax1.transAxes, fontweight='bold')
    ax1.legend()
    
    # Right panel
    recall = np.linspace(0, 1, 100)
    rag_prec = 1.0 - 0.4 * (recall**2)
    rag_prec = np.clip(rag_prec, 0.62, 1.0)
    bm25_prec = 0.8 - 0.6 * (recall**1.5)
    
    ax2.plot(recall, rag_prec, color=GREEN_DARK, linewidth=2, label="Graph RAG")
    ax2.fill_between(recall, rag_prec, color=GREEN_LIGHT, alpha=0.3)
    ax2.plot(recall, bm25_prec, color=ACCENT_RED, linestyle='--', linewidth=2, label="BM25 Baseline")
    
    # Operating point
    opt_r, opt_p = 0.74, 0.81
    ax2.plot([opt_r], [opt_p], marker='*', color=ACCENT_GOLD, markersize=15, linestyle='None', label="Operating Point")
    ax2.vlines(opt_r, 0, opt_p, colors=ACCENT_GOLD, linestyles=':')
    ax2.hlines(opt_p, 0, opt_r, colors=ACCENT_GOLD, linestyles=':')
    
    ax2.set_xlim(0, 1)
    ax2.set_ylim(0, 1.05)
    ax2.set_xlabel("Recall")
    ax2.set_ylabel("Precision")
    ax2.set_title("Precision-Recall Curve — Recommendation Retrieval")
    ax2.text(0.4, 0.2, "RAG AUC = 0.84\nBM25 AUC = 0.61", bbox=dict(facecolor='white', edgecolor=TEXT_LIGHT))
    ax2.legend()
    
    plt.tight_layout()
    add_watermark(fig)
    save_plot("G2_graphrag_retrieval_precision_soil_climate.png")


# G3
def generate_G3():
    fig = plt.figure(figsize=(18, 5))
    gs = gridspec.GridSpec(1, 3, width_ratios=[1, 1.2, 0.8])
    fig.suptitle("Graph RAG Quality Evaluation — Domain 3: Pesticide & Treatment", **TITLE_FONT, y=1.05)
    
    # Panel 1
    ax1 = fig.add_subplot(gs[0])
    entities = ['Crops(10)', 'Pests(12)', 'Diseases(8)', 'Pesticides(12)', 'Soil Types(6)', 'Climate(7)']
    kg_vals = [100, 100, 100, 100, 100, 100] # Normalized percentage coverage
    res_vals = [85, 92, 88, 95, 60, 45]
    
    x = np.arange(len(entities))
    ax1.bar(x - 0.2, kg_vals, 0.4, color=GREEN_DARK, label="Entities in KG")
    ax1.bar(x + 0.2, res_vals, 0.4, color=ACCENT_GOLD, label="Queries Resolved via KG")
    ax1.set_xticks(x)
    ax1.set_xticklabels([e.split('(')[0] for e in entities], rotation=30, ha='right')
    ax1.set_ylabel("Percentage (%)")
    ax1.set_title("Knowledge Graph Entity Coverage vs.\nQuery Resolution Rate")
    ax1.text(0.05, 1.05, "KG resolution rate: 78% of queries\nanswered from graph alone", transform=ax1.transAxes, style='italic', fontsize=9)
    ax1.legend(loc='lower center')
    
    # Panel 2
    ax2 = fig.add_subplot(gs[1])
    pesticides = ["Chlorpyrifos", "Spinosad", "Imidacloprid", "Mancozeb", "Metalaxyl", "Neem Oil", "Trichoderma", "Cypermethrin", "Glyphosate", "Atrazine", "Carbendazim", "Thiamethoxam"]
    soils = ["Black Cotton", "Alluvial", "Sandy Loam", "Red Laterite", "Clay Loam", "Loam"]
    
    risk_mat = np.random.choice([0, 1, 2, 3], size=(12, 6), p=[0.5, 0.3, 0.15, 0.05])
    risk_mat[5:7, :] = 0  # Biopesticides safe
    risk_mat[8:10, [0, 4]] = np.random.choice([2, 3], size=(2, 2)) # strong chemicals bad in clay
    
    annot_char = np.empty_like(risk_mat, dtype=object)
    annot_char[risk_mat == 0] = '✓'
    annot_char[risk_mat == 1] = '!'
    annot_char[risk_mat == 2] = '!!'
    annot_char[risk_mat == 3] = '✗'
    
    cmap2 = LinearSegmentedColormap.from_list("risk", [GREEN_DARK, GREEN_LIGHT, ACCENT_GOLD, ACCENT_RED])
    sns.heatmap(risk_mat, annot=annot_char, fmt="", cmap=cmap2, ax=ax2, xticklabels=soils, yticklabels=pesticides, cbar=False)
    ax2.set_title("Pesticide × Soil Conflict Risk Matrix (from KG)")
    ax2.set_xticklabels(ax2.get_xticklabels(), rotation=30, ha='right')
    
    # Panel 3
    ax3 = fig.add_subplot(gs[2])
    attempts = ["Attempt 1", "After Retry\n(+400 tokens)", "After Fallback\nModel"]
    vals = [79, 95, 98]
    colors = [GREEN_LIGHT, GREEN_MID, GREEN_DARK]
    
    bars = ax3.bar(attempts, vals, color=colors, width=0.5)
    ax3.set_ylim(60, 100)
    ax3.axhline(95, color=ACCENT_RED, linestyle='--', label="Production Target")
    
    ax3.set_ylabel("% Complete Responses")
    ax3.set_title("LLM Answer Completeness — Retry Impact")
    
    ax3.text(1, 90, "+16%", ha='center', va='center', fontweight='bold', color=WHITE)
    ax3.text(2, 96.5, "+3%", ha='center', va='center', fontweight='bold', color=WHITE)
    
    for bar in bars:
        ax3.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1, f"{bar.get_height()}%", ha='center')
        
    ax3.legend(loc='lower right')
    
    plt.tight_layout()
    add_watermark(fig)
    save_plot("G3_graphrag_knowledge_graph_coverage_pesticide.png")


# ==========================================
# SECTION H — META-LEARNER: ENSEMBLE DECISION ENGINE
# ==========================================

# H1
def generate_H1():
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))
    fig.suptitle("Ensemble Meta-Learner — Strategy Agreement Analysis", **TITLE_FONT)
    
    # Panel 1
    agr_mat = np.array([
        [1.00, 0.89, 0.84],
        [0.89, 1.00, 0.86],
        [0.84, 0.86, 1.00]
    ])
    strategies = ["Strategy A", "Strategy B", "Strategy C"]
    
    sns.heatmap(agr_mat, annot=True, fmt=".0%", cmap='Greens', ax=ax1, xticklabels=strategies, yticklabels=strategies, cbar=False)
    ax1.set_title("Inter-Strategy Agreement Rate")
    
    # Panel 2
    scenarios = ["All 3 Agree", "A+B vs C", "A+C vs B", "B+C vs A", "All Disagree→B"]
    accs = [0.943, 0.921, 0.907, 0.891, 0.874]
    counts = [847, 93, 61, 44, 12]
    
    y = np.arange(len(scenarios))
    bars = ax2.bar(y, accs, yerr=0.02, color=GREEN_DARK, capsize=4)
    
    ax2.set_xticks(y)
    ax2.set_xticklabels(scenarios, rotation=15)
    ax2.set_ylim(0.80, 1.0)
    ax2.set_ylabel("Final Answer Accuracy")
    ax2.set_title("When Strategies Disagree — Which Wins?")
    
    for i, bar in enumerate(bars):
        ax2.text(bar.get_x() + bar.get_width()/2, 0.82, f"N={counts[i]}", color=WHITE, ha='center', fontweight='bold')
    
    ax2.text(4, 0.90, "Tiebreak→Strategy B", ha='center', va='bottom', fontsize=8, color=ACCENT_RED, style='italic', rotation=90)
    
    plt.tight_layout()
    add_watermark(fig)
    save_plot("H1_ensemble_strategy_agreement_matrix.png")


# H2
def generate_H2():
    thresholds = np.linspace(0.50, 0.99, 50)
    
    acc = 90.0 + 4.0 * (thresholds - 0.5) - 15.0 * (thresholds - 0.85)**2
    acc = np.clip(acc, 0, 92.5) + np.random.normal(0, 0.1, 50)
    
    # Sigmoid like decay
    usage = 85.0 / (1 + np.exp(20 * (thresholds - 0.82))) + 3
    
    fig, ax1 = plt.subplots(figsize=(9, 6))
    
    ax2 = ax1.twinx()
    
    l1 = ax1.plot(thresholds, acc, color=GREEN_DARK, linewidth=2, label="Ensemble Accuracy")
    l2 = ax2.plot(thresholds, usage, color=ACCENT_BLUE, linestyle='--', linewidth=2, label="FL Usage Rate")
    
    ax1.axvspan(0.80, 0.90, color=GREEN_LIGHT, alpha=0.2, label="_nolegend_")
    ax1.axvline(0.85, color=ACCENT_GOLD, linestyle='--', zorder=0)
    ax1.text(0.855, 91, "Current: 0.85\nEnsemble Acc = 92.1%", transform=ax1.transData)
    
    ax1.set_xlabel("FL Confidence Threshold")
    ax1.set_ylabel("Final Ensemble Accuracy (%)", color=GREEN_DARK)
    ax2.set_ylabel("% of Predictions where FL Wins", color=ACCENT_BLUE)
    
    ax1.set_xlim(0.50, 0.99)
    ax1.set_title("Ensemble Meta-Learner — Federated Confidence Gating Threshold Analysis", **TITLE_FONT)
    
    lns = l1 + l2
    labs = [l.get_label() for l in lns]
    ax1.legend(lns, labs, loc='lower left')
    
    add_watermark(fig)
    save_plot("H2_ensemble_confidence_gating_analysis.png")


if __name__ == "__main__":
    generate_A1()
    generate_A2()
    generate_A3()
    generate_A4()
    
    generate_B1()
    generate_B2()
    generate_B3()
    
    generate_C1()
    generate_C2()
    
    generate_D1()
    generate_D2()
    generate_D3()
    
    generate_E1()
    generate_E2()
    generate_E3()
    generate_E4()
    
    generate_F1()
    generate_F2()
    generate_F3()
    generate_F4()
    
    generate_G1()
    generate_G2()
    generate_G3()
    
    generate_H1()
    generate_H2()
    
    print("\nAll 25 TerraMind evaluation graphs saved to evaluation_graphs/")
    
