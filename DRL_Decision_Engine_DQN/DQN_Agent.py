import torch
import torch.nn as nn
import torch.optim as optim
import numpy as np
import pandas as pd
import os

# DQN Network Definition
class DQNNetwork(nn.Module):
    def __init__(self, state_dim=3, action_dim=8):
        super(DQNNetwork, self).__init__()
        self.fc = nn.Sequential(
            nn.Linear(state_dim, 64),
            nn.ReLU(),
            nn.Linear(64, 64),
            nn.ReLU(),
            nn.Linear(64, action_dim)
        )

    def forward(self, x):
        return self.fc(x)