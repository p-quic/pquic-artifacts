import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import sqlite3
from math import sqrt

conn = sqlite3.connect('results_fec_all.db')
c = conn.cursor()

configs = c.execute("SELECT DISTINCT bw_a, delay_ms_a FROM results").fetchall()
# One liner to remove tuple
file_sizes = [1000, 10000, 50000, 1000000]#[x[0] for x in c.execute("SELECT DISTINCT file_size FROM results").fetchall()]

dct_ratios = {'eos': {}, 'full': {}}
for fs in file_sizes:
    dct_ratios['eos'][fs] = []

    for config in configs:
        # Always take the best run
        dct_sp_non_fec = c.execute("SELECT MIN(elapsed_time) FROM results WHERE bw_a = ? AND delay_ms_a = ? AND file_size = ? AND test_name = ?",
            (config[0], config[1], fs, 'sp_non_fec')).fetchone()[0]
        dct_sp_fec = c.execute("SELECT MIN(elapsed_time) FROM results WHERE bw_a = ? AND delay_ms_a = ? AND file_size = ? AND test_name = ?",
            (config[0], config[1], fs, 'sp_fec_only_end')).fetchone()[0]
        if dct_sp_fec == 0 or dct_sp_non_fec == 0:
            continue

        dct_ratio = dct_sp_fec / dct_sp_non_fec
        if dct_ratio >= 1.0 and fs >= 1000000:
            print (config, dct_ratio)
        dct_ratios['eos'][fs].append(dct_ratio)


# full_stream
conn = sqlite3.connect('results_fec_all.db')
c = conn.cursor()
configs = c.execute("SELECT DISTINCT bw_a, delay_ms_a FROM results").fetchall()
for fs in file_sizes:
    dct_ratios['full'][fs] = []
    for config in configs:
        # Always take the best run
        dct_sp_non_fec = c.execute("SELECT MIN(elapsed_time) FROM results WHERE bw_a = ? AND delay_ms_a = ? AND file_size = ? AND test_name = ?",
            (config[0], config[1], fs, 'sp_non_fec')).fetchone()[0]
        dct_sp_fec = c.execute("SELECT MIN(elapsed_time) FROM results WHERE bw_a = ? AND delay_ms_a = ? AND file_size = ? AND test_name = ?",
            (config[0], config[1], fs, 'sp_fec')).fetchone()[0]
        if dct_sp_fec == 0 or dct_sp_non_fec == 0:
            continue


        dct_ratio = dct_sp_fec / dct_sp_non_fec
        dct_ratios['full'][fs].append(dct_ratio)


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
              'text.latex.preamble': ['\usepackage{gensymb}'],
              'axes.labelsize': 9, # fontsize for x and y labels (was 10)
              'axes.titlesize': 9,
              #'text.fontsize': 9, # was 10
              'legend.fontsize': 9, # was 10
              'xtick.labelsize': 9,
              'ytick.labelsize': 9,
              'text.usetex': True,
              'figure.figsize': [fig_width,fig_height],
              'font.family': 'serif'
    }

    matplotlib.rcParams.update(params)




config_label = {1000: "1.5 KB", 10000: "10 KB", 50000: "50 KB", 1000000: "1 MB"}
color = {1000: ("darkblue", "--"), 10000: ("hotpink", "-"), 50000: ("green", "-."), 1000000: ("grey", "dotted")}
latexify()
plt.figure(figsize=(4, 1.7), dpi=300)
plt.clf()

#plt.suptitle("Experimental design, {} configs".format(len(configs)))

for i, k in enumerate(['eos', 'full']):
    sp = plt.subplot(1, 2, i+1)
    for fs in sorted(dct_ratios[k].keys()):
        sorted_array = np.array(sorted(dct_ratios[k][fs]))
        yvals = np.arange(1, len(sorted_array) + 1) / float(len(sorted_array))
        if len(sorted_array) > 0:
            yvals = np.insert(yvals, 0, 0)
            sorted_array = np.insert(sorted_array, 0, sorted_array[0])
            plt.plot(sorted_array, yvals, linewidth=1.8, label=config_label[fs], color=color[fs][0], linestyle=color[fs][1])
            # plt.xlabel("$log(DCT_{QUIC-FEC}$ / $DCT_{QUIC})$")
            plt.xlabel("DCT $PQUIC_{FEC}/PQUIC$")
            plt.xscale("log")
            plt.yticks([0, 0.25, 0.5, 0.75, 1])
            plt.xlim(xmin=0.1, xmax=10)
            if i == 0:
                plt.ylabel("CDF")
            plt.grid(b=True, which='major', linestyle='-')


# plt.legend(loc="best")
handles, labels = sp.get_legend_handles_labels()
legend = plt.figlegend(handles, labels, loc='upper center', ncol=5, bbox_to_anchor=(0.52, 0.23))
plt.tight_layout()
plt.subplots_adjust(bottom=0.43)
plt.subplots_adjust(top=0.95)
plt.savefig("fec_cdf.pdf")
# plt.show()
