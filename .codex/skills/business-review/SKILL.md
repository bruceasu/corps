---
name: business-review
description: business value review workflow for financial admin and analytics product requests. use when a user asks whether a requirement, dashboard, report, workflow, or operational tool is worth building. evaluate revenue, risk reduction, labor cost, decision efficiency, regulatory needs, customer experience, cost-benefit, smaller alternatives, and validation paths. output approve, reduce, or hold.
---

# Business Review

Use this skill to decide whether a financial admin, reporting, risk, operations, finance, or analytics request is worth pursuing.

## Decision Rules

Return one of:

- `APPROVE`: value is clear, cost is proportionate, and scope is constrained.
- `REDUCE`: value exists, but scope is too large or validation is needed first.
- `HOLD`: value is unclear, decision flow is weak, or no value dimension is met.

A request must hit at least one value dimension:

- Increase revenue
- Reduce risk
- Reduce manual labor cost
- Improve decision speed or accuracy
- Satisfy regulatory, audit, or compliance requirements
- Improve customer experience

If none are met, default to `HOLD`.

## Workflow

1. Identify the value dimension.
2. Estimate benefit qualitatively or quantitatively.
3. Estimate cost.
   - Development cost
   - Maintenance cost
   - Data governance cost
   - Operational training cost
   - Compliance/audit overhead
4. Challenge scope.
   - Is there a smaller useful version?
   - Can this be validated manually first?
   - Can an existing report, query, or process solve 80%?
5. Produce the decision.

## Output Format

```markdown
# Business Review

## Decision
APPROVE / REDUCE / HOLD

## Value Matrix
| Dimension | Evidence | Strength |
|---|---|---|

## Cost vs Benefit
| Cost Type | Estimate | Notes |
|---|---|---|

## Scope Challenge
- Smaller version:
- Manual validation option:
- Existing alternative:

## Required Conditions

## Recommendation
```

## Reference

Use `references/value-matrix.md` when a more formal value assessment is needed.
