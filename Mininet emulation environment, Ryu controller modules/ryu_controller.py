import json
from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER, DEAD_DISPATCHER, set_ev_cls
from ryu.ofproto import ofproto_v1_3
from ryu.app.wsgi import ControllerBase, WSGIApplication, route
from ryu.lib import hub
from webob import Response

sdn_instance_name = 'sdn_rest_api_app'

class SDNControllerApp(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]
    _CONTEXTS = {'wsgi': WSGIApplication}

    def __init__(self, *args, **kwargs):
        super(SDNControllerApp, self).__init__(*args, **kwargs)
        self.datapaths = {}
        self.mac_to_port = {}
        
        self.mac_stats = {}

        wsgi = kwargs['wsgi']
        wsgi.register(SDNRestController, {sdn_instance_name: self})

        self.monitor_thread = hub.spawn(self._monitor)

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        datapath = ev.msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        self.datapaths[datapath.id] = datapath

        match = parser.OFPMatch()
        actions = [parser.OFPActionOutput(ofproto.OFPP_CONTROLLER, ofproto.OFPCML_NO_BUFFER)]
        self.add_flow(datapath, 0, match, actions)

    @set_ev_cls(ofp_event.EventOFPStateChange, [MAIN_DISPATCHER, DEAD_DISPATCHER])
    def _state_change_handler(self, ev):
        datapath = ev.datapath
        if ev.state == MAIN_DISPATCHER:
            if datapath.id not in self.datapaths:
                self.datapaths[datapath.id] = datapath
        elif ev.state == DEAD_DISPATCHER:
            if datapath.id in self.datapaths:
                del self.datapaths[datapath.id]

    def _monitor(self):
        while True:
            for dp in self.datapaths.values():
                self._request_stats(dp)
            hub.sleep(2)

    def _request_stats(self, datapath):
        parser = datapath.ofproto_parser
        req = parser.OFPFlowStatsRequest(datapath)
        datapath.send_msg(req)

    @set_ev_cls(ofp_event.EventOFPFlowStatsReply, MAIN_DISPATCHER)
    def _flow_stats_reply_handler(self, ev):
        body = ev.msg.body
        for stat in body:
            if 'eth_src' in stat.match:
                mac = stat.match['eth_src']
                prev_bytes = self.mac_stats.get(mac, {}).get('byte_count', stat.byte_count)
                prev_packets = self.mac_stats.get(mac, {}).get('packet_count', stat.packet_count)

                self.mac_stats[mac] = {
                    'byte_count': stat.byte_count,
                    'packet_count': stat.packet_count,
                    'delta_bytes': max(0, stat.byte_count - prev_bytes),
                    'delta_packets': max(0, stat.packet_count - prev_packets)
                }

    def add_flow(self, datapath, priority, match, actions, buffer_id=None, idle=0, hard=0):
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        inst = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS, actions)]
        if buffer_id:
            mod = parser.OFPFlowMod(datapath=datapath, buffer_id=buffer_id,
                                    priority=priority, match=match,
                                    idle_timeout=idle, hard_timeout=hard,
                                    instructions=inst)
        else:
            mod = parser.OFPFlowMod(datapath=datapath, priority=priority,
                                    match=match, idle_timeout=idle,
                                    hard_timeout=hard, instructions=inst)
        datapath.send_msg(mod)

    def block_mac(self, src_mac):
        for dp in self.datapaths.values():
            parser = dp.ofproto_parser
            match = parser.OFPMatch(eth_src=src_mac)
            self.add_flow(dp, priority=100, match=match, actions=[])
        print(f"[SDN Controller] Blocked MAC: {src_mac}")

    def set_flow_path(self, src_mac, path_id=1):
        out_port = 1 if path_id == 1 else 2
        for dp in self.datapaths.values():
            parser = dp.ofproto_parser
            match = parser.OFPMatch(eth_src=src_mac)
            actions = [parser.OFPActionOutput(out_port)]
            self.add_flow(dp, priority=80, match=match, actions=actions)
        print(f"[SDN Controller] Set Path {path_id} (Port {out_port}) for MAC: {src_mac}")

    def limit_bandwidth(self, src_mac, limit_percent=50):
        for dp in self.datapaths.values():
            parser = dp.ofproto_parser
            match = parser.OFPMatch(eth_src=src_mac)
            actions = [parser.OFPActionOutput(dp.ofproto.OFPP_NORMAL)]
            self.add_flow(dp, priority=60, match=match, actions=actions)
        print(f"[SDN Controller] Limited MAC: {src_mac} to {limit_percent}%")

    def set_priority(self, src_mac, priority_level="HIGH"):
        prio_val = 90 if priority_level == "HIGH" else 30
        for dp in self.datapaths.values():
            parser = dp.ofproto_parser
            match = parser.OFPMatch(eth_src=src_mac)
            actions = [parser.OFPActionOutput(dp.ofproto.OFPP_NORMAL)]
            self.add_flow(dp, priority=prio_val, match=match, actions=actions)
        print(f"[SDN Controller] Set Priority {priority_level} for MAC: {src_mac}")

    def allow_traffic(self, src_mac):
        for dp in self.datapaths.values():
            parser = dp.ofproto_parser
            match = parser.OFPMatch(eth_src=src_mac)
            actions = [parser.OFPActionOutput(dp.ofproto.OFPP_NORMAL)]
            self.add_flow(dp, priority=50, match=match, actions=actions)
        print(f"[SDN Controller] Allowed Full Traffic for MAC: {src_mac}")



