import re

REMOVED_STUDY_IDS=[

]

# Make sure that the LOG_PATTERN has the same number of named groups as the SOFTWARE_DATA_COLUMNS list, and that they are in the same order.
SOFTWARE_DATA_COLUMNS = [
  'Start Datetime',
  'FunctionCall',
  'Description'
]

# Change these if you want different names for the attributes (event log columns) 
# if you change Description OR/AND Start Datetime also change it in the SOFTWARE_DATA_COLUMNS
DESCRIPTIVE_COLUMN_NAME = 'Description'
RESOURCE_COLUMN_NAME = 'Username'
ACTIVITY_COLUMN_NAME = 'FLA Activity'
START_DATETIME_COLUMN_NAME = 'Start Datetime'
CASEID_COLUMN_NAME = 'Study ID'
END_DATETIME_COLUMN_NAME = 'End Datetime'
DATASET_NAME_COLUMN_NAME = 'Dataset Name'

# ##########################################################################################################################################################
# GENERALIZATION PATTERNS - used to generalize very detialed information so the events can be used for identification of activities
# ##########################################################################################################################################################
group_patterns = {

}

generalization_patterns= {

}

SUBSTRING_PATTERNS = {**group_patterns, **generalization_patterns}

# ##########################################################################################################################################################
# ATTRIBUTE PATTERNS - used to identify attributes in the execution data
# ##########################################################################################################################################################
LOG_PATTERN = re.compile(
  r'^(?P<datetime>\d{2} \w{3} \d{4}\s+\d{2}:\d{2}:\d{2},\d{3})\s+'
  r'(?P<func_call>.+?)\s*:\s*'
  r'(?P<message>.+)$'
)

STUDYID_PATTERN = re.compile(r'\bID\s*(\d+)\b')

RESOURCE_PATTERN = re.compile(r'C:\\Users\\([^\\]+)')

DATETIME_PATTERN = "%d %b %Y %H:%M:%S,%f"

# ##########################################################################################################################################################
# EVENT ABSTRACTION - the information the event abstraction is based on
# ##########################################################################################################################################################
START_ACTIVITIES = ["1_Startup"]
END_ACTIVITIES = ["7_Shutdown", "0B_Abrupt_End_Error"]

AUTOSEGMENTATION_SEQUENCE = {
  "": "Scheduling_Segmentation_1"
}

SHUTDOWN_START_SEQUENCE = {
  "session end requested-BREAK-beginning shutdown": "Shutdown_1"
}

ACTIVITIES_MAP_EVENTS = {
  r"Launching with callback": "1_Startup",
  r"^(?:Scheduling task|Enqueuing task|Running task|Task completed):\s+Registering SPECT\b.*$" : "3_Automatic_rigid",
  r"Scheduling_Segmentation_\d+_(start|end)": "5_Autosegmentation",
  r"Scheduling task: Quantifying region.*$": "6_Perform_segmentation",
  r"Shutdown_1_end|Shutdown complete": "7_Shutdown",
  r"Beginning shutdown|Final shutdown": "0A_Error", 
}

LOADING_MESSAGES = {
  'START_MESSAGES':  [''],
  'END_MESSAGES': [""]
}

LINKING_REGISTRATION_MESSAGES = [""]

REGISTRATION_MESSAGES = {
  'START_MESSAGES': [""],
  'END_MESSAGES': [""]
}

