import math
import os
from typing import List

import numpy as np
import pandas as pd
from scipy import stats
import seaborn as sns
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
import itertools
from scipy.stats import mannwhitneyu

from comparison_analysis.comparison_config import TIME_UNITS
from comparison_analysis.utils.statistical_significance import interpret_cliffs_delta, format_p, cliffs_delta
from pre_processing.S2CF_config import ACTIVITY_COLUMN_NAME, DATASET_NAME_COLUMN_NAME, END_ACTIVITIES, END_DATETIME_COLUMN_NAME, START_ACTIVITIES, START_DATETIME_COLUMN_NAME

# ------------------------------------------------------------
# ACTIVITY DURATION COMPARISON
# ------------------------------------------------------------
# Creates one figure with boxplots for each activity on their "own" time unit scale
def create_boxplots_per_activity_duration(
  dataframe: pd.DataFrame,
  output_folder_paths: List[str],
  execution_name: str,
  metric_name: str,
  duration_column_name: str,
  activity_column_name: str = ACTIVITY_COLUMN_NAME,
  dataset_column_name: str = DATASET_NAME_COLUMN_NAME
):
  sns.set_theme(
    style="whitegrid",
    context="talk",
    font_scale=0.9
  )

  included_activity_names = dataframe[activity_column_name].unique().tolist()

  cols = 2
  rows = math.ceil(len(included_activity_names) / cols)

  fig, axes = plt.subplots(rows, cols, figsize=(14, 4 * rows))
  axes = axes.flatten()

  dataset_order = sorted(dataframe[dataset_column_name].unique())

  for ax_i, phase in enumerate(included_activity_names):
    ax = axes[ax_i]
    phase_data = dataframe[dataframe[activity_column_name] == phase].copy()

    # ---------- UNIT SELECTION ----------
    q95 = phase_data[duration_column_name].quantile(0.95)

    if q95 < 120:
        scale = 1
        unit = "seconds"
    elif q95 < 2 * 3600:
        scale = 60
        unit = "minutes"
    else:
        scale = 3600
        unit = "hours"

    phase_data["Duration_scaled"] = phase_data[duration_column_name] / scale

    # ---------- SEABORN BOXPLOT ----------
    sns.boxplot(
      data=phase_data,
      x=dataset_column_name,
      y="Duration_scaled",
      order=dataset_order,
      ax=ax,
      palette="Set2",
      hue=dataset_column_name,
      fliersize=5,
      linewidth=1.2
    )

    absolute_max = phase_data["Duration_scaled"].max()
    
    if not math.isnan(absolute_max) and absolute_max > 0:
        ax.set_ylim(0, absolute_max * 1.15)
    else:
        ax.set_ylim(0, 1)

    # ---------- MEDIAN ANNOTATIONS ----------
    medians = phase_data.groupby(dataset_column_name)["Duration_scaled"].median()
    
    for i, dataset in enumerate(dataset_order):
        if dataset in medians:
            median_val = medians[dataset]
            ax.text(
                i,
                median_val,
                f"{median_val:.2f}",
                ha="center",
                va="bottom",
                fontsize=8,
                weight='bold',
                color='black'
            )

    # ---------- LABELS & STYLING ----------
    ax.set_title(phase.replace("_", " "), fontsize=12, weight="semibold")
    ax.set_xlabel("Dataset")
    ax.set_ylabel(f"{metric_name} ({unit})")
    
    # Strip unnecessary outer borders for a cleaner look
    sns.despine(ax=ax, left=False, bottom=False)

  # Remove unused axes
  for j in range(len(included_activity_names), len(axes)):
    fig.delaxes(axes[j])

  plt.suptitle(
      f"{metric_name} comparison",
      fontsize=16,
      weight="bold"
  )
  plt.tight_layout(rect=(0, 0, 1, 0.96))

  for path in output_folder_paths:
    plt.savefig(
      os.path.join(
        path,
        f"boxplots_faceted_{metric_name.replace(' ', '-')}_{execution_name}.png"
      ),
      dpi=300,
      bbox_inches="tight"
    )
  plt.close()

