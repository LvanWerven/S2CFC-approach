
import argparse
import os

from pre_processing.utils.general_utils import list_files_and_folders_in_folder

# #############################################################################
# USE CASE:
# To confirm whether the log file name was eligable to be used as Log ID, usable to identify in which worksession an event was generated, this script was used.
#  
# EXAMPLE USAGE:
# Run the following command in a bash terminal:
# "C:/Program Files/Python314/python.exe" -m analysis_helpers.confirm_unique_file_names --lfp="ADD COMPLETE PATH TO FOLDER WITH (AT LEAST ONE) EVENT LOG"
# #############################################################################


def recursive_check_double_logIds(parent_folder_path: str) -> None:
  log_id_set = set()
  double_ids = []
  filenames = list_files_and_folders_in_folder(parent_folder_path)
  for filename in filenames:
    full_path = os.path.join(parent_folder_path, filename)
    if os.path.isdir(full_path):
      recursive_check_double_logIds(full_path)
    elif os.path.isfile(full_path) and filename.startswith('Simplicity') and full_path.endswith('.log'):
      log_id = filename.split('.')[0]
      if log_id in log_id_set:
        double_ids.append(log_id)
        print(f'DUPLICATE LOG ID FOUND: {log_id} in file {full_path}')
      else:
        log_id_set.add(log_id)
    elif os.path.isfile(full_path) and filename.startswith('parsed_Simplicity') and full_path.endswith('.csv'):
      log_id = filename.replace('parsed_', '').split('.')[0]
      if log_id in log_id_set:
        double_ids.append(log_id)
        print(f'DUPLICATE LOG ID FOUND: {log_id} in file {full_path}')
      else:
        log_id_set.add(log_id)

if __name__ == "__main__":
  parser = argparse.ArgumentParser()
  parser.add_argument("--lfp", required=True, type=str, help="Complete path directing to folder with event data")
  args = parser.parse_args()
  event_log_folder_path = args.lfp

  print('Start with check')
  recursive_check_double_logIds(event_log_folder_path)
  print('Finished checking')
