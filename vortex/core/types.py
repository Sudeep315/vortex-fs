from enum import Enum
from typing import Any, Optional
from datetime import timedelta
import re


class ValueType(str, Enum):
    INT32 = "INT32"
    INT64 = "INT64"
    FLOAT = "FLOAT"
    DOUBLE = "DOUBLE"
    STRING = "STRING"
    BYTES = "BYTES"
    BOOL = "BOOL"
    DATETIME = "DATETIME"
    EMBEDDING = "EMBEDDING"


class AggregationType(str, Enum):
    COUNT = "COUNT"
    SUM = "SUM"
    AVG = "AVG"
    MIN = "MIN"
    MAX = "MAX"
    DISTINCT_COUNT = "DISTINCT_COUNT"
    LAST = "LAST"
    FIRST = "FIRST"


class TimeWindow:
    """Represents a time duration window (e.g. 5m, 1h, 24h, 7d)."""

    def __init__(self, raw: str):
        self.raw = raw
        self.seconds = self._parse_to_seconds(raw)
        self.duration = timedelta(seconds=self.seconds)

    @staticmethod
    def _parse_to_seconds(val: str) -> int:
        val = val.strip().lower()
        match = re.match(r"^(\d+)([smhd])$", val)
        if not match:
            raise ValueError(f"Invalid window string: '{val}'. Expected format like '10s', '5m', '1h', '24h', '7d'")
        num, unit = int(match.group(1)), match.group(2)
        multipliers = {
            "s": 1,
            "m": 60,
            "h": 3600,
            "d": 86400,
        }
        return num * multipliers[unit]

    def to_sql_interval(self) -> str:
        """Returns DuckDB / Postgres compatible interval string."""
        return f"INTERVAL '{self.seconds} SECONDS'"

    def __repr__(self) -> str:
        return f"TimeWindow('{self.raw}', seconds={self.seconds})"

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, TimeWindow):
            return self.seconds == other.seconds
        return False

    def __hash__(self) -> int:
        return hash(self.seconds)
