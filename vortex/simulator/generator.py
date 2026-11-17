import random
import uuid
from typing import List, Dict, Any, Generator, Optional
from datetime import datetime, timezone, timedelta
from vortex.core.event import Event


class SyntheticEventGenerator:
    """
    Generates realistic e-commerce and fintech event streams,
    modeled after production telemetry captured by PostHog.
    """

    EVENT_TYPES = [
        "page_viewed",
        "search_performed",
        "cart_item_added",
        "payment_executed",
        "login_failed",
        "session_started",
        "password_reset_requested",
        "chargeback_filed",
    ]

    DEVICES = ["desktop_mac_safari", "desktop_win_chrome", "mobile_ios_app", "mobile_android_app"]
    CATEGORIES = ["electronics", "apparel", "home", "groceries", "luxury_goods", "gaming"]

    def __init__(self, num_users: int = 50, seed: int = 42):
        random.seed(seed)
        self.users = [f"user_{i:04d}" for i in range(1, num_users + 1)]
        self.merchants = [f"merchant_{j:02d}" for j in range(1, 11)]

    def generate_random_event(
        self,
        timestamp: Optional[datetime] = None,
        user_id: Optional[str] = None,
        force_event_type: Optional[str] = None,
    ) -> Event:
        ts = timestamp or datetime.now(timezone.utc)
        uid = user_id or random.choice(self.users)
        etype = force_event_type or random.choices(
            population=self.EVENT_TYPES,
            weights=[35, 20, 15, 12, 6, 8, 2, 2],
            k=1,
        )[0]

        props: Dict[str, Any] = {
            "device_id": random.choice(self.DEVICES),
            "ip_address": f"192.168.{random.randint(1, 20)}.{random.randint(1, 254)}",
        }

        if etype == "payment_executed":
            props["amount"] = round(random.lognormvariate(mu=3.8, sigma=0.8), 2)
            props["merchant_id"] = random.choice(self.merchants)
            props["currency"] = "USD"
            props["status"] = "success"
        elif etype == "page_viewed":
            props["url"] = f"https://shop.example.com/{random.choice(self.CATEGORIES)}"
            props["duration_sec"] = random.randint(5, 120)
        elif etype == "cart_item_added":
            props["item_price"] = round(random.uniform(15.0, 300.0), 2)
            props["category"] = random.choice(self.CATEGORIES)
        elif etype == "login_failed":
            props["reason"] = random.choice(["invalid_password", "user_not_found", "mfa_timeout"])
        elif etype == "search_performed":
            props["query"] = random.choice(["wireless headphones", "running shoes", "espresso maker", "iphone case"])
        elif etype == "chargeback_filed":
            props["amount"] = round(random.uniform(50.0, 800.0), 2)
            props["reason"] = "fraudulent_unauthorized_charge"

        return Event(
            id=str(uuid.uuid4()),
            event=etype,
            distinct_id=uid,
            timestamp=ts,
            properties=props,
        )

    def generate_historical_dataset(
        self,
        days_back: int = 7,
        events_per_day: int = 200,
    ) -> List[Event]:
        """
        Generates chronologically ordered historical event logs spanning multiple days.
        """
        events: List[Event] = []
        now = datetime.now(timezone.utc)
        start_time = now - timedelta(days=days_back)
        total_seconds = int((now - start_time).total_seconds())

        for _ in range(days_back * events_per_day):
            random_offset = random.randint(0, total_seconds)
            event_ts = start_time + timedelta(seconds=random_offset)
            events.append(self.generate_random_event(timestamp=event_ts))

        # Sort strictly by timestamp
        events.sort(key=lambda e: e.timestamp)
        return events

    def stream_generator(self, delay_sec: float = 0.1) -> Generator[Event, None, None]:
        """Infinite stream generator for continuous demoing or benchmark testing."""
        while True:
            yield self.generate_random_event()
