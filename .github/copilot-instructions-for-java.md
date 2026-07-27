# .github/copilot-instructions.md

## Repository onboarding for Copilot

This is a Java codebase maintained with human review and AI assistance.
Prioritize correctness, compatibility, and reviewable diffs over speed.

Read `AGENTS.md` first.
This file adds Copilot/GitHub workflow guidance.

---

## Default Behavior

### Plan before coding
For non-trivial tasks, first provide:
- understanding of the task
- affected packages / modules
- assumptions
- missing information
- implementation plan
- risks
- validation steps

Do not jump directly into implementation for medium or large changes.

### Keep PRs reviewable
- prefer small diffs
- avoid unrelated cleanup
- keep behavior changes explicit
- explain non-obvious design choices

---

## Java Repository Expectations

- respect layering and package structure
- keep business logic out of controllers
- preserve service boundaries
- avoid coupling transport and persistence concerns
- treat DTO, schema, and API changes as compatibility-sensitive

If the codebase uses Spring Boot or similar frameworks, follow existing patterns instead of introducing new framework styles.

---

## Testing and Validation

Every non-trivial change should be validated.

Preferred order:
1. compile / style checks
2. unit tests
3. integration tests
4. build

If available, prefer:
```bash
./scripts/verify.sh
```

Otherwise use:

Maven: `mvn test, mvn verify`
Gradle: `./gradlew test`, `./gradlew build`

Include in final summaries and PR descriptions:

- validation commands run
- pass/fail status
- anything not verified

## High-Risk Areas

Before making changes, explicitly call out risk when touching:

- auth / permission logic
- schema / migration logic
- transactions
- external APIs or message formats
- public endpoints
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
- affected modules
- tests / validation
- risks
- follow-ups
- harness improvements suggested

