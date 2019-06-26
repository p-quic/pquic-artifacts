import matplotlib
import matplotlib.pyplot as plt
import matplotlib.cbook as cbook
matplotlib.rcParams['text.usetex'] = True
matplotlib.rcParams['text.latex.unicode'] = True
plt.rc('font', family='serif')

import numpy as np
import sqlite3

from math import sqrt
SPINE_COLOR = 'gray'

conn = sqlite3.connect('results_mp_sym-cr.db')
c = conn.cursor()

configs = c.execute("SELECT DISTINCT bw_a, bw_b, delay_ms_a, delay_ms_b FROM results").fetchall()
# One liner to remove tuple
file_sizes = [x[0] for x in c.execute("SELECT DISTINCT file_size FROM results").fetchall()]

# Don't show 1.5KB
file_sizes.remove(1500)

to_redo = []

# Initialize the structure
implems = ['picoquic', 'quic-go']
dct_ratios = {}
for key in implems:
    dct_ratios[key] = {}
    for fs in file_sizes:
        dct_ratios[key][fs] = []

# Picoquic
for fs in file_sizes:
    for config in configs:
        # Always take the best run
        dct_sp = c.execute("SELECT MIN(elapsed_time) FROM results WHERE bw_a = ? AND bw_b = ? AND delay_ms_a = ? AND delay_ms_b = ? AND file_size = ? AND test_name = ?",
            (config[0], config[1], config[2], config[3], fs, 'sp_quic')).fetchone()[0]
        dct_mp = c.execute("SELECT MIN(elapsed_time) FROM results WHERE bw_a = ? AND bw_b = ? AND delay_ms_a = ? AND delay_ms_b = ? AND file_size = ? AND test_name = ?",
            (config[0], config[1], config[2], config[3], fs, 'mp_quic')).fetchone()[0]
        if dct_mp == 0 or dct_sp == 0:
            continue

        dct_ratio = dct_sp / dct_mp
        dct_ratios['picoquic'][fs].append(dct_ratio)

# quic-go
conn = sqlite3.connect('results_quic_go-cr.db')
c = conn.cursor()
for fs in file_sizes:
    for config in configs:
        # Always take the best run
        dct_sp = c.execute("SELECT MIN(elapsed_time) FROM results WHERE bw_a = ? AND bw_b = ? AND delay_ms_a = ? AND delay_ms_b = ? AND file_size = ? AND test_name = ?",
            (config[0], config[1], config[2], config[3], fs, 'sp_quic_go')).fetchone()[0]
        dct_mp = c.execute("SELECT MIN(elapsed_time) FROM results WHERE bw_a = ? AND bw_b = ? AND delay_ms_a = ? AND delay_ms_b = ? AND file_size = ? AND test_name = ?",
            (config[0], config[1], config[2], config[3], fs, 'mp_quic_go')).fetchone()[0]
        if dct_mp == 0 or dct_sp == 0:
            continue

        # In mp-quic, we need PINGs before using paths. So be fair against picoquic that only counts time on a hot connection
        dct_mp -= 2 * config[2]

        dct_ratio = dct_sp / dct_mp
        dct_ratios['quic-go'][fs].append(dct_ratio)


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
plt.clf()
fig, (ax1, ax2) = plt.subplots(1, 2, sharey=True, figsize=(4, 1.8), dpi=300)


def convert_to_str(fs):
    if fs >= 1000000:
        return str(int(fs / 1000000)) + 'MB'
    elif fs >= 1000:
        if fs % 1000 == 0:
            return str(int(fs / 1000)) + 'KB'
        else:
            return str(fs / 1000.0) + 'KB'
    else:
        return str(fs)

ticks = [convert_to_str(fs) for fs in sorted(file_sizes)]

def set_box_color(bp, color):
    plt.setp(bp['boxes'], color=color, linewidth=1)
    plt.setp(bp['whiskers'], color=color)
    plt.setp(bp['caps'], color=color)
    plt.setp(bp['medians'], color=color, linewidth=1.25)
    plt.setp(bp['fliers'], color=color, marker='.')

quic_go_stats = cbook.boxplot_stats([x for x in [dct_ratios['quic-go'][fs] for fs in sorted(file_sizes)]], labels=ticks)
plugin_stats = cbook.boxplot_stats([x for x in [dct_ratios['picoquic'][fs] for fs in sorted(file_sizes)]], labels=ticks)

bpl = ax1.bxp(quic_go_stats)
bpr = ax2.bxp(plugin_stats)

set_box_color(bpl, '#acacac')  # colors are from http://colorbrewer2.org/
set_box_color(bpr, '#414141')



# axs[0].plot([], c='#414141', label='Multipath plugin')
# axs[1].plot([], c='#acacac', label='mp-quic')
# plt.legend()

# plt.xticks(range(0, len(ticks) * 3, 3), ticks)
# plt.xlim(left=-1)

plt.yticks(np.arange(0.5, 2.5, 0.5))
plt.ylim(bottom=0.45, top=2.05)

ax1.set_title("mp-quic")
ax2.set_title("Multipath plugin")

# Tweak (beginning)
ax1.set_xlabel("x")
ax2.set_xlabel("x")

ax1.set_ylabel("Speedup ratio")
ax1.grid(linestyle='dotted', color='#dfdfdf')
ax2.grid(linestyle='dotted', color='#dfdfdf')

fig.text(0.55, 0.1, 'File size', ha='center', va='center')

plt.tight_layout()
fig.subplots_adjust(wspace=0.075)

# Tweak (ending)
ax1.set_xlabel(" ")
ax2.set_xlabel(" ")

plt.savefig("mp_boxplot_split-cr.pdf")
# print(to_redo)
