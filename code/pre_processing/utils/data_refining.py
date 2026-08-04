
from collections import defaultdict
import csv
from datetime import datetime
from functools import partial
import glob
import os
import re
import string
from typing import List

import pandas as pd

from pre_processing.S2CF_config import ACTIVITY_COLUMN_NAME, CASEID_COLUMN_NAME, START_DATETIME_COLUMN_NAME, DATETIME_PATTERN, DESCRIPTIVE_COLUMN_NAME
from pre_processing.utils.general_utils import _is_csv_file, fill_column_for_all_rows, recursive_apply_to_files

# Add the case ID to one worksession 
def propagate_values_by_keywords(
    input_file_path: str,
    output_file_path: str | None = None,
    from_keywords: list[str] = [],
    till_keywords: list[str] = [],
    value_column: str = "",
    keywords_column: str = ""
):
    df = pd.read_csv(input_file_path)

    # Normalize keyword lists
    from_keywords = [k.lower() for k in from_keywords]
    till_keywords = [k.lower() for k in till_keywords]

    output_values = [None] * len(df)
    current_value = None

    # ---------- FORWARD + BACKWARD PROPAGATION ----------
    for idx in range(len(df)):
        row = df.iloc[idx]
        event_text = str(row[keywords_column]).lower()
        row_value = row[value_column]

        # Detect new value
        if pd.notna(row_value):
            current_value = row_value

            # ---- BACKWARD FILL UNTIL from_keyword ----
            back_idx = idx - 1
            while back_idx >= 0:
                prev_event = str(df.loc[back_idx, keywords_column]).lower()

                # Do **not** overwrite existing values
                if output_values[back_idx] is not None:
                    break

                # Stop if we hit a "from keyword" boundary
                if any(k in prev_event for k in from_keywords):
                    output_values[back_idx] = current_value
                    break

                # Fill empty row
                output_values[back_idx] = current_value
                back_idx -= 1

        # Detect till_keywords (stop section)
        if any(k in event_text for k in till_keywords):
            output_values[idx] = current_value
            current_value = None
            continue

        # Forward-fill
        output_values[idx] = current_value

    df[value_column] = output_values

    # Write output
    if not output_file_path:
        output_file_path = input_file_path

    df.to_csv(output_file_path, index=False)
    return df

