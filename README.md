# rfa-tsp <!-- omit from toc -->

[![Python 3.11 | 3.12 | 3.13 | 3.14 | 3.15](https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13%20%7C%203.14%20%7C%203.15-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Dependency Security Audit](https://github.com/rsnitsch/rfa-tsp/actions/workflows/pip-audit.yml/badge.svg)](https://github.com/rsnitsch/rfa-tsp/actions/workflows/pip-audit.yml)
[![Tests](https://github.com/rsnitsch/rfa-tsp/actions/workflows/test.yml/badge.svg)](https://github.com/rsnitsch/rfa-tsp/actions/workflows/test.yml)
[![uv](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json)](https://github.com/astral-sh/uv)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

The **recursive-fold-algorithm** (RFA) is a recursive heuristic for the **travelling salesman problem** (TSP). While the
folding concept generalizes to any metric TSP, this implementation and the analyses below focus on the **2D Euclidean
TSP**, where geometric coordinates enable $O(n)$ expected runtime and $O(n)$ memory usage.

Recursive algorithms naturally split a problem into a series of smaller steps that are easier to solve individually. As
such, they're often very elegant.

## Contents <!-- omit from toc -->

- [Visualization](#visualization)
- [Concept](#concept)
  - [Folding strategies](#folding-strategies)
  - [Unfolding strategies](#unfolding-strategies)
- [Results](#results)
  - [Default configuration (with local 2-opt)](#default-configuration-with-local-2-opt)
  - [Pure RFA (without local 2-opt)](#pure-rfa-without-local-2-opt)
  - [Discussion](#discussion)
- [Algorithmic properties](#algorithmic-properties)
  - [Seed sensitivity](#seed-sensitivity)
    - [Key observations](#key-observations)
  - [Time complexity](#time-complexity)
    - [Empirical scaling](#empirical-scaling)
    - [Algorithmic analysis](#algorithmic-analysis)
  - [Memory complexity](#memory-complexity)
- [Usage](#usage)
  - [Processing a single TSPLIB instance](#processing-a-single-tsplib-instance)
  - [Processing a random TSP instance](#processing-a-random-tsp-instance)
  - [Visualizing the steps of the algorithm](#visualizing-the-steps-of-the-algorithm)
  - [Benchmarking](#benchmarking)
- [License](#license)

## Visualization

This is how the RFA finds a route for the TSPLIB problem `pr76`:

<img src="docs/rfa-tsp_tsplib_pr76.gif" alt="Step-by-step animation of RFA processing the pr76 instance" width="500">

<details>
<summary>Show command that was used to generate the above animation</summary>

Note: Version 1.0.0 was used.

```console
❯ uv run rfa-tsp tsplib:pr76 --seed 16 --export docs/rfa-tsp_tsplib_pr76.gif --export-fps 2-6
INFO | Instance:           tsplib:pr76 (76 nodes)
INFO | Folding strategy:   breadth-first
INFO | Unfolding strategy: breadth-first-2opt
INFO | Post-uncross:       False
INFO | Seed:               16
INFO | Total length:       109335
INFO | Optimal route:      108159 (overhead of RFA route: +1.09%)
INFO | Runtime:            0.021s
INFO | Exporting 148 unique frames to docs\rfa-tsp_tsplib_pr76.gif (fps=2-6, dpi=120)...
INFO | Export finished: docs\rfa-tsp_tsplib_pr76.gif
```

</details>

## Concept

RFA exploits the fact that the TSP can be trivially solved if there are only 3 nodes, because only a single round trip
route exists for 3 nodes. The solution, a triangle, is self-evident:

<img src="docs/rfa-tsp_concept_02_anchor_clean.png" alt="Self-evident triangle solution for 3 nodes" width="500">

This **trivial case** is the **recursion anchor** for the algorithm.

But how to deal with larger problem sizes? The answer is to **fold nodes**. Folding means that two nodes that are in
close proximity to each other are fused into an artificial new node. This new node gets placed in the middle between the
two original nodes and replaces them. By remembering the original nodes it is also possible to reverse such a folding
operation later on (referred to as **unfolding**). Of course, folded nodes can be folded again themselves (recursively).
These folding steps can be repeated until the problem size is reduced to a number of 3 nodes.

Let's consider the following TSP instance with 4 nodes:

<img src="docs/rfa-tsp_concept_00_init.png" alt="Initial TSP nodes" width="500">

We can pick a node and its nearest neighbor and fold them. The new node will be placed in the center and remember the
original nodes (the "children"):

<img src="docs/rfa-tsp_concept_01_fold.png"
alt="A node is folded with its nearest neighbor, creating a new node in the center"
width="500">

At this point, the number of nodes is reduced to 3. This is the trivial case and a preliminary route can be constructed.
The best route for 3 nodes is a simple triangle:

<img src="docs/rfa-tsp_concept_02_anchor.png"
alt="With only 3 nodes left, the trivial case (recursion anchor) is reached"
width="500">

Now we have to reverse the folding.

The key to RFA is that the nodes are now unfolded step by step. Each unfolding removes a node and replaces it with two
new nodes (the original child nodes from which the folded node was constructed). These new nodes can be inserted into
the preliminary route in two alternative orders only.

|              Bad choice (longer, intersecting)               |                     Good choice (shorter)                      |
| :----------------------------------------------------------: | :------------------------------------------------------------: |
| ![Bad choice](docs/rfa-tsp_concept_03_unfold_bad_choice.png) | ![Good choice](docs/rfa-tsp_concept_03_unfold_good_choice.png) |

It is trivial to calculate which option keeps the route shorter. Result:

<img src="docs/rfa-tsp_concept_03_unfold.png" alt="Result after unfolding" width="500">

The complete process can be described as follows:

- **Folding:** Pick a node and fold it with a neighboring node. Repeat folding nodes until the number of nodes has been
  reduced to 3.
- **Recursion anchor:** Create a preliminary round trip route through the 3 remaining nodes.
- **Unfolding:** Unfold the nodes until the original nodes have been restored. At each unfolding step, insert the new
  nodes in the preliminary route. Choose the insertion order that gives the shorter route length.

<!--
Images generated with:
uv run rfa-tsp random:default -n 4 -s 0 --export docs/rfa-tsp_concept.png
-->

### Folding strategies

- `breadth-first` (default up to v1.0): Randomly picks one of the least-folded nodes (minimum folding depth) and folds
  it with its nearest neighbor across all active nodes, keeping the folding tree balanced.
- `breadth-first-mutual-nn` (default since v1.1): Like `breadth-first`, processes the least-folded nodes first to keep
  the folding tree balanced, but preferentially folds mutual nearest-neighbor pairs (two nodes that are each other's
  nearest neighbor), avoiding asymmetric pairings.
- `random-nn`: A very simple yet highly efficient method which randomly picks a node and folds it with the
  nearest-neighbor.
- `outside-in`: The node furthest from the center point is folded with its nearest-neighbor. The center point is only
  calculated once at the beginning.

### Unfolding strategies

- `breadth-first`: The list of folded nodes is processed repeatedly. During each iteration, only the nodes with the
  maximum depth are unfolded.
- `breadth-first-2opt` (default): Same as `breadth-first`, but after each unfolding step, a local 2-opt optimization
  around the inserted nodes is performed.

## Results

The following benchmark results evaluate RFA across 18 instances from [TSPLIB95] (spanning 51 to 85,900 nodes, see
`TSPLIB/`). Both tables can be reproduced and updated in place via `uv run scripts/update_readme_benchmarks.py`.

### Default configuration (with local 2-opt)

<!-- BEGIN:RESULTS_DEFAULT -->

| Instance   | Optimal   | Mean RFA    | Mean vs. opt. | Std    | Mean runtime | Mean runtime per node |
| ---------- | --------- | ----------- | ------------- | ------ | ------------ | --------------------- |
| `a280`     | 2579      | 2861.3      | +10.95%       | ±1.64% | 0.015s       | 52.016µs              |
| `berlin52` | 7542      | 7734.0      | +2.55%        | ±0.00% | 0.003s       | 51.672µs              |
| `bier127`  | 118282    | 126238.7    | +6.73%        | ±0.97% | 0.007s       | 57.586µs              |
| `brd14051` | 469385    | 511500.8    | +8.97%        | ±0.24% | 0.836s       | 59.486µs              |
| `ch150`    | 6528      | 6897.9      | +5.67%        | ±1.39% | 0.008s       | 55.710µs              |
| `d18512`   | 645238    | 702524.2    | +8.88%        | ±0.11% | 1.100s       | 59.411µs              |
| `eil51`    | 426       | 452.8       | +6.30%        | ±0.38% | 0.003s       | 54.394µs              |
| `pla33810` | 66048945  | 75672270.0  | +14.57%       | ±0.18% | 1.849s       | 54.693µs              |
| `pla7397`  | 23260728  | 25807331.1  | +10.95%       | ±0.52% | 0.403s       | 54.436µs              |
| `pla85900` | 142382641 | 160903241.7 | +13.01%       | ±0.14% | 5.233s       | 60.922µs              |
| `pr1002`   | 259045    | 275593.9    | +6.39%        | ±0.66% | 0.061s       | 60.443µs              |
| `pr107`    | 44303     | 44665.2     | +0.82%        | ±0.37% | 0.006s       | 54.315µs              |
| `pr439`    | 107217    | 115302.3    | +7.54%        | ±1.24% | 0.026s       | 58.730µs              |
| `pr76`     | 108159    | 111907.8    | +3.47%        | ±0.60% | 0.004s       | 57.781µs              |
| `rat783`   | 8806      | 9538.8      | +8.32%        | ±0.47% | 0.043s       | 55.527µs              |
| `rat99`    | 1211      | 1292.3      | +6.71%        | ±2.58% | 0.005s       | 53.998µs              |
| `sw24978`  | 855597    | 934097.8    | +9.17%        | ±0.21% | 1.646s       | 65.905µs              |
| `usa13509` | 19982859  | 21806077.5  | +9.12%        | ±0.34% | 0.909s       | 67.287µs              |

**Summary statistics:**

| Metric                     | Value       |
| -------------------------- | ----------- |
| Min mean overhead          | **+0.82%**  |
| Mean overhead (arithmetic) | **+7.78%**  |
| Median mean overhead       | **+7.93%**  |
| Max mean overhead          | **+14.57%** |
| Mean runtime / trial       | **12.157s** |

**Details:**

- `rfa-tsp` version: `1.1.0`
- Folding strategy: `breadth-first-mutual-nn`
- Unfolding strategy: `breadth-first-2opt`
- Instances: 18/18
- Trials per instance: 30

<!-- END:RESULTS_DEFAULT -->

### Pure RFA (without local 2-opt)

To isolate the contribution of the recursive folding/unfolding hierarchy from the interleaved local 2-opt refinement,
the same benchmark is run with `--unfolding-strategy breadth-first`:

<details>
<summary>Show per-instance results for pure RFA (breadth-first unfolding)</summary>

<!-- BEGIN:RESULTS_PURE -->

| Instance   | Optimal   | Mean RFA    | Mean vs. opt. | Std    | Mean runtime | Mean runtime per node |
| ---------- | --------- | ----------- | ------------- | ------ | ------------ | --------------------- |
| `a280`     | 2579      | 3063.9      | +18.80%       | ±2.53% | 0.003s       | 11.526µs              |
| `berlin52` | 7542      | 8379.6      | +11.11%       | ±6.48% | 0.001s       | 13.422µs              |
| `bier127`  | 118282    | 131821.1    | +11.45%       | ±3.18% | 0.002s       | 15.210µs              |
| `brd14051` | 469385    | 547894.4    | +16.73%       | ±0.38% | 0.234s       | 16.675µs              |
| `ch150`    | 6528      | 7153.6      | +9.58%        | ±1.51% | 0.002s       | 13.381µs              |
| `d18512`   | 645238    | 752503.9    | +16.62%       | ±0.49% | 0.260s       | 14.057µs              |
| `eil51`    | 426       | 489.0       | +14.80%       | ±2.77% | 0.001s       | 16.952µs              |
| `pla33810` | 66048945  | 81360815.5  | +23.18%       | ±0.38% | 0.474s       | 14.019µs              |
| `pla7397`  | 23260728  | 27931777.0  | +20.08%       | ±0.70% | 0.113s       | 15.328µs              |
| `pla85900` | 142382641 | 173550880.1 | +21.89%       | ±0.21% | 1.562s       | 18.187µs              |
| `pr1002`   | 259045    | 303816.3    | +17.28%       | ±2.22% | 0.013s       | 13.369µs              |
| `pr107`    | 44303     | 45768.5     | +3.31%        | ±0.59% | 0.001s       | 12.859µs              |
| `pr439`    | 107217    | 125372.0    | +16.93%       | ±1.40% | 0.006s       | 13.508µs              |
| `pr76`     | 108159    | 119581.0    | +10.56%       | ±0.00% | 0.001s       | 13.190µs              |
| `rat783`   | 8806      | 10217.0     | +16.02%       | ±1.76% | 0.009s       | 11.338µs              |
| `rat99`    | 1211      | 1450.2      | +19.76%       | ±7.15% | 0.001s       | 13.170µs              |
| `sw24978`  | 855597    | 1011981.5   | +18.28%       | ±0.49% | 0.455s       | 18.199µs              |
| `usa13509` | 19982859  | 23872015.4  | +19.46%       | ±0.47% | 0.234s       | 17.321µs              |

**Summary statistics:**

| Metric                     | Value       |
| -------------------------- | ----------- |
| Min mean overhead          | **+3.31%**  |
| Mean overhead (arithmetic) | **+15.88%** |
| Median mean overhead       | **+16.83%** |
| Max mean overhead          | **+23.18%** |
| Mean runtime / trial       | **3.373s**  |

**Details:**

- `rfa-tsp` version: `1.1.0`
- Folding strategy: `breadth-first-mutual-nn`
- Unfolding strategy: `breadth-first`
- Instances: 18/18
- Trials per instance: 30

<!-- END:RESULTS_PURE -->

</details>

### Discussion

- **Pure RFA baseline:** Without any local search, pure recursive folding and unfolding achieves **+15.88%** mean
  overhead (median **+16.83%**) at ~11–18 µs per node — outperforming classic Nearest Neighbor (~23–26%) and matching
  Greedy / Multi-Fragment (~15–20%) while running in expected $O(n)$ time (`pla85900` in ~1.56 s in pure Python).
- **Impact of interleaved local 2-opt:** Adding a constant-size local 2-opt window (`radius=5`, $O(1)$ per step) during
  unfolding removes edge crossings early on coarse hierarchy levels before they accumulate. This more than halves the
  mean overhead (from **+15.88%** down to **+7.78%**) at roughly 3.6× the runtime (~52–67 µs per node), while keeping
  overall scaling linear.
- **Variance damping:** Interleaved local 2-opt also absorbs unfavorable tie-breaking decisions from the folding phase,
  substantially reducing seed variance on smaller instances (e.g., `berlin52` drops from ±6.48% to ±0.00%, `rat99` from
  ±7.15% to ±2.58%).

## Algorithmic properties

### Seed sensitivity

The `breadth-first-mutual-nn` (default), `breadth-first`, and `random-nn` folding strategies involve randomized
tie-breaking or node selection. Consequently, the quality of the resulting tour can depend on the RNG seed.

To quantify how strongly RFA depends on the seed across different problem sizes, we can evaluate multiple consecutive
seeds (`--trials`) and compare a small instance (`tsplib:pr76`) with large instances (`tsplib:pla7397`,
`tsplib:usa13509`):

| Instance          |  Nodes | Trials | Mean overhead | Std. dev. ($\sigma$) | Best overhead     |
| :---------------- | -----: | -----: | ------------: | -------------------: | :---------------- |
| `tsplib:pr76`     |     76 |  5,000 |        +3.65% |                0.52% | +2.74% (seed 0)   |
| `tsplib:pla7397`  |  7,397 |    300 |       +10.97% |                0.49% | +9.90% (seed 128) |
| `tsplib:usa13509` | 13,509 |    200 |        +9.16% |                0.30% | +8.38% (seed 5)   |

![Seed sensitivity for tsplib:usa13509](docs/rfa-tsp-seed-sensitivity_tsplib-usa13509.png)

<details>
<summary>Show plots for pla7397 and pr76</summary>

![Seed sensitivity for tsplib:pla7397](docs/rfa-tsp-seed-sensitivity_tsplib-pla7397.png)

![Seed sensitivity for tsplib:pr76](docs/rfa-tsp-seed-sensitivity_tsplib-pr76.png)

</details>

#### Key observations

- **Tight, symmetric distributions at scale:** On large instances (`pla7397`, `usa13509`), many local fallback and
  tie-breaking steps accumulate into a narrow, roughly symmetric bell curve ($\sigma = 0.30$% on `usa13509`).
- **High single-run reliability:** Because the variance is very low across all problem sizes, even a single RFA run
  produces a highly predictable result without severe bad-luck outliers. Multi-trial sweeps (`--trials`) offer only
  modest gains (~0.8–1.1 percentage points over the mean on large instances) and show rapid diminishing returns.
- **Near-determinism on small instances:** Because mutual nearest-neighbor pairs are geometrically well-defined,
  `breadth-first-mutual-nn` eliminates most of the randomness on small instances. Across 5,000 seeds on `pr76`, RFA
  collapses into just two discrete solutions (+2.74% and +3.95%), with the better one already found on seed 0.

<details>
<summary>Show commands used to generate the above plots</summary>

```console
uv run scripts/generate_seed_sensitivity_plots_for_readme.py
```

</details>

### Time complexity

#### Empirical scaling

Looking at the `Mean runtime per node` column in the [Results](#results) tables across TSPLIB instances spanning more
than three orders of magnitude in size (from 51 nodes in `eil51` to 85,900 nodes in `pla85900`) reveals a nearly
constant runtime per node — roughly **52–67 µs/node** with local 2-opt and **11–18 µs/node** without — closely matching
**linear $O(n)$ scaling** in practice.

#### Algorithmic analysis

Both phases perform exactly $n - 3$ steps:

- **Folding — expected $O(n)$, worst-case $O(n^2)$:** In each step, a node is folded with its nearest neighbor using a
  dynamic 2D spatial hash grid (`SpatialGrid`). Whenever the number of active nodes halves, the grid is rebuilt with
  coarser cells so that cell density stays roughly constant; across the entire run, all rebuilds sum to $O(n + n/2 +
  n/4 + \dots) = O(n)$. For reasonably distributed 2D point sets, each nearest-neighbor query inspects only a constant
  number of neighboring cells ($O(1)$ expected), yielding **$O(n)$ expected total time** for `breadth-first-mutual-nn`,
  `breadth-first` and `random-nn` (and $O(n \log n)$ for `outside-in` due to its max-heap).

  In the **worst case**, however, pathological point distributions (e.g., almost all nodes tightly clustered in a tiny
  area while a few distant outliers stretch the bounding box) cause many nodes to collapse into a single grid cell or
  force the ring search to scan many empty cells. Each nearest-neighbor query then degrades to $O(n)$, resulting in
  **$O(n^2)$ worst-case time**. This is a deliberate trade-off of using a lightweight spatial hash grid to support fast
  dynamic insertions and deletions at every folding step, rather than an inherent limitation of the RFA concept itself;
  density-adaptive structures such as an R-tree or quadtree handle skewed distributions more robustly in practice, but
  raise the expected time complexity from $O(n)$ to $O(n \log n)$.

- **Unfolding — strictly $O(n)$:** The tour is maintained as a circular doubly-linked structure (`nxt`/`prv`
  dictionaries), so replacing a folded node with its two children takes $O(1)$ time. With `breadth-first-2opt`, the
  local 2-opt refinement operates only on a fixed-size neighborhood window (`radius=5`, at most 12 nodes), which also
  runs in $O(1)$ per step. Thus, unfolding is **strictly $O(n)$** even in the worst case.

### Memory complexity

RFA has **strictly $O(n)$ space complexity** — even in the worst case — because Euclidean distances are computed on the
fly from node coordinates rather than stored in an $n \times n$ distance matrix:

- **Folding tree:** Exactly $n - 3$ folded nodes are created in addition to the $n$ original nodes, totaling $2n - 3$
  nodes.
- **Spatial hash grid (`SpatialGrid`):** Stores only the currently active nodes ($\le n$) and their cell assignments,
  using $O(n)$ space.
- **Tour representation:** The circular doubly-linked structure (`nxt`/`prv`) holds at most $n$ entries.

In contrast, algorithms that require a full distance matrix scale as $O(n^2)$ in memory — for `pla85900`
($n = 85{,}900$), a `float64` distance matrix alone would require ~59 GB of RAM, whereas RFA processes the instance with
a small linear memory footprint.

## Usage

This project uses `uv` as package and project manager. See: <https://docs.astral.sh/uv/>

### Processing a single TSPLIB instance

You can select a single TSPLIB instance from the `TSPLIB/` folder:

```console
❯ uv run rfa-tsp tsplib:a280
INFO     | rfa-tsp version:    1.1.0
INFO     | Timestamp:          2026-11-27 11:43:58
INFO     | Instance:           tsplib:a280 (280 nodes)
INFO     | Folding strategy:   breadth-first-mutual-nn
INFO     | Unfolding strategy: breadth-first-2opt
INFO     | Post-uncross:       False
INFO     | Weighted centroids: False
INFO     | Seed:               0
INFO     | Total length:       2860
INFO     | Optimal route:      2579 (overhead of RFA route: +10.90%)
INFO     | Runtime:            0.015s
INFO     | Runtime per node:   52.501µs
```

Results will vary slightly when you change the RNG seed:

```console
❯ uv run rfa-tsp tsplib:a280 --seed 1
...
INFO     | Seed:               1
INFO     | Total length:       2862
INFO     | Optimal route:      2579 (overhead of RFA route: +10.97%)
...
```

### Processing a random TSP instance

To process a randomly generated set of nodes:

```console
❯ uv run rfa-tsp random:your_seed --nodes 50
INFO     | rfa-tsp version:    1.1.0
INFO     | Timestamp:          2026-11-27 11:45:15
INFO     | Instance:           random:your_seed (50 nodes)
INFO     | Folding strategy:   breadth-first-mutual-nn
INFO     | Unfolding strategy: breadth-first-2opt
INFO     | Post-uncross:       False
INFO     | Weighted centroids: False
INFO     | Seed:               0
INFO     | Total length:       3197
INFO     | Runtime:            0.003s
INFO     | Runtime per node:   65.000µs
```

In this case, `your_seed` is a separate RNG seed for generating the random nodes. The default seed is `default`, so
`random` is equal to specifying `random:default`.

### Visualizing the steps of the algorithm

The folding and unfolding phases can be rendered step-by-step:

```console
❯ uv run rfa-tsp tsplib:a280 --renderer matplotlib
```

The rendering can also be exported as an animation:

```console
❯ uv run rfa-tsp tsplib:a280 --export rfa-tsp_tsplib_a280.gif --export-fps 2-6
```

### Benchmarking

To run the full benchmark across the [TSPLIB95] instances in `TSPLIB/` (see [Results](#results) for benchmark output):

```console
❯ uv run rfa-tsp-benchmark --cooldown 5 --trials 10
```

You can also export the results table directly as GitHub-Flavored Markdown (`--export-markdown results.md`) or compare
against pure RFA without local 2-opt (`--unfolding-strategy breadth-first`).

## License

The recursive-fold-algorithm (RFA) was originally conceived and developed by Robert Nitsch in 2010.

This project is licensed under the **MIT License** – see the [LICENSE](LICENSE) file for details.

The benchmark instances in `TSPLIB/` are taken from [TSPLIB95] (Gerhard Reinelt, Universität Heidelberg) and are
provided strictly for academic and benchmarking purposes.

<!--
This README was formatted with:
uvx --with mdformat-gfm --with mdformat-dollarmath mdformat --wrap 120 README.md
-->

[tsplib95]: https://comopt.ifi.uni-heidelberg.de/software/TSPLIB95/
