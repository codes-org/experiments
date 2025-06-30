# Instructions to run experiments

- Install Python 3 > 3.13
- Run `run_mpi_surrogacy_experiments.py`
- Generate figures with

```bash
python ../visualizing_jobs/print-iterations.py results/exp-XXX/dfly-8448-01-jacobi1400-milc1200-milc3500-ur700/high-fidelity/iteration-logs --legend Jacobi3D MILC MILC --end 139e6 --output figures/large-jacobi-milc-good
python ../visualizing_jobs/print-iterations.py results/exp-XXX/dfly-8448-01-jacobi1400-milc1200-milc3500-ur700/app-and-network-freezing/iteration-logs --legend Jacobi3D MILC MILC --end 139e6 --output figures/large-jacobi-milc-good-surrogate
python ../visualizing_jobs/print-iterations.py results/exp-XXX/dfly-8448-01-jacobi1400-milc1200-milc3500-ur700/high-fidelity/iteration-logs --legend Jacobi3D MILC MILC --start 55e6 --end 120e6 --output figures/large-jacobi-milc-good-zoomed-in
python ../visualizing_jobs/print-iterations.py results/exp-XXX/dfly-8448-02-jacobi1400-jacobi2800-milc4200/high-fidelity/iteration-logs --legend Jacobi3D Jacobi3D MILC --end 826e6 --output figures/large-jacobi-jacobi-milc-bad
python ../visualizing_jobs/print-iterations.py results/exp-XXX/dfly-8448-02-jacobi1400-jacobi2800-milc4200/app-surrogate/iteration-logs --legend Jacobi3D Jacobi3D MILC --end 826e6 --output figures/large-jacobi-jacobi-milc-bad-surrogate
python ../visualizing_jobs/print-iterations.py results/exp-XXX/dfly-8448-02-jacobi1400-jacobi2800-milc4200_iter=10/app-surrogate/iteration-logs --legend Jacobi3D Jacobi3D MILC --end 84e6 --output figures/large-jacobi-jacobi-milc-bad-zoomed-in
```
