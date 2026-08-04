import math
from typing import Any, Dict, Iterable, Literal, Tuple
import numpy as np
import pandas as pd
import scipy.stats as stats
import networkx as nx
from pyvis.network import Network
from collections import defaultdict
import json

from pre_processing.S2CF_config import END_DATETIME_COLUMN_NAME, START_DATETIME_COLUMN_NAME


class EventLogStore:
  def __init__(self, file_path, case_id_col, activity_col, timestamp_col):
    self.case_id_col = case_id_col
    self.activity_col = activity_col
    self.timestamp_col = timestamp_col
    
    # 1. Load the CSV
    self.df = pd.read_csv(file_path)
    
    # Ensure timestamps are actual datetime objects for proper ordering
    self.df[self.timestamp_col] = pd.to_datetime(self.df[self.timestamp_col], format="%d %b %Y %H:%M:%S,%f")
    
    # Sort by Case ID and Timestamp to ensure traces are chronological
    self.df = self.df.sort_values(by=[self.case_id_col, self.timestamp_col])
    
    # 2. Build the Trace Map (The core for Transition Systems)
    self.trace_map = {
      case_id: group.to_dict('records') 
      for case_id, group in self.df.groupby(self.case_id_col)
    }

  def get_event(self, row_index):
    """Inspect a specific event by row index."""
    return self.df.iloc[row_index]

  def get_trace(self, case_id):
    """Retrieve all events for a specific case."""
    return self.trace_map.get(case_id, [])

  def get_all_case_ids(self):
    return list(self.trace_map.keys())
  
class StateMapper:
  @staticmethod
  def set_abstraction(trace_prefix, activity_key):
    """
    rs(trace) = { attr(e) | e in trace }
    Represent state as a frozenset of unique activities performed.
    Using frozenset makes the state 'hashable' (usable as a dictionary key).
    """
    return frozenset(event[activity_key] for event in trace_prefix)

  @staticmethod
  def last_activity_set_abstraction(trace_prefix, activity_key):
    """
    State abstraction = { last_activity }
    Returns a frozenset containing only the activity of the last event.
    """
    if not trace_prefix:
      return frozenset()   # empty prefix → empty state
    
    last_event = trace_prefix[-1]
    return frozenset([last_event[activity_key]])

  @staticmethod
  def sequence_abstraction(trace_prefix, activity_key, x=None):
    """
    An alternative: rs(trace) = <e1, e2, ..., en>
    Keeps the exact order of activities.
    """
    if x is not None:
      trace_prefix = trace_prefix[-x:]  # keep only last x events
    return tuple(event[activity_key] for event in trace_prefix)
  
class ActivityMapper:
  @staticmethod
  def get_activity(event, activity_key):
    """
    ra(e) = attr(e)
    Extracts the activity label from an event.
    """
    return event.get(activity_key)

  @staticmethod
  def get_resource_activity(event, resource_key='org:resource'):
    """
    Example of an alternative: ra(e) = resource(e)
    Useful if you want to build a social network or resource transition system.
    """
    return event.get(resource_key)
  
  
class TransitionSystem:
  def __init__(self, name):
    self.name = name
    # A dictionary of states. Key: State (tuple), Value: Metadata (count)
    self.states = defaultdict(int)
    # A nested dictionary: source -> { (activity, target): count }
    self.transitions = defaultdict(lambda: defaultdict(int))
    # To track start and end states
    # self.initial_state = frozenset() #Does not work with sequences or multisetstates
    self.initial_state = tuple()  # empty tuple represents the initial state
    self.final_states = defaultdict(int)

  def add_transition(self, source, activity, target):
    self.states[source] += 1
    self.transitions[source][(activity, target)] += 1

  def mark_final(self, state):
    self.final_states[state] += 1

  def build_from_log(self, log_store, state_func, activity_func) -> list[str]:
    function_logs = []
    activity_key = log_store.activity_col
    
    for case_id in log_store.get_all_case_ids():
      trace = log_store.get_trace(case_id)
      function_logs.append(f'-----{case_id}-----')
      function_logs.append("\n".join([f"{event[log_store.timestamp_col]}-{event[activity_key]}" for event in trace]))
      
      # Every trace starts at the empty state (Initial State)
      current_state = self.initial_state
      
      for event in trace:
        # 1. ra(e)
        label = activity_func(event, activity_key)
        
        # 2. rs(prefix) - We calculate the next state
        index = trace.index(event)
        next_state = state_func(trace[:index+1], activity_key)
        
        # 3. Record the movement
        self.add_transition(current_state, label, next_state)
        current_state = next_state
      
      # Mark the last state reached as a final state for this trace
      self.mark_final(current_state)
    return function_logs  # Return logs for inspection/debugging

  def visualize_interactive(self, filename="transition_system.html"):
    """
    Visualizes the transition system using Pyvis.
    Generates an interactive HTML file.
    """
    # 1. Create a NetworkX directed graph
    G = nx.MultiDiGraph()

    # 2. Add Nodes
    for state, count in self.states.items():
      state_label = str(state) if state else "START"
      # Color coding: Green for start, Orange for final, Blue for regular
      color = "#2ecc71" if not state else ("#e67e22" if state in self.final_states else "#3498db")
      
      G.add_node(
        str(state), 
        label=state_label, 
        title=f"Frequency: {count}", # Shows on hover
        color=color,
        shape="dot",
        size=20 + (count * 0.1) # Larger nodes for frequent states
      )

    # 3. Add Edges
    for source, targets in self.transitions.items():
      for (activity, target), count in targets.items():
        G.add_edge(
          str(source), 
          str(target), 
          label=f"{activity} ({count})",
          title=f"Occurrences: {count}",
          width=1 + (count * 0.1) # Thicker lines for the "Happy Path"
        )

    # 4. Convert to Pyvis and Save
    net = Network(height="750px", width="100%", notebook=False, directed=True, heading=self.name)
    net.from_nx(G)
    
    net.set_options("""
      {
      "nodes": {
        "shape": "dot",
        "size": 16,
        "physics": false,
        "font": { "face": "Inter, Arial", "color": "#222222", "size": 14 }
      },
      "edges": {
        "arrows": { "to": { "enabled": true, "scaleFactor": 0.8 } },
        "smooth": { "enabled": true, "type": "dynamic" },
        "font": { "face": "Inter, Arial", "color": "#222222", "size": 12, "strokeWidth": 0 }
      },
      "interaction": { "hover": true, "tooltipDelay": 50 },
      "physics": { 
        "stabilization": true, 
        "barnesHut": { "gravitationalConstant": -4000 }
      }
    } """
    )
    net.write_html(filename)
    print(f"Interactive Transition System saved as {filename}. Open this file in your browser.")

  def build_from_two_logs(self, log1, log2, state_func, activity_func, log_id_attr="__log_id__"):
    """
    Build one transition system from two logs, keeping traces distinguishable
    by adding a synthetic attribute to each event (e.g., '__log_id__': 'L1' or 'L2').

    Parameters:
    - log1, log2: log_store objects
    - state_func: state abstraction function (r^s)
    - activity_func: activity abstraction function (r^a)
    - log_id_attr: name of the synthetic attribute marking log origin
    """
    function_logs = []
    activity_key = log1.activity_col   # assume same schema

    def get_all_traces(log, label):
      """Extract all traces and mark their events with origin label."""
      traces = []
      for case_id in log.get_all_case_ids():
        trace = log.get_trace(case_id)
        # Add distinguishing attribute
        for event in trace:
          event[log_id_attr] = label
        traces.append(trace)
      function_logs.append(
        "Example trace:\n - " +
        "\n - ".join(f"{k}" for k in traces[0])
      )
      return traces

    # 1. Extract and tag traces
    function_logs.append(f'get all traces of L1')
    traces_L1 = get_all_traces(log1, "L1")
    function_logs.append(f'get all traces of L2')
    traces_L2 = get_all_traces(log2, "L2")

    function_logs.append(f'------------Start looping through traces------------')
    function_logs.append(f'initial state: {self.initial_state}')
    # 2. Process all traces in a single unified TS
    for trace in traces_L1 + traces_L2:

      current_state = self.initial_state

      # iterate over events with increasing prefix
      for idx, event in enumerate(trace):
        function_logs.append(f'Add {idx}th event: {event}')
        # activity label via r^a
        activity_label = activity_func(event, activity_key)
        function_logs.append(f'created activity label using func: {activity_label}')
        # compute r^s(prefix)
        prefix = trace[:idx + 1]
        function_logs.append(f'Get prefix of event {"\n - ".join(f"{e}" for e in prefix)}')

        next_state = state_func(prefix, activity_key)
        function_logs.append(f'found next_state: {next_state}')
        # add transition
        self.add_transition(current_state, activity_label, next_state)
        # move forward
        current_state = next_state

      # mark final state
      self.mark_final(current_state)
      function_logs.append(f"final state: {current_state}")

    print("Transition system built from two logs (L1 + L2).")
    return function_logs

