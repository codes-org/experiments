#!/usr/bin/bash

np=1

expfolder="$PWD"
export CONFIGS_PATH="$PATH_TO_SCRIPT_DIR/conf"

# Backing up and copying milc json!
tmpdir="$(TMPDIR="$PWD" mktemp -d)"
mv "$PATH_TO_SWM_INSTALL/share/milc_skeleton.json" "$tmpdir/milc_skeleton.json"
cp "$CONFIGS_PATH/milc_skeleton.json" "$PATH_TO_SWM_INSTALL/share/milc_skeleton.json"
mv "$PATH_TO_UNION_INSTALL/share/conceptual.json" "$tmpdir/conceptual.json"
cp "$CONFIGS_PATH/conceptual.json" "$PATH_TO_UNION_INSTALL/share/conceptual.json"

# Copying configuration files to keep as documentation
cp "$CONFIGS_PATH/milc_skeleton.json" "$expfolder"
cp "$CONFIGS_PATH/conceptual.json" "$expfolder"
cp "$CONFIGS_PATH/jacobi_MILC.workload.conf" "$expfolder"
cp "$CONFIGS_PATH/rand_node0-1d-72-jacobi_MILC.alloc.conf" "$expfolder"

# CODES config file
export PATH_TO_CONNECTIONS="$CONFIGS_PATH"
envsubst < "$CONFIGS_PATH/dfdally-72-par.conf.in" > "$expfolder/dfdally-72-par.conf"

# running simulation
lookahead=200

mpirun_do() {
    command=("${@}")
    bash "$SCRIPTS_ROOT_DIR"/memory-log.sh > memory-log.txt &
    MEM_LOG_PID=$!

    # Running simulation and saving results to file
    mpirun -np $np --bind-to none "${command[@]}" > model-result.txt 2> model-result.stderr.txt
    # Uncomment to run using GDB (comment mpirun line). It runs in single core (np=1)
    #gdb --args "${command[@]}"
    # Multiple gdb instances, needs tmux and dtach, and python libs: libtmux and psutil
    #TMUX_MPI_MODE=pane TMUX_MPI_SYNC_PANES=1 "$SCRIPTS_ROOT_DIR"/tmux-mpi $np gdb --args "${command[@]}"

    kill $MEM_LOG_PID
}

mpirun_do "$PATH_TO_CODES_BUILD"/src/model-net-mpi-replay \
  --synch=6 \
  --cons-lookahead=$lookahead --max-opt-lookahead=$lookahead \
  --batch=4 --gvt-interval=256 \
  --workload_type=conc-online \
  --lp-io-dir=lp-io-dir \
  --workload_conf_file="$expfolder"/jacobi_MILC.workload.conf \
  --alloc_file="$expfolder"/rand_node0-1d-72-jacobi_MILC.alloc.conf \
  -- \
  "$expfolder/dfdally-72-par.conf"

# Setting milc json back
mv "$tmpdir/milc_skeleton.json" "$PATH_TO_SWM_INSTALL/share/milc_skeleton.json"
mv "$tmpdir/conceptual.json" "$PATH_TO_UNION_INSTALL/share/conceptual.json"
rmdir "$tmpdir"
