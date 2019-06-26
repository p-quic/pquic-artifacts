import os
import sqlite3

import comp
import time
from ED_benchmark_comp import int, float, str, get_path_cfgs_default_func, load_wsp, ParamsGenerator, flatten

index = 0

server = comp.CompNode('testINL1', {'testINL2': {'ip': '42.0.0.1/24', 'ifname': 'em1'}})
client = comp.CompNode('testINL2', {'testINL1': {'ip': '42.0.0.2/24', 'ifname': 'em1'}})

def symmetric_topo(v, **kwargs):
    # This is not clean, but it works...
    v["delay_ms_a"] = v["delay_ms_b"]
    v["bw_a"] = v["bw_b"]

def run_benchmark_xp(test_name, setup_nets_opts, store_result_in_db_func, **kwargs):
    global index

    client.run_cmd('pkill picoquic')
    server.run_cmd('pkill picoquic')
    client.run_cmd('pkill ab')
    server.run_cmd('pkill lighttpd')
    client.run_cmd('pkill client')
    server.run_cmd('pkill server')
    client.run_cmd('rm -rf /tmp/*.log /tmp/cache*')
    server.run_cmd('rm -rf /tmp/*.log /tmp/random*')
    client.run_cmd('rm -rf /tmp/plugins')
    server.run_cmd('rm -rf /tmp/plugins')

    client.run_cmd('cp -r ~/picoquic/plugins /tmp')
    server.run_cmd('cp -r ~/picoquic/plugins /tmp')

    plugins = ""
    if "plugins" in setup_nets_opts:
        plugins = setup_nets_opts["plugins"]
    elif test_name.startswith('fec'):
        plugins = '-P /tmp/plugins/fec/{test_name}.plugin'.format(test_name=test_name)
    elif test_name.startswith('multipath'):
        plugins = '-P /tmp/plugins/multipath/{test_name}.plugin -P /tmp/plugins/multipath/addresses_filters/filter_only_42_0_0_0_8.plugin'.format(test_name=test_name)
    elif test_name != 'plain':
        plugins = '-P /tmp/plugins/{test_name}/{test_name}.plugin'.format(test_name=test_name)

    server_logs = "-l /dev/null"

    sysctl_cmds = ["sysctl -w net.ipv4.udp_mem='65536 131072 262144'", 'sysctl -w net.ipv4.udp_rmem_min=16384', 'sysctl -w net.ipv4.udp_wmem_min=16384']
    for cmd in sysctl_cmds:
        client.run_cmd(cmd)
        server.run_cmd(cmd)

    file_sizes = kwargs['file_sizes']
    for size in file_sizes:
        print "file size %d" % size
        def run():
            # It's safer to restart each time actually...
            server.run_cmd('pkill picoquicdemo')
            # Get rid of the variability of processes
            server.run_cmd(["sh", "-c", "'cd ~/picoquic; nohup nice --20 ./picoquicdemo -a 1 {} {} -p 4443 2>&1 > /tmp/log_server.log'".format(server_logs, plugins)], daemon=True)
            server_ip = '42.0.0.1'

            # Empty the buffers and let the server start quietly
            time.sleep(0.2)

            # Get rid of the variability of processes
            client_cmd = 'timeout 60 nice --20 ~/picoquic/picoquicdemo -a 1 -4 -G {} {} -l /dev/null {} 4443 2>&1 > /tmp/log_client.log'.format(size, plugins, server_ip)
            err = client.run_cmd(client_cmd)

            if err != 0:
                print("client returned err %d" % err)
                return 0

            # Get the file to access it
            client.scp_file_from_node('/tmp/log_client.log', 'log_client.log')
            server.scp_file_from_node('/tmp/log_server.log', 'log_server.log')
            log_client = open('log_client.log')
            lines = log_client.readlines()
            elapsed_ms_str = lines[-2].split()[0]
            if elapsed_ms_str.startswith('-') or len([1 for line in lines if "Received file /doc-{}.html, after {} bytes, closing stream 4".format(size, size) in line]) == 0:
                print lines
                print "Error for this run..."
                # Relaunch the server
                return 0

            elf_us = 0
            plugin_us = 0
            total_plugin_us = 0
            for line in lines:
                if "ELF_load" in line:
                    elf_us += int(line.split()[-1])
                elif "Plugin_load" in line:
                    plugin_us += int(line.split()[-1])
                elif "Plugin_insert_plugins_from_fnames" in line:
                    total_plugin_us += int(line.split()[-1])

            print "elapsed: %s milliseconds for %s, elf_us %d, plugin_us %d total_plugin_us %d" % (elapsed_ms_str, test_name, elf_us, plugin_us, total_plugin_us)
            return float(elapsed_ms_str), elf_us, plugin_us, total_plugin_us

        results = list(filter(lambda x: x, sorted(run() for _ in range(1))))
        results, elf_us, plugin_us, total_plugin_us = [r[0] for r in results if r[0] > 0], results[0][1] if len(results) > 0 else 0, results[0][2] if len(results) > 0 else 0, results[0][3] if len(results) > 0 else 0
        median = results[int(len(results)/2)] if results else 0
        print "index = %d median = %dms elf_us = %d plugin_us = %d total_plugin_us = %d" % (index, median, elf_us, plugin_us, total_plugin_us)
        store_result_in_db_func([test_name, median, index, size, elf_us, plugin_us, total_plugin_us])

    server.run_cmd('pkill picoquicdemo')
    index += 1


