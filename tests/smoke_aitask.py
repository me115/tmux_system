#!/usr/bin/env python3
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AITASK = [sys.executable, str(ROOT / "bin" / "aitask")]
NOTIFY = [sys.executable, str(ROOT / "bin" / "aitask-codex-notify")]


def run(cmd: list[str], env: dict[str, str], *, input_text: str | None = None, check: bool = True) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(cmd, text=True, input=input_text, capture_output=True, env=env, check=False)
    if check and proc.returncode != 0:
        raise AssertionError(f"command failed: {cmd}\nstdout={proc.stdout}\nstderr={proc.stderr}")
    return proc


def main() -> int:
    if shutil.which("tmux") is None:
        print("SKIP: tmux is not installed")
        return 0

    with tempfile.TemporaryDirectory(prefix="aitask-smoke-") as tmp:
        tmp_path = Path(tmp)
        env = os.environ.copy()
        env["AITASK_DATA_DIR"] = str(tmp_path / "data")
        env["AITASK_CONFIG_DIR"] = str(tmp_path / "config")
        session = f"aitask-smoke-{os.getpid()}"
        try:
            created = run(
                [
                    *AITASK,
                    "new",
                    "smoke task",
                    "--session",
                    session,
                    "--cwd",
                    str(tmp_path),
                    "--command",
                    "sleep 120",
                    "--no-open",
                ],
                env,
            )
            match = re.search(r"#(\d+)", created.stdout)
            assert match, created.stdout
            task_id = match.group(1)

            listed = run([*AITASK, "list"], env)
            assert "RUNNING" in listed.stdout and "smoke task" in listed.stdout, listed.stdout

            sent_file = tmp_path / "sent.txt"
            receiver = run(
                [
                    *AITASK,
                    "new",
                    "send receiver",
                    "--session",
                    session,
                    "--cwd",
                    str(tmp_path),
                    "--command",
                    "python3 -c \"from pathlib import Path; Path('sent.txt').write_text(input(), encoding='utf-8')\"",
                    "--no-open",
                ],
                env,
            )
            receiver_match = re.search(r"#(\d+)", receiver.stdout)
            assert receiver_match, receiver.stdout
            receiver_id = receiver_match.group(1)
            run([*AITASK, "send", receiver_id, "hello from aitask"], env)
            for _ in range(20):
                if sent_file.exists():
                    break
                time.sleep(0.1)
            assert sent_file.read_text(encoding="utf-8") == "hello from aitask", sent_file.read_text(encoding="utf-8")

            stale = run(
                [
                    *AITASK,
                    "new",
                    "stale task",
                    "--session",
                    session,
                    "--cwd",
                    str(tmp_path),
                    "--command",
                    "sleep 120",
                    "--no-open",
                ],
                env,
            )
            stale_id_match = re.search(r"#(\d+)", stale.stdout)
            stale_target_match = re.search(r"-> \S+:(@\d+)", stale.stdout)
            assert stale_id_match and stale_target_match, stale.stdout
            stale_id = stale_id_match.group(1)
            stale_window = stale_target_match.group(1)
            subprocess.run(["tmux", "kill-window", "-t", stale_window], text=True, capture_output=True, check=False)

            without_stale = run([*AITASK, "list"], env)
            assert "stale task" not in without_stale.stdout, without_stale.stdout
            stale_history = run([*AITASK, "list", "--status", "DONE", "--all"], env)
            assert stale_id in stale_history.stdout and "DONE" in stale_history.stdout and "stale task" in stale_history.stdout, stale_history.stdout

            payload = f'{{"type":"agent-turn-complete","task_id":{task_id},"id":"turn-1","message":"done"}}'
            run(NOTIFY, env, input_text=payload)
            waiting = run([*AITASK, "list", "--status", "WAIT"], env)
            assert "WAIT" in waiting.stdout and "smoke task" in waiting.stdout, waiting.stdout

            run([*AITASK, "running", task_id, "opened"], env)
            running = run([*AITASK, "list", "--status", "RUNNING"], env)
            assert "RUNNING" in running.stdout and "smoke task" in running.stdout, running.stdout

            run([*AITASK, "done", task_id], env)
            done = run([*AITASK, "list", "--status", "DONE", "--all"], env)
            assert "DONE" in done.stdout and "smoke task" in done.stdout, done.stdout

            run([*AITASK, "sync"], env)
            print("OK: aitask smoke test passed")
            return 0
        finally:
            subprocess.run(["tmux", "kill-session", "-t", session], text=True, capture_output=True, check=False)


if __name__ == "__main__":
    raise SystemExit(main())
