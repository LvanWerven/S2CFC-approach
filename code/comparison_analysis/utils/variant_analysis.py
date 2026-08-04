# -----------------------------
# WORKSESSION EXTRACTION (WITH TIME)
# -----------------------------
import numpy as np
from pandas import Timedelta
import pandas as pd

from pre_processing.S2CF_config import END_ACTIVITIES, START_ACTIVITIES, ACTIVITY_COLUMN_NAME


def extract_worksessions_with_time(case_df):
  sessions = []
  current_session = []

  for _, row in case_df.iterrows():
    act = row[ACTIVITY_COLUMN_NAME]

    if act in START_ACTIVITIES:
      current_session = [row]

    elif current_session:
      current_session.append(row)

      if act in END_ACTIVITIES:
        sessions.append(current_session)
        current_session = []

  return sessions

# -----------------------------
# NORMALIZE ACTIVITY NAMES
# -----------------------------
def normalize_activity(act):
  if "_" in act:
    act = act.split("_", 1)[1]
  return act.replace("_", " ").lower()

def build_variant_table(
  sorted_variants: list[tuple[str, list[str]]],
  case_durations,
):
  rows = []
  variant_id = 1

  for variant, cases in sorted_variants:
    num_cases = len(cases)

    # --- Duration stats ---
    durations = [case_durations[c] for c in cases if c in case_durations]

    avg_duration = np.mean(durations) if durations else 0
    median_duration = np.median(durations) if durations else 0

    # Extract worksessions from variant (structure only)
    def extract_sessions_from_trace(trace):
      sessions = []
      current = []
      for act in trace:
        if act in START_ACTIVITIES:
          current = [act]
        elif current:
          current.append(act)
          if act in END_ACTIVITIES:
            sessions.append(tuple(current))
            current = []
      return sessions

    sessions = extract_sessions_from_trace(variant)

    for i, session in enumerate(sessions, start=1):
      activity_names = [normalize_activity(a) for a in session]

      rows.append({
        "Variant ID": variant_id,
        "Included Cases": num_cases,
        "Avg Duration (min)": round(avg_duration, 2),
        "Median Duration (min)": round(median_duration, 2),
        "Worksession Number": i,
        "Sequence": ", ".join(activity_names),
      })

    variant_id += 1

  result_df = pd.DataFrame(rows)
  return result_df