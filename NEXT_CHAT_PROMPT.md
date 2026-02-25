# Next Chat Prompt (Ready to Paste)

You are continuing the `mm_core` project at `c:\Users\syzdy\python\mm_core`.

Read first:
1. `mm_core/=== PROJECT HANDOFF PACK ===.txt`
2. `mm_core/HANDOVER_LOG.md`

Current facts:
- Collector/analyzer/QA are operational.
- Collector has reconnect/backoff.
- Analyzer legacy parsing bug is fixed.
- Unit tests exist and pass (`python -m unittest discover -s mm_core\tests -p "test_*.py" -v`).
- Main unresolved risk is long-run latency quality and potential clock-offset drift.

Primary tasks:
1. Implement periodic clock-offset refresh/drift guard in `collector.py`.
2. Add lightweight fair baseline script (`mid`, `microprice`, 1s directional check).
3. Update README with baseline command.
4. Re-run clean 24h collection and strict QA gate.

Constraints:
- Keep `mm_core/` as canonical project root.
- Do not touch `kraken_latency/` unless explicitly requested.
- Do not break collector CSV schema without explicit schema versioning.
