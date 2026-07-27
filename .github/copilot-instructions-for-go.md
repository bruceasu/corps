# .github/copilot-instructions.md

## Repository onboarding for Copilot

This is a Go codebase maintained with human review and AI assistance.
Prioritize correctness, small diffs, explicit behavior, and verification.

Read `AGENTS.md` first.
This file adds Copilot/GitHub workflow guidance.

---

## Default Behavior

### Plan before coding
For non-trivial tasks, first provide:
- understanding of the task
- affected packages / files
- assumptions
- missing information
- implementation plan
- risks
- validation steps

Do not jump directly into implementation for medium or large changes.

### Keep changes reviewable
- prefer small diffs
- avoid unrelated cleanup
- make behavior changes explicit
- explain non-obvious technical decisions

---

## Go Repository Expectations

- preserve package boundaries
- avoid unnecessary interfaces
- keep context propagation intact
- preserve explicit error handling
- treat concurrency-sensitive changes carefully
- treat exported API changes as compatibility-sensitive

Dependency changes in `go.mod` or `go.sum` are high-risk and should be called out clearly.

---

## Testing and Validation

Every non-trivial change should be validated.

Preferred order:
1. format
2. vet/static checks
3. unit tests
4. integration tests
5. build

If available, prefer:
```bash
./scripts/verify.sh
```

Otherwise use repository-standard commands such as:
```bash
go test ./...
go build ./...
go vet ./...
```
Include in final summaries and PR descriptions:

- validation commands run
- pass/fail status
- anything not verified


## High-Risk Areas

Before making changes, explicitly call out risk when touching:

- exported APIs
- concurrency
- context propagation
- auth/security
- persistence/migrations
- deployment or CI config

These changes should include stronger validation and clearer explanation.

## PR / Issue Alignment

When implementing from a task or issue:

- align to the stated goal
- respect non-goals
- do not silently expand scope
- identify follow-up work separately

Recommended final summary structure:

- summary
- affected packages
- tests / validation
- risks
- follow-ups
- harness improvements suggested
