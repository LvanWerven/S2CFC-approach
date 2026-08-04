from collections import defaultdict
import csv
from datetime import timedelta
import os
import re
from typing import DefaultDict, Dict, List, Literal, Optional, Tuple, Union

import pandas as pd

from pre_processing.utils.general_utils import identify_substring, list_files_and_folders_in_folder, normalize_string


# #############################################################################
# STREAK RECOGNITION UTILS
# #############################################################################
# Transform a .json streak map (str->str) into a tuple-based streak map (tuple->str) for easier matching
def convert_dict_to_tuple_dict(
  str_str_dict: dict[str, str],
  seperator: str,
  remove_last_item: bool = False,
) -> dict[tuple[str, ...], str]:
  tuple_map: dict[tuple[str, ...], str] = {}
  for dash_key, value in str_str_dict.items():
    if dash_key == "":
      key_tuple: tuple[str, ...] = ()
    else:
      parts = [part.strip() for part in dash_key.split(seperator)]
      if remove_last_item:
        parts = parts[:-1]
      key_tuple = tuple(parts)
    tuple_map[key_tuple] = value
  
  return tuple_map

# The "streak recognition" function for a file, which abstracts streaks into start/end markers based on a prebuilt index and a complete streak map.
def abstract_streaks_to_event_file(
    input_file_path: str,
    map_prebuild_index: Dict[Tuple[str, ...], List[str]],
    map_seq_to_id: Dict[Tuple[str, ...], str],
    output_folder_path: str,
    function_logs: List[str] = [],
    files_with_abstraction_folder_path: str = '',
    match_mode: Literal["sequential", "ordered"] = "sequential",
    ordered_overlap_policy: Literal["greedy"] = "greedy",
    track_possible: bool = False,
    show_directly: bool = False
) -> Tuple[str, List[str]]:
  # --- Helper functions that preserve behavior and log messages exactly ---
  def _log(msg: str, show: bool = False) -> None:
    if show:
      print(str)
    function_logs.append(msg)

  def _streak_to_ids(streak_tokens: List[str]) -> List[str]:
    # Using prefix index; ensure empty tuple () is NOT present in index
    return map_prebuild_index.get(tuple(streak_tokens), [])

  def _close_streak_with_markers(id_full: str, start_row_src: dict, end_row_src: dict, rows_out: List[dict]) -> None:
    # Replace the streak rows with start/end markers
    start_row = dict(start_row_src)
    end_row = dict(end_row_src)
    start_row['Message'] = f'{id_full}_start'
    end_row['Message'] = f'{id_full}_end'
    rows_out.append(start_row)
    rows_out.append(end_row)

  def _is_full_match_contiguous(streak_tokens: List[str]) -> Optional[str]:
    """
    Full match occurs IFF there is exactly one candidate ID whose full sequence equals streak_tokens.
    Uses map_seq_to_id to validate exact equality.
    """
    candidate_ids = _streak_to_ids(streak_tokens)
    if len(candidate_ids) != 1:
      return None
    id_ = candidate_ids[0]
    # Recover the full sequence for id_ from map_seq_to_id (invert lookup)
    full_seq = None
    for seq_tuple, seq_id in map_seq_to_id.items():
      if seq_id == id_:
        full_seq = seq_tuple
        break
    return id_ if full_seq is not None and tuple(streak_tokens) == full_seq else None

  # Invert {sequence -> id} to {id -> sequence} for ordered mode
  id_to_seq: Dict[str, Tuple[str, ...]] = {}
  for seq, id_ in map_seq_to_id.items():
    id_to_seq[id_] = seq

  # ---------------------------
  # Mode A: Sequential (current behavior)
  # ---------------------------
  def _process_sequential() -> Tuple[List[dict], bool, List[str]]:
    """
    Preserve current behavior:
      - replace only full contiguous matches with start/end,
      - pass through partials,
      - if none closed, output equals input.
    """
    rows_out: List[dict] = []
    fieldnames: List[str] = []
    closed_any_streak: bool = False

    # Active streak state
    streak_tokens: List[str] = []
    streak_rows: List[dict] = []
    first_row: Optional[dict] = None
    last_row: Optional[dict] = None

    with open(input_file_path, 'r', encoding='utf-8', newline='') as infile:
      reader = csv.DictReader(infile)
      fieldnames = list(reader.fieldnames) if reader.fieldnames else []

      for row in reader:
        raw_message = row.get('Message', '')
        normalized_message = normalize_string(raw_message, remove_punctuation=False)
        serialized_message, _ = identify_substring(normalized_message, action='replace')

        extended_streak = streak_tokens + [serialized_message]
        candidates = _streak_to_ids(extended_streak)
        _log(f'Check extended streak "{extended_streak}", candidates: {candidates}, len: {len(candidates)}', show_directly)

        if not streak_tokens:
          # No active streak: start or pass through
          if candidates:
            streak_tokens = extended_streak
            streak_rows = [dict(row)]
            first_row = dict(row)
            last_row = dict(row)
            _log(f'Start streak with "{serialized_message}", candidates: {candidates}', show_directly)

            id_full = _is_full_match_contiguous(streak_tokens)
            if id_full and first_row is not None and last_row is not None:
              closed_any_streak = True
              _close_streak_with_markers(id_full, first_row, last_row, rows_out)
              _log(f'Closed streak on start (full match), ID: "{id_full}"', show_directly)
              # Reset streak state
              streak_tokens = []
              streak_rows = []
              first_row = None
              last_row = None
          else:
            rows_out.append(row)

        else:
          # Active streak: continue or break
          if candidates:
            streak_tokens = extended_streak
            streak_rows.append(dict(row))
            last_row = dict(row)
            _log(f'Continue streak with "{serialized_message}", candidates: {candidates}', show_directly)

            id_full = _is_full_match_contiguous(streak_tokens)
            if id_full and first_row is not None and last_row is not None:
              closed_any_streak = True
              _close_streak_with_markers(id_full, first_row, last_row, rows_out)
              _log(f'Closed streak (full match), ID: "{id_full}"', show_directly)
              # Reset streak state
              streak_tokens = []
              streak_rows = []
              first_row = None
              last_row = None
          else:
            # Break without full match: pass through original streak rows
            if streak_rows:
              rows_out.extend(streak_rows)
              _log(
                f'Break without full match on "{serialized_message}". '
                f'Passing through streak rows: {streak_tokens}',
                show_directly
              )

            # Reset streak and re-evaluate current row
            streak_tokens = []
            streak_rows = []
            first_row = None
            last_row = None

            re_candidates = _streak_to_ids([serialized_message])
            if re_candidates:
              # Start new streak with current row
              streak_tokens = [serialized_message]
              streak_rows = [dict(row)]
              first_row = dict(row)
              last_row = dict(row)
              _log(f'Restart streak with "{serialized_message}", candidates: {re_candidates}', show_directly)

              id_full = _is_full_match_contiguous(streak_tokens)
              if id_full and first_row is not None and last_row is not None:
                closed_any_streak = True
                _close_streak_with_markers(id_full, first_row, last_row, rows_out)
                _log(f'Closed streak immediately after restart (full match), ID: "{id_full}"', show_directly)
                streak_tokens = []
                streak_rows = []
                first_row = None
                last_row = None
            else:
              rows_out.append(row)

    # EOF: if a streak is open, close only if it's a full match; else pass through its rows
    if streak_tokens and streak_rows:
      id_full = _is_full_match_contiguous(streak_tokens)
      if id_full:
        closed_any_streak = True
        start_row_src = first_row if first_row is not None else streak_rows[0]
        end_row_src = last_row if last_row is not None else streak_rows[-1]
        _close_streak_with_markers(id_full, start_row_src, end_row_src, rows_out)
        _log(f'Closed streak at EOF (full match), ID: "{id_full}"', show_directly)
      else:
        rows_out.extend(streak_rows)
        _log(f'Open streak at EOF without full match: {streak_tokens}. Passed through.', show_directly)

    return rows_out, closed_any_streak, fieldnames

  # ---------------------------
  # Mode B: Ordered (subsequence; non-contiguous)
  # ---------------------------
  def _process_ordered() -> Tuple[List[dict], bool, List[str]]:
    """
    Ordered subsequence matching:
      - track possible streaks across the file (in order, but not necessarily contiguous),
      - when a full subsequence is found: replace first/last rows with start/end, remove internal matched rows,
      - non-streak rows preserved,
      - greedy policy to prevent overlaps,
      - if no full matches, write unchanged.
    """
    # Read entire file first
    with open(input_file_path, 'r', encoding='utf-8', newline='') as infile:
      reader = csv.DictReader(infile)
      fieldnames = list(reader.fieldnames) if reader.fieldnames else []
      rows_in = [row for row in reader]

    # Precompute canonical tokens per row
    tokens: List[str] = []
    for idx, row in enumerate(rows_in):
      raw_message = row.get('Message', '')
      serialized_message, _ = identify_substring(raw_message, action='replace')
      tokens.append(serialized_message)
    _log(f"serialized all the rows")

    # Tracker structure for possible streaks:
    class Tracker:
      __slots__ = ("id", "seq", "next_idx", "matched_indices")
      def __init__(self, id_: str, seq: Tuple[str, ...]):
        self.id = id_
        self.seq = seq
        self.next_idx = 0
        self.matched_indices: List[int] = []

      # def can_advance(self, token: str) -> bool:
      #   _log(f'check can advance, {self.next_idx < len(self.seq)} and {self.seq[self.next_idx] == token}')
      #   _log(f'with values: self.next_idx = {self.next_idx}')
      #   _log(f'with values: len(self.seq) = {len(self.seq)}')
      #   _log(f'with values: self.seq[self.next_idx] = {self.seq[self.next_idx]}')
      #   _log(f'with values: token = {token}')
      #   return self.next_idx < len(self.seq) and self.seq[self.next_idx] == token

      def can_advance(self, token: str) -> bool:
        if self.next_idx >= len(self.seq):
          return False
        expected = self.seq[self.next_idx]
        # Substring match (case-insensitive)
        _log(f"can advance? (expected.lower() in token.lower()) => {expected.lower() in token.lower()}")
        return expected.lower() in token.lower()

      def advance(self, row_idx: int) -> None:
        self.matched_indices.append(row_idx)
        self.next_idx += 1

      def is_complete(self) -> bool:
        return self.next_idx == len(self.seq)

      def next_expected(self) -> Optional[str]:
        return self.seq[self.next_idx] if self.next_idx < len(self.seq) else None

    # Active trackers (possible streaks)
    trackers: List[Tracker] = []
    # Accepted full matches (non-overlapping under greedy policy)
    matches: List[Tuple[str, int, int, List[int]]] = []  # (id, start_idx, end_idx, inner_indices)
    reserved: set[int] = set()  # row indices already consumed by accepted matches

    # Build fast lookup of sequences by first token for starting trackers
    first_token_to_ids: Dict[str, List[str]] = {}
    for id_, seq in id_to_seq.items():
      if not seq:
        continue
      first_token_to_ids.setdefault(seq[0], []).append(id_)

    # Scan rows and update trackers
    for i, token in enumerate(tokens):
      row_reserved = i in reserved
      # _log(f"token = {token}")
      # _log(f'Check row_reserved: {row_reserved}')

      # Advance existing trackers on non-reserved rows
      # _log(f'wat is de lengte van deze trackers? {len(list(trackers))}')
      for tr in list(trackers):
        if row_reserved:
          continue
        if tr.can_advance(token):
          tr.advance(i)

      # Start trackers on matching first token (non-reserved rows)
      if not row_reserved:
        # _log(f"wat is dit voor list?? ids: {first_token_to_ids}")

        for id_, seq in id_to_seq.items():
          if not seq:
            continue
          first = seq[0]
          # substring (or regex) match against token
          _log(f"first.lower() ({first.lower()}) in token.lower() ({token.lower()}) => {first.lower() in token.lower()} ")
          if first.lower() in token.lower():  # or: if first.lower() in token.lower()
            tr = Tracker(id_, seq)
            tr.advance(i)
            trackers.append(tr)
            
      # If tracking possible streaks, log status
      if track_possible:
        if trackers:
          status = ", ".join(
            f'{tr.id} next="{tr.next_expected()}" matched={len(tr.matched_indices)}'
            for tr in trackers
          )
          _log(f'Ordered mode: possible streaks after row {i}: {status}', show_directly)
        else:
          _log(f'Ordered mode: no possible streaks after row {i}.', show_directly)

      # Check for completed trackers
      completed = [tr for tr in trackers if tr.is_complete()]
      if completed:
        # Greedy policy: accept the first completed tracker
        accepted = completed[0]
        id_full = accepted.id
        matched = accepted.matched_indices
        start_idx, end_idx = matched[0], matched[-1]
        inner_idxs = matched[1:-1]

        # Record match and reserve indices
        matches.append((id_full, start_idx, end_idx, inner_idxs))
        for idx in matched:
          reserved.add(idx)

        _log(
          f'Ordered mode: closed subsequence streak for "{id_full}" '
          f'at rows {start_idx}..{end_idx} (inner={inner_idxs}).',
          show_directly
        )

        # Remove trackers that overlap reserved indices (block overlaps)
        trackers = [tr for tr in trackers if not any(idx in reserved for idx in tr.matched_indices)]

    # Build the output rows based on matches
    rows_out: List[dict] = []
    closed_any_streak: bool = len(matches) > 0

    # Create lookup for quick decision
    start_at: Dict[int, Tuple[str, int]] = {}
    end_at: Dict[int, Tuple[str, int]] = {}
    inner_drop: set[int] = set()

    for id_full, start_idx, end_idx, inner_idxs in matches:
      start_at[start_idx] = (id_full, end_idx)
      end_at[end_idx] = (id_full, start_idx)
      inner_drop.update(inner_idxs)

    # Construct output stream: replace starts/ends, drop inner, keep others
    for i, row in enumerate(rows_in):
      if i in inner_drop:
        # Abstract internal matched rows
        continue

      # Handle single-row streaks (start_idx == end_idx): write both markers at same position
      if (i in start_at) and (i in end_at):
        id_full, _ = start_at[i]
        start_row = dict(row)
        start_row['Message'] = f'{id_full}_start'
        rows_out.append(start_row)

        end_row = dict(row)
        end_row['Message'] = f'{id_full}_end'
        rows_out.append(end_row)
        continue

      if i in start_at:
        id_full, _ = start_at[i]
        start_row = dict(row)
        start_row['Message'] = f'{id_full}_start'
        rows_out.append(start_row)
        continue  # do not also write the original row

      if i in end_at:
        id_full, _ = end_at[i]
        end_row = dict(row)
        end_row['Message'] = f'{id_full}_end'
        rows_out.append(end_row)
        continue

      # Not part of any replacement => keep original
      rows_out.append(row)

    return rows_out, closed_any_streak, fieldnames

  # ---------------------------
  # Dispatch by mode and write output
  # ---------------------------
  if match_mode == "sequential":
    rows_out, closed_any_streak, fieldnames = _process_sequential()
  elif match_mode == "ordered":
    if ordered_overlap_policy != "greedy":
      raise ValueError(f'Unsupported ordered_overlap_policy: {ordered_overlap_policy}')
    rows_out, closed_any_streak, fieldnames = _process_ordered()
  else:
    raise ValueError(f'Unsupported match_mode: {match_mode}')

  file_name = os.path.basename(input_file_path)
  output_file_path = os.path.join(output_folder_path, file_name)
  if closed_any_streak and files_with_abstraction_folder_path != '':
    output_file_path = os.path.join(files_with_abstraction_folder_path, file_name)

  os.makedirs(os.path.dirname(output_file_path), exist_ok=True)
  with open(output_file_path, 'w', newline='', encoding='utf-8') as outfile:
    writer = csv.DictWriter(outfile, fieldnames=fieldnames)
    writer.writeheader() 
    writer.writerows(rows_out)
  return output_file_path, function_logs

