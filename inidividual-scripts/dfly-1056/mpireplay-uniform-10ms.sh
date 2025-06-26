#!/usr/bin/bash -x
#SBATCH --nodes=1
#SBATCH --gres=gpu:4,nvme
#SBATCH --partition=el8-rpi
#SBATCH -t 60

# np should be one of: 1, 3, 11, or 33
np=3

# checking and loading mpi if in system
command -v module &> /dev/null && module load spectrum-mpi/10.4 xl_r

# CONFIGURATION
# exported env variables are to be used by `envsubst` below
expfolder="$PWD"
export CONFIG_DIR="$PATH_TO_SCRIPT_DIR/conf"

# The first parameter is the name of the subdirectory to create
mpirun_do() {
    mkdir -p "$1"
    pushd "$1"

    bash "$SCRIPTS_ROOT_DIR"/memory-log.sh > memory-log.txt &
    MEM_LOG_PID=$!

    # Running simulation and saving results to file
    mpirun -np $np "${@:2}" > model-result.txt 2> model-result.stderr.txt
    # Uncomment to run using GDB (comment mpirun line). It runs in single core (np=1)
    #gdb --args "${@:2}"
    # Multiple gdb instances, needs tmux and dtach, and python libs: libtmux and psutil
    #TMUX_MPI_MODE=pane TMUX_MPI_SYNC_PANES=1 "$SCRIPTS_ROOT_DIR"/tmux-mpi $np gdb --args "${@:2}"

    kill $MEM_LOG_PID

    popd
}

modetorun=high-fidelity
if [ $# -ge 2 ]; then
  echo "Fourth argument passed was: $2"
  modetorun="$2"
fi

# configuration details common for all experiments
export PACKET_LATENCY_TRACE_PATH=packet-latency
export PACKET_SIZE=4096
export CHUNK_SIZE=64
export BUFFER_SNAPSHOTS='"100e3", "200e3", "300e3", "400e3", "500e3", "600e3", "700e3", "800e3", "900e3", "1e6", "1.1e6", "1.2e6", "1.3e6", "1.4e6", "1.5e6", "1.6e6", "1.7e6", "1.8e6", "1.9e6", "2e6", "2.1e6", "2.2e6", "2.3e6", "2.4e6", "2.5e6", "2.6e6", "2.7e6", "2.8e6", "2.9e6", "3e6", "3.1e6", "3.2e6", "3.3e6", "3.4e6", "3.5e6", "3.6e6", "3.7e6", "3.8e6", "3.9e6", "4e6", "4.1e6", "4.2e6", "4.3e6", "4.4e6", "4.5e6", "4.6e6", "4.7e6", "4.8e6", "4.9e6", "5e6", "5.1e6", "5.2e6", "5.3e6", "5.4e6", "5.5e6", "5.6e6", "5.7e6", "5.8e6", "5.9e6", "6e6", "6.1e6", "6.2e6", "6.3e6", "6.4e6", "6.5e6", "6.6e6", "6.7e6", "6.8e6", "6.9e6", "7e6", "7.1e6", "7.2e6", "7.3e6", "7.4e6", "7.5e6", "7.6e6", "7.7e6", "7.8e6", "7.9e6", "8e6", "8.1e6", "8.2e6", "8.3e6", "8.4e6", "8.5e6", "8.6e6", "8.7e6", "8.8e6", "8.9e6", "9e6", "9.1e6", "9.2e6", "9.3e6", "9.4e6", "9.5e6", "9.6e6", "9.7e6", "9.8e6", "9.9e6", "9.990e6"'
cat "$CONFIG_DIR"/dally-1056-par.conf.in | envsubst > dfdally-1056.conf

# configuration file for hybrid-lite and hybrid codes
export IGNORE_UNTIL=1e6
export NETWORK_TREATMENT=freeze
export PREDICTOR_TYPE=average
export SWITCH_TIMESTAMPS='"3e6", "8e6"'
envsubst < "$CONFIG_DIR"/dally-1056-par.surrogate.conf.in > dfdally-1056-hybrid.conf

# configuration file for hybrid-lite
export NETWORK_TREATMENT=nothing
cat "$CONFIG_DIR"/dally-1056-par.surrogate.conf.in | envsubst > dfdally-1056-hybrid-lite.conf

# Configuration files to run uniform experiment
cp "$CONFIG_DIR"/job-allocation-1056-dragonfly-full.alloc .

period=210
work_alloc_file="1056-uniform-period=${period}.synthetic.conf"
cat > "$work_alloc_file" <<END
1056 synthetic1 0 ${period}
END

# Note: --extramem is only required for simulations with a very short period as they generate many, many, many events (and they keep on accumulating)
extramem=100000

# Note: cons-lookahead is used as the offset to process packet latency events (the event is scheduled back to the sender, thus a smaller offset will force GVT more often; too large of an offset and the predictor will be behind significantly)
simulation_params=(
     "$PATH_TO_CODES_BUILD"/src/model-net-mpi-replay
     --synch=3 
     --workload_type=swm-online --workload_conf_file="$expfolder/$work_alloc_file"
     --cons-lookahead=200
     --max-opt-lookahead=600
     --batch=4 --gvt-interval=256
     --alloc_file="$expfolder/job-allocation-1056-dragonfly-full.alloc"
     #--end=10.0001e6
     --end=0.1001e6
     --extramem=$extramem
     --lp-io-dir=codes-output
)

mpirun_do high-fidelity "${simulation_params[@]}" \
         -- "$expfolder/dfdally-1056.conf"

#mpirun_do hybrid "${simulation_params[@]}" \
#         --avl-size=21 \
#         -- "$expfolder/dfdally-1056-hybrid.conf"
#
#mpirun_do hybrid-lite "${simulation_params[@]}" \
#         -- "$expfolder/dfdally-1056-hybrid-lite.conf"
