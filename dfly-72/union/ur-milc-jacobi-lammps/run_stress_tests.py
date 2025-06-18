#!/usr/bin/env python3
"""
Stress Testing Script for 4-Application CODES Simulations
Applications: Jacobi, MILC, LAMMPS, UR (Uniform Random traffic)
"""

import os
import sys
import subprocess
import tempfile
import shutil
import random
from pathlib import Path
from string import Template
from typing import Any

class StressTestRunner:
    def __init__(self):
        self.script_dir: Path = Path(__file__).parent
        self.configs_path: str = os.environ.get('PATH_TO_SCRIPT_DIR', str(self.script_dir)) + '/conf'
        self.exp_folder: Path = Path.cwd()
        self.tmpdir: None | str = None
        
        # Validate required environment variables
        required_vars = ['PATH_TO_CODES_BUILD', 'PATH_TO_SWM_INSTALL', 'PATH_TO_UNION_INSTALL', 'SCRIPTS_ROOT_DIR']
        for var in required_vars:
            if not os.environ.get(var):
                raise RuntimeError(f"Required environment variable {var} not set")
    
    def backup_configs(self):
        """Backup original config files"""
        self.tmpdir = tempfile.mkdtemp(dir=str(self.exp_folder))
        
        swm_milc = Path(os.environ['PATH_TO_SWM_INSTALL']) / 'share/milc_skeleton.json'
        swm_lammps = Path(os.environ['PATH_TO_SWM_INSTALL']) / 'share/lammps_workload.json'
        union_conceptual = Path(os.environ['PATH_TO_UNION_INSTALL']) / 'share/conceptual.json'
        
        if swm_milc.exists():
            shutil.move(str(swm_milc), f"{self.tmpdir}/milc_skeleton.json")
        if swm_lammps.exists():
            shutil.move(str(swm_lammps), f"{self.tmpdir}/lammps_workload.json")
        if union_conceptual.exists():
            shutil.move(str(union_conceptual), f"{self.tmpdir}/conceptual.json")
    
    def restore_configs(self):
        """Restore original config files"""
        if not self.tmpdir:
            return
            
        swm_share = Path(os.environ['PATH_TO_SWM_INSTALL']) / 'share'
        union_share = Path(os.environ['PATH_TO_UNION_INSTALL']) / 'share'
        
        for filename in ['milc_skeleton.json', 'lammps_workload.json']:
            src = f"{self.tmpdir}/{filename}"
            if os.path.exists(src):
                shutil.move(src, str(swm_share / filename))
        
        conceptual_src = f"{self.tmpdir}/conceptual.json"
        if os.path.exists(conceptual_src):
            shutil.move(conceptual_src, str(union_share / 'conceptual.json'))
        
        os.rmdir(self.tmpdir)
    
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
    
    def setup_common_config(self):
        """Set up common CODES configuration"""
        os.environ.update({
            'PATH_TO_CONNECTIONS': self.configs_path,
            'NETWORK_SURR_ON': '1',
            'NETWORK_MODE': 'nothing',
            'APP_SURR_ON': '1',
            'APP_DIRECTOR_MODE': 'every-n-nanoseconds',
            'EVERY_N_GVTS': '1500',
            'EVERY_NSECS': '1.0e6',
            'ITERS_TO_COLLECT': '5'
        })
    
    def generate_base_config(self, exp_params: dict[str, Any]):
        """Generate base configuration for an experiment"""
        exp_name = exp_params['exp_name']
        
        print(f"Generating base configuration for: {exp_name}")
        print(f"  Jacobi: {exp_params['jacobi_iters']} iters, {exp_params['jacobi_msg']}B msgs, {exp_params['jacobi_nodes']} nodes, {exp_params['jacobi_compute_delay']}μs delay")
        print(f"  MILC: {exp_params['milc_iters']} iters, {exp_params['milc_msg']}B msgs, {exp_params['milc_nodes']} nodes, {exp_params['milc_compute_delay']}μs delay")
        print(f"  LAMMPS: {exp_params['lammps_nodes']} nodes, {exp_params['lammps_time_steps']} time steps")
        print(f"  UR: {exp_params['ur_nodes']} nodes, {exp_params['ur_period']}ns period")
        
        # Parse jacobi_layout for grid dimensions
        layout = exp_params['jacobi_layout'].split(',')
        proc_x, proc_y, proc_z = map(int, layout)
        
        # Generate node allocations
        allocations = self.generate_non_overlapping_allocations(
            exp_params['jacobi_nodes'], exp_params['milc_nodes'], 
            exp_params['lammps_nodes'], exp_params['ur_nodes']
        )
        
        # Set all environment variables
        env_vars = {
            'JACOBI_GRID_X': str(proc_x * 100),
            'JACOBI_GRID_Y': str(proc_y * 100),
            'JACOBI_GRID_Z': str(proc_z * 100),
            'JACOBI_BLOCK': '100',
            'JACOBI_ITERS': str(exp_params['jacobi_iters']),
            'JACOBI_MSG_SIZE': str(exp_params['jacobi_msg']),
            'JACOBI_COMPUTE_DELAY': str(exp_params['jacobi_compute_delay']),
            'JACOBI_NODES': str(exp_params['jacobi_nodes']),
            
            'MILC_ITERS': str(exp_params['milc_iters']),
            'MILC_MSG_SIZE': str(exp_params['milc_msg']),
            'MILC_COMPUTE_DELAY': str(exp_params['milc_compute_delay']),
            'MILC_NODES': str(exp_params['milc_nodes']),
            'MILC_LAYOUT': exp_params['milc_layout'],
            
            'LAMMPS_NODES': str(exp_params['lammps_nodes']),
            'LAMMPS_X_REPLICAS': str(exp_params['lammps_x_replicas']),
            'LAMMPS_Y_REPLICAS': str(exp_params['lammps_y_replicas']),
            'LAMMPS_Z_REPLICAS': str(exp_params['lammps_z_replicas']),
            'LAMMPS_TIME_STEPS': str(exp_params['lammps_time_steps']),
            
            'UR_NODES': str(exp_params['ur_nodes']),
            'UR_PERIOD': str(exp_params['ur_period']),
            
            'CURRENT_EXP_NAME': exp_name
        }
        
        # Add allocations
        env_vars.update(allocations)
        
        # Set environment variables
        os.environ.update(env_vars)
        
        # Create experiment config directory
        exp_config_dir = self.exp_folder / exp_name
        exp_config_dir.mkdir(exist_ok=True)
        
        # Generate configuration files using envsubst
        config_files = [
            ('workload.conf', 'workload.conf'),
            ('allocation.conf', 'allocation.conf'),
            ('milc_skeleton.json', 'milc_skeleton.json'),
            ('lammps_workload.json', 'lammps_workload.json'),
            ('conceptual.json', 'conceptual.json')
        ]
        
        for src_file, dst_file in config_files:
            src_path = Path(self.configs_path) / src_file
            dst_path = exp_config_dir / dst_file
            
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
        
        # Copy configs to install locations
        swm_share = Path(os.environ['PATH_TO_SWM_INSTALL']) / 'share'
        union_share = Path(os.environ['PATH_TO_UNION_INSTALL']) / 'share'
        
        shutil.copy(exp_config_dir / 'milc_skeleton.json', swm_share / 'milc_skeleton.json')
        shutil.copy(exp_config_dir / 'lammps_workload.json', swm_share / 'lammps_workload.json')
        shutil.copy(exp_config_dir / 'conceptual.json', union_share / 'conceptual.json')
        
        return exp_config_dir
    
    def run_simulation_mode(self, exp_config_dir: Path, mode_name: str, mode_settings: dict[str, str]):
        """Run a specific simulation mode"""
        print(f"  Running simulation mode: {mode_name}")
        
        # Set mode-specific environment variables
        os.environ.update(mode_settings)
        
        # Generate mode-specific network configuration
        src_path = Path(self.configs_path) / 'dfdally-72-par.conf.in'
        dst_path = exp_config_dir / f'dfdally-72-par-{mode_name}.conf'
        
        with open(src_path, 'r') as f:
            template_content = f.read()
        
        template = Template(template_content)
        substituted_content = template.substitute(os.environ)
        
        with open(dst_path, 'w') as f:
            _ = f.write(substituted_content)
        
        # Run the simulation using mpirun_do equivalent (matching original bash script)
        output_dir = f"{os.environ['CURRENT_EXP_NAME']}/{mode_name}"
        self.mpirun_do(
            output_dir,
            os.environ['PATH_TO_CODES_BUILD'] + '/src/model-net-mpi-replay',
            '--synch=3',
            '--cons-lookahead=200',
            '--batch=4', '--gvt-interval=256',
            '--cons-lookahead=200',
            '--max-opt-lookahead=600',
            '--workload_type=conc-online',
            '--lp-io-dir=lp-io-dir',
            '--extramem=100000',
            f'--workload_conf_file={exp_config_dir}/workload.conf',
            f'--alloc_file={exp_config_dir}/allocation.conf',
            '--',
            str(dst_path)
        )
    
    def mpirun_do(self, output_dir_str: str, *args: str):
        """Equivalent of the mpirun_do function"""
        output_dir = Path(output_dir_str)
        output_dir.mkdir(exist_ok=True)
        
        original_cwd = Path.cwd()
        os.chdir(output_dir)
        
        try:
            # Start memory logging
            mem_log_process = subprocess.Popen([
                'bash', f"{os.environ['SCRIPTS_ROOT_DIR']}/memory-log.sh"
            ], stdout=open('memory-log.txt', 'w'))
            
            # Run the simulation
            with open('model-result.txt', 'w') as stdout_file, \
                 open('model-result.stderr.txt', 'w') as stderr_file:
                
                cmd = ['mpirun', '-np', '3'] + list(args)
                _ = subprocess.run(cmd, stdout=stdout_file, stderr=stderr_file, check=True)
            
        finally:
            # Kill memory logging process
            if mem_log_process:
                mem_log_process.terminate()
                _ = mem_log_process.wait()
            
            os.chdir(original_cwd)
    
    def run_experiment_with_modes(self, exp_params: dict[str, Any]):
        """Run an experiment with all simulation modes"""
        exp_config_dir = self.generate_base_config(exp_params)
        exp_name = exp_params['exp_name']
        
        print(f"Running all simulation modes for: {exp_name}")
        
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
            'app-and-network': {
                'NETWORK_SURR_ON': '1',
                'APP_SURR_ON': '1',
                'NETWORK_MODE': 'nothing'
            },
            'app-and-network-freezing': {
                'NETWORK_SURR_ON': '1',
                'APP_SURR_ON': '1',
                'NETWORK_MODE': 'freeze'
            }
        }
        
        for mode_name, mode_settings in modes.items():
            self.run_simulation_mode(exp_config_dir, mode_name, mode_settings)
        
        print(f"Completed all modes for: {exp_name}")
        print("----------------------------------------")
    
    def run_stress_tests(self):
        """Run all 8 stress test experiments"""
        print("Starting 4-Application Stress Testing Suite")
        print("============================================")
        
        # Define 8 stress test experiments
        stress_tests = [
            {
                'exp_name': '1-stress-balanced',
                'jacobi_nodes': 8, 'jacobi_layout': '4,2,1', 'jacobi_msg': 1024, 'jacobi_iters': 50, 'jacobi_compute_delay': 100,
                'milc_nodes': 8, 'milc_iters': 50, 'milc_msg': 8192, 'milc_layout': '2,2,2,1', 'milc_compute_delay': 200,
                'lammps_nodes': 8, 'lammps_x_replicas': 2, 'lammps_y_replicas': 2, 'lammps_z_replicas': 2, 'lammps_time_steps': 100,
                'ur_nodes': 8, 'ur_period': 1210.0
            },
            {
                'exp_name': '2-stress-comm-heavy',
                'jacobi_nodes': 10, 'jacobi_layout': '5,2,1', 'jacobi_msg': 2048, 'jacobi_iters': 100, 'jacobi_compute_delay': 50,
                'milc_nodes': 10, 'milc_iters': 100, 'milc_msg': 16384, 'milc_layout': '5,2,1,1', 'milc_compute_delay': 100,
                'lammps_nodes': 10, 'lammps_x_replicas': 2, 'lammps_y_replicas': 2, 'lammps_z_replicas': 2, 'lammps_time_steps': 200,
                'ur_nodes': 10, 'ur_period': 908.25
            },
            {
                'exp_name': '3-stress-compute-intensive',
                'jacobi_nodes': 6, 'jacobi_layout': '3,2,1', 'jacobi_msg': 512, 'jacobi_iters': 30, 'jacobi_compute_delay': 1000,
                'milc_nodes': 6, 'milc_iters': 30, 'milc_msg': 4096, 'milc_layout': '3,2,1,1', 'milc_compute_delay': 800,
                'lammps_nodes': 6, 'lammps_x_replicas': 2, 'lammps_y_replicas': 1, 'lammps_z_replicas': 1, 'lammps_time_steps': 50,
                'ur_nodes': 6, 'ur_period': 1037.4
            },
            {
                'exp_name': '4-stress-high-iters',
                'jacobi_nodes': 12, 'jacobi_layout': '6,2,1', 'jacobi_msg': 1024, 'jacobi_iters': 200, 'jacobi_compute_delay': 150,
                'milc_nodes': 12, 'milc_iters': 200, 'milc_msg': 8192, 'milc_layout': '4,3,1,1', 'milc_compute_delay': 150,
                'lammps_nodes': 8, 'lammps_x_replicas': 2, 'lammps_y_replicas': 2, 'lammps_z_replicas': 2, 'lammps_time_steps': 500,
                'ur_nodes': 12, 'ur_period': 969.48
            },
            {
                'exp_name': '5-stress-mixed',
                'jacobi_nodes': 9, 'jacobi_layout': '3,3,1', 'jacobi_msg': 2048, 'jacobi_iters': 80, 'jacobi_compute_delay': 300,
                'milc_nodes': 9, 'milc_iters': 80, 'milc_msg': 12288, 'milc_layout': '3,3,1,1', 'milc_compute_delay': 400,
                'lammps_nodes': 9, 'lammps_x_replicas': 3, 'lammps_y_replicas': 1, 'lammps_z_replicas': 1, 'lammps_time_steps': 150,
                'ur_nodes': 9, 'ur_period': 854.8
            },
            {
                'exp_name': '6-stress-memory',
                'jacobi_nodes': 14, 'jacobi_layout': '7,2,1', 'jacobi_msg': 4096, 'jacobi_iters': 120, 'jacobi_compute_delay': 250,
                'milc_nodes': 14, 'milc_iters': 120, 'milc_msg': 16384, 'milc_layout': '7,2,1,1', 'milc_compute_delay': 300,
                'lammps_nodes': 10, 'lammps_x_replicas': 2, 'lammps_y_replicas': 2, 'lammps_z_replicas': 2, 'lammps_time_steps': 300,
                'ur_nodes': 14, 'ur_period': 807.35
            },
            {
                'exp_name': '7-stress-network-sat',
                'jacobi_nodes': 15, 'jacobi_layout': '5,3,1', 'jacobi_msg': 8192, 'jacobi_iters': 150, 'jacobi_compute_delay': 100,
                'milc_nodes': 15, 'milc_iters': 150, 'milc_msg': 32768, 'milc_layout': '5,3,1,1', 'milc_compute_delay': 200,
                'lammps_nodes': 12, 'lammps_x_replicas': 3, 'lammps_y_replicas': 2, 'lammps_z_replicas': 2, 'lammps_time_steps': 400,
                'ur_nodes': 15, 'ur_period': 764.85
            },
            {
                'exp_name': '8-stress-maximum',
                'jacobi_nodes': 16, 'jacobi_layout': '8,2,1', 'jacobi_msg': 16384, 'jacobi_iters': 200, 'jacobi_compute_delay': 500,
                'milc_nodes': 16, 'milc_iters': 200, 'milc_msg': 65536, 'milc_layout': '4,4,1,1', 'milc_compute_delay': 600,
                'lammps_nodes': 14, 'lammps_x_replicas': 4, 'lammps_y_replicas': 2, 'lammps_z_replicas': 2, 'lammps_time_steps': 500,
                'ur_nodes': 16, 'ur_period': 726.609003
            }
        ]
        
        # Backup configs and setup common configuration
        self.backup_configs()
        self.setup_common_config()
        
        try:
            # Run all stress tests
            for test_params in stress_tests:
                self.run_experiment_with_modes(test_params)
            
            print("============================================")
            print("All stress tests completed successfully!")
            print("============================================")
            
        finally:
            # Always restore configs
            self.restore_configs()

def main():
    try:
        runner = StressTestRunner()
        runner.run_stress_tests()
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