# Creates a prefix indexed map of the streaks to spead up the matching operation
def map_build_prefix_index(
  map: dict[tuple[str, ...], str],
) -> dict[tuple[str, ...], List[str]]:
  """
  Build an index mapping every possible prefix to the list of IDs that begin with it.
  Preserves the insertion order of IDs (based on streak_to_id order).
  """
  index: DefaultDict[tuple[str, ...], List[str]] = defaultdict(list)
  seen: DefaultDict[tuple[str, ...], set] = defaultdict(set)

  # Populate prefix lists in the order streaks appear in streak_to_id
  for seq, id_ in map.items():
    for i in range(1, len(seq) + 1):
      prefix = seq[:i]
      if id_ not in seen[prefix]:
        seen[prefix].add(id_)
        index[prefix].append(id_)

  return dict(index)

# #############################################################################
# EVENT MAPPING UTILS
# #############################################################################
# Get event (if any) matching with the message using the regular expression
def lookup_event(
  message: str,
  regex_map: dict,
  function_logs: list[str] = []
) -> str | None:
  for pattern, value in regex_map.items():
    regex = re.compile(pattern)
    if regex.match(message):
      return value
  return None

# Uses a regular expression mapping to add a value to a specified column
def add_column_to_csv_file_mapping(
  input_file_path: str, 
  column_name: str, 
  key_column:str, 
  map: dict[str, str],
  direct_map: bool = True,
  keys_not_in_map: list[str] = [],
  output_folder_path: str = '',
  function_logs: list[str] = []
) -> tuple[str, list[str], list[str]]:
  with open(input_file_path, 'r', encoding='utf-8') as infile:
    reader = csv.DictReader(infile)
    fieldnames = list(reader.fieldnames) if reader.fieldnames else []
    if column_name not in fieldnames:
      fieldnames.append(column_name)
    rows = []
    for row in reader:
      key = row[key_column]
      key_serialized, _ = identify_substring(key, action='replace', function_logs=function_logs)
      value = map.get(key_serialized, None)
      if not direct_map:
        value = lookup_event(key_serialized, map)
      if not value:
        keys_not_in_map.append(f'The key: "{key_serialized}" was not in the map')
      row[column_name] = value
      rows.append(row)
  output_file_path = input_file_path
  if output_folder_path:
    file_name = os.path.basename(input_file_path)
    output_file_path = os.path.join(output_folder_path, file_name)
  os.makedirs(os.path.dirname(output_file_path), exist_ok=True)
  with open(output_file_path, 'w', newline='', encoding='utf-8') as outfile:
    writer = csv.DictWriter(outfile, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)

  return output_file_path, keys_not_in_map, function_logs