def run_experimental_design(test_nets_opts, ranges, run_xp_func,
                            wsp_filename="wsp_owd_8_mp", wsp_rows=8, wsp_cols=139,
                            db_filename='results.db',
                            additional_columns=[],
                            start_func=None,
                            topology_func=None,
                            get_path_cfgs_func=get_path_cfgs_default_func,
                            max_runs=None,
                            xp_kwargs={}):
    from os import sys, path
    dir_path = path.dirname(path.abspath(__file__))
    sys.path.append(dir_path)

    if start_func:
        start_func(**xp_kwargs)

    filename = os.path.join(dir_path, wsp_filename)
    matrix = load_wsp(filename, wsp_rows, wsp_cols)
    gen = ParamsGenerator(ranges, matrix)
    vals = gen.generate_all_values()
    # vals = generate_variance_tests(ranges)

    conn = sqlite3.connect(os.path.join(dir_path, db_filename))
    cursor = conn.cursor()
    sql_create_table = gen.generate_sql_create_table(additional_values=additional_columns)
    print sql_create_table
    cursor.execute(sql_create_table)
    conn.commit()

    for i, v in enumerate(list(vals)[0:]):
        if max_runs and i >= max_runs:
            return

        for key, value in v.items():
            if isinstance(value, list):
                v[key] = value[0]

        if topology_func:
            topology_func(v, **xp_kwargs)

        for test_name, setup_nets_opts in test_nets_opts.iteritems():
            print "net config == " + str(setup_nets_opts)
            print "v == " + str(v)

            def store_result_in_db_func(result_array):
                # ugly way to handle failed results...
                values_list = flatten([v[k] for k in sorted(v.keys())]) + result_array
                sql_values_list = gen.generate_sql_insert(values_list)
                print sql_values_list
                cursor.execute(sql_values_list)
                conn.commit()
                print "committed"

            print "experiment %d/%d" % (i + 1, min(len(gen), max_runs))
            run_xp_func(test_name, setup_nets_opts, store_result_in_db_func, **xp_kwargs)


if __name__ == "__main__":
    test_nets_opts = {
        'plain': {},
        'monitoring': {},
        'multipath_rtt': {},
        'fec': {},
        'fec_rlc_gf256_window': {},
        'fec_protect_end_of_stream': {},
        'fec_rlc_gf256_window_protect_end_of_stream_only_inflight': {},
        'multipath_rtt+monitoring': {'plugins': "-P /tmp/plugins/multipath/multipath_rtt.plugin -P /tmp/plugins/multipath/addresses_filters/filter_only_42_0_0_0_8.plugin -P /tmp/plugins/monitoring/monitoring.plugin"},
    }
    ranges = {
        "bw_a": {"range": [5.0, 25.0], "type": float, "count": 1},  # Mbps
        #"loss_a": {"range": [0.1, 2], "type": float, "count": 1},  # %, TODO: Characterise typical losses with LTE
        "delay_ms_a": {"range": [2.5, 25.0], "type": float, "count": 1},  # ms
        "bw_b": {"range": [1000, 1000], "type": float, "count": 1},  # Mbps
        # "loss_b": {"range": [0.01, 1], "type": float, "count": 1},  # %
        "delay_ms_b": {"range": [0, 0], "type": float, "count": 1},  # ms
    }
    additional_columns = [('test_name', str), ('elapsed_time', float), ('test_num', int), ('file_size', int), ('elf_load', int), ('plugin_load', int), ('total_plugin_load', int)]
    xp_kwargs = {'file_sizes': (1000000000,)}

    run_experimental_design(test_nets_opts, ranges, run_benchmark_xp,
                            db_filename='results_benchmark_mc.db',
                            additional_columns=additional_columns,
                            topology_func=symmetric_topo,
                            max_runs=50,
                            xp_kwargs=xp_kwargs)
