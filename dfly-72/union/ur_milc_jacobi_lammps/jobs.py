"""
Job classes for CODES simulation experiments.
Defines different types of workloads that can be run in the simulation.
"""

from __future__ import annotations
import math
import warnings
from collections import defaultdict
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import override, ClassVar, TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path


def _initialize_key_name(instance: Job, job_class: type, default_base_name: str) -> None:
    """Shared key_name initialization logic for all job types"""
    if instance.key_name is None:
        # Auto-generate key name
        job_class._instance_counter += 1
        if job_class._instance_counter == 1:
            instance.key_name = default_base_name
        else:
            instance.key_name = f"{default_base_name}-{job_class._instance_counter}"

    # Check for collisions and warn
    if instance.key_name in job_class._used_key_names:
        warnings.warn(
            f"{job_class.__name__} key_name '{instance.key_name}' already used. "
            + "This may cause configuration conflicts.",
            UserWarning,
            stacklevel=3
        )

    job_class._used_key_names.add(instance.key_name)


class Job(ABC):
    def __init__(self, nodes: int):
        self.nodes: int = nodes
        # Will be set in __post_init__
        self.job_id: str = ""
        self.key_name: str | None = None
        self.template_path: str | None = None
        self.config_filename: str | None = None
        self.description: str = ""

    @property
    @abstractmethod
    def env_vars(self) -> dict[str, str]:
        pass

    @abstractmethod
    def validate_layout(self) -> None:
        pass

    def format_workloads_settings(self, job_name: str) -> str:
        """Format line for workloads-settings.conf"""
        return f'{self.nodes} {job_name} 1 0'

    def has_config_file(self) -> bool:
        """Whether this job type generates a config file"""
        return self.config_filename is not None

    def format_workloads_json(self, job_name: str, exp_config_dir: Path, suffix: str = "") -> str | None:
        """Format line for workloads-json.conf, or None to skip"""
        if not self.has_config_file():
            return None
        config_filename = self.config_filename
        if config_filename is None:
            return None
        config_file = config_filename.format(suffix=f"-{suffix}" if suffix else "")
        return f'{job_name} {exp_config_dir}/{config_file}'


@dataclass
class JacobiJob(Job):
    """Jacobi 3D iterative solver job."""
    nodes: int
    iters: int
    layout: tuple[int, int, int]
    msg: int
    compute_delay: float
    key_name: str | None = None  # Optional override

    _instance_counter: ClassVar[int] = 0
    _used_key_names: ClassVar[set[str]] = set()

    def __post_init__(self):
        _initialize_key_name(self, JacobiJob, "jacobi3d")
        self.job_id: str = 'conceptual-jacobi3d'
        self.template_path: str | None = 'conceptual.json'
        self.config_filename: str | None = 'conceptual{suffix}.json'
        self.description: str = f"Jacobi: {self.iters} iters, {self.msg}B msgs, {self.nodes} nodes, {self.compute_delay}μs delay"

    @classmethod
    def reset_counters(cls):
        """Reset counters for testing purposes"""
        cls._instance_counter = 0
        cls._used_key_names.clear()


    @property
    @override
    def env_vars(self) -> dict[str, str]:
        proc_x, proc_y, proc_z = self.layout
        jacobi_compute_delay = int(self.compute_delay * 1e3)

        return {
            'JACOBI_KEY_NAME': self.key_name or 'jacobi3d',  # Ensure never None
            'JACOBI_GRID_X': str(proc_x * 100),
            'JACOBI_GRID_Y': str(proc_y * 100),
            'JACOBI_GRID_Z': str(proc_z * 100),
            'JACOBI_BLOCK': '100',
            'JACOBI_ITERS': str(self.iters),
            'JACOBI_MSG_SIZE': str(self.msg),
            'JACOBI_COMPUTE_DELAY': str(jacobi_compute_delay),
            'JACOBI_NODES': str(self.nodes),
        }

    @override
    def validate_layout(self) -> None:
        jacobi_prod = math.prod(self.layout)
        if self.nodes > 0:
            assert self.nodes == jacobi_prod, \
                f"jacobi nodes have to coincide with layout: nodes={self.nodes} != prod(layout)={jacobi_prod}"


@dataclass
class MilcJob(Job):
    """MILC (MIMD Lattice Computation) quantum chromodynamics job."""
    nodes: int
    iters: int
    layout: list[int]
    msg: int
    compute_delay: float
    key_name: str | None = None  # Optional override
    _cpu_freq: float = 4e9

    _instance_counter: ClassVar[int] = 0
    _used_key_names: ClassVar[set[str]] = set()

    def __post_init__(self):
        _initialize_key_name(self, MilcJob, "milc")
        self.job_id: str = 'milc'
        self.template_path: str | None = 'milc_skeleton.json'
        self.config_filename: str | None = 'milc{suffix}_skeleton.json'
        self.description: str = f"MILC: {self.iters} iters, {self.msg}B msgs, {self.nodes} nodes, {self.compute_delay}μs delay"

    @classmethod
    def reset_counters(cls):
        """Reset counters for testing purposes"""
        cls._instance_counter = 0
        cls._used_key_names.clear()


    @property
    @override
    def env_vars(self) -> dict[str, str]:
        return {
            'MILC_ITERS': str(self.iters),
            'MILC_MSG_SIZE': str(self.msg),
            'MILC_COMPUTE_DELAY': self._calculate_compute_delay(),
            'MILC_NODES': str(self.nodes),
            'MILC_LAYOUT': ','.join(str(v) for v in self.layout),
            'DIMENSION_CNT': str(len(self.layout)),
        }

    def _calculate_compute_delay(self) -> str:
        compute_cycles_per_ms = self._cpu_freq / 1e6
        milc_compute_delay = int(self.compute_delay * compute_cycles_per_ms)
        return str(milc_compute_delay)

    @override
    def validate_layout(self) -> None:
        milc_prod = math.prod(self.layout)
        if self.nodes > 0:
            assert self.nodes == milc_prod, \
                f"milc nodes have to coincide with layout: nodes={self.nodes} != prod(layout)={milc_prod}"


