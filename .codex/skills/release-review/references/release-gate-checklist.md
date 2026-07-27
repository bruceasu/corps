# Release Gate Checklist

## Mandatory Gates

A release is blocked if any item is unresolved:

- Rollback plan is absent or untested.
- Permission impact is unknown.
- Audit impact is missing for sensitive actions.
- Migration verification is undefined.
- Data reconciliation is undefined for financial or reporting data.
- Monitoring is missing for the changed critical path.
- Owner is missing for release, rollback, or operational support.

## GO Criteria

- Scope is bounded and documented.
- Schema changes are backward compatible or safely sequenced.
- Backfills are idempotent and verifiable.
- Historical and real-time data impacts are understood.
- Metrics changes are reconciled with finance and risk owners.
- Permissions cover view, export, edit, approval, field-level, and data-scope rules.
- Audit captures actor, timestamp, action, before value, after value, reason, request id or trace id, and retention policy.
- Rollback covers application, schema, data, and feature flag fallback.
- Observability covers logs, metrics, alerts, tracing, data freshness, data quality, permission errors, and audit write failures.

## GO WITH RISK Criteria

- Risks are known and limited in blast radius.
- Recovery is manual but documented.
- Monitoring is sufficient to detect failure quickly.
- Business owner accepts the residual risk.
- Engineering owner is assigned for release support.

## NO GO Criteria

- Missing rollback for data or schema changes.
- New permissions are ambiguous or overly broad.
- Export or edit operations are unaudited.
- Financial metrics can change without reconciliation.
- Migration can corrupt or lock critical production tables.
- No verification exists for backfill correctness.
- No owner is assigned for rollback or post-release monitoring.
