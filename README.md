# CODES Experiments

This repository contains scripts for network simulation using the [CODES discrete-event simulation framework](https://github.com/codes-org/codes). Specifically, all scripts here run the binary `model-net-mpi-replay` which simulates the behaviour of one or multiple jobs running on an HPC network.

## Structure

- **`individual-scripts/`** - scripts to run one experiment at the time
- **`mpi_replay/`** - Python 3.13 script to run a battery of tests
- **`visualizing_jobs/`** - Visualizes each iteration time for all jobs in an experiment

Each experiment directory contains:

- `conf/` - Configuration files for network topology and simulation parameters
- `results/` - Output from simulation runs (logs, statistics, performance data)
- A python or shell script to run experiments with specific parameters

Feel free to copy individual scripts (or their entire subdirectory) and modify them to run new scenarios. Within `mpi_replay/`, you should be able to make a copy of `run_mpi_surrogacy_experiments.py` to run a series of experiments.

### Individual scripts structure

- **`individual-scripts/dfly-1056/`** - Dragonfly topology experiments with 1,056 nodes
- **`individual-scripts/dfly-72/`** - Dragonfly topology experiments with 72 nodes  
- **`individual-scripts/dfly-8448/`** - Dragonfly topology experiments with 8,448 nodes
- **`individual-scripts/torus-64/`** - Torus topology experiments with 64 nodes

### Visualize iterations by multiple jobs

Once you have got some results, you can run

## Usage

Run experiments using the provided script (it assumes you have compiled CODES using the `CODES-compile-instructions.sh` script and have downloaded this repo under the same directory that script resides. Please check the script `CODES-compile-instructions.sh` at <https://github.com/codes-org/codes>):

```bash
bash run-experiment.sh path-to-experiment/script.sh
# or in the case of mpi_replay
bash run-experiment.sh mpi_replay/run_mpi_surrogacy_experiments.py
# or in case you want to pass arguments to your experiment script, you can simply
bash run-experiment.sh path-to-experiment/script.sh --argument some-file.txt --other-arg
```

Results are automatically stored in `path-to-experiment/results/`.

In case you want to run an experiment with `sbatch`, you can use the script `run-sbatch.sh` instead of `run-experiment.sh`. The `run-sbatch.sh` script will run the experiments in a different folder to that of the script. This is because in systems where sbatch is needed, one often stores data in a different folder than the folder one is running the script. Under this new folder, the script will create a `results/` subfolder just as `run-experiment.sh` does.

## Dependencies

Requires the [CODES simulation framework](https://github.com/codes-org/codes) to be built and configured. It currently works with commit version @73cdbd5 of CODES.
