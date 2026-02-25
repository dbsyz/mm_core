from __future__ import annotations

import csv
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


CSV_HEADER = [
    "capture_time_utc",
    "recv_ts_ms",
    "exchange_ts",
    "exchange_ts_ms",
    "symbol",
    "bid",
    "ask",
    "bid_qty",
    "ask_qty",
    "raw_age_ms",
    "adjusted_age_ms",
    "e2e_since_sub_ms",
]


def _run_qa(csv_path: Path) -> subprocess.CompletedProcess[str]:
    script = Path(__file__).resolve().parents[1] / "data_quality_check.py"
    return subprocess.run(
        [sys.executable, str(script), "--file", str(csv_path), "--strict"],
        check=False,
        text=True,
        capture_output=True,
    )


class DataQualityCheckTests(unittest.TestCase):
    def test_strict_pass_clean_fixture(self) -> None:
        with tempfile.NamedTemporaryFile("w", delete=False, newline="", suffix=".csv") as tmp:
            path = Path(tmp.name)
            writer = csv.writer(tmp)
            writer.writerow(CSV_HEADER)
            writer.writerow(
                [
                    "2026-02-23T00:00:00+00:00",
                    "1000",
                    "2026-02-23T00:00:00+00:00",
                    "1000",
                    "BTC/EUR",
                    "100",
                    "101",
                    "1.0",
                    "1.0",
                    "5",
                    "5",
                    "1",
                ]
            )
            writer.writerow(
                [
                    "2026-02-23T00:00:01+00:00",
                    "2000",
                    "2026-02-23T00:00:01+00:00",
                    "2000",
                    "BTC/EUR",
                    "100.1",
                    "101.1",
                    "1.0",
                    "1.0",
                    "6",
                    "6",
                    "2",
                ]
            )
        try:
            result = _run_qa(path)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("qa_status=PASS", result.stdout)
        finally:
            path.unlink(missing_ok=True)

    def test_strict_fail_backward_jump(self) -> None:
        with tempfile.NamedTemporaryFile("w", delete=False, newline="", suffix=".csv") as tmp:
            path = Path(tmp.name)
            writer = csv.writer(tmp)
            writer.writerow(CSV_HEADER)
            writer.writerow(
                [
                    "2026-02-23T00:00:00+00:00",
                    "1000",
                    "2026-02-23T00:00:00+00:00",
                    "10000",
                    "BTC/EUR",
                    "100",
                    "101",
                    "1.0",
                    "1.0",
                    "5",
                    "5",
                    "1",
                ]
            )
            writer.writerow(
                [
                    "2026-02-23T00:00:01+00:00",
                    "2000",
                    "2026-02-23T00:00:01+00:00",
                    "3000",
                    "BTC/EUR",
                    "100.1",
                    "101.1",
                    "1.0",
                    "1.0",
                    "6",
                    "6",
                    "2",
                ]
            )
        try:
            result = _run_qa(path)
            self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
            self.assertIn("qa_status=FAIL", result.stdout)
        finally:
            path.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
