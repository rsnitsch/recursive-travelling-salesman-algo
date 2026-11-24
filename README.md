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

The following command runs a benchmark using a subset of the [TSPLIB] instances (see TSPLIB/ folder):

    $ python RFA_demo.py benchmark --tsplib all -s 17
    ...
    Instance      Costs of optimal route    Costs of RFA route  Cost factor    Runtime
    ----------  ------------------------  --------------------  -------------  ---------
    a280                            2579                  2878  111.59%        0.027s
    berlin52                        7542                  8345  110.65%        0.005s
    bier127                       118282                128555  108.69%        0.012s
    brd14051                      469385                516756  110.09%        3.429s
    ch150                           6528                  7108  108.88%        0.017s
    d18512                        645238                709360  109.94%        5.422s
    eil51                            426                   444  104.23%        0.008s
    pla33810                    66048945              77256794  116.97%        14.420s
    pla7397                     23260728              26273758  112.95%        1.187s
    pla85900                   142382641             163962149  115.16%        103.003s
    pr1002                        259045                279480  107.89%        0.132s
    pr107                          44303                 44381  100.18%        0.010s
    pr439                         107217                117733  109.81%        0.044s
    pr76                          108159                114068  105.46%        0.006s
    rat783                          8806                  9565  108.62%        0.080s
    rat99                           1211                  1313  108.42%        0.010s
    sw24978                       855597                950790  111.13%        9.094s
    usa13509                    19982859              22027397  110.23%        3.291s

## License

You may download and execute the RFA_demo scripts.

[tabulate]:https://pypi.python.org/pypi/tabulate
[TSPLIB]:http://comopt.ifi.uni-heidelberg.de/software/TSPLIB95/
