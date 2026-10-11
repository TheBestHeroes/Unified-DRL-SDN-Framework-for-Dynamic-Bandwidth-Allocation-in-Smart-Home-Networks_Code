import os
import warnings
import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.exceptions import InconsistentVersionWarning

warnings.filterwarnings("ignore", category=InconsistentVersionWarning)


class UserBehaviorClassifier:
    def __init__(self, model_path='robust_behavior_model.pkl', csv_path='simulation_results.csv'):
        self.model_path = model_path
        self.csv_path = csv_path
        self.feature_names = ['Delta_Packets', 'Delta_Bytes', 'Throughput_Mbps']

        if os.path.exists(self.model_path):
            self._load_model()

        elif os.path.exists(self.csv_path):
            print(f"[ML Engine] '{self.model_path}' not found. Training model from '{self.csv_path}'...")
            self.train_and_save_from_csv(self.csv_path)

        else:
            print(f"[ML Engine] First-time setup detected. Initializing with Synthetic Baseline Model...")
            self._train_from_synthetic_baseline()

    def _load_model(self):
        try:
            assets = joblib.load(self.model_path)
            self.clf = assets['model']
            self.scaler = assets['scaler']
            self.encoder = assets.get('encoder', None)

            if hasattr(self.scaler, 'feature_names_in_'):
                self.feature_names = list(self.scaler.feature_names_in_)

            self.is_loaded = True
            print(f"[ML Engine] Loaded trained model successfully from '{self.model_path}'")
        except Exception as e:
            print(f"[ML Engine] Error loading model ({e}). Retraining baseline...")
            self._train_from_synthetic_baseline()


    def _train_from_synthetic_baseline(self):
        data = {
            'Delta_Packets': [10, 25, 50, 100, 1200, 3000, 5000, 8000],
            'Delta_Bytes': [1000, 5000, 20000, 80000, 1500000, 5000000, 10000000, 25000000],
            'Throughput_Mbps': [0.01, 0.05, 0.2, 0.8, 12.0, 40.0, 80.0, 200.0],
            'Predicted_Behavior': [0, 0, 0, 0, 1, 1, 1, 1]
        }

        df_synthetic = pd.DataFrame(data)

        X = df_synthetic[self.feature_names]
        y = df_synthetic['Predicted_Behavior']

        self.scaler = StandardScaler()
        X_scaled = self.scaler.fit_transform(X)

        self.clf = RandomForestClassifier(n_estimators=10, random_state=42)
        self.clf.fit(X_scaled, y)

        self.encoder = None
        self.is_loaded = True

        self._save_model_file()
        print(f"[ML Engine] Baseline model trained and saved to '{self.model_path}'.")

    def train_and_save_from_csv(self, csv_filepath=None):
        target_csv = csv_filepath or self.csv_path

        if not os.path.exists(target_csv):
            print(f"[ML Engine] CSV '{target_csv}' not found. Skipping retrain.")
            return

        try:
            df = pd.read_csv(target_csv)

            required_cols = ['Delta_Packets', 'Delta_Bytes', 'Throughput_Mbps']
            if not all(col in df.columns for col in required_cols):
                print(f"[ML Engine] CSV missing required columns. Retraining skipped.")
                return

            X = df[required_cols]

            if 'Predicted_Behavior' in df.columns:
                y = df['Predicted_Behavior']
            elif 'Behavior' in df.columns:
                y = df['Behavior']
            else:
                y = (df['Throughput_Mbps'] > 10.0).astype(int)

            self.scaler = StandardScaler()
            X_scaled = self.scaler.fit_transform(X)

            self.clf = RandomForestClassifier(n_estimators=50, random_state=42)
            self.clf.fit(X_scaled, y)

            self.is_loaded = True
            self._save_model_file()
            print(f"[ML Engine] Model updated successfully from '{target_csv}' -> Saved to '{self.model_path}'.")

        except Exception as e:
            print(f"[ML Engine] Error reading CSV: {e}")

    def _save_model_file(self):
        assets = {
            'model': self.clf,
            'scaler': self.scaler,
            'encoder': self.encoder
        }
        joblib.dump(assets, self.model_path)

    def predict(self, pkt_rate, byte_rate):
        throughput_mbps = (byte_rate * 8) / 1_000_000.0

        raw_df = pd.DataFrame(
            [[pkt_rate, byte_rate, throughput_mbps]],
            columns=self.feature_names
        )

        scaled_features = self.scaler.transform(raw_df)
        pred_class_id = self.clf.predict(scaled_features)[0]

        return int(pred_class_id)