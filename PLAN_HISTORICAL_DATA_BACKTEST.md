# Historical Data and Backtesting Plan

Status: In progress (Phase 1 implemented, validation in progress)  
Last updated: 2026-03-01  
Scope: `mm_core` only (`c:\Users\syzdy\python\mm_core`)

## Objective
Build a robust historical pricing data foundation (Kraken BTC/EUR L1 BBO first) that supports deterministic, QA-gated backtesting.

## Plan Review
The proposed sequence is correct. The key priority is to fix data reliability before adding model complexity.  
Main refinement: explicitly define data contracts and replay interfaces before building strategy logic, to avoid rework.

## Phase 1: Ingestion Reliability Hardening
Goal: make long-run capture operationally stable and timestamp-correct.

Deliverables:
- Periodic clock-offset refresh/drift guard in `collector.py` (not only at subscribe ack).
- Session metadata in output (`session_id`, reconnect counters) or sidecar session log.
- Reconnect telemetry in logs with reason codes and retry timings.

Current status:
- Implemented:
  - periodic offset refresh controls via reconnect (`--offset-refresh-seconds`),
  - offset outlier guards (`--max-abs-clock-offset-ms`, `--max-offset-jump-ms`),
  - reconnect telemetry logging.
- Remaining in Phase 1:
  - validate on fresh contiguous 24h+ runs with unique output files.
  - decide whether session metadata goes into CSV or sidecar logs.

Acceptance criteria:
- Clean 24h run completes with no fatal exit.
- Clean 7d run can be sustained operationally (may be split into daily files).
- Strict QA pass for accepted files.
- Latency quality within gate thresholds in `PLAN_KRAKEN_BTC_EUR.md`.

## Phase 2: Canonical Historical Store
Goal: replace ad-hoc CSV usage with reproducible historical slices.

Deliverables:
- Batch builder script (recommended: `build_historical_store.py`) that ingests `mm_core/out/*.csv`.
- Canonical schema (minimum):
  - `exchange`, `symbol`, `ts_exchange`, `ts_capture`
  - `bid`, `ask`, `bid_qty`, `ask_qty`
  - `raw_age_ms`, `adjusted_age_ms`
  - `session_id`, `source_file`, `qa_status`, `qa_flags`
- Partitioning by `date` and `symbol` (Parquet recommended for v1).
- Manifest file for reproducibility (input files, row counts, output partitions, run timestamp).

Acceptance criteria:
- Rebuild from same input files yields identical row counts and deterministic partitions.
- Querying one day of BTC/EUR is fast enough for iterative research.
- Bad intervals can be excluded via QA flags without manual editing.

## Phase 3: Automated QA Pipeline
Goal: formalize data eligibility for research/backtests.

Deliverables:
- Daily QA job producing pass/fail summary and metrics.
- Stored QA report artifacts per day (machine-readable + human-readable).
- Policy for handling anomalies:
  - reject interval,
  - quarantine interval,
  - or allow with explicit warning tag.

Acceptance criteria:
- Each partition/day has explicit QA status.
- Backtest input selection can filter `qa_status=PASS` only.

## Phase 4: Replay Interface for Backtesting
Goal: deterministic event replay over canonical data.

Deliverables:
- Replay loader API/CLI:
  - inputs: symbol, date range, QA policy
  - output: ordered BBO events with stable typing
- Deterministic ordering rules and tie-break behavior documented.
- Reproducibility metadata emitted with each replay run.

Acceptance criteria:
- Same replay request produces byte-equivalent event sequence.
- Replay speed supports iterative parameter sweeps.

## Phase 5: Event-Driven Backtest Engine (L1 First)
Goal: establish baseline strategy evaluation under realistic constraints.

Deliverables:
- Backtest loop with:
  - quoting policy hooks,
  - latency assumptions,
  - fee/slippage model,
  - inventory/risk limits.
- Outputs:
  - PnL decomposition (spread capture, adverse selection, inventory cost),
  - fill statistics,
  - drawdown/tail metrics.

Acceptance criteria:
- Baseline strategy runs end-to-end on QA-approved slices.
- Results are reproducible and attributable to exact data/manifests.

## Phase 6: Feature and Model Expansion
Goal: add predictive content only after baseline infrastructure is stable.

Deliverables:
- Baseline feature set: arithmetic mid, size-weighted mid, spread, imbalance.
- Evaluation scripts for short-horizon directional signal quality.
- Versioned research outputs (metrics + assumptions).

Acceptance criteria:
- New features beat naive baselines out-of-sample.
- No data leakage across training/evaluation windows.

## Operational Standards
- Keep `mm_core/` as canonical root.
- Do not change collector CSV schema without explicit versioning/migration.
- Keep strict QA gate mandatory for "production-grade" research datasets.
- Prefer append-only raw data + derived canonical store; never overwrite raw source files.

## Immediate Next 3 Tasks
1. Validate Phase 1 on unique-file captures (1h then 24h) with strict QA gates.
2. Build historical store batch script to produce partitioned Parquet + manifest.
3. Add daily QA report generation bound to canonical partitions.

## Handover Notes for Next Chat
- Start from this file plus:
  - `mm_core/=== PROJECT HANDOFF PACK ===.txt`
  - `mm_core/HANDOVER_LOG.md`
- First implementation priority is Phase 1 (ingestion reliability), then Phase 2 (historical store).
