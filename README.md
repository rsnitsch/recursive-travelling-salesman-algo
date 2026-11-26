# rfa-tsp <!-- omit from toc -->

The **recursive-fold-algorithm** (RFA) is a recursive algorithm for the metric **travelling-salesman-problem** (TSP). The objective of the TSP is to find a
round trip through a number of cities/locations (more generally referred to as **nodes**). The round trip should be as short as possible. The TSP
is a very hard problem with difficult computational properties (TSP belongs to the NP-hard problem class).

Recursive algorithms naturally split a problem into a series of smaller steps that are easier to solve individually. As such, they're often
very elegant.

## Contents <!-- omit from toc -->

- [Idea](#idea)
  - [Folding strategies](#folding-strategies)
  - [Unfolding strategies](#unfolding-strategies)
- [Usage](#usage)
  - [Processing a single TSPLIB instance](#processing-a-single-tsplib-instance)
  - [Processing a random TSP instance](#processing-a-random-tsp-instance)
  - [Visualizing the steps of the algorithm](#visualizing-the-steps-of-the-algorithm)
  - [Benchmarking](#benchmarking)
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

## Usage

This project uses ``uv`` as packet and project manager. See: <https://docs.astral.sh/uv/>

### Processing a single TSPLIB instance

You can select a single TSPLIB instance from the ``tsplib/`` folder:

    ❯ uv run rfa-tsp tsplib:a280
    INFO | Instance:           tsplib:a280 (280 nodes)
    INFO | Folding strategy:   breadth-first
    INFO | Unfolding strategy: breadth-first-2opt
    INFO | Post-uncross:       False
    INFO | Seed:               0
    INFO | Total costs:        2882
    INFO | Optimal costs:      2579 (111.75%)
    INFO | Runtime:            0.030s

Results will vary slightly when you change the RNG seed:

    ❯ uv run rfa-tsp tsplib:a280 --seed 1
    ... (same as above) ...
    INFO | Seed:               1
    INFO | Total costs:        2837
    INFO | Optimal costs:      2579 (110.00%)
    INFO | Runtime:            0.033s

### Processing a random TSP instance

To process a randomly generated set of nodes:

    ❯ uv run rfa-tsp random --nodes 50
    INFO | Instance:           random (50 nodes)
    INFO | Folding strategy:   breadth-first
    INFO | Unfolding strategy: breadth-first-2opt
    INFO | Post-uncross:       False
    INFO | Seed:               0
    INFO | Total costs:        2991
    INFO | Runtime:            0.005s

### Visualizing the steps of the algorithm

The folding und unfolding phases can be rendered step-by-step:

    ❯ uv run rfa-tsp tsplib:a280 --renderer matplotlib

The rendering can also be exported as an animation:

    ❯ uv run rfa-tsp tsplib:a280 --renderer matplotlib --export rfa-tsp_tsplib95_a280.gif --export-fps 5

### Benchmarking

The following command runs a benchmark using a subset of the [TSPLIB95] instances (see ``TSPLIB/`` folder):

    ❯ uv run rfa-tsp-benchmark
    INFO | Folding strategy:   breadth-first
    INFO | Unfolding strategy: breadth-first-2opt
    INFO | Post-uncross:       False
    INFO | Seed:               0
    INFO | Running benchmark for 18 TSPLIB instance(s): ...
    ...
    Instance      Costs of optimal route    Costs of RFA route  Cost factor    Runtime
    ----------  ------------------------  --------------------  -------------  ---------
    a280                            2579                  2882  111.75%        0.013s
    berlin52                        7542                  8337  110.54%        0.003s
    bier127                       118282                128084  108.29%        0.007s
    brd14051                      469385                517022  110.15%        0.821s
    ch150                           6528                  6900  105.70%        0.013s
    d18512                        645238                708935  109.87%        1.104s
    eil51                            426                   443  103.99%        0.008s
    pla33810                    66048945              77483437  117.31%        1.734s
    pla7397                     23260728              26482473  113.85%        0.362s
    pla85900                   142382641             164304152  115.40%        4.739s
    pr1002                        259045                279017  107.71%        0.081s
    pr107                          44303                 44658  100.80%        0.006s
    pr439                         107217                115989  108.18%        0.023s
    pr76                          108159                114746  106.09%        0.005s
    rat783                          8806                  9664  109.74%        0.040s
    rat99                           1211                  1295  106.94%        0.006s
    sw24978                       855597                944301  110.37%        1.506s
    usa13509                    19982859              22192827  111.06%        0.825s
    
    Summary (18/18 instances):
      Mean cost factor (arithmetic): 109.32%
      Mean cost factor (geometric):  109.25%
      Median cost factor:            109.81%
      Total runtime:                 11.296s

## License

You may download and execute the RFA_demo scripts.

The benchmark instances in ``TSPLIB/`` are taken from [TSPLIB95] (Gerhard Reinelt, Universität Heidelberg) and are
provided strictly for academic and benchmarking purposes.

[TSPLIB95]:http://comopt.ifi.uni-heidelberg.de/software/TSPLIB95/
