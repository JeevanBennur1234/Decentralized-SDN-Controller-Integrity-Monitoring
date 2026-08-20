"""
controller/ryu_controller.py
Full L2 MAC-learning switch with Integrity Agent + Gossip embedded.

Run one instance per controller:
  CONTROLLER_ID=ctrl_01 ryu-manager controller/ryu_controller.py
  CONTROLLER_ID=ctrl_02 ryu-manager controller/ryu_controller.py  (separate terminal)
  CONTROLLER_ID=ctrl_03 ryu-manager controller/ryu_controller.py  (separate terminal)

L2 learning:
  - switch_features → install table-miss rule (send unknown to controller)
  - packet_in → learn src MAC, look up dst MAC, flood or unicast
  - install flow rule for known dst so future packets bypass controller
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ryu.base            import app_manager
from ryu.controller      import ofp_event
from ryu.controller.handler import MAIN_DISPATCHER, CONFIG_DISPATCHER, set_ev_cls
from ryu.ofproto         import ofproto_v1_3
from ryu.lib.packet      import packet, ethernet, ether_types

from integrity.agent  import IntegrityAgent
from gossip.node      import GossipNode
from gossip.server    import run_gossip_server
from shared.config    import CONTROLLERS, get_cid
from shared.logger    import get_logger

log    = get_logger("controller")
CID    = get_cid()
C_INFO = CONTROLLERS.get(CID, CONTROLLERS["ctrl_01"])


class SecureController(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.mac_to_port = {}
        log.info(f"SecureController starting as [{CID}]")

        # Start integrity agent (generates keys, initialises chain, writes state)
        self.agent = IntegrityAgent(cid=CID)

        # Start gossip node + its HTTP server
        self.gossip = GossipNode(cid=CID, agent=self.agent)
        run_gossip_server(self.gossip)
        self.gossip.start()

        log.info(f"[{CID}] All subsystems online | gossip_port={C_INFO['gossip_port']}")

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def _switch_up(self, ev):
        dp, of, pa = ev.msg.datapath, ev.msg.datapath.ofproto, ev.msg.datapath.ofproto_parser
        # Table-miss: everything unmatched → controller
        dp.send_msg(pa.OFPFlowMod(
            datapath=dp, priority=0,
            match=pa.OFPMatch(),
            instructions=[pa.OFPInstructionActions(of.OFPIT_APPLY_ACTIONS,
                          [pa.OFPActionOutput(of.OFPP_CONTROLLER, of.OFPCML_NO_BUFFER)])]))
        self.agent.on_switch_up(dp.id)

    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def _pkt_in(self, ev):
        msg = ev.msg
        dp  = msg.datapath
        of  = dp.ofproto
        pa  = dp.ofproto_parser
        in_port = msg.match["in_port"]

        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocols(ethernet.ethernet)[0]
        if eth.ethertype == ether_types.ETH_TYPE_LLDP:
            return

        dst, src, dpid = eth.dst, eth.src, dp.id
        self.mac_to_port.setdefault(dpid, {})[src] = in_port
        out_port = self.mac_to_port[dpid].get(dst, of.OFPP_FLOOD)
        actions  = [pa.OFPActionOutput(out_port)]

        if out_port != of.OFPP_FLOOD:
            match = pa.OFPMatch(in_port=in_port, eth_dst=dst, eth_src=src)
            self._flow(dp, 1, match, actions)
            self.agent.on_flow_add(dpid, 1, str(match))

        data = msg.data if msg.buffer_id == of.OFP_NO_BUFFER else None
        dp.send_msg(pa.OFPPacketOut(
            datapath=dp, buffer_id=msg.buffer_id,
            in_port=in_port, actions=actions, data=data))
        self.agent.on_packet_in(dpid, src, dst, in_port, out_port)

    def _flow(self, dp, pri, match, actions, idle=30):
        of, pa = dp.ofproto, dp.ofproto_parser
        dp.send_msg(pa.OFPFlowMod(
            datapath=dp, priority=pri, match=match, idle_timeout=idle,
            instructions=[pa.OFPInstructionActions(of.OFPIT_APPLY_ACTIONS, actions)]))
