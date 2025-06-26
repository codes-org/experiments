#!/usr/bin/bash

np=3

expfolder="$PWD"
export CONFIGS_PATH="$PATH_TO_SCRIPT_DIR/conf"

# Backing up and copying milc json!
tmpdir="$(TMPDIR="$PWD" mktemp -d)"
mv "$PATH_TO_SWM_INSTALL/share/"{milc_skeleton,lammps_workload}.json "$tmpdir/"
cp "$CONFIGS_PATH/milc_skeleton.json" "$PATH_TO_SWM_INSTALL/share/milc_skeleton.json"
cp "$CONFIGS_PATH/lammps_workload.json" "$PATH_TO_SWM_INSTALL/share/lammps_workload.json"

# Copying configuration files to keep as documentation
mkdir "$expfolder/conf"
cp "$CONFIGS_PATH"/{milc_skeleton,lammps_workload}.json "$expfolder/conf"
cp "$CONFIGS_PATH/"milc36+lammps32+ur4.{conf,period,load} "$expfolder/conf"

# CODES config file
export PATH_TO_CONNECTIONS="$CONFIGS_PATH"
envsubst < "$CONFIGS_PATH/kb.dfdally-72-par.long.conf.in" > "$expfolder/conf/kb.dfdally-72-par.long.conf"

lookahead=200

# The first parameter is the name of the subdirectory to create
mpirun_do() {
    bash "$SCRIPTS_ROOT_DIR"/memory-log.sh > memory-log.txt &
    MEM_LOG_PID=$!

    # Running simulation and saving results to file
    mpirun -np $np "$@" > model-result.txt 2> model-result.stderr.txt
    # Uncomment to run using GDB (comment mpirun line). It runs in single core (np=1)
    #gdb --args "$@"
    # Multiple gdb instances, needs tmux and dtach, and python libs: libtmux and psutil
    #TMUX_MPI_MODE=pane TMUX_MPI_SYNC_PANES=1 "$SCRIPTS_ROOT_DIR"/tmux-mpi $np gdb --args "$@"

    kill $MEM_LOG_PID
}

simulation_params=(
    "$PATH_TO_CODES_BUILD"/src/model-net-mpi-replay
    --synch=3
    --workload_type=conc-online
    # --extramem=50000000
    --cons-lookahead=$lookahead
    --max-opt-lookahead=$lookahead
    --disable_compute=0
    --payload_sz=4096
    --workload_conf_file="$expfolder"/conf/milc36+lammps32+ur4.load
    --alloc_file="$expfolder"/conf/milc36+lammps32+ur4.conf
    #--workload_period_file="$expfolder"/conf/milc36+lammps32+ur4.period
    #--lp-io-dir="$expfolder"/riodir
    --end=73e9
    -- "$expfolder"/conf/kb.dfdally-72-par.long.conf
)

# running simulation
mpirun_do "${simulation_params[@]}"

# Setting milc json back
mv "$tmpdir/milc_skeleton.json" "$PATH_TO_SWM_INSTALL/share/milc_skeleton.json"
mv "$tmpdir/lammps_workload.json" "$PATH_TO_SWM_INSTALL/share/lammps_workload.json"
rmdir "$tmpdir"
