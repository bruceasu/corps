# OpenSpec Finance Extension

Use this profile when generating or reviewing OpenSpec-style documentation for financial admin, operations, reporting, risk, finance, or analytics systems.

## Required Files

```text
specs/
requirements.md
design.md
tasks.md
metrics.md
permissions.md
audit.md
release.md
```

## Finance Gates

### Decision Gate

`requirements.md` must explain who sees what, what judgment they make, what action follows, and what business loss or risk exists without the change.

### Metrics Gate

`metrics.md` must define business definition, formula, unit, time dimension, refresh frequency, source system/table/field mapping, owner, currency, precision, rounding, cut-off, and consistency checks.

### Permission Gate

`permissions.md` must distinguish view, export, edit, approval, field-level, and data-scope permissions.

### Audit Gate

`audit.md` must cover sensitive actions with actor, timestamp, action, target, before value, after value, reason, request id or trace id, queryability, and retention.

### Release Gate

`release.md` must cover schema, data, metrics, permissions, audit, rollback, observability, operational support, and final GO / GO WITH RISK / NO GO decision.
