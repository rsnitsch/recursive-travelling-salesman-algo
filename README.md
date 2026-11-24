# RFA_demo <!-- omit from toc -->

The recursive-fold-algorithm (RFA) is a recursive algorithm for the metric travelling-salesman-problem (TSP). The objective of the TSP is to find a
round trip through a number of cities/locations (more generally referred to as **nodes**). The round trip should be as short as possible. The TSP
is a very hard problem with difficult computational properties (TSP belongs to the NP-hard problem class).

Recursive algorithms naturally split a problem into a series of smaller steps that are easier to solve individually. As such, they're often
very elegant.

## Contents <!-- omit from toc -->

- [Idea](#idea)
  - [Folding strategies](#folding-strategies)
  - [Unfolding strategies](#unfolding-strategies)
- [Install](#install)
- [Usage](#usage)
  - ['demo' mode](#demo-mode)
  - ['benchmark' mode](#benchmark-mode)
- [License](#license)

## Idea

RFA exploits the fact that the TSP can be trivially solved if there are only 3 nodes, because only a single round trip route exists
for 3 nodes. The solution is self-evident:

![alt](docs/rfa_00_tsp_trivial_problem_size.png)

This **trivial case** is the **recursion anchor** for the algorithm.

But how to deal with larger problem sizes? The answer is to **fold
nodes**. Folding means that two nodes that are in close proximity to each other are fused into an artifical new node. This new node gets placed in the middle
between the two original nodes. By remembering the original nodes it is also possible to reverse such a folding operation later on (referred to as **unfolding**). Of course, folded nodes can be folded again themselves (recursively).

Once only 3 nodes remain, a preliminary solution (route) can be constructed. Again, this is self-evident:

![alt](docs/rfa_00_tsp_trivial_problem_size.png)

The key to RFA is that the nodes are now unfolded step by step. Each unfolding
removes a node and replaces it with two new nodes. These new nodes can be inserted
into the preliminary route in two alternative orders only. In the following picture the artificial node in the bottom-right corner (blue) is unfolded:

![alt](docs/rfa_01_tsp_unfold_possibilities.png)

It is obvious that the new nodes (red) can only be inserted in two different orders. It is also easy to determine which of these orders gives the shorter route (the green one).

The complete process can be described as follows:

- **Folding:** Pick a node and fold it with a neighboring node. Repeat folding nodes until the number of nodes has been reduced to 3.
- **Recursion anchor:** Create a preliminary round trip route through the 3 remaining nodes.
- **Unfolding:** Unfold the nodes until the original nodes have been restored. At each unfolding step, insert the new nodes in the preliminary route. Choose the insertion order that gives the shorter route length.

### Folding strategies

- `FoldingStrategyBreadthFirst` (default): Randomly picks one of the least-folded nodes
  (minimum folding depth) and folds it with its nearest neighbor across all active nodes,
  keeping the folding tree balanced.
- `FoldingStrategyRandomWithNearestNeighbor`: A very simple yet highly efficient method
  which randomly picks a node and folds it with the nearest-neighbor.
- `FoldingStrategyOutsideIn`: The node furthest from the center point is folded with its
  nearest-neighbor. The center point is only calculated once at the beginning.

### Unfolding strategies

- `UnfoldingStrategyBreadthFirst`: The list of folded nodes is processed repeatedly. During each iteration, only
  the nodes with the maximum depth are unfolded.
- `UnfoldingStrategyBreadthFirstWithLocal2Opt` (default): Same as UnfoldingStrategyBreadthFirst, but after each unfolding
  step, a local 2-opt optimization around the inserted nodes is performed.

## Install

The scripts require

- Python 3.15
- PyPI packages `rtree`, `shapely`, and `tabulate`

The project uses ``pyproject.toml`` and ``uv`` for dependency management.

The recommended way is to run ``uv sync`` once in the project directory and from then on
just use ``uv run python <script.py>``.

## Usage

The main script is RFA_demo.py and it features multiple commandline arguments. There is only one obligatory argument, namely the mode, which may be `demo` or `benchmark`.

### 'demo' mode

The following command runs a simple demonstration based on 100 randomly generated nodes with a random number generator seed of 17:

    $ python RFA_demo.py demo -n 100 -s 17
    Total costs:    4075
    Runtime:        0.016s

### 'benchmark' mode

The following command runs a benchmark using a subset of the [TSPLIB95] instances (see TSPLIB/ folder):

    $ python RFA_demo.py benchmark --tsplib all -s 17
    ...
    Instance      Costs of optimal route    Costs of RFA route  Cost factor    Runtime
    ----------  ------------------------  --------------------  -------------  ---------
    a280                            2579                  2821  109.38%        0.015s
    berlin52                        7542                  8493  112.61%        0.002s
    bier127                       118282                127715  107.98%        0.008s
    brd14051                      469385                514516  109.61%        0.747s
    ch150                           6528                  7031  107.71%        0.010s
    d18512                        645238                709537  109.97%        0.977s
    eil51                            426                   427  100.23%        0.006s
    pla33810                    66048945              76937901  116.49%        1.586s
    pla7397                     23260728              26282060  112.99%        0.352s
    pla85900                   142382641             163775277  115.02%        4.367s
    pr1002                        259045                280345  108.22%        0.078s
    pr107                          44303                 44381  100.18%        0.005s
    pr439                         107217                116823  108.96%        0.023s
    pr76                          108159                111780  103.35%        0.004s
    rat783                          8806                  9581  108.80%        0.039s
    rat99                           1211                  1288  106.36%        0.006s
    sw24978                       855597                947318  110.72%        1.357s
    usa13509                    19982859              22071090  110.45%        0.755s

## License

You may download and execute the RFA_demo scripts.

The benchmark instances in ``TSPLIB/`` are taken from [TSPLIB95] (Gerhard Reinelt, Universität Heidelberg) and are
provided strictly for academic and benchmarking purposes.

[TSPLIB95]:http://comopt.ifi.uni-heidelberg.de/software/TSPLIB95/
