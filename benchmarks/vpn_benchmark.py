import os

import comp
import time
from ED_benchmark_comp import run_experimental_design, int, float, str


def symmetric_topo(v, **kwargs):
    # This is not clean, but it works...
    v["delay_ms_a"] = v["delay_ms_b"]
    v["bw_a"] = v["bw_b"]


def run_vpn(nodes, test_name, setup_nets_opts, store_result_in_db_func, **kwargs):
    server_ip = '42.2.1.1'

    comp.run_cmd_on_client(nodes, 'pkill picoquic')
    comp.run_cmd_on_server(nodes, 'pkill picoquic')
    comp.run_cmd_on_client(nodes, 'pkill ab')
    comp.run_cmd_on_server(nodes, 'pkill lighttpd')
    comp.run_cmd_on_client(nodes, 'pkill client')
    comp.run_cmd_on_server(nodes, 'pkill server')
    comp.run_cmd_on_client(nodes, 'rm -rf /tmp/*.log /tmp/cache*')
    comp.run_cmd_on_server(nodes, 'rm -rf /tmp/*.log /tmp/random*')

    lighttpd_conf = """
server.document-root = "/tmp" 
dir-listing.activate = "enable"
server.pid-file      = "/var/run/lighttpd.pid"
server.port          = 8080
"""

    if test_name == "sp_vpn":
        # Add tun0/tun1
        comp.run_cmd_on_client(nodes, 'ip tuntap add mode tun dev tun0')
        comp.run_cmd_on_client(nodes, 'ip addr add 43.0.0.2/24 dev tun0')
        comp.run_cmd_on_client(nodes, 'ip link set dev tun0 mtu 1400')
        comp.run_cmd_on_client(nodes, 'ip link set dev tun0 up')

        comp.run_cmd_on_client(nodes, 'ip addr add 128.0.0.2/32 dev lo')
        comp.run_cmd_on_client(nodes, 'ip route add 128.0.0.1/32 via 43.0.0.2 dev tun0')

        comp.run_cmd_on_server(nodes, 'ip tuntap add mode tun dev tun1')
        comp.run_cmd_on_server(nodes, 'ip addr add 43.0.0.1/24 dev tun1')
        comp.run_cmd_on_server(nodes, 'ip link set dev tun1 mtu 1400')
        comp.run_cmd_on_server(nodes, 'ip link set dev tun1 up')

        comp.run_cmd_on_server(nodes, 'ip addr add 128.0.0.1/32 dev lo')
        comp.run_cmd_on_server(nodes, 'ip route add 128.0.0.2/32 via 43.0.0.1 dev tun1')

        # Start the VPN server and client
        plugins = "-P ~/picoquic/plugins/datagram/datagram.plugin"
        if setup_nets_opts['multipath']:
            plugins = "-P ~/picoquic/plugins/multipath/multipath_rr.plugin"

        server_logs = ""
        if setup_nets_opts["log_server"]:
            server_logs = "-l {}".format(setup_nets_opts["log_server"])

        comp.run_cmd_on_server(nodes, 'pkill picoquicvpn')
        comp.run_cmd_on_client(nodes, 'pkill picoquicvpn')

        # Unfortunalely, it is a very complicated command, so provide the array directly
        comp.run_cmd_on_server(nodes, ["sh", "-c", "'cd ~/picoquic; nohup ./picoquicvpn {} {} -p 4443 2>&1 > /tmp/log_server.log'".format(server_logs, plugins)], daemon=True)

        time.sleep(1)
        comp.run_cmd_on_client(nodes, ["sh", "-c", "'~/picoquic/picoquicvpn {} {} 4443 2>&1 > /tmp/log_client.log'".format(plugins, server_ip)], daemon=True)
        time.sleep(1)

        lighttpd_conf += 'server.bind = "128.0.0.1"\n'

    comp.run_cmd_on_server(nodes, 'pkill lighttpd')
    comp.run_cmd_on_server(nodes, ["echo", "'%s'" % lighttpd_conf, "> ~/lighttpd.conf"], daemon=True)
    comp.run_cmd_on_server(nodes, ["lighttpd", "-f", "~/lighttpd.conf"], daemon=True)

    file_sizes = kwargs['file_sizes']
    for size in file_sizes:
        print "file size %d" % size
        comp.run_cmd_on_server(nodes, 'dd if=/dev/urandom of=/tmp/random_{size} bs={size} count=1'.format(size=size))

        def run():
            start_time = time.time()
            additional_curl_params = ''
            if test_name == 'sp_vpn':
                additional_curl_params = '--interface {}'.format('128.0.0.2')
            err = comp.run_cmd_on_client(nodes, 'curl {}:8080/random_{} -s --connect-timeout 5 --output /dev/null -w "%{{time_total}}" {} > /tmp/curl.log'.format(
                '128.0.0.1' if test_name == 'sp_vpn' else server_ip, size, additional_curl_params)
            )

            elapsed_ms = (time.time() - start_time) * 1000

            if err != 0:
                print("client returned err %d" % err)
                return 0

                # Get the file to access it
            comp.scp_file_from_client(nodes, '/tmp/curl.log', 'curl.log')
            with open('curl.log') as f:
                lines = f.readlines()
            elapsed_ms = float(lines[-1]) * 1000
            print "elapsed: %f milliseconds for %s" % (elapsed_ms, test_name)
            return elapsed_ms

        results = list(filter(lambda x: x, sorted(run() for _ in range(9))))
        results = [r for r in results if r > 0]
        avg = sum(results) / len(results) if results else 0
        median = results[int(len(results)/2)] if results else 0
        std_dev = sum(abs(x - avg) for x in results) / len(results) if results else 0
        print "median = %dms, avg = %dms, std_dev = %dms" % (median, avg, std_dev)
        store_result_in_db_func([test_name, median, std_dev, size])

    comp.run_cmd_on_server(nodes, 'pkill lighttpd')

    if test_name == 'sp_vpn':
        comp.run_cmd_on_client(nodes, 'pkill picoquicvpn')
        comp.run_cmd_on_server(nodes, 'pkill picoquicvpn')

        comp.run_cmd_on_server(nodes, 'ip tuntap del mode tun dev tun1')
        comp.run_cmd_on_client(nodes, 'ip tuntap del mode tun dev tun0')

        comp.run_cmd_on_client(nodes, 'ip addr del 128.0.0.2/32 dev lo')
        comp.run_cmd_on_server(nodes, 'ip addr del 128.0.0.1/32 dev lo')


if __name__ == "__main__":
    test_nets_opts = {
        'datagram': {'multipath': False, 'log_server': "/dev/null"},
    }
    ranges = {
        "bw_a": {"range": [1000, 1000], "type": float, "count": 1},  # Mbps
        # "loss_a": {"range": [0.1, 2], "type": float, "count": 1},  # %, TODO: Characterise typical losses with LTE
        "delay_ms_a": {"range": [0, 0], "type": float, "count": 1},  # ms
        "bw_b": {"range": [1000, 1000], "type": float, "count": 1},  # Mbps
        # "loss_b": {"range": [0.01, 1], "type": float, "count": 1},  # %
        "delay_ms_b": {"range": [0, 0], "type": float, "count": 1},  # ms
    }
    additional_columns = [('test_name', str), ('elapsed_time', float), ('std_dev_time', float), ('file_size', int)]
    xp_kwargs = {'file_sizes': (100000000,)}

    run_experimental_design(test_nets_opts, ranges, run_vpn,
                            db_filename='results_benchmark_vpn.db',
                            additional_columns=additional_columns,
                            topology_func=symmetric_topo,
                            xp_kwargs=xp_kwargs)