# #############################################################################
# REMOVE FALSE IDENTIFICATION UTILS
# #############################################################################
def parse_timespan(value: Union[int, float, timedelta]) -> timedelta:
    """
    Convert a timespan into a timedelta.

    Supported inputs:
    - timedelta -> returned unchanged
    - int/float -> interpreted as seconds
    """
    if isinstance(value, timedelta):
        return value

    if isinstance(value, (int, float)):
        return timedelta(seconds=float(value))

    raise TypeError(
        "timespan must be an int, float (seconds), or timedelta"
    )

def change_value_in_timespan(
  input_file_path: str,
  range_column: str,
  range_values: list[str],
  time_column: str,
  value_regex: str,
  change_column: str,
  timespan: Union[int, float, timedelta],
  new_change_value: str = "",
  to_change_value: Optional[str] = None,
  datetime_format: str = "%d %b %Y %H:%M:%S,%f",
  pattern_column: Optional[str] = None,
  output_file_path: Optional[str] = None,
  function_logs: list[str] = [],
):
  pattern_column = pattern_column or change_column

  window = parse_timespan(timespan)
  pattern = re.compile(value_regex)

  # Read CSV
  df = pd.read_csv(input_file_path, dtype=str)

  # Parse datetime column
  df["_parsed_time"] = pd.to_datetime(
    df[time_column],
    format=datetime_format,
    errors="raise",
  )

  last_trigger_time = None

  for index, row in df.iterrows():
    current_time = row["_parsed_time"]

    range_value = row[range_column]
    range_value = "" if pd.isna(range_value) else str(range_value)

    serialized_range_value, _ = identify_substring(
      range_value,
      action="replace",
    )

    function_logs.append(
      f"Check if {serialized_range_value} in {range_values}"
    )

    # Detect trigger rows
    if serialized_range_value in range_values:
      last_trigger_time = current_time
      function_logs.append(
        f"found trigger for phase_value: "
        f"{serialized_range_value} at row {index}"
      )

    if last_trigger_time is None:
      continue

    window_end = last_trigger_time + window

    pattern_value = row[pattern_column]
    pattern_value = "" if pd.isna(pattern_value) else str(pattern_value)

    serialized_pattern_value, _ = identify_substring(
      pattern_value,
      action="replace",
    )

    function_logs.append(
      f"value in pattern_column: {serialized_pattern_value} "
      f"and to_change_value: {to_change_value}"
    )

    matches_pattern = bool(
      pattern.search(str(serialized_pattern_value))
    )

    matches_change_value = (
      to_change_value is not None
      and serialized_pattern_value == to_change_value
    )

    if matches_pattern or matches_change_value:
      function_logs.append(
        "Regex pattern matches or removal value found"
      )

      if current_time <= window_end:
        function_logs.append("remove now")
        df.at[index, change_column] = new_change_value

    if current_time > window_end:
      last_trigger_time = None

  output_file_path = output_file_path or input_file_path

  df.drop(columns=["_parsed_time"]).to_csv(
    output_file_path,
    index=False,
    quoting=csv.QUOTE_MINIMAL,
  )

  return df, function_logs