# Merge all the csv's in one folder to one file using several filters
def merge_csv_files_in_folder(
  folder_path: str,
  output_file: str,
  filter_column: str = "",
  kept_values: list[str] = [],
  removed_values: list[str] = [],
  delete_skipped_files: bool = False,
  sorted: bool = False,
  remove_if_missing_study_id: bool = False,
  study_id_column: str = CASEID_COLUMN_NAME,
  datetime_column: str = START_DATETIME_COLUMN_NAME
) -> list[str]:

  csv_files = glob.glob(os.path.join(folder_path, "*.csv"))
  output_filepath = os.path.abspath(output_file)

  dataframes = []
  skipped_files = 0
  kept_files = 0
  total_files = 0
  function_logs = []

  # Normalize sets
  kept_set = {str(v).strip().lower() for v in kept_values}
  removed_set = {str(v).strip().lower() for v in removed_values}

  function_logs.append(f"kept_values: {kept_set}")
  function_logs.append(f"removed_values: {removed_set}")

  for file_path in csv_files:
    if os.path.abspath(file_path) == output_filepath:
      continue

    try:
      df = pd.read_csv(file_path)
      total_files += 1

      if remove_if_missing_study_id:

        if study_id_column not in df.columns:
          skipped_files += 1
          function_logs.append(f"⛔ Skipped (no '{study_id_column}' column): {os.path.basename(file_path)}")
          if delete_skipped_files:
            os.remove(file_path)
            function_logs.append(f"🗑️ Deleted: {os.path.basename(file_path)}")
          continue

        # Normalize ID column (stringify)
        study_id_series = (
          df[study_id_column]
          .dropna()
          .astype(str)
          .str.strip()
          .str.lower()
        )
        function_logs.append(f"Study Id series: {study_id_series}")

        if study_id_series.empty:
          skipped_files += 1
          function_logs.append(f"⛔ Skipped (no Study ID values): {os.path.basename(file_path)}")
          if delete_skipped_files:
            os.remove(file_path)
            function_logs.append(f"🗑️ Deleted: {os.path.basename(file_path)}")
          continue

      # Apply kept/removed filtering
      if filter_column and (kept_set or removed_set):
        series_norm = (
          df[filter_column]
          .astype(str)
          .str.strip()
          .str.lower()
          .dropna()
        )
        values_in_file = set(series_norm.unique())

        function_logs.append(f"{os.path.basename(file_path)} → values: {values_in_file}")

        # Removed-values check
        if removed_set and (values_in_file & removed_set):
          skipped_files += 1
          function_logs.append(f"⛔ Skipped (contains removed value): {os.path.basename(file_path)}")
          if delete_skipped_files:
            os.remove(file_path)
            function_logs.append(f"🗑️  Deleted: {os.path.basename(file_path)}")
          continue

        # Kept-values check
        if kept_set and not (values_in_file & kept_set):
          skipped_files += 1
          function_logs.append(f"⏭️  Skipped (missing kept value): {os.path.basename(file_path)}")
          if delete_skipped_files:
            os.remove(file_path)
            function_logs.append(f"🗑️  Deleted: {os.path.basename(file_path)}")
          continue

      # File is accepted
      dataframes.append(df)
      kept_files += 1
      function_logs.append(f"✅ Loaded: {os.path.basename(file_path)} ({len(df)} rows)")

    except Exception as e:
      function_logs.append(f"❌ Failed to read {os.path.basename(file_path)}: {e}")

  # Merge output
  if dataframes:
    merged_df = pd.concat(dataframes, ignore_index=True)

    if sorted:
      merged_df[datetime_column] = pd.to_datetime(
        merged_df[datetime_column],
        format="%Y-%m-%d %H:%M:%S",
        errors="coerce"
      )
      merged_df = merged_df.sort_values(by=datetime_column)

    merged_df.to_csv(output_file, index=False)
    function_logs.append(f"\n🎉 Merged {kept_files} files into: {output_file} ({len(merged_df)} rows)")
  else:
    function_logs.append("⚠️ No valid CSV files found to merge.")

  function_logs.append(
    f"total={total_files}, skipped={skipped_files}, kept={kept_files}"
  )

  return function_logs

def extract_case_id_from_message(
  folder_path: str, 
  id_pattern: re.Pattern,
  function_logs: list[str] = [],
  build_study_to_files_map: bool = False,
  caseId_column_name= CASEID_COLUMN_NAME,
  descriptive_column_name=DESCRIPTIVE_COLUMN_NAME
):
  '''Extracts Study ID from the Message column and adds it to a new Study ID column in each CSV file in the folder.'''
  study_to_files = defaultdict(set)

  for filename in os.listdir(folder_path):
    if filename.endswith('.csv'):
      file_path = os.path.join(folder_path, filename)
      rows = []

      with open(file_path, 'r', encoding='utf-8') as infile:
        reader = csv.DictReader(infile)
        fieldnames = list(reader.fieldnames or [])

        # Add caseId_column_name column if it doesn't exist
        if caseId_column_name not in fieldnames:
          fieldnames.append(caseId_column_name)

        row_index = 0
        for row in reader:
          message = row.get(descriptive_column_name, '')
          match = id_pattern.search(message)
          if match:
            row[caseId_column_name] = match.group(1)
            function_logs.append(f'In file "{filename}", found study ID: {match.group(1)}, in row {row_index}: "{row}')
            if build_study_to_files_map:
              study_to_files[match.group(1)].add(filename)
          else:
            # Leave existing Study ID or empty if none
            row[caseId_column_name] = row.get(caseId_column_name, '')
          row_index += 1
          rows.append(row)

        # Write updated rows back to CSV
        with open(file_path, 'w', newline='', encoding='utf-8') as outfile:
          writer = csv.DictWriter(outfile, fieldnames=fieldnames)
          writer.writeheader()
          writer.writerows(rows)

        function_logs.append(f"✅ Extracted Study ID from Message in: {filename}")
  return function_logs, study_to_files

