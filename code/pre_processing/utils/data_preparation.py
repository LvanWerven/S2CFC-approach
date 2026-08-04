
import csv
import os
import re

from pre_processing.S2CF_config import SOFTWARE_DATA_COLUMNS
from pre_processing.utils.general_utils import list_files_and_folders_in_folder

# Use the specified regex pattern to parse a log file and write the extracted data to a CSV file.
def parse_log_to_csv(input_path: str, output_csv: str, pattern: re.Pattern):
  with open(input_path, 'r', encoding='utf-8') as logfile, open(output_csv, 'w', newline='', encoding='utf-8') as csvfile:
    writer = csv.writer(csvfile)
    writer.writerow(SOFTWARE_DATA_COLUMNS)
    for line in logfile:
      line = line.strip()
      m = pattern.match(line)
      if m:
        writer.writerow(m.groupdict().values())

# Transform event data files into csv's, can also aggregate into a combined file.
def transform_data_recursive(
  parent_folder_path: str, 
  output_folder_path: str, 
  pattern: re.Pattern,
  included_names: list[str] = [],
  combined_path: str = '',
  function_logs: list[str] = []
) -> list[str]:
  """
  Walk through parent_folder_path recursively (all folders within the parent folder) and parse qualifying .log files into CSV.
  Only parse files whose full path contains any of the names in `included_names`
  (case-insensitive). If `combined_path` is provided, also append/aggregate there.

  Args:
      parent_folder_path: Root folder to start searching.
      output_folder_path: Destination folder for per-file CSV outputs.
      pattern: Compiled regex used by parse_log_to_csv.
      included_names: List of substrings; if any is found in a file's full path,
                      the file is eligible for parsing. Case-insensitive.
      combined_path: Optional path to a combined CSV file to also write into.
  """
  os.makedirs(output_folder_path, exist_ok=True)

  filenames = list_files_and_folders_in_folder(parent_folder_path)
  for filename in filenames:
    full_path = os.path.join(parent_folder_path, filename)
    function_logs.append(f'CHECKING PATH: {full_path}')

    if os.path.isdir(full_path):
      transform_data_recursive(full_path, output_folder_path, pattern, included_names, combined_path)

    elif os.path.isfile(full_path):
      is_log = full_path.endswith('.log')
      starts_with_simplicity = os.path.splitext(filename)[0].startswith('Simplicity')

      path_lower = full_path.lower()
      should_include = ( len(included_names) == 0) or any(name.lower() in path_lower for name in included_names)

      if is_log and starts_with_simplicity and should_include:
        csv_filename = f'parsed_{os.path.splitext(filename)[0]}.csv'
        output_path = os.path.join(output_folder_path, csv_filename)
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        parse_log_to_csv(full_path, output_path, pattern)

        if combined_path:
          combined_dir = os.path.dirname(combined_path)
          if combined_dir:
            os.makedirs(combined_dir, exist_ok=True)
          parse_log_to_csv(full_path, combined_path, pattern)
      else:
          function_logs.append(f'SKIPPING FILE: {full_path}')
    else:
        function_logs.append(f'SKIPPING NON-FS ENTRY: {full_path}')
  return function_logs      

# Function to implement the addition of a 'Log ID' column based on the filename
def add_log_id_column(folder_path: str):
  """Adds a 'Log ID' column to each CSV file, using the filename without 'parsed_' and '.csv'."""
  for filename in os.listdir(folder_path):
    if filename.endswith('.csv'):
      file_path = os.path.join(folder_path, filename)

      # Extract log ID from filename
      base_name = filename.replace('parsed_', '').replace('.csv', '')

      updated_rows = []

      with open(file_path, 'r', encoding='utf-8') as infile:
        reader = csv.DictReader(infile)
        fieldnames = list(reader.fieldnames or [])

        # Add column if not already present
        if 'Log ID' not in fieldnames:
          fieldnames.append('Log ID')

        for row in reader:
          row['Log ID'] = base_name
          updated_rows.append(row)

      # Write back to file
      with open(file_path, 'w', newline='', encoding='utf-8') as outfile:
        writer = csv.DictWriter(outfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(updated_rows)
