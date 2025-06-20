#!/usr/bin/env python3
"""
Testing Script for 4-Application CODES Simulations
Applications: Jacobi, MILC, LAMMPS, UR (Uniform Random traffic)

Claude wrote most of this. I'm very grateful for it :)
"""

import os
import sys
import subprocess
import random
import signal
from pathlib import Path
from string import Template
from typing import Any

class TestRunner:
    def __init__(self, modes):
        self.modes = modes
        self.script_dir: Path = Path(__file__).parent
        self.configs_path: str = os.environ.get('PATH_TO_SCRIPT_DIR', str(self.script_dir)) + '/conf'
        self.exp_folder: Path = Path.cwd()
        self.tmpdir: None | str = None
        self.failed_experiments: list[str] = []
        self.current_mpi_process: subprocess.Popen | None = None
        self.current_mem_log_process: subprocess.Popen | None = None
        self.interrupted = False
        self.cleanup_in_progress = False

        # Set up signal handler for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)

        # Validate required environment variables
        required_vars = ['PATH_TO_CODES_BUILD', 'SCRIPTS_ROOT_DIR']
        for var in required_vars:
            if not os.environ.get(var):
                raise RuntimeError(f"Required environment variable {var} not set")

    def _signal_handler(self, signum, frame):
        """Handle Ctrl+C gracefully"""
        if self.cleanup_in_progress:
            print("\nForce exiting...")
            os._exit(1)

        self.cleanup_in_progress = True
        print("\n\nReceived interrupt signal (Ctrl+C). Cleaning up...")
        self.interrupted = True

        # Kill current MPI process if running - use process group killing
        if self.current_mpi_process:
            print("Terminating MPI process and its children...")
            try:
                # Try to kill the entire process group
                pgid = os.getpgid(self.current_mpi_process.pid)
                os.killpg(pgid, signal.SIGTERM)

                # Wait a short time for graceful termination
                try:
                    self.current_mpi_process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    print("Force killing MPI process group...")
                    os.killpg(pgid, signal.SIGKILL)
                    self.current_mpi_process.wait(timeout=2)

            except (ProcessLookupError, PermissionError, OSError):
                # Process group might not exist or already dead
                try:
                    # Fallback to killing just the main process
                    self.current_mpi_process.kill()
                    self.current_mpi_process.wait(timeout=2)
                except:
                    pass

        # Kill memory logging process if running
        if self.current_mem_log_process:
            print("Terminating memory logging process...")
            try:
                self.current_mem_log_process.terminate()
                self.current_mem_log_process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                try:
                    self.current_mem_log_process.kill()
                    self.current_mem_log_process.wait(timeout=1)
                except:
                    pass
            except:
                pass

        print("Cleanup completed. Exiting...")
        sys.exit(1)

    def generate_non_overlapping_allocations(self, jacobi_nodes: int, milc_nodes: int, lammps_nodes: int, ur_nodes: int):
        """Generate non-overlapping random node allocations for 4 applications"""
        total_needed = jacobi_nodes + milc_nodes + lammps_nodes + ur_nodes

        if total_needed > 72:
            raise ValueError(f"Total nodes needed ({total_needed}) exceeds available nodes (72)")

        # Generate shuffled list of required nodes
        all_nodes = random.sample(range(72), total_needed)

        # Split into application allocations
        idx = 0
        jacobi_alloc = all_nodes[idx:idx+jacobi_nodes]
        idx += jacobi_nodes

        milc_alloc = all_nodes[idx:idx+milc_nodes]
        idx += milc_nodes

        lammps_alloc = all_nodes[idx:idx+lammps_nodes]
        idx += lammps_nodes

        ur_alloc = all_nodes[idx:idx+ur_nodes]

        return {
            'JACOBI_ALLOCATION': ' '.join(map(str, jacobi_alloc)),
            'MILC_ALLOCATION': ' '.join(map(str, milc_alloc)),
            'LAMMPS_ALLOCATION': ' '.join(map(str, lammps_alloc)),
            'UR_ALLOCATION': ' '.join(map(str, ur_alloc))
        }

    def generate_base_config(self, exp_params: dict[str, Any]):
        """Generate base configuration for an experiment"""
        exp_name = exp_params['exp_name']

        print(f"Generating base configuration for: {exp_name}")
        print(f"  Jacobi: {exp_params['jacobi_iters']} iters, {exp_params['jacobi_msg']}B msgs, {exp_params['jacobi_nodes']} nodes, {exp_params['jacobi_compute_delay']}μs delay")
        print(f"  MILC: {exp_params['milc_iters']} iters, {exp_params['milc_msg']}B msgs, {exp_params['milc_nodes']} nodes, {exp_params['milc_compute_delay']}μs delay")
        print(f"  LAMMPS: {exp_params['lammps_nodes']} nodes, {exp_params['lammps_time_steps']} time steps")
        print(f"  UR: {exp_params['ur_nodes']} nodes, {exp_params['ur_period']}ns period")

        # Parse jacobi_layout for grid dimensions
        proc_x, proc_y, proc_z = exp_params['jacobi_layout']

        # Generate node allocations
        allocations = self.generate_non_overlapping_allocations(
            exp_params['jacobi_nodes'], exp_params['milc_nodes'],
            exp_params['lammps_nodes'], exp_params['ur_nodes']
        )

        compute_cycles_per_ms = exp_params['cpu_freq'] / 1e6
        jacobi_compute_delay = int(exp_params['jacobi_compute_delay'] * 1e3)
        milc_compute_delay = int(exp_params['milc_compute_delay'] * compute_cycles_per_ms)

        # Create experiment config directory
        exp_config_dir = self.exp_folder / exp_name
        exp_config_dir.mkdir(exist_ok=True)

        # Set all environment variables
        env_vars = {
            'CPU_FREQ': str(exp_params['cpu_freq']),

            'JACOBI_GRID_X': str(proc_x * 100),
            'JACOBI_GRID_Y': str(proc_y * 100),
            'JACOBI_GRID_Z': str(proc_z * 100),
            'JACOBI_BLOCK': '100',
            'JACOBI_ITERS': str(exp_params['jacobi_iters']),
            'JACOBI_MSG_SIZE': str(exp_params['jacobi_msg']),
            'JACOBI_COMPUTE_DELAY': str(jacobi_compute_delay),
            'JACOBI_NODES': str(exp_params['jacobi_nodes']),

            'MILC_ITERS': str(exp_params['milc_iters']),
            'MILC_MSG_SIZE': str(exp_params['milc_msg']),
            'MILC_COMPUTE_DELAY': str(int(milc_compute_delay)),
            'MILC_NODES': str(exp_params['milc_nodes']),
            'MILC_LAYOUT': ','.join(str(v) for v in exp_params['milc_layout']),
            'DIMENSION_CNT': str(len(exp_params['milc_layout'])),

            'LAMMPS_NODES': str(exp_params['lammps_nodes']),
            'LAMMPS_X_REPLICAS': str(exp_params['lammps_x_replicas']),
            'LAMMPS_Y_REPLICAS': str(exp_params['lammps_y_replicas']),
            'LAMMPS_Z_REPLICAS': str(exp_params['lammps_z_replicas']),
            'LAMMPS_TIME_STEPS': str(exp_params['lammps_time_steps']),

            'UR_NODES': str(exp_params['ur_nodes']),
            'UR_PERIOD': str(exp_params['ur_period']),

            'CURRENT_EXP_NAME': exp_name,
            'CURRENT_EXP_DIR': str(exp_config_dir),
        }

        # Add allocations
        env_vars.update(allocations)

        # Set environment variables
        os.environ.update(env_vars)

        # Generate configuration files using envsubst
        config_files = [
            'workloads-settings.conf',
            'workloads-allocation.conf',
            'milc_skeleton.json',
            'lammps_workload.json',
            'conceptual.json',
            'workloads-json.conf',
            'args-file.conf',
        ]

        for src_file in config_files:
            src_path = Path(self.configs_path) / src_file
            dst_path = exp_config_dir / src_file

            if src_path.exists():
                # Use envsubst to substitute environment variables
                with open(src_path, 'r') as f:
                    template_content = f.read()

                # Use Template for environment variable substitution
                template = Template(template_content)
                try:
                    substituted_content: str = template.substitute(os.environ)
                    with open(dst_path, 'w') as f:
                        _ = f.write(substituted_content)
                except KeyError as e:
                    print(f"Warning: Environment variable {e} not found when processing {src_file}")
                    # Fall back to envsubst
                    _ = subprocess.run(['envsubst'], input=template_content, text=True,
                                 stdout=open(dst_path, 'w'), check=True)

        return exp_config_dir

    def _generate_mode_network_config(self, exp_config_dir: Path, mode_name: str) -> Path:
        """Generate mode-specific network configuration file"""
        src_path = Path(self.configs_path) / 'dfdally-72-par.conf.in'
        conf_path = exp_config_dir / f'dfdally-72-par-{mode_name}.conf'

        with open(src_path, 'r') as f:
            template_content = f.read()

        template = Template(template_content)
        substituted_content = template.substitute(os.environ)

        with open(conf_path, 'w') as f:
            _ = f.write(substituted_content)

        return conf_path

    def run_simulation_mode(
            self,
            exp_config_dir: Path,
            mode_name: str,
            mode_settings: dict[str, str],
            extraparams: list[str],
    ) -> bool:
        """Run a specific simulation mode. Returns True on success, False on failure."""
        print(f"  Running simulation mode: {mode_name}")

        # Set mode-specific environment variables
        os.environ.update(mode_settings)

        conf_path = self._generate_mode_network_config(exp_config_dir, mode_name)
        executable_path = os.environ['PATH_TO_CODES_BUILD'] + '/src/model-net-mpi-replay'
        args_file = exp_config_dir / f'args-file.conf'
        params = [executable_path, f'--args-file={str(args_file)}'] + extraparams + ['--', str(conf_path)]
        output_dir = f"{os.environ['CURRENT_EXP_NAME']}/{mode_name}"

        success = self.mpirun_do(output_dir, params)

        if not success:
            print(f"    FAILED: Mode {mode_name} failed to complete")
            return False
        else:
            print(f"    SUCCESS: Mode {mode_name} completed successfully")
            return True

    def mpirun_do(self, output_dir_str: str, args: list[str]) -> bool:
        """Equivalent of the mpirun_do function. Returns True on success, False on failure."""
        output_dir = Path(output_dir_str)
        output_dir.mkdir(exist_ok=True)

        original_cwd = Path.cwd()
        os.chdir(output_dir)

        success = True

        try:
            # Check if we've been interrupted
            if self.interrupted:
                return False

            # Start memory logging
            self.current_mem_log_process = subprocess.Popen([
                'bash', f"{os.environ['SCRIPTS_ROOT_DIR']}/memory-log.sh"
            ], stdout=open('memory-log.txt', 'w'))

            # Run the simulation
            with open('model-result.txt', 'w') as stdout_file, \
                 open('model-result.stderr.txt', 'w') as stderr_file:

                cmd = ['mpirun', '-np', '3'] + args
                # Start MPI process in its own process group for easier cleanup
                self.current_mpi_process = subprocess.Popen(
                    cmd,
                    stdout=stdout_file,
                    stderr=stderr_file,
                    preexec_fn=os.setsid  # Create new process group
                )

                # Wait for process to complete
                try:
                    returncode = self.current_mpi_process.wait()
                    if returncode != 0:
                        print(f"    ERROR: mpirun failed with return code {returncode}")
                        success = False
                except KeyboardInterrupt:
                    # This shouldn't happen as signal handler should catch it first
                    # but just in case
                    print("    Interrupted during MPI execution")
                    success = False

                self.current_mpi_process = None

        except KeyboardInterrupt:
            print("    Interrupted during mpirun setup")
            success = False
        except Exception as e:
            print(f"    ERROR: Exception during mpirun: {e}")
            success = False

        finally:
            # Clean up processes
            if self.current_mpi_process:
                try:
                    # Try to kill the process group first
                    pgid = os.getpgid(self.current_mpi_process.pid)
                    os.killpg(pgid, signal.SIGTERM)
                    self.current_mpi_process.wait(timeout=3)
                except (subprocess.TimeoutExpired, ProcessLookupError, OSError):
                    try:
                        # Force kill the process group
                        os.killpg(pgid, signal.SIGKILL)
                        self.current_mpi_process.wait(timeout=2)
                    except:
                        # Fallback to killing just the main process
                        try:
                            self.current_mpi_process.kill()
                            self.current_mpi_process.wait(timeout=1)
                        except:
                            pass
                except:
                    pass
                self.current_mpi_process = None

            if self.current_mem_log_process:
                try:
                    self.current_mem_log_process.terminate()
                    self.current_mem_log_process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    self.current_mem_log_process.kill()
                    self.current_mem_log_process.wait()
                except:
                    pass
                self.current_mem_log_process = None

            os.chdir(original_cwd)

        return success

    def setup_default_config(self):
        os.environ.update({
            'PATH_TO_CONNECTIONS': self.configs_path,
            'NETWORK_SURR_ON': '1',
            'NETWORK_MODE': 'nothing',
            'APP_SURR_ON': '1',
            #'APP_DIRECTOR_MODE': 'every-n-nanoseconds',
            'APP_DIRECTOR_MODE': 'every-n-gvt',
            'EVERY_N_GVTS': '1500',
            'EVERY_NSECS': '1.0e6',
            'ITERS_TO_COLLECT': '5'
        })

    def run_experiment_with_modes(self, exp_params: dict[str, Any], extraparams: list[str]):
        """Run an experiment with all simulation modes"""
        exp_config_dir = self.generate_base_config(exp_params)
        exp_name = exp_params['exp_name']

        print(f"Running all simulation modes for: {exp_name}")

        failed_modes = []
        successful_modes = []

        for mode_name, mode_settings in self.modes.items():
            # Check if we've been interrupted
            if self.interrupted:
                print("Experiment interrupted by user")
                break

            success = self.run_simulation_mode(exp_config_dir, mode_name, mode_settings, extraparams)
            if success:
                successful_modes.append(mode_name)
            else:
                failed_modes.append(mode_name)
                self.failed_experiments.append(f"{exp_name}/{mode_name}")

        print(f"Completed experiment: {exp_name}")
        if successful_modes:
            print(f"  Successful modes: {', '.join(successful_modes)}")
        if failed_modes:
            print(f"  Failed modes: {', '.join(failed_modes)}")
        print("----------------------------------------")

    def run_tests(self, common_config, tests):
        print("Starting Testing Suite")
        print("============================================")

        # Backup configs and setup common configuration
        self.setup_default_config()

        # Run all tests
        for params in tests:
            # Check if we've been interrupted
            if self.interrupted:
                print("Test suite interrupted by user")
                break

            test_params = common_config | params
            extraparams: list[str] = test_params['extraparams']
            self.run_experiment_with_modes(test_params, extraparams)

        print("============================================")
        print("TEST SUITE COMPLETED")
        print("============================================")

        if self.failed_experiments:
            print(f"FAILED EXPERIMENTS/MODES ({len(self.failed_experiments)}):")
            for failed in self.failed_experiments:
                print(f"  - {failed}")
            print()
            print("NOTE: Some experiments/modes failed, but the script continued")
            print("to run all remaining tests as requested.")
        else:
            print("All tests completed successfully!")

        print("============================================")


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
        'app-and-network-freezing': {
            'NETWORK_SURR_ON': '1',
            'APP_SURR_ON': '1',
            'NETWORK_MODE': 'freeze'
        },
    }

    common_config = {
        'cpu_freq': 4e9, # in Hz
        'extraparams': ['--extramem=100000'],
    }

    # Define test experiments from README.md
    tests = [
        {
            'exp_name': 'milc36-jacobi36',
            'jacobi_nodes': 36, 'jacobi_iters': 39, 'jacobi_layout': [4,3,3], 'jacobi_msg': 50_000, 'jacobi_compute_delay': 200,
            'milc_nodes': 36, 'milc_iters': 120, 'milc_layout': [2,2,3,3], 'milc_msg': 497664, 'milc_compute_delay': 0.025,
            'lammps_nodes': 0, 'lammps_x_replicas': 2, 'lammps_y_replicas': 11, 'lammps_z_replicas': 1, 'lammps_time_steps': 5,
            'ur_nodes': 0, 'ur_period': 726.609003,
            'extraparams': ['--extramem=1000000'],
        },
        #{
        #    'exp_name': 'milc48-jacobi24',
        #    'jacobi_nodes': 24, 'jacobi_layout': [4,2,3], 'jacobi_msg': 80*1024, 'jacobi_iters': 150, 'jacobi_compute_delay': 200,
        #    'milc_nodes': 48, 'milc_iters': 100, 'milc_msg': 400*1024, 'milc_layout': [2,8,3,1], 'milc_compute_delay': 50,
        #    'lammps_nodes': 0, 'lammps_x_replicas': 2, 'lammps_y_replicas': 11, 'lammps_z_replicas': 1, 'lammps_time_steps': 5,
        #    'ur_nodes': 0, 'ur_period': 726.609003,
        #    'extraparams': ['--extramem=1000000'],
        #},
        #{
        #    'exp_name': '1-bandwidth-saturation',
        #    'jacobi_nodes': 20, 'jacobi_layout': [4,5,1], 'jacobi_msg': 80*1024, 'jacobi_iters': 150, 'jacobi_compute_delay': 200,
        #    'milc_nodes': 22, 'milc_iters': 100, 'milc_msg': 400*1024, 'milc_layout': [2,11,1,1], 'milc_compute_delay': 50,
        #    'lammps_nodes': 22, 'lammps_x_replicas': 2, 'lammps_y_replicas': 11, 'lammps_z_replicas': 1, 'lammps_time_steps': 5,
        #    'ur_nodes': 8, 'ur_period': 726.609003,
        #    'extraparams': ['--extramem=1000000'],
        #},
    ]

    try:
        runner = TestRunner(modes)
        runner.run_tests(common_config, tests)
    except KeyboardInterrupt:
        # This should be handled by the signal handler, but just in case
        print("\nScript interrupted by user", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