# #############################################################################
# RANGE RECOGNITION UTILS
# #############################################################################
def add_value_in_range(
  input_file_path: str,
  output_file_path: str,
  value_to_add: str,
  target_column: str, # column to add value in
  range_column: str = '', # column to check the range status in, can only be empty when checking for emptiness of columns and starting from start
  from_values: list[str] = [],
  till_values: list[str] = [],
  till_value_inclusive: bool = True,
  from_value_inclusive: bool = True,
  extra_row_condition: dict[str, str] = {}, # {column name: regex pattern}, the row where the value is added should also adhere to this condition
  exit_when_not_empty: list[str] = [],
  overwrite_if_filled: bool = False,
  overwrite_exceptions_prefixes: list[str] = [],
  scan_direction: Literal['forward', 'backward'] = 'forward',
  substring_patterns: dict[str, str] = {},
  function_logs: list[str] = [],
  print_output_function_log: bool = False
):
  """
    Als overwrite_if_filled && overwrite_exceptions_prefixes == []:
      Schrijf de nieuwe waarde overal in de range (ongeacht of er al een waarde stond)
    Als overwrite_if_filled && overwrite_exceptions_prefixes != []:
      Schrijf de nieuwe waarde overal in de range (tenzij de oude waarde een prefix uit de exceptions heeft)
    Als !overwrite_if_filled && overwrite_exceptions_prefixes == []:
      Schrijf de nieuwe waarde alleen als er nog geen andere waarde is.
    Als !overwrite_if_filled && overwrite_exceptions_prefixes != []:
      Schrijf de nieuwe waarde alleen als er nog geen andere waarde is, tenzij de prefix van de oude waarde in de exceptions zit.
  """
  
  def _output_str(msg: str):
    function_logs.append(msg)
    if print_output_function_log:
      print(msg)

  def _check_add_new_value(old_message: str | None, row: dict[str, str]):
    if not isinstance(old_message, str) and not extra_row_condition:
      _output_str(f'5. No old message, add value')
      return True
    
    conform_with_extra_conditions = not extra_row_condition
    _output_str(f'Checking extra condition, starting with {conform_with_extra_conditions}')
    for column, pattern in extra_row_condition.items():
      value_pattern = re.compile(pattern)
      row_value = row[column]
      conform_with_extra_conditions = value_pattern.search(str(row_value))
      if not conform_with_extra_conditions:
        break
      _output_str(f'After round for column: {column}, conform value is: {conform_with_extra_conditions}')

    if not isinstance(old_message, str) and conform_with_extra_conditions:
      _output_str(f'6. No old message, and conform extra conditions')
      return True
    elif not isinstance(old_message, str) and not conform_with_extra_conditions:
      _output_str(f'7. No old message, but not conform extra conditions')
      return False
    elif not isinstance(old_message, str):
      _output_str(f'!! 8. No old message, and no boolean evaluation for extra_conditions ')
      return True
    
    message_prefix = old_message.split('_')[0]
    if overwrite_if_filled and len(overwrite_exceptions_prefixes) == 0 and conform_with_extra_conditions:
      _output_str(f'1. Overschrijf de waarde: True')
      return True
    elif overwrite_if_filled and len(overwrite_exceptions_prefixes) > 0:
      _output_str(f'2. Overschrijf de waarde: {message_prefix in overwrite_exceptions_prefixes}, prefix: {message_prefix}')
      return message_prefix not in overwrite_exceptions_prefixes and conform_with_extra_conditions
    elif not overwrite_if_filled and len(overwrite_exceptions_prefixes) == 0:
      _output_str(f'3. Overschrijf de waarde: {old_message == ''}, old_message: {old_message}')
      return old_message == '' and conform_with_extra_conditions
    
    _output_str(f'4. Overschrijf de waarde: {(old_message == '' or message_prefix in overwrite_exceptions_prefixes) and conform_with_extra_conditions}, old_message: {old_message}')
    return (old_message == '' or message_prefix in overwrite_exceptions_prefixes) and conform_with_extra_conditions

  def _check_value_in_list(value: str, value_list: list[str]):
    if value == '':
      return False
    for x in value_list:
      if value in x:
        return True
    return False
  
  def _exit_range(message_to_check: str, row: dict[str, str]) -> bool:
    if _check_value_in_list(message_to_check, till_values):
      _output_str(f'Exiting range at message: {message_to_check}, since in till_values')
      return True
    
    if len(exit_when_not_empty) > 0:
      for column_name in exit_when_not_empty:
        column_value = row.get(column_name, '')
        if column_value != '' and column_value != value_to_add:
          _output_str(f'Exiting range at message: {message_to_check}, since column {column_name} has a value: {column_value}')
          return True
    return False

  added_phase_value_in_file = False
  in_range = False
  function_logs.append(f'Start on file {input_file_path}')
  start_range = 0
  with open(input_file_path, 'r', encoding='utf-8') as infile:
    reader = csv.DictReader(infile)
    fieldnames = list(reader.fieldnames) if reader.fieldnames else []
    if target_column not in fieldnames:
      fieldnames.append(target_column)
    rows = list(reader)
    n = len(rows)
    indices = range(n) if scan_direction == 'forward' else range(n - 1, -1, -1)

    for i in indices:
      row = rows[i]
      message_to_check = row.get(range_column, '')
      serialized_message_to_check, _ = identify_substring(message_to_check, substring_patterns, action='replace')
      old_target_value = row.get(target_column)

      # Voeg target waardes wanneer we in bereik zijn
      if in_range:
        add_new_value = _check_add_new_value(old_target_value, row)
        if not add_new_value:
          _output_str(f"Skipping row with message '{serialized_message_to_check}' because target column already has value '{old_target_value}' and overwrite_if_filled is False.")
        else:
          row[target_column] = value_to_add
      else:
      # Als geen expliciete from_value is, dan altijd in range (vanaf start van scan)
        if len(from_values) == 0 and ((i==0 and scan_direction == 'forward') or (i==n-1 and scan_direction == 'backward')):
          in_range = True
          added_phase_value_in_file = True
          start_range = i
          _output_str('Entering range (no from_value set)')
          if from_value_inclusive and _check_add_new_value(old_target_value, row):
            row[target_column] = value_to_add
        # Check entering (from_value)
        elif len(from_values) > 0 and serialized_message_to_check and _check_value_in_list(serialized_message_to_check, from_values):
          in_range = True
          added_phase_value_in_file = True
          start_range = i
          _output_str(f'Entering range at message: {serialized_message_to_check}')
          if from_value_inclusive:
            row[target_column] = value_to_add

      if in_range and _exit_range(serialized_message_to_check, row) and start_range != i:
        in_range = False
        if not till_value_inclusive:
          row[target_column] = old_target_value

  with open(output_file_path, 'w', newline='', encoding='utf-8') as outfile:
    writer = csv.DictWriter(outfile, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)
    _output_str(f'Wrote updated file to {output_file_path}')

  return output_file_path, function_logs, added_phase_value_in_file

