## ADDED Requirements

### Requirement: Handle Codex turn completion
The system SHALL provide a Codex notification handler that processes agent turn completion events and maps them to the corresponding AI task.

#### Scenario: Codex turn completes for known task
- **WHEN** Codex emits an `agent-turn-complete` notification for task `12`
- **THEN** the handler resolves task `12`
- **AND** the handler updates task `12` to status `WAIT`
- **AND** the handler records the notification time

#### Scenario: Notification cannot be matched
- **WHEN** the handler receives a Codex notification that cannot be matched to a task
- **THEN** the handler records a diagnostic message
- **AND** the handler does not modify unrelated tasks

### Requirement: Notify user when task needs attention
The system SHALL notify the user when a task transitions to `WAIT` because Codex completed an agent turn.

#### Scenario: Desktop notification configured
- **WHEN** task `12` transitions to `WAIT` and desktop notifications are enabled
- **THEN** the system sends a local notification containing the task title and status

#### Scenario: Feishu notification configured
- **WHEN** task `12` transitions to `WAIT` and Feishu webhook configuration is present
- **THEN** the system sends a Feishu message containing the task title, status, and command to reopen the task

### Requirement: Avoid duplicate WAIT notifications
The system SHALL avoid sending repeated notifications for the same completed turn when the same notification event is processed more than once.

#### Scenario: Duplicate notification event
- **WHEN** the handler receives the same completion event twice for task `12`
- **THEN** the task remains `WAIT`
- **AND** the system sends at most one user notification for that completion

### Requirement: Preserve user control after notification
The system SHALL leave the task terminal open and wait for explicit user interaction after marking a task `WAIT`.

#### Scenario: Task is waiting for user
- **WHEN** task `12` is marked `WAIT`
- **THEN** the tmux window remains available
- **AND** the Codex conversation history remains visible in that window
- **AND** the system does not automatically send a new prompt to Codex

### Requirement: Support notification adapter configuration
The system SHALL allow notification adapters to be enabled or disabled through local configuration without changing task records.

#### Scenario: No external notification configured
- **WHEN** Codex completes a turn and no desktop or Feishu notification adapter is configured
- **THEN** the system still marks the task `WAIT`
- **AND** the system still reorders the task list and tmux window
