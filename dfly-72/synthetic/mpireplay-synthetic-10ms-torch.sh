#!/usr/bin/bash -x

# np should be one of: 1, 3 or 9
np=3

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

    # Uncomment to run using GDB (comment mpirun line). It runs in single core (np=1)
    #gdb --args "${@:2}"
    mpirun -np $np "${@:2}" > model-result.txt 2> model-result.stderr.txt

    kill $MEM_LOG_PID

    popd
}


# configuration file for hybrid-torch
export PACKET_LATENCY_TRACE_PATH=packet-latency
export PACKET_SIZE=1024
export CHUNK_SIZE=64
export BUFFER_SNAPSHOTS='"100e3", "200e3", "300e3", "400e3", "500e3", "600e3", "700e3", "800e3", "900e3", "1e6", "1.1e6", "1.2e6", "1.3e6", "1.4e6", "1.5e6", "1.6e6", "1.7e6", "1.8e6", "1.9e6", "2e6", "2.1e6", "2.2e6", "2.3e6", "2.4e6", "2.5e6", "2.6e6", "2.7e6", "2.8e6", "2.9e6", "3e6", "3.1e6", "3.2e6", "3.3e6", "3.4e6", "3.5e6", "3.6e6", "3.7e6", "3.8e6", "3.9e6", "4e6", "4.1e6", "4.2e6", "4.3e6", "4.4e6", "4.5e6", "4.6e6", "4.7e6", "4.8e6", "4.9e6", "5e6", "5.1e6", "5.2e6", "5.3e6", "5.4e6", "5.5e6", "5.6e6", "5.7e6", "5.8e6", "5.9e6", "6e6", "6.1e6", "6.2e6", "6.3e6", "6.4e6", "6.5e6", "6.6e6", "6.7e6", "6.8e6", "6.9e6", "7e6", "7.1e6", "7.2e6", "7.3e6", "7.4e6", "7.5e6", "7.6e6", "7.7e6", "7.8e6", "7.9e6", "8e6", "8.1e6", "8.2e6", "8.3e6", "8.4e6", "8.5e6", "8.6e6", "8.7e6", "8.8e6", "8.9e6", "9e6", "9.1e6", "9.2e6", "9.3e6", "9.4e6", "9.5e6", "9.6e6", "9.7e6", "9.8e6", "9.9e6", "10.0e6"'
export IGNORE_UNTIL=2e6
export SWITCH_TIMESTAMPS='"3e6", "8e6"'
export NETWORK_TREATMENT=freeze
export PREDICTOR_TYPE="torch-jit"
export TORCH_JIT_MODEL_PATH="$PATH_TO_SCRIPT_DIR"/ml-model.pt
cat "$CONFIG_DIR"/dragonfly-72-surrogate.template.conf.in | envsubst > terminal-dragonfly-72-torch.conf

# Configuration files to run experiment
cp "$CONFIG_DIR"/job-allocation-72-dragonfly-full.alloc .

# Note: --extramem is only required for simulations with a very short period as they generate many, many, many events (and they keep on accumulating)
extramem=10000

# Note: cons-lookahead is used as the offset to process packet latency events (the event is scheduled back to the sender, thus a smaller offset will force GVT more often; too large of an offset and the predictor will be behind significantly)
simulation_params=(
     "$PATH_TO_CODES_BUILD"/src/model-net-mpi-replay
     --synch=3
     --workload_type=swm-online
     --cons-lookahead=200
     --max-opt-lookahead=600
     --batch=4 --gvt-interval=256
     --alloc_file="$expfolder/job-allocation-72-dragonfly-full.alloc"
     --end=10.0001e6
     --extramem=$extramem
     --lp-io-dir=codes-output
     --perm-thresh=$((500 * 1024))
)


# Taken from https://stackoverflow.com/a/45201229
split_fields() {
   # assumes that $1 is a single, valid word and $2 is the line to split
   # TODO: check assumptions ^
   readarray -td '' $1 < <(awk '{ gsub(/, */,"\0"); print; }' <<<"$2, "); unset $1'[-1]';
   declare -p $1;
}

experiments=(
    "1, uniform, 470"
    #"2, nearest-neighbor, 470"
    #"3, all2all, 34000"
    #"4, stencil, 3000"
    #"5, permutation, 1800"
    #"5, permutation, 3000"
    #"6, bisection, 1400"
)
# Running code!!
for exp in "${experiments[@]}"; do
 split_fields fields "$exp"

 synthetic=${fields[0]}
 syn_name=${fields[1]}
 period=${fields[2]}

 mkdir -p synthetic${synthetic}-${syn_name}-${end}ms
 pushd synthetic${synthetic}-${syn_name}-${end}ms

   work_alloc_file="72-dragonfly-period=${period}.synthetic${synthetic}.conf"
   subexp_folder="$PWD"
   cat > "$work_alloc_file" <<END
72 synthetic${synthetic} 0 ${period}
END

   mpirun_do hybrid-torch "${simulation_params[@]}" \
          --workload_conf_file="$subexp_folder/$work_alloc_file" \
          -- "$expfolder/terminal-dragonfly-72-torch.conf"
 popd
done