def recursive_add_value_in_range(
  parent_folder_path: str,
  output_folder_path: str,
  value_to_add: str,
  target_column: str,
  range_column: str = '',
  from_values: list[str] = [],
  till_values: list[str] = [],
  till_value_inclusive: bool = True,
  from_value_inclusive: bool = True,
  exit_when_not_empty: list[str] = [],
  overwrite_if_filled: bool = False,
  extra_row_condition: dict[str, str] = {}, # {column name: regex pattern}, the row where the value is added should also adhere to this condition
  overwrite_exceptions_prefixes: list[str] = [],
  scan_direction: Literal['forward', 'backward'] = 'forward',
  substring_patterns: dict[str, str] = {},
  function_logs: list[str] = [],
  print_output_function_log: bool = False
) -> tuple[list[str], list[str]]:
  filenames = list_files_and_folders_in_folder(parent_folder_path)
  missed_files = []
  for filename in filenames:
    full_path = os.path.join(parent_folder_path, filename)
    if os.path.isdir(full_path):
      recursive_add_value_in_range(
        parent_folder_path=full_path,
        output_folder_path=output_folder_path,
        range_column=range_column,
        target_column=target_column,
        value_to_add=value_to_add,
        from_values=from_values,
        till_values=till_values,
        till_value_inclusive=till_value_inclusive,
        from_value_inclusive=from_value_inclusive,  
        exit_when_not_empty=exit_when_not_empty,
        extra_row_condition=extra_row_condition,
        overwrite_if_filled=overwrite_if_filled,
        overwrite_exceptions_prefixes=overwrite_exceptions_prefixes,
        scan_direction=scan_direction,
        function_logs=function_logs,
        substring_patterns=substring_patterns,
        print_output_function_log=print_output_function_log
      )
      continue
    elif os.path.isfile(full_path) and full_path.endswith('.csv'):
      _, _, added_value_in_file = add_value_in_range(
        input_file_path=full_path,
        output_file_path=os.path.join(output_folder_path, filename),
        value_to_add=value_to_add,
        target_column=target_column,
        range_column=range_column,
        from_values=from_values,
        till_values=till_values,
        till_value_inclusive=till_value_inclusive,
        from_value_inclusive=from_value_inclusive,
        exit_when_not_empty=exit_when_not_empty,
        extra_row_condition=extra_row_condition,
        overwrite_if_filled=overwrite_if_filled,
        overwrite_exceptions_prefixes=overwrite_exceptions_prefixes,
        scan_direction=scan_direction,
        substring_patterns=substring_patterns,
        function_logs=function_logs,
        print_output_function_log=print_output_function_log
      )
      if not added_value_in_file:
        missed_files.append(full_path)
    else:
      print(f"⚠️ No valid log CSV file {full_path}")
  return missed_files, function_logs

