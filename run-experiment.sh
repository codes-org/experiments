#!/usr/bin/bash

# Execution example:
# ./run-experiment.sh 1024-nearest-neighbor/mpireplay-nearest-neighbor-10ms.sh

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &> /dev/null && pwd)
BASE_DIR="$(realpath "$SCRIPT_DIR"/..)"
PATH_TO_CODES_BUILD="$BASE_DIR/codes/build"
PATH_TO_UNION_INSTALL="$BASE_DIR/Union/install"
PATH_TO_SWM_INSTALL="$BASE_DIR/swm-workloads/swm/build/bin"

# Checking for validity of input
if [ $# -lt 1 ]; then
  echo "This script requires at least ONE argument: the script to run," \
    "followed by any other arguments to pass on the script"
  exit 1
fi

# Finding out paths and
EXPERIMENT_SCRIPT="$(realpath "$1")"
EXPERIMENTS_PATH="$(dirname -- "$EXPERIMENT_SCRIPT")/results"
PATH_TO_SCRIPT_DIR="$(realpath "$(dirname "$EXPERIMENT_SCRIPT")")"

# Creating new sub-folder to hold current experiment
if [ -d "$EXPERIMENTS_PATH" ]; then
  # Find latest experiment number
  last="$(ls -1 "$EXPERIMENTS_PATH" | grep exp- | sort | tail -n 1)"
  last_index=${last/exp-}
  last_index=${last_index%/}
  # new folder name
  expfolder="$EXPERIMENTS_PATH/exp-$( printf %03d $(( 10#$last_index + 1 )) )"
else
  expfolder="$EXPERIMENTS_PATH/exp-001"
fi

mkdir -p "$expfolder" || exit 1

# Variables to be accessed by script to be run!!
export SCRIPTS_ROOT_DIR="$SCRIPT_DIR"
export PATH_TO_CODES_BUILD
export PATH_TO_SCRIPT_DIR
export PATH_TO_UNION_INSTALL
export PATH_TO_SWM_INSTALL

# We pass all parameters to the script
pushd "$expfolder"
if [[ "$EXPERIMENT_SCRIPT" == *.py ]]; then
  python3 "$EXPERIMENT_SCRIPT" "$@"
else
  bash -x "$EXPERIMENT_SCRIPT" "$@"
fi
popd
