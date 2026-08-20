#!/usr/bin/env python3
"""
scripts/mininet_topo.py
Custom Mininet topology for multi-controller setup.
Run:  sudo python3 scripts/mininet_topo.py
"""
from mininet.net  import Mininet
from mininet.topo import Topo
from mininet.node import RemoteController, OVSSwitch
from mininet.cli  import CLI
from mininet.log  import setLogLevel

class TreeTopo(Topo):
    def build(self):
        s1 = self.addSwitch("s1")
        for i in range(2, 5):
            sw = self.addSwitch(f"s{i}")
            self.addLink(s1, sw)
            for j in range(3):
                h = self.addHost(f"h{(i-2)*3+j+1}")
                self.addLink(sw, h)

def run():
    setLogLevel("info")
    topo = TreeTopo()
    net  = Mininet(topo=topo, switch=OVSSwitch,
                   controller=None, autoSetMacs=True)
    net.addController("c0", controller=RemoteController,
                      ip="127.0.0.1", port=6633)
    net.start()
    print("\n[Mininet] topology started")
    print("  Try: pingall, net, dump")
    CLI(net)
    net.stop()

if __name__ == "__main__":
    run()
