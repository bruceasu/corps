---
name: office-hours-finance
description: financial product intake and scope reduction workflow for admin platforms, operations tools, risk dashboards, finance reports, and analytics systems. use when a user wants to clarify a financial backend requirement, discover the real business problem, identify stakeholders, map the decision flow, reduce scope, and list unknowns before design or implementation. do not use for coding or implementation.
---

# Office Hours Finance

Use this skill to turn vague financial admin, operations, reporting, risk, finance, or analytics requests into a decision-centric product brief.

## Hard Rules

- Do not design architecture, database schemas, APIs, UI, code, or implementation tasks.
- Do not accept feature-centric wording such as "add a page", "add a button", or "make a report" as sufficient.
- Require a clear decision flow: who is in what situation, sees what signal, makes what judgment, triggers what action, and what downstream impact follows.
- If the request has no decision or operational action, recommend `HOLD` or a smaller validation step.
- Prefer scope reduction over expansion.

## Workflow

1. Identify the problem.
   - Who has the problem?
   - How often does it happen?
   - What is the business impact?
   - How is it handled today?

2. Map the decision flow.
   - User or stakeholder
   - Data or signal they inspect
   - Judgment they make
   - Action they take
   - Downstream owner or system affected

3. Map stakeholders.
   - Operations
   - Customer support
   - Risk
   - Finance
   - Audit
   - Management
   - Engineering or data team

4. Reduce scope.
   - Must Have: needed for the first useful decision/action
   - Should Have: important but not required for first release
   - Nice To Have: defer by default

5. List unknowns.
   - Missing data
   - Undefined business rules
   - Undefined metric definitions
   - Undefined permissions
   - Undefined audit or retention requirements
   - Unclear operational owner

## Output Format

Use this structure:

```markdown
# Problem Brief

## Problem

## Current Workaround

## Decision Flow
| Actor | Situation | Sees | Decides | Acts | Downstream Impact |
|---|---|---|---|---|---|

## Stakeholders

## Scope
### Must Have
### Should Have
### Nice To Have

## Unknowns

## Recommendation
Proceed to business-review / metrics-review / hold / validate manually first.
```

## Reference

Use `references/intake-template.md` when the user wants a reusable intake document.
