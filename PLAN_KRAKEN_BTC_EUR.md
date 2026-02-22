# Kraken BTC/EUR Build Plan (POC -> Scale)

Scope: start with one exchange (Kraken) and one pair (`BTC/EUR`) and build a reusable framework for multi-exchange market making.

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
