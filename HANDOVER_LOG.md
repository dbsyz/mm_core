# Handover Log

## 2026-02-25

### Summary
- Completed hardening pass for reliability and handover readiness.
- Updated primary handoff document:
  - `mm_core/=== PROJECT HANDOFF PACK ===.txt`
- Added automated tests:
  - `mm_core/tests/test_analyze.py`
  - `mm_core/tests/test_collector.py`
  - `mm_core/tests/test_data_quality_check.py`

### Code Changes
- `mm_core/analyze.py`
  - Fixed legacy parsing behavior so 11-column legacy rows do not treat trailing values as `e2e_since_sub_ms`.
- `mm_core/collector.py`
  - Added reconnect loop with bounded exponential backoff.
  - Preserved `--max-seconds` as total run duration across reconnects.
  - Re-estimates clock offset on each new websocket session.

### Verification Performed
- Static compile:
- `test_venv\Scripts\python.exe -m py_compile mm_core\collector.py mm_core\analyze.py mm_core\data_quality_check.py`
- Unit tests:
- `test_venv\Scripts\python.exe -m unittest discover -s mm_core\tests -p "test_*.py" -v`
- Result:
- `Ran 6 tests ... OK`

### Operational Findings (Important)
- 24h file checked:
- `mm_core\out\kraken_bbo_latency_24h_2026-02-22.csv`
- Analyzer output showed severe degradation:
- p50 about 1306 ms, p95 about 1431 ms, unsafe share about 98.64%.
- Strict QA failed:
- backward timestamp share about 5.90%, max backward jump about 19606 ms.
- Interpretation:
- data quality in that run is not acceptable for MM decision use without further investigation.

### Remaining Risks / TODO
- Add periodic clock-offset refresh or drift guard during long sessions.
- Add fair baseline script (mid/microprice + 1s directional quality).
- Add integration tests with replay fixtures.
- Decide policy on tracked `__pycache__/*.pyc` files (currently noisy in diffs).

### Notes for Next Chat
- Use `mm_core/=== PROJECT HANDOFF PACK ===.txt` as the canonical start point.
- Keep `mm_core` as canonical root and avoid touching `kraken_latency` unless asked.

## 2026-03-01

### Summary
- Added execution plan document for historical data foundation and backtesting readiness:
  - `mm_core/PLAN_HISTORICAL_DATA_BACKTEST.md`

### Why
- Consolidates the agreed strategy into a handover-ready, phase-based roadmap with concrete acceptance criteria.
- Reduces ambiguity for next chats by defining implementation order and quality gates.

### Priority
- Phase 1 (ingestion reliability hardening) and Phase 2 (canonical historical store) are the immediate build targets.

## 2026-03-01 (Step 1 execution)

### Summary
- Implemented Phase 1 starter in collector:
  - periodic clock-offset refresh by controlled reconnect,
  - offset drift/outlier guardrails,
  - new runtime knobs for offset policy.

### Code Changes
- `mm_core/collector.py`
  - Added `validate_clock_offset(...)` to reject invalid offset estimates.
  - Added periodic refresh control:
    - `--offset-refresh-seconds` (default 900, 0 disables).
  - Added guard parameters:
    - `--max-abs-clock-offset-ms` (default 2000),
    - `--max-offset-jump-ms` (default 500).

### Test and Runtime Verification
- Compile checks passed:
  - `python -m py_compile` on collector/analyzer/qa/visualization scripts.
- Unit tests passed:
  - `python -m unittest discover -s mm_core\tests -p "test_*.py" -v`
  - 9 tests passing (added collector offset validation tests).
- Live smoke passed:
  - `collector.py --max-seconds 8` produced valid output.
  - `analyze.py` + `data_quality_check.py --strict` passed on smoke output.

## 2026-03-01 (1h validation + visualization)

### Summary
- Ran a 1h capture validation and post-run analysis/strict QA.
- Generated interactive chart for latest run.
- Standardized operating policy: create a new output file on each run (no append for QA/backtest inputs).

### Runtime Results
- File analyzed:
  - `mm_core/out/kraken_bbo_1h_test.csv`
- `analyze.py` (latest run segment):
  - `runs_detected=4`, `samples=46165`
  - `p50=15.497ms`, `p95=54.160ms`, `p99=114.128ms`, `unsafe_share=1.78%`
- `data_quality_check.py --strict`:
  - `qa_status=PASS`
  - backward timestamp share `3.35%` (below strict threshold)
- Note:
  - run segmentation indicates file reuse/appending; latest run duration ~883s.
  - use unique output file per run going forward.

### Visualization
- Added/validated scripts:
  - `mm_core/visualize_bbo.py` (static PNG outputs)
  - `mm_core/visualize_bbo_interactive.py` (interactive HTML with toggles/zoom)
- Latest interactive output:
  - `mm_core/out/plots/kraken_bbo_1h_test_2026-03-01_interactive.html`

### Interpretation Snapshot
- The captured hour showed strong selloff conditions:
  - mid change about `-1.94%`, range about `1205` points.
  - spread tails widened (`p95` and `max` elevated).
