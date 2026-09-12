from mininet.net import Mininet
from mininet.node import RemoteController, OVSSwitch
from mininet.cli import CLI
from mininet.log import setLogLevel


def run():

    net = Mininet(switch=OVSSwitch)

    # =========================
    # Controllers
    # =========================

    c1 = net.addController(
        'c1',
        controller=RemoteController,
        ip='127.0.0.1',
        port=6633
    )

    c2 = net.addController(
        'c2',
        controller=RemoteController,
        ip='127.0.0.1',
        port=6634
    )

    c3 = net.addController(
        'c3',
        controller=RemoteController,
        ip='127.0.0.1',
        port=6635
    )

    # =========================
    # Switches
    # =========================

    s1 = net.addSwitch('s1')
    s2 = net.addSwitch('s2')
    s3 = net.addSwitch('s3')

    # =========================
    # Hosts
    # =========================

    hosts = []

    for i in range(1, 10):
        h = net.addHost(f'h{i}')
        hosts.append(h)

    # =========================
    # Host ↔ Switch Links
    # =========================

    # h1-h3 → s1
    net.addLink(hosts[0], s1)
    net.addLink(hosts[1], s1)
    net.addLink(hosts[2], s1)

    # h4-h6 → s2
    net.addLink(hosts[3], s2)
    net.addLink(hosts[4], s2)
    net.addLink(hosts[5], s2)

    # h7-h9 → s3
    net.addLink(hosts[6], s3)
    net.addLink(hosts[7], s3)
    net.addLink(hosts[8], s3)

    # =========================
    # Switch ↔ Switch Links
    # =========================

    net.addLink(s1, s2)
    net.addLink(s2, s3)

    # =========================
    # Build Network
    # =========================

    net.build()

    # =========================
    # Assign Controllers
    # =========================

    s1.start([c1, c2])
    s2.start([c2, c3])
    s3.start([c3, c1])

    print("\n=== Multi-Controller SDN Started ===")
    print("s1 -> ctrl_01 (6633), ctrl_02 (6634)")
    print("s2 -> ctrl_02 (6634), ctrl_03 (6635)")
    print("s3 -> ctrl_03 (6635), ctrl_01 (6633)")
    print("9 hosts connected (h1-h9)")
    print("====================================\n")

    CLI(net)

    net.stop()


if __name__ == '__main__':
    setLogLevel('info')
    run()