class StateMeasurementMapper:
  @staticmethod
  def is_state_reached(trace, activity_key, state_repr_func, target_state):
    """
    Checks whether the target_state is reached in any prefix of the trace.
    Returns 1 if reached, 0 if not.
    (Keep the 0 here! We want 0s for probability/frequency averages).
    """
    for i in range(len(trace)):
      prefix = trace[: i + 1]
      state = state_repr_func(prefix, activity_key)

      if state == target_state:
        return 1
    return 0
  
  @staticmethod
  def state_sojourn_time(
    trace,
    activity_key,
    state_repr_func,
    target_state,
    timestamp_key=START_DATETIME_COLUMN_NAME,
    end_timestamp_key=END_DATETIME_COLUMN_NAME
  ):
    """
    Sojourn time = total duration of all events that resolve to the target_state.
    Returns None if the state is never visited in this trace.
    """
    total_duration = 0.0
    state_was_visited = False

    for i in range(len(trace)):
        prefix = trace[: i + 1]
        current_state = state_repr_func(prefix, activity_key)
        
        if current_state == target_state:
            state_was_visited = True
            start_dt = pd.to_datetime(trace[i][timestamp_key], format='mixed')
            end_dt = pd.to_datetime(trace[i][end_timestamp_key], format='mixed')
            
            duration = (end_dt - start_dt).total_seconds()
            total_duration += duration

    # Return None so we don't skew the averages with 0.0s for missed states
    if state_was_visited:
        return total_duration
    return None

  @staticmethod
  def time_to_reach_state(
      trace,
      activity_key,
      state_repr_func,
      target_state,
      timestamp_key = START_DATETIME_COLUMN_NAME
  ):
    """
    Measures time until target_state is first reached.
    Returns None if the state is never reached.
    """
    start_time = pd.to_datetime(trace[0][timestamp_key], format='mixed')

    for i in range(len(trace)):
        prefix = trace[: i + 1]
        state = state_repr_func(prefix, activity_key)

        if state == target_state:
            reached_at = pd.to_datetime(trace[i][timestamp_key], format='mixed')
            return (reached_at - start_time).total_seconds()

    # State not reached, return None to exclude from average
    return None
  
class TransitionMeasurementMapper:
  @staticmethod
  def transition_occurrence(
    trace, 
    activity_key, 
    state_repr_func, 
    transition_repr_func, 
    target_transition,
    source_state, 
    target_state
  ):
    for k in range(len(trace)):
        prefix = trace[:k+1]

        if transition_repr_func(prefix[-1], activity_key) != target_transition:
            continue

        if state_repr_func(prefix[:-1], activity_key) == source_state and \
           state_repr_func(prefix, activity_key) == target_state:
            return 1
    return 0
  
  @staticmethod
  def transition_delay(
    trace,
    activity_key,
    state_repr_func,
    transition_repr_func,
    target_transition,
    source_state,
    target_state,
    timestamp_key=START_DATETIME_COLUMN_NAME,
    end_timestamp_key=END_DATETIME_COLUMN_NAME
  ):
    """
    Measures transition delay between source_state and target_state via a specific activity.
    """
    previous_event = None
    previous_state = state_repr_func([], activity_key) # Initialize as the starting state

    for i in range(len(trace)):
        prefix = trace[: i + 1]
        current_state = state_repr_func(prefix, activity_key)
        current_event = trace[i]
        
        if previous_event is not None:
            current_activity = transition_repr_func(current_event, activity_key)
            
            if (previous_state == source_state and 
                current_activity == target_transition and 
                current_state == target_state):
                
                start_time = pd.to_datetime(previous_event[end_timestamp_key], format='mixed')
                end_time = pd.to_datetime(current_event[timestamp_key], format='mixed')
                
                return (end_time - start_time).total_seconds()

        previous_state = current_state
        previous_event = current_event

    return None
  
