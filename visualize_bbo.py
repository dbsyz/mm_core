#!/usr/bin/env python3
"""Plot bid/ask and mid-price time series from collector CSV output."""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass
class Tick:
    capture_time: datetime
    bid: float
    ask: float
    bid_qty: float
    ask_qty: float

    @property
    def arithmetic_mid(self) -> float:
        return (self.bid + self.ask) / 2.0

    @property
    def size_weighted_mid(self) -> float:
        denom = self.bid_qty + self.ask_qty
        if denom <= 0:
            return self.arithmetic_mid
        # Microprice-style weighting by opposite queue size.
        return (self.ask * self.bid_qty + self.bid * self.ask_qty) / denom


def parse_float(row: list[str], idx: int) -> float | None:
    try:
        return float(row[idx])
    except (ValueError, IndexError):
        return None


def parse_time(value: str) -> datetime | None:
    if not value:
        return None
    normalized = value.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None


def load_ticks(path: Path) -> list[Tick]:
    with path.open("r", newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader, None)
        if not header:
            return []
        try:
            idx_capture = header.index("capture_time_utc")
            idx_bid = header.index("bid")
            idx_ask = header.index("ask")
            idx_bid_qty = header.index("bid_qty")
            idx_ask_qty = header.index("ask_qty")
        except ValueError:
            raise RuntimeError("missing expected columns in CSV header")

        ticks: list[Tick] = []
        for row in reader:
            ts = parse_time(row[idx_capture] if len(row) > idx_capture else "")
            bid = parse_float(row, idx_bid)
            ask = parse_float(row, idx_ask)
            bid_qty = parse_float(row, idx_bid_qty)
            ask_qty = parse_float(row, idx_ask_qty)
            if None in (ts, bid, ask, bid_qty, ask_qty):
                continue
            ticks.append(
                Tick(
                    capture_time=ts,  # type: ignore[arg-type]
                    bid=bid,  # type: ignore[arg-type]
                    ask=ask,  # type: ignore[arg-type]
                    bid_qty=bid_qty,  # type: ignore[arg-type]
                    ask_qty=ask_qty,  # type: ignore[arg-type]
                )
            )
    return ticks


def downsample(ticks: list[Tick], max_points: int) -> list[Tick]:
    if max_points <= 0 or len(ticks) <= max_points:
        return ticks
    stride = max(1, len(ticks) // max_points)
    sampled = ticks[::stride]
    if sampled[-1] is not ticks[-1]:
        sampled.append(ticks[-1])
    return sampled


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", required=True, help="Input CSV file from collector.")
    parser.add_argument(
        "--outdir",
        default="mm_core/out/plots",
        help="Directory for PNG outputs (default: mm_core/out/plots).",
    )
    parser.add_argument(
        "--max-points",
        type=int,
        default=20_000,
        help="Downsample cap for plotting large files (default: 20000).",
    )
    parser.add_argument(
        "--prefix",
        default=None,
        help="Optional output filename prefix (default: input file stem).",
    )
    args = parser.parse_args()

    path = Path(args.file)
    if not path.exists():
        print(f"file not found: {path}")
        return 1

    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.dates as mdates
        import matplotlib.pyplot as plt
    except ModuleNotFoundError:
        print("matplotlib is required. Install with:")
        print(r"test_venv\Scripts\python.exe -m pip install -r mm_core\requirements.txt")
        return 2

    ticks = load_ticks(path)
    if not ticks:
        print("no valid rows found")
        return 1
    ticks = downsample(ticks, args.max_points)

    times = [t.capture_time for t in ticks]
    bids = [t.bid for t in ticks]
    asks = [t.ask for t in ticks]
    mids = [t.arithmetic_mid for t in ticks]
    sw_mids = [t.size_weighted_mid for t in ticks]

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    prefix = args.prefix or path.stem

    fig, ax = plt.subplots(figsize=(14, 6))
    ax.plot(times, bids, label="bid", linewidth=1.0)
    ax.plot(times, asks, label="ask", linewidth=1.0)
    ax.set_title("Bid/Ask Time Series")
    ax.set_xlabel("Time (UTC)")
    ax.set_ylabel("Price")
    ax.grid(alpha=0.25)
    ax.legend(loc="best")
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M:%S"))
    fig.autofmt_xdate()
    bid_ask_path = outdir / f"{prefix}_bid_ask.png"
    fig.tight_layout()
    fig.savefig(bid_ask_path, dpi=140)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(14, 6))
    ax.plot(times, mids, label="arithmetic_mid", linewidth=1.0)
    ax.plot(times, sw_mids, label="size_weighted_mid", linewidth=1.0)
    ax.set_title("Arithmetic Mid vs Size-Weighted Mid")
    ax.set_xlabel("Time (UTC)")
    ax.set_ylabel("Price")
    ax.grid(alpha=0.25)
    ax.legend(loc="best")
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M:%S"))
    fig.autofmt_xdate()
    mids_path = outdir / f"{prefix}_mids.png"
    fig.tight_layout()
    fig.savefig(mids_path, dpi=140)
    plt.close(fig)

    print(f"samples_plotted={len(ticks)}")
    print(f"bid_ask_plot={bid_ask_path}")
    print(f"mids_plot={mids_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
