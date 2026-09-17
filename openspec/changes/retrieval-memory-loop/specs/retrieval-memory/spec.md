## ADDED Requirements

### Requirement: The system SHALL retrieve memory for planning

Before producing a task plan, the orchestrator SHALL request a bounded set of relevant recall cards using the current task intent. Retrieved cards SHALL be labelled as historical, untrusted context.

#### Scenario: Relevant prior outcome

- **WHEN** a new task matches a prior recorded outcome
- **THEN** the planning prompt SHALL include a bounded recall card with source, timestamp, status, and summary.

#### Scenario: No relevant memory

- **WHEN** no record meets the relevance threshold
- **THEN** planning SHALL continue without a memory section.

### Requirement: Search SHALL support CJK queries

The local retrieval implementation SHALL produce relevance terms for CJK text as well as Latin-script text.

#### Scenario: Chinese query

- **WHEN** a user searches for a Chinese phrase represented in a record
- **THEN** the matching record SHALL rank ahead of unrelated recent records.

### Requirement: Execution outcomes SHALL be captured safely

Tool and skill execution paths SHALL submit an outcome record containing source, status, capability identity, and bounded diagnostic summary. Sensitive values SHALL be redacted or omitted before persistence.

#### Scenario: Failed tool execution

- **WHEN** a tool returns a failure envelope
- **THEN** a failure memory record SHALL be stored without unbounded output or sensitive arguments.

### Requirement: Recall SHALL preserve provenance

Each recall card SHALL identify its record source and creation time, and SHALL NOT present prior model output as authoritative instructions.

#### Scenario: Recalled historical result

- **WHEN** a record is selected for planning recall
- **THEN** its card SHALL include the source and creation time
- **AND** it SHALL be labelled as historical, untrusted context.
