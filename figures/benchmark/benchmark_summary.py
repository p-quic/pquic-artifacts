import numpy as np
import sqlite3

conn = sqlite3.connect('results_benchmark_mc.db')
c = conn.cursor()

configs = [x[0] for x in c.execute("SELECT DISTINCT test_name FROM results").fetchall()]
# One liner to remove tuple
file_sizes = [x[0] for x in c.execute("SELECT DISTINCT file_size FROM results").fetchall()]

data_table = ""

for config in configs:
    records = c.execute("SELECT elapsed_time, elf_load, plugin_load FROM results WHERE test_name = ?", (config,)).fetchall()
    elapsed_time_med = np.median([r[0] for r in records])
    throughput = file_sizes[0] * 8.0 / (elapsed_time_med * 1000.0)
    throughput_std = np.std([file_sizes[0] * 8.0 / (r[0] * 1000.0) for r in records])
    elf_load_med = np.median([r[1] for r in records])
    plugin_load_med = np.median([r[2] for r in records])
    data_table += """
{} & {:.1f} Mbps & {:.1f} \% & {} ms \\\\
""".format(config, throughput, throughput_std * 100 / throughput, plugin_load_med)
    data_table += "\\hline"


pre_table = """
\\begin{table}
\centering
\\begin{tabular}{c|c|c|c}
Plugin & $\\tilde{x}$ Goodput & $\sigma / \\tilde{x}$ Goodput & Load Time \\\\
\hline
"""

post_table = """
\end{tabular}
\end{table}
"""

latex_code = pre_table + data_table + post_table
print(latex_code)
