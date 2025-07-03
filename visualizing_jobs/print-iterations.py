# Adapted from example from matplotlib lib

import glob
from typing import Any, TextIO
import argparse
import pathlib
import colorsys
from collections import defaultdict
import os
import csv

import matplotlib.pyplot as plt
import matplotlib
from matplotlib.patches import Rectangle
from matplotlib.lines import Line2D
import numpy as np
import matplotlib.colors as mc


def adjust_lightness(color: str | tuple[float, float, float], amount: float = 0.5):
    """
    Taken from: https://stackoverflow.com/a/49601444
    Smaller than 1 amounts darkness, larger than 1 lightens
    Examples:
    >> adjust_lightness('g', 1.3)
    >> adjust_lightness('#F034A3', 0.6)
    >> adjust_lightness((.3,.55,.1), 1.5)
    """
    try:
        c = mc.cnames[color]  # type: ignore[reportArgumentType]
    except:
        c = color
    c = colorsys.rgb_to_hls(*mc.to_rgb(c))
    return colorsys.hls_to_rgb(c[0], max(0, min(1, amount * c[1])), c[2])


def plot_sequence(
        ax: Any,
        job_data: Any,
        color: str = 'red',
        print_names: bool = True,
        shade_iter_before_jump: bool = False,
):
    seq = job_data['time']
    names = job_data['iter']
    height = job_data['iter_time']
    skipped = job_data['skipped']

    assert(len(seq) == len(height) == len(names))
    n = len(seq)
    box_sequence = [(0, seq[0], height[0], skipped[0])]
    box_sequence.extend(zip(seq, height[1:], height[1:], skipped[1:]))
    for i, (start, width, heit, skip) in enumerate(box_sequence):
        if skip:
            assert heit == 0
            continue
        is_box_before_jump = shade_iter_before_jump and i < n - 1 and skipped[i+1]
        lightness = 1.9 if is_box_before_jump else 1.5
        box = Rectangle((start, 0), width, heit, color=adjust_lightness(color, lightness))
        ax.add_patch(box)

    cleaned_seq = list(seq[~ skipped])
    cleaned_height = list(height[~ skipped])
    cleaned_names = list(names[~ skipped])

    if skipped[-1]:
        cleaned_seq.append(seq[-1])
        cleaned_height.append(mean_after_last_jump(height, shade_iter_before_jump))
        cleaned_names.append(names[-1])
    # ax.plot(seq, np.zeros_like(seq), "-o", color="k", markerfacecolor="w")

    ax.scatter(cleaned_seq[:-1], cleaned_height[:-1], marker='.', color=color)
    ax.scatter(cleaned_seq[-1], cleaned_height[-1], marker='^', color=color)
    ax.vlines(cleaned_seq, 0, cleaned_height, color=adjust_lightness(color, 1.3))

    # annotate lines
    if print_names:
        for d, h, r in zip(cleaned_seq, cleaned_height, cleaned_names):
            ax.annotate(r, xy=(d, h),
                        xytext=(3, np.sign(h)*3), textcoords="offset points",
                        horizontalalignment="right",
                        verticalalignment="bottom" if h > 0 else "top")


def mean_after_last_jump(height: np.ndarray, ignore_last_before_if_jump: bool) -> float:
    indices = np.nonzero(height == 0)[0]
    n = len(height)
    if height[-1] == 0:
        assert(indices[-1] == n - 1)
        last = n - 2 if ignore_last_before_if_jump else n - 1
        first = indices[-2] + 1 if len(indices) > 1 else 0
    else:
        last = n
        first = indices[-1] + 1 if indices else 0

    return float(height[first: last].mean())


def find_suspended_timestamps(log_file: TextIO) -> dict[int, list[float]]:
    susp_pattern = r' SUSPENDED node \d+ job (\d+) rank \d+ until time (\d*\.?\d+)'
    susp_iters = np.fromregex(log_file, susp_pattern, [('job', np.int64), ('time', np.float64)])
    susp_iters = np.unique(susp_iters)

    restarted_at: dict[int, list[float]] = defaultdict(list)
    for job, time in susp_iters:
        restarted_at[int(job)].append(float(time))

    return restarted_at


def correct_time_due_suspension(job_info: Any, restarted_at: list[float]):
    for rstr in restarted_at:
        indices, = np.where(np.bitwise_not(job_info['time'] <= rstr))
        # suspension must've happened before the end of the simulation
        if indices.size > 0:
            rstr_ind = indices[0]
            assert rstr_ind > 0, "The job cannot be suspended before it started running"
            offset = rstr - job_info['time'][rstr_ind-1]
            #job_info['time'][rstr_ind] += rstr
            job_info['iter_time'][rstr_ind] -= offset


