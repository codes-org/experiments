#!/usr/bin/env python3
"""
Analyze CODES experiment results to extract runtime performance and application accuracy.
Mostly written by Claude.
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

def extract_simulation_runtime(content: str, model_result_path: Path) -> float | None:
    """Extract the simulation runtime from model-result.txt content"""
    # Look for "Running Time = X.XXXX seconds"
    match = re.search(r'Running Time = ([\d.]+) seconds', content)
    if match:
        return float(match.group(1))
    else:
        print(f"Warning: Could not find running time in {model_result_path}")
        return None

def extract_app_completion_times(content: str) -> dict[int, float]:
    """Extract application completion times from model-result.txt content"""
    # Look for all "App X: XXXXX.XXXX" patterns
    app_matches = re.findall(r'App (\d+): ([\d.]+)', content)

    app_times: dict[int, float] = {}
    for app_id, time_str in app_matches:  # type: ignore[misc]
        app_times[int(app_id)] = float(time_str)

    return app_times

def extract_net_events_processed(content: str, model_result_path: Path) -> int | None:
    """Extract the net events processed from model-result.txt content"""
    # Look for "Net Events Processed                                XXXXXXXX"
    match = re.search(r'Net Events Processed\s+(\d+)', content)
    if match:
        return int(match.group(1))
    else:
        print(f"Warning: Could not find net events processed in {model_result_path}")
        return None

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

            # Read file once and extract all data
            try:
                with open(mode_path, 'r') as f:
                    content = f.read()

                runtime = extract_simulation_runtime(content, mode_path)
                app_times = extract_app_completion_times(content)
                net_events = extract_net_events_processed(content, mode_path)

                exp_data[mode] = {
                    'runtime': runtime,
                    'app_times': app_times,
                    'net_events': net_events
                }
            except Exception as e:
                print(f"Error reading {mode_path}: {e}")
                exp_data[mode] = {
                    'runtime': None,
                    'app_times': {},
                    'net_events': None
                }

        results.append({
            'experiment': exp,
            'data': exp_data,
            'job_types': job_info.get(exp, [])
        })

    return results

def calculate_speedups_and_errors(results: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """Calculate speedups, application completion errors, and event metrics"""

    speedup_data = []
    error_data = []
    dashboard_data = []

    for result in results:
        exp_name = result['experiment']
        data = result['data']
        job_types = result['job_types']

        if 'high-fidelity' not in data:
            print(f"Warning: No high-fidelity data for {exp_name}")
            continue

        hf_runtime = data['high-fidelity']['runtime']
        hf_app_times = data['high-fidelity']['app_times']
        hf_net_events = data['high-fidelity']['net_events']

        for mode in SURROGATE_MODES:
            if mode not in data:
                continue

            mode_data = data[mode]

            # Calculate speedup
            speedup = None
            if hf_runtime and mode_data['runtime']:
                speedup = hf_runtime / mode_data['runtime']
                speedup_data.append({
                    'Experiment': exp_name,
                    'Mode': mode,
                    'HF_Runtime_s': hf_runtime,
                    'Surrogate_Runtime_s': mode_data['runtime'],
                    'Speedup': speedup
                })

            # Calculate event metrics
            events_skipped_pct = None
            theoretical_speedup = None
            if hf_net_events and mode_data['net_events']:
                event_ratio = mode_data['net_events'] / hf_net_events
                events_skipped_pct = (1 - event_ratio) * 100
                theoretical_speedup = 1 / event_ratio

            # Calculate application completion errors and collect for dashboard
            app_errors = []
            for app_id in hf_app_times.keys():
                if app_id in mode_data['app_times']:
                    hf_time = hf_app_times[app_id]
                    mode_time = mode_data['app_times'][app_id]

                    if hf_time and mode_time:
                        error = ((mode_time - hf_time) / hf_time) * 100
                        app_errors.append(abs(error))

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

            # Calculate dashboard metrics
            if app_errors:
                min_error = min(app_errors)
                max_error = max(app_errors)
                apps_above_5pct = sum(1 for err in app_errors if err > 5.0)
                total_apps = len(app_errors)

                # Calculate efficiency
                efficiency = None
                if speedup and theoretical_speedup:
                    efficiency = speedup / theoretical_speedup

                dashboard_data.append({
                    'Experiment': exp_name,
                    'Mode': mode,
                    'Speedup': speedup,
                    'Events_Skipped_Pct': events_skipped_pct,
                    'Theoretical_Speedup': theoretical_speedup,
                    'Efficiency': efficiency,
                    'Min_Error_Pct': min_error,
                    'Max_Error_Pct': max_error,
                    'Apps_Above_5pct': apps_above_5pct,
                    'Total_Apps': total_apps
                })

    return speedup_data, error_data, dashboard_data

def parse_iteration_experiment_name(exp_name: str) -> tuple[str, int | None]:
    """Parse experiment name to extract base name and iteration number.

    Returns:
        tuple: (base_name, iteration_number) or (exp_name, None) if no iteration found
    """
    match = re.match(r'(.+)_iter=(\d+)$', exp_name)
    if match:
        base_name = match.group(1)
        iteration = int(match.group(2))
        return base_name, iteration
    return exp_name, None

def analyze_iteration_experiments(base_path: Path, job_info: dict[str, list[str]]) -> dict[str, list[dict[str, Any]]]:
    """Analyze iteration experiments grouped by base experiment name"""
    all_experiments = []

    # Get all experiments in the directory
    for exp_dir in base_path.iterdir():
        if exp_dir.is_dir() and not exp_dir.name.startswith('.'):
            all_experiments.append(exp_dir.name)

    # Group experiments by base name
    iteration_groups: dict[str, list[str]] = {}
    for exp_name in all_experiments:
        base_name, iteration = parse_iteration_experiment_name(exp_name)
        if iteration is not None:
            if base_name not in iteration_groups:
                iteration_groups[base_name] = []
            iteration_groups[base_name].append(exp_name)

    # Analyze each group
    results_by_base: dict[str, list[dict[str, Any]]] = {}
    for base_name, exp_list in iteration_groups.items():
        print(f"Analyzing iteration group: {base_name}")

        # Analyze each experiment in the group
        group_results = []
        for exp_name in sorted(exp_list):  # Sort to ensure consistent order
            exp_path = base_path / exp_name

            # Reuse existing analysis logic
            exp_data: dict[str, dict[str, Any]] = {}

            for mode in ['high-fidelity'] + SURROGATE_MODES:
                mode_path = exp_path / mode / 'model-result.txt'
                if not mode_path.exists():
                    continue

                # Read file once and extract all data
                try:
                    with open(mode_path, 'r') as f:
                        content = f.read()

                    runtime = extract_simulation_runtime(content, mode_path)
                    app_times = extract_app_completion_times(content)
                    net_events = extract_net_events_processed(content, mode_path)

                    exp_data[mode] = {
                        'runtime': runtime,
                        'app_times': app_times,
                        'net_events': net_events
                    }
                except Exception as e:
                    print(f"Error reading {mode_path}: {e}")
                    exp_data[mode] = {
                        'runtime': None,
                        'app_times': {},
                        'net_events': None
                    }

            # Parse iteration number
            _, iteration = parse_iteration_experiment_name(exp_name)

            group_results.append({
                'experiment': exp_name,
                'base_name': base_name,
                'iteration': iteration,
                'data': exp_data,
                'job_types': job_info.get(base_name, job_info.get(exp_name, []))
            })

        results_by_base[base_name] = group_results

    return results_by_base

def calculate_iteration_metrics(iteration_results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Calculate metrics for iteration experiments"""
    iteration_data = []

    # Find high-fidelity baseline (should be in iter=1)
    hf_baseline = None
    for result in iteration_results:
        if 'high-fidelity' in result['data'] and result['data']['high-fidelity']['runtime']:
            hf_baseline = result['data']['high-fidelity']
            break

    if not hf_baseline:
        print("Warning: No high-fidelity baseline found for iteration analysis")
        return []

    hf_runtime = hf_baseline['runtime']
    hf_app_times = hf_baseline['app_times']
    hf_net_events = hf_baseline['net_events']

    # Process each iteration
    for result in iteration_results:
        iteration = result['iteration']
        job_types = result['job_types']

        # Add high-fidelity entry only for iteration 1
        if iteration == 1:
            iteration_data.append({
                'Base_Experiment': result['base_name'],
                'Iteration': iteration,
                'Mode': 'high-fidelity',
                'Speedup': 1.0,
                'Events_Skipped_Pct': 0.0,
                'Theoretical_Speedup': 1.0,
                'Efficiency': 1.0,
                'Min_Error_Pct': 0.0,
                'Max_Error_Pct': 0.0,
                'Apps_Above_5pct': 0,
                'Total_Apps': len(hf_app_times) if hf_app_times else 0
            })

        # Process surrogate modes
        for mode in SURROGATE_MODES:
            if mode not in result['data']:
                continue

            mode_data = result['data'][mode]

            # Calculate speedup
            speedup = None
            if hf_runtime and mode_data['runtime']:
                speedup = hf_runtime / mode_data['runtime']

            # Calculate event metrics
            events_skipped_pct = None
            theoretical_speedup = None
            if hf_net_events and mode_data['net_events']:
                event_ratio = mode_data['net_events'] / hf_net_events
                events_skipped_pct = (1 - event_ratio) * 100
                theoretical_speedup = 1 / event_ratio

            # Calculate efficiency
            efficiency = None
            if speedup and theoretical_speedup:
                efficiency = speedup / theoretical_speedup

            # Calculate application errors
            app_errors = []
            for app_id in hf_app_times.keys():
                if app_id in mode_data['app_times']:
                    hf_time = hf_app_times[app_id]
                    mode_time = mode_data['app_times'][app_id]

                    if hf_time and mode_time:
                        error = ((mode_time - hf_time) / hf_time) * 100
                        app_errors.append(abs(error))

            # Calculate error metrics
            min_error = min(app_errors) if app_errors else None
            max_error = max(app_errors) if app_errors else None
            apps_above_5pct = sum(1 for err in app_errors if err > 5.0) if app_errors else 0
            total_apps = len(app_errors) if app_errors else 0

            iteration_data.append({
                'Base_Experiment': result['base_name'],
                'Iteration': iteration,
                'Mode': mode,
                'Speedup': speedup,
                'Events_Skipped_Pct': events_skipped_pct,
                'Theoretical_Speedup': theoretical_speedup,
                'Efficiency': efficiency,
                'Min_Error_Pct': min_error,
                'Max_Error_Pct': max_error,
                'Apps_Above_5pct': apps_above_5pct,
                'Total_Apps': total_apps
            })

    return iteration_data

