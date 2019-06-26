import comp
import time
from ED_benchmark_comp import run_experimental_design, int, float, str

index = 0

def symmetric_topo(v, **kwargs):
    # This is not clean, but it works...
    v["delay_ms_a"] = v["delay_ms_b"]
    v["bw_a"] = v["bw_b"]

def run_benchmark_xp(nodes, test_name, setup_nets_opts, store_result_in_db_func, **kwargs):
    global index

    comp.run_cmd_on_client(nodes, 'pkill picoquic')
    comp.run_cmd_on_server(nodes, 'pkill picoquic')
    comp.run_cmd_on_client(nodes, 'pkill ab')
    comp.run_cmd_on_server(nodes, 'pkill lighttpd')
    comp.run_cmd_on_client(nodes, 'pkill client')
    comp.run_cmd_on_server(nodes, 'pkill server')
    comp.run_cmd_on_client(nodes, 'rm -rf /tmp/*.log /tmp/cache*')
    comp.run_cmd_on_server(nodes, 'rm -rf /tmp/*.log /tmp/random*')
    comp.run_cmd_on_client(nodes, 'rm -rf /tmp/plugins')
    comp.run_cmd_on_server(nodes, 'rm -rf /tmp/plugins')

    comp.run_cmd_on_client(nodes, 'cp -r ~/picoquic/plugins /tmp')
    comp.run_cmd_on_server(nodes, 'cp -r ~/picoquic/plugins /tmp')

    plugins = ""
    if "plugins" in setup_nets_opts:
        plugins = setup_nets_opts["plugins"]
    elif test_name.startswith('fec'):
        plugins = '-P /tmp/plugins/fec/{test_name}.plugin'.format(test_name=test_name)
    elif test_name.startswith('multipath'):
        plugins = '-P /tmp/plugins/multipath/{test_name}.plugin -P /tmp/plugins/multipath/addresses_filters/filter_no_v6_no_10_no_42-3.plugin'.format(test_name=test_name)
    elif test_name != 'plain':
        plugins = '-P /tmp/plugins/{test_name}/{test_name}.plugin'.format(test_name=test_name)

    server_logs = "-l /dev/null"

    sysctl_cmds = ["sysctl -w net.ipv4.udp_mem='65536 131072 262144'", 'sysctl -w net.ipv4.udp_rmem_min=16384', 'sysctl -w net.ipv4.udp_wmem_min=16384']
    for cmd in sysctl_cmds:
        comp.run_cmd_on_client(nodes, cmd)
        comp.run_cmd_on_server(nodes, cmd)

    file_sizes = kwargs['file_sizes']
    for size in file_sizes:
        print "file size %d" % size
        def run():
            # It's safer to restart each time actually...
            comp.run_cmd_on_server(nodes, 'pkill picoquicdemo')
            # Get rid of the variability of processes
            comp.run_cmd_on_server(nodes, ["sh", "-c", "'cd ~/picoquic; nohup nice --20 ./picoquicdemo {} {} -p 4443 2>&1 > /tmp/log_server.log'".format(server_logs, plugins)], daemon=True)
            server_ip = '42.2.1.1'

            # Empty the buffers and let the server start quietly
            time.sleep(0.2)

            # Get rid of the variability of processes
            client_cmd = 'timeout 40 nice --20 ~/picoquic/picoquicdemo -4 -G {} {} -l /dev/null {} 4443 2>&1 > /tmp/log_client.log'.format(size, plugins, server_ip)
            err = comp.run_cmd_on_client(nodes, client_cmd)

            if err != 0:
                print("client returned err %d" % err)
                return 0

            # Get the file to access it
            comp.scp_file_from_client(nodes, '/tmp/log_client.log', 'log_client.log')
            log_client = open('log_client.log')
            lines = log_client.readlines()
            elapsed_ms_str = lines[-2].split()[0]
            if elapsed_ms_str.startswith('-') or len([1 for line in lines if "Received file /doc-{}.html, after {} bytes, closing stream 4".format(size, size) in line]) == 0:
                print lines[-1]
                print "Error for this run..."
                # Relaunch the server
                return 0

            elf_us = 0
            plugin_us = 0
            for line in lines:
                if "ELF_load" in line:
                    elf_us += int(line.split()[-1])
                elif "Plugin_load" in line:
                    plugin_us += int(line.split()[-1])

            print "elapsed: %s milliseconds for %s, elf_us %d, plugin_us %d" % (elapsed_ms_str, test_name, elf_us, plugin_us)
            return float(elapsed_ms_str), elf_us, plugin_us

        results = list(filter(lambda x: x, sorted(run() for _ in range(1))))
        results, elf_us, plugin_us = [r[0] for r in results if r[0] > 0], results[0][1] if len(results) > 0 else 0, results[0][2] if len(results) > 0 else 0
        median = results[int(len(results)/2)] if results else 0
        print "index = %d median = %dms elf_us = %d plugin_us = %d" % (index, median, elf_us, plugin_us)
        store_result_in_db_func([test_name, median, index, size, elf_us, plugin_us])

    comp.run_cmd_on_server(nodes, 'pkill picoquicdemo')
    index += 1


if __name__ == "__main__":
    test_nets_opts = {
        'plain': {},
        'monitoring': {},
        'multipath_rtt': {},
        'fec': {},
        'fec_rlc_gf256_window': {},
        'fec_protect_end_of_stream': {},
        'fec_rlc_gf256_window_protect_end_of_stream_only_inflight': {},
        'multipath_rtt+monitoring': {'plugins': "-P /tmp/plugins/multipath/multipath_rtt.plugin -P /tmp/plugins/multipath/addresses_filters/filter_no_v6_no_10_no_42-3.plugin -P /tmp/plugins/monitoring/monitoring.plugin"},
    }
    ranges = {
        "bw_a": {"range": [5.0, 25.0], "type": float, "count": 1},  # Mbps
        #"loss_a": {"range": [0.1, 2], "type": float, "count": 1},  # %, TODO: Characterise typical losses with LTE
        "delay_ms_a": {"range": [2.5, 25.0], "type": float, "count": 1},  # ms
        "bw_b": {"range": [1000, 1000], "type": float, "count": 1},  # Mbps
        # "loss_b": {"range": [0.01, 1], "type": float, "count": 1},  # %
        "delay_ms_b": {"range": [0, 0], "type": float, "count": 1},  # ms
    }
    additional_columns = [('test_name', str), ('elapsed_time', float), ('test_num', int), ('file_size', int), ('elf_load', int), ('plugin_load', int)]
    xp_kwargs = {'file_sizes': (150000000,  )}

    run_experimental_design(test_nets_opts, ranges, run_benchmark_xp,
                            db_filename='results_benchmark.db',
                            additional_columns=additional_columns,
                            topology_func=symmetric_topo,
                            max_runs=50,
                            xp_kwargs=xp_kwargs)
