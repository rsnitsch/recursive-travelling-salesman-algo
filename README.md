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

- `FoldingStrategyRandomWithNearestNeighbor`: A very simple yet highly efficient method which
  randomly picks a node and folds it with the nearest-neighbor.
- `FoldingStrategyOutsideIn`: The node furthest from the center point is folded with its nearest-neighbor. The center
  point is only calculated once at the beginning.

### Unfolding strategies

- `UnfoldingStrategyBreadthFirst`: The list of folded nodes is processed repeatedly. During each iteration, only
  the nodes with the maximum depth are unfolded.

## Install

The scripts require

- Python 3, for example 3.13 is working.
- optionally: the [tabulate] module (for pretty results in benchmark mode)

The easiest way is to use `pipenv`. A `Pipfile` is included in the project. You can simply download the code and run `pipenv install` in the top-level
project folder. Then switch to the project's Python environment by executing `pipenv shell`. You can now execute the main script `RFA_demo.py` as described
in the below *Usage* section.

## Usage

The main script is RFA_demo.py and it features multiple commandline arguments. There is only one obligatory argument, namely the mode, which may be `demo` or `benchmark`.

### 'demo' mode

The following command runs a simple demonstration based on 100 randomly generated nodes with a random number generator seed of 17:

    $ python RFA_demo.py demo -n 100 -s 17
    Total costs:    4366
    Runtime:        0.003s

### 'benchmark' mode

The following command runs a benchmark using a subset of the [TSPLIB] instances (a280, berlin52, bier127, ch150, eil51, pr76, pr107, pr439, pr1002, rat99, and rat783):

    $ python RFA_demo.py benchmark -s 17
    ...
    Instance      Costs of optimal route    Costs of RFA route  Cost factor    Runtime
    ----------  ------------------------  --------------------  -------------  ---------
    a280                            2579                  3332  129.20%        0.015s
    berlin52                        7542                 10083  133.69%        0.001s
    bier127                       118282                145374  122.90%        0.004s
    ch150                           6528                  7991  122.41%        0.005s
    eil51                            426                   446  104.69%        0.001s
    pr76                          108159                125575  116.10%        0.002s
    pr107                          44303                 46440  104.82%        0.003s
    pr439                         107217                131166  122.34%        0.039s
    pr1002                        259045                305608  117.97%        0.184s
    rat99                           1211                  1449  119.65%        0.003s
    rat783                          8806                  9891  112.32%        0.112s

Alternatively you can use the outside-in folding strategy:

    $ python RFA_demo.py benchmark -s 17 --folding-strategy outside-in
    ...
    Instance      Costs of optimal route    Costs of RFA route  Cost factor    Runtime
    ----------  ------------------------  --------------------  -------------  ---------
    a280                            2579                  3353  130.01%        0.027s
    berlin52                        7542                  9223  122.29%        0.001s
    bier127                       118282                138397  117.01%        0.006s
    ch150                           6528                  7861  120.42%        0.008s
    eil51                            426                   469  110.09%        0.001s
    pr76                          108159                125535  116.07%        0.002s
    pr107                          44303                 47920  108.16%        0.005s
    pr439                         107217                136940  127.72%        0.064s
    pr1002                        259045                320124  123.58%        0.317s
    rat99                           1211                  1440  118.91%        0.004s
    rat783                          8806                 10756  122.14%        0.196s

## License

You may download and execute the RFA_demo scripts.

[tabulate]:https://pypi.python.org/pypi/tabulate
[TSPLIB]:http://comopt.ifi.uni-heidelberg.de/software/TSPLIB95/
