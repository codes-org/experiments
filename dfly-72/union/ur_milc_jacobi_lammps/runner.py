"""
Test runner for CODES simulation experiments.
Handles execution of experiments for multiple experiments and their network config variations.
"""

import os
import sys
import subprocess
import signal
from pathlib import Path
from .jobs import Experiment
from .config_generator import ConfigGenerator


class TestRunner:
    """Main test runner for CODES simulation experiments."""

    def __init__(self, env_vars: dict[str, str], config_generator: ConfigGenerator, np: int = 3):
        self.env_vars: dict[str, str] = env_vars
        self.config_generator: ConfigGenerator = config_generator
        self.np: int = np
        self.failed_experiments: list[str] = []
        self.current_mpi_process: subprocess.Popen[bytes] | None = None
        self.current_mem_log_process: subprocess.Popen[bytes] | None = None
        self.interrupted: bool = False
        self.cleanup_in_progress: bool = False

        # Set up signal handler for graceful shutdown
        _ = signal.signal(signal.SIGINT, self._signal_handler)

        # Validate required environment variables
        required_vars = ['PATH_TO_CODES_BUILD', 'SCRIPTS_ROOT_DIR']
        for var in required_vars:
            if not os.environ.get(var):
                raise RuntimeError(f"Required environment variable {var} not set")

    def _signal_handler(self, _signum: int, _frame: object) -> None:
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
                    _ = self.current_mpi_process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    print("Force killing MPI process group...")
                    os.killpg(pgid, signal.SIGKILL)
                    _ = self.current_mpi_process.wait(timeout=2)

            except (ProcessLookupError, PermissionError, OSError):
                # Process group might not exist or already dead
                try:
                    # Fallback to killing just the main process
                    self.current_mpi_process.kill()
                    _ = self.current_mpi_process.wait(timeout=2)
                except:
                    pass

        # Kill memory logging process if running
        if self.current_mem_log_process:
            print("Terminating memory logging process...")
            try:
                self.current_mem_log_process.terminate()
                _ = self.current_mem_log_process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                try:
                    self.current_mem_log_process.kill()
                    _ = self.current_mem_log_process.wait(timeout=1)
                except:
                    pass
            except:
                pass

        print("Cleanup completed. Exiting...")
        sys.exit(1)

    def run_simulation_variation(
            self,
            exp_config_dir: Path,
            variation_name: str,
            extraparams: list[str],
            env_vars: dict[str, str],
    ) -> bool:
        print(f"  Running simulation variation: {variation_name}")

        conf_path = self.config_generator.generate_network_config(exp_config_dir, variation_name, env_vars)
        executable_path = os.environ['PATH_TO_CODES_BUILD'] + '/src/model-net-mpi-replay'
        args_file = exp_config_dir / f'args-file.conf'
        params = [executable_path, f'--args-file={str(args_file)}'] + extraparams + ['--', str(conf_path)]
        output_dir = f"{exp_config_dir.name}/{variation_name}"

        success = self.mpirun_do(output_dir, params)

        if not success:
            print(f"    FAILED: Variation {variation_name} failed to complete")
            return False
        else:
            print(f"    SUCCESS: Variation {variation_name} completed successfully")
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

                cmd = ['mpirun', '-np', str(self.np)] + args
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
                    _ = self.current_mpi_process.wait(timeout=3)
                except (subprocess.TimeoutExpired, ProcessLookupError, OSError) as e:
                    try:
                        # Force kill the process group (only if pgid was successfully obtained)
                        try:
                            pgid = os.getpgid(self.current_mpi_process.pid)
                            os.killpg(pgid, signal.SIGKILL)
                            _ = self.current_mpi_process.wait(timeout=2)
                        except (ProcessLookupError, OSError):
                            # Fallback to killing just the main process
                            self.current_mpi_process.kill()
                            _ = self.current_mpi_process.wait(timeout=1)
                    except:
                        # Final fallback to killing just the main process
                        try:
                            self.current_mpi_process.kill()
                            _ = self.current_mpi_process.wait(timeout=1)
                        except:
                            pass
                except:
                    pass
                self.current_mpi_process = None

            if self.current_mem_log_process:
                try:
                    self.current_mem_log_process.terminate()
                    _ = self.current_mem_log_process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    self.current_mem_log_process.kill()
                    _ = self.current_mem_log_process.wait()
                except:
                    pass
                self.current_mem_log_process = None

            os.chdir(original_cwd)

        return success

    def run_experiment_with_config_variations(self, experiment: Experiment, env_vars: dict[str, str]) -> None:
        exp_config_dir = self.config_generator.generate_base_config(experiment, env_vars)
        exp_name = experiment.name

        print(f"Running all simulation variations for: {exp_name}")

        failed_variations: list[str] = []
        successful_variations: list[str] = []

        for variation_name, overridding_vars in experiment.net_config_variations.items():
            # Check if we've been interrupted
            if self.interrupted:
                print("Experiment interrupted by user")
                break

            success = self.run_simulation_variation(exp_config_dir, variation_name, experiment.extraparams, env_vars | overridding_vars)
            if success:
                successful_variations.append(variation_name)
            else:
                failed_variations.append(variation_name)
                self.failed_experiments.append(f"{exp_name}/{variation_name}")

        print(f"Completed experiment: {exp_name}")
        if successful_variations:
            print(f"  Successful variations: {', '.join(successful_variations)}")
        if failed_variations:
            print(f"  Failed variations: {', '.join(failed_variations)}")
        print("----------------------------------------")

    def run_tests(self, experiments: list[Experiment]) -> None:
        """Run all test experiments."""
        print("Starting Testing Suite")
        print("============================================")

        # Run all tests
        for experiment in experiments:
            # Check if we've been interrupted
            if self.interrupted:
                print("Test suite interrupted by user")
                break

            self.run_experiment_with_config_variations(experiment, self.env_vars)

        print("============================================")
        print("TEST SUITE COMPLETED")
        print("============================================")

        if self.failed_experiments:
            print(f"FAILED EXPERIMENTS/VARIATIONS ({len(self.failed_experiments)}):")
            for failed in self.failed_experiments:
                print(f"  - {failed}")
            print()
            print("NOTE: Some experiments/variations failed, but the script continued")
            print("to run all remaining tests as requested.")
        else:
            print("All tests completed successfully!")

        print("============================================")
