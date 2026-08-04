
import argparse
from collections import defaultdict
import os
import sys
import pandas as pd

from pre_processing.S2CF_config import RESOURCE_COLUMN_NAME, START_DATETIME_COLUMN_NAME, DATETIME_PATTERN, END_DATETIME_COLUMN_NAME, DATASET_NAME_COLUMN_NAME, ACTIVITY_COLUMN_NAME, CASEID_COLUMN_NAME
from comparison_analysis.comparison_config import MIMINUM_NUMBER_CASES_THRESHOLD, PROCESS_COMPARATOR_CONFIGS, TIME_UNITS
from pre_processing.utils.data_refining import filter_csv_by_prefix
from comparison_analysis.utils.handover_comparison import count_switches_folder, create_handover_latex_table
from comparison_analysis.utils.process_comparator_types import AnnotatedTransitionSystem, EventLogStore
from comparison_analysis.utils.variant_analysis import build_variant_table, extract_worksessions_with_time
from comparison_analysis.utils.performance_comparison import create_boxplot_graph, create_boxplots_per_activity_duration, create_log_scaled_boxplot_activity_durations, create_linear_scaled_boxplot_activity_durations, create_boxplot_for_activity_duration, create_stacked_bar_figure, create_table_activity_durations, compute_trace_metrics, create_trace_duration_latex_table