class SDNRestController(ControllerBase):
    def __init__(self, req, link, data, **config):
        super(SDNRestController, self).__init__(req, link, data, **config)
        self.sdn_app = data[sdn_instance_name]

    @route('sdn', '/sdn/control', methods=['POST'])
    def handle_control(self, req, **kwargs):
        try:
            body = json.loads(req.body)
            src_mac = body.get('src_mac')
            action = body.get('action')

            if not src_mac or not action:
                res_body = json.dumps({"error": "Invalid payload"}).encode('utf-8')
                return Response(status=400, content_type='application/json', body=res_body)

            if action == "BLOCK":
                self.sdn_app.block_mac(src_mac)
            elif action == "ROUTE_PRIMARY":
                self.sdn_app.set_flow_path(src_mac, path_id=1)
            elif action == "ROUTE_SECONDARY":
                self.sdn_app.set_flow_path(src_mac, path_id=2)
            elif action == "LIMIT_50":
                self.sdn_app.limit_bandwidth(src_mac, 50)
            elif action == "LIMIT_10":
                self.sdn_app.limit_bandwidth(src_mac, 10)
            elif action == "PRIORITY_HIGH":
                self.sdn_app.set_priority(src_mac, "HIGH")
            elif action == "PRIORITY_LOW":
                self.sdn_app.set_priority(src_mac, "LOW")
            elif action == "ALLOW_100":
                self.sdn_app.allow_traffic(src_mac)

            res_body = json.dumps({"status": "success"}).encode('utf-8')
            return Response(status=200, content_type='application/json', body=res_body)
        except Exception as e:
            res_body = json.dumps({"error": str(e)}).encode('utf-8')
            return Response(status=500, content_type='application/json', body=res_body)


    @route('sdn', '/sdn/stats', methods=['GET'])
    def handle_stats(self, req, **kwargs):
        try:
            mac = req.GET.get('mac', None)
            
            if mac:
                real_stats = self.sdn_app.mac_stats.get(mac, {'delta_bytes': 0, 'delta_packets': 0})
                stats_data = {
                    "mac": mac,
                    "delta_bytes": real_stats.get('delta_bytes', 0),
                    "delta_packets": real_stats.get('delta_packets', 0)
                }
            
            else:
                stats_data = {
                    target_mac: {
                        "delta_bytes": stats.get('delta_bytes', 0),
                        "delta_packets": stats.get('delta_packets', 0)
                    }
                    for target_mac, stats in self.sdn_app.mac_stats.items()
                }
            
            res_body = json.dumps(stats_data).encode('utf-8')
            return Response(status=200, content_type='application/json', body=res_body)

        except Exception as e:
            res_body = json.dumps({"error": str(e)}).encode('utf-8')
            return Response(status=500, content_type='application/json', body=res_body)