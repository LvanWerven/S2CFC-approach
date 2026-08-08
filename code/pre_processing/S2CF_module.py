
import argparse
import os
import re
from functools import partial


from pre_processing.S2CF_config import ACTIVITY_COLUMN_NAME, CASEID_COLUMN_NAME, DATASET_NAME_COLUMN_NAME, END_ACTIVITIES, REMOVED_STUDY_IDS, START_ACTIVITIES, START_DATETIME_COLUMN_NAME, DESCRIPTIVE_COLUMN_NAME, END_DATETIME_COLUMN_NAME, LINKING_REGISTRATION_MESSAGES, LOG_PATTERN, REGISTRATION_MESSAGES, REGISTRATION_MESSAGES, ACTIVITIES_MAP_EVENTS, ACTIVITIES_MAP_EVENTS, AUTOSEGMENTATION_SEQUENCE, LOADING_MESSAGES, RESOURCE_COLUMN_NAME, RESOURCE_PATTERN, SHUTDOWN_START_SEQUENCE, SHUTDOWN_START_SEQUENCE, STUDYID_PATTERN, SUBSTRING_PATTERNS
from pre_processing.utils.data_refining import annotate_all_csvs, filter_csv_by_prefix, filter_file, group_cases, merge_activity_events, merge_csv_files_in_folder, propagate_values_by_keywords, split_file_on_values
from pre_processing.utils.general_utils import _is_csv_file, add_identified_value_to_column, fill_column_for_all_rows, output_list_to_txt, recursive_apply_to_files
from pre_processing.utils.data_preparation import add_log_id_column, transform_data_recursive
from pre_processing.utils.event_abstraction import abstract_streaks_to_event_file, add_column_to_csv_file_mapping, add_events, annotate_phase_markers, change_value_in_timespan, convert_dict_to_tuple_dict, map_build_prefix_index, recursive_add_value_in_range

