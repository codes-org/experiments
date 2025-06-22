"""
Configuration file generator for CODES simulation experiments.
Handles template processing, environment variable substitution, and node allocation.
"""

import random
from pathlib import Path
from string import Template
from .jobs import Experiment, Job


class ConfigGenerator:
    """Handles generation of configuration files for experiments."""

    def __init__(self, configs_path: str, exp_folder: Path):
        self.configs_path: str = configs_path
        self.exp_folder: Path = exp_folder


    def generate_base_config(self, experiment: Experiment, env_vars: dict[str, str]) -> Path:
        """Generate base configuration for an experiment."""
        experiment.validate_jobs()

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
        experiment_env_vars = env_vars | {
            'CURRENT_EXP_DIR': str(exp_config_dir),
        }

        # Generate configuration files directly
        jobs_by_type = experiment.get_jobs_by_type()
        self._generate_config_files(exp_config_dir, jobs_by_type, experiment_env_vars)

        return exp_config_dir

    def _generate_config_files(self, exp_config_dir: Path, jobs_by_type: dict[str, list[tuple[Job, str]]], env_vars: dict[str, str]) -> None:
        """Generate all configuration files for the experiment."""

        # Write direct config files (no templates needed)
        self._write_workloads_settings(exp_config_dir, jobs_by_type)
        self._write_workloads_json(exp_config_dir, jobs_by_type)
        self._write_workloads_allocation(exp_config_dir, jobs_by_type)

        # Process job-specific templates
        self._process_job_templates(exp_config_dir, jobs_by_type, env_vars)

        # Process args-file template
        src_path = Path(self.configs_path) / 'args-file.conf'
        dst_path = exp_config_dir / 'args-file.conf'
        self.process_template(src_path, dst_path, env_vars)

    def _write_workloads_settings(self, exp_config_dir: Path, jobs_by_type: dict[str, list[tuple[Job, str]]]) -> None:
        """Write workloads-settings.conf file directly."""
        lines: list[str] = []

        for _, job_suffix_pairs in jobs_by_type.items():
            for job, suffix in job_suffix_pairs:
                # Use job's job_id as the base name for job identification
                job_name = f'{job.job_id}{f"-{suffix}" if suffix else ""}'

                # Use the job's format method - no special handling needed!
                lines.append(job.format_workloads_settings(job_name))

        content = '\n'.join(lines) + '\n'
        with open(exp_config_dir / 'workloads-settings.conf', 'w') as f:
            _ = f.write(content)

    def _write_workloads_json(self, exp_config_dir: Path, jobs_by_type: dict[str, list[tuple[Job, str]]]) -> None:
        """Write workloads-json.conf file directly."""
        lines: list[str] = []

        for _, job_suffix_pairs in jobs_by_type.items():
            for job, suffix in job_suffix_pairs:
                # Use job's job_id as the base name for job identification
                job_name = f'{job.job_id}{f"-{suffix}" if suffix else ""}'

                # Use the job's format method - returns None for jobs without config files
                json_line = job.format_workloads_json(job_name, exp_config_dir, suffix)
                if json_line:
                    lines.append(json_line)

        content = '\n'.join(lines) + '\n'
        with open(exp_config_dir / 'workloads-json.conf', 'w') as f:
            _ = f.write(content)

    def _write_workloads_allocation(self, exp_config_dir: Path, jobs_by_type: dict[str, list[tuple[Job, str]]]) -> None:
        """Write workloads-allocation.conf file directly."""
        lines: list[str] = []

        # Generate allocation lines directly from the job allocations we created
        total_needed = sum(job.nodes for job_list in jobs_by_type.values() for job, _ in job_list)
        all_nodes = random.sample(range(72), total_needed)

        idx = 0
        # Generate allocation lines in the same order as workloads-settings.conf
        for _, job_suffix_pairs in jobs_by_type.items():
            for job, _ in job_suffix_pairs:
                job_nodes = all_nodes[idx:idx + job.nodes]
                idx += job.nodes
                lines.append(' '.join(map(str, job_nodes)))

        content = '\n'.join(lines) + '\n'

        with open(exp_config_dir / 'workloads-allocation.conf', 'w') as f:
            _ = f.write(content)

    def _process_job_templates(self, exp_config_dir: Path, jobs_by_type: dict[str, list[tuple[Job, str]]], env_vars: dict[str, str]) -> None:
        """Process all job templates using job.template_path and job.config_filename"""

        # Handle all job types generically using their template_path and config_filename
        for _, job_suffix_pairs in jobs_by_type.items():
            for job, suffix in job_suffix_pairs:
                if job.template_path and job.config_filename:  # Only process jobs that have templates and config files
                    src_path = Path(self.configs_path) / job.template_path
                    config_filename = job.config_filename.format(
                        suffix=f"-{suffix}" if suffix else ""
                    )
                    dst_path = exp_config_dir / config_filename

                    # Combine global env vars with job-specific env vars
                    combined_env_vars = env_vars | job.env_vars
                    self.process_template(src_path, dst_path, combined_env_vars)

    def process_template(self, src_path: Path, dst_path: Path, env_vars: dict[str, str]) -> None:
        """Unified template processor - handles all template → config transformations."""
        if not src_path.exists():
            return

        with open(src_path, 'r') as f:
            template_content = f.read()

        template = Template(template_content)
        substituted_content = template.substitute(env_vars)
        with open(dst_path, 'w') as f:
            _ = f.write(substituted_content)

    def generate_mode_network_config(self, exp_config_dir: Path, mode_name: str, env_vars: dict[str, str]) -> Path:
        """Generate mode-specific network configuration file."""
        dst_file = f'dfdally-72-par-{mode_name}.conf'

        # Add experiment-specific variables
        template_vars = env_vars | {
            'CURRENT_EXP_NAME': exp_config_dir.name,
            'CURRENT_EXP_DIR': str(exp_config_dir),
            'PATH_TO_CONNECTIONS': self.configs_path,
        }

        src_path = Path(self.configs_path) / 'dfdally-72-par.conf.in'
        dst_path = exp_config_dir / dst_file
        self.process_template(src_path, dst_path, template_vars)
        return dst_path
