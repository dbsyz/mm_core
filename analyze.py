#!/usr/bin/env python3
"""Analyze Kraken latency CSV produced by collector.py."""

from __future__ import annotations

import argparse
import csv
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


def parse_age_from_row(header: list[str], row: list[str], prefer_adjusted: bool) -> float | None:
    if not row:
        return None

    # New schema, correct header.
    if "adjusted_age_ms" in header:
        try:
            idx = header.index("adjusted_age_ms")
            return float(row[idx])
        except (ValueError, IndexError):
            return None

    # Legacy header + new rows appended (mixed file): adjusted_age_ms is at index 10.
    if len(row) >= 12:
        try:
            return float(row[10])
        except ValueError:
            return None

    if prefer_adjusted:
        return None

    # Legacy schema fallback.
    if "data_age_ms" in header:
        try:
            idx = header.index("data_age_ms")
            return float(row[idx])
        except (ValueError, IndexError):
            return None

    return None


def classify_regime(value: float, normal_max: float, degraded_max: float) -> str:
    if value <= normal_max:
        return "normal"
    if value <= degraded_max:
        return "degraded"
    return "unsafe"


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
    args = parser.parse_args()
    path = Path(args.file)
    if not path.exists():
        print(f"file not found: {path}")
        return 1

    ages: list[float] = []
    with path.open("r", newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader, None)
        if not header:
            print("empty file")
            return 1
        rows = list(reader)

    has_adjusted_rows = "adjusted_age_ms" in header or any(len(r) >= 12 for r in rows)
    for row in rows:
        age = parse_age_from_row(header, row, prefer_adjusted=has_adjusted_rows)
        if age is not None:
            ages.append(age)

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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
