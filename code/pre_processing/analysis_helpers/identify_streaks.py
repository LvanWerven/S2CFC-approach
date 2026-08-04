


import argparse
import json
import os

from pre_processing.analysis_helpers.identify_streaks_utils import create_map_streak_to_id, filter_streaks, find_streaks_in_folder, streak_comparison_output

# #############################################################################
# USE CASE:
# This script can be used to find possible streaks in event logs based on a given start event and a specific attribute (e.g., "Message"). 
# It identifies streaks, filters them based on a count threshold, and creates a mapping of streaks to IDs. 
# The results are saved in the output folder.
# 
# EXAMPLE USAGE:
# To identify the streaks for the autosegmentation, run the following command in a bash terminal:
# python.exe analysis_helpers/identify_streaks --lfp "ADD COMPLETE PATH TO FOLDER WITH (AT LEAST ONE) EVENT LOG"
# --se "scheduling task: performing liver segmentation" --attribute "Message"
# #############################################################################

def output_dict_to_json(
  mapping_dict: dict[str, str], 
  output_folder: str, 
  file_name: str
) -> str:
  """
  Saves a dictionary as a JSON file in the specified folder and returns the file path.
  Creates the folder if it doesn't exist.
  """
  os.makedirs(output_folder, exist_ok=True)
  
  if not file_name.lower().endswith(".json"):
    file_name += ".json"

  file_path = os.path.join(output_folder, file_name)

  with open(file_path, "w", encoding="utf-8") as f:
    json.dump(mapping_dict, f, indent=4)

  return file_path

if __name__ == "__main__":
  parser = argparse.ArgumentParser()
  parser.add_argument("--lfp", required=True, type=str, help="Complete path directing to folder with event data")
  parser.add_argument("--se", nargs='+', required=True, help="The values of the event attributes that should serve as start events for the streaks ")
  parser.add_argument('--max_length', type=str, default='80', help="The maximum length of the streak")
  parser.add_argument("--attribute", type=str, required=True, help="The attribute name of the event data column that should be used to identify streaks")
  args = parser.parse_args()

  event_log_folder_path = args.lfp
  start_events = args.se
  attribute_name = args.attribute
  maximum_streak_length = int(args.max_length)

  for start_event in start_events:
    start_event_key = "_".join([start_event.split()[0], start_event.split()[-1]])

    streaks, find_streaks_function_logs = find_streaks_in_folder(
      parent_folder_path=event_log_folder_path, 
      column_name=attribute_name,
      start_event_message=start_event,
      function_logs=[],
      max_streak_length=maximum_streak_length
    )

    filtered_streaks, filtered_out_streaks = filter_streaks(
      prefix_counts= streaks,
      count_threshold=2
    )
    
    streaks_comparison_output_file = streak_comparison_output(
      streaks_counter=filtered_streaks,
      output_folder_path=os.path.join(event_log_folder_path, 'streaks_comparison'),
      output_file_name=f'filtered_streaks_started_at_{start_event_key}.txt'
    )

    streaks_comparison_output_file = streak_comparison_output(
      streaks_counter=filtered_out_streaks,
      output_folder_path=os.path.join(event_log_folder_path, 'streaks_comparison'),
      output_file_name=f'filtered_out_streaks_starting_at_{start_event_key}.txt'
    )

    streak_map = create_map_streak_to_id(
      streaks= [streak for streak, _ in filtered_streaks.items()],
      prefix=start_event_key
    )

    streak_map_output = {'-BREAK-'.join(streak): id for streak, id in streak_map.items()}

    map_output_path = output_dict_to_json(
      mapping_dict=streak_map_output,
      output_folder=os.path.join(event_log_folder_path, 'streaks_comparison'),
      file_name="_".join([start_event_key, "Map"])
    )
    print(f'output path streak map {map_output_path}')
