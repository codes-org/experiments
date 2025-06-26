#!/usr/bin/env python3
"""
Analyze CODES experiment results to extract runtime performance and application accuracy.
"""

import re
import json
import pandas as pd
from pathlib import Path
import sys
from typing import Any

# Global configuration variables
SIMULATION_MODES = [
    "high-fidelity",
    "app-surrogate",
    "app-and-network",
    "app-and-network-freezing"
]

SURROGATE_MODES = ['app-surrogate', 'app-and-network', 'app-and-network-freezing']

def load_experiment_metadata(base_path: Path) -> dict[str, list[str]]:
    """Load experiment metadata from JSON file"""
    metadata_file = base_path / "experiment_metadata.json"
    try:
        with open(metadata_file, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Warning: Metadata file not found at {metadata_file}")
        return {}
    except json.JSONDecodeError as e:
        print(f"Error parsing metadata file: {e}")
        return {}

def extract_simulation_runtime(model_result_path: Path) -> float | None:
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

def extract_app_completion_times(model_result_path: Path) -> dict[int, float]:
    """Extract application completion times from model-result.txt"""
    try:
        with open(model_result_path, 'r') as f:
            content = f.read()

        # Look for all "App X: XXXXX.XXXX" patterns
        app_matches = re.findall(r'App (\d+): ([\d.]+)', content)

        app_times: dict[int, float] = {}
        for app_id, time_str in app_matches:  # type: ignore[misc]
            app_times[int(app_id)] = float(time_str)

        return app_times
    except Exception as e:
        print(f"Error reading {model_result_path}: {e}")
        return {}

def analyze_all_experiments(base_path: Path, job_info: dict[str, list[str]]) -> list[dict[str, str | list[str] | dict[str, float | dict[int, float] | None]]]:
    """Analyze all experiments and return structured data"""

    # Get experiment directories from the actual results folder
    base_path = Path(base_path)
    experiments = [d.name for d in base_path.iterdir() if d.is_dir()]
    experiments.sort()

    # Analyze all simulation modes
    modes = SIMULATION_MODES

    results: list[dict[str, str | list[str] | dict[str, float | dict[int, float] | None]]] = []

    for exp in experiments:
        exp_path = base_path / exp
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
            app_times = extract_app_completion_times(mode_path)

            exp_data[mode] = {
                'runtime': runtime,
                'app_times': app_times
            }

        results.append({
            'experiment': exp,
            'data': exp_data,
            'job_types': job_info.get(exp, [])
        })

    return results

def calculate_speedups_and_errors(results: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Calculate speedups and application completion errors"""

    speedup_data = []
    error_data = []

    for result in results:
        exp_name = result['experiment']
        data = result['data']
        job_types = result['job_types']

        if 'high-fidelity' not in data:
            print(f"Warning: No high-fidelity data for {exp_name}")
            continue

        hf_runtime = data['high-fidelity']['runtime']
        hf_app_times = data['high-fidelity']['app_times']

        for mode in SURROGATE_MODES:
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
            for app_id in hf_app_times.keys():
                if app_id in mode_data['app_times']:
                    hf_time = hf_app_times[app_id]
                    mode_time = mode_data['app_times'][app_id]

                    if hf_time and mode_time:
                        error = ((mode_time - hf_time) / hf_time) * 100

                        # Get application name
                        app_name = f"App {app_id}"
                        if app_id < len(job_types):
                            app_name = f"{job_types[app_id]} (App {app_id})"

                        error_data.append({
                            'Experiment': exp_name,
                            'Mode': mode,
                            'Application': app_name,
                            'HF_Completion_ns': hf_time,
                            'Surrogate_Completion_ns': mode_time,
                            'Error_Percent': error
                        })

    return speedup_data, error_data

def main(base_path: Path, save_csv: bool = False) -> None:
    print("Analyzing CODES experiment results")
    print("=" * 50)

    # Load job info from metadata file
    job_info = load_experiment_metadata(base_path)

    # Extract all data
    results = analyze_all_experiments(base_path, job_info)

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
        speedup_pivot = speedup_df.pivot(
                index='Experiment',
                columns='Mode',
                values='Speedup'
        ).reindex(columns=SURROGATE_MODES)
        print(speedup_pivot.round(2))

        print(f"\nAverage speedups across all experiments:")
        for mode in SURROGATE_MODES:
            speedup_pivot_fair = speedup_pivot.dropna()
            if mode in speedup_pivot.columns:
                avg_speedup = speedup_pivot[mode].mean()
                avg_speedup_fair = speedup_pivot_fair[mode].mean()
                print(f"  {mode}: {avg_speedup:.2f}×  ({avg_speedup_fair:.2f}× ignoring any experiments with NaN)")
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
        ).reindex(columns=SURROGATE_MODES)
        print(error_pivot.round(2))

        print(f"\nAverage absolute errors across all experiments:")
        for mode in SURROGATE_MODES:
            if mode in error_pivot.columns:
                avg_abs_error = error_pivot[mode].abs().mean()
                print(f"  {mode}: {avg_abs_error:.2f}%")
    else:
        print("No error data available")

    # Save detailed results to CSV
    if save_csv:
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
    base_path = Path("results/exp-225-ghc-iter=2/")
    if len(sys.argv) > 1:
        base_path = Path(sys.argv[1])
    main(base_path)
