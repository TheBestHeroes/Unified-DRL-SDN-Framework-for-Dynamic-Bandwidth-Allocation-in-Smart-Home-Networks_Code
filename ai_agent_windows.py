import os
import time
import pandas as pd
import numpy as np
import requests
import atexit
import sys

from User_Behavior_Model.agent import UserBehaviorClassifier
from DRL_Decision_Engine_DQN.DRL_Agent import DRLDecisionAgent, calculate_qos_reward, ACTIONS


CONTROL_URL = "http://127.0.0.1:8080/sdn/control"
STATS_URL = "http://127.0.0.1:8080/sdn/stats"
CSV_FILE = "simulation_results.csv"
DQN_MODEL_PATH = 'dqn_warmstart_model.pth'

NETWORK_NODES = [
    {"mac": "00:00:00:00:00:01", "name": "h1_user_video"},
    {"mac": "00:00:00:00:00:02", "name": "h2_iot_device"},
    {"mac": "00:00:00:00:00:03", "name": "h3_normal_user"},
    {"mac": "00:00:00:00:00:04", "name": "h4_heavy_traffic"}
]



behavior_model = UserBehaviorClassifier()
drl_agent = DRLDecisionAgent(state_dim=3, action_dim=8)

csv_headers = [
    'Timestamp', 'Node_MAC', 'Node_Name', 'Predicted_Behavior', 
    'Delta_Bytes', 'Delta_Packets', 'Throughput_Mbps', 
    'Latency_ms', 'Jitter_ms', 'Packet_Loss_Ratio', 
    'Fairness_Index', 'Action', 'Reward'
]


if os.path.exists(DQN_MODEL_PATH):
    print("[Warm-Start] Loading pre-trained DQN model weights...")
    drl_agent.load_weights(DQN_MODEL_PATH)
elif os.path.exists(CSV_FILE):
    print("[Warm-Start] Pre-training DQN model using historical data...")
    drl_agent.pretrain_offline(dataset_path=CSV_FILE, epochs=20)
    drl_agent.save_weights(DQN_MODEL_PATH)
else:
    print("[Warm-Start] No PTH or CSV found. Starting DQN with random initialization.")



def on_shutdown():
    print("\n[*] Shutting down AI Agent...")

    if os.path.exists(CSV_FILE):
        print("[*] Re-training ML behavior model from CSV...")
        behavior_model.train_and_save_from_csv(CSV_FILE)


    if 'drl_agent' in globals():
        print(f"[*] Saving updated DQN weights to '{DQN_MODEL_PATH}'...")
        drl_agent.save_weights(DQN_MODEL_PATH)

    print("[*] All state weights saved successfully. Goodbye!")

atexit.register(on_shutdown)


pd.DataFrame(columns=csv_headers).to_csv(CSV_FILE, index=False)



print("[*] Launching AI Agent Windows Orchestrator...")
session = requests.Session()
timestamp = 1

try:
    if os.path.exists('dqn_warmstart_model.pth'):
        print("[Warm-Start] Loading pre-trained DQN model weights...")
        drl_agent.load_weights('dqn_warmstart_model.pth')
    else:
        print("[Warm-Start] Pre-training DQN model using historical data...")
        drl_agent.pretrain_offline(dataset_path=CSV_FILE, epochs=20)
        drl_agent.save_weights('dqn_warmstart_model.pth')
                
    while True:

        node_stats = []
        all_throughputs = []

        for node in NETWORK_NODES:
            mac = node['mac']
            name = node['name']

            try:
                res = session.get(f"{STATS_URL}?mac={mac}", timeout=2)
                data = res.json()
                delta_bytes = data.get('delta_bytes', 0)
                delta_packets = data.get('delta_packets', 0)
            except Exception:
                delta_bytes = np.random.choice([5000, 150000, 3800000]) if name == "h4_heavy_traffic" else 25000
                delta_packets = delta_bytes // 1000

            tp_bps = delta_bytes * 8.0
            all_throughputs.append(tp_bps)

            node_stats.append({
                'mac': mac,
                'name': name,
                'delta_bytes': delta_bytes,
                'delta_packets': delta_packets,
                'tp_bps': tp_bps
            })


        for stat in node_stats:
            mac = stat['mac']
            name = stat['name']
            delta_bytes = stat['delta_bytes']
            delta_packets = stat['delta_packets']
            tp_bps = stat['tp_bps']

            # know the predicted behavior class using the User Behavior Classifier
            predicted_behavior = behavior_model.predict(delta_packets, delta_bytes)

            # state representation for the DRL agent
            traffic_ratio = delta_bytes / 1000000.0
            state = [delta_bytes, delta_packets, traffic_ratio]

            
            action_id = drl_agent.select_action(state, epsilon=0.05)
            action_str = ACTIONS[action_id]

            # apply the selected action to the SDN controller
            payload = {"src_mac": mac, "action": action_str}
            try:
                session.post(CONTROL_URL, json=payload, timeout=2)
            except Exception:
                pass

            # sdn controller returns estimated QoS metrics based on the action taken
            tp_mbps = tp_bps / 1_000_000.0

            if action_str in ["ALLOW_100", "PRIORITY_HIGH"]:
                est_latency = np.random.uniform(2.0, 8.0)
                est_jitter = np.random.uniform(0.5, 2.0)
            elif action_str == "ROUTE_SECONDARY":
                est_latency = np.random.uniform(10.0, 20.0)
                est_jitter = np.random.uniform(2.0, 5.0)
            elif action_str in ["LIMIT_50", "LIMIT_10"]:
                est_latency = np.random.uniform(40.0, 90.0)
                est_jitter = np.random.uniform(10.0, 20.0)
            else: # BLOCK
                est_latency = 200.0
                est_jitter = 50.0

            est_loss = 0.0 if action_str != "BLOCK" else 1.0

            # calculate the reward based on the predicted behavior, action taken, and estimated QoS metrics
            reward, fairness_idx = calculate_qos_reward(
                behavior_class=predicted_behavior,
                action_str=action_str,
                throughput_bps=tp_bps,
                latency_ms=est_latency,
                jitter_ms=est_jitter,
                packet_loss_ratio=est_loss,
                flow_allocations=all_throughputs
            )

            drl_agent.train_step(state, action_id, reward)

            # write the results to the CSV file
            new_row = {
                'Timestamp': timestamp,
                'Node_MAC': mac,
                'Node_Name': name,
                'Predicted_Behavior': "HIGH_TRAFFIC" if predicted_behavior == 1 else "NORMAL",
                'Delta_Bytes': delta_bytes,
                'Delta_Packets': delta_packets,
                'Throughput_Mbps': round(tp_mbps, 3),
                'Latency_ms': round(est_latency, 2),
                'Jitter_ms': round(est_jitter, 2),
                'Packet_Loss_Ratio': round(est_loss, 2),
                'Fairness_Index': round(fairness_idx, 3),
                'Action': action_str,
                'Reward': round(reward, 3)
            }
            pd.DataFrame([new_row]).to_csv(CSV_FILE, mode='a', header=False, index=False)

            print(f"[Step {timestamp:03d}] Node: {name:15s} | Behavior: {predicted_behavior} | Action: {action_str:14s} | Reward: {reward:+.3f}")

        timestamp += 1
        time.sleep(1)

except KeyboardInterrupt:
    print("\n[!] AI Agent Windows Controller Stopped Successfully.")
    sys.exit(0)