# Next Chat Prompt (Ready to Paste)

You are continuing the `mm_core` project at `c:\Users\syzdy\python\mm_core`.

Read first:
1. `mm_core/=== PROJECT HANDOFF PACK ===.txt`
2. `mm_core/HANDOVER_LOG.md`

Current facts:
- Collector/analyzer/QA are operational.
- Collector has reconnect/backoff plus periodic offset refresh guardrails.
- Analyzer legacy parsing bug is fixed.
- Unit tests exist and pass (9 tests).
- Visualization scripts exist:
  - `mm_core/visualize_bbo.py`
  - `mm_core/visualize_bbo_interactive.py`
- Main unresolved risk is long-run contiguous run quality validation.

Primary tasks:
1. Validate Step 1 on fresh unique-file captures (1h then 24h), strict QA gated.
2. Build historical store batch pipeline (partitioned Parquet + manifest).
3. Add lightweight fair baseline script (`mid`, `microprice`, 1s directional check).
4. Update README with baseline + visualization commands.

Constraints:
- Keep `mm_core/` as canonical project root.
- Do not touch `kraken_latency/` unless explicitly requested.
- Use new output file per run (no append) for QA/backtesting inputs.
- Do not break collector CSV schema without explicit schema versioning.
