## 1. Project Shape and Storage

- [x] 1.1 Decide the initial executable location and packaging approach for `aitask`.
- [x] 1.2 Implement first-run configuration paths for the task database and optional notification settings.
- [x] 1.3 Create the SQLite schema for tasks, task events, and notification deduplication.
- [x] 1.4 Implement task repository functions for create, read, list, update status, and append event.
- [x] 1.5 Add database initialization and migration handling.

## 2. tmux Runtime Integration

- [x] 2.1 Implement tmux command wrapper utilities with structured errors.
- [x] 2.2 Implement session detection and creation for task sessions.
- [x] 2.3 Implement task window creation with working directory selection.
- [x] 2.4 Store `@aitask_id` and `@aitask_status` tmux window options for each task window.
- [x] 2.5 Rename task windows when status or title changes.
- [x] 2.6 Move WAIT task windows before non-WAIT task windows where tmux permits it.
- [x] 2.7 Implement runtime lookup by task ID, window ID, pane ID, and tmux metadata.

## 3. CLI Workflow

- [x] 3.1 Implement `aitask new "title" [--session <name>] [--cwd <path>] [--command <cmd>]`.
- [x] 3.2 Launch Codex in the task window with `AITASK_ID` and `AITASK_TITLE` context.
- [x] 3.3 Implement `aitask list` with compact WAIT-first output suitable for mobile SSH.
- [x] 3.4 Implement `aitask list --status <status>` filtering.
- [x] 3.5 Implement `aitask open <id>` to transition WAIT tasks to RUNNING and enter the tmux window.
- [x] 3.6 Implement manual status commands: `pending`, `running`, `wait`, `done`, and `err`.
- [x] 3.7 Implement `aitask sync` to detect missing tmux windows and stale metadata.
- [x] 3.8 Implement helpful command errors for missing tmux, invalid task IDs, and missing sessions.

## 4. Codex Notification Integration

- [x] 4.1 Implement `aitask-codex-notify` to read Codex notification payloads from stdin or argv as configured.
- [x] 4.2 Resolve the task from `AITASK_ID`, tmux metadata, or safe fallback context.
- [x] 4.3 Handle `agent-turn-complete` by changing the task status to WAIT.
- [x] 4.4 Record notification timestamps and last messages on the task record.
- [x] 4.5 Deduplicate repeated notification events for the same completed turn.
- [x] 4.6 Document the required Codex `notify` configuration.

## 5. User Notifications

- [x] 5.1 Implement an optional macOS desktop notification adapter.
- [x] 5.2 Implement an optional Feishu webhook notification adapter using local config.
- [x] 5.3 Include task title, status, and `aitask open <id>` command in external notifications.
- [x] 5.4 Ensure task status still changes to WAIT when no external notification adapter is configured.

## 6. Validation and Documentation

- [x] 6.1 Add command-level smoke tests or scripted checks for storage and status transitions.
- [x] 6.2 Add tmux integration smoke tests that can run against a temporary tmux session.
- [x] 6.3 Verify mobile-friendly output width and direct numeric task opening.
- [x] 6.4 Update `tmux.md` with the final `aitask` workflow after implementation.
- [x] 6.5 Document recovery steps for database/tmux drift and Codex notify misconfiguration.
