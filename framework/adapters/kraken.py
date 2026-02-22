from __future__ import annotations

from datetime import datetime
from typing import Any

from mm_core.framework.models import BBOEvent


class KrakenBBOAdapter:
    exchange_name = "kraken"

    def normalize_symbol(self, symbol: str) -> str:
        return symbol.strip().upper()

    def subscribe_payload(self, symbol: str) -> dict[str, Any]:
        return {
            "method": "subscribe",
            "params": {
                "channel": "ticker",
                "symbol": [self.normalize_symbol(symbol)],
                "event_trigger": "bbo",
                "snapshot": True,
            },
        }

    def parse_bbo(self, message: dict[str, Any], capture_ts_ms: float) -> BBOEvent | None:
        if message.get("channel") != "ticker":
            return None
        if message.get("type") not in {"snapshot", "update"}:
            return None
        data = message.get("data")
        if not isinstance(data, list) or not data:
            return None
        row = data[0]
        if not isinstance(row, dict):
            return None

        exchange_ts_ms = parse_exchange_ts_ms(row.get("timestamp"))
        if exchange_ts_ms is None:
            return None

        try:
            return BBOEvent(
                exchange=self.exchange_name,
                symbol=str(row.get("symbol", "")).upper(),
                exchange_ts_ms=exchange_ts_ms,
                capture_ts_ms=capture_ts_ms,
                bid=float(row["bid"]),
                ask=float(row["ask"]),
                bid_qty=float(row["bid_qty"]),
                ask_qty=float(row["ask_qty"]),
            )
        except (KeyError, TypeError, ValueError):
            return None


def parse_exchange_ts_ms(value: str | None) -> float | None:
    if not value:
        return None
    normalized = value.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized).timestamp() * 1000.0
    except ValueError:
        return None
