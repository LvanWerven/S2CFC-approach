import argparse
import csv
import os

from pre_processing.utils.general_utils import identify_substring, list_files_and_folders_in_folder, normalize_string, output_list_to_txt

# #############################################################################
# USE CASE:
# This script can be used to find recurring occurrences of a substring to enable finding keywords or patterns in attribute values. 
# 
# EXAMPLE USAGE:
# Check if there are substrings that should be generalized: GENERALIZATION_SUBSTRINGS
# 
# To find queue status events in the FLA use case, run the following command in a bash terminal:
# "C:/Program Files/Python314/python.exe" -m analysis_helpers.find_recurring_substrings --lfp="ADD COMPLETE PATH TO FOLDER WITH (AT LEAST ONE) EVENT LOG" --mfp="ADD COMPLETE PATH TO FOLDER WITH (AT LEAST ONE) EVENT LOG" --ss="task" --attributes "Message"
# #############################################################################

GENERALIZATION_SUBSTRINGS = {}

def merge_dict_of_dict_matches(
  target: dict[str, dict[str, int]], 
  source: dict[str, dict[str, int]]
) -> None:
  """
  Merges the 'source' matches into the 'target' matches, summing up counts 
  for common (column, value) pairs.
  """
  for col_name, value_counts in source.items():
      if col_name not in target:
          target[col_name] = value_counts
      else:
          for value, count in value_counts.items():
              target[col_name][value] = target[col_name].get(value, 0) + count

def find_term_in_csv_file(
    file_path: str, 
    search_string: str, 
    columns: list[str], 
    case_sensitive: bool = True, # specifies whether the search is case sensitive
    extract_search_term: bool = False # save the value within the column without the search_string
) -> dict[str, dict[str, int]]:
  """
  Read a .csv at file_path and return a list of rows
  (as dicts) where any of the given columns contains search_word (case-insensitive,
  substring match). If a specified column name isn't present exactly, a case-insensitive
  match against available headers is attempted.
  """
  matches: dict[str, dict[str, int]] = {} # { column_name : { message_value: quantity } }
  if not os.path.isfile(file_path):
    print('Cannot find the file at this filepath', file_path)
    return matches
  try:
    with open(file_path, 'r', encoding='utf-8') as file:
      reader = csv.DictReader(file)
      search_lower = search_string.lower()
      for row in reader:
        for col_name in columns:
          value = row.get(col_name)
          if value is None:
            continue
          found_term = search_string in str(value) or (not case_sensitive and search_lower in str(value).lower())
          if found_term and extract_search_term:
            value = value.replace(search_string, '').strip()
          if found_term and col_name not in matches:
            matches[col_name] = {}
          elif found_term and str(value) in matches[col_name]:
            matches[col_name][str(value)] += 1
          elif found_term and str(value) not in matches[col_name]:
            matches[col_name][str(value)] = 1

  except Exception as e:
    print('Something went wrong', e)
    return matches

  return matches

def recursive_find_term_in_csv_file(
  parent_folder_path: str, 
  search_string: str, 
  columns: list[str],
  matches: dict[str, dict[str, int]] = {}, 
  case_sensitive: bool = True,
  extract_search_term: bool = False
) -> dict[str, dict[str, int]]:
  filenames = list_files_and_folders_in_folder(parent_folder_path)
  for file_name in filenames:
    full_path = os.path.join(parent_folder_path, file_name)
    if os.path.isfile(full_path) and file_name.startswith('parsed_') and file_name.endswith('.csv'):
      file_matches = find_term_in_csv_file(
        file_path = full_path,
        search_string=search_string,
        columns=columns,
        case_sensitive=case_sensitive,
        extract_search_term=extract_search_term
      )
      merge_dict_of_dict_matches(matches, file_matches)
    elif os.path.isdir(full_path):
      recursive_find_term_in_csv_file(
        parent_folder_path= full_path,
        matches=matches,
        search_string=search_string,
        columns=columns,
        case_sensitive=case_sensitive,
        extract_search_term=extract_search_term
      )
  return matches

def describe_word_groups(
  input_txt_file_path: str,
  output_folder: str,
  output_file_name: str,
  num_words_in_group: int = 3,
  remove_substrings: dict[str, str] = {},
):
  
  def _get_group_key(text, num_tokens=3):
    tokens = text.split()
    return " ".join(tokens[:num_tokens]).replace(' ', '_')

  task_groups: dict[str, list[str]] = {}
  with open(input_txt_file_path, 'r') as file:
    lines = file.readlines()
    tasks = [line.strip() for line in lines]
    for task in tasks:
      if remove_substrings:
        task, _ = identify_substring(task, patterns=remove_substrings, action='remove')
      norm = normalize_string(task)
      key = _get_group_key(norm, num_tokens=num_words_in_group)
      if key not in task_groups:
        task_groups[key] = []
      task_groups[key].append(task)
  output_list = []
  for key, items in task_groups.items():
    output_list.append(f"Group: {key} ({len(items)} tasks)")
    for item in items:
      output_list.append(f"  - {item}")
  output_list_to_txt(output_list, output_folder, output_file_name)

def describe_prefix_match(
  prefix_matches: dict[str, dict[str, int]],
  output_folder_path: str,
  file_output_name: str
):
  lines: list[str] = []
  for col_name, value in prefix_matches.items():
    lines.append(f'Matches on column {col_name}')
    for message, number in value.items():
      lines.append(f'Number of matches: {number}, on message: "{message}"')
  file_path = output_list_to_txt(lines, output_folder_path, file_output_name )
  print('outputted on', file_path)



if __name__ == "__main__":
  parser = argparse.ArgumentParser()
  parser.add_argument("--lfp", required=True, type=str, help="Complete path directing to folder with event data")
  parser.add_argument("--mfp", required=True, type=str, help="Complete path directing to folder where the output should be stored")
  parser.add_argument("--ss", type=str, required=True, help="The search string")
  parser.add_argument("--attributes", nargs="+", required=True, help="The attribute name of the event data column that should be used to find the search string in")
  parser.add_argument('--casesensitive', action='store_true', default=False, help="Is the match on the search string case sensitive")
  parser.add_argument('--ng', type=str, default="2", help="The number of words that the term groups are created on")
  args = parser.parse_args()

  event_log_folder_path = args.lfp
  found_matches_folder_path = args.mfp
  search_string = args.ss
  attributes = args.attributes
  case_sensitive=args.casesensitive
  number_of_words_for_group = int(args.ng)

  prefix_matches = recursive_find_term_in_csv_file(
    parent_folder_path=event_log_folder_path,
    search_string=search_string,
    columns=attributes,
    case_sensitive=case_sensitive,
    extract_search_term=False 
  )
  
  file_output_name = f'messages_including_{search_string}.txt'
  describe_prefix_match(
    prefix_matches=prefix_matches,
    output_folder_path=found_matches_folder_path,
    file_output_name=file_output_name
  )
  messages_including_task = os.path.join(found_matches_folder_path, file_output_name)
  describe_word_groups(
    input_txt_file_path=messages_including_task,
    output_folder=found_matches_folder_path,
    output_file_name=f'groups_{search_string}_matches',
    num_words_in_group=2,
    remove_substrings=GENERALIZATION_SUBSTRINGS
  )
