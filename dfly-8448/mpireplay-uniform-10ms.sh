#!/usr/bin/bash -x
#SBATCH --nodes=1
#SBATCH --gres=gpu:6,nvme
#SBATCH --partition=el8
#SBATCH --ntasks-per-node=33
#SBATCH -t 240

# np should be one of: 1, 3, 11, or 33
np=33

# checking and loading mpi if in system
command -v module &> /dev/null && module load spectrum-mpi/10.4 xl_r

# Checking if NVMe space is available
NVME_DIR=/mnt/nvme/uid_${SLURM_JOB_UID}/job_${SLURM_JOB_ID}
[ ! -d "$NVME_DIR" ] && NVME_DIR=.

# The first parameter is the name of the subdirectory to create
mpirun_do() {
    mkdir -p "$1"
    pushd "$1"

    bash "$SCRIPTS_ROOT_DIR"/memory-log.sh > memory-log.txt &
    MEM_LOG_PID=$!

    mpirun "${@:2}" > model-result.txt 2> model-result.stderr.txt

    kill $MEM_LOG_PID

    # Moving data from NVMe to disk (current folder)
    [ "$NVME_DIR" != . ] && [ -n "$(ls -A "$NVME_DIR" 2>/dev/null)" ] && mv "$NVME_DIR/"* .

    popd
}


# CONFIGURATION
# exported env variables are to be used by `envsubst` below
expfolder="$PWD"
export CONFIG_DIR="$PATH_TO_SCRIPT_DIR/conf"

# configuration details common for all experiments
export PACKET_LATENCY_TRACE_PATH=$NVME_DIR/packet-latency
export PACKET_SIZE=4096
export CHUNK_SIZE=64
export BUFFER_SNAPSHOTS='"100e3", "200e3", "300e3", "400e3", "500e3", "600e3", "700e3", "800e3", "900e3", "1e6", "1.1e6", "1.2e6", "1.3e6", "1.4e6", "1.5e6", "1.6e6", "1.7e6", "1.8e6", "1.9e6", "2e6", "2.1e6", "2.2e6", "2.3e6", "2.4e6", "2.5e6", "2.6e6", "2.7e6", "2.8e6", "2.9e6", "3e6", "3.1e6", "3.2e6", "3.3e6", "3.4e6", "3.5e6", "3.6e6", "3.7e6", "3.8e6", "3.9e6", "4e6", "4.1e6", "4.2e6", "4.3e6", "4.4e6", "4.5e6", "4.6e6", "4.7e6", "4.8e6", "4.9e6", "5e6", "5.1e6", "5.2e6", "5.3e6", "5.4e6", "5.5e6", "5.6e6", "5.7e6", "5.8e6", "5.9e6", "6e6", "6.1e6", "6.2e6", "6.3e6", "6.4e6", "6.5e6", "6.6e6", "6.7e6", "6.8e6", "6.9e6", "7e6", "7.1e6", "7.2e6", "7.3e6", "7.4e6", "7.5e6", "7.6e6", "7.7e6", "7.8e6", "7.9e6", "8e6", "8.1e6", "8.2e6", "8.3e6", "8.4e6", "8.5e6", "8.6e6", "8.7e6", "8.8e6", "8.9e6", "9e6", "9.1e6", "9.2e6", "9.3e6", "9.4e6", "9.5e6", "9.6e6", "9.7e6", "9.8e6", "9.9e6", "9.990e6"'
envsubst < "$CONFIG_DIR"/dfdally-8k-par.conf.in > "$expfolder/dfdally-8k.conf"

# configuration file for hybrid-lite and hybrid codes
export IGNORE_UNTIL=1e6
export NETWORK_TREATMENT=freeze
export PREDICTOR_TYPE=average
export SWITCH_TIMESTAMPS='"3e6", "8e6"'
envsubst < "$CONFIG_DIR"/dfdally-8k-par-surrogate.conf.in > "$expfolder/dfdally-8k-surrogate-avg-hybrid.conf"

# configuration file for hybrid-lite
export NETWORK_TREATMENT=nothing
envsubst < "$CONFIG_DIR"/dfdally-8k-par-surrogate.conf.in > "$expfolder/dfdally-8k-surrogate-avg-lite.conf"

# Configuration files to run uniform experiment
cp "$CONFIG_DIR"/job-allocation-8k-dragonfly-full.alloc .

period=205
work_alloc_file="8448-uniform-period=${period}-8k.synthetic.conf"
cat > "$work_alloc_file" <<END
8448 synthetic1 0 ${period}
END

lookahead=200
# Note: --extramem is only required for simulations with a very short period as they generate many, many, many events (and they keep on accumulating)
extramem=1000000

# Note: cons-lookahead is used as the offset to process packet latency events (the event is scheduled back to the sender, thus a smaller offset will force GVT more often; too large of an offset and the predictor will be behind significantly)
simulation_params=(
     "$PATH_TO_CODES_BUILD"/src/model-net-mpi-replay
     --synch=3 
     --workload_type=swm-online --workload_conf_file="$expfolder/$work_alloc_file"
     --cons-lookahead=200
     --max-opt-lookahead=600
     --batch=4 --gvt-interval=256
     --alloc_file="$expfolder/job-allocation-8k-dragonfly-full.alloc"
     --end=10.0001e6
     --extramem=$extramem
     --lp-io-dir=codes-output
)

# Running experiments
mpirun_do high-fidelity -np $np "${simulation_params[@]}" \
         -- "$expfolder/dfdally-8k.conf"

mpirun_do hybrid -np $np "${simulation_params[@]}" \
         -- "$expfolder/dfdally-8k-surrogate-avg-hybrid.conf"

#mpirun_do hybrid-lite -np $np "${simulation_params[@]}" \
#         -- "$expfolder/dfdally-8k-surrogate-avg-lite.conf"
