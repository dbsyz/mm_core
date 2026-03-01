#!/usr/bin/env python3
"""Generate interactive BBO/mid chart for a selected UTC date."""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from datetime import date, datetime
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
    def weighted_mid(self) -> float:
        denom = self.bid_qty + self.ask_qty
        if denom <= 0:
            return self.arithmetic_mid
        # Microprice-style weighted mid.
        return (self.ask * self.bid_qty + self.bid * self.ask_qty) / denom


def parse_time(value: str) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def parse_float(row: list[str], idx: int) -> float | None:
    try:
        return float(row[idx])
    except (ValueError, IndexError):
        return None


def load_ticks(path: Path) -> list[Tick]:
    with path.open("r", newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader, None)
        if not header:
            return []

        try:
            i_ts = header.index("capture_time_utc")
            i_bid = header.index("bid")
            i_ask = header.index("ask")
            i_bid_qty = header.index("bid_qty")
            i_ask_qty = header.index("ask_qty")
        except ValueError as exc:
            raise RuntimeError(f"missing expected column in CSV: {exc}") from exc

        ticks: list[Tick] = []
        for row in reader:
            ts = parse_time(row[i_ts] if len(row) > i_ts else "")
            bid = parse_float(row, i_bid)
            ask = parse_float(row, i_ask)
            bid_qty = parse_float(row, i_bid_qty)
            ask_qty = parse_float(row, i_ask_qty)
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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", required=True, help="Input CSV file from collector.")
    parser.add_argument(
        "--date",
        required=True,
        help="UTC date in YYYY-MM-DD format to display.",
    )
    parser.add_argument(
        "--out",
        default=None,
        help="Output HTML path (default: mm_core/out/plots/<file>_<date>_interactive.html).",
    )
    parser.add_argument(
        "--max-points",
        type=int,
        default=120_000,
        help="Max points to plot after stride downsampling (default: 120000).",
    )
    args = parser.parse_args()

    in_path = Path(args.file)
    if not in_path.exists():
        print(f"file not found: {in_path}")
        return 1

    try:
        selected_date = date.fromisoformat(args.date)
    except ValueError:
        print("invalid --date format, expected YYYY-MM-DD")
        return 1

    try:
        import plotly.graph_objects as go
    except ModuleNotFoundError:
        print("plotly is required. Install with:")
        print(r"test_venv\Scripts\python.exe -m pip install -r mm_core\requirements.txt")
        return 2

    ticks = load_ticks(in_path)
    day_ticks = [t for t in ticks if t.capture_time.date() == selected_date]
    if not day_ticks:
        print(f"no rows found for date={selected_date.isoformat()} in {in_path}")
        return 1

    if args.max_points > 0 and len(day_ticks) > args.max_points:
        stride = max(1, len(day_ticks) // args.max_points)
        day_ticks = day_ticks[::stride]
        last_for_day = day_ticks[-1]
        if last_for_day.capture_time.date() == selected_date:
            day_full = [t for t in ticks if t.capture_time.date() == selected_date]
            if day_full and day_full[-1].capture_time != last_for_day.capture_time:
                day_ticks.append(day_full[-1])

    times = [t.capture_time for t in day_ticks]
    bids = [t.bid for t in day_ticks]
    asks = [t.ask for t in day_ticks]
    mids = [t.arithmetic_mid for t in day_ticks]
    w_mids = [t.weighted_mid for t in day_ticks]

    fig = go.Figure()
    fig.add_trace(go.Scattergl(x=times, y=bids, mode="lines", name="Bid"))
    fig.add_trace(go.Scattergl(x=times, y=asks, mode="lines", name="Ask"))
    fig.add_trace(go.Scattergl(x=times, y=mids, mode="lines", name="Arithmetic Mid"))
    fig.add_trace(go.Scattergl(x=times, y=w_mids, mode="lines", name="Size-Weighted Mid"))

    fig.update_layout(
        title=f"BBO and Mid Series ({selected_date.isoformat()} UTC)",
        xaxis_title="Time (UTC)",
        yaxis_title="Price",
        hovermode="x unified",
        template="plotly_white",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
    )
    fig.update_xaxes(rangeslider_visible=True)

    default_out = Path("mm_core/out/plots") / f"{in_path.stem}_{selected_date.isoformat()}_interactive.html"
    out_path = Path(args.out) if args.out else default_out
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.write_html(out_path, include_plotlyjs="cdn")

    print(f"samples_plotted={len(day_ticks)}")
    print(f"out_html={out_path}")
    print("tip: click legend names to toggle traces; use wheel/box zoom to inspect microstructure.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
