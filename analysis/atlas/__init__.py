"""Procurement Concentration Atlas.

Pre-computed analytical tables over Alberta procurement data
(ab.ab_sole_source + ab.ab_contracts). Agents read from these
tables instead of running ad-hoc SQL — keeps the data layer
defensible (statistical baselines, percentile thresholds) and
the agent layer focused (synthesis + narrative + Q&A).

Entry points:
- build.py — pulls source tables into local DuckDB, computes
  Atlas tables, writes parquet outputs to atlas_data/.
- metrics.py — pure functions (Herfindahl, Gini, top-N share,
  temporal Z-score), reused by build.py and Conductor's
  compute() / code_compute() tools.
- baselines.py — percentile distributions used to derive
  data-driven thresholds (NOT magic numbers).
- known_cases.py — pytest-style assertions: known true-positive
  monopolies must surface at risk_score >= 60.
- quality_audit.py — surfaces data-quality findings as their
  own deliverable (entity-name dupes, placeholder vendors,
  inconsistent province strings).
"""
