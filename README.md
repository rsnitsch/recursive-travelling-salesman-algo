# RFA_demo

RFA_demo is a demonstration of the recursive-fold-algorithm (RFA) implemented in Python. The RFA is an algorithm for calculating routes for the metric travelling-salesman-problem (TSP).

A detailed description of the RFA and some screenshots are available on my [homepage] (in German language).

## Requirements

The scripts require

- Python 3.2 or above.
- optionally: the [tabulate] module (for pretty results in benchmark mode)

## Usage

The main script is RFA_demo.py and it features multiple commandline arguments. There is only one obligatory argument, namely the mode, which may be `demo` or `benchmark`.

### 'demo' mode
The following command runs a simple demonstration based on 100 randomly generated nodes with a random number generator seed of 17:

```
$ RFA_demo.py demo -n 100 -s 17
Total costs:    4398
Runtime:        0.013s
```

By default, the generated nodes and the resulting route will also be rendered on-screen (using Python's `turtle` module).

### 'benchmark' mode
The following command runs a benchmark using a subset of the [TSPLIB] instances (a280, berlin52, bier127, ch150, eil51, pr76, pr107, pr439, pr1002, rat99, and rat783):

```
$ RFA_demo.py benchmark -s 17 --no-rendering
...
Instance      Costs of optimal route    Costs of RFA route  Cost factor    Runtime
----------  ------------------------  --------------------  -------------  ---------
a280                            2579                  3364  130.44%        0.069s
berlin52                        7542                 10083  133.69%        0.004s
bier127                       118282                139393  117.85%        0.018s
ch150                           6528                  8040  123.16%        0.024s
eil51                            426                   461  108.22%        0.004s
pr76                          108159                126517  116.97%        0.007s
pr107                          44303                 46094  104.04%        0.013s
pr439                         107217                132399  123.49%        0.179s
pr1002                        259045                308964  119.27%        0.880s
rat99                           1211                  1493  123.29%        0.011s
rat783                          8806                 10164  115.42%        0.535s
```

Remarks:

- A random number generator seed is used even in benchmark mode, because the algorithm itself uses random numbers for calculating a route.
- The `no-rendering` switch disables the on-screen rendering of the calculated route. If you remove this switch, you will be able to review the calculated route.

# License
You may download and execute the RFA_demo scripts.

[tabulate]:https://pypi.python.org/pypi/tabulate
[homepage]:https://www.robertnitsch.de/de/notes/rfa-traveling-salesman
[TSPLIB]:http://comopt.ifi.uni-heidelberg.de/software/TSPLIB95/
