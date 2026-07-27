# Permission and Audit Checklist

## Permission Model

Define all permission layers, not only page access:

| Action | View | Export | Edit | Approve | Field-Level Restriction | Data-Scope Restriction |
|---|---|---|---|---|---|---|

## Role and Scope Review

For each role, define:

- Role purpose
- Allowed actions
- Denied actions
- Data scope
- Field masking rules
- Export limits
- Approval requirements
- Default access for new users

## Sensitive Actions

Treat these as sensitive by default:

- Customer asset view
- Customer personal information view
- Export customer data
- Edit balances, limits, rates, fees, settlement, or risk flags
- Override workflow status
- Approve financial or operational changes
- Change roles or permissions
- Trigger backfills, recalculations, or data corrections

## Audit Requirements

Each sensitive action must capture:

- Actor
- Timestamp
- Action
- Target entity
- Before value
- After value
- Reason
- Request ID or trace ID
- Source IP or session context when available
- Retention policy

## Blockers

Mark the design `INCOMPLETE` or `HIGH RISK` when:

- Export permission is not separated from view permission.
- Edit permission is not separated from approval permission.
- Field-level or data-scope restrictions are undefined for sensitive data.
- Sensitive actions do not capture before and after values.
- Audit retention is undefined.
- Permission defaults for new roles or users are unclear.