def generate_raw_data_csv(iteration_results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Generate raw data for CSV export including runtimes and net events"""
    raw_data = []

    for result in iteration_results:
        base_name = result['base_name']
        iteration = result['iteration']

        # Process all modes including high-fidelity
        for mode in ['high-fidelity'] + SURROGATE_MODES:
            if mode not in result['data']:
                continue

            mode_data = result['data'][mode]

            # Add simulation runtime data
            raw_data.append({
                'Base_Experiment': base_name,
                'Iteration': iteration,
                'Mode': mode,
                'Data_Type': 'simulation_runtime',
                'Value': mode_data['runtime'],
                'Unit': 'seconds'
            })

            # Add net events data
            raw_data.append({
                'Base_Experiment': base_name,
                'Iteration': iteration,
                'Mode': mode,
                'Data_Type': 'net_events_processed',
                'Value': mode_data['net_events'],
                'Unit': 'events'
            })

            # Add application completion times
            for app_id, app_time in mode_data['app_times'].items():
                raw_data.append({
                    'Base_Experiment': base_name,
                    'Iteration': iteration,
                    'Mode': mode,
                    'Data_Type': f'app_{app_id}_completion_time',
                    'Value': app_time,
                    'Unit': 'nanoseconds'
                })

    return raw_data

def display_iteration_analysis(iteration_data: list[dict[str, Any]]) -> None:
    """Display iteration analysis results"""
    if not iteration_data:
        print("No iteration data to display")
        return

    # Group by base experiment
    base_experiments = {}
    for row in iteration_data:
        base_name = row['Base_Experiment']
        if base_name not in base_experiments:
            base_experiments[base_name] = []
        base_experiments[base_name].append(row)

    for base_name, rows in base_experiments.items():
        print(f"\nITERATION ANALYSIS SUMMARY")
        print("=" * 100)
        print(f"Base Experiment: {base_name}")
        print()
        print(f"{'Iteration':<10} {'Mode':<25} {'Speedup':<8} {'Skipped%':<9} {'Theoretical':<11} {'Efficiency':<10} {'Error Range%':<15} {'Apps>5%':<8}")
        print("-" * 100)

        # Sort by iteration, then by high-fidelity first, then surrogate modes
        def sort_key(row):
            iteration = row['Iteration']
            mode = row['Mode']
            if mode == 'high-fidelity':
                return (iteration, 0)
            else:
                return (iteration, 1, mode)

        sorted_rows = sorted(rows, key=sort_key)

        for row in sorted_rows:
            iteration_str = str(row['Iteration'])
            mode_str = row['Mode']
            speedup_str = f"{row['Speedup']:.2f}x" if row['Speedup'] else "N/A"
            skipped_str = f"{row['Events_Skipped_Pct']:.1f}%" if row['Events_Skipped_Pct'] is not None else "N/A"
            theoretical_str = f"{row['Theoretical_Speedup']:.2f}x" if row['Theoretical_Speedup'] else "N/A"
            efficiency_str = f"{row['Efficiency']:.3f}" if row['Efficiency'] is not None else "N/A"

            if row['Min_Error_Pct'] is not None and row['Max_Error_Pct'] is not None:
                error_range_str = f"{row['Min_Error_Pct']:.1f}% - {row['Max_Error_Pct']:.1f}%"
            else:
                error_range_str = "N/A"

            apps_str = f"{row['Apps_Above_5pct']}/{row['Total_Apps']}" if row['Apps_Above_5pct'] is not None else "N/A"

            print(f"{iteration_str:<10} {mode_str:<25} {speedup_str:<8} {skipped_str:<9} {theoretical_str:<11} {efficiency_str:<10} {error_range_str:<15} {apps_str:<8}")

        # Add footnotes
        print("\n" + "=" * 100)
        print("Notes:")
        print("  * Theoretical Speedup = 1 / (1 - Events Skipped%) = Maximum possible speedup from event reduction alone")
        print("  * Efficiency = Actual Speedup / Theoretical Speedup = How well the mode utilizes event reduction potential")
        print("  * Efficiency < 1.0 indicates overhead from communication, memory access, or other bottlenecks")

def main_experiments_results(base_path: Path, saveas: Path | None = None) -> None:
    print("Analyzing CODES experiment results")
    print("=" * 50)

    # Load job info from metadata file
    job_info = load_experiment_metadata(base_path)

    # Extract all data
    results = analyze_all_experiments(base_path, job_info)

    # Calculate speedups and errors
    speedup_data, error_data, dashboard_data = calculate_speedups_and_errors(results)

    # Create DataFrames
    speedup_df = pd.DataFrame(speedup_data)
    error_df = pd.DataFrame(error_data)
    dashboard_df = pd.DataFrame(dashboard_data)

    # Display comprehensive dashboard first
    print("\nSIMULATION PERFORMANCE SUMMARY")
    print("=" * 100)
    if not dashboard_df.empty:
        # Format the dashboard display with grouped experiments
        print(f"{'Mode':<25} {'Speedup':<8} {'Skipped%':<9} {'Theoretical':<11} {'Efficiency':<10} {'Error Range%':<15} {'Apps>5%':<8}")
        print("-" * 100)

        # Group by experiment
        current_exp = ""
        for _, row in dashboard_df.iterrows():
            if row['Experiment'] != current_exp:
                current_exp = row['Experiment']
                print(f"\n{current_exp}")

            speedup_str = f"{row['Speedup']:.2f}x" if row['Speedup'] else "N/A"
            skipped_str = f"{row['Events_Skipped_Pct']:.1f}%" if row['Events_Skipped_Pct'] is not None else "N/A"
            theoretical_str = f"{row['Theoretical_Speedup']:.2f}x" if row['Theoretical_Speedup'] else "N/A"
            efficiency_str = f"{row['Efficiency']:.3f}" if row['Efficiency'] is not None else "N/A"
            error_range_str = f"{row['Min_Error_Pct']:.1f}% - {row['Max_Error_Pct']:.1f}%" if row['Min_Error_Pct'] is not None else "N/A"
            apps_str = f"{row['Apps_Above_5pct']}/{row['Total_Apps']}" if row['Apps_Above_5pct'] is not None else "N/A"

            print(f"  {row['Mode']:<23} {speedup_str:<8} {skipped_str:<9} {theoretical_str:<11} {efficiency_str:<10} {error_range_str:<15} {apps_str:<8}")

        # Add footnotes
        print("\n" + "=" * 100)
        print("Notes:")
        print("  * Theoretical Speedup = 1 / (1 - Events Skipped%) = Maximum possible speedup from event reduction alone")
        print("  * Efficiency = Actual Speedup / Theoretical Speedup = How well the mode utilizes event reduction potential")
        print("  * Efficiency < 1.0 indicates overhead from communication, memory access, or other bottlenecks")
    else:
        print("No dashboard data available")

    print("\nAPPLICATION COMPLETION TIME ERRORS")
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
    if saveas:
        print(f"\nSAVING DETAILED RESULTS")
        print("=" * 50)

        speedup_df.to_csv(f'{saveas}_speedup_results.csv', index=False)
        error_df.to_csv(f'{saveas}_error_results.csv', index=False)
        dashboard_df.to_csv(f'{saveas}_dashboard_results.csv', index=False)

        print("Saved detailed results to:")
        print(f"  - {saveas}_speedup_results.csv")
        print(f"  - {saveas}_error_results.csv")
        print(f"  - {saveas}_dashboard_results.csv")

    # Summary statistics
    print(f"\nSUMMARY STATISTICS")
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

def main_iteration_analysis(base_path: Path, saveas: Path | None = None) -> None:
    """Main function for iteration analysis"""
    print("Analyzing CODES iteration experiments")
    print("=" * 50)

    # Load job information
    job_info = load_experiment_metadata(base_path)

    # Analyze iteration experiments
    results_by_base = analyze_iteration_experiments(base_path, job_info)

    if not results_by_base:
        print("No iteration experiments found!")
        print("Make sure experiment directories follow the pattern: experiment_name_iter=X")
        return

    # Process each base experiment
    for base_name, iteration_results in results_by_base.items():
        print(f"\nProcessing base experiment: {base_name}")

        # Calculate iteration metrics
        iteration_data = calculate_iteration_metrics(iteration_results)

        # Display results
        display_iteration_analysis(iteration_data)

        # Save to CSV if requested
        if saveas and iteration_data:
            import pandas as pd

            # Save iteration analysis
            df = pd.DataFrame(iteration_data)
            analysis_filename = f"{saveas}_iteration_analysis_{base_name}.csv"
            df.to_csv(analysis_filename, index=False)
            print(f"\nIteration analysis saved to {analysis_filename}")

            # Generate and save raw data
            raw_data = generate_raw_data_csv(iteration_results)
            if raw_data:
                raw_df = pd.DataFrame(raw_data)
                raw_filename = f"{saveas}_raw_data_{base_name}.csv"
                raw_df.to_csv(raw_filename, index=False)
                print(f"Raw data saved to {raw_filename}")

    print(f"\nAnalyzed {len(results_by_base)} base experiment(s) with iteration variants")

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Analyze CODES experiment results")
    parser.add_argument("path", nargs="?", default="results/exp-225-ghc-iter=2/",
                        help="Path to experiment results directory")
    parser.add_argument("--iteration-analysis", action="store_true",
                        help="Analyze experiments with different iteration counts")
    parser.add_argument("--save-as", type=Path, default=None,
                        help="Save results to CSV files with given prefix (e.g., --saveas experiments-3)")

    args = parser.parse_args()
    base_path = Path(args.path)

    if args.iteration_analysis:
        main_iteration_analysis(base_path, args.saveas)
    else:
        main_experiments_results(base_path, args.saveas)
