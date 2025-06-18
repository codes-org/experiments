#!/usr/bin/bash

np=3
synch=3

expfolder="$PWD"
export CONFIGS_PATH="$PATH_TO_SCRIPT_DIR/conf"

# Copying configuration files to keep as documentation
#export MILC_ITERS=120000
#export JACOBI_ITERS=39000
export MILC_ITERS=12
export JACOBI_ITERS=12

cp "$CONFIGS_PATH/jacobi_MILC.workload.conf" "$expfolder"
cp "$CONFIGS_PATH/rand_node0-1d-72-jacobi_MILC.alloc.conf" "$expfolder"
envsubst < "$CONFIGS_PATH/milc_skeleton.json" > "$expfolder/milc_skeleton.json"
envsubst < "$CONFIGS_PATH/conceptual.json" > "$expfolder/conceptual.json"

# Backing up and copying milc json!
tmpdir="$(TMPDIR="$PWD" mktemp -d)"
mv "$PATH_TO_SWM_INSTALL/share/milc_skeleton.json" "$tmpdir/milc_skeleton.json"
cp "$expfolder/milc_skeleton.json" "$PATH_TO_SWM_INSTALL/share/milc_skeleton.json"
mv "$PATH_TO_UNION_INSTALL/share/conceptual.json" "$tmpdir/conceptual.json"
cp "$expfolder/conceptual.json" "$PATH_TO_UNION_INSTALL/share/conceptual.json"

# CODES config file
export PATH_TO_CONNECTIONS="$CONFIGS_PATH"
export NETWORK_SURR_ON=1
#export NETWORK_MODE=freeze
export NETWORK_MODE=nothing

export APP_SURR_ON=1
#export APP_DIRECTOR_MODE=every-n-gvt
export APP_DIRECTOR_MODE=every-n-nanoseconds
export EVERY_N_GVTS=1500
export EVERY_NSECS=1.0e6
export PATH_TO_CONNECTIONS="$CONFIGS_PATH"
export ITERS_TO_COLLECT=1

envsubst < "$CONFIGS_PATH/dfdally-72-par.conf.in" > "$expfolder/dfdally-72-par.conf"

#export APP_SURR_ON=0
#envsubst < "$CONFIGS_PATH/dfdally-72-par-hf.conf.in" > "$expfolder/dfdally-72-par.conf"

# running simulation
lookahead=200

mpirun_do() {
    # TODO: add folder here!! and run mpirun_do for highfidelity and surrogate modes, and then many other options
    bash "$SCRIPTS_ROOT_DIR"/memory-log.sh > memory-log.txt &
    MEM_LOG_PID=$!

    # Running simulation and saving results to file
    mpirun -np $np "${@}" > model-result.txt 2> model-result.stderr.txt
    # Uncomment to run using GDB (comment mpirun line). It runs in single core (np=1)
    #gdb --args "${@}"
    # Multiple gdb instances, needs tmux and dtach, and python libs: libtmux and psutil
    #TMUX_MPI_MODE=pane TMUX_MPI_SYNC_PANES=1 "$SCRIPTS_ROOT_DIR"/tmux-mpi $np gdb --args "${@}"

    kill $MEM_LOG_PID
}

#gdb --args "$PATH_TO_CODES_BUILD"/src/model-net-mpi-replay \
mpirun_do "$PATH_TO_CODES_BUILD"/src/model-net-mpi-replay \
  --synch=$synch \
  --cons-lookahead=$lookahead --max-opt-lookahead=$lookahead \
  --batch=4 --gvt-interval=256 \
  --cons-lookahead=200 \
  --max-opt-lookahead=600 \
  --workload_type=conc-online \
  --lp-io-dir=lp-io-dir \
  --workload_conf_file="$expfolder"/jacobi_MILC.workload.conf \
  --alloc_file="$expfolder"/rand_node0-1d-72-jacobi_MILC.alloc.conf \
  -- "$expfolder/dfdally-72-par.conf"

# Setting milc json back
mv "$tmpdir/milc_skeleton.json" "$PATH_TO_SWM_INSTALL/share/milc_skeleton.json"
mv "$tmpdir/conceptual.json" "$PATH_TO_UNION_INSTALL/share/conceptual.json"
rmdir "$tmpdir"
