#!/usr/bin/env python3
"""Measure market data latency for Kraken spot BBO (BTC/EUR, event_trigger=bbo)."""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import signal
import statistics
import sys
import time
from collections import deque
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import websockets


KRAKEN_WS_V2 = "wss://ws.kraken.com/v2"
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


@dataclass
class LatencySample:
    exchange_ts_ms: float
    recv_ts_ms: float
    raw_age_ms: float
    adjusted_age_ms: float
    e2e_since_sub_ms: float


def utc_iso_now() -> str:
    return datetime.now(tz=UTC).isoformat()


def epoch_ms() -> float:
    return time.time_ns() / 1_000_000.0


def parse_exchange_ts_ms(value: str | None) -> float | None:
    if not value:
        return None
    normalized = value.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized).timestamp() * 1000.0
    except ValueError:
        return None


def pct(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    idx = (len(ordered) - 1) * p
    lo = int(idx)
    hi = min(lo + 1, len(ordered) - 1)
    if lo == hi:
        return ordered[lo]
    frac = idx - lo
    return ordered[lo] * (1.0 - frac) + ordered[hi] * frac


class RollingStats:
    def __init__(self, maxlen: int = 50_000) -> None:
        self.samples: deque[LatencySample] = deque(maxlen=maxlen)
        self.msg_count_total = 0
        self.window_start_ms = epoch_ms()

    def add(self, sample: LatencySample) -> None:
        self.samples.append(sample)
        self.msg_count_total += 1

    def summary(self) -> dict[str, float]:
        ages = [s.adjusted_age_ms for s in self.samples]
        elapsed_s = max((epoch_ms() - self.window_start_ms) / 1000.0, 1e-6)
        return {
            "count_window": float(len(ages)),
            "msg_rate_per_s": self.msg_count_total / elapsed_s,
            "age_ms_min": min(ages) if ages else 0.0,
            "age_ms_mean": statistics.fmean(ages) if ages else 0.0,
            "age_ms_p50": pct(ages, 0.50),
            "age_ms_p95": pct(ages, 0.95),
            "age_ms_p99": pct(ages, 0.99),
            "age_ms_max": max(ages) if ages else 0.0,
        }


def subscribe_payload(symbol: str) -> dict[str, Any]:
    return {
        "method": "subscribe",
        "params": {
            "channel": "ticker",
            "symbol": [symbol],
            "event_trigger": "bbo",
            "snapshot": True,
        },
    }


def normalize_symbol(symbol: str) -> str:
    return symbol.strip().upper()


def default_output_path() -> Path:
    stamp = datetime.now(tz=UTC).strftime("%Y%m%d_%H%M%S")
    return Path(f"mm_core/out/kraken_bbo_latency_{stamp}.csv")


def ensure_csv(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        with path.open("r", newline="", encoding="utf-8") as f:
            first_line = f.readline().strip()
        expected = ",".join(CSV_HEADER)
        if first_line != expected:
            raise RuntimeError(
                f"CSV header mismatch for {path}. Use a new --out path or migrate file schema."
            )
        return
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(CSV_HEADER)


def parse_ticker_event(message: dict[str, Any]) -> dict[str, Any] | None:
    if message.get("channel") != "ticker":
        return None
    msg_type = message.get("type")
    if msg_type not in {"snapshot", "update"}:
        return None
    data = message.get("data")
    if not isinstance(data, list) or not data:
        return None
    row = data[0]
    if not isinstance(row, dict):
        return None
    return row


def validate_clock_offset(
    candidate_offset_ms: float,
    last_good_offset_ms: float | None,
    max_abs_clock_offset_ms: float,
    max_offset_jump_ms: float,
) -> tuple[float | None, str]:
    if abs(candidate_offset_ms) > max_abs_clock_offset_ms:
        return None, "rejected_abs"
    if last_good_offset_ms is not None:
        jump = abs(candidate_offset_ms - last_good_offset_ms)
        if jump > max_offset_jump_ms:
            return None, "rejected_jump"
    return candidate_offset_ms, "accepted"


async def run_collector(
    symbol: str,
    out_csv: Path,
    summary_every_s: float,
    ws_url: str,
    max_seconds: float | None,
    offset_refresh_seconds: float,
    max_abs_clock_offset_ms: float,
    max_offset_jump_ms: float,
) -> None:
    symbol = normalize_symbol(symbol)
    ensure_csv(out_csv)
    stats = RollingStats()
    stop_event = asyncio.Event()
    session_start_ms = epoch_ms()
    reconnect_attempt = 0
    last_good_offset_ms: float | None = None

    def _stop_handler(*_: Any) -> None:
        stop_event.set()

    signal.signal(signal.SIGINT, _stop_handler)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, _stop_handler)

    print(f"[{utc_iso_now()}] starting collector out={out_csv}")
    next_summary_ts = time.monotonic() + summary_every_s
    with out_csv.open("a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        while not stop_event.is_set():
            if max_seconds is not None and (epoch_ms() - session_start_ms) / 1000.0 >= max_seconds:
                stop_event.set()
                break

            clock_offset_ms = 0.0
            clock_offset_ready = False
            clock_offset_set_ms: float | None = None
            sub_send_ms = 0.0
            try:
                print(f"[{utc_iso_now()}] connecting ws={ws_url} symbol={symbol}")
                async with websockets.connect(ws_url, ping_interval=15, ping_timeout=15) as ws:
                    connection_open_ms = epoch_ms()
                    payload = subscribe_payload(symbol)
                    sub_send_ms = epoch_ms()
                    await ws.send(json.dumps(payload))
                    print(f"[{utc_iso_now()}] subscribed payload={payload}")
                    reconnect_attempt = 0

                    while not stop_event.is_set():
                        if (
                            max_seconds is not None
                            and (epoch_ms() - session_start_ms) / 1000.0 >= max_seconds
                        ):
                            stop_event.set()
                            break

                        if (
                            offset_refresh_seconds > 0.0
                            and (
                                (
                                    clock_offset_ready
                                    and clock_offset_set_ms is not None
                                    and (epoch_ms() - clock_offset_set_ms) / 1000.0
                                    >= offset_refresh_seconds
                                )
                                or (
                                    not clock_offset_ready
                                    and (epoch_ms() - connection_open_ms) / 1000.0
                                    >= offset_refresh_seconds
                                )
                            )
                        ):
                            print(
                                f"[{utc_iso_now()}] refreshing clock offset after "
                                f"{offset_refresh_seconds:.0f}s via reconnect"
                            )
                            break

                        raw = await asyncio.wait_for(ws.recv(), timeout=30)
                        recv_ts_ms = epoch_ms()
                        msg = json.loads(raw)

                        if msg.get("method") == "subscribe":
                            if not msg.get("success", False):
                                raise RuntimeError(f"subscription failed: {msg}")
                            server_in_ms = parse_exchange_ts_ms(msg.get("time_in"))
                            server_out_ms = parse_exchange_ts_ms(msg.get("time_out"))
                            if server_in_ms is not None and server_out_ms is not None:
                                local_recv_ms = recv_ts_ms
                                t0 = sub_send_ms
                                t1 = server_in_ms
                                t2 = server_out_ms
                                t3 = local_recv_ms
                                # NTP style estimate: server_clock - local_clock.
                                candidate_offset_ms = ((t1 - t0) + (t2 - t3)) / 2.0
                                accepted, reason = validate_clock_offset(
                                    candidate_offset_ms=candidate_offset_ms,
                                    last_good_offset_ms=last_good_offset_ms,
                                    max_abs_clock_offset_ms=max_abs_clock_offset_ms,
                                    max_offset_jump_ms=max_offset_jump_ms,
                                )
                                if accepted is None:
                                    if last_good_offset_ms is not None:
                                        clock_offset_ms = last_good_offset_ms
                                        clock_offset_ready = True
                                        clock_offset_set_ms = recv_ts_ms
                                        print(
                                            f"[{utc_iso_now()}] warning: clock_offset candidate="
                                            f"{candidate_offset_ms:.3f} rejected ({reason}); "
                                            f"reusing last_good={last_good_offset_ms:.3f}"
                                        )
                                    else:
                                        print(
                                            f"[{utc_iso_now()}] warning: clock_offset candidate="
                                            f"{candidate_offset_ms:.3f} rejected ({reason}); "
                                            "using raw_age_ms until a valid offset is available"
                                        )
                                else:
                                    clock_offset_ms = accepted
                                    clock_offset_ready = True
                                    clock_offset_set_ms = recv_ts_ms
                                    last_good_offset_ms = accepted
                                    print(
                                        f"[{utc_iso_now()}] clock_offset_ms={clock_offset_ms:.3f} "
                                        f"(server-local, {reason})"
                                    )
                            continue

                        ticker = parse_ticker_event(msg)
                        if ticker is None:
                            continue

                        exchange_ts = ticker.get("timestamp")
                        exchange_ts_ms = parse_exchange_ts_ms(exchange_ts)
                        if exchange_ts_ms is None:
                            continue

                        raw_age_ms = recv_ts_ms - exchange_ts_ms
                        adjusted_age_ms = (
                            raw_age_ms + clock_offset_ms if clock_offset_ready else raw_age_ms
                        )
                        sample = LatencySample(
                            exchange_ts_ms=exchange_ts_ms,
                            recv_ts_ms=recv_ts_ms,
                            raw_age_ms=raw_age_ms,
                            adjusted_age_ms=adjusted_age_ms,
                            e2e_since_sub_ms=recv_ts_ms - sub_send_ms,
                        )
                        stats.add(sample)

                        writer.writerow(
                            [
                                utc_iso_now(),
                                f"{recv_ts_ms:.3f}",
                                exchange_ts,
                                f"{exchange_ts_ms:.3f}",
                                ticker.get("symbol", symbol),
                                ticker.get("bid"),
                                ticker.get("ask"),
                                ticker.get("bid_qty"),
                                ticker.get("ask_qty"),
                                f"{raw_age_ms:.3f}",
                                f"{adjusted_age_ms:.3f}",
                                f"{sample.e2e_since_sub_ms:.3f}",
                            ]
                        )

                        if time.monotonic() >= next_summary_ts:
                            s = stats.summary()
                            print(
                                (
                                    f"[{utc_iso_now()}] n={int(s['count_window'])} "
                                    f"rate={s['msg_rate_per_s']:.2f}/s "
                                    f"age_ms p50={s['age_ms_p50']:.2f} "
                                    f"p95={s['age_ms_p95']:.2f} p99={s['age_ms_p99']:.2f} "
                                    f"mean={s['age_ms_mean']:.2f} max={s['age_ms_max']:.2f}"
                                )
                            )
                            next_summary_ts = time.monotonic() + summary_every_s
            except RuntimeError:
                raise
            except (
                TimeoutError,
                OSError,
                websockets.exceptions.ConnectionClosed,
                websockets.exceptions.WebSocketException,
                json.JSONDecodeError,
            ) as exc:
                if stop_event.is_set():
                    break
                reconnect_attempt += 1
                delay_s = min(30.0, 2.0 ** min(reconnect_attempt, 5))
                print(
                    f"[{utc_iso_now()}] warning: ws loop error={exc!r}; "
                    f"reconnect_attempt={reconnect_attempt} sleep={delay_s:.1f}s"
                )
                try:
                    await asyncio.wait_for(stop_event.wait(), timeout=delay_s)
                except TimeoutError:
                    pass
                continue

    print(f"[{utc_iso_now()}] stopped cleanly")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--symbol",
        default="BTC/EUR",
        help="Kraken symbol in ws v2 format (default: BTC/EUR).",
    )
    parser.add_argument(
        "--out",
        default=None,
        help=(
            "Output CSV path for raw samples. If omitted, a timestamped file is created "
            "under mm_core/out/."
        ),
    )
    parser.add_argument(
        "--summary-every",
        type=float,
        default=5.0,
        help="Seconds between rolling latency summaries (default: 5).",
    )
    parser.add_argument(
        "--ws-url",
        default=KRAKEN_WS_V2,
        help="Kraken websocket v2 URL.",
    )
    parser.add_argument(
        "--max-seconds",
        type=float,
        default=None,
        help="Optional max runtime in seconds (useful for smoke tests).",
    )
    parser.add_argument(
        "--offset-refresh-seconds",
        type=float,
        default=900.0,
        help=(
            "Re-estimate clock offset by reconnecting at this interval in seconds "
            "(default: 900, set 0 to disable)."
        ),
    )
    parser.add_argument(
        "--max-abs-clock-offset-ms",
        type=float,
        default=2_000.0,
        help="Reject new clock offset estimates beyond this absolute bound (default: 2000).",
    )
    parser.add_argument(
        "--max-offset-jump-ms",
        type=float,
        default=500.0,
        help="Reject new clock offsets that jump this much vs last accepted (default: 500).",
    )
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    out_csv = Path(args.out) if args.out else default_output_path()
    try:
        asyncio.run(
            run_collector(
                symbol=args.symbol,
                out_csv=out_csv,
                summary_every_s=args.summary_every,
                ws_url=args.ws_url,
                max_seconds=args.max_seconds,
                offset_refresh_seconds=args.offset_refresh_seconds,
                max_abs_clock_offset_ms=args.max_abs_clock_offset_ms,
                max_offset_jump_ms=args.max_offset_jump_ms,
            )
        )
    except KeyboardInterrupt:
        pass
    except Exception as exc:
        print(f"fatal: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
