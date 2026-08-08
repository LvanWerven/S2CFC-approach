  #!/bin/bash

  # Exit immediately if any command fails
  set -e

  NAME=$1
  INCLUDE_MANUAL_REGISTRATION=$2

  if [ "$INCLUDE_MANUAL_REGISTRATION" = "true" ]; then
    IMR_FLAG="--IMR"
  else
    IMR_FLAG=""
  fi

  echo "Name of the run we are going to use: $NAME"
  echo "Include the manual registration activity: $INCLUDE_MANUAL_REGISTRATION"

  echo "-------- START RUNNING --------"

  PARENT_FOLDER=""
  RAW_PRE_DATA_FOLDER=""
  RAW_TRIAL_DATA_FOLDER=""


  # ------------------------------------------------------------
  # 1. Run the S2CF_module for the pre-AI-addition data
  # ------------------------------------------------------------
  py -m pre_processing.S2CF_module \
    --lfp=$RAW_PRE_DATA_FOLDER \
    --dsn="pre-AI-addition" \
    --wfp="$PARENT_FOLDER\\pre_$NAME" \
    --fn "" \
    --rtp="" \
    $IMR_FLAG \
    --log

  echo "Finished running S2CF_module for pre-AI-addition data. Now running for trial-AI-addition data."

  # ------------------------------------------------------------
  # 2. Run the S2CF_module for the trial-AI-addition data
  # ------------------------------------------------------------
  py -m pre_processing.S2CF_module \
    --lfp=$RAW_TRIAL_DATA_FOLDER \
    --dsn="trial-AI-addition" \
    --wfp="$PARENT_FOLDER\\trial_$NAME" \
    $IMR_FLAG \
    --pID "" \
    --log

  echo "Finished running S2CF_module for trial-AI-addition data."
  
  # ------------------------------------------------------------
  # 3. Run the comparison_module for the preprocessed data
  # ------------------------------------------------------------
  py -m comparison_analysis.comparison_module \
    --elfp "$PARENT_FOLDER\\trial_$NAME" "$PARENT_FOLDER\\pre_$NAME" \
    --ofp "$PARENT_FOLDER\\comparison_results_$NAME" \
    --dsn "trial-AI-addition" "pre-AI-addition" \
    --name="$NAME"