# Used for annotating the beginning and the end of the activities from the event annotations
def annotate_phase_markers(
  input_csv_path: str,
  output_folder_path: str,
  threshold: int = 2,
  include_not_mapped_phase: bool = False,
  marker_column: str = "Activity Marker",
  phase_column: str = "Activity",
  marker_joiner: str = " ",
  phase_prefix: list[str] = [],
  apply_prefix_filter_to_not_mapped: bool = False,
  combine_markers: bool = False,
  function_logs: list[str] = [],
) -> Tuple[str, list[str]]:
  """
  Append a column with phase start/end markers based on contiguous segments and outlier rules,
  considering only phases whose key starts with a given prefix (default: '6').
  
  Implemented rules:
  - Outlier = contiguous run of a phase with length < threshold.
  - Start   = first row of each non-outlier segment (length >= threshold).
  - End     = last occurrence of that phase BEFORE the next non-outlier start of a DIFFERENT phase.
              If none exists after, end at the last occurrence of that phase in the file.
              The end may land on a later outlier occurrence of the same phase.

  Empty Activity handling:
  - include_not_mapped_phase == False:
      * Rows with empty Activity are kept in output but ignored for all logic (they do not contribute to segments).
  - include_not_mapped_phase == True:
      * Empty Activity is mapped to "not_mapped" and treated like any other phase (may be outlier/non-outlier),
        unless apply_prefix_filter_to_not_mapped=True and phase_prefix filtering is active.

  Activity prefix filter:
  - Only phases with keys starting with `phase_prefix` are considered in the segmentation/marking logic.
  - Rows with other phases are kept but ignored for logic.
  - "not_mapped" is included by default even though it does not start with the prefix,
    unless apply_prefix_filter_to_not_mapped=True.

  Assumptions:
  - Input rows are already chronological and should remain in their original order.
  - The `phase_column` values are already normalized and should be used as-is for markers.

  Parameters
  ----------
  input_csv_path : str
      Path to the input CSV file.
  output_csv_path : str
      Path to write the annotated CSV file.
  threshold : int, default=2
      Minimum contiguous segment length to be considered non-outlier.
  include_not_mapped_phase : bool, default=False
      Map empty Activity to "not_mapped" and include in logic (subject to prefix options).
  marker_column : str, default="Activity Marker"
      Name of the column where markers are written.
  phase_column : str, default="Activity"
      Name of the column containing the phase key.
  marker_joiner : str, default=" "
      String used between phase and 'start'/'end' (e.g., " " → "phase 6 start", "_" → "phase_6_start").
  phase_prefix : list[str], default=[]
      Only phases whose key starts with this prefix are considered.
  apply_prefix_filter_to_not_mapped : bool, default=False
      If True, "not_mapped" must also satisfy the prefix filter (it normally doesn't and will be excluded).

  Output
  ------
  Writes the CSV with an extra column containing: "<phase>{joiner}start", "<phase>{joiner}end", or "".

  Raises
  ------
  ValueError
      If threshold < 2 or phase_column not present in the CSV.
  """

  # Validate parameters
  if threshold < 2:
    raise ValueError("threshold must be >= 2 (a phase needs at least start and end).")

  # Load CSV (preserve original order)
  df = pd.read_csv(input_csv_path)

  filename = os.path.basename(input_csv_path)
  output_csv_path = os.path.join(output_folder_path, filename)

  if phase_column not in df.columns:
    raise ValueError(f"Column '{phase_column}' not found in the CSV.")

  # Prepare series (do not mutate original Activity values in df)
  phase_series = df[phase_column].fillna("").astype(str).str.strip()

  # Prepare the output column (only create if it doesn't exist)
  if marker_column not in df.columns:
    df[marker_column] = ""


  # Build candidate arrays used for segmentation and boundary logic.
  candidate_orig_idx: List[int] = []
  candidate_phase: List[str] = []

  def phase_passes_prefix(p: str) -> bool:
    return p.startswith(tuple(phase_prefix))

  if include_not_mapped_phase:
    for i, p in enumerate(phase_series):
      if p == "":
        mapped = "not_mapped"
        include_nm = (not apply_prefix_filter_to_not_mapped) or phase_passes_prefix(mapped)
        if include_nm:
          candidate_orig_idx.append(i)
          candidate_phase.append(mapped)
      else:
        if phase_passes_prefix(p):
          candidate_orig_idx.append(i)
          candidate_phase.append(p)
  else:
    # Ignore empty phases entirely, but keep rows in output
    for i, p in enumerate(phase_series):
      if p != "" and phase_passes_prefix(p):
        candidate_orig_idx.append(i)
        candidate_phase.append(p)

  # If no candidate rows match the prefix (or nothing to process), just save
  if not candidate_phase:
    df.to_csv(output_csv_path, index=False)
    return output_csv_path, function_logs

  # Build contiguous segments in candidate space
  segments = []
  curr_phase = candidate_phase[0]
  seg_start = 0
  for pos in range(1, len(candidate_phase) + 1):
    at_end = pos == len(candidate_phase)
    if at_end or candidate_phase[pos] != curr_phase:
      seg = {
        "phase": curr_phase,
        "cand_start": seg_start,
        "cand_end": pos - 1,  # inclusive
        "length": pos - seg_start,
      }
      segments.append(seg)
      function_logs.append(f"Identified segment: {seg['phase']} from candidate pos {seg['cand_start']} to {seg['cand_end']} (length {seg['length']})")
      if not at_end:
        curr_phase = candidate_phase[pos]
        seg_start = pos

  # Identify non-outlier segments
  non_outlier_seg_idxs = [i for i, s in enumerate(segments) if s["length"] >= threshold]

  for seg in non_outlier_seg_idxs:
    function_logs.append(f"Segment {seg}, {segments[seg]['phase']} is non-outlier (length {segments[seg]['length']} >= threshold {threshold})")

  # If none => nothing to mark
  if not non_outlier_seg_idxs:
    df.to_csv(output_csv_path, index=False)
    return output_csv_path, function_logs

  # Only start a phase when we switch to a DIFFERENT phase.
  effective_start_seg_idxs: List[int] = []
  active_phase_for_start = None
  for idx in non_outlier_seg_idxs:
    p = segments[idx]["phase"]
    function_logs.append(f"Evaluating segment {idx} for start marker: phase {p}, active_phase_for_start {active_phase_for_start}")
    if active_phase_for_start is None or p != active_phase_for_start:
      effective_start_seg_idxs.append(idx)
      active_phase_for_start = p
      function_logs.append(f"--> Marking segment {idx} as effective start segment.")
    else:
      pass

  # Precompute effective non-outlier starts (candidate positions) for boundary search
  effective_non_outlier_starts: List[Tuple[int, str]] = [
    (segments[i]["cand_start"], segments[i]["phase"]) for i in effective_start_seg_idxs
  ]

  def join_marker(phase_label: str, kind: str) -> str:
    return f"{phase_label}{marker_joiner}{kind}"

  # Place START markers
  for idx in effective_start_seg_idxs:
    seg = segments[idx]
    start_cand_pos = seg["cand_start"]
    start_orig_idx = candidate_orig_idx[start_cand_pos]
    start_marker = join_marker(seg["phase"], "start")
    existing = str(df.at[start_orig_idx, marker_column]).strip()
    if existing and existing != start_marker and combine_markers:
      df.at[start_orig_idx, marker_column] = existing + " | " + start_marker
    elif not existing:
      df.at[start_orig_idx, marker_column] = start_marker

  # Place END markers
  for idx in non_outlier_seg_idxs:
    seg = segments[idx]
    s_phase = seg["phase"]
    s_start_pos = seg["cand_start"]

    # Find boundary: next non-outlier start of a DIFFERENT phase
    boundary_pos = len(candidate_phase)
    for (cand_pos, phase_name) in effective_non_outlier_starts:
      if cand_pos > s_start_pos and phase_name != s_phase:
        boundary_pos = cand_pos
        break

    # Find last occurrence of s_phase before boundary_pos
    last_pos = None
    for p in range(s_start_pos, min(boundary_pos, len(candidate_phase))):
      if candidate_phase[p] == s_phase:
        last_pos = p

    if last_pos is None:
      # Safety fallback: last position of this segment
      last_pos = seg["cand_end"]

    end_orig_idx = candidate_orig_idx[last_pos]
    existing = str(df.at[end_orig_idx, marker_column]).strip()
    end_marker = join_marker(s_phase, "end")
    if existing and existing != end_marker and combine_markers:
      df.at[end_orig_idx, marker_column] = existing + " | " + end_marker
    else:
      df.at[end_orig_idx, marker_column] = end_marker

  # Write out
  df.to_csv(output_csv_path, index=False)

  return output_csv_path, function_logs

# Used to add the artificial end events
def add_events(
  file_path: str, 
  columns_to_copy: list[str],
  values_to_add: dict[str, str],
  copies: int = 2,
):
  with open(file_path, "r", newline="", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    fieldnames = list(reader.fieldnames) if reader.fieldnames else []
    rows = list(reader)

  last_row = rows[-1]

  # Build the new rows
  new_rows = []
  for _ in range(copies):
      new_row = {col: "" for col in fieldnames}
      for col in columns_to_copy:
          new_row[col] = last_row.get(col, "")
      for col, val in values_to_add.items():
          new_row[col] = val
      new_rows.append(new_row)

    # Write back (overwrite with original + new rows)
  with open(file_path, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)
    writer.writerows(new_rows)
