
import argparse
import csv
from datetime import datetime
import json
import os

from pre_processing.utils.general_utils import list_files_and_folders_in_folder

# #############################################################################
# USE CASE:
# Creates an excel file with the number of events, first and last datetime, time span and included dates
# 
# EXAMPLE USAGE:
# Run the following command in a bash terminal:
# "C:/Program Files/Python314/python.exe" -m analysis_helpers.gather_log_metrics --lfp="ADD COMPLETE PATH TO FOLDER WITH (AT LEAST ONE) EVENT LOG" \
# --mfp="ADD COMPLETE PATH TO FOLDER WITH STREAK MAP FILES (.JSON)" --attribute="Datetime" --gt="60"
# #############################################################################

def output_dict_of_dicts_to_csv(
  data: dict[str, dict],
  folder_path: str,
  filename: str,
  id_column: str = "id",
  encoding: str = "utf-8",
  overwrite: bool = True
) -> str:
  """
  Write a dict[str, dict] to a CSV file.
  - top-level keys become the id_column values
  - inner dict keys become CSV column names
  Returns the full path to the written CSV.
  """
  os.makedirs(folder_path, exist_ok=True)
  if not filename.lower().endswith(".csv"):
    filename = f"{filename}.csv"
  file_path = os.path.join(folder_path, filename)
  mode = "w" if overwrite else "x"

  # collect all column names from inner dicts
  columns = set()
  for v in data.values():
    if isinstance(v, dict):
      columns.update(v.keys())
  columns = sorted(columns)

  fieldnames = [id_column] + columns

  with open(file_path, mode, newline="", encoding=encoding) as fh:
    writer = csv.DictWriter(fh, fieldnames=fieldnames)
    writer.writeheader()
    for id_key, inner in data.items():
      row = {id_column: id_key}
      if isinstance(inner, dict):
        for col in columns:
          val = inner.get(col)
          if val is None:
            row[col] = ""
          elif isinstance(val, (dict, list, tuple, set)):
            row[col] = json.dumps(val, default=str)
          else:
            row[col] = str(val)
      else:
        # non-dict inner value: place under a single column (first column) or as JSON in a "value" column
        if columns:
          row[columns[0]] = json.dumps(inner, default=str)
        else:
          row["value"] = json.dumps(inner, default=str)
      writer.writerow(row)

  return file_path

def recursive_datetime_metrics(parent_folder_path: str, datetime_column: str, gap_threshold: float = 60) -> dict[str, dict]:
  all_metrics = {}
  filenames = list_files_and_folders_in_folder(parent_folder_path)
  for filename in filenames:
    full_path = os.path.join(parent_folder_path, filename)
    if os.path.isdir(full_path):
      next_metrics = recursive_datetime_metrics(full_path, datetime_column)
      all_metrics.update(next_metrics)
    elif os.path.isfile(full_path) and filename.startswith('parsed_') and full_path.endswith('.csv'):
      file_metrics = datetime_metrics_for_logfile(parent_folder_path, filename, datetime_column, gap_threshold)
      all_metrics[file_metrics[0]] = file_metrics[1]
  return all_metrics

def datetime_metrics_for_logfile(folder_path: str, filename: str, datetime_column: str, gap_threshold: float = 60) -> tuple[str, object]:
  metrics = {
    "num_events": 0,
    "start_datetime": None,
    "end_datetime": None,
    "time_span_log": None,
    "dates": None,
    "gaps_over_threshold": [],  # List of (start_datetime, end_datetime, gap_duration) tuples
  }
  date = ''

  csv_path = os.path.join(folder_path, filename)
  with open(csv_path, 'r', encoding='utf-8') as infile:
    reader = csv.DictReader(infile)
    previous_datetime = None


    dates = set()
    for row in reader:
      metrics["num_events"] += 1

      datetime_value = row.get(datetime_column)
      if datetime_value:
        date = f'{datetime_value.split(' ')[0]} {datetime_value.split(' ')[1]} {datetime_value.split(' ')[2]}'
        dates.add(date)
        # Update start and end datetime
        if metrics["start_datetime"] is None:
          metrics["start_datetime"] = datetime_value
        metrics["end_datetime"] = datetime_value
        
        # Calculate gaps
        if previous_datetime:
          gap_duration = (datetime.strptime(datetime_value, '%d %b %Y %H:%M:%S,%f') - 
                  datetime.strptime(previous_datetime, '%d %b %Y %H:%M:%S,%f')).total_seconds()
          if gap_duration > gap_threshold:  # Example threshold of 60 seconds
            metrics["gaps_over_threshold"].append((previous_datetime, datetime_value, gap_duration))
        
        previous_datetime = datetime_value

  # Calculate time span
  if metrics["start_datetime"] and metrics["end_datetime"]:
    start_dt = datetime.strptime(metrics["start_datetime"], '%d %b %Y %H:%M:%S,%f')
    end_dt = datetime.strptime(metrics["end_datetime"], '%d %b %Y %H:%M:%S,%f')
    time_delta = end_dt - start_dt
    total_seconds = int(time_delta.total_seconds())
    days = total_seconds // 86400
    hours = (total_seconds % 86400) // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    metrics["time_span_log"] = {
      "days": days,
      "hours": hours,
      "minutes": minutes,
      "seconds": seconds,
    }

  metrics["dates"] = dates

  return (filename, metrics)

if __name__ == "__main__":
  parser = argparse.ArgumentParser()
  parser.add_argument("--lfp", required=True, type=str, help="Complete path directing to folder with event data")
  parser.add_argument("--mfp", type=str, help="Complete path directing to folder where metrics excel can be stored")
  parser.add_argument("--attribute", type=str, required=True, help="The attribute name of the event data column that holds the datetime")
  parser.add_argument("--gt", type=str, default="60", help="The number of seconds that count as a gap")
  args = parser.parse_args()
  
  attribute_name = args.attribute
  gap_threshold = float(args.gt)

  event_log_folder_path = args.lfp
  metrics_folder_path = args.mfp
  if not metrics_folder_path:
    metrics_folder_path = event_log_folder_path

  print('Start gathering information')
  folder_metrics = recursive_datetime_metrics(
    parent_folder_path=event_log_folder_path,
    datetime_column=attribute_name,
    gap_threshold=gap_threshold
  )

  os.makedirs(metrics_folder_path, exist_ok=True)
  output_csv_path = output_dict_of_dicts_to_csv(
    data=folder_metrics, 
    folder_path=metrics_folder_path, 
    filename="datetime_metrics_logfiles"
  )
  print(f'Datetime metrics written to file: {output_csv_path}')