def create_log_scaled_boxplot_activity_durations(
  dataframe: pd.DataFrame,
  output_folder_paths: List[str],
  execution_name: str,
  metric_name: str,
  duration_column_name: str,
  activity_column_name: str = ACTIVITY_COLUMN_NAME,
  dataset_column_name: str = DATASET_NAME_COLUMN_NAME
):
  dataframe["Activity_Label"] = dataframe[activity_column_name].str.replace("_", " ")
  included_activity_names = dataframe[activity_column_name].unique().tolist()

  phase_order = sorted([p.replace("_", " ") for p in included_activity_names])
  phase_order = [p.replace("_", " ") for p in phase_order if not p.startswith("0")]

  dataset_order = sorted(dataframe[dataset_column_name].unique().tolist())

  sns.set_theme(
    style="whitegrid",
    context="talk",      # larger fonts
    font_scale=0.9
  )

  plt.figure(figsize=(max(18, len(phase_order) * 1.2), 8))

  ax = sns.boxplot(
    data=dataframe,
    x="Activity_Label",
    y=duration_column_name,
    hue=dataset_column_name,
    order=phase_order,
    hue_order=dataset_order,
    palette="Set2",
    linewidth=1,
    fliersize=3
  )

  # Log-scale y-axis
  ax.set_yscale("log")

  # Labels
  ax.set_ylabel("Duration (seconds, log scale)")
  ax.set_xlabel(activity_column_name)
  ax.set_title(f"{metric_name} comparison", pad=20)

  # Improve x-axis readability
  ax.tick_params(axis="x", rotation=40)
  ax.margins(x=0.05)

  # Grid on y-axis only
  ax.grid(True, which="both", axis="y", alpha=0.3)
  ax.grid(False, axis="x")

  ax.legend(
    title="Dataset",
    loc="upper left",
    bbox_to_anchor=(1.01, 1),
    frameon=True
  )

  plt.tight_layout(rect=(0, 0, 0.88, 1))

  for path in output_folder_paths:
    plt.savefig(
      os.path.join(
        path,
        f"log_scaled_boxplot_{metric_name}_{execution_name}.png"
      ),
      dpi=300,
      bbox_inches="tight"
    )
  plt.close()
  
def create_linear_scaled_boxplot_activity_durations(
  dataframe: pd.DataFrame,
  output_folder_paths: List[str],
  execution_name: str,
  metric_name: str,
  duration_column_name: str,
  activity_column_name: str = ACTIVITY_COLUMN_NAME,
  dataset_column_name: str = DATASET_NAME_COLUMN_NAME 
):
  dataframe["Duration_h"] = dataframe[duration_column_name] / 3600

  # Create readable phase label
  dataframe["Activity_Label"] = dataframe[activity_column_name].str.replace("_", " ")

  # Explicit ordering
  included_activity_names = dataframe[activity_column_name].unique().tolist()

  phase_order = sorted([p.replace("_", " ") for p in included_activity_names])

  dataset_order = sorted(dataframe[dataset_column_name].unique())

  sns.set_theme(
      style="whitegrid",
      context="talk",
      font_scale=0.9
  )

  plt.figure(figsize=(max(18, len(phase_order) * 1.2), 8))

  ax = sns.boxplot(
      data=dataframe,
      x="Activity_Label",
      y="Duration_h",
      hue=dataset_column_name,
      order=phase_order,
      hue_order=dataset_order,
      palette="Set2",
      linewidth=1,
      fliersize=3
  )

  # ---------- LINEAR Y-AXIS IN HOURS ----------
  ax.set_ylabel("Duration (hours)")
  ax.set_xlabel(activity_column_name)
  ax.set_title(f"{metric_name} comparison", pad=20)

  # Force sensible baseline for linear scale
  ax.set_ylim(bottom=0)

  # Improve x-axis readability
  ax.tick_params(axis="x", rotation=40)
  ax.margins(x=0.05)

  # Grid on y-axis only
  ax.grid(True, axis="y", alpha=0.3)
  ax.grid(False, axis="x")

  ax.legend(
      title="Dataset",
      loc="upper left",
      bbox_to_anchor=(1.01, 1),
      frameon=True
  )

  plt.tight_layout(rect=(0, 0, 0.88, 1))

  # ---------- SAVE ----------
  for path in output_folder_paths:
    plt.savefig(
      os.path.join(
        path,
        f"boxplot_{metric_name}_linear_hours_{execution_name}.png"
      ),
      dpi=300,
      bbox_inches="tight"
    )
  plt.close()

