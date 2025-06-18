#!/usr/bin/bash

np=1

expfolder="$PWD"
export CONFIGS_PATH="$PATH_TO_SCRIPT_DIR/conf"

# Backing up and copying milc json!
tmpdir="$(TMPDIR="$PWD" mktemp -d)"
mv "$PATH_TO_SWM_INSTALL/share/milc_skeleton.json" "$tmpdir/milc_skeleton.json"
cp "$CONFIGS_PATH/milc_skeleton.json" "$PATH_TO_SWM_INSTALL/share/milc_skeleton.json"

# Copying configuration files to keep as documentation
cp "$CONFIGS_PATH/milc_skeleton.json" "$expfolder"
cp "$CONFIGS_PATH/milc.workload.conf" "$expfolder"
cp "$CONFIGS_PATH/milc-continuous-36-ranks.alloc.conf" "$expfolder"

# CODES config file
export PATH_TO_CONNECTIONS="$CONFIGS_PATH"
envsubst < "$CONFIGS_PATH/dfdally-72-par.conf.in" > "$expfolder/dfdally-72-par.conf"

# running simulation
lookahead=200

#gdb --args "$PATH_TO_CODES_BUILD"/src/model-net-mpi-replay \
mpirun -np $np "$PATH_TO_CODES_BUILD"/src/model-net-mpi-replay \
  --synch=3 --extramem=100000 \
  --cons-lookahead=$lookahead --max-opt-lookahead=$lookahead \
  --batch=4 --gvt-interval=256 \
  --workload_type=conc-online \
  --lp-io-dir=lp-io-dir \
  --workload_conf_file="$expfolder"/milc.workload.conf \
  --alloc_file="$expfolder"/milc-continuous-36-ranks.alloc.conf \
  -- \
  "$expfolder/dfdally-72-par.conf" \
    > model-output.txt 2> model-output-error.txt

# Setting milc json back
mv "$tmpdir/milc_skeleton.json" "$PATH_TO_SWM_INSTALL/share/milc_skeleton.json"
rmdir "$tmpdir"
