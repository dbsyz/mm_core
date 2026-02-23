# Kraken BTC/EUR Build Plan (POC -> Scale)

Scope: start with one exchange (Kraken) and one pair (`BTC/EUR`) and build a reusable framework for multi-exchange market making.

## 24h Decision Gate (Run This First)

Goal: decide objectively whether to proceed to 1-week capture.

### How to run

1) Collect for 24h:
- `test_venv\Scripts\python.exe mm_core\collector.py --symbol BTC/EUR --out mm_core\out\kraken_bbo_latency_24h.csv --max-seconds 86400`

2) Analyze with fixed operational thresholds:
- `test_venv\Scripts\python.exe mm_core\analyze.py --file mm_core\out\kraken_bbo_latency_24h.csv --normal-max-ms 20 --degraded-max-ms 80`

3) Run routine data QA:
- `test_venv\Scripts\python.exe mm_core\data_quality_check.py --file mm_core\out\kraken_bbo_latency_24h.csv --strict`

### Pass/Fail criteria

Mandatory pass checks:
- collector ran at least 23.5h without fatal exit
- parseable samples >= 500,000
- `p50 <= 15ms`
- `p95 <= 100ms`
- `p99 <= 400ms`
- `unsafe_share (age > 80ms) <= 8%`
- routine data QA status is `PASS` (strict mode)

Conditional pass checks:
- no prolonged feed silence observed in logs (no gaps > 60s)
- no repeated instability pattern (for example, frequent reconnect loops)

Decision:
- If all mandatory checks pass and no major conditional red flags: proceed to 1-week collection.
- If any mandatory check fails: fix ingestion/infra issues first, then rerun 24h gate.

## Phase 0: Foundation (now)

Goal: stable, measurable market-data capture.

Deliverables:
- live BBO collector running continuously for `BTC/EUR`
- schema-validated raw storage
- latency analyzer with regime statistics

Go/no-go checks:
- collector uptime > 99% over a 24h run
- no silent schema corruption
- p95/p99 latency monitored and exported daily

## Phase 1: Canonical Data Layer

Goal: make exchange-specific data look identical internally.

Deliverables:
- canonical event schema (`exchange`, `symbol`, `ts_exchange`, `ts_capture`, `bid`, `ask`, sizes)
- Kraken adapter module that maps raw messages to canonical events
- config file for exchange/pair runtime

Go/no-go checks:
- deterministic parser tests pass for snapshots and updates
- gap/heartbeat/reconnect events logged

## Phase 2: Feature + Fair Value Research

Goal: build first fair-mid model for quoting decisions.

Deliverables:
- features: mid, spread, microprice, imbalance, short-horizon realized vol
- baseline fair-mid model with 1s and 5s horizons
- research notebook/report with out-of-sample diagnostics

Go/no-go checks:
- feature quality checks pass (no NaN bursts, monotonic timestamps)
- baseline model beats naive mid on directional error and calibration

## Phase 3: Event-Driven Backtest

Goal: test quoting logic with realistic market frictions.

Deliverables:
- event-driven simulator fed by canonical events
- fee/rebate model, inventory penalties, latency assumptions
- PnL decomposition: spread capture vs adverse selection vs inventory

Go/no-go checks:
- strategy remains profitable across parameter stress tests
- tail losses bounded under latency/volatility shocks

## Phase 4: Quoting Engine V1

Goal: convert research into controlled policy.

Deliverables:
- policy engine: quote width and size from fair-mid + inventory + latency regime + vol regime
- hard risk controls: max inventory, max staleness, kill switches
- full telemetry for decision latency and quote changes

Go/no-go checks:
- no risk-limit breaches in simulation and paper trading
- deterministic regime transitions with hysteresis

## Phase 5: Live Rollout

Goal: controlled progression from paper to small real size.

Deliverables:
- paper trading runbook
- limited-size production rollout
- daily TCA and incident review workflow

Go/no-go checks:
- stable live operation for 2+ weeks
- acceptable adverse-selection profile in volatile sessions

## Standardization Rules for Scaling

When adding exchange #2 or pair #2:
- do not fork business logic
- add only a new adapter + config
- keep same canonical event schema, feature pipeline, backtester, and policy engine

This keeps the POC architecture reusable and avoids rewrite debt.