# Group files with the same case ID's together
def group_cases(
  folder_path: str,
  id_pattern: re.Pattern,
  output_folder_path: str,
  include_study_ids: list[str] = [],
  build_study_to_files_map: bool = True
):
  extract_function_logs, study_to_files_map = extract_case_id_from_message(
    folder_path=folder_path,
    id_pattern=id_pattern,
    build_study_to_files_map=build_study_to_files_map
  )

  add_caseid_to_all_rows = partial(
    fill_column_for_all_rows,
    column_name=CASEID_COLUMN_NAME,
  )
  extract_function_logs = recursive_apply_to_files(
    folder_path=folder_path,
    file_handler=add_caseid_to_all_rows,
    file_filter = _is_csv_file,
    function_logs=extract_function_logs
  )

  for study_id, files in study_to_files_map.items():
    if len(include_study_ids) == 0 or study_id in include_study_ids:
      merge_csv_files(
        folder_path=folder_path,
        output_file_path=os.path.join(output_folder_path, f'merged_event_data_{study_id}.csv'),
        file_names=list(files)
      )
  return study_to_files_map, extract_function_logs


def merge_csv_files(
  folder_path: str,
  output_file_path: str,
  file_names: list[str],
  print_str: bool = False,
):
  "Merges the specified CSV files in the folder into one DataFrame and saves it to output_file_path."
  "Uses the timestamp in the filename to sort the files chronologically before merging."

  def _extract_datetime(file_name: str) -> datetime:
    match = re.search(r'(\d{4}-\d{2}-\d{2}-\d{6})', file_name)
    if match:
      return datetime.strptime(match.group(1), "%Y-%m-%d-%H%M%S")

    # fallback so type checker is happy
    return datetime.min

  sorted_file_names = sorted(file_names, key=_extract_datetime)
  file_paths = [os.path.join(folder_path, f) for f in sorted_file_names]
  dataframes = []
  for file_path in file_paths:
    try:
      df = pd.read_csv(file_path)
      dataframes.append(df)
      if print_str:
        print(f"✅ Loaded: {os.path.basename(file_path)} ({len(df)} rows)")
    except Exception as e:
      if print_str:
        print(f"❌ Failed to read {os.path.basename(file_path)}: {e}")

  if dataframes:
    merged_df = pd.concat(dataframes, ignore_index=True)
    merged_df.to_csv(output_file_path, index=False)
    if print_str:
      print(f"\n🎉 Merged {len(file_names)} files into: {output_file_path} ({len(merged_df)} rows)")


def filter_file(
  file_path: str, 
  output_folder_path: str, 
  columns_to_delete: list[str]
) -> str:
  file_name = os.path.basename(file_path)
  output_file_path = os.path.join(output_folder_path, file_name)

  os.makedirs(output_folder_path, exist_ok=True)

  with open(file_path, 'r', encoding='utf-8', newline='') as infile, open(output_file_path, 'w', newline='') as outfile:
    reader = csv.DictReader(infile)
    fieldnames = list(reader.fieldnames) if reader.fieldnames else []
    fieldnames = [f for f in fieldnames if f not in columns_to_delete]

    writer = csv.DictWriter(outfile, fieldnames=fieldnames)
    writer.writeheader()

    for row in reader:
      phase_marker = row['Activity Marker']
      if phase_marker != '':
        for column_to_delete in columns_to_delete:
          row.pop(column_to_delete, None)
        writer.writerow(row)
  return output_file_path

