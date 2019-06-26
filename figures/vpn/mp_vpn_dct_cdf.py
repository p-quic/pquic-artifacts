import sqlite3
import matplotlib
from os import path

import numpy as np
import matplotlib.pyplot as plt
from matplotlib import ticker

matplotlib.rcParams['text.usetex'] = True
matplotlib.rcParams['text.latex.unicode'] = True
plt.rc('font', family='serif')


def flatten(l):
    """
        inefficiently flattens a list
        l: an arbitrary list
    """
    if not l:
        return list(l)
    if isinstance(l[0], (list, tuple)):
        return flatten(l[0]) + flatten(l[1:])
    return [l[0]] + flatten(l[1:])


def pretty_print_size(byte_size):
    suffixes = ['B', 'kB', 'MB', 'GB', 'TB', 'PB']
    if not byte_size or byte_size == 0:
        return '0 B'
    i = 0
    while byte_size >= 1000 and i < len(suffixes) - 1:
        byte_size /= 1000.
        i += 1  
    f = ('%.2f' % byte_size).rstrip('0').rstrip('.')
    return '%s %s' % (f, suffixes[i])


dir_path = path.dirname(path.abspath(__file__))
conn = sqlite3.connect(path.join(dir_path, 'results_vpn_bulk-cr.db'))
file_sizes = flatten(conn.execute("select distinct file_size from results").fetchall())
tests = flatten(conn.execute("select distinct test_name from results").fetchall())

#colors = ['#d7191c','#fdae61','#ffffbf','#abd9e9','#2c7bb6']
colors = ["darkblue", "hotpink", "green", "grey", "lightblue"]


# https://matplotlib.org/gallery/lines_bars_and_markers/linestyles.html
linestyles = dict([('solid',               (0, ())),
     ('loosely dotted',      (0, (1, 10))),
     ('dotted',              (0, (1, 5))),
     ('densely dotted',      (0, (1, 1))),

     ('loosely dashed',      (0, (5, 10))),
     ('dashed',              (0, (5, 5))),
     ('densely dashed',      (0, (5, 1))),

     ('loosely dashdotted',  (0, (3, 10, 1, 10))),
     ('dashdotted',          (0, (3, 5, 1, 5))),
     ('densely dashdotted',  (0, (3, 1, 1, 1))),

     ('loosely dashdotdotted', (0, (3, 10, 1, 10, 1, 10))),
     ('dashdotdotted',         (0, (3, 5, 1, 5, 1, 5))),
     ('densely dashdotdotted', (0, (3, 1, 1, 1, 1, 1)))])

patterns = ["dashed", "solid", "densely dashdotted", "densely dashdotdotted", "densely dotted"]

fig = plt.figure(figsize=(4, 1.6), dpi=300)

baseline = 'tcp'
evaluated = 'mp_vpn'


for file_size, color, pattern in zip(file_sizes, colors, patterns):
    results = conn.execute('select R1.bw_b, R1.delay_ms_b, R1.file_size, R2.elapsed_time/R1.elapsed_time, R2.test_name from results R1 join results R2 where R1.bw_b = R2.bw_b and R1.delay_ms_b = R2.delay_ms_b and R1.file_size = R2.file_size and R1.file_size = (?) and R1.test_name <> R2.test_name and R1.test_name = (?) and R2.test_name = (?)',
        (file_size, baseline, evaluated)).fetchall()
    #if file_size == 1000000:
    # print([r for r in results if r[3] < 0.75 or r[3] > 1.5])
    results = list(sorted([r[3] for r in results]))
    

    increment = 1.0 / len(results)
    plt.plot(results, np.arange(0, 1, increment), label=pretty_print_size(file_size), color=color, linewidth=2, linestyle=linestyles[pattern])


from math import sqrt
SPINE_COLOR = 'gray'
def latexify(fig_width=None, fig_height=None, columns=1):
    """Set up matplotlib's RC params for LaTeX plotting.
    Call this before plotting a figure.

    Parameters
    ----------
    fig_width : float, optional, inches
    fig_height : float,  optional, inches
    columns : {1, 2}
    """

    # code adapted from http://www.scipy.org/Cookbook/Matplotlib/LaTeX_Examples

    # Width and max height in inches for IEEE journals taken from
    # computer.org/cms/Computer.org/Journal%20templates/transactions_art_guide.pdf

    assert(columns in [1,2])

    if fig_width is None:
        fig_width = 3.39 if columns==1 else 6.9 # width in inches

    if fig_height is None:
        golden_mean = (sqrt(5)-1.0)/2.0    # Aesthetic ratio
        fig_height = fig_width*golden_mean # height in inches

    MAX_HEIGHT_INCHES = 8.0
    if fig_height > MAX_HEIGHT_INCHES:
        print("WARNING: fig_height too large:" + fig_height + 
              "so will reduce to" + MAX_HEIGHT_INCHES + "inches.")
        fig_height = MAX_HEIGHT_INCHES

    params = {'backend': 'ps',
              'text.latex.preamble': ['\\usepackage{gensymb}'],
              'axes.labelsize': 9, # fontsize for x and y labels (was 10)
              'axes.titlesize': 9,
              'font.size': 9, # was 10
              'legend.fontsize': 9, # was 10
              'xtick.labelsize': 9,
              'ytick.labelsize': 9,
              'text.usetex': True,
              'figure.figsize': [fig_width,fig_height],
              'font.family': 'serif'
    }

    matplotlib.rcParams.update(params)


def format_axes(ax):

    for spine in ['top', 'right']:
        ax.spines[spine].set_visible(False)

    for spine in ['left', 'bottom']:
        ax.spines[spine].set_color(SPINE_COLOR)
        ax.spines[spine].set_linewidth(0.5)

    ax.xaxis.set_ticks_position('bottom')
    ax.yaxis.set_ticks_position('left')

    for axis in [ax.xaxis, ax.yaxis]:
        axis.set_tick_params(direction='out', color=SPINE_COLOR)

    return ax


latexify()

plt.grid()
legend = plt.legend(bbox_to_anchor=(1.05, 1), loc=2, borderaxespad=0., handlelength=3)
plt.ylim(0, 1)
plt.xscale('log')
plt.xlim(0.50, 1.20)
plt.xticks([0.50, 0.60, 0.70, 0.80, 0.90, 1.00, 1.10, 1.20])
plt.yticks([0, 0.25, 0.5, 0.75, 1])
plt.xlabel('DCT in/out')
ax = plt.gca().get_xaxis()
#locs = np.append(np.arange(0.5, 1, 0.1), np.arange(1, 2.2, 0.2))
#ax.set_minor_locator(ticker.FixedLocator(locs))
#ax.set_major_locator(ticker.NullLocator())
ax.set_major_formatter(ticker.ScalarFormatter())
ax.set_minor_formatter(ticker.ScalarFormatter())
ax.set_ticks([], minor=True)
plt.gca().ticklabel_format(style='plain', axis='x', useOffset=False)
plt.ylabel('CDF')
plt.tight_layout()
plt.savefig('mp_vpn_dct_cdf.pdf', bbox_inches='tight', pad_inches=0)