def create_boxplot_for_activity_duration(
  activity_label: str,
  activity_data: pd.DataFrame,
  output_folder_paths: List[str],
  execution_name: str,
  metric_name: str,
  duration_column_name: str,
  dataset_column_name: str = DATASET_NAME_COLUMN_NAME 
):
  dataset_order = sorted(activity_data[dataset_column_name].unique().tolist())
  palette = dict(
      zip(dataset_order, sns.color_palette("Set2", len(dataset_order)))
  )
  # ------------------------------------------------
  # AUTOMATIC UNIT SELECTION (95th percentile)
  # ------------------------------------------------
  q95 = activity_data[duration_column_name].quantile(0.95)

  if q95 < 120:
    scale = 1
    unit = "seconds"
  elif q95 < 2 * 3600:
    scale = 60
    unit = "minutes"
  else:
    scale = 3600
    unit = "hours"

  activity_data["Duration_scaled"] = activity_data[duration_column_name] / scale

  # ------------------------------------------------
  # BOXPLOT
  # ------------------------------------------------
  plt.figure(figsize=(9, 5))
  ax = sns.boxplot(
    data=activity_data,
    x=dataset_column_name,
    y="Duration_scaled",
    order=dataset_order,
    palette=palette,
    hue=dataset_column_name,
    showfliers=True
  )

  # ------------------------------------------------
  # CALCULATE Y-OFFSET FOR MEDIAN LABELS
  # ------------------------------------------------
  y_min, y_max = ax.get_ylim()
  y_offset = 0.04 * (y_max - y_min)  # 4% of axis range

  medians = (
    activity_data
    .groupby(dataset_column_name)["Duration_scaled"]
    .median()
    .reindex(dataset_order)
  )

  for i, (_, median) in enumerate(medians.items()):
    ax.text(
      i,
      median + y_offset,
      f"{median:.2f}",
      ha="center",
      va="bottom",
      fontsize=9,
      fontweight="bold",
      color="black",
      zorder=10
    )

  # ------------------------------------------------
  # LABELS & STYLE
  # ------------------------------------------------
  ax.set_title(
    f"{metric_name} – activity: {activity_label.replace('_', ' ')}",
    pad=15
  )
  ax.set_xlabel("Dataset")
  ax.set_ylabel(f"Duration ({unit})")

  ax.grid(True, axis="y", alpha=0.3)

  plt.tight_layout()

  # ------------------------------------------------
  # SAVE
  # ------------------------------------------------
  for path in output_folder_paths:
    plt.savefig(
      os.path.join(
        path,
        f"boxplot_activity_{activity_label}_{execution_name}.png"
      ),
      dpi=300,
      bbox_inches="tight"
    )
  plt.close()

def create_table_activity_durations(
  dataframe: pd.DataFrame,
  output_folder_paths: List[str],
  execution_name: str,
  metric_name: str,
  duration_column_name: str,
  activity_column_name: str = ACTIVITY_COLUMN_NAME,
  dataset_column_name: str = DATASET_NAME_COLUMN_NAME 
):
  datasets = dataframe[dataset_column_name].unique()
  if len(datasets) != 2:
      raise ValueError(f"Expected exactly 2 datasets, found {len(datasets)}: {datasets}")

  ds1, ds2 = sorted(datasets)
  unique_activities = sorted(dataframe[activity_column_name].unique())

  significance_rows = []

