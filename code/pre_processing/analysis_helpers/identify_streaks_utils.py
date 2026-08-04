

from collections import defaultdict
import csv
import os
from pathlib import Path
from typing import Counter, Dict, List, Tuple

from dotenv import load_dotenv
import pandas as pd

from pre_processing.utils.general_utils import identify_substring, list_files_and_folders_in_folder, normalize_string, output_list_to_txt


# def validate_env_vars(required_vars: list[str], env_file: str = ".env") -> None:
#   """
#   Loads the .env file and validates that all required variables
#   are present and non-empty.

#   Args:
#       required_vars: List of required environment variable names.
#       env_file: Path to the .env file.

#   Raises:
#       FileNotFoundError: If the .env file does not exist.
#       ValueError: If one or more required variables are missing or empty.
#   """
#   env_path = Path(env_file)

#   if not env_path.exists():
#     raise FileNotFoundError(f".env file not found: {env_file}")

#   load_dotenv(env_path)

#   missing = [
#       var
#       for var in required_vars
#       if not os.getenv(var, "").strip()
#   ]

#   if missing:
#       raise ValueError(
#           f"Missing or empty environment variables: {', '.join(missing)}"
#       )

def find_message_in_column(
  file_path: str,
  column_name: str,
  search_string: str,
  generalized: bool = False,
  normalized: bool = False,
  function_logs: list[str] = [],
) -> tuple[List[tuple[int, dict[str, str]]], list[str]]:
  matches: List[tuple[int, dict[str, str]]] = []
  row_index = 0
  if not os.path.isfile(file_path):
    print('Cannot find the file at this filepath', file_path)
    return matches, function_logs
  with open(file_path, 'r', encoding='utf-8') as file:
    reader = csv.DictReader(file)
    column_names = list(reader.fieldnames) if reader.fieldnames else []
    if column_name not in column_names:
      print(f'Column name "{column_name}" not found in file {file_path}. Available columns: {column_names}')
      return matches, function_logs
    for row in reader:
      row_index += 1
      value = row.get(column_name, '')
      if normalized:
        function_logs.append(f'Normalizing value: "{value}"')
        value = normalize_string(value, remove_punctuation=False)
      if generalized:
        function_logs.append(f'Generalizing value: "{value}"')
        value, _ = identify_substring(value, action='replace')
      function_logs.append(f'Checking row {row_index} with value: "{value}" for search string: "{search_string}"')
      if search_string in value.lower():
        matches.append((row_index, row))
  return matches, function_logs


def compare_streaks(
  streaks: list[tuple[int, int, int, str, str, list[str]]],
) -> tuple[Counter[tuple[str, ...]], Counter[int]]:
  streaks_list = [streak for _, _, _, _, _, streak in streaks]
  
  start_index_counts = Counter(
      start_index
      for _, start_index_a, start_index_b, _, _, _ in streaks
      for start_index in (start_index_a, start_index_b)
  )

  # Convert lists to tuples to make them hashable
  tuples = [tuple(order) for order in streaks_list]
  return Counter(tuples), start_index_counts

LogFileData = tuple[str, list[str], list[tuple[int, dict[str, str]]]] # (filename, column_values, start_matches)
StreakType = tuple[int, int, int, str, str, list[str]]

def find_equal_message_streaks_in_folder(
  parent_folder_path: str,
  column_name: str,
  start_event_message: str,
  substring_patterns: dict[str, str] = {},
  function_logs: list[str] = [],
) -> tuple[list[StreakType], list[str]]:
  combined_streaks: list[StreakType] = []
  
  filenames = list_files_and_folders_in_folder(parent_folder_path)
  log_files = [f for f in filenames if os.path.isfile(os.path.join(parent_folder_path, f)) and f.startswith('parsed_') and f.endswith('.csv')]
  
  processed_files: list[LogFileData] = []
  
  for filename in log_files:
    full_path = os.path.join(parent_folder_path, filename)
    
    df = pd.read_csv(full_path)
    column_values = df[column_name].tolist()
    
    matches, function_logs = find_message_in_column(full_path, column_name, start_event_message)
    
    processed_files.append((filename, column_values, matches))

  for i in range(len(processed_files)):
    for j in range(i + 1, len(processed_files)):
      file_a_name, values_a, matches_a = processed_files[i]
      file_b_name, values_b, matches_b = processed_files[j]
      function_logs.append(f'Vergelijk {file_a_name} met {file_b_name}')
      
      streaks, function_logs = find_equal_message_streaks_in_logfiles(
        values_a, 
        values_b, 
        matches_a, 
        matches_b,
        substring_patterns,
        function_logs
      )
      combined_streaks.extend(streaks)
          
  return combined_streaks, function_logs

