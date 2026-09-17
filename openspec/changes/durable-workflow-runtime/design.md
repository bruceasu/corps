## Context

`WorkflowEngine.execute` constructs `{input: ...}`, processes a topologically sorted list, and merges each output directly into that dictionary. It cannot distinguish a completed node from a partially executed node after interruption. The parser detects cycles but does not validate duplicate ids or edge references before access.

## Decision

Add a local `RunStore` and `WorkflowRun` model:

```
created -> running -> completed | failed | cancelled
                    node: pending -> running -> succeeded | failed | timed_out | skipped
```

The engine validates a definition before creating the run. It emits lifecycle events before and after each node, persists a snapshot after terminal node transitions, and supports an explicit resume entry point. Completed nodes are not replayed. A failed or interrupted node is only retried when its configured retry policy permits it; external replay requires explicit idempotency metadata.

Context becomes namespaced by node/output key. Unqualified writes that collide with reserved or existing keys fail validation rather than silently overwrite state. Tool execution receives timeout/cancellation information through an adapter, with an initial fallback for legacy callables.

## Compatibility

`WorkflowEngine.execute(config, input_data)` remains supported and creates an ephemeral-or-local durable run by default. Existing sequential skill definitions are parsed into the same ordered nodes. New retry, timeout, idempotency, and output namespace fields are optional.

## Observability

Run status, node attempts, timing, error summaries, and safe output references are inspectable without loading raw tool output into logs.
