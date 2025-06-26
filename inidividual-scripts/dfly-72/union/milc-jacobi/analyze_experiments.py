#!/usr/bin/env python3
"""
Analyze CODES experiment results to extract runtime performance and application accuracy.
Processes all 5 experiments × 4 simulation modes = 20 total runs.
"""

import os
import re
import pandas as pd
from pathlib import Path

def extract_simulation_runtime(model_result_path):
    """Extract the simulation runtime from model-result.txt"""
    try:
        with open(model_result_path, 'r') as f:
            content = f.read()
        
        # Look for "Running Time = X.XXXX seconds"
        match = re.search(r'Running Time = ([\d.]+) seconds', content)
        if match:
            return float(match.group(1))
        else:
            print(f"Warning: Could not find running time in {model_result_path}")
            return None
    except Exception as e:
        print(f"Error reading {model_result_path}: {e}")
        return None

def extract_app_completion_times(model_result_path):
    """Extract application completion times from model-result.txt"""
    try:
        with open(model_result_path, 'r') as f:
            content = f.read()
        
        # Look for "App 0: XXXXX.XXXX" and "App 1: XXXXX.XXXX"
        app0_match = re.search(r'App 0: ([\d.]+)', content)
        app1_match = re.search(r'App 1: ([\d.]+)', content)
        
        app0_time = float(app0_match.group(1)) if app0_match else None
        app1_time = float(app1_match.group(1)) if app1_match else None
        
        return app0_time, app1_time
    except Exception as e:
        print(f"Error reading {model_result_path}: {e}")
        return None, None

def analyze_all_experiments(base_path):
    """Analyze all experiments and return structured data"""
    
    # Define experiment names and simulation modes
    experiments = [
        "1-balanced-workload",
        "2-communication-heavy", 
        "3-iteration-heavy",
        "4-asymmetric-load",
        "5-high-concurrency"
    ]
    
    modes = [
        "high-fidelity",
        "app-surrogate",
        "app-net-not-freeze", 
        "app-net-freeze"
    ]
    
    results = []
    
    for exp in experiments:
        exp_path = Path(base_path) / exp
        if not exp_path.exists():
            print(f"Warning: Experiment {exp} not found at {exp_path}")
            continue
            
        exp_data = {}
        
        for mode in modes:
            mode_path = exp_path / mode / "model-result.txt"
            if not mode_path.exists():
                print(f"Warning: {mode} not found for {exp}")
                continue
                
            # Extract data
            runtime = extract_simulation_runtime(mode_path)
            app0_time, app1_time = extract_app_completion_times(mode_path)
            
            exp_data[mode] = {
                'runtime': runtime,
                'app0_completion': app0_time,
                'app1_completion': app1_time
            }
        
        results.append({
            'experiment': exp,
            'data': exp_data
        })
    
    return results

def calculate_speedups_and_errors(results):
    """Calculate speedups and application completion errors"""
    
    speedup_data = []
    error_data = []
    
    for result in results:
        exp_name = result['experiment']
        data = result['data']
        
        if 'high-fidelity' not in data:
            print(f"Warning: No high-fidelity data for {exp_name}")
            continue
            
        hf_runtime = data['high-fidelity']['runtime']
        hf_app0 = data['high-fidelity']['app0_completion']
        hf_app1 = data['high-fidelity']['app1_completion']
        
        for mode in ['app-surrogate', 'app-net-not-freeze', 'app-net-freeze']:
            if mode not in data:
                continue
                
            mode_data = data[mode]
            
            # Calculate speedup
            if hf_runtime and mode_data['runtime']:
                speedup = hf_runtime / mode_data['runtime']
                speedup_data.append({
                    'Experiment': exp_name,
                    'Mode': mode,
                    'HF_Runtime_s': hf_runtime,
                    'Surrogate_Runtime_s': mode_data['runtime'],
                    'Speedup': speedup
                })
            
            # Calculate application completion errors
            if hf_app0 and mode_data['app0_completion']:
                app0_error = ((mode_data['app0_completion'] - hf_app0) / hf_app0) * 100
                error_data.append({
                    'Experiment': exp_name,
                    'Mode': mode,
                    'Application': 'Jacobi (App 0)',
                    'HF_Completion_ns': hf_app0,
                    'Surrogate_Completion_ns': mode_data['app0_completion'],
                    'Error_Percent': app0_error
                })
            
            if hf_app1 and mode_data['app1_completion']:
                app1_error = ((mode_data['app1_completion'] - hf_app1) / hf_app1) * 100
                error_data.append({
                    'Experiment': exp_name,
                    'Mode': mode,
                    'Application': 'MILC (App 1)',
                    'HF_Completion_ns': hf_app1,
                    'Surrogate_Completion_ns': mode_data['app1_completion'],
                    'Error_Percent': app1_error
                })
    
    return speedup_data, error_data