# typing cannot be done for structured arrays :S
def parse_iteration_log(log_file_path: pathlib.Path):
    if log_file_path.is_dir():
        log_file_names = [pathlib.Path(log_path) for log_path in glob.glob(str(log_file_path / "pe=*.txt"))]
    else:
        log_file_names = [log_file_path]

    log_pattern = r'((?:SKIPPED TO |))ITERATION (\d+) node \d+ job (\d+) rank \d+ time (\d*\.?\d+)\n'
    #log_pattern = r' MARK_(\d+) node \d+ job (\d+) rank \d+ time (\d*\.?\d+)'
    log_iters_list = []
    restarted_at: dict[int, list[float]] = defaultdict(list)
    for log_file_name in log_file_names:
        log_file = log_file_name.open('r')
        log_iters_one = np.fromregex(log_file, log_pattern, [('skipped', '?'), ('iter', np.int64), ('job', np.int64), ('time', np.float64)])
        log_iters_list.append(log_iters_one)

        _ = log_file.seek(0)
        restarted_at |= find_suspended_timestamps(log_file)
    log_iters = np.concat(log_iters_list)

    def get_avg_for_iters(job: np.int64):
        def avg(it: np.int64) -> np.float64:
            matched_iters = log_iters[np.bitwise_and(log_iters['job'] == job, log_iters['iter'] == it)]
            return np.mean(matched_iters['time'].astype(np.float64))
        return avg

    jobs: dict[int, np.ndarray[Any, Any]] = {}
    for job in np.unique(log_iters['job']):
        iterations = np.unique(log_iters[log_iters['job'] == job]['iter'])
        # avg_timestamp = np.vectorize(get_avg_for_iters(job), otypes=(np.float64,))(iterations)
        avg_timestamp = np.array([get_avg_for_iters(job)(it) for it in iterations])
        assert(iterations.size == avg_timestamp.size)

        # finding time that each iteration took
        avg_iter_time = avg_timestamp.copy()
        avg_iter_time[1:] -= avg_timestamp[:-1]

        # "removing" iterations which were skipped!
        log_iters_job = log_iters[log_iters['job'] == job]
        skipped = np.array([np.any(log_iters_job[log_iters_job['iter'] == it]['skipped']) for it in iterations])

        # fallback algorithm to detect skipped iterations
        to_rem = iterations.copy()
        to_rem[1:] -= to_rem[:-1] + 1  # with this we find a gap in the data, anything that is not ONE iteration apart is considered to have been skipped
        to_rem[0] = 0  # Assuming the first value hasn't been skipped
        skipped[to_rem != 0] = 1

        avg_iter_time[skipped] = 0

        combined = np.zeros_like(iterations, dtype=[('iter', np.int64), ('time', np.float64), ('iter_time', np.float64), ('skipped', np.bool_)])
        combined['iter'] = iterations
        combined['time'] = avg_timestamp
        combined['iter_time'] = avg_iter_time
        combined['skipped'] = skipped

        correct_time_due_suspension(combined, restarted_at[job])

        jobs[int(job)] = combined

    return jobs


