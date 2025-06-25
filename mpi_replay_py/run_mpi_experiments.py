#!/usr/bin/env python3
"""
Testing Script for Multi-Application CODES Simulations
Refactored to use flexible job classes supporting variable numbers of jobs.

Claude wrote most of this. I'm very grateful for it :)
"""

import os
import sys
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
        'high-fidelity': {
            'NETWORK_SURR_ON': '0',
            'APP_SURR_ON': '0'
        },
        'app-surrogate': {
            'NETWORK_SURR_ON': '0',
            'APP_SURR_ON': '1'
        },
        'app-and-network': {
            'NETWORK_SURR_ON': '1',
            'APP_SURR_ON': '1',
            'NETWORK_MODE': 'nothing'
        },
        'app-and-network-freezing': {
            'NETWORK_SURR_ON': '1',
            'APP_SURR_ON': '1',
            'NETWORK_MODE': 'freeze'
        },
    }

    # Define test experiments using new Experiment and Job classes
    experiments_72 = [
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

    # Define scaled-up experiments for 1056-node network
    # Scaled to preserve communication patterns and network stress characteristics
    experiments_1056 = [
        # Experiment 1: Scaled from 58 → 862 nodes (preserves 80.6% utilization)
        Experiment(
            '01-jacobi175-milc144-milc455-ur88',
            [
                JacobiJob(nodes=175, iters=39, layout=(5, 7, 5), msg=50 * 1024, compute_delay=200),
                MilcJob(nodes=144, iters=30, layout=[18, 8], msg=480 * 1024, compute_delay=1500),
                MilcJob(nodes=455, iters=120, layout=[13, 5, 7], msg=10 * 1024, compute_delay=0.025),
                UrJob(nodes=88, period=1200),
            ],
            extraparams=['--extramem=1000000'],
            net_config_variations=net_config_variations,
        ),

        # Experiment 2: Scaled from 72 → 1050 nodes (preserves 1:2:3 ratio)
        Experiment(
            '02-jacobi175-jacobi350-milc525',
            [
                JacobiJob(nodes=175, iters=110, layout=(5, 7, 5), msg=50 * 1024, compute_delay=200),
                JacobiJob(nodes=350, iters=200, layout=(10, 5, 7), msg=10 * 1024, compute_delay=500),
                MilcJob(nodes=525, iters=120, layout=[3, 5, 5, 7], msg=486 * 1024, compute_delay=0.025),
            ],
            extraparams=['--extramem=1000000'],
            net_config_variations=net_config_variations,
        ),

        # Experiment 3: Scaled from 72 → 960 nodes (preserves 2:3:1 ratio)
        Experiment(
            '03-jacobi320-milc480-lammps160',
            [
                JacobiJob(nodes=320, iters=39, layout=(8, 5, 8), msg=50 * 1024, compute_delay=200),
                MilcJob(nodes=480, iters=120, layout=[4, 4, 5, 6], msg=486 * 1024, compute_delay=0.025),
                LammpsJob(nodes=160, time_steps=5, replicas=(5, 8, 4)),
            ],
            extraparams=['--extramem=1000000'],
            net_config_variations=net_config_variations,
        ),

        # Experiment 4: Scaled from 54 → 808 nodes (preserves 75% utilization)
        Experiment(
            '04-jacobi336-milc384-ur88',
            [
                JacobiJob(nodes=336, iters=25, layout=(12, 4, 7), msg=200 * 1024, compute_delay=10),
                MilcJob(nodes=384, iters=150, layout=[4, 4, 4, 6], msg=150 * 1024, compute_delay=500),
                UrJob(nodes=88, period=1200),
            ],
            extraparams=['--extramem=1000000'],
            net_config_variations=net_config_variations,
        ),

        # Experiment 5: Scaled from 72 → 1056 nodes (preserves extreme imbalance patterns)
        Experiment(
            '05-milc323-jacobi289-ur444',
            [
                MilcJob(nodes=323, iters=100, layout=[1, 17, 1, 19], msg=400 * 1024, compute_delay=50),
                JacobiJob(nodes=289, iters=150, layout=(1, 17, 17), msg=80 * 1024, compute_delay=200),
                UrJob(nodes=444, period=726.609003),
            ],
            extraparams=['--extramem=1000000'],
            net_config_variations=net_config_variations,
        ),

        # Experiment 6: Scaled from 72 → 1056 nodes (preserves patterns, stays under limit)
        Experiment(
            '06-jacobi288-milc384-lammps280-ur104',
            [
                JacobiJob(nodes=288, iters=2000, layout=(12, 4, 6), msg=60 * 1024, compute_delay=400),
                MilcJob(nodes=384, iters=500, layout=[4, 4, 4, 6], msg=400 * 1024, compute_delay=300),
                LammpsJob(nodes=280, time_steps=10, replicas=(8, 5, 7)),
                UrJob(nodes=104, period=1000),
            ],
            extraparams=['--extramem=1000000'],
            net_config_variations=net_config_variations,
        ),
    ]

    # Define scaled-up experiments for 8448-node network
    # Scaled to preserve communication patterns while maximizing network utilization
    experiments_8448 = [
        # Experiment 1: Scaled from 58 → 6800 nodes (preserves 80.6% utilization)
        Experiment(
            '01-jacobi1400-milc1200-milc3500-ur700',
            [
                JacobiJob(nodes=1400, iters=39, layout=(10, 10, 14), msg=50 * 1024, compute_delay=200),
                MilcJob(nodes=1200, iters=30, layout=[5, 5, 6, 8], msg=480 * 1024, compute_delay=1500),
                MilcJob(nodes=3500, iters=120, layout=[10, 14, 25], msg=10 * 1024, compute_delay=0.025),
                UrJob(nodes=700, period=1200),
            ],
            extraparams=['--extramem=1000000'],
            net_config_variations=net_config_variations,
        ),

        # Experiment 2: Scaled from 72 → 8400 nodes (preserves 1:2:3 ratio)
        Experiment(
            '02-jacobi1400-jacobi2800-milc4200',
            [
                JacobiJob(nodes=1400, iters=110, layout=(10, 10, 14), msg=50 * 1024, compute_delay=200),
                JacobiJob(nodes=2800, iters=200, layout=(10, 14, 20), msg=10 * 1024, compute_delay=500),
                MilcJob(nodes=4200, iters=120, layout=[6, 7, 10, 10], msg=486 * 1024, compute_delay=0.025),
            ],
            extraparams=['--extramem=1000000'],
            net_config_variations=net_config_variations,
        ),

        # Experiment 3: Scaled from 72 → 8400 nodes (preserves 2:3:1 ratio)
        Experiment(
            '03-jacobi2800-milc4200-lammps1400',
            [
                JacobiJob(nodes=2800, iters=39, layout=(10, 14, 20), msg=50 * 1024, compute_delay=200),
                MilcJob(nodes=4200, iters=120, layout=[6, 7, 10, 10], msg=486 * 1024, compute_delay=0.025),
                LammpsJob(nodes=1400, time_steps=5, replicas=(10, 10, 14)),
            ],
            extraparams=['--extramem=1000000'],
            net_config_variations=net_config_variations,
        ),

        # Experiment 4: Scaled from 54 → 6300 nodes (preserves 75% utilization)
        Experiment(
            '04-jacobi2800-milc2800-ur700',
            [
                JacobiJob(nodes=2800, iters=25, layout=(10, 14, 20), msg=200 * 1024, compute_delay=10),
                MilcJob(nodes=2800, iters=150, layout=[5, 7, 8, 10], msg=150 * 1024, compute_delay=500),
                UrJob(nodes=700, period=1200),
            ],
            extraparams=['--extramem=1000000'],
            net_config_variations=net_config_variations,
        ),

        # Experiment 5: Scaled from 72 → 8448 nodes (preserves extreme imbalance patterns)
        Experiment(
            '05-milc2500-jacobi2300-ur3648',
            [
                MilcJob(nodes=2500, iters=100, layout=[1, 1, 25, 100], msg=400 * 1024, compute_delay=50),
                JacobiJob(nodes=2300, iters=150, layout=(1, 23, 100), msg=80 * 1024, compute_delay=200),
                UrJob(nodes=3648, period=726.609003),
            ],
            extraparams=['--extramem=1000000'],
            net_config_variations=net_config_variations,
        ),

        # Experiment 6: Scaled from 72 → 8448 nodes (preserves patterns, challenges network)
        Experiment(
            '06-jacobi2300-milc2800-lammps2300-ur1048',
            [
                JacobiJob(nodes=2300, iters=2000, layout=(10, 10, 23), msg=60 * 1024, compute_delay=400),
                MilcJob(nodes=2800, iters=500, layout=[5, 7, 8, 10], msg=400 * 1024, compute_delay=300),
                LammpsJob(nodes=2300, time_steps=10, replicas=(23, 10, 10)),
                UrJob(nodes=1048, period=1000),
            ],
            extraparams=['--extramem=1000000'],
            net_config_variations=net_config_variations,
        ),
    ]

    try:
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
        #    env_vars={'TMUX_MPI_MODE': 'pane', 'TMUX_MPI_SYNC_PANES': '1'},
        #    redirect_output=False,
        #)
        # debug in sequential
        #execute = Execute(
        #    ['gdb', '--args', executable_path],
        #    scripts_dir=scripts_root_dir,
        #    redirect_output=False,
        #)

        # Run 72-node experiments
        print("=" * 60)
        print("RUNNING 72-NODE NETWORK EXPERIMENTS")
        print("=" * 60)
        config_generator_72 = ConfigGenerator(configs_path, exp_folder, random_seed=seed, random_allocation=True, network_config=DFLY_72)
        runner_72 = TestRunner(template_vars, config_generator_72, execute_with=execute)
        runner_72.run_tests(experiments_72)

        # Run 1056-node experiments
        print("=" * 60)
        print("RUNNING 1056-NODE NETWORK EXPERIMENTS")
        print("=" * 60)
        config_generator_1056 = ConfigGenerator(configs_path, exp_folder, random_seed=seed, random_allocation=True, network_config=DFLY_1056)
        runner_1056 = TestRunner(template_vars, config_generator_1056, execute_with=execute)
        runner_1056.run_tests(experiments_1056)

        # Run 8448-node experiments
        print("=" * 60)
        print("RUNNING 8448-NODE NETWORK EXPERIMENTS")
        print("=" * 60)
        config_generator_8448 = ConfigGenerator(configs_path, exp_folder, random_seed=seed, random_allocation=True, network_config=DFLY_8448)
        runner_8448 = TestRunner(template_vars, config_generator_8448, execute_with=execute)
        runner_8448.run_tests(experiments_8448)
    except KeyboardInterrupt:
        # This should be handled by the signal handler, but just in case
        print("\nScript interrupted by user", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