def find_equal_message_streaks_in_logfiles(
  column_values_a: list[str],
  column_values_b: list[str],
  matchesa: list[tuple[int, dict[str, str]]],
  matchesb: list[tuple[int, dict[str, str]]],
  substring_patterns: dict[str, str] = {},
  function_logs: list[str] = []
) -> tuple[list[StreakType], list[str]]:
  streaks: list[StreakType] = []

  len_a = len(column_values_a)
  len_b = len(column_values_b)
  
  serialized_values_a = []
  for valuea in column_values_a:
    serialized_value, _ = identify_substring(input=valuea, patterns=substring_patterns, action='replace')
    serialized_values_a.append(serialized_value)
      
  serialized_values_b = []
  for valueb in column_values_b:
    serialized_value, _ = identify_substring(input=valueb, patterns=substring_patterns, action='replace')
    serialized_values_b.append(serialized_value)

  for indexa, _ in matchesa: 
    start_index_a = indexa - 1

    for indexb, _ in matchesb:
      start_index_b = indexb - 1
      
      streak_length = 0
      current_indexa = start_index_a
      current_indexb = start_index_b
      streak_values = []

      while True:
        serialized_valuea = serialized_values_a[current_indexa] if 0 <= current_indexa < len_a else None
        serialized_valueb = serialized_values_b[current_indexb] if 0 <= current_indexb < len_b else None

        is_end_of_file = serialized_valuea is None or serialized_valueb is None
        is_match = serialized_valuea == serialized_valueb

        if is_match:
          if streak_length == 0:
            function_logs.append(f'Streak gestart met indexen {current_indexa}, {current_indexb}')
          streak_length += 1
          
          if is_end_of_file:
            streak_values.append('<END OF FILES MATCH>')
            if streak_length > 0:
              function_logs.append(f'Streak afgelopen met lengte {streak_length}, beide files afgelopen')
              streaks.append((streak_length, start_index_a, start_index_b, serialized_valuea or '', serialized_valueb or '', streak_values))
            break
          else:
            current_indexa += 1
            current_indexb += 1
            streak_values.append(serialized_valuea)
        else:
          if streak_length > 1:
            function_logs.append(f'Streak afgelopen met lengte {streak_length}')
            streaks.append((streak_length, start_index_a, start_index_b, serialized_valuea or '', serialized_valueb or '', streak_values))
          break

  return streaks, function_logs

def streak_comparison_output(
  streaks_counter: dict[tuple[str, ...], int],
  output_folder_path: str,
  output_file_name: str,
):
  output_list: list[str] = []
  output_list.append('------------------Streak Aggregation------------------')
  for streak, count in streaks_counter.items():
    streak_str = "\n -> ".join(streak)
    output_list.append(f'Streak (length {len(streak)}) - Count: {count} :\n {streak_str} ')
  output_file_path = output_list_to_txt(output_list, output_folder_path, output_file_name)
  print('Output streak comparison file:', output_file_path)

def create_map_streak_to_id(
  streaks: List[tuple[str, ...]],
  prefix: str,
) -> dict[tuple[str, ...], str]:
  return {streak: f"{prefix}_{i+1}" for i, streak in enumerate(streaks)}

def find_streaks_in_folder(
  parent_folder_path: str,
  column_name: str,
  start_event_message: str,
  function_logs: list[str] = [],
  substring_patterns: dict[str,str] = {},
  max_streak_length: int = 40,
) -> tuple[dict[tuple[str, ...], int], list[str]]:
  buckets = defaultdict(int)

  def _add_sequence(seq):
    key = tuple(seq)
    buckets[key] += 1

  filenames = list_files_and_folders_in_folder(parent_folder_path)
  log_files = [f for f in filenames if os.path.isfile(os.path.join(parent_folder_path, f)) and f.startswith('parsed_') and f.endswith('.csv')]
  
  processed_files: list[LogFileData] = []

  normalized_message = normalize_string(start_event_message, remove_punctuation=False)
  serialized_start_message, _ = identify_substring(input=normalized_message, patterns=substring_patterns, action='replace')
  
  for filename in log_files:
    full_path = os.path.join(parent_folder_path, filename)
    
    df = pd.read_csv(full_path)
    column_values = df[column_name].tolist()
    
    matches, function_logs = find_message_in_column(full_path, column_name, serialized_start_message, generalized=True, normalized=True, function_logs=function_logs)
    function_logs.append(f'File: {filename}, found {len(matches)} matches for start event "{serialized_start_message}"')
    processed_files.append((filename, column_values, matches))

  for _, file_values, file_matches in processed_files:
    serialized_values = []

    for value in file_values:
      normalized_value = normalize_string(value, remove_punctuation=False)
      serialized_value, _ = identify_substring(input=normalized_value, patterns=substring_patterns, action='replace')
      serialized_values.append(serialized_value)
      function_logs.append(f'Original: "{value}", Normalized: "{normalized_value}", Serialized: "{serialized_value}"')

    for matchIndex, _ in file_matches:
      sequence: List[str] = []
      index = matchIndex -1
      
      # Include start events in streak
      sequence.append(serialized_values[index])
      _add_sequence(sequence)
      index += 1

      function_logs.append(f'Start streak at index: {index}')
      while index < len(file_values) and len(sequence) < max_streak_length:
        file_serialized_value = serialized_values[index]
        # If run into start event message again go to next match
        if file_serialized_value == serialized_start_message:
          function_logs.append(f'Found start message again at index: {index}')
          break
        sequence.append(file_serialized_value)
        _add_sequence(sequence)
        index += 1

  return buckets, function_logs

def filter_streaks(
  prefix_counts: Dict[Tuple[str, ...], int],
  count_threshold: int = 0
) -> Tuple[Dict[Tuple[str, ...], int], Dict[Tuple[str, ...], int]]:
  sorted_dict = sorted(
    prefix_counts.items(),
    key=lambda kv: (len(kv[0]), kv[1]),
    reverse=True
  )
  
  filtered_dict: Dict[Tuple[str, ...], int] = {}
  rest_dict: Dict[Tuple[str, ...], int] = {}

  for seq, cnt in sorted_dict:
    is_subset = any(is_prefix(seq, kept_seq) for kept_seq in filtered_dict.keys())
    if is_subset or cnt < count_threshold:
      rest_dict[seq] = cnt
    else:
      filtered_dict[seq] = cnt
  return filtered_dict, rest_dict


def is_prefix(small: Tuple[str, ...], big: Tuple[str, ...]) -> bool:
  """Return True if 'small' is a prefix of 'big'."""
  if len(small) > len(big):
    return False
  return big[:len(small)] == small
