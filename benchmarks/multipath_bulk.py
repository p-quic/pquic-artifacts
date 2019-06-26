import comp
import time
from ED_benchmark_comp import run_experimental_design, int, float, str

def symmetric_topo(v, **kwargs):
    # This is not clean, but it works...
    v["delay_ms_a"] = v["delay_ms_b"]
    v["bw_a"] = v["bw_b"]

def run_multipath_xp(nodes, test_name, setup_nets_opts, store_result_in_db_func, **kwargs):
    plugins = ""
    if setup_nets_opts.get('multipath', False):
        plugins = "-P ~/picoquic/plugins/multipath/multipath_rtt.plugin -P ~/picoquic/plugins/multipath/addresses_filters/filter_no_v6_no_10_no_42-3.plugin"
    else:
        plugins = "-P ~/picoquic/plugins/no_pacing/no_pacing.plugin"

    server_logs = ""
    if setup_nets_opts.get("log_server", False):
        server_logs = "-l {}".format(setup_nets_opts["log_server"])

    def relaunch_config():
        comp.run_cmd_on_client(nodes, 'pkill picoquic')
        comp.run_cmd_on_server(nodes, 'pkill picoquic')
        comp.run_cmd_on_client(nodes, 'pkill ab')
        comp.run_cmd_on_server(nodes, 'pkill lighttpd')
        comp.run_cmd_on_client(nodes, 'pkill client')
        comp.run_cmd_on_server(nodes, 'pkill server')
        comp.run_cmd_on_client(nodes, 'rm -rf /tmp/*.log /tmp/cache*')
        comp.run_cmd_on_server(nodes, 'rm -rf /tmp/*.log /tmp/random*')

        comp.run_cmd_on_server(nodes, 'pkill picoquicdemo')
        time.sleep(1)
        # Unfortunalely, it is a very complicated command, so provide the array directly
        comp.run_cmd_on_server(nodes, ["sh", "-c", "'cd ~/picoquic; nohup ./picoquicdemo {} {} -p 4443 2>&1 > /tmp/log_server.log'".format(server_logs, plugins)], daemon=True)
        time.sleep(1)

    relaunch_config()
    file_sizes = kwargs['file_sizes']
    for size in file_sizes:
        print "file size %d" % size
        def run():
            # It's safer to restart each time actually...
            comp.run_cmd_on_server(nodes, 'pkill picoquicdemo')
            comp.run_cmd_on_server(nodes, ["sh", "-c", "'cd ~/picoquic; nohup ./picoquicdemo {} {} -p 4443 2>&1 > /tmp/log_server.log'".format(server_logs, plugins)], daemon=True)
            server_ip = '42.2.1.1'

            # Empty the buffers and let the server start quietly
            time.sleep(0.2)

            client_cmd = 'timeout 30 ~/picoquic/picoquicdemo -G {} {} -l /dev/null {} 4443 2>&1 > /tmp/log_client.log'.format(size, plugins, server_ip)
            err = comp.run_cmd_on_client(nodes, client_cmd)

            if err != 0:
                print("client returned err %d" % err)
                relaunch_config()
                return 0

            # Get the file to access it
            comp.scp_file_from_client(nodes, '/tmp/log_client.log', 'log_client.log')
            log_client = open('log_client.log')
            lines = log_client.readlines()
            elapsed_ms_str = lines[-2].split()[0]
            if (elapsed_ms_str.startswith('-') or "Client exit with code = 0" not in lines[-1]):
                print lines[-1]
                print "Error for this run..."
                # Relaunch the server
                relaunch_config()
                return 0

            print "elapsed: %s milliseconds for %s" % (elapsed_ms_str, test_name)
            return float(elapsed_ms_str)

        results = list(filter(lambda x: x, sorted(run() for _ in range(9))))
        results = [r for r in results if r > 0]
        avg = sum(results) / len(results) if results else 0
        median = results[int(len(results)/2)] if results else 0
        std_dev = sum(abs(x - avg) for x in results) / len(results) if results else 0
        print "median = %dms, avg = %dms, std_dev = %dms" % (median, avg, std_dev)
        store_result_in_db_func([test_name, median, std_dev, size, len(results)])

    comp.run_cmd_on_server(nodes, 'pkill picoquicdemo')


if __name__ == "__main__":
    test_nets_opts = {
        'sp_quic': {'multipath': False, 'run_client': False, 'log_server': "/dev/null"},
        'mp_quic': {'multipath': True, 'run_client': False, 'log_server': "/dev/null"},
    }
    ranges = {
        "bw_a": {"range": [5.0, 50.0], "type": float, "count": 1},  # Mbps
        #"loss_a": {"range": [0.1, 2], "type": float, "count": 1},  # %, TODO: Characterise typical losses with LTE
        "delay_ms_a": {"range": [2.5, 25.0], "type": float, "count": 1},  # ms
        "bw_b": {"range": [5.0, 50.0], "type": float, "count": 1},  # Mbps
        # "loss_b": {"range": [0.01, 1], "type": float, "count": 1},  # %
        "delay_ms_b": {"range": [2.5, 25.0], "type": float, "count": 1},  # ms
    }
    additional_columns = [('test_name', str), ('elapsed_time', float), ('std_dev_time', float), ('file_size', int), ('num_xps', int)]
    xp_kwargs = {'file_sizes': (1500, 10000, 50000, 1000000, 10000000)}

    run_experimental_design(test_nets_opts, ranges, run_multipath_xp,
                            db_filename='results_mp_sym.db',
                            additional_columns=additional_columns,
                            topology_func=symmetric_topo,
                            xp_kwargs=xp_kwargs)
