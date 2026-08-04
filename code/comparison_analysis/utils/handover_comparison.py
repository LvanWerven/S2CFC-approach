import csv
import os
from typing import List

# Used to count the changes within a file, aggregated for files in a folder. Used to count the handovers, where a file contains the whole execution of one case.
def count_switches_folder(
  file_paths: list[str],
  column_name: str,
  add_empty: bool = False,
) -> tuple[dict[str, int], dict[str, int], list[str]]:
  switch_count = {}
  switch_per_file = {}
  logs = []
  for file_path in file_paths:
    with open(file_path, 'r', encoding='utf-8', newline='') as infile:
      reader = csv.DictReader(infile)
      active_value = ''
      num_row = 0
      for row in reader:
        value = row.get(column_name, '')
        if num_row == 0 and (add_empty or value != ''):
          active_value = value
        elif active_value != value:
          logs.append(f'switch: {active_value} -> {value}')
          switch_name = f"{active_value}_{value}"
          count = switch_count.get(switch_name, 0)
          switch_count[switch_name] = count+1
          active_value = value

          file_name = os.path.basename(file_path).replace('.csv', '')
          count_switch = switch_per_file.get(file_name, 0)
          switch_per_file[file_name] = count_switch+1

        num_row = num_row+1
      
  return switch_count, switch_per_file, logs

# Used to create a latex table used as a representation of the handover analysis
def create_handover_latex_table(
  table_rows: List[str],
  output_folder_paths: List[str],
  execution_name: str,
):
  latex_table = rf"""
    \begin{{table}}[ht]
        \centering
        \caption{{The handover metrics over the different datasets, where the ratio is calculated as the total number of handovers divided by the number of studies and rounded on three decimal places.}}
        \label{{tab:handover-comparison}}
        \begin{{tabularx}}{{\textwidth}}{{X C{{3cm}} C{{3cm}} C{{3cm}}}}
        \toprule
        \textbf{{Dataset}} & \textbf{{Total number of handovers}} & \textbf{{Number of studies}} & \textbf{{Ratio handovers per study}} \\
        \midrule
        {'\n    \\addlinespace\n    '.join(table_rows)}
        \bottomrule
        \end{{tabularx}}
    \end{{table}}
    """

  for path in output_folder_paths:
    output_file_path = os.path.join(path, f'handover_latex_table_{execution_name}.txt') 
    with open(output_file_path, 'w', encoding="utf-8") as f:
      f.write(latex_table)