class Annotation:
  @staticmethod
  def annotate_state(log, activity_key, state_repr_func, state_measure_func, target_state):
    """
    Produces a multiset of numerical measurements for a given state.
    
    Parameters:
    - log: list of traces
    - activity_key: event attribute used for abstraction
    - state_repr_func: state abstraction function r^s
    - state_measure_func: measurement function m(σ, s)
    - target_state: the state we are annotating

    Returns:
    - list of integers (multiset of measurements)
    """
    measurements = []

    for trace in log:
      value = state_measure_func(
        trace=trace,
        activity_key=activity_key,
        state_repr_func=state_repr_func,
        target_state=target_state
      )
      measurements.append(value)

    return measurements  # Multiset

  @staticmethod
  def annotate_transition(
    log, activity_key, state_repr_func, transition_repr_func,
    transition_measure_func, target_transition
  ):
    """
    Produces a multiset of numerical measurements for a given transition.
    
    Parameters:
    - log: list of traces
    - activity_key: event attribute used
    - state_repr_func: r^s (may or may not be used depending on measurement)
    - transition_repr_func: r^t
    - transition_measure_func: m(σ, t)
    - target_transition: transition being annotated
    
    Returns:
    - list of integers (multiset of measurements)
    """
    measurements = []

    for trace in log:
      value = transition_measure_func(
        trace=trace,
        activity_key=activity_key,
        state_repr_func=state_repr_func,
        transition_repr_func=transition_repr_func,
        target_transition=target_transition
      )
      measurements.append(value)

    return measurements
  
class SignificanceTest:
  @staticmethod
  def _comparison_oracle(
    samples_a: Iterable[float],
    samples_b: Iterable[float],
    alpha: float = 0.05,
    normality_alpha: float = 0.05,
    normality_test: str = "auto",
  ) -> Tuple[bool, Dict[str, Any]]:
    
    """
    Decide if two multisets of numerical measurements differ significantly.

    Strategy:
      1) Test normality per group.
      2) If both look normal -> two-tailed Welch's t-test.
         Else -> two-sided Mann-Whitney U-test.

    Parameters
    ----------
    samples_a, samples_b : Iterable[float]
        The two multisets (e.g., annotations from L1 and L2).
    alpha : float, default=0.05
        Significance level for the difference test.
    normality_alpha : float, default=0.05
        Significance level for the normality test.
    normality_test : {'auto', 'shapiro', 'dagostino'}
        - 'auto': Shapiro for n <= 5000; D'Agostino K^2 for larger n (if feasible).
        - 'shapiro': Shapiro-Wilk test.
        - 'dagostino': D'Agostino K^2 test (requires n >= 8).

    Returns
    -------
    is_different : bool
        True if we reject the null hypothesis of equal distributions (p < alpha).
    info : dict
        Diagnostics including chosen test, p-value, statistic, sample sizes,
        and normality results.
    """
    # ---------- Prepare data ----------
    a = np.array(list(samples_a), dtype=float)
    b = np.array(list(samples_b), dtype=float)
    # Drop NaNs/inf
    a = a[np.isfinite(a)]
    b = b[np.isfinite(b)]

    n_a, n_b = len(a), len(b)
    if n_a == 0 or n_b == 0:
        raise ValueError("Both samples must contain at least one finite numeric value.")
    if n_a < 2 or n_b < 2:
        # With <2 values per group, hypothesis testing is ill-defined.
        # Default to Mann-Whitney for minimal ordinal comparison if both >=2 are not available.
        # But if one group has only 1 value, we cannot run rank tests either; bail out.
        raise ValueError("Both samples must contain at least two observations to run tests.")

    # ---------- Normality testing ----------
    normal_flags = {"A": False, "B": False}
    normal_pvals = {"A": np.nan, "B": np.nan}

    def run_shapiro(x: np.ndarray):
        from scipy.stats import shapiro
        # Shapiro in SciPy supports n in [3..5000] reliably
        if len(x) < 3:
            return False, np.nan
        stat, p = shapiro(x)
        return (p >= normality_alpha), p

    def run_dagostino(x: np.ndarray):
        from scipy.stats import normaltest
        # D'Agostino K^2 requires n >= 8 for stability
        if len(x) < 8:
            return False, np.nan
        stat, p = normaltest(x)
        return (p >= normality_alpha), p

    def auto_normality(x: np.ndarray):
        # Heuristic: use Shapiro for n <= 5000, else D'Agostino (if n>=8)
        if len(x) <= 5000:
            return run_shapiro(x)
        else:
            return run_dagostino(x)

    if normality_test == "shapiro":
        normal_flags["A"], normal_pvals["A"] = run_shapiro(a)
        normal_flags["B"], normal_pvals["B"] = run_shapiro(b)
    elif normality_test == "dagostino":
        normal_flags["A"], normal_pvals["A"] = run_dagostino(a)
        normal_flags["B"], normal_pvals["B"] = run_dagostino(b)
    elif normality_test == "auto":
        normal_flags["A"], normal_pvals["A"] = auto_normality(a)
        normal_flags["B"], normal_pvals["B"] = auto_normality(b)
    else:
        raise ValueError("normality_test must be one of {'auto', 'shapiro', 'dagostino'}.")

    both_normal = normal_flags["A"] and normal_flags["B"]
    # ---------- Hypothesis test selection ----------
    test_used = None
    stat = np.nan
    p_value = np.nan

    if both_normal:
        # Welch's t-test (two-tailed)
        from scipy.stats import ttest_ind
        res = ttest_ind(a, b, equal_var=False, alternative="two-sided")  
        if hasattr(res, "statistic") and hasattr(res, "pvalue"):
          stat = float(getattr(res, 'statistic'))
          p_value = float(getattr(res, 'pvalue'))
        else: 
          raise ValueError("Could not find the stat and/or p_value")

        test_used = "welch_t"
    else:
        # Mann-Whitney U (two-sided). Handle ties via 'asymptotic' if needed.
        from scipy.stats import mannwhitneyu
        # method='auto' lets SciPy pick 'exact' (small n, no ties) or 'asymptotic' (otherwise)
        res = mannwhitneyu(a, b, alternative="two-sided", method="auto")
        stat = float(res.statistic)
        p_value = float(res.pvalue)
        test_used = "mannwhitney_u"

    is_different = bool(p_value < alpha)

    info = {
      "test_used": test_used,
      "alpha": alpha,
      "p_value": p_value,
      "statistic": stat,
      "n": {"A": n_a, "B": n_b},
      "normality_alpha": normality_alpha,
      "normality": {
          "A": {"is_normal": normal_flags["A"], "p_value": normal_pvals["A"]},
          "B": {"is_normal": normal_flags["B"], "p_value": normal_pvals["B"]},
      },
      "both_normal": both_normal,
      "means": {"A": float(np.mean(a)), "B": float(np.mean(b))},
      "stds": {"A": float(np.std(a, ddof=1)), "B": float(np.std(b, ddof=1))},
    }

    return is_different, info
  
  @staticmethod
  def _fishers_exact(l1, l2, alpha):
    """
    Calculates the p-value using Fisher's Exact Test.
    Returns a p-value between 0 and 1.
    """
    # Create the 2x2 table
    table = np.array([
        [l1.count(1), l1.count(0)],
        [l2.count(1), l2.count(0)]
    ])
    
    _, p_value = stats.fisher_exact(table)
    
    info = {
      "test_used": 'fishers_exact',
      "alpha": alpha,
      "p_value": p_value,
    }

    is_different = bool(p_value < alpha)
    return is_different, info

