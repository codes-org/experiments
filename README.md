# CODES Experiments

This repository contains experimental configurations and scripts for network simulation using the [CODES discrete-event simulation framework](https://github.com/codes-org/codes).

## Structure

- **`dfly-1056/`** - Dragonfly topology experiments with 1,056 nodes
- **`dfly-72/`** - Dragonfly topology experiments with 72 nodes  
- **`dfly-8448/`** - Dragonfly topology experiments with 8,448 nodes
- **`torus-64/`** - Torus topology experiments with 64 nodes

Each experiment directory contains:
- `conf/` - Configuration files for network topology and simulation parameters
- `results/` - Output from simulation runs (logs, statistics, performance data)
- Shell scripts for running experiments with specific parameters

## Usage

Run experiments using the provided script (it assumes you have compiled CODES using the `CODES-compile-instructions.sh` script and have downloaded this repo under the same directory that script recides):

```bash
bash run-experiment.sh path-to-experiment/script.sh
```

Results are automatically stored in `path-to-experiment/results/`.

## Dependencies

Requires the [CODES simulation framework](https://github.com/codes-org/codes) to be built and configured.
