## 1. Memory model and storage

- [ ] 1.1 Add versioned outcome and recall-card models while retaining read compatibility for existing JSONL records.
- [ ] 1.2 Add bounded, redacted persistence helpers and stable record identifiers.
- [ ] 1.3 Wire tool and skill execution outcomes into memory capture.

## 2. Retrieval and planning integration

- [ ] 2.1 Implement deterministic CJK and Latin lexical ranking with scope, status, and recency signals.
- [ ] 2.2 Add a bounded recall API and inject labelled cards into DPEF planning prompts.
- [ ] 2.3 Preserve knowledge CLI list/search behaviour and expose provenance in its output.

## 3. Verification

- [ ] 3.1 Add temporary-store tests for legacy record reads, bounds, redaction, and provenance.
- [ ] 3.2 Add Chinese and Latin relevance/ranking tests.
- [ ] 3.3 Add orchestration tests for recall injection and no-match behaviour.

## TODO

- [ ] Keep retrieval local and lexical in this change; semantic/vector retrieval remains an extension seam only.

## Verification

- [ ] Run focused memory-store and orchestrator tests after implementation approval.

## Notes

- %% Confirm project-wide secret patterns and tool argument classifications before finalizing redaction defaults.