class EffectSizeTest:
  @staticmethod
  def _cohens_d(samples_a, samples_b):
    """
    Computes Cohen's d effect size for two independent samples and returns:
      - effect_size: absolute magnitude of the effect (float)
      - sign: +1 if A > B, -1 if A < B, 0 if equal

    Uses the pooled SD for unequal variances (recommended Welch formulation).
    """

    a = np.asarray(samples_a, dtype=float)
    b = np.asarray(samples_b, dtype=float)

    a = a[np.isfinite(a)]
    b = b[np.isfinite(b)]

    if len(a) < 2 or len(b) < 2:
        return 0.0, 0

    mean_a = float(np.mean(a))
    mean_b = float(np.mean(b))

    var_a = float(np.var(a, ddof=1))
    var_b = float(np.var(b, ddof=1))

    # Pooled SD for unequal variances (Welch)
    pooled_sd = np.sqrt((var_a + var_b) / 2)

    if pooled_sd == 0:
        # No variance = no effect or perfectly separated distributions
        if mean_a == mean_b:
            return 0.0, 0
        return float('inf'), (1 if mean_a > mean_b else -1)

    # Cohen's d
    d = (mean_a - mean_b) / pooled_sd

    sign = 0
    if d > 0:
        sign = 1
    elif d < 0:
        sign = -1

    return abs(float(d)), sign

  @staticmethod
  def _cliffs_delta(samples_a, samples_b):
    """
    Computes Cliff's delta effect size for two independent samples.
    Returns:
        - effect_size: absolute magnitude of the effect (float between 0.0 and 1.0)
        - sign: +1 if A > B, -1 if A < B, 0 if equal
    
    Perfect for skewed process mining durations and unequal sample sizes.
    """
    # Convert to numpy arrays
    a = np.asarray(samples_a, dtype=float)
    b = np.asarray(samples_b, dtype=float)

    # Remove NaNs and infs
    a = a[np.isfinite(a)]
    b = b[np.isfinite(b)]

    n_a, n_b = len(a), len(b)
    if n_a == 0 or n_b == 0:
        return 0.0, 0  # No effect size possible

    # Matrix comparison (broadcasting)
    diff_matrix = a[:, None] - b
    
    pos = np.sum((diff_matrix > 0).astype(int))
    neg = np.sum((diff_matrix < 0).astype(int))
    
    # Cliff's delta ranges from -1 to +1
    d = (pos - neg) / (n_a * n_b)

    sign = 0
    if d > 0:
        sign = 1
    elif d < 0:
        sign = -1

    return abs(float(d)), sign

  @staticmethod
  def _odds_ratio(l1, l2, dmax=3.0):
    """
    Calculates the Odds Ratio and a symmetrical direction/magnitude score.
    Returns: (raw_odds_ratio, symmetrical_score)
    
    Symmetrical Score Mapping:
    - inf  -> Overwhelmingly L1 (Bright Green)
    - +val -> Leans L1          (Medium Green)
    - 0    -> Neutral           (Dark/Dull Purple)
    - -val -> Leans L2          (Medium Purple)
    - -inf -> Overwhelmingly L2 (Bright Purple)
    """
    a = l1.count(1) # L1 Occurred
    b = l1.count(0) # L1 Did not occur
    c = l2.count(1) # L2 Occurred
    d = l2.count(0) # L2 Did not occur
    
    # 1. Handle the extreme "Infinite" cases first
    # Case A: Strongest possible L1 effect (either L1 never fails, or L2 never succeeds)
    if b == 0 or c == 0:
      if (a == 0 and b == 0) or (c == 0 and d == 0): # Empty check
        return 0.0, 0, 1
      return float(dmax), 1, float('inf') # Forces intensity to 1.0 (Max Brightness)

    # Case B: Pure L2 dominance (L1 never succeeds OR L2 never fails)
    if a == 0 or d == 0:
      return float(dmax), -1, float('-inf') # Forces intensity to 1.0 (Max Brightness)

    # 2. Calculate Standard Odds Ratio
    odds_ratio = (a * d) / (b * c)
    
    # 3. If perfectly balanced
    if odds_ratio == 1.0:
      return 0.0, 0, 1

    # 4. Use Log-Odds to calculate symmetrical magnitude
    log_or = math.log(odds_ratio)
    
    eff = abs(log_or)     # Scale of brightness (always positive)
    sign = 1 if log_or > 0 else -1  # 1 for L1, -1 for L2
    
    return eff, sign, odds_ratio
  
