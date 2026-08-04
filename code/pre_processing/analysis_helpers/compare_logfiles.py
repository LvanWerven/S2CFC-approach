
import argparse
import os
from typing import Literal

import pandas as pd

from pre_processing.S2CF_config import SUBSTRING_PATTERNS
from pre_processing.utils.general_utils import identify_substring, list_files_and_folders_in_folder, output_list_to_txt

# #############################################################################
# USE CASE:
# Compare logfiles in a folder on a specified attribute, can be used to, for example, find a startup or shutdown activity. 
# 
# EXAMPLE USAGE:
# Make sure to check certain substrings, e.g. file paths or ID's that are unique and should first be generalized before the event attribute can be compared. If available, an example can be the SUBSTRING_PATTERNS in the module_config
# 
# Run the following command in a bash terminal:
# "C:/Program Files/Python314/python.exe" -m analysis_helpers.compare_logfiles --lfp="ADD COMPLETE PATH TO FOLDER WITH (AT LEAST ONE) EVENT LOG" \
# --mfp="ADD COMPLETE PATH TO FOLDER WHERE THE COMPARISON OUTPUT SHOULD BE STORED" --attributes "Message" "FunctionCall" --sen="1" --een="75"
# #############################################################################

def compare_logfiles_in_folder(
    from_event_number: int, 
    to_event_number: int, 
    parent_folder_path: str, 
    columns_to_compare: list[str], 
    action_substring: Literal['identify', 'remove', 'replace', 'ignore'],
    selection_file_names: list[str] = [],
    substring_patterns: dict[str, str] = {}
) -> dict[tuple[str, str], tuple[bool, list[dict]]]:
  comparison_results = {}
  filenames = list_files_and_folders_in_folder(parent_folder_path)
  log_files = [f for f in filenames if os.path.isfile(os.path.join(parent_folder_path, f)) and f.startswith('parsed_') and f.endswith('.csv')]
  length_first_version = len(log_files)
  if selection_file_names:
    log_files = [f for f in filenames if f in selection_file_names]
    print(f'Only Selected list, length first list: {length_first_version}, length filtered: {len(log_files)}')
  
  for i in range(len(log_files)):
    for j in range(i + 1, len(log_files)):
      file_a = log_files[i]
      file_b = log_files[j]
      if file_a == file_b:
        print(f'Same files: {file_a} and {file_b}')
        continue
      full_path_a = os.path.join(parent_folder_path, file_a)
      full_path_b = os.path.join(parent_folder_path, file_b)
      identical, differences = compare_two_logfiles(
        from_event_number, 
        to_event_number, 
        full_path_a, 
        full_path_b, 
        columns_to_compare, 
        action_substring,
        substring_patterns
      )
        
      comparison_results[(file_a, file_b)] = (identical, differences)
  return comparison_results

def compare_two_logfiles(
  from_event_number: int, 
  to_event_number: int, 
  file_path_a: str, 
  file_path_b: str, 
  columns_to_compare: list[str],
  action_substring: Literal['identify', 'remove', 'replace', 'ignore'],
  substring_patterns: dict[str, str] = {}
) -> tuple[bool, list[dict]]:
  """
  Checks if a range of rows in two separate CSV files are identical 
  based on a specified list of columns.

  This function assumes event numbers are 1-based (i.e., row 1 is the first row).

  Args:
      from_event_number (int): The 1-based index of the starting row (inclusive).
      to_event_number (int): The 1-based index of the ending row (exclusive).
      file_path_a (str): The path to the first CSV file.
      file_path_b (str): The path to the second CSV file.
      columns_to_compare (List[str]): A list of column names (strings) 
                                      to use for the comparison.

  Returns:
      bool: True if the specified subset of rows/columns is identical 
            in both files, False otherwise.
  """
  if from_event_number <= 0 or from_event_number >= to_event_number:
    print("Error: 'from_event_number' must be positive and less than 'to_event_number'.")
    return False, []

  try:
    df_a = pd.read_csv(file_path_a)
    df_b = pd.read_csv(file_path_b)

    # 1-based event number adjustment for 0-based pandas indexing:
    # from_index is 1 less than the start number (inclusive)
    # to_index is the end number itself (exclusive, as per standard slicing)
    from_index = from_event_number - 1
    to_index = to_event_number

    # --- Subsetting DataFrames ---

    # 1. Select the rows first using .iloc for integer-based slicing
    # Check if the requested indices are valid before slicing
    if to_index > len(df_a) or to_index > len(df_b):
      print(f"Error: Requested range ({from_index} to {to_index}) exceeds file length.")
      return False, []

    subset_a_rows = df_a.iloc[from_index:to_index]
    subset_b_rows = df_b.iloc[from_index:to_index]

    subset_a = subset_a_rows.loc[:, columns_to_compare]
    subset_b = subset_b_rows.loc[:, columns_to_compare]

    # --- Comparison ---
    # Normalize row indexing for direct position-based comparison
    subset_a = subset_a.reset_index(drop=True)
    subset_b = subset_b.reset_index(drop=True)

    differences = []

    for i in range(len(subset_a)):
      row_a = subset_a.iloc[i]
      row_b = subset_b.iloc[i]
      row_diff = {}

      for col in columns_to_compare:
        a_val = row_a[col]
        b_val = row_b[col]

        # Check whether comparision should be strict or adjusted
        if action_substring != 'ignore':
          a_val, _ = identify_substring(input=a_val, patterns=substring_patterns, action=action_substring)
          b_val, _ = identify_substring(input=b_val, patterns=substring_patterns, action=action_substring)

        # Treat NaN/None as equal if both are missing
        if pd.isna(a_val) and pd.isna(b_val):
          continue

        # Different if one is NaN and the other isn't, or values are not equal
        if (pd.isna(a_val) != pd.isna(b_val)) or (not pd.isna(a_val) and a_val != b_val):
          row_diff[col] = {"file_a": a_val, "file_b": b_val}

      if row_diff:
        differences.append({
          "event_number": from_event_number + i,  # 1-based event number
          "row_position_in_file": from_index + i + 1, # 0-based row index in original file
          "differences": row_diff
        })

    # After iterating all rows, decide result based on collected differences
    if not differences:
      return True, []
    return not differences, differences
  
  except FileNotFoundError as e:
    print(f"Error: File not found at path: {e.filename}")
    return False, []
  except KeyError as e:
      print(f"Error: One or more specified columns not found: {e}")
      return False, []
  except pd.errors.EmptyDataError:
      print("Error: One of the files is empty.")
      return False, []
  except Exception as e:
      print(f"An unexpected error occurred: {e}")
      return False, []