def export_iteration_data_to_csv(parsed_logs: dict[int, Any], saveas: pathlib.Path, legends: list[str] | None = None) -> None:
    """Export iteration data to CSV files using native Python csv module"""

    # Create application name mapping
    app_names = {}
    if legends:
        for job_id in parsed_logs.keys():
            if job_id < len(legends):
                app_names[job_id] = legends[job_id]
            else:
                app_names[job_id] = f"App_{job_id}"
    else:
        for job_id in parsed_logs.keys():
            app_names[job_id] = f"App_{job_id}"

    # Export raw iteration data
    raw_filename = f"{saveas}_iteration_raw_data.csv"
    with open(raw_filename, 'w', newline='') as csvfile:
        writer = csv.writer(csvfile)

        # Write header
        writer.writerow(['Job_ID', 'Application_Name', 'Iteration', 'Cumulative_Time_ns', 'Iteration_Time_ns', 'Skipped'])

        # Write data for each job
        for job_id, job_data in parsed_logs.items():
            app_name = app_names[job_id]

            for i in range(len(job_data)):
                writer.writerow([
                    job_id,
                    app_name,
                    int(job_data['iter'][i]),
                    float(job_data['time'][i]),
                    float(job_data['iter_time'][i]),
                    bool(job_data['skipped'][i])
                ])

    # Export summary statistics
    summary_filename = f"{saveas}_iteration_summary.csv"
    with open(summary_filename, 'w', newline='') as csvfile:
        writer = csv.writer(csvfile)

        # Write header
        writer.writerow([
            'Job_ID', 'Application_Name', 'Total_Iterations', 'Skipped_Iterations',
            'Mean_Iteration_Time_ns', 'Std_Iteration_Time_ns', 'Total_Virtual_Time_ns',
            'Max_Iteration_Time_ns', 'Min_Iteration_Time_ns'
        ])

        # Calculate and write statistics for each job
        for job_id, job_data in parsed_logs.items():
            app_name = app_names[job_id]

            total_iterations = len(job_data)
            skipped_iterations = int(np.sum(job_data['skipped']))

            # Calculate statistics only on non-skipped iterations
            non_skipped_times = job_data['iter_time'][~job_data['skipped']]

            if len(non_skipped_times) > 0:
                mean_iter_time = float(np.mean(non_skipped_times))
                std_iter_time = float(np.std(non_skipped_times))
                max_iter_time = float(np.max(non_skipped_times))
                min_iter_time = float(np.min(non_skipped_times))
                total_virtual_time = float(np.sum(non_skipped_times))
            else:
                mean_iter_time = 0.0
                std_iter_time = 0.0
                max_iter_time = 0.0
                min_iter_time = 0.0
                total_virtual_time = 0.0

            writer.writerow([
                job_id,
                app_name,
                total_iterations,
                skipped_iterations,
                mean_iter_time,
                std_iter_time,
                total_virtual_time,
                max_iter_time,
                min_iter_time
            ])

    print(f"Iteration data exported to:")
    print(f"  - {raw_filename}")
    print(f"  - {summary_filename}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    _ = parser.add_argument('file', type=pathlib.Path)
    _ = parser.add_argument('--output', type=pathlib.Path, help='Name of output figure', default=None)
    _ = parser.add_argument('--save-as', type=pathlib.Path, default=None,
                            help='Save iteration data to CSV files with given prefix (e.g., --saveas experiment-1)')
    _ = parser.add_argument('--iter-count', dest='iter_count', action='store_true')
    _ = parser.add_argument('--legends', nargs='+', help='Application names', required=False)
    _ = parser.add_argument('--no-show-plot', dest='show_plot', action='store_false')
    _ = parser.add_argument('--start', type=float, help="Start of zoom in window (for plotting purposes, default=0)")
    _ = parser.add_argument('--end', type=float, help="End of zoom in window (for plotting purposes, default=end of simulation)")
    _ = parser.add_argument('--no-shade-jump', dest='shade_jump', action='store_false',
                            help='If a jump is detected (fast-forwarding) the last iteration before the jump is shaded differently')
    args = parser.parse_args()

    if args.output:
        matplotlib.use("pgf")
        matplotlib.rcParams.update({
            "pgf.texsystem": "pdflatex",
            'font.family': 'serif',
            'font.size': 16,
            'text.usetex': True,
            'pgf.rcfonts': False,
        })

    # Load either from .npz or from text file
    log_file_path, ext = os.path.splitext(args.file)
    if ext == '.npz':
        file_loaded = np.load(args.file)
        parsed_logs = {int(i): file_loaded[i] for i in file_loaded.files}
    else:
        parsed_logs = parse_iteration_log(args.file)
        with open(log_file_path + '.npz', 'wb') as outfile:
            np.savez(outfile, **{str(i): v for i, v in parsed_logs.items()})

    final_timestamp = float(max(job['time'].max() for job in parsed_logs.values()))
    print("Simulation end =", final_timestamp)

    # Export to CSV if requested
    if args.saveas:
        export_iteration_data_to_csv(parsed_logs, args.saveas, args.legends)

    if not args.show_plot:
        exit(0)

    # Creating plot with data
    fig, ax = plt.subplots(figsize=(10, 5), layout="constrained")
    _ = ax.set_xlabel("Total virtual time (ns)")
    _ = ax.set_ylabel("Virtual time \nper iteration (ns)")
    #ax.set(title="")

    # adjusting plot (to zoom in)
    end_of_simulation = max(v['time'].max() for v in parsed_logs.values())
    start = args.start if args.start else 0
    end = args.end if args.end else end_of_simulation
    if end > end_of_simulation:
        end_of_simulation = end
    _ = ax.plot([0, end_of_simulation], [0, 0], "-", color="k", markerfacecolor="w")

    padding = 0.05
    width_plot = end - start
    _ = ax.set_xlim(start - width_plot * padding, end + width_plot * padding)

    color_table = ['tab:red', 'tab:blue', 'tab:green', 'tab:black']
    assert all(job < len(color_table) for job in parsed_logs.keys())

    def key_jobs(job: int) -> float:
        iter_times = parsed_logs[job]['iter_time']
        non_zero_iter_times = iter_times[iter_times != 0]
        return float(non_zero_iter_times.mean())
    jobs_order_to_print = sorted(parsed_logs.keys(), key=key_jobs, reverse=True)

    for job in jobs_order_to_print:
        plot_sequence(
            ax,
            parsed_logs[job],
            color=color_table[job],
            print_names=args.iter_count,
            shade_iter_before_jump=args.shade_jump)

    _ = plt.setp(ax.get_xticklabels(), rotation=30, ha="right")

    if args.legends:
        custom_lines = []
        legends = []
        for legend, color in zip(args.legends, color_table):
            # Finding legend for application with ID i
            legend: str
            legends.append(legend)
            custom_lines.append(Line2D([0], [0], color=color))
        _ = ax.legend(custom_lines, legends)

    #ax.margins(y=0.1)
    if args.output:
        plt.tight_layout()
        plt.savefig(f'{args.output}.pgf', bbox_inches='tight')
        plt.savefig(f'{args.output}.pdf', bbox_inches='tight')
    else:
        plt.show()
