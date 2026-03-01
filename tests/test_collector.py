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

    def test_validate_clock_offset_rejects_abs_outlier(self) -> None:
        accepted, reason = self.collector.validate_clock_offset(
            candidate_offset_ms=5000.0,
            last_good_offset_ms=None,
            max_abs_clock_offset_ms=2000.0,
            max_offset_jump_ms=500.0,
        )
        self.assertIsNone(accepted)
        self.assertEqual(reason, "rejected_abs")

    def test_validate_clock_offset_rejects_jump_outlier(self) -> None:
        accepted, reason = self.collector.validate_clock_offset(
            candidate_offset_ms=1200.0,
            last_good_offset_ms=100.0,
            max_abs_clock_offset_ms=2000.0,
            max_offset_jump_ms=500.0,
        )
        self.assertIsNone(accepted)
        self.assertEqual(reason, "rejected_jump")

    def test_validate_clock_offset_accepts_valid(self) -> None:
        accepted, reason = self.collector.validate_clock_offset(
            candidate_offset_ms=120.0,
            last_good_offset_ms=100.0,
            max_abs_clock_offset_ms=2000.0,
            max_offset_jump_ms=500.0,
        )
        self.assertEqual(accepted, 120.0)
        self.assertEqual(reason, "accepted")


if __name__ == "__main__":
    unittest.main()
