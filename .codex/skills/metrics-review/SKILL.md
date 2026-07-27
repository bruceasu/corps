---
name: metrics-review
description: metrics governance and data definition workflow for financial systems, reporting dashboards, operations analytics, risk metrics, and finance reports. use when a user needs to define, review, reconcile, or validate financial metrics, formulas, data sources, owners, refresh frequency, time dimensions, currency handling, precision, and consistency with finance or risk definitions.
---

# Metrics Review

Use this skill to define or review financial metrics before they are implemented in dashboards, reports, APIs, operational tools, data marts, or decision workflows.

## Hard Rules

- Do not only ask how to query the data; first define what the number means in business terms.
- Do not approve a metric without a business definition, formula, unit, time dimension, refresh frequency, source mapping, and owner.
- Treat financial amount, currency, precision, rounding, time zone, settlement period, and snapshot-vs-transaction ambiguity as high-risk.
- Check whether the metric duplicates or conflicts with existing finance, risk, or management reporting definitions.
- If the source tables or fields are unknown, mark the metric as incomplete.

## Required Checks

For each metric, define:

- Name
- Business definition
- Formula
- Unit
- Time dimension
- Refresh frequency
- Source system
- Source table and field mapping
- Business owner
- Technical owner
- Consistency notes
- Known limitations
- Readiness gate: READY / INCOMPLETE / CONFLICT

## Financial Correctness Checklist

- Currency and base reporting currency
- FX source and conversion timestamp
- Decimal precision and rounding mode
- Time zone and business day cut-off
- Settlement cycle or value date
- Snapshot vs ledger transaction semantics
- Deduplication rule
- Inclusion/exclusion rules for test, frozen, closed, internal, or abnormal accounts

## Output Format

```markdown
# Metrics Spec

## Metric: <name>

### Business Definition

### Formula

### Unit

### Time Dimension

### Refresh Frequency

### Source Systems

### Source Tables and Fields
| System | Table | Field | Transformation | Notes |
|---|---|---|---|---|

### Ownership
- Business Owner:
- Technical Owner:

### Consistency Check
- Existing similar metric:
- Finance conflict:
- Risk conflict:
- Management reporting conflict:

### Financial Correctness Notes

### Known Limitations

### Status
READY / INCOMPLETE / CONFLICT
```

## References

- Use `references/metrics-spec-template.md` for a reusable metrics document.
- Use `references/metrics-governance-rules.md` for detailed metric review rules.
