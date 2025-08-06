"""
Test runner for CODES simulation experiments.
Handles execution of experiments for multiple experiments and their network config variations.
"""

import os
import sys
import subprocess
import signal
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from .jobs import Experiment
from .config_generator import ConfigGenerator


class MemoryLogger:
    def __init__(self, scripts_dir: str):
        self.scripts_dir: str = scripts_dir
        self.process: subprocess.Popen[bytes] | None = None

    def start(self) -> bool:
        try:
            with open('memory-log.txt', 'w') as log_file:
                self.process = subprocess.Popen([
                    'bash', f"{self.scripts_dir}/memory-log.sh"
                ], stdout=log_file)
            return True
        except Exception as e:
            print(f"    ERROR: Failed to start memory logging: {e}")
            return False

    def stop(self) -> None:
        if self.process:
            try:
                self.process.terminate()
                _ = self.process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                try:
                    self.process.kill()
                    _ = self.process.wait(timeout=1)
                except:
                    pass
            except:
                pass
            self.process = None


class Execute:
    def __init__(self, binary_path: list[str], scripts_dir: str, env_vars: dict[str, str] | None = None, redirect_output: bool = True):
        self.binary_path: list[str] = binary_path
        self.env_vars: dict[str, str] = env_vars or {}
        self.memory_logger: MemoryLogger = MemoryLogger(scripts_dir)
        self.process: subprocess.Popen[bytes] | None = None
        self.interrupted: bool = False
        self.redirect_output: bool = redirect_output

    def __call__(self, output_dir: str, additional_args: list[str] | None = None) -> bool:
        complete_command = self.binary_path + (additional_args or [])
        output_path = Path(output_dir)

        with self.execution_context(output_path, self.env_vars):
            if self.interrupted:
                return False
            return self._execute_command(complete_command)

    @contextmanager
    def execution_context(self, output_dir: Path, env_vars: dict[str, str]) -> Generator[None, None, None]:
        original_cwd = Path.cwd()
        original_env = os.environ.copy()

        try:
            output_dir.mkdir(exist_ok=True)
            os.chdir(output_dir)
            os.environ.update(env_vars)

            if not self.memory_logger.start():
                raise RuntimeError("Failed to start memory logging")

            yield

        finally:
            self._cleanup_all()
            os.environ.clear()
            os.environ.update(original_env)
            os.chdir(original_cwd)

    def _execute_command(self, command: list[str]) -> bool:
        try:
            if self.redirect_output:
                return self._execute_with_file_output(command)
            else:
                return self._execute_with_interactive_output(command)

        except KeyboardInterrupt:
            print("    Interrupted during command execution")
            return False
        except Exception as e:
            print(f"    ERROR: Exception during command execution: {e}")
            return False

    def _execute_with_file_output(self, command: list[str]) -> bool:
        with open('model-result.txt', 'w') as stdout_file, \
             open('model-result.stderr.txt', 'w') as stderr_file:

            self.process = subprocess.Popen(
                command,
                stdout=stdout_file,
                stderr=stderr_file,
                preexec_fn=os.setsid
            )

            returncode = self.process.wait()
            self.process = None

            if returncode != 0:
                print(f"    ERROR: Command failed with return code {returncode}")
                return False
            return True

    def _execute_with_interactive_output(self, command: list[str]) -> bool:
        def setup_child_process():
            # Create new session and process group - isolates subprocess from parent's signal handling
            os.setsid()
            # Attempt to set as foreground process group for proper terminal signal delivery
            if os.isatty(sys.stdin.fileno()):
                try:
                    os.tcsetpgrp(sys.stdin.fileno(), os.getpid())
                except OSError:
                    # Some terminal environments don't support this operation
                    pass

        # Connect subprocess directly to terminal for full interactivity
        self.process = subprocess.Popen(
            command,
            stdin=sys.stdin,
            stdout=sys.stdout,
            stderr=sys.stderr,
            preexec_fn=setup_child_process
        )

        # Forward SIGINT (Ctrl+C) from parent to subprocess process group
        def forward_signal_to_subprocess(signum: int, _frame: object):
            if self.process is None:
                return
            try:
                # Send signal to entire process group, not just main process
                os.killpg(self.process.pid, signum)
            except (ProcessLookupError, OSError):
                # Process may have already terminated
                pass

        # Replace parent's signal handler with forwarding handler during subprocess execution
        original_handler = signal.signal(signal.SIGINT, forward_signal_to_subprocess)

        try:
            returncode = self.process.wait()
            self.process = None

            if returncode != 0:
                print(f"    ERROR: Command failed with return code {returncode}")
                return False
            return True

        except Exception as e:
            print(f"    ERROR: Exception during interactive execution: {e}")
            return False
        finally:
            # Restore original signal handler
            _ = signal.signal(signal.SIGINT, original_handler)

            # Restore parent as foreground process group if in a terminal
            if os.isatty(sys.stdin.fileno()):
                try:
                    os.tcsetpgrp(sys.stdin.fileno(), os.getpgrp())
                except OSError:
                    pass

    def _kill_process(self) -> None:
        if self.process:
            try:
                pgid = os.getpgid(self.process.pid)
                os.killpg(pgid, signal.SIGTERM)
                _ = self.process.wait(timeout=3)
            except (subprocess.TimeoutExpired, ProcessLookupError, OSError):
                try:
                    pgid = os.getpgid(self.process.pid)
                    os.killpg(pgid, signal.SIGKILL)
                    _ = self.process.wait(timeout=2)
                except (ProcessLookupError, OSError):
                    try:
                        self.process.kill()
                        _ = self.process.wait(timeout=1)
                    except:
                        pass
                except:
                    pass
            except:
                pass
            self.process = None

    def _cleanup_all(self) -> None:
        self._kill_process()
        self.memory_logger.stop()

    def interrupt(self) -> None:
        self.interrupted = True
        self._cleanup_all()


