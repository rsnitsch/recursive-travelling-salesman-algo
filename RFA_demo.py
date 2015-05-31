#!/usr/bin/env python3
# coding=UTF-8
"""
Package:    RFA demonstration
Author:     Robert Nitsch
Source:     http://www.robertnitsch.de/de:informatik:rfa-traveling-salesman

This package demonstrates the recursive fold algorithm (RFA) for metric
traveling-salesman-problems. See the URL above for details (german).
"""
import os
import random
import sys
import turtle

from common import *
from RFA import *

def main(argv):
    if len(argv) == 1:
        selected = "random"
    elif len(argv) == 2:
        selected = argv[1]
    else:
        print("Usage: %s [random|tsplib]")
        return 1

    if selected == "random":
        main_random(seed=0)
    elif selected == "tsplib":
        main_tsplib(seed=0)
    else:
        print("Invalid selection: '%s'." % selected, file=sys.stderr)

    return 0

def main_random(seed=0):
    # KONFIGURATION:

    """
    Gibt an, wie groß die X- bzw. Y-Koordinaten maximal sein dürfen.
    Die Koordinaten werden dann im Intervall [0, max_size] liegen.

    Empfohlen: 500.
    """
    max_size = 500

    # ENDE DER KONFIGURATION.
    
    nodes = generate_random_nodes(100, max_size=max_size)

    # Zur Reproduzierbarkeit.
    random.seed(seed)

    # RFA ausführen.
    rfa = RFABasic(nodes)
    route = rfa.run()

    total_costs   = route.get_total_costs()
    runtime       = rfa.get_runtime()

    print("Total costs:\t%s" % total_costs)
    print("Runtime:\t%ss" % runtime)
    print()

    # Darstellen der Route
    paint_turtle(route, max_size=max_size)

def main_tsplib(seed=0):
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

    # Zur Reproduzierbarkeit.
    random.seed(seed)

    # Anwenden des RFA auf die angegebenen TSPLIB-Instanzen.
    for tspi in tsplib.split(","):
        nodes = load_nodes_from_tsplib_file(os.path.join(tsplib_folder,
                                                         "%s.tsp" % tspi))

        rfa = RFABasic(nodes)
        route = rfa.run()
        #print [str(i) for i in route]

        optimal_costs = tsplib_get_optimal_solution(tspi)
        total_costs   = route.get_total_costs()
        factor        = round(float(total_costs) / optimal_costs * 100, 2)
        runtime       = rfa.get_runtime()

        print(format % {'instance':         tspi,
                        'total_costs':      total_costs,
                        'runtime':          runtime,
                        'optimal_costs':    optimal_costs,
                        'factor':           factor})

def paint_turtle(route, max_size=500, scale=1.5):
    w = max_size+100
    h = max_size+100
    
    turtle.setup(width=w*scale, height=h*scale)
    turtle.title("RFA demo (click to close)")

    # For transforming coordinates to fit turtle's screen.
    tc = lambda c: int(c-(max_size/2)) * scale

    turtle.hideturtle()
    turtle.goto(tc(route[0].x), tc(route[0].y))
    turtle.clear()

    turtle.speed(10)
    turtle.tracer(len(route)/20, 500)

    for i in range(1,len(route)):
        turtle.goto(tc(route[i].x), tc(route[i].y))
        turtle.dot()

    turtle.goto(tc(route[0].x), tc(route[0].y))
    turtle.dot()
    turtle.exitonclick()

if __name__ == "__main__":
    sys.exit(main(sys.argv))
