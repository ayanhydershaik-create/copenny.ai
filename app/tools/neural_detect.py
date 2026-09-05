import numpy as np
from sklearn.neural_network import MLPClassifier
import joblib
import os
from typing import List, Tuple, Dict, Any

class NeuralAnomalyDetector:
    """
    A Multi-Layer Perceptron (MLP) based anomaly detector.
    Provides deep-learning statistical pattern recognition for transaction classification.
    """
    def __init__(self, model_path: str = None):
        self.model_path = model_path or os.path.join(
            os.path.dirname(__file__), "..", "..", "state", "models", "neural_anomaly_model.pkl"
        )
        self.clf = MLPClassifier(
            hidden_layer_sizes=(16, 8), 
            activation='relu', 
            solver='adam', 
            max_iter=500,
            random_state=42
        )
        self.is_trained = False
        self._load_model()

    def _load_model(self):
        if os.path.exists(self.model_path):
            try:
                self.clf = joblib.load(self.model_path)
                self.is_trained = True
                print("Neural Anomaly Model loaded successfully.")
            except Exception as e:
                print(f"Could not load neural model: {e}")

    def train_on_mock(self):
        """Trains the MLP on synthetic financial anomaly data."""
        # Features: [RelativeAmount, FrequencyScore, LatencyDays]
        # Label: 0 (Normal), 1 (Anomaly)
        X = np.array([
            [0.1, 0.9, 1], [0.2, 0.8, 2], [0.15, 0.95, 1], [0.05, 0.9, 1], # Normal
            [0.8, 0.1, 30], [0.9, 0.05, 45], [0.75, 0.15, 20], [0.95, 0.01, 60] # Anomalies
        ])
        y = np.array([0, 0, 0, 0, 1, 1, 1, 1])
        
        print("Training Neural Anomaly Detector (MLP)...")
        self.clf.fit(X, y)
        self.is_trained = True
        
        # Save model
        os.makedirs(os.path.dirname(self.model_path), exist_ok=True)
        joblib.dump(self.clf, self.model_path)
        print(f"Model saved to {self.model_path}")

    def predict_anomaly(self, relative_amount: float, frequency_score: float, latency_days: int) -> Dict[str, Any]:
        """
        Predicts if a transaction is an anomaly using the Deep Learning model.
        Returns probability and classification.
        """
        if not self.is_trained:
            # Auto-train on first use for demo purposes
            self.train_on_mock()

        features = np.array([[relative_amount, frequency_score, latency_days]])
        prediction = self.clf.predict(features)[0]
        probability = self.clf.predict_proba(features)[0][1] # Probability of anomaly

        return {
            "is_anomaly": bool(prediction),
            "anomaly_probability": round(float(probability), 4),
            "model_architecture": "Multi-Layer Perceptron (Neural Network)",
            "activation_function": "ReLU",
            "solver": "Adam Optimizer"
        }

if __name__ == "__main__":
    detector = NeuralAnomalyDetector()
    detector.train_on_mock()
    test_val = detector.predict_anomaly(0.85, 0.05, 40)
    print(f"Test Result: {test_val}")