# --- 2. STATISTICAL ANALYSIS PER ACTIVITY ---
  for activity in unique_activities:
    # Filter data for the specific activity
    act_data = dataframe[dataframe[activity_column_name] == activity]
    
    data_ds1 = act_data[act_data[dataset_column_name] == ds1][duration_column_name].dropna()
    data_ds2 = act_data[act_data[dataset_column_name] == ds2][duration_column_name].dropna()
    
    n1, n2 = len(data_ds1), len(data_ds2)
    
    # Skip if we don't have enough data points to compute statistics
    if n1 < 5 or n2 < 5:
        continue
        
    # Calculate Medians (Robust against process mining tail outliers)
    median_1 = data_ds1.median()
    median_2 = data_ds2.median()
    diff_seconds = median_1 - median_2
    
    # Mann-Whitney U test (Non-parametric test for skewed duration distributions)
    u_stat, p_val = stats.mannwhitneyu(data_ds1, data_ds2, alternative='two-sided')
    
    # Cliff's Delta for Effect Size (-1.0 to +1.0)
    # Interpretation: <0.147 (Negligible), <0.33 (Small), <0.474 (Medium), otherwise (Large)
    d_val =cliffs_delta(data_ds1, data_ds2)
    
    # Map effect size value to a standard academic qualitative descriptor
    effect_size_label = interpret_cliffs_delta(d_val)

    # Formatting significance stars
    if p_val < 0.001:    stars = "***"
    elif p_val < 0.01:   stars = "**"
    elif p_val < 0.05:   stars = "*"
    else:                stars = "ns" # non-significant
    
    significance_rows.append({
        f"{ACTIVITY_COLUMN_NAME}": activity.replace("_", " "),
        f"Median {ds1} (s)": round(median_1, 2),
        f"Median {ds2} (s)": round(median_2, 2),
        "Δ Median (s)": round(diff_seconds, 2),
        "p-value": f"{format_p(p_val)}",
        "Sign.": stars,
        "Cliff's d": round(d_val, 3),
        "Effect Size": effect_size_label
    })

  # --- 3. DISPLAY THE PROCESS MINING TABLE ---
  results_df = pd.DataFrame(significance_rows)

  latex_table = results_df.to_latex(index=False)
  for path in output_folder_paths:
    output_file_path = os.path.join(path, f'{metric_name.replace(' ', '-')}_significance_latex_table_{execution_name}.txt') 
    with open(output_file_path, 'w', encoding="utf-8") as f:
      f.write(latex_table)

# ------------------------------------------------------------
# TRACE DURATION COMPARISON 
# ------------------------------------------------------------

def create_stacked_bar_figure(
  dataframe: pd.DataFrame,
  output_folder_paths: List[str],
  execution_name: str,
  metric_name: str,
  duration_column_name: str,
  activity_column_name: str = ACTIVITY_COLUMN_NAME,
  dataset_column_name: str = DATASET_NAME_COLUMN_NAME 
):
  
  included_activity_names = dataframe[activity_column_name].unique().tolist()

  activity_durations = (
    dataframe
      .groupby([dataset_column_name, activity_column_name])[duration_column_name]
      .mean()
      .reset_index()
      .pivot(index=activity_column_name, columns=dataset_column_name, values=duration_column_name)
      .reindex(included_activity_names)
      .fillna(0)
  )
  # Convert to minutes
  phase_summary_minutes = activity_durations / 60.0

  dataset_values = sorted(dataframe[dataset_column_name].unique().tolist())

  activities = phase_summary_minutes.index.tolist()
  before_values_inc_v2 = phase_summary_minutes[dataset_values[0]].tolist()
  after_values_inc_v2 = phase_summary_minutes[dataset_values[1]].tolist()

  draw_sankey_plot(
    activities=activities,
    before_values=before_values_inc_v2,
    after_values=after_values_inc_v2,
    plot_name=f"{metric_name.replace(' ', '-')}_sankey_{execution_name}.png",
    output_folder_paths=output_folder_paths
  )

