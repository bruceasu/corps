## Problem Statement

Saved chat knowledge is manually created and searchable only through the knowledge CLI. Tool and skill outcomes are not recorded by their execution paths, and retrieved records are not supplied to chat planning. The lexical tokenizer excludes Chinese terms, causing Chinese queries to fall back to recent records instead of relevant memory.

## Solution

Create a bounded retrieval-memory loop: capture curated chat, tool, and skill outcomes with provenance; retrieve relevant records for a new task; inject a small labelled memory context into planning; and support Chinese as well as Latin-script search.

## User Stories

1. As a Chinese-speaking user, I want prior relevant work found from a Chinese request, so that I do not repeat solved work.
2. As a chat user, I want useful task history available automatically at planning time, so that saved memory affects future answers.
3. As an operator, I want to know where a recalled fact came from and how old it is, so that I can judge whether to trust it.
4. As a tool user, I want successful and failed executions recorded with safe summaries, so that repeated failures can be avoided.
5. As a privacy-conscious user, I want sensitive content excluded or bounded before persistence and prompt injection.
6. As an existing user, I want the current knowledge CLI to remain usable, so that scripts and workflows stay compatible.

## Implementation Decisions

- Retain the local JSONL store as the initial persistence format; add a versioned record schema and migration-tolerant reader.
- Use CJK-friendly lexical retrieval first, with a defined adapter seam for optional semantic retrieval later.
- Separate raw evidence from compact recall cards; only cards are eligible for prompt injection.
- Retrieve at planning time using current user intent and bounded recent session context.
- Do not automatically treat model-generated summaries as trusted instructions.

## Testing Decisions

- Test the public record/search and planning-context seams with temporary directories and deterministic records.
- Include Chinese query relevance, provenance, redaction/bounds, ranking, and no-match cases.
- Use existing knowledge CLI behaviour as compatibility prior art.

## Out of Scope

- Cloud vector databases, cross-user memory sharing, background embedding jobs, and automatic deletion policy enforcement beyond local configurable retention.

## Further Notes

%% Define the exact sensitive-field redaction rules from the project's tool metadata before enabling automatic capture of all arguments.
