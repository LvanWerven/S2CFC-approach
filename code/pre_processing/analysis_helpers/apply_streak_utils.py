

from collections import Counter
import json
from typing import Dict, List, Tuple

def read_dict_from_json(file_path: str) -> dict[str, str]:
  """
  Reads a JSON file and returns its contents as a dictionary.
  """
  with open(file_path, "r", encoding="utf-8") as f:
    return json.load(f)


def extract_mustevents_streaks(
  streak_variants_map: Dict[Tuple[str, ...], str],
  print_output: bool = False,
) -> Tuple[Tuple[str, ...], List[Tuple[str, int]]]:
    tuple_list: List[Tuple[str, ...]] = list(streak_variants_map.keys())
    if not tuple_list:
      return tuple(), []

    # Count in how many distinct tuples each event appears.
    # Also capture first-seen location (tuple index, then position) to order outputs stably.
    presence_counter: Counter = Counter()
    first_seen_order: Dict[str, Tuple[int, int]] = {}

    for t_idx, events in enumerate(tuple_list):
      # Use a set to avoid double-counting the same event within one tuple.
      unique_in_tuple = set(events)
      for e in events:
        # Track first appearance position (for stable, intuitive ordering)
        if e not in first_seen_order:
            first_seen_order[e] = (t_idx, events.index(e))
      for e in unique_in_tuple:
        presence_counter[e] += 1

    total_tuples = len(tuple_list)
    first_tuple = tuple_list[0]

    # Ordered intersection: keep events from the first tuple that appear in all tuples.
    common_in_order = tuple(
        e for e in first_tuple
        if presence_counter.get(e, 0) == total_tuples
    )

    # Partials: events that are NOT in all tuples, ordered by first appearance across input.
    partials_with_counts = [
        (e, cnt) for e, cnt in presence_counter.items() if cnt < total_tuples
    ]
    partials_with_counts.sort(key=lambda item: first_seen_order[item[0]])

    if print_output:
      print(f"Found {len(tuple_list)} variants")
      streak_str = "\n -> ".join(common_in_order)
      print(streak_str)

      for event, count in partials_with_counts:
        print(f"Event '{event}', found only in {count} variants")

    return common_in_order, partials_with_counts
