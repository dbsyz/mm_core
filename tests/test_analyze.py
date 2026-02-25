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


class AnalyzeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.analyze = _load_module("mm_core_analyze", "analyze.py")

    def test_parse_row_legacy_does_not_infer_e2e(self) -> None:
        header = [
            "capture_time_utc",
            "recv_ts_ms",
            "exchange_ts",
            "symbol",
            "bid",
            "ask",
            "bid_qty",
            "ask_qty",
            "data_age_ms",
            "extra1",
            "extra2",
        ]
        row = [
            "2026-02-23T00:00:00+00:00",
            "1",
            "2026-02-23T00:00:00+00:00",
            "BTC/EUR",
            "1",
            "2",
            "3",
            "4",
            "15.5",
            "a",
            "b",
        ]
        parsed = self.analyze.parse_row(header, row, prefer_adjusted=False)
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed.age_ms, 15.5)
        self.assertIsNone(parsed.e2e_since_sub_ms)

    def test_split_runs_on_e2e_reset(self) -> None:
        parsed_rows = [
            self.analyze.ParsedRow("t1", 1.0, 1000.0),
            self.analyze.ParsedRow("t2", 2.0, 1200.0),
            self.analyze.ParsedRow("t3", 3.0, 200.0),
            self.analyze.ParsedRow("t4", 4.0, 300.0),
        ]
        runs = self.analyze.split_runs(parsed_rows)
        self.assertEqual(len(runs), 2)
        self.assertEqual(len(runs[0]), 2)
        self.assertEqual(len(runs[1]), 2)


if __name__ == "__main__":
    unittest.main()
