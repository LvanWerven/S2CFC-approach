
import argparse
from functools import partial
import os

from pre_processing.analysis_helpers.apply_streak_utils import extract_mustevents_streaks, read_dict_from_json
from pre_processing.utils.event_abstraction import abstract_streaks_to_event_file, convert_dict_to_tuple_dict, map_build_prefix_index
from pre_processing.utils.general_utils import _is_csv_file, list_files_and_folders_in_folder, output_list_to_txt, recursive_apply_to_files

# #############################################################################
# USE CASE:
# Test the streak abstractions found in using the identify_streaks.py script
# The script will apply the streak abstractions to the event logs in the specified folder and create new files with the abstracted events using the streak ids in the streak maps.
# 
# EXAMPLE USAGE:
# To identify the streaks for the autosegmentation, run the following command in a bash terminal:
# "C:/Program Files/Python314/python.exe" -m analysis_helpers.apply_streak --lfp="ADD COMPLETE PATH TO FOLDER WITH (AT LEAST ONE) EVENT LOG" \
# --mfp="ADD COMPLETE PATH TO FOLDER WITH STREAK MAP FILES (.JSON)" --attribute="Message"
# #############################################################################

if __name__ == "__main__":
  parser = argparse.ArgumentParser()
  parser.add_argument("--lfp", required=True, type=str, help="Complete path directing to folder with event data")
  parser.add_argument("--mfp", required=True, type=str, help="Complete path directing to folder with the streak map files")
  parser.add_argument("--attribute", type=str, required=True, help="The attribute name of the event data column that should be used to identify streaks")
  args = parser.parse_args()

  event_log_folder_path = args.lfp
  streak_map_folder_path = args.mfp
  attribute_name = args.attribute

  filenames = list_files_and_folders_in_folder(streak_map_folder_path)
    
  complete_streaks: dict[tuple[str, ...], str] = {}
  for filename in filenames:
    full_path = os.path.join(streak_map_folder_path, filename)
    streak_key = filename.removesuffix('_Map.json')
    if os.path.isfile(full_path) and full_path.endswith('_Map.json'):
      streak_map = read_dict_from_json(
        file_path=full_path
      )
      processed_streak_map = convert_dict_to_tuple_dict(
        str_str_dict = streak_map,
        seperator = '-BREAK-',
        remove_last_item=False
      )

      must_have_events, partials_with_counts = extract_mustevents_streaks(
        streak_variants_map= processed_streak_map,
        print_output=True
      )
      complete_streaks[must_have_events] = streak_key
  
  prefixed_map = map_build_prefix_index(
    map=complete_streaks
  )

  abstract_streaks_function = partial(
    abstract_streaks_to_event_file,
    map_prebuild_index=prefixed_map,
    map_seq_to_id=complete_streaks,
    output_folder_path=os.path.join(event_log_folder_path, 'files_with_abstraction'),
    files_with_abstraction_folder_path=os.path.join(event_log_folder_path, 'files_with_abstraction'),
    match_mode='sequential', 
    track_possible=False,
    show_directly=False
  )

  function_logs = recursive_apply_to_files(
    folder_path=event_log_folder_path,
    file_handler=abstract_streaks_function,
    file_filter=_is_csv_file,
    function_logs=[]
  )

  abstraction_function_log_output_file = output_list_to_txt(function_logs, event_log_folder_path, f'streaks_abstracted_function_log.txt')
  print(f'output abstraction log {abstraction_function_log_output_file}')