if __name__ == "__main__":
  print(' ----- Starting the S2CF module  ----- ')
  parser = argparse.ArgumentParser()
  parser.add_argument("--lfp", required=True, type=str, help="Complete path directing to folder with software execution event data files")
  parser.add_argument("--dsn", required=True, type=str, help="The name of the data set")
  parser.add_argument("--fn", nargs='+', default=[], help="Folder names in parent log folder that should be included")
  parser.add_argument("--wfp", required=True, type=str, help="Complete path directing to a folder in which the outputs will be saved")
  parser.add_argument("--rtp", default='', type=str, help="Complete path directing to a .txt file with the report times of the studies, if this is not provided no activities will be annotated")
  parser.add_argument("--pID", default=[], nargs='+', help="List of study ID's that should be included")
  parser.add_argument("--IMR", action="store_true", help="Include manual registration activity")
  parser.add_argument('--log', action='store_true', default=False, help="Create log files")
  parser.add_argument("--execute", nargs='+', default=[], help="The names of the steps (data preparation, event abstraction, and data refining) that should be executed, if empty it runs the whole module")
  args = parser.parse_args()

  # Get all the parameters ready for use in a readable variable
  logs_folder = args.lfp
  dataset_name = args.dsn
  folder_names_to_include = args.fn
  run_folder = args.wfp
  event_data_folder = os.path.join(run_folder, "event_data")
  event_logs_folder = os.path.join(run_folder, "event_logs")
  include_study_id = args.pID
  include_manual_registration_activity = args.IMR
  report_times_path = args.rtp
  steps_to_execute = args.execute

  if 'dp' in steps_to_execute or 'dataprep' in steps_to_execute or 'data prep' in steps_to_execute:
    steps_to_execute.append('data preparation')
  if 'ea' in steps_to_execute or 'eventabs' in steps_to_execute or 'event abs' in steps_to_execute:
    steps_to_execute.append('event abstraction')
  if 'dr' in steps_to_execute or 'dataref' in steps_to_execute or 'data ref' in steps_to_execute:
    steps_to_execute.append('data refining')

  # Create the necessary folders within the working folder "run_folder"
  if not os.path.exists(logs_folder):
    raise FileNotFoundError(f"Path does not exist: {logs_folder}")
  os.makedirs(event_data_folder, exist_ok=True)
  
  # #############################################################################
  # DATA PREPARATION
  # #############################################################################
  if len(steps_to_execute) == 0 or 'data preparation' in steps_to_execute:
    print('1. Data preparation')

    print('1.1 Transform data')
    transform_function_logs = transform_data_recursive(
      parent_folder_path=logs_folder,
      output_folder_path=event_data_folder,
      included_names = folder_names_to_include,
      pattern=LOG_PATTERN
    )

    add_resource_function_logs = []
    fill_resource_function_logs = []

    print('1.2 Add resource attribute')
    add_resource_to_column = partial(
      add_identified_value_to_column,
      column_name=RESOURCE_COLUMN_NAME,
      regex_pattern=RESOURCE_PATTERN,
      search_in_column_name=DESCRIPTIVE_COLUMN_NAME,
      function_logs = add_resource_function_logs
    )
    # Add resource to column based on regex pattern
    recursive_apply_to_files(
      folder_path=event_data_folder,
      file_handler=add_resource_to_column,
      file_filter = _is_csv_file,
      function_logs=add_resource_function_logs
    )

    add_resource_to_all_rows = partial(
      fill_column_for_all_rows,
      column_name=RESOURCE_COLUMN_NAME,
      function_logs=fill_resource_function_logs
    )

    # Fill resource column for all rows based on the first row of the file
    recursive_apply_to_files(
      folder_path=event_data_folder,
      file_handler=add_resource_to_all_rows,
      file_filter = _is_csv_file,
      function_logs=fill_resource_function_logs
    )

    print('1.3 Add Log ID')
    add_log_id_column(
      folder_path=event_data_folder
    )

    if args.log:
      execution_logs_path = os.path.join(run_folder, "execution_logs")
      os.makedirs(execution_logs_path, exist_ok=True)
      output_list_to_txt(transform_function_logs, execution_logs_path, f'transform_function_logs.txt')
      output_list_to_txt(add_resource_function_logs, execution_logs_path, f'add_resource_function_log.txt')
      output_list_to_txt(fill_resource_function_logs, execution_logs_path, f'fill_resource_function_logs.txt')

  # #############################################################################
  # EVENT ABSTRACTION
  # #############################################################################
  if len(steps_to_execute) == 0 or 'event abstraction' in steps_to_execute:
    print('2. Event abstraction')
    os.makedirs(event_logs_folder, exist_ok=True)


    print('2.1 Apply streak recognition')
    # Build streak map for autosegmentation activity sequence
    processed_streak_map_5 = convert_dict_to_tuple_dict(
      str_str_dict = AUTOSEGMENTATION_SEQUENCE,
      seperator = '-BREAK-',
      remove_last_item=False
    )
    prefixed_map_5 = map_build_prefix_index(
      map=processed_streak_map_5
    )
    # Apply streak recognition to identify the autosegmentation sequence in the event logs
    abstract_streak_activity5_function = partial(
      abstract_streaks_to_event_file,
      map_prebuild_index=prefixed_map_5,
      map_seq_to_id=processed_streak_map_5,
      output_folder_path=event_logs_folder,
      match_mode='sequential', 
      track_possible=False,
      show_directly=False
    )

    function_logs_abstract_streak_step5 = recursive_apply_to_files(
      folder_path=event_data_folder,
      file_handler=abstract_streak_activity5_function,
      file_filter=_is_csv_file,
      function_logs=[]
    )

    # Build streak map for start sequence of shutdown activity
    processed_streak_map_7 = convert_dict_to_tuple_dict(
      str_str_dict = SHUTDOWN_START_SEQUENCE,
      seperator = '-BREAK-',
      remove_last_item=False
    )
    prefixed_map_7 = map_build_prefix_index(
      map=processed_streak_map_7
    )
    # Apply streak recognition to identify the start sequence of shutdown activity in the event logs
    abstract_streak_activity7_function = partial(
      abstract_streaks_to_event_file,
      map_prebuild_index=prefixed_map_7,
      map_seq_to_id=processed_streak_map_7,
      output_folder_path=event_logs_folder,
      match_mode='ordered', 
      track_possible=True,
      show_directly=False
    )

    function_logs_abstract_streak_step7 = recursive_apply_to_files(
      folder_path=event_logs_folder,
      file_handler=abstract_streak_activity7_function,
      file_filter=_is_csv_file,
      function_logs=[]
    )

    print('2.2 Apply event mapping')
    event_mapping_function = partial(
      add_column_to_csv_file_mapping,
      column_name=ACTIVITY_COLUMN_NAME,
      key_column=DESCRIPTIVE_COLUMN_NAME,
      map=ACTIVITIES_MAP_EVENTS,
      direct_map=False,
      output_folder_path=event_logs_folder
    )

    event_mapping_function_logs = recursive_apply_to_files(
      folder_path=event_logs_folder,
      file_handler=event_mapping_function,
      file_filter=_is_csv_file,
      function_logs=[]
    )

    print('2.3 Remove false identification')
    # Remove the 6_ activity identification that is added after the 3_ activity identification, since this is post processing of the 3_ activity and not a separate activity.
    remove_6_identification_after_3_function_logs = []
    remove_6_identification_after_3 = partial(
      change_value_in_timespan,
      time_column=START_DATETIME_COLUMN_NAME,
      range_column=ACTIVITY_COLUMN_NAME,
      range_values=["3_Automatic_rigid"],
      value_regex=r"^6_",
      timespan=1,
      change_column=ACTIVITY_COLUMN_NAME,
      to_change_value="6_Perform_segmentation",
      new_change_value="3_Automatic_rigid",
      datetime_format="%d %b %Y %H:%M:%S,%f",
      function_logs = remove_6_identification_after_3_function_logs
    )

    recursive_apply_to_files(
      folder_path=event_logs_folder,
      file_handler=remove_6_identification_after_3,
      file_filter = _is_csv_file,
      function_logs=remove_6_identification_after_3_function_logs
    )

    # Remove the 6_ activity identification that is added after starting registration if there are segments available.
    remove_6_identification_after_opening_registration = partial(
      change_value_in_timespan,
      time_column=START_DATETIME_COLUMN_NAME,
      range_column=DESCRIPTIVE_COLUMN_NAME,
      range_values= LINKING_REGISTRATION_MESSAGES,
      value_regex=r"^6_",
      timespan=1,
      change_column=ACTIVITY_COLUMN_NAME,
      to_change_value="6_Perform_segmentation",
      new_change_value="",
      datetime_format="%d %b %Y %H:%M:%S,%f",
      function_logs = remove_6_identification_after_3_function_logs
    )

    recursive_apply_to_files(
      folder_path=event_logs_folder,
      file_handler=remove_6_identification_after_opening_registration,
      file_filter = _is_csv_file,
      function_logs=remove_6_identification_after_3_function_logs
    )

    print('2.4 Apply range recognition')
    _, add_activity_4_function_logs = recursive_add_value_in_range(
      parent_folder_path=event_logs_folder,
      output_folder_path=event_logs_folder,
      value_to_add="4_Manual_rigid",
      target_column=ACTIVITY_COLUMN_NAME,
      range_column= DESCRIPTIVE_COLUMN_NAME,
      from_values = REGISTRATION_MESSAGES['START_MESSAGES'],
      till_values=REGISTRATION_MESSAGES['END_MESSAGES'],
      extra_row_condition= {ACTIVITY_COLUMN_NAME: r"^6_"},
      till_value_inclusive= False,
      from_value_inclusive= False,
      exit_when_not_empty=[],
      overwrite_if_filled=False,
      overwrite_exceptions_prefixes = ['6'],
      scan_direction = 'forward',
      substring_patterns=SUBSTRING_PATTERNS,
      function_logs= [],
    ) 

    _, add_activity_2_function_logs = recursive_add_value_in_range(
      parent_folder_path=event_logs_folder,
      output_folder_path=event_logs_folder,
      value_to_add="2_Loading_study_data",
      target_column=ACTIVITY_COLUMN_NAME,
      range_column= DESCRIPTIVE_COLUMN_NAME,
      from_values = LOADING_MESSAGES['START_MESSAGES'],
      till_values=LOADING_MESSAGES['END_MESSAGES'],
      till_value_inclusive= False,
      from_value_inclusive= True,
      exit_when_not_empty=[],
      overwrite_if_filled=True,
      scan_direction = 'forward',
      substring_patterns=SUBSTRING_PATTERNS,
      function_logs= [],
    )

    # Add the 1_Startup activity to the Activity column from the start of a file until another activity is identified.
    _, add_activity_1_function_logs = recursive_add_value_in_range(
      parent_folder_path=event_logs_folder,
      output_folder_path=event_logs_folder,
      value_to_add='1_Startup',
      target_column=ACTIVITY_COLUMN_NAME,
      from_value_inclusive=True,
      till_value_inclusive = False,
      exit_when_not_empty= [ACTIVITY_COLUMN_NAME],
      function_logs=[],
      print_output_function_log=False,
      substring_patterns=SUBSTRING_PATTERNS,
    )

    # Add the 1_Startup activity to the Activity column from the identification of an "extra" start of a session mid log file
    _, add_activity_1_function_logs = recursive_add_value_in_range(
      parent_folder_path=event_logs_folder,
      output_folder_path=event_logs_folder,
      value_to_add='1_Startup',
      target_column=ACTIVITY_COLUMN_NAME,
      range_column=ACTIVITY_COLUMN_NAME,
      from_values=["1_Startup"],
      from_value_inclusive=True,
      till_value_inclusive = False,
      exit_when_not_empty= [ACTIVITY_COLUMN_NAME],
      function_logs=[],
      print_output_function_log=False,
      substring_patterns=SUBSTRING_PATTERNS,
    )

    _, add_activity_0A_function_logs = recursive_add_value_in_range(
      parent_folder_path=event_logs_folder,
      output_folder_path=event_logs_folder,
      value_to_add='0A_Error',
      target_column=ACTIVITY_COLUMN_NAME,
      range_column=ACTIVITY_COLUMN_NAME,
      from_values=["0A_Error"],
      from_value_inclusive=True,
      till_value_inclusive = True,
      function_logs=[],
      print_output_function_log=False,
      substring_patterns=SUBSTRING_PATTERNS,
    )

    missed_files, add_activity_7_function_logs = recursive_add_value_in_range(
      parent_folder_path=event_logs_folder,
      output_folder_path=event_logs_folder,
      value_to_add='7_Shutdown',
      target_column=ACTIVITY_COLUMN_NAME,
      range_column=ACTIVITY_COLUMN_NAME,
      from_value_inclusive = True,
      from_values = ["7_Shutdown"],
      till_values = ["7_Shutdown"],
      overwrite_if_filled=False,
      overwrite_exceptions_prefixes=['0A'],
      function_logs=[],
      print_output_function_log=False,
      substring_patterns=SUBSTRING_PATTERNS,
    )

    print('2.5 Add artificial shutdown')
    for file_path in missed_files:
      add_events(
        file_path=file_path,
        columns_to_copy=[START_DATETIME_COLUMN_NAME, RESOURCE_COLUMN_NAME, "Log ID"],
        values_to_add= {ACTIVITY_COLUMN_NAME: "0B_Abrupt_End_Error"}
      )

    print('2.6 Identify start and end activities')
    annotate_function = partial(
      annotate_phase_markers,
      output_folder_path=event_logs_folder,
      threshold=2,
      include_not_mapped_phase=False,
      marker_column="Activity Marker",
      phase_column=ACTIVITY_COLUMN_NAME,
      marker_joiner="_",
      phase_prefix=["1", "2", "3", "4", "5", "6", "7", "0A", "0B"],
    )

    annotate_function_logs = recursive_apply_to_files(
      folder_path=event_logs_folder,
      file_filter=_is_csv_file,
      file_handler=annotate_function,
      function_logs=[]
    )
    
    if not include_manual_registration_activity:
      print('Remove manual registration activity')
      # Remove the activity markers with prefix 4, since these are based on the manual registration activity which is not always present and therefore not a good indicator for the phase.
      _, remove_activity_markers_4 = recursive_add_value_in_range(
        parent_folder_path=event_logs_folder,
        output_folder_path=event_logs_folder,
        value_to_add='',
        target_column='Activity Marker',
        range_column=ACTIVITY_COLUMN_NAME,
        from_value_inclusive = True,
        from_values = [],
        till_values = [],
        overwrite_if_filled=False,
        overwrite_exceptions_prefixes=['4'],
        function_logs=[],
        print_output_function_log=False,
        substring_patterns=SUBSTRING_PATTERNS,
      )

    if args.log:
      execution_logs_path = os.path.join(run_folder, "execution_logs")
      output_list_to_txt(function_logs_abstract_streak_step5, execution_logs_path, f'abstract_streaks_function_log_step5.txt')
      output_list_to_txt(function_logs_abstract_streak_step7, execution_logs_path, f'abstract_streaks_function_log_step7.txt')
      output_list_to_txt(event_mapping_function_logs, execution_logs_path, f"event_mapping_function_logs.txt")
      output_list_to_txt(add_activity_4_function_logs, execution_logs_path, f"add_activity_4_function_logs.txt")
      output_list_to_txt(add_activity_1_function_logs, execution_logs_path, f'add_activity_1_function_logs.txt')
      output_list_to_txt(add_activity_0A_function_logs, execution_logs_path, f'add_activity_0A_function_logs.txt')
      add_activity_7_function_logs.append('Missed files:')
      add_activity_7_function_logs.extend(missed_files)
      output_list_to_txt(add_activity_7_function_logs, execution_logs_path, f'add_activity_7_function_logs.txt')

  # #############################################################################
  # DATA REFINING
  # #############################################################################
  if len(steps_to_execute) == 0 or 'data refining' in steps_to_execute:
    print('3. Data refining')

    print('3.1 Add Case ID')
    # Add identified Study ID to the Study ID column based on the regex pattern
    find_study_id_function = partial(
      add_identified_value_to_column,
      column_name=CASEID_COLUMN_NAME,
      regex_pattern=STUDYID_PATTERN,
      search_in_column_name=DESCRIPTIVE_COLUMN_NAME,
    )

    find_study_id_function_logs = recursive_apply_to_files(
      folder_path=event_logs_folder,
      file_handler=find_study_id_function,
    )

    # Add added Study ID to the Study ID column for all rows in the file between the start and end of a worksession, based on the Activity Marker column.
    propagate_studyid_by_keywords = partial(
      propagate_values_by_keywords,
      from_keywords=START_ACTIVITIES,
      till_keywords=END_ACTIVITIES,
      value_column=CASEID_COLUMN_NAME,
      keywords_column="Activity Marker"
    )
    print('Split files on start and end of worksession')
    fill_studyids_function_logs = []
    recursive_apply_to_files(
      folder_path=event_logs_folder,
      file_handler=propagate_studyid_by_keywords,
      file_filter = _is_csv_file,
      function_logs=fill_studyids_function_logs
    )

    split_file_function = partial(
      split_file_on_values,
      split_before_value='1_Startup_start',
      split_after_value='7_Shutdown_end',
      value_column='Activity Marker',
      delete_parent_file=True
    )

    fill_studyids_function_logs = []
    split_file_on_value_function_logs = recursive_apply_to_files(
      folder_path=event_logs_folder,
      file_handler=split_file_function,
      file_filter = _is_csv_file,
      function_logs=fill_studyids_function_logs
    )

    print('Remove edge cases and merge files')
    event_log_file_path = os.path.join(run_folder, 'clinically_enhanced_event_log.csv')
    # Remove the studies that are excluded from the analysis based on the list of study IDs in the .env file.
    remove_studies_function_logs = merge_csv_files_in_folder(
      folder_path=event_logs_folder,
      output_file=event_log_file_path,
      filter_column=CASEID_COLUMN_NAME,
      kept_values=include_study_id,
      removed_values=REMOVED_STUDY_IDS,
      delete_skipped_files=True,
      remove_if_missing_study_id=True
    )

    # From here on there is one event log file with all the events of the included studies.
    # event log path = event_log_file_path

    # However, since we want to annotate the event logs of a study using the report time, we merge the seperate files in the event_log folder per study ID.
    print(f'Merge event logs by {CASEID_COLUMN_NAME}')
    grouped_study_logs_folder = os.path.join(run_folder, 'grouped_per_case')
    os.makedirs(grouped_study_logs_folder, exist_ok=True)
    _, group_cases_function_logs = group_cases(
      folder_path=event_logs_folder,
      id_pattern=re.compile(r'\bID\s*(\d+)\b'),
      output_folder_path=grouped_study_logs_folder,
    )

    print('3.2 Filter non-phase events')
    filtered_study_logs_folder = os.path.join(run_folder, 'filtered_per_case')
    os.makedirs(filtered_study_logs_folder, exist_ok=True)
    filter_file_function = partial(
      filter_file,
      columns_to_delete=[DESCRIPTIVE_COLUMN_NAME, 'FunctionCall'],
      output_folder_path=filtered_study_logs_folder,
    )
    function_logs_filter_files = recursive_apply_to_files(
      folder_path=grouped_study_logs_folder,
      file_filter=_is_csv_file,
      file_handler=filter_file_function
    )

    print('3.3 Merge start + end events')
    end_time_folder = os.path.join(run_folder, 'filtered_annotated_event_logs_per_case')
    os.makedirs(end_time_folder, exist_ok=True)
    merge_activity_events_function = partial(
      merge_activity_events,
      start_datetime_column_name=START_DATETIME_COLUMN_NAME,
      end_datetime_column_name=END_DATETIME_COLUMN_NAME,
      identify_start_end_activities_column_name='Activity Marker',
      output_folder=end_time_folder
    )
    function_logs_add_end_time = recursive_apply_to_files(
      folder_path=filtered_study_logs_folder,
      file_filter=_is_csv_file,
      file_handler=merge_activity_events_function
    )

    print('3.4 Annotate post-report activity')
    end_folder_path = end_time_folder
    if report_times_path:
      annotated_report_time_folder = os.path.join(run_folder, 'filtered_annotated_event_logs_per_case')
      os.makedirs(annotated_report_time_folder, exist_ok=True)
      annotate_all_csvs(
        folder_path=end_time_folder,
        studyID_to_report_time_file_path=report_times_path,
        output_folder_path=annotated_report_time_folder
      )
      end_folder_path = annotated_report_time_folder
    else:
      print('No report times provided, skipping annotation of post-report activity')

    print('Add dataset name as attribute')
    _, add_dataset_name_function_logs = recursive_add_value_in_range(
      parent_folder_path=end_folder_path,
      output_folder_path=end_folder_path,
      value_to_add=dataset_name,
      target_column=DATASET_NAME_COLUMN_NAME,
      range_column=DATASET_NAME_COLUMN_NAME,
      from_value_inclusive=True,
      till_value_inclusive = True,
      overwrite_if_filled=False,
      function_logs=[],
      print_output_function_log=False,
    )

    print('Merge event logs')
    merge_csv_files_in_folder(
      folder_path=os.path.join(end_folder_path),
      output_file=os.path.join(run_folder, "event_log_V2_annotated.csv"),
    )

    filter_csv_by_prefix(
      input_file=os.path.join(run_folder, "event_log_V2_annotated.csv"),
      output_file=os.path.join(run_folder, "event_log_removed_V2.csv"),
      column_name=ACTIVITY_COLUMN_NAME,
      pattern=r"^2_\d+[A-Za-z]*_.*"
    )

    print(' ----- Finishing the S2CF module  ----- ')
    
    if args.log:
      execution_logs_path = os.path.join(run_folder, "execution_logs")
      output_list_to_txt(find_study_id_function_logs, execution_logs_path, f'find_study_id_function_logs.txt')
      output_list_to_txt(fill_studyids_function_logs, execution_logs_path, f'fill_studyids_function_logs.txt')
      output_list_to_txt(remove_studies_function_logs, execution_logs_path, f'merge_function_logs.txt')
      output_list_to_txt(group_cases_function_logs, execution_logs_path, f'group_cases_function_logs.txt')
      output_list_to_txt(function_logs_filter_files, execution_logs_path, f'function_logs_filter_files.txt')
      output_list_to_txt(function_logs_add_end_time, execution_logs_path, f'function_logs_add_end_time.txt')
      output_list_to_txt(add_dataset_name_function_logs, execution_logs_path, f'add_dataset_name_function_logs.txt')
      output_list_to_txt(split_file_on_value_function_logs, execution_logs_path, f'split_file_on_value_function_logs.txt')
      