class TestRunner:
    def __init__(
            self,
            template_vars: dict[str, str],
            config_generator: ConfigGenerator,
            execute_with: Execute,
    ):
        self.template_vars: dict[str, str] = template_vars
        self.config_generator: ConfigGenerator = config_generator
        self.failed_experiments: list[str] = []
        self.interrupted: bool = False
        self.cleanup_in_progress: bool = False
        self.executor: Execute = execute_with

        _ = signal.signal(signal.SIGINT, self._signal_handler)

    def _signal_handler(self, _signum: int, _frame: object) -> None:
        if self.cleanup_in_progress:
            print("\nForce exiting...")
            os._exit(1)

        self.cleanup_in_progress = True
        print("\n\nReceived interrupt signal (Ctrl+C). Cleaning up...")
        self.interrupted = True
        self.executor.interrupt()

        print("Cleanup completed. Exiting...")
        sys.exit(1)

    def run_simulation(self, exp_config_dir: Path, variation_name: str,
                               extraparams: list[str], template_vars: dict[str, str]) -> bool:
        print(f"  Running simulation variation: {variation_name}")

        conf_path = self.config_generator.generate_network_config(exp_config_dir, variation_name, template_vars)
        args_file = exp_config_dir / f'args-file.conf'

        additional_args = [f'--args-file={str(args_file)}'] + extraparams + ['--', str(conf_path)]
        output_dir = f"{exp_config_dir.name}/{variation_name}"
        success = self.executor(output_dir, additional_args)

        if not success:
            print(f"    FAILED: Variation {variation_name} failed to complete")
            return False
        else:
            print(f"    SUCCESS: Variation {variation_name} completed successfully")
            return True

    def run_single_experiment(self, experiment: Experiment, template_vars: dict[str, str]) -> None:
        assert experiment.config_variations is None

        exp_config_dir = self.config_generator.generate_base_config(experiment, template_vars)
        exp_name = experiment.name

        print(f"Running single experiment for: {exp_name}")

        # Check if we've been interrupted
        success = False
        if self.interrupted:
            print("Experiment interrupted by user")
        else:
            success = self.run_simulation(exp_config_dir, "exec_output", experiment.extraparams, template_vars)

        if success:
            print("Successfully completed experiment")
        else:
            print("Failed to complete experiment")
            self.failed_experiments.append(exp_name)
        print("----------------------------------------")

    def run_experiment_with_config_variations(self, experiment: Experiment, template_vars: dict[str, str]) -> None:
        assert experiment.config_variations is not None

        exp_config_dir = self.config_generator.generate_base_config(experiment, template_vars)
        exp_name = experiment.name

        print(f"Running all simulation variations for: {exp_name}")

        failed_variations: list[str] = []
        successful_variations: list[str] = []

        for variation_name, overridding_vars in experiment.config_variations.items():
            # Check if we've been interrupted
            if self.interrupted:
                print("Experiment interrupted by user")
                break

            success = self.run_simulation(exp_config_dir, variation_name, experiment.extraparams, template_vars | overridding_vars)
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

            if experiment.config_variations is None:
                self.run_single_experiment(experiment, self.template_vars)
            else:
                self.run_experiment_with_config_variations(experiment, self.template_vars)

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
