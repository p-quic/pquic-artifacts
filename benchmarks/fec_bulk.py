import comp
import time
from ED_benchmark_comp import run_experimental_design, int, float, str, get_path_cfgs_default_func

SERVER_IP = '42.2.1.1'
SERVER_PORT = 4443
CLIENT_IP_1 = '42.0.1.1'
CLIENT_IP_2 = '42.0.2.1'

def run_fec_xp(nodes, test_name, setup_nets_opts, store_result_in_db_func, **kwargs):
    plugins = ""
    if setup_nets_opts['fec'] and setup_nets_opts['fec_only_end']:
        plugins = "-P ~/picoquic/plugins/fec/fec_rlc_gf256_window_protect_end_of_stream_only_inflight.plugin -P ~/picoquic/plugins/no_pacing/no_pacing.plugin"
    elif setup_nets_opts['fec']:
        plugins = "-P ~/picoquic/plugins/fec/fec_rlc_gf256_window.plugin -P ~/picoquic/plugins/no_pacing/no_pacing.plugin"
    else:
        plugins = "-P ~/picoquic/plugins/no_pacing/no_pacing.plugin"

    server_logs = ""
    if setup_nets_opts["log_server"]:
        server_logs = "-l {}".format(setup_nets_opts["log_server"])

    comp.run_cmd_on_client(nodes, 'pkill picoquic')
    comp.run_cmd_on_server(nodes, 'pkill picoquic')
    comp.run_cmd_on_client(nodes, 'pkill ab')
    comp.run_cmd_on_server(nodes, 'pkill lighttpd')
    comp.run_cmd_on_client(nodes, 'pkill client')
    comp.run_cmd_on_server(nodes, 'pkill server')
    comp.run_cmd_on_client(nodes, 'rm -rf /tmp/*.log /tmp/cache*')
    comp.run_cmd_on_server(nodes, 'rm -rf /tmp/*.log /tmp/random*')
    # Unfortunalely, it is a very complicated command, so provide the array directly
    comp.run_cmd_on_server(nodes, ["sh", "-c", "'cd ~/picoquic; nohup ./picoquicdemo {} {} -p 4443 2>&1 > /tmp/log_server.log'".format(server_logs, plugins)], daemon=True)

    file_sizes = kwargs['file_sizes']
    for size in file_sizes:
        print "file size %d" % size
        def run():
            for cmd in comp.tc_dropper_reset(nodes["comp5"].links["comp1"]['ifname']):
                print nodes["comp5"].name, "should be comp5"
                nodes["comp5"].run_cmd(cmd)
            for cmd in comp.tc_dropper_reset(nodes["comp1"].links["comp5"]['ifname']):
                nodes["comp1"].run_cmd(cmd)
                print nodes["comp1"].name, "should be comp1"
            # It's safer to restart each time actually...
            comp.run_cmd_on_server(nodes, 'pkill picoquicdemo')
            comp.run_cmd_on_server(nodes, ["sh", "-c", "'cd ~/picoquic; nohup ./picoquicdemo {} {} -p 4443 2>&1 > /tmp/log_server.log'".format(server_logs, plugins)], daemon=True)
            server_ip = SERVER_IP
            # Empty the buffers and let the server start quietly
            time.sleep(0.2)

            client_cmd = 'timeout 120 ~/picoquic/picoquicdemo -4 -G {} {} -l /dev/null {} 4443 2>&1 > /tmp/log_client.log'.format(size, plugins, server_ip)
            err = comp.run_cmd_on_client(nodes, client_cmd)

            if err != 0:
                print("client returned err %d" % err)
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
                return 0

            print "elapsed: %s milliseconds for %s" % (elapsed_ms_str, test_name)
            return float(elapsed_ms_str)

        results = list(filter(lambda x: x, sorted(run() for _ in range(5))))
        results = [r for r in results if r > 0]
        avg = sum(results) / len(results) if results else 0
        median = results[int(len(results)/2)] if results else 0
        std_dev = sum(abs(x - avg) for x in results) / len(results) if results else 0
        print "median = %dms, avg = %dms, std_dev = %dms" % (median, avg, std_dev)
        store_result_in_db_func([test_name, median, std_dev, size])

    comp.run_cmd_on_server(nodes, 'pkill picoquicdemo')


if __name__ == "__main__":
    def get_path_cfgs(v, exp_index=None, **kwargs):
        cfgs = get_path_cfgs_default_func(v, **kwargs)
        for val in cfgs.values():
            val["use_dropper"] = True
        seed = exp_index + 1
        cfgs['path_1_cfg']['loss'] = v['loss_a']
        cfgs['path_1_cfg']['seed'] = seed
        cfgs['path_1_cfg']['server_ip'] = SERVER_IP
        cfgs['path_1_cfg']['server_port'] = SERVER_PORT
        cfgs['path_1_cfg']['client_ip'] = CLIENT_IP_1
        cfgs['path_1_cfg']['client_ip'] = CLIENT_IP_1

        # cfgs['path_2_cfg']['loss'] = v['loss_b']
        # cfgs['path_2_cfg']['seed'] = seed + 500
        # cfgs['path_2_cfg']['server_ip'] = SERVER_IP
        # cfgs['path_2_cfg']['server_port'] = SERVER_PORT
        # cfgs['path_2_cfg']['client_ip'] = CLIENT_IP_2

        return cfgs

    test_nets_opts = {
        'sp_fec': {'fec': True, 'fec_only_end': False, 'multipath': False, 'log_server': "/dev/null"},
        'sp_fec_only_end': {'fec': True, 'fec_only_end': True, 'multipath': False, 'log_server': "/dev/null"},
        'sp_non_fec': {'fec': False, 'fec_only_end': False, 'multipath': False, 'log_server': "/dev/null"},
    }
    ranges_default = {
        "bw_a": {"range": [5.0, 50.0], "type": float, "count": 1},  # Mbps
        "loss_a": {"range": [0.1, 2], "type": float, "count": 1},  # %
        "delay_ms_a": {"range": [2.5, 25.0], "type": float, "count": 1},  # ms
        #"bw_b": {"range": [5.0, 50.0], "type": float, "count": 1},  # Mbps
        #"loss_b": {"range": [0.01, 1], "type": float, "count": 1},  # %
        #"delay_ms_b": {"range": [2.5, 25.0], "type": float, "count": 1},  # ms
    }

    ranges_fec = {
        "bw_a": {"range": [0.3, 10], "type": float, "count": 1},  # Mbps
        "loss_a": {"range": [1, 8], "type": float, "count": 1},  # %
        "delay_ms_a": {"range": [100, 400], "type": float, "count": 1},  # ms
    }
    additional_columns = [('test_name', str), ('elapsed_time', float), ('std_dev_time', float), ('file_size', int)]
    xp_kwargs = {'file_sizes': (1000, 10000, 50000, 1000000)}

    comp.TC_EXEC = "~/iproute2-4.18.0/tc/tc"
    run_experimental_design(test_nets_opts, ranges_fec, run_fec_xp,
                            db_filename='results_fec_sym_with_tiray4.db',
                            additional_columns=additional_columns,
                            xp_kwargs=xp_kwargs,
                            get_path_cfgs_func=get_path_cfgs)
