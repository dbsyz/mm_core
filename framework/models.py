from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BBOEvent:
    exchange: str
    symbol: str
    exchange_ts_ms: float
    capture_ts_ms: float
    bid: float
    ask: float
    bid_qty: float
    ask_qty: float
