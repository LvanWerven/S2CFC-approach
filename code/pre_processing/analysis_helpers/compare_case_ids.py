import argparse
import os

from pre_processing.utils.general_utils import _is_csv_file, list_files_and_folders_in_folder, output_list_to_txt

# #############################################################################
# USE CASE:
# This script can be used to find Case ID's that are unique for both of the folders and occur in both the folders.
# 
# EXAMPLE USAGE:
# Make sure that the Case ID is in the title of the event log file. Otherwise change the implementation of _get_caseId_from_name
# 
# Run the following command in a bash terminal:
# "C:/Program Files/Python314/python.exe" -m analysis_helpers.compare_case_ids --lfp1="ADD COMPLETE PATH TO FOLDER WITH (AT LEAST ONE) EVENT LOG" --lfp2="ADD COMPLETE PATH TO FOLDER WITH (AT LEAST ONE) EVENT LOG" --ofp="ADD COMPLETE PATH TO OUTPUT FOLDER"
# #############################################################################

def _get_caseId_from_name(file_name: str):
  return file_name.split('_')[-1].replace('.csv', '')

if __name__ == "__main__":
  parser = argparse.ArgumentParser()
  parser.add_argument("--lfp1", required=True, type=str, help="Complete path directing to folder A with case logfiles")
  parser.add_argument("--lfp2", required=True, type=str, help="Complete path directing to folder B with case logfiles")
  parser.add_argument("--ofp", required=True, type=str, help="Complete path directing to folder where the output should be stored")
  args = parser.parse_args()

  case_folder_path_A = args.lfp1
  case_folder_path_B = args.lfp2
  output_folder_path = args.ofp

  file_names_A = list_files_and_folders_in_folder(case_folder_path_A)
  file_names_B = list_files_and_folders_in_folder(case_folder_path_B)

  case_ids_A = {
    _get_caseId_from_name(f)
    for f in file_names_A
    if _is_csv_file(os.path.join(case_folder_path_A, f))
  }

  case_ids_B = {
    _get_caseId_from_name(f)
    for f in file_names_B
    if _is_csv_file(os.path.join(case_folder_path_B, f))
  }

  # --- Compare sets ---
  in_both = sorted(case_ids_A & case_ids_B)
  only_in_A = sorted(case_ids_A - case_ids_B)
  only_in_B = sorted(case_ids_B - case_ids_A)

  # --- Save output ---
  output_lines_A = [
    f"Unique caseId's in folder: {case_folder_path_A}",
    '\n'.join(only_in_A)
  ]
  output_file_path = output_list_to_txt(
    output_lines_A,
    output_folder_path,
    'unique_caseIds_in_first_folder.txt'
  )
  print(f'Outputted in: {output_file_path}')

  output_lines = [
    f"Unique caseId's in folder: {case_folder_path_B}:",
    '\n'.join(only_in_B)
  ]

  output_file_path = output_list_to_txt(
    output_lines,
    output_folder_path,
    'unqiue_caseIds_in_second_folder.txt'
  )
  print(f'Outputted in: {output_file_path}')

  output_lines_both = [
    f"caseId's in both folders",
    '\n'.join(in_both)
  ]
  output_file_path = output_list_to_txt(
    output_lines_both,
    output_folder_path,
    'caseIds_in_both_folders.txt'
  )
  print(f'Outputted in: {output_file_path}')



