#!/usr/bin/env python3
"""
Testing Script for Multi-Application CODES Simulations
Refactored to use flexible job classes supporting variable numbers of jobs.

Claude wrote most of this. I'm very grateful for it :)
"""

import os
import sys
from pathlib import Path
from .config_generator import ConfigGenerator
from .jobs import Experiment, JacobiJob, MilcJob, LammpsJob, UrJob
from .runner import TestRunner

script_dir: Path = Path(__file__).parent
configs_path: str = os.environ.get('PATH_TO_SCRIPT_DIR', str(script_dir)) + '/conf'
exp_folder: Path = Path.cwd()

# Single consolidated environment variables dictionary
env_vars = {
    # System variables
    'CPU_FREQ': str(4e9),  # in Hz
    'SCRIPTS_ROOT_DIR': os.environ['SCRIPTS_ROOT_DIR'],
    'PATH_TO_CODES_BUILD': os.environ['PATH_TO_CODES_BUILD'],

    # Template variables
    'PATH_TO_CONNECTIONS': configs_path,
    'NETWORK_SURR_ON': '0',
    'NETWORK_MODE': 'nothing',
    'APP_SURR_ON': '0',
    'APP_DIRECTOR_MODE': 'every-n-gvt',
    'EVERY_N_GVTS': '1500',
    'EVERY_NSECS': '1.0e6',
    'ITERS_TO_COLLECT': '5'
}

if __name__ == "__main__":

    # Define simulation modes
    modes = {
        'high-fidelity': {
            'NETWORK_SURR_ON': '0',
            'APP_SURR_ON': '0'
        },
        #'app-surrogate': {
        #    'NETWORK_SURR_ON': '0',
        #    'APP_SURR_ON': '1'
        #},
        #'app-and-network': {
        #    'NETWORK_SURR_ON': '1',
        #    'APP_SURR_ON': '1',
        #    'NETWORK_MODE': 'nothing'
        #},
        #'app-and-network-freezing': {
        #    'NETWORK_SURR_ON': '1',
        #    'APP_SURR_ON': '1',
        #    'NETWORK_MODE': 'freeze'
        #},
    }

    common_config: dict[str, float | str | list[str]] = {
        'extraparams': ['--extramem=100000'],
    }

    # Define test experiments using new Experiment and Job classes
    experiments = [
        Experiment(
            'jacobi12-milc10-milc36',
            [
                JacobiJob(nodes=12, iters=39, layout=(2, 3, 2), msg=50 * 1024, compute_delay=200),
                MilcJob(nodes=10, iters=20, layout=[5, 2], msg=480 * 1024, compute_delay=0.025),
                MilcJob(nodes=36, iters=120, layout=[2, 2, 3, 3], msg=10 * 1024, compute_delay=0.025),
            ],
            extraparams=['--extramem=1000000'],
            modes=modes,
        ),

        Experiment(
            'milc36-jacobi36',
            [
                MilcJob(nodes=36, iters=120, layout=[2, 2, 3, 3], msg=486 * 1024, compute_delay=0.025),
                JacobiJob(nodes=36, iters=10, layout=(4, 3, 3), msg=10 * 1024, compute_delay=500),
            ],
            extraparams=['--extramem=1000000'],
            modes=modes,
        ),

        Experiment(
            'jacobi12-jacobi24-milc36',
            [
                JacobiJob(nodes=12, iters=39, layout=(2, 3, 2), msg=50 * 1024, compute_delay=200),
                JacobiJob(nodes=24, iters=10, layout=(4, 2, 3), msg=10 * 1024, compute_delay=500),
                MilcJob(nodes=36, iters=120, layout=[2, 2, 3, 3], msg=486 * 1024, compute_delay=0.025),
            ],
            extraparams=['--extramem=1000000'],
            modes=modes,
        ),

        #Experiment(
        #    'lammps12-milc24-jacobi36',
        #    [
        #        JacobiJob(nodes=24, iters=39, layout=(4, 3, 2), msg=50 * 1024, compute_delay=200),
        #        MilcJob(nodes=36, iters=120, layout=[2, 2, 3, 3], msg=486 * 1024, compute_delay=0.025),
        #        LammpsJob(nodes=12, replicas=(3, 2, 2), time_steps=5),
        #    ],
        #    extraparams=['--extramem=1000000'],
        #    modes=modes,
        #),

        #Experiment(
        #    'milc48-jacobi24',
        #    [
        #        JacobiJob(nodes=24, iters=150, layout=(4, 2, 3), msg=80 * 1024, compute_delay=200),
        #        MilcJob(nodes=48, iters=100, layout=[2, 8, 3, 1], msg=400 * 1024, compute_delay=50),
        #    ],
        #    extraparams=['--extramem=1000000'],
        #    modes=modes,
        #),

        #Experiment(
        #    'milc20-lammps22-jacobi20-ur8',
        #    [
        #        MilcJob(nodes=22, iters=100, layout=[2, 11, 1, 1], msg=400 * 1024, compute_delay=50),
        #        LammpsJob(nodes=22, replicas=(2, 11, 1), time_steps=5),
        #        JacobiJob(nodes=20, iters=150, layout=(4, 5, 1), msg=80 * 1024, compute_delay=200),
        #        UrJob(nodes=8, period=726.609003),
        #    ],
        #    extraparams=['--extramem=1000000'],
        #    modes=modes,
        #),
    ]

    try:
        config_generator = ConfigGenerator(configs_path, exp_folder)
        runner = TestRunner(env_vars, config_generator)
        runner.run_tests(common_config, experiments)
    except KeyboardInterrupt:
        # This should be handled by the signal handler, but just in case
        print("\nScript interrupted by user", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
