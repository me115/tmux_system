## Context

The user runs many long-lived AI terminal interactions. A typical task is handed to Codex, runs for roughly 20 minutes, and then waits for the user to review output or provide the next instruction. The current tmux workflow preserves terminal state, but it does not provide a structured task list, stable task identifiers, status transitions, WAIT-first prioritization, or cross-device notification behavior.

The system must work locally in iTerm2 and remotely over mobile SSH. Therefore the primary interface must be command-line driven and terminal-portable. iTerm2 features can be optional enhancements, but the core workflow must rely only on tmux, a local task store, and shell commands.

## Goals / Non-Goals

**Goals:**

- Provide a local `aitask` CLI for creating, listing, opening, and updating AI tasks.
- Represent each AI task as one tmux window with a clear task title and status prefix.
- Persist task state outside tmux so task identity survives window renames and can be queried reliably.
- Automatically mark a task `WAIT` when Codex completes an agent turn and needs user attention.
- Move `WAIT` tasks to the front of the tmux window list and show them first in the task list.
- Make the UI usable from local iTerm2 and constrained mobile SSH clients.
- Keep the first implementation small enough to be dependable before adding richer automation.

**Non-Goals:**

- Replacing tmux as the terminal runtime.
- Running AI interactions through Feishu or another chat app as the primary interface.
- Depending on iTerm2 proprietary features for the core workflow.
- Building a web service or daemon in the first version.
- Supporting every AI CLI on day one; Codex is the first-class integration, with an adapter boundary for future tools.

## Decisions

### Decision: Use SQLite as the task source of truth

Use a local SQLite database for task metadata instead of relying on tmux window names alone.

The task record should include:

- `id`
- `title`
- `status`
- `session`
- `window_id`
- `pane_id`
- `cwd`
- `command`
- `created_at`
- `updated_at`
- `last_wait_at`
- `last_message`

Rationale:

- tmux window names are user-visible and easy to change accidentally.
- SQLite supports ordered queries such as WAIT-first lists without adding a service.
- Mobile SSH usage benefits from fast, deterministic command output.
- A database makes future features such as history, archived tasks, and multiple AI tools straightforward.

Alternative considered: JSON file. It is simpler, but concurrent command invocations and ordered queries become more fragile. JSON is acceptable for an early spike, but SQLite is the intended implementation.

### Decision: Keep tmux as the runtime, not the database

Each task runs in one tmux window. The tmux window name mirrors the task state:

```text
WAIT fix-login-timeout
RUNNING design-feishu-router
DONE investigate-codex-notify
```

The task ID and status should also be written to tmux window options:

```bash
tmux set-window-option -t <target> @aitask_id <id>
tmux set-window-option -t <target> @aitask_status <status>
```

Rationale:

- The visible window name provides an immediate mental map.
- tmux options provide a recovery path if the database and tmux layout drift.
- tmux remains responsible for persistence, attach/detach behavior, panes, and terminal state.

Alternative considered: one tmux session per task. That isolates tasks strongly, but task switching and WAIT-first prioritization are less natural. One project/session with many task windows maps better to the desired list and mobile navigation workflow.

### Decision: Make `aitask open` the authoritative entry path

The reliable state transition from `WAIT` to `RUNNING` should happen when the user runs:

```bash
aitask open <id>
```

This command updates the database, renames the tmux window, and attaches/selects the target window. tmux hooks can later provide best-effort synchronization when the user enters a task through raw tmux shortcuts, but the command path is the first version's source of truth.

Rationale:

- tmux hooks can be inconsistent across direct attach, client switching, key bindings, and nested workflows.
- A command path is predictable over local and mobile SSH.
- The command can provide a clean mobile-friendly selection flow.

### Decision: Use Codex notify for `RUNNING -> WAIT`

Configure Codex `notify` to call an `aitask-codex-notify` handler when an agent turn completes. The task launch command should inject task identity into the Codex process:

```bash
AITASK_ID=<id> AITASK_TITLE=<title> codex
```

When the notify handler receives an `agent-turn-complete` event, it should:

1. Resolve the task by `AITASK_ID` or tmux pane metadata.
2. Set task status to `WAIT`.
3. Rename the tmux window to `WAIT <title>`.
4. Move the tmux window near the front of the session.
5. Send a local desktop notification and/or Feishu notification if configured.

Rationale:

- Codex knows when a turn completes; tmux only knows terminal activity.
- A notify handler avoids screen scraping.
- The task manager can remain process-free until events occur.

### Decision: Provide both scriptable commands and a simple terminal list

The initial interface should support:

```bash
aitask new "task title" [--session <name>] [--cwd <path>] [--command codex]
aitask list [--status WAIT]
aitask open <id>
aitask wait <id>
aitask running <id>
aitask done <id>
aitask err <id> [message]
aitask sync
```

`aitask` without subcommands can show a compact numbered list optimized for mobile SSH. Rich TUI interactions can come later.

Rationale:

- Scriptable commands are easy to test and integrate with tmux/Codex.
- Mobile terminals are easier with numeric IDs and short commands than complex full-screen TUIs.
- A later curses/textual/fzf UI can reuse the same database and command layer.

## Risks / Trade-offs

- Codex notify payload or environment may not include enough task identity -> Inject `AITASK_ID` at launch and also write tmux pane/window metadata for fallback lookup.
- User switches directly with raw tmux shortcuts -> Keep the database authoritative through `aitask open`; add `aitask sync` and optional hooks after the MVP.
- tmux window IDs change after restart or restore -> Store stable task IDs and recover by tmux options and title matching where possible.
- WAIT windows moved to the front may disturb user window ordering -> Limit automatic moves to `WAIT` transitions and preserve visible IDs in titles.
- Feishu notification secrets are sensitive -> Keep webhook configuration in a chmod 600 local env file and make notification adapters optional.
- Mobile SSH screens are narrow -> Use compact list formatting and support direct numeric commands.

## Migration Plan

1. Add the `aitask` CLI and initialize the local SQLite store on first use.
2. Add tmux integration for creating task windows, writing tmux metadata, renaming windows, opening windows, and moving WAIT windows.
3. Add manual status commands and WAIT-first task listing.
4. Configure Codex notify to call the task notification handler.
5. Add optional notification adapters for macOS and Feishu.
6. Add `aitask sync` to repair database/tmux drift.
7. Optionally add tmux hooks and richer TUI behavior once the command workflow is stable.

Rollback is simple: remove the Codex notify config line, stop using `aitask`, and continue using tmux windows directly. Existing tmux sessions are not destroyed by the task manager.

## Open Questions

- Should completed task windows remain visible by default, move to a DONE area, or close after confirmation?
- Should the default database live under `~/.local/share/aitask/tasks.db` or inside this repository for easier versioned development?
- Should the first TUI use only Python stdlib/curses, or should it depend on a richer library later?
