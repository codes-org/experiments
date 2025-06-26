#!/usr/bin/bash

np=3
synch=3

expfolder="$PWD"
export CONFIGS_PATH="$PATH_TO_SCRIPT_DIR/conf"

# Function to backup and restore original config files
backup_configs() {
    tmpdir="$(TMPDIR="$PWD" mktemp -d)"
    mv "$PATH_TO_SWM_INSTALL/share/milc_skeleton.json" "$tmpdir/milc_skeleton.json"
    mv "$PATH_TO_UNION_INSTALL/share/conceptual.json" "$tmpdir/conceptual.json"
}

restore_configs() {
    mv "$tmpdir/milc_skeleton.json" "$PATH_TO_SWM_INSTALL/share/milc_skeleton.json"
    mv "$tmpdir/conceptual.json" "$PATH_TO_UNION_INSTALL/share/conceptual.json"
    rmdir "$tmpdir"
}

# Common CODES config settings
setup_common_config() {
    export PATH_TO_CONNECTIONS="$CONFIGS_PATH"
    export NETWORK_SURR_ON=1
    #export NETWORK_MODE=freeze
    export NETWORK_MODE=nothing
    export APP_SURR_ON=1
    #export APP_DIRECTOR_MODE=every-n-gvt
    export APP_DIRECTOR_MODE=every-n-nanoseconds
    export EVERY_N_GVTS=1500
    export EVERY_NSECS=1.0e6
    export ITERS_TO_COLLECT=5
}


# Modified mpirun_do function that creates experiment subdirectories
lookahead=200

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

# Function to generate non-overlapping random node allocations
generate_non_overlapping_allocations() {
    local jacobi_nodes=$1 milc_nodes=$2
    local total_needed=$((jacobi_nodes + milc_nodes))
    
    if [ $total_needed -gt 72 ]; then
        echo "Error: Total nodes needed ($total_needed) exceeds available nodes (72)" >&2
        exit 1
    fi
    
    # Generate shuffled list of required nodes
    local all_nodes=($(shuf -i 0-71 -n $total_needed))
    
    # Split into jacobi and milc allocations
    local jacobi_alloc=""
    local milc_alloc=""
    
    for i in $(seq 0 $((jacobi_nodes-1))); do
        jacobi_alloc="$jacobi_alloc ${all_nodes[$i]}"
    done
    
    for i in $(seq $jacobi_nodes $((total_needed-1))); do
        milc_alloc="$milc_alloc ${all_nodes[$i]}"
    done
    
    # Remove leading spaces and export
    export JACOBI_ALLOCATION=$(echo $jacobi_alloc | sed 's/^ *//')
    export MILC_ALLOCATION=$(echo $milc_alloc | sed 's/^ *//')
}

# Function to generate base configuration for an experiment
generate_base_config() {
    # Parse named parameters
    local exp_name jacobi_iters jacobi_msg jacobi_layout jacobi_nodes
    local milc_iters milc_msg milc_nodes milc_layout
    
    for arg in "$@"; do
        case $arg in
            exp_name=*) exp_name="${arg#*=}" ;;
            jacobi_iters=*) jacobi_iters="${arg#*=}" ;;
            jacobi_msg=*) jacobi_msg="${arg#*=}" ;;
            jacobi_layout=*) jacobi_layout="${arg#*=}" ;;
            jacobi_nodes=*) jacobi_nodes="${arg#*=}" ;;
            milc_iters=*) milc_iters="${arg#*=}" ;;
            milc_msg=*) milc_msg="${arg#*=}" ;;
            milc_nodes=*) milc_nodes="${arg#*=}" ;;
            milc_layout=*) milc_layout="${arg#*=}" ;;
        esac
    done
    
    echo "Generating base configuration for: $exp_name"
    echo "  Jacobi: $jacobi_iters iters, ${jacobi_msg}B msgs, $jacobi_nodes nodes, layout=[$jacobi_layout]"
    echo "  MILC: $milc_iters iters, ${milc_msg}B msgs, $milc_nodes nodes, layout=[$milc_layout]"
    
    # Parse jacobi_layout (e.g., "4,3,3" -> separate variables for processor grid)
    IFS=',' read -ra layout <<< "$jacobi_layout"
    local proc_x=${layout[0]} proc_y=${layout[1]} proc_z=${layout[2]}
    
    # Calculate grid dimensions based on processor layout
    export JACOBI_GRID_X=${proc_x}00
    export JACOBI_GRID_Y=${proc_y}00
    export JACOBI_GRID_Z=${proc_z}00
    export JACOBI_BLOCK=100
    
    # Generate non-overlapping node allocations
    generate_non_overlapping_allocations $jacobi_nodes $milc_nodes
    
    # Set experiment-specific variables
    export JACOBI_ITERS=$jacobi_iters
    export JACOBI_MSG_SIZE=$jacobi_msg
    export MILC_ITERS=$milc_iters
    export MILC_MSG_SIZE=$milc_msg
    export JACOBI_NODES=$jacobi_nodes
    export MILC_NODES=$milc_nodes
    export MILC_LAYOUT=$milc_layout
    
    # Store experiment name for simulation modes
    export CURRENT_EXP_NAME="$exp_name"
    
    # Generate base configuration files (everything except dfdally-72-par.conf)
    local exp_config_dir="$expfolder/$exp_name"
    mkdir -p "$exp_config_dir"
    
    envsubst < "$CONFIGS_PATH/jacobi_MILC.workload.conf" > "$exp_config_dir/jacobi_MILC.workload.conf"
    envsubst < "$CONFIGS_PATH/milc_skeleton.json" > "$exp_config_dir/milc_skeleton.json"
    envsubst < "$CONFIGS_PATH/conceptual.json" > "$exp_config_dir/conceptual.json"
    envsubst < "$CONFIGS_PATH/rand_node0-1d-72-jacobi_MILC.alloc.conf" > "$exp_config_dir/rand_node0-1d-72-jacobi_MILC.alloc.conf"
    
    # Copy configs to install locations
    cp "$exp_config_dir/milc_skeleton.json" "$PATH_TO_SWM_INSTALL/share/milc_skeleton.json"
    cp "$exp_config_dir/conceptual.json" "$PATH_TO_UNION_INSTALL/share/conceptual.json"
}

