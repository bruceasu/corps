## Context

`ProblemKnowledgeStore` persists JSONL records and individual Markdown copies, but only explicit chat commands call it. Its tokenizer strips all Chinese characters, and retrieval is disconnected from `DPEFOrchestrator`.

## Decision

Add a `MemoryService` at the existing knowledge-store seam. It has three responsibilities:

1. record normalized outcome events with provenance and retention-safe fields;
2. return ranked `MemoryRecall` cards for a query and scope;
3. render bounded recall cards as untrusted context for planning.

The first ranking implementation is deterministic lexical search. Latin terms use normalized token matching; CJK text uses overlapping character n-grams. Ranking incorporates query match, record status, recency, and explicit scope without treating success as proof of correctness.

Raw session transcripts remain available only as bounded source material. Recall cards contain title, source, timestamp, status, compact summary, and opaque record id. The orchestrator asks for recalls once before planning and labels them as historical, untrusted context.

## Data and Compatibility

Existing records remain readable. New records add a schema version, stable id, origin/run metadata when available, and sensitivity classification. JSONL appends and Markdown exports continue for local inspection.

## Safety and Retention

Capture applies field bounds and redaction before persistence. Prompt injection receives only bounded recall cards, never raw arguments or full transcripts by default.
