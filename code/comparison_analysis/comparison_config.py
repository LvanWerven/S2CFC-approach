from comparison_analysis.utils.process_comparator_types import ActivityMapper, AnnotatedTransitionSystem, EffectSizeTest, EventLogStore, SignificanceTest, StateMapper, StateMeasurementMapper, TransitionMeasurementMapper, TransitionSystem

# #############################################################################
# PERFORMANCE - TRACE DURATION
# #############################################################################
TIME_UNITS = 'hours'

# #############################################################################
# BEHAVIOUS - CONTROL-FLOW
# #############################################################################
PROCESS_COMPARATOR_CONFIGS = [
  {
    "name": "sequence_control-flow-occurrence",
    "state_mapper": StateMapper.sequence_abstraction,
    "activity_mapper": ActivityMapper.get_activity,
    "state_measurement_mapper": StateMeasurementMapper.is_state_reached,
    "transition_measurement_mapper": TransitionMeasurementMapper.transition_occurrence,
    'significance_test': SignificanceTest._fishers_exact,
    'effect_size_test': EffectSizeTest._odds_ratio,
  },
  {
    "name": "sequence_control-flow-performance",
    "state_mapper": StateMapper.sequence_abstraction,
    "activity_mapper": ActivityMapper.get_activity,
    "state_measurement_mapper": StateMeasurementMapper.state_sojourn_time,
    "transition_measurement_mapper": TransitionMeasurementMapper.transition_delay,
    'significance_test': SignificanceTest._comparison_oracle,
    'effect_size_test': EffectSizeTest._cliffs_delta,
  }
]

# #############################################################################
# BEHAVIOUS - VARIANT
# #############################################################################
MIMINUM_NUMBER_CASES_THRESHOLD = 2