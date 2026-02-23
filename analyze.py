#!/usr/bin/env python3
"""Analyze Kraken latency CSV produced by collector.py."""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from pathlib import Path


def pct(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    idx = (len(ordered) - 1) * p
    lo = int(idx)
    hi = min(lo + 1, len(ordered) - 1)
    frac = idx - lo
    return ordered[lo] * (1.0 - frac) + ordered[hi] * frac


@dataclass
class ParsedRow:
    capture_time_utc: str
    age_ms: float
    e2e_since_sub_ms: float | None


def parse_float_cell(row: list[str], idx: int) -> float | None:
    try:
        return float(row[idx])
    except (ValueError, IndexError):
        return None


def parse_row(header: list[str], row: list[str], prefer_adjusted: bool) -> ParsedRow | None:
    if not row:
        return None

    capture_time = row[0] if row else ""
    e2e = None
    if "e2e_since_sub_ms" in header:
        e2e = parse_float_cell(row, header.index("e2e_since_sub_ms"))
    elif len(row) >= 11:
        e2e = parse_float_cell(row, len(row) - 1)

    # New schema, correct header.
    if "adjusted_age_ms" in header:
        age = parse_float_cell(row, header.index("adjusted_age_ms"))
        if age is None:
            return None
        return ParsedRow(capture_time_utc=capture_time, age_ms=age, e2e_since_sub_ms=e2e)

    # Legacy header + new rows appended (mixed file): adjusted_age_ms is at index 10.
    if len(row) >= 12:
        age = parse_float_cell(row, 10)
        if age is None:
            return None
        return ParsedRow(capture_time_utc=capture_time, age_ms=age, e2e_since_sub_ms=e2e)

    if prefer_adjusted:
        return None

    # Legacy schema fallback.
    if "data_age_ms" in header:
        age = parse_float_cell(row, header.index("data_age_ms"))
        if age is None:
            return None
        return ParsedRow(capture_time_utc=capture_time, age_ms=age, e2e_since_sub_ms=e2e)

    return None


def classify_regime(value: float, normal_max: float, degraded_max: float) -> str:
    if value <= normal_max:
        return "normal"
    if value <= degraded_max:
        return "degraded"
    return "unsafe"


def split_runs(rows: list[ParsedRow]) -> list[list[ParsedRow]]:
    if not rows:
        return []
    runs: list[list[ParsedRow]] = []
    current: list[ParsedRow] = []
    prev_e2e: float | None = None
    for row in rows:
        e2e = row.e2e_since_sub_ms
        if current and e2e is not None and prev_e2e is not None and e2e + 1e-6 < prev_e2e:
            runs.append(current)
            current = []
        current.append(row)
        if e2e is not None:
            prev_e2e = e2e
    if current:
        runs.append(current)
    return runs


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--file",
        default="mm_core/out/kraken_bbo_latency.csv",
        help="Latency CSV file path.",
    )
    parser.add_argument(
        "--normal-max-ms",
        type=float,
        default=None,
        help="Normal regime upper bound in ms (default: p95 from sample).",
    )
    parser.add_argument(
        "--degraded-max-ms",
        type=float,
        default=None,
        help="Degraded regime upper bound in ms (default: p99 from sample).",
    )
    parser.add_argument(
        "--all-runs",
        action="store_true",
        help="Analyze all rows in file instead of latest contiguous run.",
    )
    args = parser.parse_args()
    path = Path(args.file)
    if not path.exists():
        print(f"file not found: {path}")
        return 1

    parsed_rows: list[ParsedRow] = []
    with path.open("r", newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader, None)
        if not header:
            print("empty file")
            return 1
        rows = list(reader)

    has_adjusted_rows = "adjusted_age_ms" in header or any(len(r) >= 12 for r in rows)
    for row in rows:
        parsed = parse_row(header, row, prefer_adjusted=has_adjusted_rows)
        if parsed is not None:
            parsed_rows.append(parsed)

    if not parsed_rows:
        print("no valid samples")
        return 1

    runs = split_runs(parsed_rows)
    selected = parsed_rows if args.all_runs else runs[-1]
    ages = [r.age_ms for r in selected]

    if not ages:
        print("no valid samples")
        return 1

    p95 = pct(ages, 0.95)
    p99 = pct(ages, 0.99)
    normal_max = p95 if args.normal_max_ms is None else args.normal_max_ms
    degraded_max = p99 if args.degraded_max_ms is None else args.degraded_max_ms
    if degraded_max < normal_max:
        print("invalid thresholds: degraded-max-ms must be >= normal-max-ms")
        return 1

    regime_counts = {"normal": 0, "degraded": 0, "unsafe": 0}
    for age in ages:
        regime_counts[classify_regime(age, normal_max, degraded_max)] += 1

    n = len(ages)
    if args.all_runs:
        print(f"runs_detected={len(runs)} mode=all_runs")
    else:
        print(f"runs_detected={len(runs)} mode=latest_run")
        print(f"latest_run_start={selected[0].capture_time_utc}")
        print(f"latest_run_end={selected[-1].capture_time_utc}")
    print(f"samples={n}")
    print(f"age_ms min={min(ages):.3f}")
    print(f"age_ms p50={pct(ages, 0.50):.3f}")
    print(f"age_ms p95={p95:.3f}")
    print(f"age_ms p99={p99:.3f}")
    print(f"age_ms max={max(ages):.3f}")
    print(f"age_ms mean={sum(ages) / n:.3f}")
    print(f"regime normal <= {normal_max:.3f} ms")
    print(f"regime degraded <= {degraded_max:.3f} ms")
    print(f"regime unsafe > {degraded_max:.3f} ms")
    print(
        f"regime_counts normal={regime_counts['normal']} "
        f"degraded={regime_counts['degraded']} unsafe={regime_counts['unsafe']}"
    )
    print(
        f"regime_share normal={regime_counts['normal'] / n:.2%} "
        f"degraded={regime_counts['degraded'] / n:.2%} unsafe={regime_counts['unsafe'] / n:.2%}"
    )
    p50 = pct(ages, 0.50)
    if p50 > 250.0:
        print(
            "warning: p50 is very high (>250ms). Check for wrong file/run, stale clocks, "
            "or degraded network conditions."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