# #############################################################################
# Split files if there are two studies in one file
# #############################################################################
def split_file_on_values(
  input_file: str,
  split_before_value: str,
  split_after_value: str,
  value_column: str,
  delete_parent_file=False
) -> List[str]:
  """_
  Splits a CSV file into multiple CSV files.
  Each new file begins at `split_before_value`
  and ends at the next occurrence of `split_after_value`.
  
  New files are stored in the SAME folder as the input file, and named:
      <original_name>_A.csv, <original_name>_B.csv, ...
  
  Parameters
  ----------
  input_file : str
      Path to the CSV file.
      
  split_before_value : str
      Marker indicating the start of a segment.
      
  split_after_value : str
      Marker indicating the end of a segment.
      
  value_column : str
      Column name where markers are found.
      
  delete_parent_file : bool
      If True, deletes the original input CSV after splitting.
  """
  function_logs = []
  # Read input CSV
  df = pd.read_csv(input_file)

  # Prepare file paths
  folder = os.path.dirname(input_file)
  basename = os.path.basename(input_file)
  filename_no_ext, _ = os.path.splitext(basename)

  segments = []
  current_segment = []
  is_collecting = False

  # Main splitting logic
  for _, row in df.iterrows():
    marker = str(row[value_column]).strip()

    # Start a new segment
    if marker == split_before_value:
      if current_segment:
        segments.append(pd.DataFrame(current_segment))
        current_segment = []
      is_collecting = True

    if is_collecting:
      current_segment.append(row)

    # End segment
    if marker == split_after_value and is_collecting:
      segments.append(pd.DataFrame(current_segment))
      current_segment = []
      is_collecting = False

  # If file ends mid-segment, save it too
  if current_segment:
    segments.append(pd.DataFrame(current_segment))

  # Save segments with A, B, C... suffixes
  letters = list(string.ascii_uppercase)

  for i, seg in enumerate(segments):
    suffix = letters[i] if i < len(letters) else f"_{i+1}"
    out_name = f"{filename_no_ext}_{suffix}.csv"
    out_path = os.path.join(folder, out_name)

    seg.to_csv(out_path, index=False)
    function_logs.append(f"✅ Saved: {out_path}")

  # Optionally delete input file
  if delete_parent_file:
    os.remove(input_file)
    function_logs.append(f"Deleted parent file: {input_file}")

  function_logs.append(f"✅ Done! Created {len(segments)} files.")
  return function_logs

# #############################################################################
# ANNOTATE POST-REPORT ACTIVITIES
# #############################################################################
def annotate_all_csvs(studyID_to_report_time_file_path, folder_path, output_folder_path: str = ''):
  """
  Main function:
  - loads trigger times
  - iterates through all CSVs in folder
  - annotates them in place
  """

  trigger_times = load_trigger_times(studyID_to_report_time_file_path)
  # print(f'trigger_time keys: {trigger_times}')
  for filename in os.listdir(folder_path):
    if filename.startswith("merged_event_data") and filename.endswith(".csv"):
      csv_path = os.path.join(folder_path, filename)
      annotate_csv_file(csv_path, trigger_times, output_folder_path)

  print("✔ Annotation complete!")

# Create a dictionary (Case ID, report upload time) from a .txt file case ID; report upload time
def load_trigger_times(studyID_to_report_time_file_path: str) -> dict[str, datetime]:
  """
  Reads the .txt file containing lines: StudyID;dd-mm-yyyy HH:MM
  Returns a dict: {studyID: datetime_object}
  """
  trigger_dict = {}
  with open(studyID_to_report_time_file_path, "r", encoding="utf-8") as f:
    for line in f:
      line = line.strip()
      if not line:
        continue

      study_id, dt = line.split(";")
      if dt == '':
        continue
      trigger_dt = datetime.strptime(dt, "%d-%m-%Y %H:%M")
      trigger_dict[study_id] = trigger_dt

  return trigger_dict

