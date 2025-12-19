import json
import os

import numpy as np
import pandas as pd
from datetime import datetime
import uuid


class NumpyEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        if isinstance(obj, np.integer):
            return int(obj)
        if isinstance(obj, np.floating):
            return float(obj)
        if isinstance(obj, np.bool_):
            return bool(obj)
        return super(NumpyEncoder, self).default(obj)


class DataCollector:
    def __init__(self, base_path, env_id, task_name, exp_i):
        self.base_path = base_path
        self.env_id = env_id
        self.task_name = task_name
        self.exp_i = exp_i
        self.data_path = os.path.join(self.base_path, self.env_id, self.task_name, f"exp_{self.exp_i}")
        self.data = []
        self.create_data_directory()

    def create_data_directory(self):
        os.makedirs(self.data_path, exist_ok=True)

    def create_task_directory(self):
        os.makedirs(self.task_path, exist_ok=True)

    def collect_data(self, step_data):
        self.data.append(step_data)

    def save_checkpoint(self):
        checkpoint_path = os.path.join(self.data_path, f'checkpoint_{len(self.data)}.json')
        try:
            with open(checkpoint_path, 'w') as f:
                json.dump(self.data, f, cls=NumpyEncoder)
        except Exception as e:
            print(f"Error saving checkpoint: {str(e)}")
            self.record_failure("Checkpoint save error", str(e))

    def load_checkpoint(self, checkpoint_path):
        try:
            with open(checkpoint_path, 'r') as f:
                self.data = json.load(f)
        except Exception as e:
            print(f"Error loading checkpoint: {str(e)}")
            self.record_failure("Checkpoint load error", str(e))

    def save_to_csv(self):
        try:
            df = pd.DataFrame(self.data)
            csv_path = os.path.join(self.data_path, 'collected_data.csv')
            df.to_csv(csv_path, index=False)
        except Exception as e:
            print(f"Error saving to CSV: {str(e)}")
            self.record_failure("CSV save error", str(e))

    def save_to_json(self):
        json_path = os.path.join(self.data_path, 'collected_data.json')
        try:
            with open(json_path, 'w') as f:
                json.dump(self.data, f, cls=NumpyEncoder, indent=2)
        except Exception as e:
            print(f"Error saving to JSON: {str(e)}")
            self.record_failure("JSON save error", str(e))

    def save_trajectory(self, trajectory_data):
        """Save detailed trajectory data for a single task"""
        trajectory_path = os.path.join(self.data_path, 'trajectory.json')
        try:
            with open(trajectory_path, 'w') as f:
                json.dump(trajectory_data, f, cls=NumpyEncoder, indent=2)
        except Exception as e:
            print(f"Error saving trajectory: {str(e)}")
            self.record_failure("Trajectory save error", str(e))

    def record_failure(self, error_message, stack_trace):
        failure_data = {
            'timestamp': datetime.now().isoformat(),
            'error_message': error_message,
            'stack_trace': stack_trace
        }
        failure_path = os.path.join(self.data_path, 'failures.json')
        try:
            with open(failure_path, 'a') as f:
                json.dump(failure_data, f)
                f.write('\n')  # For easier reading of multiple entries
        except Exception as e:
            print(f"Error recording failure: {str(e)}")