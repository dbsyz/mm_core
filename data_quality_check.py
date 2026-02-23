#!/usr/bin/env python3
"""Routine post-collection QA checks for Kraken BTC/EUR BBO CSV data."""

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


def parse_float(row: list[str], idx: int) -> float | None:
    try:
        return float(row[idx])
    except (ValueError, IndexError):
        return None


@dataclass
class Row:
    capture_time_utc: str
    exchange_ts_ms: float
    bid: float
    ask: float
    bid_qty: float
    ask_qty: float
    adjusted_age_ms: float
    e2e_since_sub_ms: float | None

    @property
    def spread(self) -> float:
        return self.ask - self.bid


def parse_row(header: list[str], row: list[str]) -> Row | None:
    if not row:
        return None

    try:
        idx_exchange_ts_ms = header.index("exchange_ts_ms")
        idx_bid = header.index("bid")
        idx_ask = header.index("ask")
        idx_bid_qty = header.index("bid_qty")
        idx_ask_qty = header.index("ask_qty")
        idx_adjusted = header.index("adjusted_age_ms")
    except ValueError:
        return None

    capture_time = row[0]
    exchange_ts_ms = parse_float(row, idx_exchange_ts_ms)
    bid = parse_float(row, idx_bid)
    ask = parse_float(row, idx_ask)
    bid_qty = parse_float(row, idx_bid_qty)
    ask_qty = parse_float(row, idx_ask_qty)
    adjusted_age_ms = parse_float(row, idx_adjusted)

    if None in (exchange_ts_ms, bid, ask, bid_qty, ask_qty, adjusted_age_ms):
        return None

    e2e = None
    if "e2e_since_sub_ms" in header:
        e2e = parse_float(row, header.index("e2e_since_sub_ms"))

    return Row(
        capture_time_utc=capture_time,
        exchange_ts_ms=exchange_ts_ms,  # type: ignore[arg-type]
        bid=bid,  # type: ignore[arg-type]
        ask=ask,  # type: ignore[arg-type]
        bid_qty=bid_qty,  # type: ignore[arg-type]
        ask_qty=ask_qty,  # type: ignore[arg-type]
        adjusted_age_ms=adjusted_age_ms,  # type: ignore[arg-type]
        e2e_since_sub_ms=e2e,
    )


def split_runs(rows: list[Row]) -> list[list[Row]]:
    if not rows:
        return []
    runs: list[list[Row]] = []
    current: list[Row] = []
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
    parser.add_argument("--file", required=True, help="Input CSV path from collector.")
    parser.add_argument(
        "--all-runs",
        action="store_true",
        help="Analyze all runs in file. Default analyzes only latest contiguous run.",
    )
    parser.add_argument(
        "--top-spikes",
        type=int,
        default=10,
        help="Number of worst latency spikes to print (default: 10).",
    )
    parser.add_argument(
        "--max-timestamp-backward-ms",
        type=float,
        default=1.0,
        help="Tolerance for backwards exchange timestamp before counting anomaly.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit non-zero when hard integrity checks fail.",
    )
    parser.add_argument(
        "--max-backward-share",
        type=float,
        default=0.05,
        help=(
            "Fail threshold for backward timestamp ratio in strict mode "
            "(default: 0.05 = 5%%)."
        ),
    )
    parser.add_argument(
        "--max-backward-jump-ms",
        type=float,
        default=5000.0,
        help="Fail threshold for largest backward timestamp jump magnitude in ms.",
    )
    args = parser.parse_args()

    path = Path(args.file)
    if not path.exists():
        print(f"file not found: {path}")
        return 1

    with path.open("r", newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader, None)
        if not header:
            print("empty file")
            return 1
        parsed = [r for row in reader if (r := parse_row(header, row)) is not None]

    if not parsed:
        print("no parseable rows with expected schema")
        return 1

    runs = split_runs(parsed)
    rows = parsed if args.all_runs else runs[-1]
    n = len(rows)
    start = rows[0].capture_time_utc
    end = rows[-1].capture_time_utc

    spreads = [r.spread for r in rows]
    ages = [r.adjusted_age_ms for r in rows]

    crossed_quotes = sum(1 for r in rows if r.bid > r.ask)
    non_positive_sizes = sum(1 for r in rows if r.bid_qty <= 0.0 or r.ask_qty <= 0.0)
    non_positive_spread = sum(1 for s in spreads if s <= 0.0)

    backward_ts_count = 0
    max_backward_jump_ms = 0.0
    prev_ts = rows[0].exchange_ts_ms
    for r in rows[1:]:
        delta = r.exchange_ts_ms - prev_ts
        if delta < -abs(args.max_timestamp_backward_ms):
            backward_ts_count += 1
            max_backward_jump_ms = min(max_backward_jump_ms, delta)
        prev_ts = r.exchange_ts_ms

    duration_s = max((rows[-1].exchange_ts_ms - rows[0].exchange_ts_ms) / 1000.0, 1e-9)
    update_rate = n / duration_s

    spikes = sorted(rows, key=lambda r: r.adjusted_age_ms, reverse=True)[: max(args.top_spikes, 0)]

    print(f"runs_detected={len(runs)} mode={'all_runs' if args.all_runs else 'latest_run'}")
    print(f"start={start}")
    print(f"end={end}")
    print(f"samples={n}")
    print(f"duration_s={duration_s:.3f}")
    print(f"update_rate_per_s={update_rate:.3f}")
    print(f"spread min={min(spreads):.8f}")
    print(f"spread p50={pct(spreads, 0.50):.8f}")
    print(f"spread p95={pct(spreads, 0.95):.8f}")
    print(f"spread max={max(spreads):.8f}")
    print(f"age_ms p50={pct(ages, 0.50):.3f}")
    print(f"age_ms p95={pct(ages, 0.95):.3f}")
    print(f"age_ms p99={pct(ages, 0.99):.3f}")
    print(f"age_ms max={max(ages):.3f}")
    print(f"integrity crossed_quotes={crossed_quotes}")
    print(f"integrity non_positive_sizes={non_positive_sizes}")
    print(f"integrity non_positive_spread={non_positive_spread}")
    print(f"integrity backward_exchange_ts_count={backward_ts_count}")
    print(f"integrity max_backward_exchange_ts_jump_ms={max_backward_jump_ms:.3f}")
    backward_share = backward_ts_count / n
    print(f"integrity backward_exchange_ts_share={backward_share:.2%}")

    if spikes:
        print("top_latency_spikes:")
        for spike in spikes:
            print(f"{spike.capture_time_utc} adjusted_age_ms={spike.adjusted_age_ms:.3f}")

    backward_severe = (
        backward_share > args.max_backward_share
        or abs(max_backward_jump_ms) > args.max_backward_jump_ms
    )
    hard_fail = crossed_quotes > 0 or non_positive_sizes > 0 or non_positive_spread > 0
    final_fail = hard_fail or backward_severe
    print(f"qa_status={'FAIL' if final_fail else 'PASS'}")
    if backward_ts_count > 0 and not backward_severe:
        print(
            "warning: backward exchange timestamps observed within configured tolerance; "
            "treat as venue timestamp noise unless trend worsens."
        )
    if backward_severe:
        print("warning: backward exchange timestamp anomalies exceed configured threshold.")

    if args.strict and final_fail:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