def annotate_csv_file(
  csv_path: str, 
  trigger_times: dict[str, datetime], 
  output_folder_path: str = '',
  datetime_column_name: str = START_DATETIME_COLUMN_NAME,
  activity_column_name: str = ACTIVITY_COLUMN_NAME,
  caseid_column_name: str = CASEID_COLUMN_NAME
) -> None:
  """
  Reads one CSV file and annotates Activity values if the record datetime
  is AFTER the datetime specified in the trigger_times dictionary.
  """
  function_logs = []
  updated_rows = []
  study_id_for_file = ""
  annotated_at_start = False
  with open(csv_path, "r", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    fieldnames = list(reader.fieldnames or [])
    function_logs.append(f'Start checking {csv_path} for annotation')
    for row in reader:
      previous_value_row = row.get(activity_column_name, '').strip()
      study_id = row.get(caseid_column_name, '').strip()
      if study_id_for_file == '' and study_id != caseid_column_name:
        study_id_for_file = study_id[:-2]

      if study_id_for_file == '':
        print(f'not registered {caseid_column_name} for file yet')
        function_logs.append(f'not registered {caseid_column_name} for file yet')
        updated_rows.append(row)
        continue

      raw_dt = row[datetime_column_name].replace('"', '')
      # Check if we have a trigger for this Study ID
      if study_id_for_file in trigger_times.keys() and raw_dt != datetime_column_name:
        if raw_dt == '':
          print(f'Empty datetime found in row for {caseid_column_name}: {study_id_for_file}')
          print(row)
        log_dt = datetime.strptime(raw_dt, DATETIME_PATTERN)
        trigger_dt = trigger_times.get(study_id_for_file, '')        
        if trigger_dt == '' and previous_value_row != '':
          row[activity_column_name] = previous_value_row
        elif trigger_dt is isinstance(trigger_dt, str):
          continue
        
        # Annotate if log datetime is AFTER trigger datetime
        if not isinstance(trigger_dt, str) and log_dt > trigger_dt and (previous_value_row == '1_Startup' or annotated_at_start):
          if previous_value_row == '1_Startup':
            annotated_at_start = True
          function_logs.append(f'Annotate for: {csv_path}')
          row[activity_column_name] = f"2_{row[activity_column_name]}"

      updated_rows.append(row)
  
  output_file_path = csv_path

  if output_folder_path:
    os.makedirs(output_folder_path, exist_ok=True)
    file_name = os.path.basename(csv_path)
    output_file_path = os.path.join(output_folder_path, file_name)

  # Overwrite the CSV with updated rows
  with open(output_file_path, "w", encoding="utf-8", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(updated_rows)

# Used to remove the post-report activities
def filter_csv_by_prefix(input_file, output_file, column_name, pattern):
    """
    Remove rows from a CSV where column_name starts with prefix.

    :param input_file: Path to input CSV file
    :param output_file: Path to output CSV file
    :param column_name: Column to check
    :param prefix: Prefix to filter out
    """
    regex = re.compile(pattern)
    with open(input_file, mode='r', newline='', encoding='utf-8') as infile:
      reader = csv.DictReader(infile)
      fieldnames = list(reader.fieldnames) if reader.fieldnames else []

      if column_name not in fieldnames:
        raise ValueError(f"Column '{column_name}' not found in fieldnames: {fieldnames} of CSV {input_file}.")

      with open(output_file, mode='w', newline='', encoding='utf-8') as outfile:
        writer = csv.DictWriter(outfile, fieldnames=fieldnames)
        writer.writeheader()

        for row in reader:
          value = row[column_name]
          
          # Skip rows where the value starts with the prefix
          if value is not None and regex.search(value):
            continue

          writer.writerow(row)

# Used to merge the start and end of the activities together to form one event for each activity
def merge_activity_events(
  file_path: str,
  start_datetime_column_name: str,
  end_datetime_column_name: str,
  identify_start_end_activities_column_name: str,
  output_folder: str, 
) -> str:
  splitted_file_path = os.path.basename(file_path)
  output_file_name = f'{splitted_file_path.replace('.csv', '')}.csv'
  # output_folder_time_a = os.path.join(output_folder, 'End_Times')
  output_file_path = os.path.join(output_folder, output_file_name)
  
  os.makedirs(output_folder, exist_ok=True)

  with open(file_path, 'r', encoding='utf-8', newline='') as infile, open(output_file_path, 'w', newline='') as outfile:
    reader = csv.DictReader(infile)
    fieldnames = list(reader.fieldnames) if reader.fieldnames else []
    fieldnames.append(end_datetime_column_name)
    fieldnames = [f for f in fieldnames if f != identify_start_end_activities_column_name]
    
    writer = csv.DictWriter(outfile, fieldnames=fieldnames)
    writer.writeheader()

    start_row = {}
    for row in reader:
      if start_row:
        s_phase_marker = start_row[identify_start_end_activities_column_name]
        e_phase_marker = row[identify_start_end_activities_column_name]

        e_phase = e_phase_marker.replace("end", "")
        s_phase = s_phase_marker.replace("start", "")
        if s_phase == e_phase:
          start_row[end_datetime_column_name] = row[start_datetime_column_name]
          start_row.pop(identify_start_end_activities_column_name, None)
          writer.writerow(start_row)

          start_row = {}
        else: 
          print(f'---------Something went wrong---------')
          print(f'start row: {start_row}')
          print(f'end row: {row}')
      else:
        s_phase_marker = row[identify_start_end_activities_column_name]
        start_marker = s_phase_marker.endswith('start')
        if start_marker:
          start_row = row
    
  return output_file_path

