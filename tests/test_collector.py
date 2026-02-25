from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import unittest


def _load_module(module_name: str, relative_path: str):
    root = Path(__file__).resolve().parents[1]
    module_path = root / relative_path
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"failed loading module from {module_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


class CollectorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.collector = _load_module("mm_core_collector", "collector.py")

    def test_parse_ticker_event_accepts_snapshot(self) -> None:
        msg = {
            "channel": "ticker",
            "type": "snapshot",
            "data": [{"symbol": "BTC/EUR", "bid": "1", "ask": "2"}],
        }
        row = self.collector.parse_ticker_event(msg)
        self.assertIsNotNone(row)
        self.assertEqual(row["symbol"], "BTC/EUR")

    def test_parse_ticker_event_rejects_non_ticker(self) -> None:
        msg = {"channel": "trade", "type": "snapshot", "data": [{}]}
        self.assertIsNone(self.collector.parse_ticker_event(msg))


if __name__ == "__main__":
    unittest.main()
