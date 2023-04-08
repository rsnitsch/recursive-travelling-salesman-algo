#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script for executing the recursive-fold-algorithm (RFA) for metric travelling-salesman-problems
and displaying visualizations/benchmarks.

@todo: Implement "animation mode" that allows to observe how the algorithm works step by step.
"""
import argparse
import os
import random
import sys
import turtle

from common import generate_random_nodes, tsplib_get_optimal_solution, load_nodes_from_tsplib_file
from RFA import RFABasic


def create_option_parser():
    kwargs = {
        "description":
        "Calculate and display routes for metric travelling-salesman-problems using the recursive-fold-algorithm."
    }

    parser = argparse.ArgumentParser(**kwargs)

    # Add options to the OptionParser.
    parser.add_argument("mode", type=str, action="store", help="Either 'demo' or 'benchmark'.")

    DEFAULT_NUMBER_OF_NODES = 100
    parser.add_argument("-n",
                        "--nodes",
                        type=int,
                        action="store",
                        dest="number_of_nodes",
                        default=DEFAULT_NUMBER_OF_NODES,
                        help=("Number of nodes for demo mode (default = %d)" % DEFAULT_NUMBER_OF_NODES))

    DEFAULT_SEED = 0
    parser.add_argument("-s",
                        "--seed",
                        type=int,
                        action="store",
                        dest="seed",
                        default=DEFAULT_SEED,
                        help="Random number generator seed (default = %d)" % DEFAULT_SEED)

    parser.add_argument("--no-rendering",
                        action="store_true",
                        dest="no_rendering",
                        default=False,
                        help="Do not render calculated routes")

    return parser


def main(argv):
    parser = create_option_parser()
    args = parser.parse_args(args=argv[1:])

    if not args.mode in ("demo", "benchmark"):
        parser.error("Ungültiger Modus gewählt. Nur 'demo' oder 'benchmark' erlaubt.")

    if args.number_of_nodes <= 2:
        parser.error("Anzahl der nodes muss größer-gleich 3 sein.")

    if args.mode == "demo":
        main_random(args.number_of_nodes, args.seed, not args.no_rendering)
    elif args.mode == "benchmark":
        main_tsplib(args.seed, not args.no_rendering)

    return 0


def main_random(number_of_nodes, seed=0, rendering_enabled=True):
    # KONFIGURATION:
    """
    Gibt an, wie groß die X- bzw. Y-Koordinaten maximal sein dürfen.
    Die Koordinaten werden dann im Intervall [0, max_size] liegen.

    Empfohlen: 500.
    """
    max_size = 500

    # ENDE DER KONFIGURATION.

    nodes = generate_random_nodes(number_of_nodes, max_size=max_size)

    # Zur Reproduzierbarkeit.
    random.seed(seed)

    # RFA ausführen.
    rfa = RFABasic(nodes)
    route = rfa.run()

    total_costs = route.get_total_costs()
    runtime = rfa.get_runtime()

    print("Total costs:\t%s" % total_costs)
    print("Runtime:\t%ss" % runtime)
    print()

    # Darstellen der Route
    if rendering_enabled:
        paint_turtle(route, title="RFA demo with %d nodes and seed = %d (click to close)" % (number_of_nodes, seed))


def main_tsplib(seed=0, rendering_enabled=True):
    # KONFIGURATION:
    """
    TSPLIB-Instanzen, die ausgeführt werden sollen.

    Achtung: Es werden nur "EUC_2D"-Instanzen unterstützt!

    Empfohlen: "a280,berlin52,bier127,ch150,eil51,pr76,pr107,pr439,pr1002,rat99,rat783"
    """
    tsplib = "a280,berlin52,bier127,ch150,eil51,pr76,pr107,pr439,pr1002,rat99,rat783"
    #tsplib = "a280,berlin52,bier127,ch150,eil51,pr76,pr107,pr439,pr1002,rat99,rat783,brd14051,d18512"
    """
    Ausgabeformat für die Ergebnisse.

    Empfohlen: "Instance:\t%(instance)s\nTotal costs:\t%(total_costs)s\nRuntime:\t%(runtime)ss\n"
    """
    format = "Instance:\t%(instance)s\nTotal costs:\t%(total_costs)s\nRuntime:\t%(runtime)ss\n"
    # format = "<tr><td>%(instance)s</td><td>%(optimal_costs)s</td><td>%(total_costs)s</td><td>%(factor)s%%</td><td>%(runtime)ss</td></tr>"

    # Ordner mit den TSPLIB-Instanzen (in entpackter Form)
    tsplib_folder = './TSPLIB'

    # ENDE DER KONFIGURATION.

    try:
        from tabulate import tabulate
        tabulate_available = True
    except ImportError:
        print("Warning: tabulate module could not be imported. Benchmark results will not be pretty-printed.")
        tabulate_available = False

    # Zur Reproduzierbarkeit.
    random.seed(seed)

    # Zeilen für Ergebnis-Tabelle sammeln.
    rows = list()

    # Anwenden des RFA auf die angegebenen TSPLIB-Instanzen.
    for tspi in tsplib.split(","):
        nodes = load_nodes_from_tsplib_file(os.path.join(tsplib_folder, "%s.tsp" % tspi))

        rfa = RFABasic(nodes)
        route = rfa.run()
        if rendering_enabled:
            paint_turtle(route,
                         title="RFA route for TSPLIB instance '%s' with seed = %d (click to close)" % (tspi, seed))

        optimal_costs = tsplib_get_optimal_solution(tspi)
        total_costs = route.get_total_costs()
        factor = round(float(total_costs) / optimal_costs * 100, 2)
        runtime = rfa.get_runtime()

        rows.append([tspi, optimal_costs, total_costs, "%.2f%%" % factor, "%.3fs" % runtime])

        print(
            format % {
                'instance': tspi,
                'total_costs': total_costs,
                'runtime': runtime,
                'optimal_costs': optimal_costs,
                'factor': factor
            })

    # Ergebnis-Tabelle ausgeben.
    headers = ["Instance", "Costs of optimal route", "Costs of RFA route", "Cost factor", "Runtime"]
    if tabulate_available:
        print(tabulate(rows, headers=headers))
    else:
        # Fallback if tabulate module is not available.
        import pprint
        rows.insert(0, headers)
        pprint.pprint(rows)


def paint_turtle(route, scale=1.5, title="Route rendering (click to close)"):
    min_x = min([node.x for node in route])
    max_x = max([node.x for node in route])
    min_y = min([node.y for node in route])
    max_y = max([node.y for node in route])

    data_width = max_x - min_x
    data_height = max_y - min_y
    data_aspect = data_width / float(data_height)

    MAX_DISPLAY_DIMENSION = 500
    display_padding = MAX_DISPLAY_DIMENSION * 0.1
    if data_width > data_height:
        display_width = MAX_DISPLAY_DIMENSION
        display_height = display_width / data_aspect
    else:
        display_height = MAX_DISPLAY_DIMENSION
        display_width = display_height * data_aspect
    w = display_width + 2 * display_padding
    h = display_height + 2 * display_padding

    try:
        turtle.setup(width=w * scale, height=h * scale)
        turtle.title(title)

        # For transforming data coordinates to turtle's screen coordinates.
        tc_x = lambda x: int((x - min_x) / data_width * display_width - display_width / 2.0) * scale
        tc_y = lambda y: int((y - min_y) / data_height * display_height - display_height / 2.0) * scale

        turtle.hideturtle()
        turtle.goto(tc_x(route[0].x), tc_y(route[0].y))
        turtle.clear()

        turtle.speed("fastest")
        turtle.tracer(len(route) / 20, 500)

        for i in range(1, len(route)):
            turtle.goto(tc_x(route[i].x), tc_y(route[i].y))
            turtle.dot()

        turtle.goto(tc_x(route[0].x), tc_y(route[0].y))
        turtle.dot()

        turtle.exitonclick()
    except turtle.Terminator:
        pass


if __name__ == "__main__":
    sys.exit(main(sys.argv))
