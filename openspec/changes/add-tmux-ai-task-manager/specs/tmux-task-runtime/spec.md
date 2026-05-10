## ADDED Requirements

### Requirement: Create one tmux window per task
The system SHALL represent each active AI task as a dedicated tmux window inside a selected tmux session.

#### Scenario: Create task window
- **WHEN** the user creates a task in session `clipcap`
- **THEN** the system creates a tmux window in session `clipcap`
- **AND** the window starts in the task working directory
- **AND** the window title includes the task status and title

### Requirement: Store task metadata in tmux window options
The system SHALL write task identity and status into tmux window options so tmux state can be correlated with the persistent task store.

#### Scenario: Window metadata is written
- **WHEN** the system creates or updates a task window
- **THEN** the tmux window option `@aitask_id` contains the task ID
- **AND** the tmux window option `@aitask_status` contains the current task status

### Requirement: Start Codex with task context
The system SHALL start Codex in the task window with environment variables or equivalent context that identify the task to notification handlers.

#### Scenario: Codex receives task identity
- **WHEN** the system launches Codex for task `12`
- **THEN** the Codex process receives `AITASK_ID=12`
- **AND** the Codex process receives the task title through `AITASK_TITLE` or an equivalent context variable

### Requirement: Rename tmux windows on status changes
The system SHALL keep the tmux window name synchronized with the persisted task status and title.

#### Scenario: Task becomes waiting
- **WHEN** task `12` transitions to `WAIT`
- **THEN** the associated tmux window name begins with `WAIT`
- **AND** the window name still includes the task title

#### Scenario: Task becomes running
- **WHEN** task `12` transitions to `RUNNING`
- **THEN** the associated tmux window name begins with `RUNNING`
- **AND** the window name still includes the task title

### Requirement: Prioritize waiting windows
The system SHALL move a task's tmux window toward the front of its session when the task transitions to `WAIT`.

#### Scenario: Waiting task moves forward
- **WHEN** a Codex notification changes task `12` from `RUNNING` to `WAIT`
- **THEN** the system moves the associated tmux window before non-WAIT task windows where tmux permits it
- **AND** the system preserves the task's tmux metadata after the move

### Requirement: Preserve tmux as the durable terminal runtime
The system SHALL use tmux attach, detach, windows, and panes as the durable runtime for task terminals without requiring a background web service.

#### Scenario: User detaches and returns
- **WHEN** the user detaches from tmux while a task is running
- **THEN** the task window remains alive inside tmux
- **AND** the user can later run `aitask open <id>` to return to the same task window

