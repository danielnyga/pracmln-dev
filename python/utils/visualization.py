'''
Created on Sep 11, 2014

@author: nyga
'''

import matplotlib.pyplot as plt
import numpy as np
from matplotlib import rc
import itertools
from numpy.ma.core import floor, ceil

COLORS = ['blue', 'green', 'red', 'orange']
CVALUE = {'blue': '#355FD6',
          'green': '#47A544',
          'red': '#A54D44',
          'orange': '#D0742F'}

MARKERS = ['s', 'v', 'o', '^']

def plot_fscores(labels, series):
    length = max(map(len, series))
    fig = plt.figure()
    ax = fig.gca()
    ax.set_xticks(np.arange(0,float(len(series))), 1)
    ymin = min(map(min, series))
    ymax = max(map(max, series))
    ymin = floor(ymin * 10) / 10
    ymax = ceil(ymax * 10) / 10
    ax.set_yticks(np.arange(ymin,ymax,0.1))
    plt.axis([0, length-1, ymin, ymax])
    fontProperties = {'family':'sans-serif','sans-serif':['Helvetica'],
    'weight' : 'normal', 'size' : 20}
    rc('text', usetex=True)
    rc('font',**fontProperties)
    ax.set_xticklabels([r'$\frac{%d}{%d}$' % (i+1, length-i) for i in range(length)], fontProperties)
    plt.grid()
    for i, [l, s] in enumerate(zip(labels, series)):
        c = CVALUE[COLORS[i]]
        plt.plot(range(len(s)), s, '-', marker=MARKERS[i], color=c, linewidth=2.5, markersize=12, fillstyle='full', label=l)
    plt.legend(loc="best")
    plt.ylabel(r'$F_1$')
    plt.xlabel(r'$k$')
    
if __name__ == '__main__':
    fol = [[0.40, 0.41, 0.41, 0.42, 0.44, 0.49, 0.44, 0.46, 0.51],
           [0.27, 0.29, 0.29, 0.32, 0.29, 0.34, 0.38, 0.36, 0.38],
           [0.28, 0.30, 0.30, 0.31, 0.31, 0.34, 0.34, 0.34, 0.34],
           [0.27, 0.28, 0.29, 0.29, 0.32, 0.32, 0.34, 0.34, 0.34],
           [0.42, 0.43, 0.43, 0.44, 0.46, 0.45, 0.46, 0.53, 0.55],
           [0.16, 0.16, 0.16, 0.16, 0.16, 0.16, 0.16, 0.16, 0.16]]
    fuzzy = [[0.64, 0.69, 0.67, 0.68, 0.75, 0.75, 0.75, 0.75, 0.75],
             [0.44, 0.50, 0.49, 0.51, 0.49, 0.52, 0.57, 0.56, 0.57],
             [0.36, 0.49, 0.54, 0.48, 0.60, 0.56, 0.61, 0.61, 0.65],
             [0.40, 0.51, 0.57, 0.62, 0.64, 0.64, 0.66, 0.66, 0.66],
             [0.43, 0.48, 0.48, 0.50, 0.53, 0.50, 0.51, 0.51, 0.50],
             [0.53, 0.79, 0.73, 0.77, 0.76, 0.83, 0.83, 0.82, 0.82]]
    fol_avg = []
    fuzzy_avg = []
    for (fo, fu) in zip(zip(*fol), zip(*fuzzy)):
        fol_avg.append(np.mean(fo))
        fuzzy_avg.append(np.mean(fu))
    print fol_avg
    print fuzzy_avg
    actioncore ='avg'
#     actioncore = ['filling', 'add', 'slice', 'cutting', 'putting', 'stirring']
    for (fo, fu, ac) in zip([fol_avg], [fuzzy_avg], actioncore):
        plot_fscores(['FOL', 'Fuzzy'],[fo, fu])
        plt.savefig('%s.pdf' % ac)
    