def draw_sankey_plot(
  activities,
  before_values,
  after_values,
  plot_name,
  output_folder_paths,
):
  phase_colors = [
    "#6aa5ff",  # blue
    "#e38d8d",  # rose red
    "#5b7f23",  # green
    "#8d76ad",  # violet
  ]
  
  def _bar_is_long_enough(bar, min_length_cm=0.7):
    min_length_in = min_length_cm / 2.54
    ax = bar.axes
    fig = ax.figure

    fig.canvas.draw()

    x0 = bar.get_x()
    x1 = x0 + bar.get_width()

    # Transform to display coords
    disp_x0 = ax.transData.transform((x0, 0))[0]
    disp_x1 = ax.transData.transform((x1, 0))[0]

    bar_length_in = abs(disp_x1 - disp_x0) / fig.dpi
    return bar_length_in >= min_length_in


  # If more phases exist, auto-extend colors

  palette = itertools.cycle(plt.cm.tab20.colors)
  while len(phase_colors) < len(activities):
      phase_colors.append(next(palette))

  fig, ax = plt.subplots(figsize=(18, 6), facecolor="white")
  ax.set_facecolor("white")

  # Remove axes
  for side in ["top","right","left","bottom"]:
      ax.spines[side].set_visible(False)
  ax.set_xticks([])
  ax.set_yticks([])

  # Draw stacked bars
  def draw_stacked(values, y_pos):
      centers = []
      left = 0
      bars = []
      for v, col in zip(values, phase_colors):
          bar = ax.barh(y_pos, v, left=left, color=col, height=0.3)
          bars.append(bar[0])
          centers.append(left + v/2)
          left += v
      return bars, centers

  offset = max(max(before_values), max(after_values)) * 0.03  # small spacing

  before_bars, before_centers = draw_stacked(before_values, y_pos=1)
  after_bars, after_centers   = draw_stacked(after_values,  y_pos=0)

  total_before = sum(before_values)
  total_after  = sum(after_values)

  ax.text(total_before, 1, f"{total_before:.1f} min",
          va='center', ha='left', fontsize=16, color='black')

  ax.text(total_after + offset, 0, f"{total_after:.1f} min",
          va='center', ha='left', fontsize=16, color='black')


  # Add labels only if readable
  for bar, val in zip(before_bars, before_values):
    if _bar_is_long_enough(bar):
      ax.text(bar.get_x() + bar.get_width()/2, bar.get_y()+bar.get_height()/2,
        f"{val:.1f}", color="white", ha="center", va="center", fontsize=18)

  for bar, val in zip(after_bars, after_values):
    if _bar_is_long_enough(bar):
      ax.text(bar.get_x() + bar.get_width()/2, bar.get_y()+bar.get_height()/2,
            f"{val:.1f}", color="white", ha="center", va="center", fontsize=18)

  # Connector lines (start to start)
  for b_bar, a_bar in zip(before_bars, after_bars):
    x_before = b_bar.get_x()
    x_after  = a_bar.get_x()

    y_before = b_bar.get_y() + b_bar.get_height()/2
    y_after  = a_bar.get_y() + a_bar.get_height()/2

    ax.plot([x_before, x_after], [y_before, y_after], color="black", linewidth=1)

  # Labels
  before_y = 1+ 0.2   # slightly above before bar
  after_y  = 0+ 0.2   # slightly above after bar

  ax.text(12, before_y, "Pre-AI-addition (minutes)", color="black", fontsize=18,
      va="bottom", ha="left")

  ax.text(12, after_y,  "Trial-AI-addition (minutes)", color="black", fontsize=18,
      va="bottom", ha="left")

  ax.set_ylim(-3, 1.5)
  # Legend
  handles = [Rectangle((0,0),1,1,color=c) for c in phase_colors]
  ax.legend(handles, activities, fontsize=16, facecolor="white", edgecolor="black", labelcolor="black", loc="upper left", bbox_to_anchor=(1.25, 1))

  plt.tight_layout()

  # Save
  for path in output_folder_paths:
    plt.savefig(os.path.join(path, plot_name), dpi=300, bbox_inches="tight")
  plt.close()

def compute_trace_metrics(
  df: pd.DataFrame,
  activity_column_name: str = ACTIVITY_COLUMN_NAME,
  start_activities: List[str] = START_ACTIVITIES,
  end_activities: List[str] = END_ACTIVITIES,
  start_datetime_column_name: str = START_DATETIME_COLUMN_NAME,
  end_datetime_column_name: str = END_DATETIME_COLUMN_NAME
) -> pd.Series:
  """
  Compute:
    - total_duration: last end time - first start time
    - inactive_time: sum of gaps (Shutdown → next Startup)
    - active_time: total_duration - inactive_time
    - duration metrics converted to TIME_UNITS
  """
  df = df.sort_values(start_datetime_column_name)

  start_time = df[start_datetime_column_name].min()
  end_time = df[end_datetime_column_name].max()
  total_duration = end_time - start_time

  inactive_time = pd.Timedelta(0)

  for i in range(len(df) - 1):
    event = df.iloc[i]
    next_event = df.iloc[i + 1]

    if (
      str(event[activity_column_name]) in end_activities
      and str(next_event[activity_column_name]) in start_activities
    ):
      gap = (
        next_event[start_datetime_column_name]
        - event[end_datetime_column_name]
      )

      if pd.notna(gap) and gap > pd.Timedelta(0):
        inactive_time += gap

  active_time = total_duration - inactive_time

  metrics = {
    "start_time": start_time,
    "end_time": end_time,
    "total_duration": total_duration,
    "inactive_time": inactive_time,
    "active_time": active_time,
  }

  # Add converted duration columns
  for col in ["total_duration", "inactive_time", "active_time"]:
    metrics[f"{col}_{TIME_UNITS}"] = to_units(metrics[col])

  return pd.Series(metrics)