@dataclass
class LammpsJob(Job):
    """LAMMPS molecular dynamics job."""
    nodes: int
    replicas: tuple[int, int, int]
    time_steps: int
    key_name: str | None = None  # Optional override

    _instance_counter: ClassVar[int] = 0
    _used_key_names: ClassVar[set[str]] = set()

    def __post_init__(self):
        _initialize_key_name(self, LammpsJob, "lammps")
        self.job_id: str = 'lammps'
        self.template_path: str | None = 'lammps_workload.json'
        self.config_filename: str | None = 'lammps{suffix}_workload.json'
        self.description: str = f"LAMMPS: {self.nodes} nodes, {self.time_steps} time steps"

    @classmethod
    def reset_counters(cls):
        """Reset counters for testing purposes"""
        cls._instance_counter = 0
        cls._used_key_names.clear()


    @property
    @override
    def env_vars(self) -> dict[str, str]:
        lammps_x_replicas, lammps_y_replicas, lammps_z_replicas = self.replicas

        return {
            'LAMMPS_NODES': str(self.nodes),
            'LAMMPS_X_REPLICAS': str(lammps_x_replicas),
            'LAMMPS_Y_REPLICAS': str(lammps_y_replicas),
            'LAMMPS_Z_REPLICAS': str(lammps_z_replicas),
            'LAMMPS_TIME_STEPS': str(self.time_steps),
        }

    @override
    def validate_layout(self) -> None:
        lammps_prod = math.prod(self.replicas)
        if self.nodes > 0:
            assert self.nodes == lammps_prod, \
                f"lammps nodes have to coincide with replicas: nodes={self.nodes} != prod(layout)={lammps_prod}"


@dataclass
class UrJob(Job):
    """Uniform Random traffic job."""
    nodes: int
    period: float
    key_name: str | None = None  # Optional override

    _instance_counter: ClassVar[int] = 0
    _used_key_names: ClassVar[set[str]] = set()

    def __post_init__(self):
        _initialize_key_name(self, UrJob, "synthetic1")
        self.job_id: str = 'synthetic1'
        self.template_path: str | None = None
        self.config_filename: str | None = None
        self.description: str = f"UR: {self.nodes} nodes, {self.period}ns period"

    @classmethod
    def reset_counters(cls):
        """Reset counters for testing purposes"""
        cls._instance_counter = 0
        cls._used_key_names.clear()


    @property
    @override
    def env_vars(self) -> dict[str, str]:
        return {
            'UR_NODES': str(self.nodes),
            'UR_PERIOD': str(self.period),
        }

    @override
    def validate_layout(self) -> None:
        pass

    @override
    def format_workloads_settings(self, job_name: str) -> str:
        """UR jobs have different workloads-settings format"""
        return f'{self.nodes} {job_name} 0 {self.period}'


class Experiment:
    """Container for an experiment with multiple jobs."""

    def __init__(self, name: str, jobs: list[Job], extraparams: list[str], modes: dict[str, dict[str, str]]):
        # Reset all job counters before processing jobs for this experiment
        self.reset_all_job_counters()

        self.name = name
        self.jobs = jobs
        self.extraparams = extraparams
        self.modes = modes

    def get_total_nodes(self) -> int:
        """Get the total number of nodes needed for all jobs."""
        return sum(job.nodes for job in self.jobs)

    def validate_jobs(self) -> None:
        """Validate all jobs and check total node constraints."""
        for job in self.jobs:
            job.validate_layout()

        total_nodes = self.get_total_nodes()
        if total_nodes > 72:
            raise ValueError(f"Total nodes needed ({total_nodes}) exceeds available nodes (72)")

    def get_jobs_by_type(self) -> dict[str, list[tuple[Job, str]]]:
        """Group jobs by type and assign suffixes for multiple instances."""
        jobs_by_type: dict[str, list[Job]] = defaultdict(list)

        for job in self.jobs:
            jobs_by_type[job.job_id].append(job)

        # Assign suffixes for multiple instances
        result: dict[str, list[tuple[Job, str]]] = {}
        for job_id, job_list in jobs_by_type.items():
            result[job_id] = []
            for i, job in enumerate(job_list):
                suffix = str(i + 1) if i > 0 else ''  # First instance has no suffix, second gets "2", etc.
                result[job_id].append((job, suffix))

        return result

    @classmethod
    def reset_all_job_counters(cls):
        """Reset all job type counters for testing purposes"""
        JacobiJob.reset_counters()
        MilcJob.reset_counters()
        LammpsJob.reset_counters()
        UrJob.reset_counters()
