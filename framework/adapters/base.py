from __future__ import annotations

from typing import Any, Protocol

from mm_core.framework.models import BBOEvent


class ExchangeAdapter(Protocol):
    exchange_name: str

    def normalize_symbol(self, symbol: str) -> str:
        """Normalize user input into the exchange-native symbol."""

    def subscribe_payload(self, symbol: str) -> dict[str, Any]:
        """Build subscription payload for BBO stream."""

    def parse_bbo(self, message: dict[str, Any], capture_ts_ms: float) -> BBOEvent | None:
        """Parse raw exchange message into canonical BBO event."""
