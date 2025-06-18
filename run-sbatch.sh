#!/usr/bin/bash

# Execution example:
# ./run-sbatch.sh kronos-data/terminal-dragonfly-72-pings=40.sh

echo "CHANGE paths in run-sbatch to your own!" && exit 1 # REMOVE THIS LINE AFTER UPDATING PARAMS BELOW

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &> /dev/null && pwd)
#HOME=/gpfs/u/home/SPNR/SPNRcrzc
BASE_EXPERIMENTS_PATH="$HOME/scratch/codes-experiments/kronos"
PATH_TO_CODES_BUILD="$HOME/barn/kronos/codes-only/codes/build"
#PATH_TO_CODES_SRC="$HOME/barn/kronos/codes-only/codes/"

# Checking for validity of input
if [ $# -lt 1 ]; then
  echo "This script requires at least ONE argument: the script to run," \
    "followed by any other arguments to pass on the script"
  exit 1
fi

# Finding out paths and
SBATCH_SCRIPT="$(realpath "$1")"
EXPERIMENTS_NAME=$(realpath --relative-to="$SCRIPT_DIR" "$SBATCH_SCRIPT")
EXPERIMENTS_NAME=${EXPERIMENTS_NAME%.*}
EXPERIMENTS_PATH="$BASE_EXPERIMENTS_PATH/$EXPERIMENTS_NAME"
PATH_TO_SCRIPT_DIR="$(realpath "$(dirname "$SBATCH_SCRIPT")")"

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

# We pass all parameters to the script
sbatch -D "$expfolder" "$SBATCH_SCRIPT" "$@"
#pushd "$expfolder"
#bash -x "$SBATCH_SCRIPT" "$@"
#popd