if __name__ == "__main__":
  print('Starting the Comparison module')
  parser = argparse.ArgumentParser()
  parser.add_argument("--elfp", required=True, nargs='+', help="Complete path directing to folders (as created by the S2CF module) with preprocessed event log files. At least with an event log with all the traces, and for handover analysis a folder with files per case.")
  parser.add_argument("--ofp", required=True, nargs='+', help="Complete path directing to folders where the output of the comparisons should be stored")
  parser.add_argument("--dsn", required=True, nargs='+', help="The name of the data set, make sure that they are in the same order of the folders")
  parser.add_argument("--name", default="", type=str, help="The name of this execution")
  parser.add_argument("--execute", nargs='+', default=[], help="The names of the comparisons (performance, behaviour and handover) that should be executed, if empty it runs the whole module")
  parser.add_argument("--eln", type=str, default='event_log_removed_V2.csv', help="The name of the event log, in the elfp folders that contains the complete event log for the comparison")
  parser.add_argument('--cfp', type=str, default='filtered_annotated_event_logs_per_study', help="The name of the folder in which the event log files per case are stored")
  parser.add_argument("--ea", action="store_true", default=True, help="Exclude the annotated activities")
  args = parser.parse_args()

  log_folders = args.elfp
  output_folder_paths = args.ofp
  comparisons_to_execute = args.execute
  event_log_file_name = args.eln
  case_folder_name = args.cfp
  execution_name = args.name
  exclude_annotated = args.ea
  dataset_names = args.dsn

  if not log_folders or len(log_folders) <= 1:
    print('Add at least two event log folders to be compared')
    sys.exit(1)

  for path in output_folder_paths:
    os.makedirs(path, exist_ok=True)

  event_log_path_A = ''
  event_log_path_B = ''

  case_folder_path_A = ''
  case_folder_path_B = ''
  for log_folder in log_folders:
    if not os.path.exists(log_folder):
      raise FileNotFoundError(f"Path does not exist: {log_folder}")
    
    event_log_path = os.path.join(log_folder, event_log_file_name)
    if not os.path.exists(event_log_path):
      print(f'No event log is found on path {event_log_path}')
    elif not event_log_path_A:
      event_log_path_A = event_log_path
    elif not event_log_path_B:
      event_log_path_B = event_log_path
    else:
      print('I have found more than two event log files, currently I can only use two. Extend this module to use them all three')

    case_folder_path = os.path.join(log_folder, case_folder_name)
    if not os.path.exists(case_folder_path):
      print(f'No event log is found on path {case_folder_path}')
    elif not case_folder_path_A:
      case_folder_path_A = event_log_path
    elif not case_folder_path_B:
      case_folder_path_B = event_log_path
    else:
      print('I have found more than two case file folders, currently I can only use two. Extend this module to use them all three')

  event_log_file_paths = [event_log_path_A, event_log_path_B]

  # #############################################################################
  # PERFORMANCE COMPARISON
  # #############################################################################
  if len(comparisons_to_execute) == 0 or 'performance' in comparisons_to_execute:
    folder_paths = []
    for output_folder_path in output_folder_paths:
      folder_path = os.path.join(output_folder_path, 'performance_comparison')
      os.makedirs(folder_path, exist_ok=True)
      folder_paths.append(folder_path)

    print(' ----- Start performance comparison ----- ')
    dfs = []

    for file_path in event_log_file_paths:
      df = pd.read_csv(file_path)
      df[START_DATETIME_COLUMN_NAME] = pd.to_datetime(df[START_DATETIME_COLUMN_NAME], format=DATETIME_PATTERN)
      df[END_DATETIME_COLUMN_NAME] = pd.to_datetime(df[END_DATETIME_COLUMN_NAME], format=DATETIME_PATTERN)

      df["Duration"] = df[END_DATETIME_COLUMN_NAME] - df[START_DATETIME_COLUMN_NAME]
      duration_seconds = df["Duration"].dt.total_seconds()
      df["Duration_s"] = duration_seconds

      # Remove annotated activities if requested
      if exclude_annotated:
        df = df[
          ~df[ACTIVITY_COLUMN_NAME].str.match(r"^2_\d+", na=False)
        ]

      dfs.append(df)

    print(' ---- Start activity duration comparison ---- ')
    datasets_combined: pd.DataFrame = pd.concat(dfs, ignore_index=True)

    print('Get summary tables for activity durations')
    # The activity durations aggregated per case
    total_activity_durations: pd.DataFrame = (
      datasets_combined
      .groupby([DATASET_NAME_COLUMN_NAME, CASEID_COLUMN_NAME, ACTIVITY_COLUMN_NAME], as_index=False)["Duration_s"]
      .sum()
      .rename(columns={"Duration_s": "Total_Duration_s"})
    )

    total_activity_duration_summary: pd.DataFrame = (
      total_activity_durations
      .groupby([DATASET_NAME_COLUMN_NAME, ACTIVITY_COLUMN_NAME])["Total_Duration_s"]
      .agg(["min", "max", "mean", "median", "count"])
    )

    # The activity durations per execution
    average_activity_durations: pd.DataFrame = (
      datasets_combined
      .groupby([DATASET_NAME_COLUMN_NAME, ACTIVITY_COLUMN_NAME])["Duration_s"]
      .agg(["min", "max", "mean", "median", "count"])
    )

    for path in folder_paths:
      total_activity_duration_summary.to_csv(os.path.join(path, f"total-activity-duration_{execution_name}.csv"))
      average_activity_durations.to_csv(os.path.join(path, f"avg-activity-duration_{execution_name}.csv"))

    print('Create activity duration boxplots per activity')
    create_boxplots_per_activity_duration(
      dataframe=datasets_combined,
      execution_name=execution_name,
      duration_column_name= "Duration_s",
      metric_name="Average activity duration",
      activity_column_name=ACTIVITY_COLUMN_NAME,
      dataset_column_name=DATASET_NAME_COLUMN_NAME,
      output_folder_paths=folder_paths
    )

    create_boxplots_per_activity_duration(
      dataframe = total_activity_durations,
      execution_name=execution_name,
      duration_column_name="Total_Duration_s",
      metric_name="Total activity duration",
      activity_column_name=ACTIVITY_COLUMN_NAME,
      dataset_column_name=DATASET_NAME_COLUMN_NAME,
      output_folder_paths=folder_paths
    )

    print('Create log scaled boxplots for the activity durations')
    create_log_scaled_boxplot_activity_durations(
      dataframe= datasets_combined,
      execution_name=execution_name,
      duration_column_name= "Duration_s",
      metric_name="Average activity duration",
      activity_column_name=ACTIVITY_COLUMN_NAME,
      dataset_column_name=DATASET_NAME_COLUMN_NAME,
      output_folder_paths=folder_paths
    )

    create_log_scaled_boxplot_activity_durations(
      dataframe = total_activity_durations,
      execution_name=execution_name,
      duration_column_name="Total_Duration_s",
      metric_name="Total activity duration",
      activity_column_name=ACTIVITY_COLUMN_NAME,
      dataset_column_name=DATASET_NAME_COLUMN_NAME,
      output_folder_paths=folder_paths
    )

    print('Create linear scaled boxplots for the activity durations')
    create_linear_scaled_boxplot_activity_durations(
      dataframe= datasets_combined,
      execution_name=execution_name,
      duration_column_name= "Duration_s",
      metric_name="Average activity duration",
      activity_column_name=ACTIVITY_COLUMN_NAME,
      dataset_column_name=DATASET_NAME_COLUMN_NAME,
      output_folder_paths=folder_paths
    )

    create_linear_scaled_boxplot_activity_durations(
      dataframe = total_activity_durations,
      execution_name=execution_name,
      duration_column_name="Total_Duration_s",
      metric_name="Total activity duration",
      activity_column_name=ACTIVITY_COLUMN_NAME,
      dataset_column_name=DATASET_NAME_COLUMN_NAME,
      output_folder_paths=folder_paths
    )

    print('Create boxplots for each of the activity durations per activity')
    activities_sorted = datasets_combined[ACTIVITY_COLUMN_NAME].unique().tolist()

    for activity in activities_sorted:
      average_activity_data = datasets_combined[datasets_combined[ACTIVITY_COLUMN_NAME] == activity].copy()
      create_boxplot_for_activity_duration(
        activity_label=activity,
        activity_data = average_activity_data,
        execution_name=execution_name,
        duration_column_name="Duration_s",
        metric_name="Average activity duration",
        dataset_column_name=DATASET_NAME_COLUMN_NAME,
        output_folder_paths=folder_paths
      )

      total_activity_data = total_activity_durations[total_activity_durations[ACTIVITY_COLUMN_NAME] == activity].copy()
      create_boxplot_for_activity_duration(
        activity_label=activity,
        activity_data=total_activity_data,
        execution_name=execution_name,
        duration_column_name="Total_Duration_s",
        metric_name="Total activity duration",
        dataset_column_name=DATASET_NAME_COLUMN_NAME,
        output_folder_paths=folder_paths
      )
    
    print('Create stacked bar figure for each of the activity durations')
    create_stacked_bar_figure(
      dataframe= datasets_combined,
      execution_name=execution_name,
      duration_column_name= "Duration_s",
      metric_name="Average activity duration",
      activity_column_name=ACTIVITY_COLUMN_NAME,
      dataset_column_name=DATASET_NAME_COLUMN_NAME,
      output_folder_paths=folder_paths
    )

    create_stacked_bar_figure(
      dataframe = total_activity_durations,
      execution_name=execution_name,
      duration_column_name="Total_Duration_s",
      metric_name="Total activity duration",
      activity_column_name=ACTIVITY_COLUMN_NAME,
      dataset_column_name=DATASET_NAME_COLUMN_NAME,
      output_folder_paths=folder_paths
    )

    print('Create significance latex tables for activity durations')
    create_table_activity_durations(
      dataframe= datasets_combined,
      execution_name=execution_name,
      duration_column_name= "Duration_s",
      metric_name="Average activity duration",
      activity_column_name=ACTIVITY_COLUMN_NAME,
      dataset_column_name=DATASET_NAME_COLUMN_NAME,
      output_folder_paths=folder_paths
    )

    create_table_activity_durations(
      dataframe = total_activity_durations,
      execution_name=execution_name,
      duration_column_name="Total_Duration_s",
      metric_name="Total activity duration",
      activity_column_name=ACTIVITY_COLUMN_NAME,
      dataset_column_name=DATASET_NAME_COLUMN_NAME,
      output_folder_paths=folder_paths
    )

    print(' ---- Start trace duration comparison ---- ')
    trace_metrics_combined = (datasets_combined
                              .groupby(CASEID_COLUMN_NAME, dropna=False)
                              .apply(compute_trace_metrics, include_groups=False)
                              .reset_index()
    )
    complete_trace_metrics = datasets_combined.merge(
        trace_metrics_combined,
        on=CASEID_COLUMN_NAME,
        how="left"
    )

    summary_total = (complete_trace_metrics.groupby(DATASET_NAME_COLUMN_NAME)[f"total_duration_{TIME_UNITS}"]
      .agg(["count", "min", "max", "mean", "median"])
      .sort_index())    
    summary_inactive = (complete_trace_metrics.groupby(DATASET_NAME_COLUMN_NAME)[f"inactive_time_{TIME_UNITS}"]
      .agg(["count", "min", "max", "mean", "median"])
      .sort_index()) 
    summary_active = (complete_trace_metrics.groupby(DATASET_NAME_COLUMN_NAME)[f"active_time_{TIME_UNITS}"]
      .agg(["count", "min", "max", "mean", "median"])
      .sort_index()) 

    print('Save summary tables for metrics')
    for path in folder_paths:
      summary_total.to_csv(os.path.join(path, f"summary_total_duration_{execution_name}.csv"))
      summary_inactive.to_csv(os.path.join(path, f"summary_inactive_time_{execution_name}.csv"))
      summary_active.to_csv(os.path.join(path, f"summary_active_time_{execution_name}.csv"))

    print('Create boxplots for trace durations')
    create_boxplot_graph(
      dataframe=complete_trace_metrics,
      output_folder_paths=folder_paths,
      value_column=f'total_duration_{TIME_UNITS}',
      title=f"total_duration_{TIME_UNITS}_with_outliers",
      metric_name='Throughput time',
      execution_name=execution_name,
      show_outliers=True,
    )
    create_boxplot_graph(
      dataframe=complete_trace_metrics,
      output_folder_paths=folder_paths,
      value_column=f'total_duration_{TIME_UNITS}',
      title=f"total_duration_{TIME_UNITS}_without_outliers",
      execution_name=execution_name,
      metric_name='Throughput time',
      show_outliers=False,
    )

    create_boxplot_graph(
      dataframe=complete_trace_metrics,
      output_folder_paths=folder_paths,
      value_column=f'active_time_{TIME_UNITS}',
      title=f"active_time_{TIME_UNITS}_with_outliers",
      execution_name=execution_name,
      metric_name='Active time',
      show_outliers=True,
    )
    create_boxplot_graph(
      dataframe=complete_trace_metrics,
      output_folder_paths=folder_paths,
      value_column=f'active_time_{TIME_UNITS}',
      title=f"active_time_{TIME_UNITS}_without_outliers",
      execution_name=execution_name,
      metric_name='Active time',
      show_outliers=False,
    )

    create_boxplot_graph(
      dataframe=complete_trace_metrics,
      output_folder_paths=folder_paths,
      value_column=f'inactive_time_{TIME_UNITS}',
      title=f"inactive_time_{TIME_UNITS}_with_outliers",
      execution_name=execution_name,
      metric_name='Inactive time',
      show_outliers=True,
    )
    create_boxplot_graph(
      dataframe=complete_trace_metrics,
      output_folder_paths=folder_paths,
      value_column=f'inactive_time_{TIME_UNITS}',
      title=f"inactive_time_{TIME_UNITS}_without_outliers",
      execution_name=execution_name,
      metric_name='Inactive time',
      show_outliers=False,
    )

    print('Create latex table for trace durations')
    create_trace_duration_latex_table(
      dataframe = complete_trace_metrics,
      output_folder_paths = folder_paths,
      execution_name= execution_name,
    )

  # #############################################################################
  # BEHAVIOUR COMPARISON
  # ############################################################################# 
  if len(comparisons_to_execute) == 0 or 'behaviour' in comparisons_to_execute:
    folder_paths = []
    for output_folder_path in output_folder_paths:
      folder_path = os.path.join(output_folder_path, 'behaviour_comparison')
      os.makedirs(folder_path, exist_ok=True)
      folder_paths.append(folder_path)
    print(' ----- Start control-flow comparison ----- ')
    for index, process_comparator_config in enumerate(PROCESS_COMPARATOR_CONFIGS):
      print(f' ---- Start Process Comparator config {process_comparator_config.get("name", f"config_{index}")} ')
      pc_folder_paths = []
      for output_folder_path in folder_paths:
        folder_path = os.path.join(output_folder_path, process_comparator_config.get("name", f'config_{index}'))
        os.makedirs(folder_path, exist_ok=True)
        pc_folder_paths.append(folder_path)

      log1 = EventLogStore(event_log_path_A, CASEID_COLUMN_NAME, ACTIVITY_COLUMN_NAME, START_DATETIME_COLUMN_NAME)
      log2 = EventLogStore(event_log_path_B, CASEID_COLUMN_NAME, ACTIVITY_COLUMN_NAME, START_DATETIME_COLUMN_NAME)

      an = AnnotatedTransitionSystem()
      build_function_logs = an.build(
        L1=log1,
        L2=log2,
        rs=process_comparator_config["state_mapper"],
        ra=process_comparator_config["activity_mapper"],
        sm=process_comparator_config["state_measurement_mapper"],
        tm=process_comparator_config["transition_measurement_mapper"]
      )

      for folder_path in pc_folder_paths:
        an.visualize_with_annotations(
          os.path.join(folder_path, "annotated_transition_system.html")
        )

      summary, function_logs = an.determine_differences(
        significance_test=process_comparator_config["significance_test"],
        effect_size=process_comparator_config["effect_size_test"]
      )

      for folder_path in pc_folder_paths:
        an.export_comparisons_txt(os.path.join(folder_path, 'comparisons.txt'))
        an.visualize_significance(
          os.path.join(folder_path, "annotated_ts_significance.html")
        )
        an.visualize_significance_scaled(
          os.path.join(folder_path, "ats_significance_scaled.html"),
          mode='active_mode'
        )

    print(' ----- Start variant comparison -----')
    for index, file_path in enumerate(event_log_file_paths): 
      df = pd.read_csv(file_path)

      df = df[[START_DATETIME_COLUMN_NAME, END_DATETIME_COLUMN_NAME, CASEID_COLUMN_NAME, ACTIVITY_COLUMN_NAME]].copy()

      # Convert timestamps
      df[START_DATETIME_COLUMN_NAME] = pd.to_datetime(df[START_DATETIME_COLUMN_NAME], format=DATETIME_PATTERN, errors='coerce')
      df[END_DATETIME_COLUMN_NAME] = pd.to_datetime(df[END_DATETIME_COLUMN_NAME], format=DATETIME_PATTERN, errors='coerce')

      # Sort properly
      df = df.sort_values([CASEID_COLUMN_NAME, START_DATETIME_COLUMN_NAME])

      # BUILD FULL TRACE PER CASE
      case_traces = {}
      case_groups = dict(tuple(df.groupby(CASEID_COLUMN_NAME)))

      for case_id, group in case_groups.items():
        trace = tuple(group[ACTIVITY_COLUMN_NAME].tolist())
        case_traces[case_id] = trace
      
      # GROUP INTO VARIANTS
      variant_dict = defaultdict(list)

      for case_id, trace in case_traces.items():
          variant_dict[trace].append(case_id)
          
      # FILTER BY THRESHOLD
      variant_dict = {
        k: v for k, v in variant_dict.items()
        if len(v) >= MIMINUM_NUMBER_CASES_THRESHOLD
      }

      # SORT VARIANTS
      sorted_variants = sorted(
          variant_dict.items(),
          key=lambda x: len(x[1]),
          reverse=True
      )

      # CALCULATE DURATIONS PER CASE
      case_durations = {}

      for case_id, group in case_groups.items():
        sessions = extract_worksessions_with_time(group)

        total_duration = pd.Timedelta(0)

        for session in sessions:
          start_time = session[0][START_DATETIME_COLUMN_NAME]
          end_time = session[-1][END_DATETIME_COLUMN_NAME]

          if pd.notnull(start_time) and pd.notnull(end_time):
            total_duration += (end_time - start_time)

        # store duration in minutes
        case_durations[case_id] = total_duration.total_seconds() / 60

      result_df = build_variant_table(
        case_durations=case_durations,
        sorted_variants=sorted_variants,
      )

      result_df = result_df.sort_values(["Variant ID", "Worksession Number"])
      
      for path in folder_paths:
        output_file_path = os.path.join(path, f'variant_analysis_{dataset_names[index]}.txt') 
        with open(output_file_path, 'w', encoding="utf-8") as f:
          f.write(result_df.to_latex(index=False))

        output_file_path = os.path.join(path, f'variant_analysis_{dataset_names[index]}.csv') 
        result_df.to_csv(output_file_path, index=False, encoding="utf-8")

  # #############################################################################
  # HANDOVER COMPARISON
  # ############################################################################# 
  if len(comparisons_to_execute) == 0 or 'handover' in comparisons_to_execute:
    print(' ----- Start handover comparison ----- ')
    folder_paths = []
    for output_folder_path in output_folder_paths:
      folder_path = os.path.join(output_folder_path, 'handover_comparison')
      os.makedirs(folder_path, exist_ok=True)
      folder_paths.append(folder_path)

    output_lines = []
    table_rows = []
    for index, input_folder in enumerate(log_folders):
      folder_path = os.path.join(input_folder, case_folder_name)

      event_logs_per_study = []
      if exclude_annotated:
        file_paths = [
          os.path.join(folder_path, f) for f in os.listdir(folder_path)
        ]
        output_folder = os.path.join(input_folder, 'excluded_annotated_activities')
        os.makedirs(output_folder, exist_ok=True)
        for file_path in file_paths:
          file_name = os.path.basename(file_path)
          output_file_path = os.path.join(output_folder, file_name)
          filter_csv_by_prefix(
            input_file=file_path,
            output_file=output_file_path,
            column_name=ACTIVITY_COLUMN_NAME,
            pattern=r"^2_\d+[A-Za-z]*_.*"
          )
          event_logs_per_study.append(output_file_path)

      switch_count, switch_per_study, _ = count_switches_folder(
        file_paths=event_logs_per_study,
        column_name=RESOURCE_COLUMN_NAME,
        add_empty=False,
      )

      total_handovers = sum(switch_count.values())
      n_studies = len(event_logs_per_study)
      ratio = round(total_handovers / n_studies, 3) if n_studies > 0 else 0

      output_lines.append(f'Switch count for {dataset_names[index]}: {switch_count}')
      output_lines.append(f'Total switch count for {dataset_names[index]}: {sum(switch_count.values())}')

      table_rows.append(
        f'{dataset_names[index]} & {total_handovers} & {n_studies} & {ratio:.3f} \\\\'
      )
    create_handover_latex_table(
      table_rows=table_rows,
      output_folder_paths=folder_paths,
      execution_name=execution_name
    )
    for path in folder_paths:
      output_file_path = os.path.join(path, f'handover_analysis_{execution_name}.txt') 
      with open(output_file_path, 'w', encoding="utf-8") as f:
        f.write('\n'.join(output_lines))

      output_file_path = os.path.join(path, f'handover_analysis_{execution_name}.csv')
      df = pd.DataFrame([row.split(' & ') for row in table_rows], columns=['Dataset', 'Total Handovers', 'Number of Studies', 'Average Handovers per Study'])
      df.to_csv(output_file_path, index=False, encoding="utf-8")
