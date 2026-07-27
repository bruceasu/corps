---
name: release-review
description: release gate review workflow for financial admin systems, operations platforms, reporting tools, risk dashboards, data pipelines, permission changes, schema migrations, and production deployments. use before launch to check schema changes, rollback strategy, data impact, permission impact, audit impact, monitoring, migration risk, backfill requirements, release readiness, and final go, go with risk, or no go decision.
---

# Release Review

Use this skill to review whether a financial admin, operations, reporting, risk, finance, analytics, dashboard, or data-pipeline change is safe to release.

## Hard Rules

- Do not approve a release without explicit rollback coverage.
- Do not approve a release when permission impact is unknown.
- Do not approve a release when audit impact is missing for sensitive actions.
- Treat schema migrations, backfills, permission changes, export features, customer asset views, finance reports, and risk dashboards as high-risk by default.
- Use `NO GO` when critical data, permission, audit, rollback, or monitoring gaps remain unresolved.
- Do not write implementation code or migration scripts unless the user explicitly asks outside release review.

## Workflow

1. Identify release scope and affected systems.
2. Review schema and migration risk.
3. Review data impact.
4. Review metrics and reporting impact.
5. Review permission impact.
6. Review audit impact.
7. Review rollback and feature-flag strategy.
8. Review observability and operational readiness.
9. Produce a release decision.

## Required Review Areas

### Scope

- Feature or change summary
- Affected services, jobs, tables, dashboards, APIs, and admin screens
- Customer-facing, internal-only, or regulatory impact
- Feature flag or staged rollout availability

### Schema Change

- DDL changes
- Index changes
- Migration lock risk
- Backward compatibility
- Forward compatibility
- Backfill requirement
- Migration verification query

### Data Impact

- Historical data impact
- Real-time data impact
- Recalculation or backfill need
- Data freshness expectation
- Idempotency and duplicate handling
- Reconciliation plan

### Metrics and Reporting Impact

- Changed metric definitions
- Changed aggregation or deduplication logic
- Time-window changes
- Currency, precision, rounding, settlement, or cut-off changes
- Finance, risk, or management reporting conflicts

### Permission Impact

- New view permission
- New export permission
- New edit permission
- New approval permission
- Field-level permission impact
- Data-scope permission impact
- Role migration or default access risk

### Audit Impact

- Sensitive actions introduced or changed
- Required audit fields
- Before/after value capture
- Reason capture
- Request ID or trace ID
- Retention requirement
- Audit queryability

### Rollback

- Application rollback
- Schema rollback
- Data rollback
- Feature flag fallback
- Manual recovery procedure
- Rollback owner
- Rollback verification

### Observability

- Release health dashboard
- Logs
- Metrics
- Alerts
- Tracing
- Data freshness checks
- Data quality checks
- Permission error monitoring
- Audit write failure monitoring

## Decision Rules

Return one of:

- `GO`: critical paths, schema, data, permissions, audit, rollback, and monitoring are confirmed.
- `GO WITH RISK`: risks are known, impact is bounded, owners are assigned, and recovery is credible.
- `NO GO`: unresolved critical gaps remain in rollback, data correctness, permissions, auditability, migration safety, or monitoring.

## Output Format

```markdown
# Release Review

## Decision
GO / GO WITH RISK / NO GO

## Scope

## Release Checklist
| Area | Status | Evidence | Risk | Required Action |
|---|---|---|---|---|

## Schema and Migration

## Data Impact

## Metrics and Reporting Impact

## Permission Impact

## Audit Impact

## Rollback Plan

## Observability and Operations

## Open Risks
| Risk | Severity | Owner | Mitigation | Release Blocker? |
|---|---|---|---|---|

## Final Recommendation
```

## References

- Use `references/release-gate-checklist.md` for detailed release gate criteria.
- Use `references/migration-risk-template.md` for schema and backfill-heavy releases.
