"""
Configuration file generator for CODES simulation experiments.
Handles template processing.
"""

import random
from pathlib import Path
from string import Template
from .jobs import Experiment, Job
from dataclasses import dataclass


@dataclass
class NetworkConfig:
    """Configuration for a network topology."""
    name: str
    config_dir: str
    template_file: str
    output_prefix: str
    max_nodes: int


# Predefined network configurations
DFLY_72 = NetworkConfig(
    name="dfly-72",
    config_dir="dfly-72",
    template_file="dfdally-72-par.conf.in",
    output_prefix="dfdally-72-par",
    max_nodes=72
)

DFLY_1056 = NetworkConfig(
    name="dfly-1056",
    config_dir="dfly-1056",
    template_file="dfdally-1056-par.conf.in",
    output_prefix="dfdally-1056-par",
    max_nodes=1056
)

DFLY_8448 = NetworkConfig(
    name="dfly-8448",
    config_dir="dfly-8448",
    template_file="dfdally-8448-par.conf.in",
    output_prefix="dfdally-8448-par",
    max_nodes=8448
)


class ConfigGenerator:
    """Handles generation of configuration files for experiments."""

    def __init__(
        self,
        configs_path: str,
        exp_folder: Path,
        random_seed: int | None = None,
        random_allocation: bool = True,
        network_config: NetworkConfig = DFLY_72,
    ):
        self.configs_path: str = configs_path
        self.exp_folder: Path = exp_folder
        self.random_seed: int | None = random_seed
        self.random_allocation: bool = random_allocation
        self.network_config: NetworkConfig = network_config

    def generate_base_config(self, experiment: Experiment, template_vars: dict[str, str]) -> Path:
        """Generate base configuration for an experiment."""
        experiment.validate_jobs(self.network_config.max_nodes)

        exp_name = experiment.name
        jobs = experiment.jobs

        print(f"Generating base configuration for: {exp_name}")

        # Print job information
        for job in jobs:
            print(f"  {job.description}")

        # Create experiment config directory
        exp_config_dir = self.exp_folder / exp_name
        exp_config_dir.mkdir(exist_ok=True)

        # Add experiment-specific variables
        experiment_template_vars = template_vars | {
            'CURRENT_EXP_DIR': str(exp_config_dir),
        }

        # Generate configuration files directly
        self._generate_config_files(exp_config_dir, jobs, experiment_template_vars)

        return exp_config_dir

    def _generate_config_files(self, exp_config_dir: Path, jobs: list[Job], template_vars: dict[str, str]) -> None:
        """Generate all configuration files for the experiment."""

        # Write direct config files (no templates needed)
        self._write_workloads_settings(exp_config_dir, jobs)
        self._write_workloads_json(exp_config_dir, jobs)
        self._write_workloads_allocation(exp_config_dir, jobs)

        # Process job-specific templates
        self._process_job_templates(exp_config_dir, jobs, template_vars)

        # Process args-file template
        src_path = Path(self.configs_path) / 'args-file.conf'
        dst_path = exp_config_dir / 'args-file.conf'
        self.process_template(src_path, dst_path, template_vars)

    def _write_workloads_settings(self, exp_config_dir: Path, jobs: list[Job]) -> None:
        """Write workloads-settings.conf file directly."""
        lines = [job.format_workloads_settings(job.job_id) for job in jobs]
        content = '\n'.join(lines) + '\n'
        with open(exp_config_dir / 'workloads-settings.conf', 'w') as f:
            _ = f.write(content)

    def _write_workloads_json(self, exp_config_dir: Path, jobs: list[Job]) -> None:
        """Write workloads-json.conf file directly."""
        lines: list[str] = [f'{job.job_id} {exp_config_dir}/{job.config_filename}' for job in jobs if job.config_filename]
        content = '\n'.join(lines) + '\n'
        with open(exp_config_dir / 'workloads-json.conf', 'w') as f:
            _ = f.write(content)

    def _write_workloads_allocation(self, exp_config_dir: Path, jobs: list[Job]) -> None:
        """Write workloads-allocation.conf file directly."""
        lines: list[str] = []

        total_needed = sum(job.nodes for job in jobs)
        if total_needed > self.network_config.max_nodes:
            raise ValueError(f"Total nodes required ({total_needed}) exceeds network capacity ({self.network_config.max_nodes})")

        all_nodes = list(range(self.network_config.max_nodes))
        if self.random_allocation:
            if self.random_seed is not None:
                prev_state = random.getstate()
                random.seed(self.random_seed)
                random.shuffle(all_nodes)
                random.setstate(prev_state)
            else:
                random.shuffle(all_nodes)

        # Generate allocation lines in the same order as workloads-settings.conf
        idx = 0
        for job in jobs:
            job_nodes = all_nodes[idx:idx + job.nodes]
            idx += job.nodes
            lines.append(' '.join(map(str, job_nodes)))

        content = '\n'.join(lines) + '\n'

        with open(exp_config_dir / 'workloads-allocation.conf', 'w') as f:
            _ = f.write(content)

    def _process_job_templates(self, exp_config_dir: Path, jobs: list[Job], template_vars: dict[str, str]) -> None:
        for job in jobs:
            if not (job.template_path and job.config_filename):
                continue
            src_path = Path(self.configs_path) / job.template_path
            dst_path = exp_config_dir / job.config_filename
            self.process_template(src_path, dst_path, template_vars | job.template_vars)

    def process_template(self, src_path: Path, dst_path: Path, template_vars: dict[str, str]) -> None:
        if not src_path.exists():
            return

        with open(src_path, 'r') as f:
            template_content = f.read()

        template = Template(template_content)
        substituted_content = template.substitute(template_vars)
        with open(dst_path, 'w') as f:
            _ = f.write(substituted_content)

    def generate_network_config(self, exp_config_dir: Path, variation_name: str, template_vars: dict[str, str]) -> Path:
        dst_file = f'{self.network_config.output_prefix}-{variation_name}.conf'

        # Add experiment-specific variables
        template_vars = template_vars | {
            'CURRENT_EXP_DIR': str(exp_config_dir),
            'PATH_TO_CONNECTIONS': f'{self.configs_path}/{self.network_config.config_dir}',
        }

        src_path = Path(self.configs_path) / self.network_config.config_dir / self.network_config.template_file
        dst_path = exp_config_dir / dst_file
        self.process_template(src_path, dst_path, template_vars)
        return dst_path
