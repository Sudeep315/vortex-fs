#!/usr/bin/env python3
"""
VortexFS One-Click Quickstart Runner
Seeds initial demo events if the offline store is empty and launches the API + Web Dashboard.
"""

import sys
import webbrowser
import threading
import time
from pathlib import Path

# Ensure root directory is in sys.path
sys.path.insert(0, str(Path(__file__).parent))

from vortex.serving.client import FeatureStoreClient
from vortex.simulator.generator import SyntheticEventGenerator
from vortex.cli import start


def seed_if_empty():
    """Seeds 300 realistic events on first run so the store is pre-populated."""
    client = FeatureStoreClient()
    stats = client.offline_store.get_stats()
    if stats.get("total_events", 0) == 0:
        print("[VortexFS] Pre-populating store with 300 initial realistic events...")
        gen = SyntheticEventGenerator(num_users=30, seed=42)
        events = gen.generate_historical_dataset(days_back=7, events_per_day=45)
        client.ingest_batch(events)
        client.flush()
        print("[VortexFS] ✓ Initial seed completed successfully.")


def open_browser():
    time.sleep(1.5)
    url = "http://localhost:8000"
    print(f"\n[VortexFS] Opening Web Console at {url}")
    try:
        webbrowser.open(url)
    except Exception:
        pass


if __name__ == "__main__":
    seed_if_empty()
    threading.Thread(target=open_browser, daemon=True).start()
    print("\n[VortexFS] Starting server on http://0.0.0.0:8000 ...")
    start.main(args=["--host", "0.0.0.0", "--port", "8000"])
