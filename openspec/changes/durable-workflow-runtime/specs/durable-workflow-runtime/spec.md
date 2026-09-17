## ADDED Requirements

### Requirement: Workflow runs SHALL have durable node state

The runtime SHALL assign each workflow invocation a run identifier and persist node lifecycle transitions and checkpoints locally.

#### Scenario: Process interrupted after a completed node

- **WHEN** a run is interrupted after node A succeeds and before node B completes
- **THEN** resuming the run SHALL preserve A's output reference
- **AND** SHALL NOT execute A again.

### Requirement: Workflow definitions SHALL be validated before execution

The runtime SHALL reject duplicate node identifiers, edges with unknown endpoints, invalid output-key collisions, and unsupported node configurations before any node executes.

#### Scenario: Unknown edge endpoint

- **WHEN** a workflow edge references a node that is absent from the definition
- **THEN** the runtime SHALL return a validation error identifying that edge
- **AND** SHALL execute no tools.

### Requirement: Retries and time limits SHALL be explicit

Each node SHALL have bounded retry and timeout behaviour. A retry SHALL record its attempt and failure reason. The runtime SHALL NOT automatically replay a non-idempotent external action after interruption.

#### Scenario: Retry exhaustion

- **WHEN** a retryable node fails more times than its configured limit
- **THEN** the run SHALL transition to failed
- **AND** the trace SHALL record all attempts.

### Requirement: Runs SHALL be cancellable and inspectable

The runtime SHALL expose terminal run state and per-node status after completion, failure, timeout, or cancellation.

#### Scenario: Cancelled run inspection

- **WHEN** a caller cancels a running workflow
- **THEN** the run SHALL enter the cancelled terminal state
- **AND** inspection SHALL show the last terminal or active state for every node.
