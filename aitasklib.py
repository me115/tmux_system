#!/usr/bin/env python3
"""Local tmux-backed AI task manager.

The implementation intentionally uses only Python's standard library so the
same commands work from iTerm2, a remote SSH session, or a constrained mobile
terminal.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import json
import os
import re
import select
import shlex
import sqlite3
import subprocess
import sys
import time
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

STATUSES = {"PENDING", "RUNNING", "WAIT", "DONE", "ERR"}
ACTIVE_STATUSES = {"PENDING", "RUNNING", "WAIT", "ERR"}
RUNNING_MARKERS = ("Working", "esc to interrupt")
TRUST_PROMPT_MARKERS = ("Do you trust the contents of this directory?", "Press enter to continue")
IDLE_PROMPT_MARKERS = ("› Implement {feature}",)
ANSI_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
FEISHU_RESULT_CHAR_LIMIT = 3600


class AitaskError(RuntimeError):
    pass


class TmuxError(AitaskError):
    pass


@dataclass(frozen=True)
class Paths:
    config_dir: Path
    data_dir: Path
    db_path: Path
    config_path: Path
    feishu_env_path: Path


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def format_local_time(value: str | None) -> str:
    if not value:
        return ""
    raw = value.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(raw)
    except ValueError:
        return value[:19].replace("T", " ")
    if dt.tzinfo is not None:
        dt = dt.astimezone()
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def default_session_name(cwd: Path) -> str:
    name = cwd.name or "aitasks"
    return "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in name).strip("-") or "aitasks"


def resolve_paths() -> Paths:
    home = Path.home()
    config_dir = Path(os.environ.get("AITASK_CONFIG_DIR", home / ".config" / "aitask")).expanduser()
    data_dir = Path(os.environ.get("AITASK_DATA_DIR", home / ".local" / "share" / "aitask")).expanduser()
    db_path = Path(os.environ.get("AITASK_DB", data_dir / "tasks.db")).expanduser()
    return Paths(
        config_dir=config_dir,
        data_dir=data_dir,
        db_path=db_path,
        config_path=config_dir / "config.json",
        feishu_env_path=config_dir / "feishu.env",
    )


def load_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip("'\"")
    return values


def load_config(paths: Paths) -> dict[str, Any]:
    config: dict[str, Any] = {}
    if paths.config_path.exists():
        try:
            loaded = json.loads(paths.config_path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                config.update(loaded)
        except json.JSONDecodeError as exc:
            raise AitaskError(f"Invalid config JSON: {paths.config_path}: {exc}") from exc
    env_values = load_env_file(paths.feishu_env_path)
    for key, value in env_values.items():
        os.environ.setdefault(key, value)
    return config


class Store:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.row_factory = sqlite3.Row
        self.init_db()

    def close(self) -> None:
        self.conn.close()

    def init_db(self) -> None:
        self.conn.executescript(
            """
            PRAGMA journal_mode = WAL;
            PRAGMA foreign_keys = ON;

            CREATE TABLE IF NOT EXISTS schema_migrations (
              version INTEGER PRIMARY KEY,
              applied_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS tasks (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              title TEXT NOT NULL,
              status TEXT NOT NULL CHECK (status IN ('PENDING','RUNNING','WAIT','DONE','ERR')),
              session TEXT NOT NULL,
              window_id TEXT,
              pane_id TEXT,
              cwd TEXT NOT NULL,
              command TEXT NOT NULL,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              last_wait_at TEXT,
              last_message TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_tasks_status_updated ON tasks(status, updated_at);
            CREATE INDEX IF NOT EXISTS idx_tasks_session_window ON tasks(session, window_id);
            CREATE INDEX IF NOT EXISTS idx_tasks_pane ON tasks(pane_id);

            CREATE TABLE IF NOT EXISTS task_events (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              task_id INTEGER,
              event_type TEXT NOT NULL,
              message TEXT,
              payload_json TEXT,
              created_at TEXT NOT NULL,
              FOREIGN KEY(task_id) REFERENCES tasks(id) ON DELETE SET NULL
            );

            CREATE TABLE IF NOT EXISTS notification_events (
              event_key TEXT PRIMARY KEY,
              task_id INTEGER,
              event_type TEXT NOT NULL,
              payload_json TEXT,
              created_at TEXT NOT NULL,
              FOREIGN KEY(task_id) REFERENCES tasks(id) ON DELETE SET NULL
            );
            """
        )
        self.conn.execute(
            "INSERT OR IGNORE INTO schema_migrations(version, applied_at) VALUES (?, ?)",
            (1, now_iso()),
        )
        self.conn.commit()

    def create_task(self, *, title: str, status: str, session: str, cwd: str, command: str) -> sqlite3.Row:
        ts = now_iso()
        cur = self.conn.execute(
            """
            INSERT INTO tasks(title, status, session, cwd, command, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (title, status, session, cwd, command, ts, ts),
        )
        task = self.get_task(cur.lastrowid)
        assert task is not None
        self.append_event(task["id"], "created", f"{status} {title}")
        return task

    def get_task(self, task_id: int) -> sqlite3.Row | None:
        return self.conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()

    def find_task_by_pane(self, pane_id: str) -> sqlite3.Row | None:
        return self.conn.execute("SELECT * FROM tasks WHERE pane_id = ?", (pane_id,)).fetchone()

    def list_tasks(self, status: str | None = None, include_done: bool = True) -> list[sqlite3.Row]:
        where = ""
        params: tuple[Any, ...] = ()
        if status:
            where = "WHERE status = ?"
            params = (status,)
        elif not include_done:
            where = "WHERE status != 'DONE'"
        query = f"""
            SELECT * FROM tasks
            {where}
            ORDER BY
              CASE status
                WHEN 'WAIT' THEN 0
                WHEN 'RUNNING' THEN 1
                WHEN 'PENDING' THEN 2
                WHEN 'ERR' THEN 3
                WHEN 'DONE' THEN 4
                ELSE 5
              END,
              COALESCE(last_wait_at, updated_at) DESC,
              id DESC
        """
        return list(self.conn.execute(query, params))

    def update_runtime(self, task_id: int, *, window_id: str | None, pane_id: str | None) -> None:
        self.conn.execute(
            "UPDATE tasks SET window_id = ?, pane_id = ?, updated_at = ? WHERE id = ?",
            (window_id, pane_id, now_iso(), task_id),
        )
        self.conn.commit()

    def update_status(self, task_id: int, status: str, message: str | None = None) -> sqlite3.Row:
        if status not in STATUSES:
            raise AitaskError(f"Invalid status: {status}")
        ts = now_iso()
        last_wait_at = ts if status == "WAIT" else None
        if status == "WAIT":
            self.conn.execute(
                """
                UPDATE tasks
                SET status = ?, updated_at = ?, last_wait_at = ?, last_message = COALESCE(?, last_message)
                WHERE id = ?
                """,
                (status, ts, last_wait_at, message, task_id),
            )
        else:
            self.conn.execute(
                """
                UPDATE tasks
                SET status = ?, updated_at = ?, last_message = COALESCE(?, last_message)
                WHERE id = ?
                """,
                (status, ts, message, task_id),
            )
        self.append_event(task_id, f"status:{status}", message, commit=False)
        self.conn.commit()
        task = self.get_task(task_id)
        if task is None:
            raise AitaskError(f"Task not found: {task_id}")
        return task

    def append_event(
        self,
        task_id: int | None,
        event_type: str,
        message: str | None = None,
        payload: Any | None = None,
        *,
        commit: bool = True,
    ) -> None:
        self.conn.execute(
            """
            INSERT INTO task_events(task_id, event_type, message, payload_json, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (task_id, event_type, message, json.dumps(payload, ensure_ascii=False) if payload is not None else None, now_iso()),
        )
        if commit:
            self.conn.commit()

    def insert_notification_event(self, event_key: str, task_id: int | None, event_type: str, payload: Any) -> bool:
        try:
            self.conn.execute(
                """
                INSERT INTO notification_events(event_key, task_id, event_type, payload_json, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (event_key, task_id, event_type, json.dumps(payload, ensure_ascii=False), now_iso()),
            )
            self.conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False


def run_tmux(args: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    cmd = ["tmux", *args]
    try:
        proc = subprocess.run(cmd, text=True, capture_output=True, check=False)
    except FileNotFoundError as exc:
        raise TmuxError("tmux is not installed or not in PATH") from exc
    if check and proc.returncode != 0:
        stderr = proc.stderr.strip() or proc.stdout.strip()
        raise TmuxError(f"tmux {' '.join(args)} failed: {stderr}")
    return proc


def tmux_has_session(session: str) -> bool:
    return run_tmux(["has-session", "-t", session], check=False).returncode == 0


def ensure_session(session: str, cwd: str) -> None:
    if not tmux_has_session(session):
        run_tmux(["new-session", "-d", "-s", session, "-n", "tasks", "-c", cwd])


def tmux_target(task: sqlite3.Row) -> str:
    if task["window_id"]:
        return task["window_id"]
    return f"{task['session']}:{shell_name(task['status'], task['title'])}"


def shell_name(status: str, title: str) -> str:
    compact = " ".join(title.split())
    if len(compact) > 80:
        compact = compact[:77] + "..."
    return f"{status} {compact}"


def tmux_new_window(task: sqlite3.Row) -> tuple[str, str]:
    target = f"{task['session']}:"
    command = task["command"]
    shell_cmd = f"export AITASK_ID={shlex.quote(str(task['id']))}; export AITASK_TITLE={shlex.quote(task['title'])}; {command}"
    proc = run_tmux(
        [
            "new-window",
            "-P",
            "-F",
            "#{window_id} #{pane_id}",
            "-t",
            target,
            "-n",
            shell_name(task["status"], task["title"]),
            "-c",
            task["cwd"],
            shell_cmd,
        ]
    )
    parts = proc.stdout.strip().split()
    if len(parts) < 2:
        raise TmuxError(f"Could not parse tmux new-window output: {proc.stdout!r}")
    return parts[0], parts[1]


def tmux_set_task_options(task: sqlite3.Row) -> None:
    target = task["window_id"] or f"{task['session']}:"
    run_tmux(["set-window-option", "-t", target, "@aitask_id", str(task["id"])])
    run_tmux(["set-window-option", "-t", target, "@aitask_status", task["status"]])


def tmux_enable_pane_monitor(task: sqlite3.Row, *, replace: bool = False) -> None:
    if not task["pane_id"]:
        return
    if replace:
        run_tmux(["pipe-pane", "-t", task["pane_id"]], check=False)
    command = " ".join(
        [
            shlex.quote(sys.executable),
            shlex.quote(str(Path(__file__).resolve())),
            "_tmux-pane-monitor",
            shlex.quote(str(task["id"])),
            shlex.quote(str(task["pane_id"])),
        ]
    )
    args = ["pipe-pane", "-t", task["pane_id"], command] if replace else ["pipe-pane", "-o", "-t", task["pane_id"], command]
    run_tmux(args, check=False)


def tmux_rename_task_window(task: sqlite3.Row) -> None:
    if task["window_id"]:
        run_tmux(["rename-window", "-t", task["window_id"], shell_name(task["status"], task["title"])])
        tmux_set_task_options(task)


def tmux_window_exists(task: sqlite3.Row) -> bool:
    if not task["window_id"]:
        return False
    proc = run_tmux(["display-message", "-p", "-t", task["window_id"], "#{window_id}"], check=False)
    return proc.returncode == 0 and proc.stdout.strip() == task["window_id"]


def tmux_capture_pane(task: sqlite3.Row, *, lines: int = 80) -> str:
    if not task["pane_id"]:
        return ""
    proc = run_tmux(["capture-pane", "-p", "-t", task["pane_id"], "-S", f"-{lines}"], check=False)
    if proc.returncode != 0:
        return ""
    return proc.stdout


def tmux_capture_recent_pane(task: sqlite3.Row, *, lines: int = 24) -> str:
    captured = tmux_capture_pane(task, lines=lines)
    return "\n".join(captured.splitlines()[-lines:])


def format_task_result_for_feishu(task: sqlite3.Row, *, lines: int = 120) -> str:
    captured = compact_terminal_text(tmux_capture_pane(task, lines=lines))
    if not captured:
        captured = "(no captured pane output)"
    captured = truncate_middle_head(captured, FEISHU_RESULT_CHAR_LIMIT)
    updated = format_local_time(task["updated_at"])
    target = f"{task['session']}:{task['window_id'] or '-'}"
    return "\n".join(
        [
            f"AI task result #{task['id']} [{task['status']}]",
            task["title"],
            f"target: {target}",
            f"updated: {updated}",
            "",
            captured,
        ]
    )


def tmux_move_wait_forward(task: sqlite3.Row) -> None:
    if not task["window_id"]:
        return
    # Position 1 works well with base-index 1 and is accepted even when tmux uses 0.
    proc = run_tmux(["move-window", "-t", f"{task['session']}:1", "-s", task["window_id"]], check=False)
    if proc.returncode != 0:
        # If slot 1 is occupied, tmux may refuse. Swapping is less disruptive than
        # failing the task transition.
        run_tmux(["swap-window", "-t", f"{task['session']}:1", "-s", task["window_id"]], check=False)
    fresh_id = run_tmux(["display-message", "-p", "-t", f"{task['session']}:1", "#{window_id}"], check=False)
    if fresh_id.returncode == 0 and fresh_id.stdout.strip():
        run_tmux(["set-window-option", "-t", fresh_id.stdout.strip(), "@aitask_id", str(task["id"])], check=False)
        run_tmux(["set-window-option", "-t", fresh_id.stdout.strip(), "@aitask_status", task["status"]], check=False)


def apply_status_transition(
    store: Store,
    task: sqlite3.Row,
    status: str,
    message: str | None = None,
    *,
    config: dict[str, Any] | None = None,
    rename_window: bool = True,
    move_wait_forward: bool = True,
    notify_wait: bool = True,
) -> sqlite3.Row:
    previous_status = task["status"]
    updated = store.update_status(int(task["id"]), status, message)
    if rename_window and tmux_window_exists(updated):
        tmux_rename_task_window(updated)
        if status == "WAIT" and move_wait_forward:
            tmux_move_wait_forward(updated)
    if notify_wait and previous_status == "RUNNING" and status == "WAIT":
        notify_user(updated, config or {})
    return updated


def tmux_select_or_attach(task: sqlite3.Row) -> None:
    target = task["window_id"] or f"{task['session']}:{shell_name(task['status'], task['title'])}"
    if os.environ.get("TMUX"):
        run_tmux(["select-window", "-t", target])
    else:
        os.execvp("tmux", ["tmux", "attach", "-t", target])


def tmux_activate_window(task: sqlite3.Row) -> None:
    if not task["window_id"]:
        return
    run_tmux(["select-window", "-t", task["window_id"]], check=False)


def tmux_send_to_task(task: sqlite3.Row, text: str) -> None:
    if not task["pane_id"]:
        raise TmuxError(f"Task pane is missing for #{task['id']}")
    buffer_name = f"aitask-{task['id']}-{int(time.time() * 1000)}"
    run_tmux(["set-buffer", "-b", buffer_name, text])
    try:
        run_tmux(["paste-buffer", "-b", buffer_name, "-t", task["pane_id"]])
        run_tmux(["send-keys", "-t", task["pane_id"], "C-m"])
    finally:
        run_tmux(["delete-buffer", "-b", buffer_name], check=False)


def tmux_press_enter(task: sqlite3.Row) -> None:
    if not task["pane_id"]:
        raise TmuxError(f"Task pane is missing for #{task['id']}")
    run_tmux(["send-keys", "-t", task["pane_id"], "C-m"])


def find_task_from_tmux_metadata(store: Store) -> sqlite3.Row | None:
    if not os.environ.get("TMUX"):
        return None
    pane = run_tmux(["display-message", "-p", "#{pane_id}"], check=False)
    if pane.returncode == 0 and pane.stdout.strip():
        task = store.find_task_by_pane(pane.stdout.strip())
        if task:
            return task
    task_id = run_tmux(["display-message", "-p", "#{@aitask_id}"], check=False)
    raw = task_id.stdout.strip() if task_id.returncode == 0 else ""
    if raw.isdigit():
        return store.get_task(int(raw))
    return None


def print_tasks(tasks: Iterable[sqlite3.Row]) -> None:
    rows = list(tasks)
    if not rows:
        print("No tasks.")
        return
    print("ID  STATUS   TARGET        UPDATED              TITLE")
    print("--  -------  ------------  -------------------  ----------------")
    for task in rows:
        target = f"{task['session']}:{task['window_id'] or '-'}"
        updated = format_local_time(task["updated_at"])
        print(f"{task['id']:<3} {task['status']:<7} {target:<12.12} {updated:<19} {task['title']}")


def format_task_detail(task: sqlite3.Row) -> str:
    target = f"{task['session']}:{task['window_id'] or '-'}"
    pane = task["pane_id"] or "-"
    updated = format_local_time(task["updated_at"])
    created = format_local_time(task["created_at"])
    attach_hint = f"tmux attach -t {shlex.quote(task['session'])}"
    return "\n".join(
        [
            f"#{task['id']} {task['status']} {task['title']}",
            f"target: {target}",
            f"pane: {pane}",
            f"cwd: {task['cwd']}",
            f"created: {created}",
            f"updated: {updated}",
            f"attach: {attach_hint}",
        ]
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="aitask", description="tmux-backed AI task manager")
    sub = parser.add_subparsers(dest="cmd")

    new = sub.add_parser("new", help="create a tmux-backed AI task")
    new.add_argument("title")
    new.add_argument("--session", "-s")
    new.add_argument("--cwd", "-C", default=os.getcwd())
    new.add_argument("--command", default="codex --dangerously-bypass-approvals-and-sandbox")
    new.add_argument("--status", choices=sorted(STATUSES), default="RUNNING")
    new.add_argument("--no-open", action="store_true", help="create the task without selecting the window")

    ls = sub.add_parser("list", help="list tasks")
    ls.add_argument("--status", choices=sorted(STATUSES))
    ls.add_argument("--all", action="store_true", help="include DONE tasks")

    open_cmd = sub.add_parser("open", help="open a task by ID")
    open_cmd.add_argument("--feishu", action="store_true", help="send captured main pane output to Feishu before opening")
    open_cmd.add_argument("--no-feishu", action="store_true", help="do not send captured output to Feishu")
    open_cmd.add_argument("--feishu-lines", type=int, default=120, help="number of pane lines to capture for Feishu")
    open_cmd.add_argument("id", type=int)

    activate = sub.add_parser("activate", help="select a task tmux window without attaching")
    activate.add_argument("id", type=int)

    show = sub.add_parser("show", help="show task metadata")
    show.add_argument("id", type=int)

    tail = sub.add_parser("tail", help="print recent main pane output")
    tail.add_argument("id", type=int)
    tail.add_argument("--lines", "-n", type=int, default=120)

    send = sub.add_parser("send", help="send text to the task main pane")
    send.add_argument("id", type=int)
    send.add_argument("text", nargs="+")

    for status in ["pending", "running", "wait", "done"]:
        p = sub.add_parser(status, help=f"mark task {status.upper()}")
        p.add_argument("id", type=int)
        p.add_argument("message", nargs="*")

    err = sub.add_parser("err", help="mark task ERR")
    err.add_argument("id", type=int)
    err.add_argument("message", nargs="*")

    sub.add_parser("sync", help="sync task records with tmux runtime")
    sub.add_parser("doctor", help="show paths and integration hints")
    sub.add_parser("notify-config", help="print Codex notify configuration snippet")
    focus = sub.add_parser("_tmux-focus", help=argparse.SUPPRESS)
    focus.add_argument("window_id", nargs="?")
    monitor = sub.add_parser("_tmux-pane-monitor", help=argparse.SUPPRESS)
    monitor.add_argument("id", type=int)
    monitor.add_argument("pane_id")
    return parser


def open_store() -> tuple[Paths, dict[str, Any], Store]:
    paths = resolve_paths()
    config = load_config(paths)
    return paths, config, Store(paths.db_path)


def cmd_new(args: argparse.Namespace, store: Store) -> int:
    cwd = str(Path(args.cwd).expanduser().resolve())
    session = args.session or default_session_name(Path(cwd))
    ensure_session(session, cwd)
    task = store.create_task(title=args.title, status=args.status, session=session, cwd=cwd, command=args.command)
    window_id, pane_id = tmux_new_window(task)
    store.update_runtime(task["id"], window_id=window_id, pane_id=pane_id)
    task = store.get_task(task["id"])
    assert task is not None
    tmux_set_task_options(task)
    tmux_enable_pane_monitor(task)
    print(f"Created task #{task['id']} {task['status']} {task['title']} -> {task['session']}:{task['window_id']}")
    if not args.no_open:
        tmux_select_or_attach(task)
    return 0


def require_task(store: Store, task_id: int) -> sqlite3.Row:
    task = store.get_task(task_id)
    if task is None:
        raise AitaskError(f"Task not found: {task_id}")
    return task


def cmd_open(args: argparse.Namespace, store: Store, config: dict[str, Any]) -> int:
    task = require_task(store, args.id)
    if not tmux_window_exists(task):
        store.update_status(task["id"], "DONE", "tmux window missing; hidden from default list")
        raise TmuxError(f"Task window is missing for #{task['id']}; hidden from default list")
    if args.feishu and not args.no_feishu:
        try:
            sent = push_task_result_to_feishu(task, config, lines=max(1, args.feishu_lines))
            if sent:
                print(f"sent task #{task['id']} result to Feishu", file=sys.stderr)
            else:
                print(
                    "aitask: Feishu push skipped; set AITASK_FEISHU_TARGET or AITASK_FEISHU_WEBHOOK",
                    file=sys.stderr,
                )
        except AitaskError as exc:
            print(f"aitask: Feishu push failed: {exc}", file=sys.stderr)
    tmux_select_or_attach(task)
    return 0


def cmd_activate(args: argparse.Namespace, store: Store) -> int:
    task = require_task(store, args.id)
    if not tmux_window_exists(task):
        store.update_status(task["id"], "DONE", "tmux window missing; hidden from default list")
        raise TmuxError(f"Task window is missing for #{task['id']}; hidden from default list")
    tmux_activate_window(task)
    print(f"activated #{task['id']} {task['title']} -> {task['session']}:{task['window_id']}")
    print(f"attach: tmux attach -t {shlex.quote(task['session'])}")
    return 0


def cmd_show(args: argparse.Namespace, store: Store) -> int:
    task = require_task(store, args.id)
    print(format_task_detail(task))
    return 0


def cmd_tail(args: argparse.Namespace, store: Store) -> int:
    task = require_task(store, args.id)
    print(format_task_result_for_feishu(task, lines=max(1, args.lines)))
    return 0


def cmd_send(args: argparse.Namespace, store: Store, config: dict[str, Any]) -> int:
    task = require_task(store, args.id)
    if not tmux_window_exists(task):
        store.update_status(task["id"], "DONE", "tmux window missing; hidden from default list")
        raise TmuxError(f"Task window is missing for #{task['id']}; hidden from default list")
    text = " ".join(args.text).strip()
    if not text:
        raise AitaskError("send text cannot be empty")
    accepted_trust = clear_codex_trust_prompt_if_present(task)
    tmux_send_to_task(task, text)
    started = wait_for_pane_condition(task, pane_output_indicates_running, timeout=4.0)
    next_status = "RUNNING" if started else "WAIT"
    message = "message sent to Codex" if started else "message sent, but Codex did not start working"
    task = apply_status_transition(store, task, next_status, message, config=config)
    suffix = " and accepted trust prompt" if accepted_trust else ""
    print(f"sent to #{task['id']} {task['title']}{suffix}; status={next_status}")
    return 0


def update_task_status(store: Store, task_id: int, status: str, message: str | None = None, config: dict[str, Any] | None = None) -> int:
    task = require_task(store, task_id)
    task = apply_status_transition(store, task, status, message, config=config)
    print(f"#{task['id']} -> {task['status']} {task['title']}")
    return 0


def cmd_tmux_focus(args: argparse.Namespace, store: Store) -> int:
    # Kept for backward compatibility with older tmux configs.
    # Viewing a task window is not the same as making the model run again.
    return 0


def strip_terminal_control(text: str) -> str:
    text = ANSI_RE.sub("", text)
    return "".join(ch for ch in text if ch == "\n" or ch == "\t" or ord(ch) >= 32)


def compact_terminal_text(text: str) -> str:
    cleaned = strip_terminal_control(text).replace("\r", "\n")
    lines: list[str] = []
    blank = 0
    for raw in cleaned.splitlines():
        line = raw.rstrip()
        if line:
            blank = 0
            lines.append(line)
            continue
        blank += 1
        if blank <= 1:
            lines.append("")
    return "\n".join(lines).strip()


def truncate_middle_head(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return f"... trimmed to last {limit} chars ...\n{text[-limit:]}"


def pane_output_indicates_running(text: str) -> bool:
    cleaned = strip_terminal_control(text)
    return any(marker in cleaned for marker in RUNNING_MARKERS)


def pane_output_indicates_idle_prompt(text: str) -> bool:
    cleaned = strip_terminal_control(text)
    return any(marker in cleaned for marker in IDLE_PROMPT_MARKERS)


def pane_output_indicates_trust_prompt(text: str) -> bool:
    cleaned = strip_terminal_control(text)
    return any(marker in cleaned for marker in TRUST_PROMPT_MARKERS)


def wait_for_pane_condition(task: sqlite3.Row, predicate: Any, *, timeout: float = 3.0, interval: float = 0.2) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate(tmux_capture_pane(task)):
            return True
        time.sleep(interval)
    return predicate(tmux_capture_pane(task))


def clear_codex_trust_prompt_if_present(task: sqlite3.Row) -> bool:
    if not pane_output_indicates_trust_prompt(tmux_capture_pane(task)):
        return False
    tmux_press_enter(task)
    wait_for_pane_condition(task, lambda text: not pane_output_indicates_trust_prompt(text), timeout=5.0)
    return True


def maybe_mark_running_from_pane(store: Store, task: sqlite3.Row) -> bool:
    if task["status"] not in {"WAIT", "PENDING"} or not task["pane_id"]:
        return False
    if not pane_output_indicates_running(tmux_capture_recent_pane(task)):
        return False
    updated = store.update_status(task["id"], "RUNNING", "Codex started working")
    if tmux_window_exists(updated):
        tmux_rename_task_window(updated)
    return True


def maybe_mark_wait_from_idle_pane(store: Store, task: sqlite3.Row, config: dict[str, Any] | None = None) -> bool:
    if task["status"] != "RUNNING" or not task["pane_id"] or not task["last_wait_at"]:
        return False
    recent = tmux_capture_recent_pane(task)
    if pane_output_indicates_running(recent) or not pane_output_indicates_idle_prompt(recent):
        return False
    apply_status_transition(store, task, "WAIT", "Codex is idle", config=config)
    return True


def sync_runtime_tasks(store: Store, config: dict[str, Any] | None = None, *, verbose: bool = False) -> int:
    changed = 0
    for task in store.list_tasks(include_done=False):
        if task["status"] in ACTIVE_STATUSES and task["window_id"] and not tmux_window_exists(task):
            apply_status_transition(
                store,
                task,
                "DONE",
                "tmux window missing; hidden from default list",
                config=config,
                rename_window=False,
            )
            if verbose:
                print(f"#{task['id']} marked DONE: tmux window missing")
            changed += 1
            continue
        if maybe_mark_running_from_pane(store, task):
            if verbose:
                print(f"#{task['id']} marked RUNNING: Codex is working")
            changed += 1
            continue
        if maybe_mark_wait_from_idle_pane(store, task, config=config):
            if verbose:
                print(f"#{task['id']} marked WAIT: Codex is idle")
            changed += 1
            continue
        if verbose and task["window_id"] and tmux_window_exists(task):
            tmux_set_task_options(task)
            tmux_rename_task_window(task)
            tmux_enable_pane_monitor(task, replace=True)
    return changed


def cmd_tmux_pane_monitor(args: argparse.Namespace, store: Store) -> int:
    rolling = ""
    while True:
        raw = os.read(sys.stdin.fileno(), 4096)
        if not raw:
            return 0
        text = raw.decode("utf-8", errors="ignore")
        rolling = (rolling + text)[-4096:]
        if not pane_output_indicates_running(rolling):
            continue
        task = store.get_task(args.id)
        if task is None:
            return 0
        if task["pane_id"] != args.pane_id:
            rolling = ""
            continue
        if task["status"] in {"WAIT", "PENDING"}:
            task = store.update_status(task["id"], "RUNNING", "Codex started working")
            if tmux_window_exists(task):
                tmux_rename_task_window(task)
        rolling = ""
    return 0


def cmd_sync(store: Store, config: dict[str, Any]) -> int:
    changed = sync_runtime_tasks(store, config, verbose=True)
    print(f"sync complete; changed={changed}")
    return 0


def cmd_doctor(paths: Paths, config: dict[str, Any]) -> int:
    notifications = config.get("notifications", {}) if isinstance(config.get("notifications"), dict) else {}
    print(f"db: {paths.db_path}")
    print(f"config: {paths.config_path}")
    print(f"feishu env: {paths.feishu_env_path}")
    print(f"desktop notify: {bool(notifications.get('desktop') or os.environ.get('AITASK_NOTIFY_DESKTOP'))}")
    print(f"feishu webhook: {bool(os.environ.get('FEISHU_WEBHOOK') or os.environ.get('AITASK_FEISHU_WEBHOOK') or notifications.get('feishu_webhook'))}")
    print(f"feishu target: {bool(os.environ.get('AITASK_FEISHU_TARGET') or notifications.get('feishu_target'))}")
    try:
        tmux = run_tmux(["-V"], check=False)
        print(f"tmux: {(tmux.stdout or tmux.stderr).strip() if tmux.returncode == 0 else 'not available'}")
    except TmuxError:
        print("tmux: not installed or not in PATH")
    return 0


def cmd_notify_config() -> int:
    print('notify = ["python3", "/Users/Shared/openclaw-share/repos/tmux_system/bin/codex-notify-dispatch"]')
    return 0


def cli_main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not args.cmd:
        args.cmd = "list"
        args.status = None
        args.all = False
    paths, config, store = open_store()
    try:
        if args.cmd == "new":
            return cmd_new(args, store)
        if args.cmd == "list":
            status = args.status.upper() if args.status else None
            sync_runtime_tasks(store, config)
            print_tasks(store.list_tasks(status=status, include_done=args.all))
            return 0
        if args.cmd == "open":
            return cmd_open(args, store, config)
        if args.cmd == "activate":
            return cmd_activate(args, store)
        if args.cmd == "show":
            return cmd_show(args, store)
        if args.cmd == "tail":
            return cmd_tail(args, store)
        if args.cmd == "send":
            return cmd_send(args, store, config)
        if args.cmd in {"pending", "running", "wait", "done", "err"}:
            message = " ".join(args.message).strip() or None
            return update_task_status(store, args.id, args.cmd.upper(), message, config=config)
        if args.cmd == "sync":
            return cmd_sync(store, config)
        if args.cmd == "doctor":
            return cmd_doctor(paths, config)
        if args.cmd == "notify-config":
            return cmd_notify_config()
        if args.cmd == "_tmux-focus":
            return cmd_tmux_focus(args, store)
        if args.cmd == "_tmux-pane-monitor":
            return cmd_tmux_pane_monitor(args, store)
        parser.error(f"unknown command {args.cmd}")
        return 2
    finally:
        store.close()


def read_notify_payload(argv: list[str]) -> dict[str, Any]:
    chunks: list[str] = []
    if not sys.stdin.isatty():
        ready, _, _ = select.select([sys.stdin], [], [], 0)
        if ready:
            chunks.append(sys.stdin.read())
    if not chunks and os.environ.get("AITASK_NOTIFY_PAYLOAD"):
        chunks.append(os.environ["AITASK_NOTIFY_PAYLOAD"])
    if not chunks and os.environ.get("CODEX_NOTIFY_PAYLOAD"):
        chunks.append(os.environ["CODEX_NOTIFY_PAYLOAD"])
    if not chunks and os.environ.get("CODEX_NOTIFICATION"):
        chunks.append(os.environ["CODEX_NOTIFICATION"])
    if argv:
        chunks.extend(argv)
    raw = "\n".join(part for part in chunks if part).strip()
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else {"value": parsed}
    except json.JSONDecodeError:
        return {"message": raw}


def event_type(payload: dict[str, Any]) -> str:
    for key in ("type", "event", "event_type", "eventType", "name"):
        value = payload.get(key)
        if isinstance(value, str) and value:
            return value
    return "agent-turn-complete"


def event_key(payload: dict[str, Any], task_id: int | None, typ: str) -> str:
    for key in ("id", "event_id", "eventId", "turn_id", "turnId"):
        value = payload.get(key)
        if value:
            return f"{typ}:{task_id}:{value}"
    encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    return f"{typ}:{task_id}:{hashlib.sha256(encoded.encode('utf-8')).hexdigest()}"


def resolve_task_for_notify(store: Store, payload: dict[str, Any]) -> sqlite3.Row | None:
    raw_id = os.environ.get("AITASK_ID") or payload.get("AITASK_ID") or payload.get("task_id") or payload.get("taskId")
    if raw_id is not None and str(raw_id).isdigit():
        task = store.get_task(int(raw_id))
        if task:
            return task
    return find_task_from_tmux_metadata(store)


def send_desktop_notification(title: str, body: str) -> None:
    if sys.platform != "darwin":
        return
    script = f'display notification {json.dumps(body)} with title {json.dumps(title)}'
    subprocess.run(["osascript", "-e", script], text=True, capture_output=True, check=False)


def feishu_sign(secret: str, timestamp: str) -> str:
    string_to_sign = f"{timestamp}\n{secret}".encode("utf-8")
    digest = hmac.new(string_to_sign, b"", hashlib.sha256).digest()
    return base64.b64encode(digest).decode("utf-8")


def send_feishu(webhook: str, secret: str | None, text: str) -> None:
    payload: dict[str, Any] = {"msg_type": "text", "content": {"text": text}}
    if secret:
        timestamp = str(int(time.time()))
        payload["timestamp"] = timestamp
        payload["sign"] = feishu_sign(secret, timestamp)
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(webhook, data=data, headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=10) as resp:
        resp.read()


def send_openclaw_feishu(target: str, text: str, *, account: str | None = None, channel: str = "feishu") -> None:
    cmd = ["openclaw", "message", "send", "--channel", channel, "--target", target, "--message", text]
    if account:
        cmd.extend(["--account", account])
    try:
        proc = subprocess.run(cmd, text=True, capture_output=True, check=False, timeout=20)
    except FileNotFoundError as exc:
        raise AitaskError("openclaw CLI is not installed or not in PATH") from exc
    except subprocess.TimeoutExpired as exc:
        raise AitaskError("openclaw message send timed out") from exc
    if proc.returncode != 0:
        stderr = proc.stderr.strip() or proc.stdout.strip()
        raise AitaskError(f"openclaw message send failed: {stderr}")


def send_feishu_text(text: str, config: dict[str, Any]) -> bool:
    notifications = config.get("notifications", {}) if isinstance(config.get("notifications"), dict) else {}
    target = os.environ.get("AITASK_FEISHU_TARGET") or notifications.get("feishu_target")
    if target:
        account = os.environ.get("AITASK_FEISHU_ACCOUNT") or notifications.get("feishu_account")
        channel = os.environ.get("AITASK_FEISHU_CHANNEL") or notifications.get("feishu_channel") or "feishu"
        send_openclaw_feishu(str(target), text, account=str(account) if account else None, channel=str(channel))
        return True
    webhook = os.environ.get("AITASK_FEISHU_WEBHOOK") or os.environ.get("FEISHU_WEBHOOK") or notifications.get("feishu_webhook")
    if webhook:
        secret = os.environ.get("AITASK_FEISHU_SECRET") or os.environ.get("FEISHU_SECRET") or notifications.get("feishu_secret")
        send_feishu(str(webhook), str(secret) if secret else None, text)
        return True
    return False


def push_task_result_to_feishu(task: sqlite3.Row, config: dict[str, Any], *, lines: int = 120) -> bool:
    return send_feishu_text(format_task_result_for_feishu(task, lines=lines), config)


def notify_user(task: sqlite3.Row, config: dict[str, Any]) -> None:
    text = f"AI task WAIT: #{task['id']} {task['title']}\nOpen: aitask open {task['id']}"
    notifications = config.get("notifications", {}) if isinstance(config.get("notifications"), dict) else {}
    if notifications.get("desktop") or os.environ.get("AITASK_NOTIFY_DESKTOP"):
        send_desktop_notification("AI task waiting", text)
    try:
        send_feishu_text(text, config)
    except AitaskError as exc:
        print(f"aitask: Feishu notify failed: {exc}", file=sys.stderr)


def notify_main(argv: list[str] | None = None) -> int:
    payload = read_notify_payload(argv or sys.argv[1:])
    paths, config, store = open_store()
    try:
        typ = event_type(payload)
        task = resolve_task_for_notify(store, payload)
        key = event_key(payload, int(task["id"]) if task else None, typ)
        if not store.insert_notification_event(key, int(task["id"]) if task else None, typ, payload):
            return 0
        if typ != "agent-turn-complete":
            store.append_event(int(task["id"]) if task else None, f"notify:{typ}", payload=payload)
            return 0
        if task is None:
            store.append_event(None, "notify:unmatched", "could not resolve task", payload)
            return 0
        message = payload.get("message") if isinstance(payload.get("message"), str) else "Codex turn complete"
        apply_status_transition(store, task, "WAIT", message, config=config)
        return 0
    finally:
        store.close()


if __name__ == "__main__":
    try:
        raise SystemExit(cli_main())
    except AitaskError as exc:
        print(f"aitask: {exc}", file=sys.stderr)
        raise SystemExit(1)
