# Metrics Governance Rules

## Non-Negotiable Rule

Do not only ask how to query the data. First define what the number means in business terms.

## Required Fields

Every metric must define:

- Metric name
- Business definition
- Formula
- Unit
- Time dimension
- Refresh frequency
- Source system
- Source table
- Source fields
- Business owner
- Technical owner
- Known limitations
- Status: READY, INCOMPLETE, or CONFLICT

## Financial Correctness

Check:

- Currency and base reporting currency
- FX source and conversion timestamp
- Decimal precision
- Rounding mode
- Time zone
- Business day cut-off
- Settlement cycle or value date
- Snapshot versus ledger transaction semantics
- Deduplication rule
- Inclusion and exclusion rules for test, frozen, closed, internal, or abnormal accounts

## Consistency Review

Before approving a metric, check whether it conflicts with:

- Existing metric registry definitions
- Finance reporting definitions
- Risk exposure definitions
- Management reporting definitions
- Regulatory reporting definitions
- Existing dashboard labels or aliases

## Status Rules

Use `READY` only when the definition, formula, source mapping, owner, and consistency checks are complete.

Use `INCOMPLETE` when source fields, owners, refresh frequency, time dimension, or financial correctness rules are missing.

Use `CONFLICT` when finance, risk, regulatory, or management reporting definitions disagree and no owner has resolved the difference.

## Blockers

Block downstream engineering review when:

- Metric formula is missing.
- Source table or field mapping is missing.
- Currency or precision handling is undefined for monetary values.
- Time window or business day cut-off is undefined.
- Finance or risk conflict remains unresolved.
- Owner is missing.
