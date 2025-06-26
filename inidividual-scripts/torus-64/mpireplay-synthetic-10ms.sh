#!/usr/bin/bash -x

np=1

# CONFIGURATION
# exported env variables are to be used by `envsubst` below
expfolder="$PWD"
export CONFIG_DIR="$PATH_TO_SCRIPT_DIR/conf"

# The first parameter is the name of the subdirectory to create
mpirun_do() {
    # mkdir -p "$1"
    # pushd "$1"

    bash "$SCRIPTS_ROOT_DIR"/memory-log.sh > memory-log.txt &
    MEM_LOG_PID=$!

    # Running simulation and saving results to file
    mpirun -np $np "${@:2}" > model-result.txt 2> model-result.stderr.txt
    # Uncomment to run using GDB (comment mpirun line). It runs in single core (np=1)
    #gdb --args "${@:2}"
    # Multiple gdb instances, needs tmux and dtach, and python libs: libtmux and psutil
    #TMUX_MPI_MODE=pane TMUX_MPI_SYNC_PANES=1 "$SCRIPTS_ROOT_DIR"/tmux-mpi $np gdb --args "${@:2}"

    kill $MEM_LOG_PID

    # popd
}


# configuration details
export PACKET_SIZE=4096
export CHUNK_SIZE=128
cat "$CONFIG_DIR"/torus.template.conf.in | envsubst > torus.conf
cp "$CONFIG_DIR"/job-allocation-64-full.alloc .

# Note: --extramem is only required for simulations with a very short period as they generate many, many, many events (and they keep on accumulating)
extramem=10000

# Note: cons-lookahead is used as the offset to process packet latency events (the event is scheduled back to the sender, thus a smaller offset will force GVT more often; too large of an offset and the predictor will be behind significantly)
simulation_params=(
     "$PATH_TO_CODES_BUILD"/src/model-net-mpi-replay
     --synch=3
     --workload_type=swm-online
     --cons-lookahead=200
     #--max-opt-lookahead=600
     --batch=4 --gvt-interval=256
     --alloc_file="$expfolder/job-allocation-64-full.alloc"
     --end=10.0001e6
     --extramem=$extramem
     --lp-io-dir=codes-output
     # prem-thresh used only by permutation workload; no other synthetic pattern uses this parameter (uniform random, nearest-neighbor, etc)
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

   work_alloc_file="torus-period=${period}.synthetic${synthetic}.conf"
   subexp_folder="$PWD"
   cat > "$work_alloc_file" <<END
64 synthetic${synthetic} 0 ${period}
END

   mpirun_do high-fidelity "${simulation_params[@]}" \
          --workload_conf_file="$subexp_folder/$work_alloc_file" \
          -- "$expfolder/torus.conf"
   
 popd
done
