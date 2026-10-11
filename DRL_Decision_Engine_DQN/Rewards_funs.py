import torch
import torch.nn as nn
import torch.optim as optim
import numpy as np
import pandas as pd
import os


# Jain's Fairness function
def calculate_jains_fairness_index(allocations):
    allocations = np.array(allocations, dtype=float)
    if len(allocations) == 0 or np.sum(allocations ** 2) == 0:
        return 1.0
    
    n = len(allocations)
    sum_x = np.sum(allocations)
    sum_sq_x = np.sum(allocations ** 2)
    return float((sum_x ** 2) / (n * sum_sq_x))

# new QoS reward function
def calculate_qos_reward(behavior_class, action_str, 
                         throughput_bps=0.0, 
                         latency_ms=10.0, 
                         jitter_ms=2.0, 
                         packet_loss_ratio=0.0, 
                         flow_allocations=None):
    
    if flow_allocations is None:
        flow_allocations = [throughput_bps] if throughput_bps > 0 else [1.0]

    is_positive_action = action_str in ["ALLOW_100", "PRIORITY_HIGH", "ROUTE_SECONDARY"]
    is_restrictive_action = action_str in ["LIMIT_50", "LIMIT_10", "BLOCK", "PRIORITY_LOW"]

    if behavior_class == 1 and is_restrictive_action:
        r_action = 1.0
    elif behavior_class == 0 and is_positive_action:
        r_action = 1.0
    elif behavior_class == 0 and is_restrictive_action:
        r_action = -1.0
    else:
        r_action = -1.0

    max_throughput = 10_000_000.0  # 10 Mbps
    max_latency = 200.0            # 200 ms
    max_jitter = 50.0              # 50 ms
    
    norm_throughput = min(throughput_bps / max_throughput, 1.0)
    norm_latency = min(latency_ms / max_latency, 1.0)
    norm_jitter = min(jitter_ms / max_jitter, 1.0)
    norm_packet_loss = min(packet_loss_ratio, 1.0)

    fairness_index = calculate_jains_fairness_index(flow_allocations)

    w_action = 0.40
    w_throughput = 0.20
    w_latency = 0.15
    w_jitter = 0.10
    w_loss = 0.10
    w_fairness = 0.05

    total_reward = (
        (w_action * r_action) +
        (w_throughput * norm_throughput) -
        (w_latency * norm_latency) -
        (w_jitter * norm_jitter) -
        (w_loss * norm_packet_loss) +
        (w_fairness * fairness_index)
    )

    return float(np.clip(total_reward, -1.0, 1.0)), fairness_index

