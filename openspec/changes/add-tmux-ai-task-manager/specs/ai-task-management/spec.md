## ADDED Requirements

### Requirement: Create AI task records
The system SHALL provide a command-line interface that creates an AI task with a stable numeric or short unique ID, title, status, working directory, command, tmux session, tmux window identifier, tmux pane identifier, creation timestamp, and update timestamp.

#### Scenario: Create task with title
- **WHEN** the user runs `aitask new "Fix login timeout"` from a project directory
- **THEN** the system creates a task record titled `Fix login timeout`
- **AND** the task record includes a stable task ID
- **AND** the task record includes the current directory as its working directory
- **AND** the task status is `RUNNING` unless the user explicitly requests another initial status

#### Scenario: Create task with explicit session and directory
- **WHEN** the user runs `aitask new "Review API design" --session openclaw --cwd /repo/openclaw`
- **THEN** the system creates the task in the `openclaw` tmux session
- **AND** the task record stores `/repo/openclaw` as its working directory

### Requirement: List tasks in priority order
The system SHALL provide a terminal-friendly task list that orders tasks by attention priority, with `WAIT` tasks before `RUNNING`, `PENDING`, `ERR`, and `DONE` tasks.

#### Scenario: WAIT tasks appear first
- **WHEN** the user runs `aitask list`
- **THEN** every `WAIT` task appears before non-WAIT active tasks
- **AND** each row includes task ID, status, title, tmux target, and last update time

#### Scenario: Filter by status
- **WHEN** the user runs `aitask list --status WAIT`
- **THEN** the output includes only tasks with status `WAIT`

### Requirement: Open task from command line
The system SHALL provide a command that opens a task by ID and transitions `WAIT` tasks to `RUNNING` before selecting or attaching to the associated tmux window.

#### Scenario: Open waiting task
- **WHEN** the user runs `aitask open 12` for a task with status `WAIT`
- **THEN** the system changes task `12` to `RUNNING`
- **AND** the associated tmux window name reflects `RUNNING`
- **AND** the user is attached to or switched into the associated tmux window

#### Scenario: Open already running task
- **WHEN** the user runs `aitask open 12` for a task with status `RUNNING`
- **THEN** the system leaves the status as `RUNNING`
- **AND** the user is attached to or switched into the associated tmux window

### Requirement: Manually update task status
The system SHALL provide command-line status updates for `PENDING`, `RUNNING`, `WAIT`, `DONE`, and `ERR`.

#### Scenario: Mark task done
- **WHEN** the user runs `aitask done 12`
- **THEN** the system changes task `12` to `DONE`
- **AND** the associated tmux window name reflects `DONE`

#### Scenario: Mark task error
- **WHEN** the user runs `aitask err 12 "tests failed"`
- **THEN** the system changes task `12` to `ERR`
- **AND** the task stores `tests failed` as the latest status message

### Requirement: Operate over mobile SSH
The system SHALL keep all required workflows usable through plain terminal commands without depending on iTerm2-only features, mouse input, or a graphical desktop.

#### Scenario: Mobile user selects task by ID
- **WHEN** the user connects over SSH from a mobile terminal and runs `aitask list`
- **THEN** the user can identify a task ID from compact text output
- **AND** the user can run `aitask open <id>` to enter that task

### Requirement: Synchronize task records with runtime state
The system SHALL provide a sync command that detects missing tmux windows, missing task metadata, and stale task statuses where they can be inferred safely.

#### Scenario: Task window is missing
- **WHEN** the user runs `aitask sync` and a task's tmux window no longer exists
- **THEN** the system marks the task `ERR` or reports it as orphaned
- **AND** the system does not delete the task record without explicit user confirmation