class AnnotatedTransitionSystem:
  """
  Builds a transition system from log L1 and annotates all states and transitions
  using measurement functions sm and tm evaluated over logs L1 and L2.
  """
  def __init__(self, name="AnnotatedTS"):
    self.ts = TransitionSystem(name)
    
    self.state_annotations = defaultdict(lambda: {"L1": [], "L2": []})
    self.transition_annotations = defaultdict(lambda: {"L1": [], "L2": []})
    
    self.state_comparisons = {}
    self.transition_comparisons = {}

  def export_comparisons_txt(self, filename: str = "ats_comparisons.txt"):
    """
    Export state and transition comparison results to a simple, readable .txt file.

    Format:
    - States section
    - Transitions section
    Each entry shows significance result, p-value, effect size, sign, test used, etc.
    """

    with open(filename, "w", encoding="utf-8") as f:

        f.write("=== Annotated Transition System Comparison Report ===\n")
        f.write(f"Name: {self.ts.name}\n")
        f.write("=====================================================\n\n")

        # --------------------------------------------------
        # STATES
        # --------------------------------------------------
        f.write("=== STATE COMPARISONS ===\n\n")

        for state, info in self.state_comparisons.items():

            f.write(f"State: {str(state) if state else 'START'}\n")
            f.write(f"  Significant difference: {info.get('is_different')}\n")
            f.write(f"  Insufficient data:     {info.get('insufficient_data')}\n")

            # p-value and statistic
            pval = info.get("p_value")
            stat = info.get("statistic")
            if pval is not None:
                f.write(f"  p-value:               {pval:.6g}\n")
            else:
                f.write(f"  p-value:               None\n")

            if stat is not None:
                f.write(f"  Test statistic:        {stat:.6g}\n")
            else:
                f.write(f"  Test statistic:        None\n")

            # Test name
            f.write(f"  Test used:             {info.get('test_used')}\n")

            # Effect size
            eff = info.get("effect_size")
            sign = info.get("effect_sign")
            if eff is not None:
                f.write(f"  Effect size (d):       {eff:.6g}\n")
                f.write(f"  Effect sign:           {sign}\n")

            # Sample sizes
            n_dict = info.get("n", {})
            f.write(f"  Sample sizes:          L1={n_dict.get('A')}, L2={n_dict.get('B')}\n")

            # Normality info
            norm = info.get("normality", {})
            if norm:
                f.write("  Normality:\n")
                f.write(f"    L1: is_normal={norm['A']['is_normal']}, p={norm['A']['p_value']}\n")
                f.write(f"    L2: is_normal={norm['B']['is_normal']}, p={norm['B']['p_value']}\n")

            # Optional error
            if "error" in info:
                f.write(f"  Error:                 {info['error']}\n")

            f.write("\n")

        # --------------------------------------------------
        # TRANSITIONS
        # --------------------------------------------------
        f.write("\n=== TRANSITION COMPARISONS ===\n\n")

        for (source, activity, target), info in self.transition_comparisons.items():

            f.write(f"Transition: {str(source)} --{activity}--> {str(target)}\n")
            f.write(f"  Significant difference: {info.get('is_different')}\n")
            f.write(f"  Insufficient data:     {info.get('insufficient_data')}\n")

            # p-value and statistic
            pval = info.get("p_value")
            stat = info.get("statistic")
            if pval is not None:
                f.write(f"  p-value:               {pval:.6g}\n")
            else:
                f.write("  p-value:               None\n")

            if stat is not None:
                f.write(f"  Test statistic:        {stat:.6g}\n")
            else:
                f.write("  Test statistic:        None\n")

            # Test name
            f.write(f"  Test used:             {info.get('test_used')}\n")

            # Effect size
            eff = info.get("effect_size")
            sign = info.get("effect_sign")
            if eff is not None:
                f.write(f"  Effect size (d):       {eff:.6g}\n")
                f.write(f"  Effect sign:           {sign}\n")

            # Sample sizes
            n_dict = info.get("n", {})
            f.write(f"  Sample sizes:          L1={n_dict.get('L1')}, L2={n_dict.get('L2')}\n")

            # Normality info
            norm = info.get("normality", {})
            if norm:
                f.write("  Normality:\n")
                f.write(f"    L1: is_normal={norm['A']['is_normal']}, p={norm['A']['p_value']}\n")
                f.write(f"    L2: is_normal={norm['B']['is_normal']}, p={norm['B']['p_value']}\n")

            if "error" in info:
                f.write(f"  Error:                 {info['error']}\n")

            f.write("\n")

    print(f"Comparison results exported to {filename}")

  def get_significant_states(self):
      """Return list of states with significant differences."""
      return [s for s, res in self.state_comparisons.items() if res.get("is_different")]

  def get_significant_transitions(self):
      """Return list of (source, activity, target) keys with significant differences."""
      return [k for k, res in self.transition_comparisons.items() if res.get("is_different")]

  def build(
    self, 
    L1, L2, 
    rs, ra, 
    sm, tm, 
    log_id_attr="__log_id__"
  ):
    """
    Builds an annotated transition system for two logs L1 and L2.

    - TS structure is constructed using BOTH logs.
    - Every event receives a synthetic log-origin attribute (log_id_attr),
      so L1 and L2 remain distinguishable even in one unified TS.
    - State and transition annotations keep separate values for L1 and L2.
    """

    activity_key = L1.activity_col
    function_logs = []

    def get_all_traces(log, label):
      """Extract all traces and mark their events with origin label."""
      traces = []
      for case_id in log.get_all_case_ids():
        trace = log.get_trace(case_id)
        # Add distinguishing attribute
        for event in trace:
          event[log_id_attr] = label
        traces.append(trace)
      function_logs.append(
        "Example trace:\n - " +
        "\n - ".join(f"{k}" for k in traces[0])
      )
      return traces

    traces_L1 = get_all_traces(L1, "L1")
    traces_L2 = get_all_traces(L2, "L2")

    self.ts.build_from_two_logs(L1, L2, rs, ra)

    all_states = list(self.ts.states.keys())
    all_transition_keys = [
      (source, activity, target)
      for source, tdict in self.ts.transitions.items()
      for (activity, target) in tdict
    ]

    # Initialize nested annotation dicts
    for s in all_states:
      self.state_annotations[s] = {"L1": [], "L2": []}

    for tr in all_transition_keys:
      self.transition_annotations[tr] = {"L1": [], "L2": []}

    for trace in traces_L1:
      for state in all_states:
        value = sm(
          trace=trace,
          activity_key=activity_key,
          state_repr_func=rs,
          target_state=state
        )
        if value is not None:
          self.state_annotations[state]["L1"].append(value)
    function_logs.append(f'Example trace: {str(traces_L1[0])}')
    function_logs.append(f'sm value: {str(self.state_annotations[all_states[0]]["L1"])}')

    for trace in traces_L2:
      for state in all_states:
        value = sm(
          trace=trace,
          activity_key=activity_key,
          state_repr_func=rs,
          target_state=state
        )
        if value is not None:
          self.state_annotations[state]["L2"].append(value)
      function_logs.append(f'Example state_annotation for state: {str(all_states[0])}')
      function_logs.append(f'sm value: {str(self.state_annotations[all_states[0]]["L2"])}')

    for trace in traces_L1:
      for (source, activity, target) in all_transition_keys:
        value = tm(
          trace=trace,
          activity_key=activity_key,
          state_repr_func=rs,
          transition_repr_func=ra,
          target_transition=activity,
          source_state=source, 
          target_state=target,
        )
        if value is not None:
          self.transition_annotations[(source, activity, target)]["L1"].append(value)

    for trace in traces_L2:
      for (source, activity, target) in all_transition_keys:
        value = tm(
          trace=trace,
          activity_key=activity_key,
          state_repr_func=rs,
          transition_repr_func=ra,
          target_transition=activity,
          source_state=source, 
          target_state=target,
        )
        if value is not None:
          self.transition_annotations[(source, activity, target)]["L2"].append(value)

    print("AnnotatedTransitionSystem successfully built using logs L1 and L2.")
    return function_logs

  def determine_differences(
    self,
    alpha: float = 0.05,
    normality_alpha: float = 0.05,
    normality_test: str = "auto",
    significance_test = SignificanceTest._comparison_oracle,
    effect_size = EffectSizeTest._cliffs_delta,
    min_n: int = 2,
  ):
    """
    Runs the comparison oracle on all states and transitions, comparing
    L1 vs L2 annotation multisets, and stores the results.

    Parameters
    ----------
    alpha : float
        Significance level for the main hypothesis test.
    normality_alpha : float
        Significance level for the normality test.
    normality_test : {'auto','shapiro','dagostino'}
        Which normality test strategy to use in the oracle.
    min_n : int
        Minimum sample size required in each group to attempt a test.

    Returns
    -------
    summary : dict
        Counts of significant differences for states and transitions.
    """
    function_logs = []
    self.state_comparisons = {}
    self.transition_comparisons = {}

    # ---------- States ----------
    for state, ann in self.state_annotations.items():
      A = ann.get("L1", [])
      B = ann.get("L2", [])

      # Guard against insufficient data
      if len(A) < min_n or len(B) < min_n:
        function_logs.append(f"Not sufficient data for state = {state}, len A = {len(A)}, len B = {len(B)}")
        self.state_comparisons[state] = {
          "is_different": False,
          "p_value": None,
          "statistic": None,
          "test_used": None,
          "n": {"A": len(A), "B": len(B)},
          "insufficient_data": True,
        }
        continue

      try:
        if significance_test != SignificanceTest._comparison_oracle:
           is_diff, info = significance_test(A, B, alpha)
        else: 
          is_diff, info = significance_test(
            samples_a=A,
            samples_b=B,
            alpha=alpha,
            normality_alpha=normality_alpha,
            normality_test=normality_test,
          )
        function_logs.append(
          f"Found difference for state = {state} : {is_diff}"
          # f"Found difference for state = {state} : {is_diff}, info: {'\n'.join(f'{k}: {v}' for k, v in info.items())}"
        )
        self.state_comparisons[state] = {
          "is_different": is_diff,
          **info,  # includes p_value, statistic, test_used, n, normality, etc.
          "insufficient_data": False,
        }

        # Compute effect size for states
        if effect_size == EffectSizeTest._odds_ratio:
          effect, sign, ratio = effect_size(A, B)

          self.state_comparisons[state].update({
            "effect_size": effect,
            "effect_sign": sign,
            "odds_ratio": ratio
          })

        else:
          effect, sign = effect_size(A, B)
          self.state_comparisons[state].update({
            "effect_size": effect,
            "effect_sign": sign,
          })
        
      except Exception as e:
        # Fail-safe: record error, no difference declared
        print(f'Found error: {e}')
        function_logs.append(f"Found an error for state = {state}, {e}")
        self.state_comparisons[state] = {
          "is_different": False,
          "p_value": None,
          "statistic": None,
          "test_used": None,
          "n": {"A": len(A), "B": len(B)},
          "insufficient_data": True,
          "error": str(e),
        }

    # ---------- Transitions ----------
    for tr_key, ann in self.transition_annotations.items():
      A = ann.get("L1", [])
      B = ann.get("L2", [])

      if len(A) < min_n or len(B) < min_n:
        function_logs.append(f"Not sufficient data for state = {tr_key}, len A = {len(A)}, len B = {len(B)}")
        
        self.transition_comparisons[tr_key] = {
          "is_different": False,
          "p_value": None,
          "statistic": None,
          "test_used": None,
          "n": {"A": len(A), "B": len(B)},
          "insufficient_data": True,
        }
        continue

      try:
        if significance_test != SignificanceTest._comparison_oracle:
           is_diff, info = significance_test(A, B, alpha)
        else: 
          is_diff, info = significance_test(
            samples_a=A,
            samples_b=B,
            alpha=alpha,
            normality_alpha=normality_alpha,
            normality_test=normality_test,
          )
        function_logs.append(
          f"Found difference for state = {tr_key} : {is_diff}"
          # f"Found difference for state = {tr_key} : {is_diff}, info: {'\n'.join(f'{k}: {v}' for k, v in info.items())}"
        )
        self.transition_comparisons[tr_key] = {
          "is_different": is_diff,
          **info,
          "insufficient_data": False,
        }
        # Compute effect size for transitions
        if effect_size == EffectSizeTest._odds_ratio:
          effect, sign, ratio = effect_size(A, B)
          self.transition_comparisons[tr_key].update({
            "effect_size": effect,
            "effect_sign": sign,
            "odds_ratio": ratio
          })

        else:
          effect, sign = effect_size(A, B)
          self.transition_comparisons[tr_key].update({
            "effect_size": effect,
            "effect_sign": sign,
          })

      except Exception as e:
        print(f'Found error for transition: {e}')
        function_logs.append(f"Found an error for transition = {tr_key}, {e}")
        self.transition_comparisons[tr_key] = {
          "is_different": False,
          "p_value": None,
          "statistic": None,
          "test_used": None,
          "n": {"A": len(A), "B": len(B)},
          "insufficient_data": True,
          "error": str(e),
        }

    # ---------- Summary ----------
    num_sig_states = sum(1 for v in self.state_comparisons.values() if v.get("is_different"))
    num_sig_trans = sum(1 for v in self.transition_comparisons.values() if v.get("is_different"))

    summary = {
      "states_significant": num_sig_states,
      "states_total": len(self.state_comparisons),
      "transitions_significant": num_sig_trans,
      "transitions_total": len(self.transition_comparisons),
      "alpha": alpha,
      "normality_alpha": normality_alpha,
      "normality_test": normality_test,
    }
    return summary, function_logs

  # Optional export functionality:
  def save_annotations(self, filename="annotations.json"):
    data = {
      "states": {str(s): values for s, values in self.state_annotations.items()},
      "transitions": {
        f"{str(s)} -> {a} -> {str(t)}": vals
        for (s, a, t), vals in self.transition_annotations.items()
      }
    }

    with open(filename, "w") as f:
      json.dump(data, f, indent=2)

    print(f"Annotation file saved as {filename}")

  def visualize_with_annotations(self, filename="annotated_transition_system.html"):
    """
    Visualizes the Annotated Transition System using PyVis.
    Shows L1/L2 annotations for states and transitions.
    """

    G = nx.MultiDiGraph()

    def _ones_ratio(values):
      ones = sum(1 for v in values if v == 1)
      total = len(values)
      return f"{ones}/{total}"

    # --------------------------
    # 1. Add States (nodes)
    # --------------------------
    for state, count in self.ts.states.items():

        state_label = str(state) if state else "START"

        # Fetch L1/L2 annotation dict
        ann = self.state_annotations.get(state, {"L1": [], "L2": []})

        # Format annotations
        ann_L1 = _ones_ratio(ann["L1"])
        ann_L2 = _ones_ratio(ann["L2"])
        
        full_label = (
            f"{state_label}\n"
            f"L1: {ann_L1}\n"
            f"L2: {ann_L2}"
        )

        tooltip = (
            f"Frequency: {count} - "
            f"L1 annotation: {ann_L1}"
            f"L2 annotation: {ann_L2}"
        )

        # Color coding
        color = (
            "#2ecc71" if not state else
            ("#e67e22" if state in self.ts.final_states else "#3498db")
        )

        G.add_node(
            str(state),
            label=full_label,
            title=tooltip,
            color=color,
            shape="dot",
        )

    # --------------------------
    # 2. Add Transitions (edges)
    # --------------------------
    for source, targets in self.ts.transitions.items():
        for (activity, target), count in targets.items():

            ann_key = (source, activity, target)
            ann = self.transition_annotations.get(
                ann_key, {"L1": [], "L2": []}
            )

            ann_L1 = _ones_ratio(ann["L1"])
            ann_L2 = _ones_ratio(ann["L2"])
            # ann_L1 = "{" + ", ".join(str(v) for v in ann["L1"]) + "}"
            # ann_L2 = "{" + ", ".join(str(v) for v in ann["L2"]) + "}"

            edge_label = (
                f"{activity} ({count})\n"
                f"L1: {ann_L1}\n"
                f"L2: {ann_L2}"
            )

            tooltip = (
                f"Occurrences: {count}"
                f"L1 annotation: {ann_L1}"
                f"L2 annotation: {ann_L2}"
            )

            G.add_edge(
                str(source),
                str(target),
                label=edge_label,
                title=tooltip,
                width=1 + (count / 5)
            )

    # --------------------------
    # 3. Export to PyVis
    # --------------------------
    net = Network(height="750px", width="100%", directed=True, heading=self.ts.name)
    net.from_nx(G)
    net.show_buttons()

    net.write_html(filename)

    print(f"Annotated Transition System saved as {filename}. Open this file in your browser.")

  def visualize_significance(self, filename: str = "annotated_ts_significance.html"):
    """
    Visualize the Annotated Transition System highlighting statistically significant differences.

    Coloring rule:
      - Green: element shows a significant difference (is_different == True)
      - Black: element does NOT show a significant difference, or insufficient data/not tested

    Requires: `determine_differences()` to have been called to populate
              self.state_comparisons and self.transition_comparisons.
    """

    G = nx.MultiDiGraph()

    # Helper to get comparison info safely
    def _state_cmp_info(state):
      info = self.state_comparisons.get(state, None)
      if not info:
        return False, None, None, {"L1": None, "L2": None}, True
      return (
        bool(info.get("is_different", False)),
        info.get("p_value", None),
        info.get("test_used", None),
        info.get("n", {"L1": None, "L2": None}),
        bool(info.get("insufficient_data", False)),
      )

    def _trans_cmp_info(triple_key):
      info = self.transition_comparisons.get(triple_key, None)
      if not info:
        return False, None, None, {"L1": None, "L2": None}, True
      return (
        bool(info.get("is_different", False)),
        info.get("p_value", None),
        info.get("test_used", None),
        info.get("n", {"L1": None, "L2": None}),
        bool(info.get("insufficient_data", False)),
      )

    # --------------------------
    # 1) Nodes (states)
    # --------------------------
    for state, count in self.ts.states.items():
      # Label: state only (no annotations)
      state_label = str(state) if state else "START"

      is_diff, pval, test_used, n_dict, insufficient = _state_cmp_info(state)

      color = "#2ecc71" if is_diff else "#000000"  # green if significant, else black

      tooltip_lines = [
        f"Frequency: {count}",
        f"Significant: {is_diff}",
      ]
      if pval is not None:
        tooltip_lines.append(f"p-value: {pval:.4g}")
      if test_used:
        tooltip_lines.append(f"Test: {test_used}")
      if isinstance(n_dict, dict) and ("A" in n_dict and "A" in n_dict):
        tooltip_lines.append(f"n(L1): {n_dict.get('A')}, n(L2): {n_dict.get('B')}")
      if insufficient:
        tooltip_lines.append("Insufficient data or not tested")

      G.add_node(
        str(state),
        label=state_label,
        title=" - ".join(tooltip_lines),
        color=color,
        shape="dot",
      )

    # --------------------------
    # 2) Edges (transitions)
    # --------------------------
    for source, targets in self.ts.transitions.items():
      for (activity, target), count in targets.items():
        tr_key = (source, activity, target)
        is_diff, pval, test_used, n_dict, insufficient = _trans_cmp_info(tr_key)

        # Edge label: activity + count only
        edge_label = f"{activity} ({count})"

        color = "#ff0000" if insufficient else "#000000" 

        color = "#2ecc71" if is_diff else color  # green if significant, else black

        tooltip_lines = [
          f"Occurrences: {count}",
          f"Significant: {is_diff}",
        ]
        if pval is not None:
          tooltip_lines.append(f"p-value: {pval:.4g}")
        if test_used:
          tooltip_lines.append(f"Test: {test_used}")
        if isinstance(n_dict, dict) and ("A" in n_dict and "B" in n_dict):
          tooltip_lines.append(f"n(L1): {n_dict.get('A')}, n(L2): {n_dict.get('B')}")
        if insufficient:
          tooltip_lines.append("Insufficient data or not tested")

        G.add_edge(
          str(source),
          str(target),
          label=edge_label,
          title=" - ".join(tooltip_lines),
          color=color,
          width=1 + (count / 5),
        )

    # --------------------------
    # 3) Export to PyVis
    # --------------------------
    net = Network(height="750px", width="100%", directed=True, heading=f"{self.ts.name} – Significance")
    net.from_nx(G)
    net.show_buttons()
    net.write_html(filename)

    print(f"Significance visualization saved as {filename}. Open this file in your browser.")

  def visualize_significance_scaled(
      self, 
      filename="ats_significance_scaled.html", 
      d_max=1.5,
      mode: Literal['tree_mode', 'graph_mode', 'active_mode'] = 'graph_mode'
    ):
    """
    Visualize significance using colors scaled by effect size and direction.
    Labels are plain text. Tooltips (title) use real HTML (bold, line breaks).
    
    Color coding:
      - Green scale  : positive effect (L1 > L2)
      - Purple scale : negative effect (L1 < L2)
      - Black        : not significant / insufficient data / unknown
    Intensity = min(1.0, |d| / d_max)
    """

    # -------------------------------
    # Color mapping by effect + sign
    # -------------------------------
    def color_from_effect(is_diff, eff, sign, dmax):
        if not is_diff or eff is None or sign == 0:
            return "#000000"   # black
        intensity = float(min(1.0, abs(eff) / float(dmax)))
        if sign > 0:
            # positive => green (from rgb(0,80,0) to rgb(0,255,0))
            green = int(80 + intensity * 175)   # 80 → 255
            return f"rgb(0,{green},0)"
        else:
            # negative => purple (from rgb(80,0,80) to rgb(255,0,255))
            rb = int(80 + intensity * 175)      # 80 → 255-ish
            return f"rgb({rb},0,{rb})"

    # -------------------------------
    # Helpers to fetch compare info
    # -------------------------------
    def _state_info(state):
        info = self.state_comparisons.get(state, None)
        if not info:
            return False, None, 0, True, None, None
        return (
            bool(info.get("is_different", False)),
            info.get("effect_size", None),
            info.get("effect_sign", 0),
            bool(info.get("insufficient_data", False)),
            info.get("odds_ratio", None),
            info,
        )

    def _trans_info(key):
        info = self.transition_comparisons.get(key, None)
        if not info:
            return False, None, 0, True, None, None
        return (
            bool(info.get("is_different", False)),
            info.get("effect_size", None),
            info.get("effect_sign", 0),
            bool(info.get("insufficient_data", False)),
            info.get("odds_ratio", None),
            info,
        )

    # -------------------------------
    # Build graph
    # -------------------------------
    G = nx.MultiDiGraph()

    # (1) Nodes (states)
    for state, count in self.ts.states.items():
        label_plain = str(state) if state else "START"
        label_plain = str(state[-1]) if state else "START"

        is_diff, eff, sign, insufficient, odds_ratio, info, = _state_info(state)
        color = color_from_effect(is_diff, eff, sign, d_max)

        # Tooltip (HTML)
        tooltip_parts = [
            f"State:{label_plain}",
            f"Frequency: {count}",
            f"Significant: {is_diff}",
        ]
        if info:
            if info.get("p_value") is not None:
                tooltip_parts.append(f"p-value: {info['p_value']:.4g}")
            if info.get("test_used"):
                tooltip_parts.append(f"Test: {info['test_used']}")
            # Your oracle stores n under keys "A"/"B" — harmonize to L1/L2 for display.
            n_dict = info.get("n", {})
            nL1 = n_dict.get("L1", n_dict.get("A"))
            nL2 = n_dict.get("L2", n_dict.get("B"))
            if nL1 is not None or nL2 is not None:
                tooltip_parts.append(f"n(L1):{nL1}, n(L2): {nL2}")
        if eff is not None:
            direction = "L1 > L2" if sign > 0 else ("L1 < L2" if sign < 0 else "none")
            if odds_ratio is not None:
              tooltip_parts.append(f"Odds Ratio (d): {odds_ratio}")
            else:
              tooltip_parts.append(f"Effect size (d): {eff:.4g}")
            tooltip_parts.append(f"Direction:t {direction}")
        if insufficient:
            tooltip_parts.append("<i>Insufficient data or not tested</i>")
        if info and "error" in info:
            tooltip_parts.append(f"Error: {info['error']}")

        G.add_node(
            str(state),
            label=label_plain,
            title=" - ".join(tooltip_parts),
            color= "lightgray" if label_plain == "START" else color,
            shape="dot",
        )

    # (2) Edges (transitions)
    for source, targets in self.ts.transitions.items():
        for (activity, target), count in targets.items():
            tr_key = (source, activity, target)
            is_diff, eff, sign, insufficient, odds_ratio, info = _trans_info(tr_key)

            label_plain = f"{activity} ({count})"
            color = color_from_effect(is_diff, eff, sign, d_max)

            tooltip_parts = [
                f"Transition: {str(source)} --{activity}--> {str(target)}",
                f"Occurrences: {count}",
                f"Significant: {is_diff}",
            ]
            if info:
                if info.get("p_value") is not None:
                    tooltip_parts.append(f"p-value: {info['p_value']:.4g}")
                if info.get("test_used"):
                    tooltip_parts.append(f"Test: {info['test_used']}")
                n_dict = info.get("n", {})
                nL1 = n_dict.get("L1", n_dict.get("A"))
                nL2 = n_dict.get("L2", n_dict.get("B"))
                if nL1 is not None or nL2 is not None:
                    tooltip_parts.append(f"n(L1): {nL1}, n(L2): {nL2}")
            if eff is not None:
                direction = "L1 > L2" if sign > 0 else ("L1 < L2" if sign < 0 else "none")
                if odds_ratio is not None:
                  tooltip_parts.append(f"Odds Ratio (d): {odds_ratio}")
                else:
                  tooltip_parts.append(f"Effect size (d): {eff:.4g}")
                tooltip_parts.append(f"Direction: {direction}")
            if insufficient:
                tooltip_parts.append("<i>Insufficient data or not tested</i>")
            if info and "error" in info:
                tooltip_parts.append(f"Error: {info['error']}")

            G.add_edge(
                str(source),
                str(target),
                label=label_plain,
                title=" - ".join(tooltip_parts),
                color=color,
                width=1 + (count / 5),
                arrows="to",
            )

    # -------------------------------
    # Create network and options
    # -------------------------------
    net = Network(height="800px", width="100%", directed=True, heading=f"{self.ts.name} - Effect Size Visualization")
    net.from_nx(G)

    options = ''
    if mode == 'tree_mode':
      options = '''{
        "nodes": {
          "borderWidth": null,
          "borderWidthSelected": null,
          "opacity": null,
          "size": null
        },
        "edges": {
          "color": {
            "inherit": true
          },
          "selfReferenceSize": null,
          "selfReference": {
            "angle": 0.7853981633974483
          },
          "smooth": false
        },
        "layout": {
          "hierarchical": {
            "enabled": true,
            "levelSeparation": 235,
            "nodeSpacing": 300,
            "treeSpacing": 500
          }
        },
        "physics": {
          "enabled": false,
          "hierarchicalRepulsion": {
            "centralGravity": 0,
            "nodeDistance": 295,
            "avoidOverlap": null
          },
          "minVelocity": 0.75,
          "solver": "hierarchicalRepulsion"
        }
      }'''
    elif mode == 'graph_mode':
      options = """
        {
          "nodes": {
            "shape": "dot",
            "size": 16,
            "physics": false,
            "font": { "face": "Inter, Arial", "color": "#222222", "size": 14 }
          },
          "edges": {
            "arrows": { "to": { "enabled": true, "scaleFactor": 0.8 } },
            "smooth": { "enabled": true, "type": "dynamic" },
            "font": { "face": "Inter, Arial", "color": "#222222", "size": 12, "strokeWidth": 0 }
          },
          "interaction": { "hover": true, "tooltipDelay": 50 },
          "physics": { 
            "stabilization": true, 
            "barnesHut": { "gravitationalConstant": -4000 }
          }
        }
      """
    elif mode == 'active_mode': 
      net.show_buttons()
    
    if not mode == 'active_mode':
      net.set_options(options)
    # Export
    net.write_html(filename)
    print(f"Effect-size-based significance visualization saved as {filename}.")