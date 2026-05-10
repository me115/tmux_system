## Why

The current tmux workflow can keep many Codex terminals alive, but it does not provide a durable task index, reliable task status, WAIT-first prioritization, or notifications when an agent turn needs human input. A local command-line task manager will make long-running AI terminal work usable from both iTerm2 and remote mobile SSH sessions.

## What Changes

- Add a local `aitask` command-line task manager for creating, listing, opening, and updating AI tasks backed by tmux windows.
- Track task metadata outside tmux so each task has a stable ID, title, status, tmux target, working directory, timestamps, and last notification summary.
- Launch one tmux window per AI task and start Codex inside that window with enough environment/context to identify the task.
- Integrate Codex turn-completion notifications so a finished agent turn can mark the task `WAIT`, move it to the top of the tmux window list, and notify the user.
- Provide a terminal-friendly task list and navigation flow that works over SSH on mobile as well as in local iTerm2.
- Support manual status changes for `RUNNING`, `WAIT`, `DONE`, and `ERR`, with room for later automation via tmux hooks.

## Capabilities

### New Capabilities

- `ai-task-management`: Manage AI-assisted terminal tasks with stable IDs, statuses, tmux bindings, and terminal-friendly commands.
- `tmux-task-runtime`: Use tmux sessions, windows, panes, and window options as the persistent runtime for each task.
- `codex-task-notifications`: Convert Codex turn-completion events into task status transitions, prioritization, and user notifications.

### Modified Capabilities

- None.

## Impact

- Adds a local CLI/TUI surface, likely under a script or small app such as `aitask`.
- Adds a local persistent task store, preferably SQLite for durable metadata and ordered queries.
- Adds tmux integration commands for creating windows, selecting windows, renaming windows, setting tmux metadata, and moving WAIT windows forward.
- Adds Codex `notify` configuration and a notification handler script.
- May add optional notification adapters for macOS desktop notifications and Feishu webhook messages.