def to_units(td, units="hours"):
    UNIT_DIVISOR = {'seconds': 1, 'minutes': 60, 'hours': 3600}[units]

    if isinstance(td, pd.Series):
        return td.dt.total_seconds() / UNIT_DIVISOR

    return td.total_seconds() / UNIT_DIVISOR

def create_boxplot_graph(
  dataframe: pd.DataFrame,
  output_folder_paths: List[str],
  value_column: str,
  execution_name: str,
  show_outliers: bool,
  title: str,
  metric_name: str,
  units_label: str = TIME_UNITS,
  dataset_name_attribute: str = DATASET_NAME_COLUMN_NAME,
):
    """
    Seaborn-based comparison plot (boxplot only, no histogram).
    """

    # Set seaborn style
    sns.set(style="whitegrid")

    plt.figure(figsize=(8, 6))

    # Boxplot comparing the two sources
    ax = sns.boxplot(
        data=dataframe,
        x=dataset_name_attribute,
        y=value_column,
        palette="Set2",
        hue=dataset_name_attribute,
        showfliers=show_outliers
    )

    medians = dataframe.groupby(dataset_name_attribute)[value_column].median()
    dataset_names = dataframe[dataset_name_attribute].unique().tolist()
    for i, (source, median) in enumerate(medians.items()):
        ax.text(
            i,
            median,
            f"{median:.2f}",
            ha="center",
            va="bottom",
            fontsize=14,
            fontweight="bold",
            color="black",
            zorder=10
        )
    # Labels & title
    ax.set_title(f"{metric_name} ({units_label})", fontsize=18)
    ax.set_xlabel("", fontsize=14)
    ax.set_ylabel(f"{metric_name} ({units_label})", fontsize=16)

    # Rename x-axis labels to match input labels
    ax.set_xticks([0,1])
    ax.set_xticklabels(dataset_names)
    ax.tick_params(axis='both', labelsize=16)
    plt.tight_layout()

    for path in output_folder_paths:
      plt.savefig(
        os.path.join(
          path,
          f"{title}_{execution_name}.png"
        ),
        dpi=300,
        bbox_inches="tight"
      )
    plt.close()

def create_trace_duration_latex_table(
  dataframe: pd.DataFrame,
  output_folder_paths: str,
  execution_name: str,
  time_units: str = TIME_UNITS,
  dataset_name_column: str = DATASET_NAME_COLUMN_NAME,
):
  metrics = {
    "Throughput time": f"total_duration_{time_units}",
    "Inactive time": f"inactive_time_{time_units}",
    "Active FLA time": f"active_time_{time_units}"
  }

  dataset_names = dataframe[dataset_name_column].unique().tolist()

  results = []

  for name, col in metrics.items():
    data_a = dataframe[dataframe[dataset_name_column] == dataset_names[0]][col].dropna()
    data_b = dataframe[dataframe[dataset_name_column] == dataset_names[1]][col].dropna()

    # Mann-Whitney U test
    stat, p_value = mannwhitneyu(data_a, data_b, alternative="two-sided")

    # Cliff's delta
    delta = cliffs_delta(data_a, data_b)

    results.append({
      "Metric": name,
      "Median A": np.median(data_a),
      "Median B": np.median(data_b),
      "p-value": p_value,
      "Cliffs delta": delta
    })

  stats_df = pd.DataFrame(results)

  stats_df["Effect size"] = stats_df["Cliffs delta"].apply(interpret_cliffs_delta)

  stats_df["p-value"] = stats_df["p-value"].apply(format_p)

  latex_table = stats_df.to_latex(
    index=False,
    float_format="%.3f",
    caption="Statistical comparison between pre-AI and trial-AI traces using Mann–Whitney U test and Cliff's Delta.",
    label="tab:trace_comparison_stats"
  )

  for path in output_folder_paths:
    output_file_path = os.path.join(path, f'trace_duration_significance_latex_table_{execution_name}.txt') 
    with open(output_file_path, 'w', encoding="utf-8") as f:
      f.write(latex_table)
