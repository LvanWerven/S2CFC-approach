
import csv
import os
import re
from typing import Any, Callable, Literal, Optional

from pre_processing import S2CF_config
from pre_processing.S2CF_config import DESCRIPTIVE_COLUMN_NAME

# Used to create .txt files with the output of various functions or create log files to track the execution of functions
def output_list_to_txt(lines: list[str], folder_path: str, filename: str, encoding: str = "utf-8", overwrite: bool = True) -> str:
  """
  Write a list of strings to a .txt file (one item per line).
  Returns the full path of the written file.
  """
  os.makedirs(folder_path, exist_ok=True)
  if not filename.lower().endswith(".txt"):
    filename = f"{filename}.txt"
  file_path = os.path.join(folder_path, filename)
  mode = "w" if overwrite else "x"
  with open(file_path, mode, encoding=encoding) as fh:
    for item in lines:
      fh.write(f"{item}\n")
  return file_path

# Lists all the items in a folder and returns them as a list of strings
def list_files_and_folders_in_folder(folder_path) -> list[str]:
  filenames = os.listdir(folder_path)
  return filenames

# Call a function for each file in a folder, optionally filtering files based on a provided filter function.
def recursive_apply_to_files(
  folder_path: str,
  file_handler: Callable[[str], Any],
  file_filter: Optional[Callable[[str], bool]] = None,
  function_logs: Optional[list[str]] = None
) -> list[str]:
  if function_logs is None:
    function_logs = []

  try:
    filenames = os.listdir(folder_path)
  except Exception as e:
    function_logs.append(f'ERROR: Cannot list directory "{folder_path}": {e}')
    return function_logs

  for filename in filenames:
    full_path = os.path.join(folder_path, filename)

    if os.path.isdir(full_path):
      # Recurse into subfolders
      recursive_apply_to_files(
        folder_path=full_path,
        file_handler=file_handler,
        file_filter=file_filter,
        function_logs=function_logs
      )

    elif os.path.isfile(full_path):
      if file_filter is None or file_filter(full_path):
        try:
          file_handler(full_path)
          function_logs.append(f'Handled file: {full_path}')
        except Exception as e:
          function_logs.append(f'ERROR: Handler failed for "{full_path}": {e}')
      else:
        function_logs.append(f'Skipped by filter: {full_path}')
    else:
      function_logs.append(f'Skipping non-file entry: {full_path}')

  return function_logs

# Add a "found value" in the search column (using the regular expression pattern) to a specific (new) column in a CSV file, creating the column if it doesn't exist.
def add_identified_value_to_column(
  file_path: str,
  column_name: str,
  regex_pattern: re.Pattern,
  search_in_column_name: str = DESCRIPTIVE_COLUMN_NAME,
  function_logs: list[str] = []
):
  rows = []
  file_name = os.path.basename(file_path)
  with open(file_path, 'r', encoding='utf-8') as infile:
    reader = csv.DictReader(infile)
    fieldnames = list(reader.fieldnames or [])

    if column_name not in fieldnames:
      fieldnames.append(column_name)

    row_index = 0
    for row in reader:
      message = row.get(search_in_column_name, '')
      match = regex_pattern.search(message)
      if match:
        row[column_name] = match.group(1)
        function_logs.append(f'In file "{file_name}", found value: {match.group(1)}, in row {row_index}: "{row}')
      else:
        row[column_name] = row.get(column_name, '')
      row_index += 1
      rows.append(row)

    with open(file_path, 'w', newline='', encoding='utf-8') as outfile:
      writer = csv.DictWriter(outfile, fieldnames=fieldnames)
      writer.writeheader()
      writer.writerows(rows)

  function_logs.append(f"✅ Extracted {column_name} from {search_in_column_name} in: {file_name}")
  return function_logs

# Fill a specific column in a CSV file with a value found in the first non-empty occurrence of that column, for all rows.
def fill_column_for_all_rows(
  file_path: str,
  column_name: str,
  function_logs: list[str] = []
):
  file_name = os.path.basename(file_path)
  rows = []

  # Read rows and find Study IDs
  with open(file_path, 'r', encoding='utf-8') as infile:
    reader = csv.DictReader(infile)
    # Ensure fieldnames is a list (not None) before using it for writing
    fieldnames = list(reader.fieldnames or [])

    study_id = None
    for row in reader:
      pid = row.get(column_name, '').strip()
      if pid:
        study_id = pid
      rows.append(row)

  if not study_id:
    function_logs.append(f"ℹ️ No {column_name} found in {file_name}, with {len(rows)} events, skipping fill.")
    return function_logs

  for row in rows:
    if not row.get(column_name, '').strip():
      row[column_name] = study_id

  # Write back to CSV
  with open(file_path, 'w', newline='', encoding='utf-8') as outfile:
    writer = csv.DictWriter(outfile, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)

  function_logs.append(f"✅ Filled {column_name} '{study_id}' in all rows of: {column_name}")
  return function_logs

# Identify, remove or replace substrings in a string based value using a dictionary of patterns.
def identify_substring(
  input: str,
  patterns: dict[str, str] = S2CF_config.SUBSTRING_PATTERNS,
  action: Literal['identify', 'remove', 'replace'] = 'replace',
  function_logs: list[str] = []
) -> tuple[str, list[str]] :
  """
  Processes an input string by searching it based on a list of
  regular expressions (patterns) and performs an action.

  Args:
      text: The input string which may contain the date-time string.
      patterns: A list of regular expression strings to search for.
      remove: 
          - If True (default): Remove ALL found date-time strings
            and return the cleaned-up text (str).
          - If False: Return the FIRST found date-time string (str).
            If not found, return None.

  Returns:
    Optional[str]: The cleaned-up text, the found date-time string, or None.
  """
  output = input
  function_logs.append(f'Matching "{input}"')
  if action != 'identify':
    for key, pattern in patterns.items():
      if action == 'remove':
        output = re.sub(pattern, '', output)
        function_logs.append(f'Removed pattern: {key}')
      elif action == 'replace':
        output = re.sub(pattern, key, output)
        function_logs.append(f'Replaced pattern: {key}')
    return output, function_logs

  else:
    for key, pattern in patterns.items():
      match = re.search(pattern, output)
      if match:
        return match.group(0), function_logs
      else:
        function_logs.append(f'No match for "{key}"')
    return output, function_logs

# Remove punctuation and normalize whitespace in a string, optionally removing punctuation.
def normalize_string(input: str, remove_punctuation: bool = False) -> str:
  text = input.lower()
  text = re.sub(r"\s+", " ", text).strip()
  if remove_punctuation:
    text = re.sub(r"[^\w\s-]", "", text)
  return text

# filter on files that have the csv postfix 
def _is_csv_file(full_path: str):
  return os.path.isfile(full_path) and full_path.endswith('.csv')
