'''
Created on Sep 11, 2014

@author: nyga
'''
import os

import matplotlib.pyplot as plt
import numpy as np
from matplotlib import rc
from numpy.ma.core import floor, ceil
import thread
from pracmln.utils.latexmath2png import math2png


COLORS = ['blue', 'green', 'red', 'orange']
CVALUE = {'blue': '#355FD6',
          'green': '#47A544',
          'red': '#A54D44',
          'orange': '#D0742F'}

MARKERS = ['s', 'v', 'o', '^']
DECLARATIONS = [r'''\DeclareMathOperator*{\argmin}{\arg\!\min}''',
                r'''\DeclareMathOperator*{\argmax}{\arg\!\max}''',
                r'''\newcommand{\Pcond}[1]{\ensuremath{P\left(\begin{array}{c|c}#1\end{array}\right)}}''']


def plot_fscores(labels, series):
    length = max(map(len, series))
    fig = plt.figure()
    ax = fig.gca()
    ax.set_xticks(np.arange(0, float(len(series))), 1)
    ymin = min(map(min, series))
    ymax = max(map(max, series))
    ymin = floor(ymin * 10) / 10
    ymax = ceil(ymax * 10) / 10
    ax.set_yticks(np.arange(ymin, ymax, 0.1))
    plt.axis([0, length - 1, ymin, ymax])
    fontProperties = {'family': 'sans-serif', 'sans-serif': ['Helvetica'],
                      'weight': 'normal', 'size': 20}
    rc('text', usetex=True)
    rc('font', **fontProperties)
    ax.set_xticklabels(
        [r'$\frac{%d}{%d}$' % (i + 1, length - i) for i in range(length)],
        fontProperties)
    plt.grid()
    for i, [l, s] in enumerate(zip(labels, series)):
        c = CVALUE[COLORS[i]]
        plt.plot(range(len(s)), s, '-', marker=MARKERS[i], color=c,
                 linewidth=2.5, markersize=12, fillstyle='full', label=l)
    plt.legend(loc="best")
    plt.ylabel(r'$F_1$')
    plt.xlabel(r'$k$')


def plot_KLDiv_with_logscale(series):
    length = len(series)
    fig = plt.figure()
    ax = fig.gca()
    ax.set_xticks(np.arange(0, float(len(series))), 1)
    ymin = min(series)
    ymax = max(series)
    ymin = floor(ymin * 10) / 10
    ymax = ceil(ymax * 10) / 10
    ax.set_yticks(np.arange(ymin, ymax, 0.1))
    plt.axis([0, length - 1, ymin, ymax])
    fontProperties = {'family': 'sans-serif', 'sans-serif': ['Helvetica'],
                      'weight': 'normal', 'size': 20}
    rc('text', usetex=True)
    rc('font', **fontProperties)
    #     ax.set_xticklabels([r'$\frac{%d}{%d}$' % (i+1, length-i) for i in range(length)], fontProperties)
    plt.grid()
    a = plt.axes()  # plt.axis([0, length-1, ymin, ymax])
    plt.yscale('log')

    c = CVALUE[COLORS[0]]
    m = MARKERS[0]
    plt.plot(range(len(series)), series, '-', marker=m, color=c, linewidth=2.5,
             markersize=12, fillstyle='full', label='Label')
    c = CVALUE[COLORS[1]]
    m = MARKERS[1]
    plt.plot(range(len(series)), series, '-', marker=m, color=c, linewidth=2.5,
             markersize=12, fillstyle='full', label='Label')

    plt.legend(loc="best")
    plt.ylabel(r'$F_1$')
    plt.xlabel(r'$k$')


def get_cond_prob_png(queries, dbs, filename='cond_prob', filedir='/tmp'):
    """
    Preprocessing of png generation: assemble latex code for argmax term

    :param queries:     list or comma-separated string of query predicates
    :param dbs:         evidence database
    :param filename:    filename prefix of the generated file
    :param filedir:     location of temporary generated file
    :return:            a png string generated by math2png
    """
    safefilename = '{}-{}-{}'.format(filename, os.getpid(), thread.get_ident())

    if isinstance(queries, str):
        queries = queries.split(',')

    evidencelist = []
    if isinstance(dbs, str):
        evidencelist = dbs.split(',')
    elif isinstance(dbs, list):
        for db in dbs:
            evidencelist.extend([e for e in db.evidence.keys() if db.evidence[e] == 1.0])
    else:
        evidencelist.extend([e if dbs.evidence[e] == 1.0 else '!' + e for e in dbs.evidence.keys()])

    # escape possibly occurring underscores in predicate names
    query = r'''\\'''.join([r'''\text{{ {0} }} '''.format(q.replace('_', '\_')) for q in queries])
    evidence = r'''\\'''.join([r'''\text{{ {0} }} '''.format(e.replace('_', '\_')) for e in evidencelist])

    underset = '_{{ \\tiny\\begin{{array}}{{c}}{0}\end{{array}} }}'.format(query)

    # generate actual equation
    head = r'''\argmax{}'''.format(underset)
    bracket_term = r'''\Pcond{{ \begin{{array}}{{c}}{0}\end{{array}} & \begin{{array}}{{c}}{1}\end{{array}} }}'''.format(
        query, evidence)
    eq = r'''{} {}'''.format(head, bracket_term)
    
    return math2png(eq, filedir, declarations=DECLARATIONS, filename=safefilename, size=10)


if __name__ == '__main__':
    pass
