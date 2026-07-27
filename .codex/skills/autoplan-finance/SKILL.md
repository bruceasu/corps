---
name: autoplan-finance
description: planning orchestrator for financial product decision workflows across office hours, business review, metrics review, engineering review, and release readiness review. use when a user wants a complete plan.md for a financial admin, operations, reporting, dashboard, risk, finance, or analytics requirement. enforce decision flow, metrics governance, permissions, auditability, and release gates. generate structured planning output only. do not code, modify files, or create pull requests.
---

# Autoplan Finance

Use this skill to generate a complete planning document for a financial admin, operations, reporting, finance, risk, or analytics requirement.

## Hard Rules

- Do not write code.
- Do not modify repository files.
- Do not create pull requests.
- Do not invent missing business rules, data sources, permissions, or audit requirements.
- If inputs are incomplete, produce a plan with explicit unknowns and decision gates.

## Workflow

Run the planning sequence conceptually:

1. Office Hours Finance: clarify problem, stakeholders, decision flow, scope, and unknowns.
2. Business Review: determine `APPROVE`, `REDUCE`, or `HOLD`.
3. Metrics Review: define metrics, formulas, sources, owners, and consistency risks.
4. Engineering Review Finance: define architecture, data flow, permissions, audit, failure modes, observability, and testing.
5. Release Review: assess schema, data, metrics, permissions, audit, rollback, and monitoring readiness when the plan is near launch.
6. Produce `PLAN.md`.

## Decision Gates

- If the decision flow is missing, mark plan status as `BLOCKED: unclear decision flow`.
- If business value is weak, mark plan status as `HOLD` or `REDUCE`.
- If metric definitions are missing, mark the metrics section as `INCOMPLETE`.
- If metrics lack business definition, formula, source fields, owner, currency/precision handling, or time-window semantics, block downstream engineering decisions.
- If permissions are missing, mark architecture as `INCOMPLETE`.
- If view, export, edit, approval, field-level, or data-scope permissions are undefined, block release readiness.
- If auditability is missing for sensitive actions, mark release readiness as `BLOCKED`.
- If rollback, migration verification, monitoring, or data reconciliation is missing, mark release readiness as `NO GO`.

## Output Format

```markdown
# PLAN.md

## Status
APPROVE / REDUCE / HOLD / BLOCKED

## 1. Problem

## 2. Stakeholders

## 3. Business Value

## 4. Scope
### Must Have
### Should Have
### Nice To Have
### Explicit Non-Goals

## 5. Metrics

## 6. Data Definition

## 7. Architecture

## 8. Permissions

## 9. Audit Requirements

## 10. Testing Strategy

## 11. Release Readiness
GO / GO WITH RISK / NO GO / NOT YET REVIEWED

## 12. Risks

## 13. Milestones

## 14. Open Questions

## 15. Next Review
```

## OpenSpec Finance Profile

When the user asks for OpenSpec-compatible output, use this file set:

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

Use `references/plan-template.md` for the reusable plan format. Use `references/openspec-finance-extension.md` when the user asks to create or review OpenSpec-style documents.
