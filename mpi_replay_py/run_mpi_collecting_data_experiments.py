#!/usr/bin/env python3
"""
Testing Script for Multi-Application CODES Simulations
Refactored to use flexible job classes supporting variable numbers of jobs.

Claude wrote a substancial amount of code in this folder. I'm very grateful for it :). I cleaned up the mess.
"""

import os
import sys
import json
from pathlib import Path
from .utils.config_generator import ConfigGenerator, DFLY_72, DFLY_1056, DFLY_8448
from .utils.jobs import Experiment, JacobiJob, MilcJob, LammpsJob, UrJob
from .utils.runner import TestRunner, Execute

seed = 14829 # Same seed makes the simulation deterministic
scripts_root_dir = os.environ['SCRIPTS_ROOT_DIR']
this_script_dir: Path = Path(__file__).parent
configs_path = os.environ.get('PATH_TO_SCRIPT_DIR', str(this_script_dir)) + '/conf'
executable_path = os.environ['PATH_TO_CODES_BUILD'] + '/src/model-net-mpi-replay'
exp_folder = Path.cwd()

# This will affect all variables to replace in the templates
template_vars = {
    # Network configuration
    'PACKET_SIZE': '4096',
    'CHUNK_SIZE': '4096',
    # Surrogate configuration
    'NETWORK_SURR_ON': '0',
    'NETWORK_MODE': 'nothing',
    'APP_SURR_ON': '0',
    'APP_DIRECTOR_MODE': 'every-n-nanoseconds', # options: 'every-n-gvt' (non-deterministic switch) and 'every-n-nanoseconds' (deterministic switch)
    'EVERY_N_GVTS': '1500',
    'EVERY_NSECS': '1.0e6',
    'ITERS_TO_COLLECT': '3',
    # Other parameters, not needed right now
    'BUFFER_SNAPSHOTS': '',
    'PACKET_LATENCY_TRACE_PATH': 'packet_latency',

    # Options in other files than dfly-*.conf files
    'CPU_FREQ': '4e9',  # in Hz
}

def export_experiment_metadata(experiments_list: list[Experiment], output_path: Path):
    """Export experiment job types to JSON file"""
    metadata = {}

    for exp in experiments_list:
        job_types: list[str] = [job.__class__.__name__.replace("Job", "") for job in exp.jobs]
        metadata[exp.name] = job_types

    metadata_file = os.path.join(output_path, "experiment_metadata.json")
    with open(metadata_file, 'w') as f:
        json.dump(metadata, f, indent=2)

    return metadata_file

if __name__ == "__main__":
    # Define test experiments using new Experiment and Job classes
    experiments_72 = [
        Experiment(
            'dfly-72-01-jacobi12-milc10-milc30-ur6',
            [
                JacobiJob(nodes=12, iters=39, layout=(2, 3, 2), msg=50 * 1024, compute_delay=200),
                MilcJob(nodes=10, iters=30, layout=[5, 2], msg=480 * 1024, compute_delay=1500),
                MilcJob(nodes=30, iters=120, layout=[5, 2, 3], msg=10 * 1024, compute_delay=0.025),
                UrJob(nodes=6, period=1200),
            ],
            extraparams=['--extramem=1000000'],
        ),

        Experiment(
            'dfly-72-02-jacobi12-jacobi24-milc36',
            [
                JacobiJob(nodes=12, iters=110, layout=(2, 3, 2), msg=50 * 1024, compute_delay=200),
                JacobiJob(nodes=24, iters=200, layout=(4, 2, 3), msg=10 * 1024, compute_delay=500),
                MilcJob(nodes=36, iters=120, layout=[2, 2, 3, 3], msg=486 * 1024, compute_delay=0.025),
            ],
            extraparams=['--extramem=1000000'],
        ),

        Experiment(
            'dfly-72-03-jacobi36-milc24-lammps12',
            [
                JacobiJob(nodes=24, iters=39, layout=(4, 3, 2), msg=50 * 1024, compute_delay=200),
                MilcJob(nodes=36, iters=120, layout=[2, 2, 3, 3], msg=486 * 1024, compute_delay=0.025),
                LammpsJob(nodes=12, time_steps=5, replicas=(3, 2, 2)),
            ],
            extraparams=['--extramem=1000000'],
        ),

        Experiment(
            'dfly-72-04-jacobi24-milc24-ur6',
            [
                JacobiJob(nodes=24, iters=25, layout=(6, 2, 2), msg=200 * 1024, compute_delay=10),
                MilcJob(nodes=24, iters=150, layout=[3, 2, 2, 2], msg=150 * 1024, compute_delay=500),
                UrJob(nodes=6, period=1200),
            ],
            extraparams=['--extramem=1000000'],
        ),

        Experiment(
            'dfly-72-05-milc20-jacobi20-ur30',
            [
                MilcJob(nodes=22, iters=100, layout=[2, 11, 1, 1], msg=400 * 1024, compute_delay=50),
                JacobiJob(nodes=20, iters=150, layout=(4, 5, 1), msg=80 * 1024, compute_delay=200),
                UrJob(nodes=30, period=726.609003),
            ],
            extraparams=['--extramem=1000000'],
        ),

        Experiment(
            'dfly-72-06-jacobi20-milc24-lammps20-ur8',
            [
                JacobiJob(nodes=20, iters=2000, layout=(5, 2, 2), msg=60 * 1024, compute_delay=400),
                MilcJob(nodes=24, iters=500, layout=[3, 2, 2, 2], msg=400 * 1024, compute_delay=300),
                LammpsJob(nodes=20, time_steps=10, replicas=(4, 5, 1)),
                UrJob(nodes=8, period=1000),
            ],
            extraparams=['--extramem=1000000'],
        ),
    ]

    try:
        # ideal np = 9 for 72 nodes, and np = 33 for 1056 and 8448 nodes
        np = 3

        # normal execution mode
        execute = Execute(
            binary_path=['mpirun', '-np', str(np), executable_path],
            scripts_dir=scripts_root_dir,
        )
        # debug using tmux-mpi (in parallel)
        #execute = Execute(
        #    binary_path=[os.environ['SCRIPTS_ROOT_DIR'] + '/tmux-mpi', str(np), 'gdb', '--args', executable_path],
        #    scripts_dir=scripts_root_dir,
        #    env_vars={'TMUX_MPI_MODE': 'pane', 'TMUX_MPI_SYNC_PANES': '1', 'TMUX_MPI_MPIRUN': 'mpirun --map-by hwthread:oversubscribe'},
        #    redirect_output=False,
        #)
        # debug in sequential
        #execute = Execute(
        #    ['gdb', '--args', executable_path],
        #    scripts_dir=scripts_root_dir,
        #    redirect_output=False,
        #)

        # Run 72-node experiments
        print("Running Network Experiments")
        config_generator_72 = ConfigGenerator(configs_path, exp_folder, random_seed=seed, random_allocation=True, network_config=DFLY_72)
        runner_72 = TestRunner(template_vars, config_generator_72, execute_with=execute)
        runner_72.run_tests(experiments_72)
    except KeyboardInterrupt:
        # This should be handled by the signal handler, but just in case
        print("\nScript interrupted by user", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
