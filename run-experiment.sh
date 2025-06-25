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
mkdir -p "$EXPERIMENTS_PATH" || exit 1

# Find highest experiment number
max_num=0
if [ -d "$EXPERIMENTS_PATH" ]; then
  max_num=$(find "$EXPERIMENTS_PATH" -maxdepth 1 -type d -name "exp-[0-9][0-9][0-9]*" -printf "%f\n" 2>/dev/null | \
    sed -n 's/^exp-\([0-9]\{3\}\).*/\1/p' | \
    awk 'BEGIN{max=0} {num=int($0); if(num>max) max=num} END{print max}')
  max_num=${max_num:-0}
fi

# Create new experiment folder
next_num=$((max_num + 1))
expfolder="$EXPERIMENTS_PATH/exp-$(printf "%03d" $next_num)"

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
  export PYTHONPATH="$(realpath "$PATH_TO_SCRIPT_DIR/../"):$PYTHONPATH"
  PACKAGE_NAME="$(basename "$PATH_TO_SCRIPT_DIR")"
  SCRIPT_NAME="$(basename "$EXPERIMENT_SCRIPT" .py)"
  python3 -m $PACKAGE_NAME.$SCRIPT_NAME "${@:2}"
else
  bash -x "$EXPERIMENT_SCRIPT" "$@"
fi
popd