def main():
    # Path to experiment results
    base_path = "/home/development/kronos/2024-feb-22/experiments/dfly-72/union/milc-jacobi/results/exp-358"
    
    print("Analyzing CODES experiment results...")
    print("=" * 50)
    
    # Extract all data
    results = analyze_all_experiments(base_path)
    
    # Calculate speedups and errors
    speedup_data, error_data = calculate_speedups_and_errors(results)
    
    # Create DataFrames
    speedup_df = pd.DataFrame(speedup_data)
    error_df = pd.DataFrame(error_data)
    
    # Display results
    print("\n📊 SIMULATION RUNTIME SPEEDUPS")
    print("=" * 50)
    if not speedup_df.empty:
        # Pivot table for better readability
        speedup_pivot = speedup_df.pivot(index='Experiment', columns='Mode', values='Speedup')
        print(speedup_pivot.round(2))
        
        print(f"\nAverage speedups across all experiments:")
        for mode in ['app-surrogate', 'app-net-not-freeze', 'app-net-freeze']:
            if mode in speedup_pivot.columns:
                avg_speedup = speedup_pivot[mode].mean()
                print(f"  {mode}: {avg_speedup:.2f}×")
    else:
        print("No speedup data available")
    
    print("\n📊 APPLICATION COMPLETION TIME ERRORS")
    print("=" * 50)
    if not error_df.empty:
        # Pivot table for better readability
        error_pivot = error_df.pivot_table(
            index=['Experiment', 'Application'], 
            columns='Mode', 
            values='Error_Percent'
        )
        print(error_pivot.round(2))
        
        print(f"\nAverage absolute errors across all experiments:")
        for mode in ['app-surrogate', 'app-net-not-freeze', 'app-net-freeze']:
            if mode in error_pivot.columns:
                avg_abs_error = error_pivot[mode].abs().mean()
                print(f"  {mode}: {avg_abs_error:.2f}%")
    else:
        print("No error data available")
    
    # Save detailed results to CSV
    print(f"\n💾 SAVING DETAILED RESULTS")
    print("=" * 50)
    
    speedup_df.to_csv('speedup_results.csv', index=False)
    error_df.to_csv('error_results.csv', index=False)
    
    print("Saved detailed results to:")
    print("  - speedup_results.csv")
    print("  - error_results.csv")
    
    # Summary statistics
    print(f"\n📈 SUMMARY STATISTICS")
    print("=" * 50)
    
    if not speedup_df.empty:
        print(f"Total simulations analyzed: {len(speedup_df)}")
        print(f"Best speedup: {speedup_df['Speedup'].max():.2f}× ({speedup_df.loc[speedup_df['Speedup'].idxmax(), 'Experiment']} - {speedup_df.loc[speedup_df['Speedup'].idxmax(), 'Mode']})")
        print(f"Worst speedup: {speedup_df['Speedup'].min():.2f}× ({speedup_df.loc[speedup_df['Speedup'].idxmin(), 'Experiment']} - {speedup_df.loc[speedup_df['Speedup'].idxmin(), 'Mode']})")
    
    if not error_df.empty:
        print(f"Best accuracy: {error_df['Error_Percent'].abs().min():.2f}% error")
        print(f"Worst accuracy: {error_df['Error_Percent'].abs().max():.2f}% error")
        
        # Check how many results have < 5% error
        low_error_count = (error_df['Error_Percent'].abs() < 5.0).sum()
        total_error_count = len(error_df)
        print(f"Results with <5% error: {low_error_count}/{total_error_count} ({low_error_count/total_error_count*100:.1f}%)")

if __name__ == "__main__":
    main()