
import argparse
import re

from pm_liver_workflow.code.pre_processing.utils.general_utils import output_list_to_txt
from pre_processing.utils.data_refining import extract_case_id_from_message

# #############################################################################
# USE CASE:
# Can be used to detect which logfiles contain events generated for wich case.
# 
# EXAMPLE USAGE:
# Make sure to fill in the correct ID pattern so the case ID can be found in the descriptive attribute by matching it to the regular expression pattern.
# 
# Run the following command in a bash terminal:
# "C:/Program Files/Python314/python.exe" -m analysis_helpers.get_map_of_files_per_case_id --lfp="ADD COMPLETE PATH TO FOLDER WITH (AT LEAST ONE) EVENT LOG" \
# --mfp="ADD COMPLETE PATH TO FOLDER WHERE THE COMPARISON OUTPUT SHOULD BE STORED" --cc="Case ID" --dc="Message"
# #############################################################################


ID_PATTERN = re.compile(r'\bID\s*(\d+)\b')

if __name__ == "__main__":
  parser = argparse.ArgumentParser()
  parser.add_argument("--lfp", required=True, type=str, help="Complete path directing to folder with event data")
  parser.add_argument("--ofp", default="", type=str, help="Complete path directing to folder with the output of the map")
  parser.add_argument("--cc", type=str, required=True, help="The attribute name in which the case ID should be stored")
  parser.add_argument("--dc", type=str, required=True, help="The attribute name in which the case ID can be found")
  args = parser.parse_args()

  event_log_folder_path = args.lfp
  output_folder_path = args.ofp
  caseId_column_name= args.cc
  descriptive_column_name = args.dc

  if not output_folder_path:
    output_folder_path = event_log_folder_path

  function_logs, study_to_files_map = extract_case_id_from_message(
    folder_path=event_log_folder_path,
    id_pattern=ID_PATTERN,
    build_study_to_files_map=True,
    caseId_column_name= caseId_column_name,
    descriptive_column_name= descriptive_column_name,
  )

  output_list_to_txt(function_logs, output_folder_path, f'function_logs_study_id.txt')

  study_id_lines = [f"{study_id}: {files}" for study_id, files in study_to_files_map.items()]
  study_id_lines.append(f"Total unique study IDs: {len(study_to_files_map)}, Total files: {sum(len(files) for files in study_to_files_map.values())}")

  output_list_to_txt(study_id_lines, output_folder_path, f'study_to_files_map.txt')

  