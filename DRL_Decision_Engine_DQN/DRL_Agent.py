import torch
import torch.nn as nn
import torch.optim as optim
import numpy as np
import pandas as pd
import os
from DRL_Decision_Engine_DQN.Rewards_funs import calculate_qos_reward
from DRL_Decision_Engine_DQN.DQN_Agent import DQNNetwork


ACTIONS = {
    0: "ALLOW_100",
    1: "LIMIT_50",
    2: "LIMIT_10",
    3: "BLOCK",
    4: "ROUTE_PRIMARY",
    5: "ROUTE_SECONDARY",
    6: "PRIORITY_HIGH",
    7: "PRIORITY_LOW"
}
ACTION_TO_ID = {
    "ALLOW_100": 0,
    "LIMIT_50": 1,
    "LIMIT_10": 2,
    "BLOCK": 3,
    "ROUTE_PRIMARY": 4,
    "ROUTE_SECONDARY": 5,
    "PRIORITY_HIGH": 6,
    "PRIORITY_LOW": 7
}



# DRL Decision Agent with Warm-Start Pre-training Support
class DRLDecisionAgent:
    def __init__(self, state_dim=3, action_dim=8, lr=0.001):
        self.model = DQNNetwork(state_dim, action_dim)
        self.optimizer = optim.Adam(self.model.parameters(), lr=lr)
        self.criterion = nn.MSELoss()
        self.action_dim = action_dim

    def select_action(self, state, epsilon=0.05):
        if np.random.rand() < epsilon:
            return np.random.choice(self.action_dim)
        else:
            with torch.no_grad():
                state_t = torch.FloatTensor(state)
                q_values = self.model(state_t)
                return torch.argmax(q_values).item()

    def train_step(self, state, action_id, reward):
        state_t = torch.FloatTensor(state)
        q_val = self.model(state_t)[action_id]
        target_q = torch.tensor(reward, dtype=torch.float32)
        
        loss = self.criterion(q_val, target_q)
        self.optimizer.zero_grad()
        loss.backward()
        self.optimizer.step()
        return loss.item()

    def pretrain_offline(self, dataset_path='simulation_results.csv', epochs=20, batch_size=32):
        if not os.path.exists(dataset_path):
            print(f"[Warm-Start] Error: File '{dataset_path}' not found!")
            return

        print(f"[Warm-Start] Reading historical log data from '{dataset_path}'...")
        df = pd.read_csv(dataset_path)

        if 'Action_ID' in df.columns:
            df['Action_ID'] = pd.to_numeric(df['Action_ID'], errors='coerce')
        else:
            df['Action'] = df['Action'].astype(str).str.strip()
            df['Action_ID'] = df['Action'].map(ACTION_TO_ID)

        initial_count = len(df)
        df = df.dropna(subset=['Delta_Packets', 'Delta_Bytes', 'Throughput_Mbps', 'Action_ID', 'Reward'])
        
        if len(df) == 0:
            print("[Warm-Start] Error: No valid rows remaining after cleaning NaN values!")
            return
            
        if len(df) < initial_count:
            print(f"[Warm-Start] Dropped {initial_count - len(df)} invalid/NaN rows.")

        states = df[['Delta_Packets', 'Delta_Bytes', 'Throughput_Mbps']].values.astype(np.float32)
        actions = df['Action_ID'].values.astype(np.int64)
        rewards = df['Reward'].values.astype(np.float32)

        dataset_size = len(states)
        print(f"[Warm-Start] Pre-training on {dataset_size} samples...")

        for epoch in range(epochs):
            indices = np.arange(dataset_size)
            np.random.shuffle(indices)
            epoch_loss = 0.0

            for i in range(0, dataset_size, batch_size):
                batch_idx = indices[i:i+batch_size]
                
                b_states = torch.FloatTensor(states[batch_idx])
                b_actions = torch.LongTensor(actions[batch_idx])
                b_rewards = torch.FloatTensor(rewards[batch_idx])

                q_vals = self.model(b_states)
                state_action_values = q_vals.gather(1, b_actions.unsqueeze(1)).squeeze(1)

                loss = self.criterion(state_action_values, b_rewards)

                self.optimizer.zero_grad()
                loss.backward()
                self.optimizer.step()

                epoch_loss += loss.item()

            if (epoch + 1) % 5 == 0 or epoch == 0:
                avg_loss = epoch_loss / max(1, (dataset_size // batch_size))
                print(f" -> Epoch [{epoch+1:02d}/{epochs:02d}] | Loss: {avg_loss:.6f}")

        print("[Warm-Start] Offline Pre-training Completed Successfully!\n")


    def save_weights(self, filepath='dqn_warmstart_model.pth'):
        torch.save(self.model.state_dict(), filepath)
        print(f"[Model Saved] Saved DQN weights to '{filepath}'")

    def load_weights(self, filepath='dqn_warmstart_model.pth'):
        if os.path.exists(filepath):
            self.model.load_state_dict(torch.load(filepath))
            print(f"[Model Loaded] Successfully loaded warm-start weights from '{filepath}'")
        else:
            print(f"[Model Load Warning] File '{filepath}' not found!")