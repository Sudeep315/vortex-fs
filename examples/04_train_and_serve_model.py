"""
Example 4: Production Online Model Inference with Feature Store
Demonstrates end-to-end integration:
Online Feature Lookup (<2ms) -> Real-time Fraud Scoring -> Instant Authorization Decision.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from vortex.serving.client import FeatureStoreClient
from vortex.simulator.ml_model import FraudRiskModel


def main():
    print("=== VortexFS: Online Model Inference Demo ===")
    client = FeatureStoreClient()
    model = FraudRiskModel()

    user_id = "user_0001"
    transaction_amount = 250.0

    print(f"\nEvaluating real-time authorization for User: {user_id}")
    print(f"Transaction Attempt: ${transaction_amount:.2f} USD")

    # Run inference pipeline
    result = model.predict_risk(
        client=client,
        user_id=user_id,
        transaction_amount=transaction_amount,
    )

    print("\n--- Model Decision Result ---")
    print(f"  Outcome:        {result['decision']}")
    print(f"  Fraud Score:    {result['fraud_probability'] * 100:.1f}%")
    print(f"  Recommendation: {result['recommendation']}")

    print("\n--- Features Used (Retrieved Real-Time from Online Store) ---")
    for fname, fval in result["retrieved_features"].items():
        print(f"  • {fname:25s}: {fval}")


if __name__ == "__main__":
    main()