def describe_comparison_folder(
  comparison: dict[tuple[str, str], tuple[bool, list[dict]]],
  start_event: int,
  end_event: int,
  print_output: bool, 
  write_output: bool,
  columns: list[str],
  output_folder_path: str,
):
  total_identical = 0
  total_different = 0
  file_lines = []
  if write_output:
    file_lines.append('Comparison Results of Log Files:\n')
    file_lines.append(f'Compared Event Range: {start_event} to {end_event}. On columns: {columns}\n')
    file_lines.append('-----------------------------------\n')
  for file_pair, result in comparison.items():
    file_a, file_b = file_pair
    identical, differences = result
    _, total_identical_comparison, total_different_comparison = describe_comparison_two_files(
      identical=identical, 
      differences= differences, 
      file_name_a=file_a, 
      file_name_b=file_b, 
      print_output=print_output,
      write_output=write_output,
      file_lines=file_lines,
      total_identical=total_identical,
      total_different=total_different
    )
    total_identical += total_identical_comparison
    total_different += total_different_comparison
    file_lines.append('-----------------------------------\n')
  file_lines.append(f'Total identical file pairs: {total_identical}\n')
  file_lines.append(f'Total different file pairs: {total_different}\n')
  
  output_file = output_list_to_txt(file_lines, output_folder_path, "logfile_comparison_results")
  print(f'output file: {output_file}')

def describe_comparison_two_files(
    identical: bool, 
    differences: list[dict], 
    file_name_a: str, 
    file_name_b: str, 
    print_output: bool = False, 
    write_output: bool = True, 
    file_lines: list[str] = [], 
    total_identical: int = 0, 
    total_different: int = 0 
  ) -> tuple[list[str], int, int]:
  if identical:
    total_identical += 1 
    file_lines.append(f'Files "{file_name_a}" and "{file_name_b}" are identical in the specified event range.')
  else:
    total_different += 1
    file_lines.append(f'Files "{file_name_a}" and "{file_name_b}" differ in the specified event range. Differences:')
    for diff in differences:
      event_num = diff["event_number"]
      row_pos = diff["row_position_in_file"]
      row_diffs = diff["differences"]
      file_lines.append(f'  Event Number: {event_num}, Row Position in File: {row_pos}')
      if write_output or print_output:
        for col, vals in row_diffs.items():
          file_lines.append(f'    Column: {col}, File A: {vals["file_a"]}, File B: {vals["file_b"]}')
  return file_lines, total_identical, total_different

if __name__ == "__main__":
  parser = argparse.ArgumentParser()
  parser.add_argument("--lfp", required=True, type=str, help="Complete path directing to folder with event data")
  parser.add_argument("--mfp", required=True, type=str, help="Complete path directing to folder with the output of the comparison")
  parser.add_argument("--attributes", nargs="+", required=True, help="The attribute name of the event data column that should be used to identify streaks")
  parser.add_argument("--sen", type=str, default="1", help="The event row from which to start the comparison")
  parser.add_argument("--een", type=str, default="", help="The event row till which the comparison should go")

  args = parser.parse_args()

  event_log_folder_path = args.lfp
  comparsion_output_folder = args.mfp
  start_event_number = int(args.sen)
  end_event_number = int(args.een)
  attributes_to_compare_on = args.attributes

  print("Start Comparison")
  comparison_result = compare_logfiles_in_folder(
    from_event_number= start_event_number, 
    to_event_number= end_event_number, 
    parent_folder_path=event_log_folder_path, 
    columns_to_compare=attributes_to_compare_on,
    action_substring='replace',
    substring_patterns=SUBSTRING_PATTERNS,
    selection_file_names= []
  )
  print('End Comparison - Start describing')
  describe_comparison_folder(
    comparison=comparison_result,
    start_event= start_event_number,
    end_event=end_event_number,
    print_output=False,
    write_output=True,
    columns=attributes_to_compare_on,
    output_folder_path= comparsion_output_folder
  )