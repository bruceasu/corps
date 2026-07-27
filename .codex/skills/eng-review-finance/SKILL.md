---
name: eng-review-finance
description: architecture review workflow for financial admin platforms, operations systems, analytics dashboards, reporting systems, and data pipelines. use when a user needs technical design review before implementation, including system boundaries, module responsibilities, data flow, permissions, auditability, failure modes, observability, and testing strategy. do not write code.
---

# Engineering Review Finance

Use this skill to review or draft a financial-system technical design before implementation.

## Hard Rules

- Do not write code, implementation patches, database migrations, or pull requests.
- If metrics are undefined, route to `metrics-review` first.
- If permissions are undefined, do not approve the architecture.
- If view, export, edit, approval, field-level, or data-scope permissions are undefined for sensitive data, mark the design incomplete.
- If audit requirements are absent for sensitive actions, mark the design incomplete.
- If audit does not capture actor, timestamp, action, before value, after value, reason, request id or trace id, and retention policy, mark the design incomplete.
- Prefer explicit boundaries, data contracts, and failure modes over generic architecture prose.

## Workflow

1. Review system boundary.
2. Review module responsibilities.
3. Review data flow.
4. Review permission model.
5. Review auditability.
6. Review failure modes.
7. Review observability.
8. Review testing strategy.
9. List decisions required before implementation.

## Required Review Areas

### Architecture Review
- System boundary
- Module ownership
- External dependencies
- Data contracts
- Backward compatibility

### Data Flow Review
Use this canonical path when applicable:

```text
Source -> ETL/streaming -> warehouse/datamart -> API -> dashboard/admin UI
```

### Permission Review
- View permission
- Export permission
- Edit permission
- Approval permission
- Field-level permission
- Data-scope permission

### Auditability Review
- Actor
- Timestamp
- Action
- Before value
- After value
- Reason
- Request ID or trace ID
- Retention policy

### Failure Mode Review
- Data delay
- Duplicate message
- Missing event
- Partial backfill
- Rollback failure
- Permission misconfiguration
- Stale dashboard data

### Observability Review
- Logs
- Metrics
- Alerts
- Tracing
- Data freshness checks
- Data quality checks

### Testing Review
- Unit
- Integration
- E2E
- Data validation
- Permission tests
- Audit log tests
- Migration and rollback tests

## Output Format

```markdown
# Engineering Review

## Status
READY / INCOMPLETE / HIGH RISK

## System Boundary

## Module Responsibilities

## Data Flow

## Permissions

## Audit Requirements

## Failure Modes
| Failure Mode | Impact | Detection | Mitigation |
|---|---|---|---|

## Observability

## Testing Strategy

## Risks

## Release Readiness Impact
- Schema or migration risk:
- Data impact:
- Permission impact:
- Audit impact:
- Rollback considerations:
- Monitoring required before release:

## Required Decisions Before Implementation
```

## References

- Use `references/architecture-review-template.md` for a complete review document.
- Use `references/data-flow-template.md` for data pipeline designs.
- Use `references/permission-audit-checklist.md` for permission and audit review.
