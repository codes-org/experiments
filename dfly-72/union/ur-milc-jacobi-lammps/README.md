# Selected Stress Test Experiments

8 most effective stress tests for challenging surrogate prediction accuracy:

1. bandwidth-saturation

Goal: Test surrogate accuracy at maximum network utilization

- UR: 8 nodes, period=726.609003 ns (100% bandwidth saturation)
- Jacobi: 20 nodes, 150 iters, 80KB msgs, layout=4×5×1, 200μs compute (balanced compute/comm)
- MILC: 22 nodes, 100 iters, 400KB msgs, layout=2×11×1×1, 50μs compute (communication-heavy)
- LAMMPS: 22 nodes, 8000 steps, 2×11×1 replicas

Challenge: Surrogate must predict under maximum congestion

2. micro-vs-macro-timing

Goal: Extreme iteration time variability to stress temporal prediction

- UR: 6 nodes, period=1200 ns (60% bandwidth)
- Jacobi: 24 nodes, 15 iters, 200KB msgs, layout=6×2×2 (fast finish), 10μs compute (very communication-heavy, finishes fast)
- MILC: 24 nodes, 800 iters, 150KB msgs, layout=3×2×2×2 (very slow), 500μs compute (computation-heavy, runs long)
- LAMMPS: 18 nodes, 40000 steps, 3×3×2 replicas (extremely slow)

Challenge: 53× iteration ratio tests surrogate's temporal scaling

3. cascade-failure-pattern

Goal: Sequential app completion creating shifting network conditions

- UR: 4 nodes, period=1000 ns (70% bandwidth)
- Jacobi: 16 nodes, 50 iters, 60KB msgs, layout=4×2×2 (finish ~1 min)
- MILC: 20 nodes, 200 iters, 300KB msgs, layout=4×5×1×1 (finish ~3 min),  50μs compute (fast finish)
- LAMMPS: 32 nodes, 25000 steps, 4×4×2 replicas (finish ~6 min), 200μs compute (medium finish)

Challenge: Network conditions change as apps complete

4. resource-starvation

Goal: Extreme asymmetric allocation testing resource contention

- UR: 12 nodes, period=900 ns (80% bandwidth)
- Jacobi: 4 nodes, 300 iters, 120KB msgs, layout=2×2×1 (starved), 800μs compute (high compute to offset starvation)
- MILC: 52 nodes, 120 iters, 600KB msgs, layout=13×2×2×1 (dominant), 100μs compute (balanced)
- LAMMPS: 4 nodes, 15000 steps, 2×2×1 replicas (starved)

Challenge: 13:1 node ratio creates extreme resource imbalance

5. bursty-communication-chaos

Goal: Extreme message size variation testing bandwidth prediction

- UR: 8 nodes, period=800 ns (90% bandwidth)
- Jacobi: 28 nodes, 400 iters, 20KB msgs, layout=7×2×2 (tiny msgs, frequent), 5μs compute (minimal - pure communication)
- MILC: 20 nodes, 80 iters, 1MB msgs, layout=4×5×1×1 (huge msgs, rare), 1000μs compute (high compute - rare but heavy communication)
- LAMMPS: 16 nodes, 12000 steps, 4×2×2 replicas (medium)

Challenge: 50:1 message size ratio tests bandwidth modeling

6. geometric-routing-stress

Goal: Spatial layouts forcing complex routing patterns

- UR: 6 nodes, period=1100 ns (65% bandwidth)
- Jacobi: 24 nodes, 200 iters, 100KB msgs, layout=12×2×1 (flat, max hops), 300μs compute (computation-heavy)
- MILC: 24 nodes, 150 iters, 350KB msgs, layout=2×2×2×3 (cubic, min hops), 150μs compute (balanced)
- LAMMPS: 18 nodes, 10000 steps, 9×2×1 replicas (linear)

Challenge: Different geometric patterns stress routing prediction

7. endurance-marathon

Goal: Long simulation testing surrogate drift and stability

- UR: 8 nodes, period=1000 ns (70% bandwidth)
- Jacobi: 20 nodes, 2000 iters, 60KB msgs, layout=5×2×2, 400μs compute (sustained computation)
- MILC: 24 nodes, 500 iters, 400KB msgs, layout=3×2×2×2, 300μs compute (sustained computation)
- LAMMPS: 20 nodes, 60000 steps, 4×5×1 replicas

Challenge: Long runtime tests surrogate prediction drift

8. application-interference

Goal: Apps designed to maximally interfere with each other

- UR: 10 nodes, period=850 ns (85% bandwidth)
- Jacobi: 21 nodes, 600 iters, 80KB msgs, layout=7×3×1 (sustained load), 100μs compute (communication-focused)
- MILC: 21 nodes, 300 iters, 500KB msgs, layout=7×3×1×1 (same topology!), 100μs compute (same ratio - creates interference)
- LAMMPS: 20 nodes, 18000 steps, 4×5×1 replicas (overlapping)

Challenge: Competing apps on similar topologies create interference

## Compute Delay Design Rationale

- Range: 5μs - 1000μs (200× variation)
- Communication-Heavy (5-50μs): Apps spend most time in network communication
- Balanced (100-300μs): Realistic mix of computation and communication
- Computation-Heavy (400-1000μs): Apps spend significant time computing

This creates diverse computation vs communication ratios that will:

1. Test temporal prediction accuracy across different app behaviors
2. Create realistic interference patterns between apps
3. Challenge surrogate models to handle varied timing patterns
4. Validate surrogate robustness across the computation/communication spectrum

The compute delays will make apps behave more like real HPC applications where computation and communication phases are balanced differently, providing much more challenging scenarios for surrogate prediction accuracy.

## Key Stress Testing Features

- Iteration Variability: 15-2000 iterations (133× range)
- Message Size Range: 20KB-1MB (50× range)
- Node Allocation: 4-52 nodes (13× range)
- Network Stress: 60-100% bandwidth utilization
- Temporal Patterns: Sequential, parallel, and overlapping completion
- Spatial Patterns: Linear, flat, cubic, and competing geometries

These experiments will reveal surrogate breaking points across bandwidth saturation, temporal prediction, resource contention, and application interference scenarios.