# Function to run a specific simulation mode
run_simulation_mode() {
    local mode_name="$1"
    shift  # Remove mode_name from arguments
    
    echo "  Running simulation mode: $mode_name"
    
    # Set mode-specific environment variables
    for var_setting in "$@"; do
        export "$var_setting"
    done
    
    # Generate mode-specific network configuration
    local exp_config_dir="$expfolder/$CURRENT_EXP_NAME"
    envsubst < "$CONFIGS_PATH/dfdally-72-par.conf.in" > "$exp_config_dir/dfdally-72-par-$mode_name.conf"
    
    # Run the simulation in mode-specific subdirectory
    mpirun_do "$CURRENT_EXP_NAME/$mode_name" "$PATH_TO_CODES_BUILD"/src/model-net-mpi-replay \
      --synch=$synch \
      --cons-lookahead=$lookahead --max-opt-lookahead=$lookahead \
      --batch=4 --gvt-interval=256 \
      --cons-lookahead=200 \
      --max-opt-lookahead=600 \
      --workload_type=conc-online \
      --lp-io-dir=lp-io-dir \
      --workload_conf_file="$exp_config_dir/jacobi_MILC.workload.conf" \
      --alloc_file="$exp_config_dir/rand_node0-1d-72-jacobi_MILC.alloc.conf" \
      -- "$exp_config_dir/dfdally-72-par-$mode_name.conf"
}

# Function to run an experiment with all simulation modes
run_experiment_with_modes() {
    # Generate base configuration once
    generate_base_config "$@"
    
    # Run all 4 simulation modes
    echo "Running all simulation modes for: $CURRENT_EXP_NAME"
    
    run_simulation_mode "high-fidelity" \
        NETWORK_SURR_ON=0 \
        APP_SURR_ON=0
    
    run_simulation_mode "app-surrogate" \
        NETWORK_SURR_ON=0 \
        APP_SURR_ON=1
    
    run_simulation_mode "app-net-not-freeze" \
        NETWORK_SURR_ON=1 \
        APP_SURR_ON=1 \
        NETWORK_MODE=nothing
    
    run_simulation_mode "app-net-freeze" \
        NETWORK_SURR_ON=1 \
        APP_SURR_ON=1 \
        NETWORK_MODE=freeze
    
    echo "Completed all modes for: $CURRENT_EXP_NAME"
    echo "----------------------------------------"
}

# Backup original config files
backup_configs
setup_common_config

# Run all experiments with all simulation modes
# Mixed timing: some experiments have Jacobi > MILC, others have MILC > Jacobi for variability

run_experiment_with_modes \
    exp_name="1-balanced-workload" \
    jacobi_iters=50 jacobi_msg=75000 jacobi_layout="4,3,3" jacobi_nodes=36 \
    milc_iters=100 milc_msg=400000 milc_nodes=36 milc_layout="2,2,3,3"

run_experiment_with_modes \
    exp_name="2-communication-heavy" \
    jacobi_iters=120 jacobi_msg=150000 jacobi_layout="6,3,2" jacobi_nodes=36 \
    milc_iters=80 milc_msg=300000 milc_nodes=36 milc_layout="3,3,2,2"

run_experiment_with_modes \
    exp_name="3-iteration-heavy" \
    jacobi_iters=500 jacobi_msg=60000 jacobi_layout="4,3,3" jacobi_nodes=36 \
    milc_iters=120 milc_msg=200000 milc_nodes=36 milc_layout="2,2,3,3"

run_experiment_with_modes \
    exp_name="4-asymmetric-load" \
    jacobi_iters=30 jacobi_msg=30000 jacobi_layout="3,2,2" jacobi_nodes=12 \
    milc_iters=180 milc_msg=600000 milc_nodes=60 milc_layout="5,4,3,1"

run_experiment_with_modes \
    exp_name="5-high-concurrency" \
    jacobi_iters=400 jacobi_msg=80000 jacobi_layout="6,6,1" jacobi_nodes=36 \
    milc_iters=80 milc_msg=250000 milc_nodes=36 milc_layout="6,6,1,1"

# Restore original config files
restore_configs
