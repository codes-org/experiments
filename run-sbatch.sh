#!/usr/bin/bash

# Execution example:
# ./run-sbatch.sh path-to-script/script.sh

echo "CHANGE paths in run-sbatch to your own!" && exit 1 # REMOVE THIS LINE AFTER UPDATING PARAMS BELOW

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &> /dev/null && pwd)
#HOME=/gpfs/u/home/SPNR/SPNRcrzc
BASE_EXPERIMENTS_PATH="$HOME/scratch/codes-experiments/kronos"
PATH_TO_CODES_BUILD="$HOME/barn/kronos/codes-only/codes/build"
PATH_TO_UNION_INSTALL="$BASE_DIR/Union/install"
PATH_TO_SWM_INSTALL="$BASE_DIR/swm-workloads/swm/build/bin"

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
if [[ "$SBATCH_SCRIPT" == *.py ]]; then
  export PYTHONPATH="$(realpath "$PATH_TO_SCRIPT_DIR/../"):$PYTHONPATH"
  PACKAGE_NAME="$(basename "$PATH_TO_SCRIPT_DIR")"
  SCRIPT_NAME="$(basename "$SBATCH_SCRIPT" .py)"
  sbatch -D "$expfolder" python3 -m $PACKAGE_NAME.$SCRIPT_NAME "${@:2}"
else
  sbatch -D "$expfolder" "$SBATCH_SCRIPT" "$@"
fi
#pushd "$expfolder"
#bash -x "$SBATCH_SCRIPT" "$@"
#popd
