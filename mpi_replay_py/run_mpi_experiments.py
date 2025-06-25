#!/usr/bin/env python3
"""
Testing Script for Multi-Application CODES Simulations
Refactored to use flexible job classes supporting variable numbers of jobs.

Claude wrote most of this. I'm very grateful for it :)
"""

import os
import sys
from pathlib import Path
from .utils.config_generator import ConfigGenerator, DFLY_1056
from .utils.jobs import Experiment, JacobiJob, MilcJob, LammpsJob, UrJob
from .utils.runner import TestRunner, Execute

seed = 14829 # Same seed makes the simulation deterministic
scripts_root_dir = os.environ['SCRIPTS_ROOT_DIR']
this_script_dir: Path = Path(__file__).parent
configs_path = os.environ.get('PATH_TO_SCRIPT_DIR', str(this_script_dir)) + '/conf'
executable_path = os.environ['PATH_TO_CODES_BUILD'] + '/src/model-net-mpi-replay'
exp_folder = Path.cwd()

np = 3

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
    'ITERS_TO_COLLECT': '2',
    # Other parameters, not needed right now
    'PACKET_LATENCY_TRACE_PATH': '',
    'BUFFER_SNAPSHOTS': '',

    # Options in other files than dfly-*.conf files
    'CPU_FREQ': '4e9',  # in Hz
}

if __name__ == "__main__":

    # Define simulation modes
    net_config_variations = {
        #'high-fidelity': {
        #    'NETWORK_SURR_ON': '0',
        #    'APP_SURR_ON': '0'
        #},
        #'app-surrogate': {
        #    'NETWORK_SURR_ON': '0',
        #    'APP_SURR_ON': '1'
        #},
        #'app-and-network': {
        #    'NETWORK_SURR_ON': '1',
        #    'APP_SURR_ON': '1',
        #    'NETWORK_MODE': 'nothing'
        #},
        'app-and-network-freezing': {
            'NETWORK_SURR_ON': '1',
            'APP_SURR_ON': '1',
            'NETWORK_MODE': 'freeze'
        },
    }

    # Define test experiments using new Experiment and Job classes
    experiments = [
        Experiment(
            '01-jacobi12-milc10-milc30-ur6',
            [
                JacobiJob(nodes=12, iters=39, layout=(2, 3, 2), msg=50 * 1024, compute_delay=200),
                MilcJob(nodes=10, iters=30, layout=[5, 2], msg=480 * 1024, compute_delay=1500),
                MilcJob(nodes=30, iters=120, layout=[5, 2, 3], msg=10 * 1024, compute_delay=0.025),
                UrJob(nodes=6, period=1200),
            ],
            extraparams=['--extramem=1000000'],
            net_config_variations=net_config_variations,
        ),

        Experiment(
            '02-jacobi12-jacobi24-milc36',
            [
                JacobiJob(nodes=12, iters=110, layout=(2, 3, 2), msg=50 * 1024, compute_delay=200),
                JacobiJob(nodes=24, iters=200, layout=(4, 2, 3), msg=10 * 1024, compute_delay=500),
                MilcJob(nodes=36, iters=120, layout=[2, 2, 3, 3], msg=486 * 1024, compute_delay=0.025),
            ],
            extraparams=['--extramem=1000000'],
            net_config_variations=net_config_variations,
        ),

        Experiment(
            '03-jacobi36-milc24-lammps12',
            [
                JacobiJob(nodes=24, iters=39, layout=(4, 3, 2), msg=50 * 1024, compute_delay=200),
                MilcJob(nodes=36, iters=120, layout=[2, 2, 3, 3], msg=486 * 1024, compute_delay=0.025),
                LammpsJob(nodes=12, time_steps=5, replicas=(3, 2, 2)),
            ],
            extraparams=['--extramem=1000000'],
            net_config_variations=net_config_variations,
        ),

        Experiment(
            '04-jacobi24-milc24-ur6',
            [
                JacobiJob(nodes=24, iters=25, layout=(6, 2, 2), msg=200 * 1024, compute_delay=10),
                MilcJob(nodes=24, iters=150, layout=[3, 2, 2, 2], msg=150 * 1024, compute_delay=500),
                UrJob(nodes=6, period=1200),
            ],
            extraparams=['--extramem=1000000'],
            net_config_variations=net_config_variations,
        ),

        Experiment(
            '05-milc20-jacobi20-ur30',
            [
                MilcJob(nodes=22, iters=100, layout=[2, 11, 1, 1], msg=400 * 1024, compute_delay=50),
                JacobiJob(nodes=20, iters=150, layout=(4, 5, 1), msg=80 * 1024, compute_delay=200),
                UrJob(nodes=30, period=726.609003),
            ],
            extraparams=['--extramem=1000000'],
            net_config_variations=net_config_variations,
        ),

        Experiment(
            '06-jacobi20-milc24-lammps20-ur8',
            [
                JacobiJob(nodes=20, iters=2000, layout=(5, 2, 2), msg=60 * 1024, compute_delay=400),
                MilcJob(nodes=24, iters=500, layout=[3, 2, 2, 2], msg=400 * 1024, compute_delay=300),
                LammpsJob(nodes=20, time_steps=10, replicas=(4, 5, 1)),
                UrJob(nodes=8, period=1000),
            ],
            extraparams=['--extramem=1000000'],
            net_config_variations=net_config_variations,
        ),
    ]

    try:
        # normal execution mode
        execute = Execute(
            binary_path=['mpirun', '-np', str(np), executable_path],
            scripts_dir=scripts_root_dir,
        )
        # debug using tmux-mpi (in parallel)
        #execute = Execute(
        #    binary_path=[os.environ['SCRIPTS_ROOT_DIR'] + '/tmux-mpi', str(np), 'gdb', '--args', executable_path],
        #    scripts_dir=scripts_root_dir,
        #    env_vars={'TMUX_MPI_MODE': 'pane', 'TMUX_MPI_SYNC_PANES': '1'},
        #    redirect_output=False,
        #)
        # debug in sequential
        #execute = Execute(
        #    ['gdb', '--args', executable_path],
        #    scripts_dir=scripts_root_dir,
        #    redirect_output=False,
        #)

        config_generator = ConfigGenerator(configs_path, exp_folder, random_seed=seed, random_allocation=True, network_config=DFLY_1056)
        runner = TestRunner(template_vars, config_generator, execute_with=execute)
        runner.run_tests(experiments)
    except KeyboardInterrupt:
        # This should be handled by the signal handler, but just in case
        print("\nScript interrupted by user", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
