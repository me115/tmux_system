#!/usr/bin/env python3
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from aitasklib import Store

AITASK = [sys.executable, str(ROOT / "bin" / "aitask")]
NOTIFY = [sys.executable, str(ROOT / "bin" / "aitask-codex-notify")]


def run(cmd: list[str], env: dict[str, str], *, input_text: str | None = None) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(cmd, text=True, input=input_text, capture_output=True, env=env, check=False)
    if proc.returncode != 0:
        raise AssertionError(f"command failed: {cmd}\nstdout={proc.stdout}\nstderr={proc.stderr}")
    return proc


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="aitask-store-") as tmp:
        tmp_path = Path(tmp)
        env = os.environ.copy()
        env["AITASK_DATA_DIR"] = str(tmp_path / "data")
        env["AITASK_CONFIG_DIR"] = str(tmp_path / "config")
        fake_bin = tmp_path / "bin"
        fake_bin.mkdir()
        send_log = tmp_path / "openclaw-send.log"
        fake_openclaw = fake_bin / "openclaw"
        fake_openclaw.write_text(
            "#!/bin/sh\n"
            "printf '%s\\n' \"$*\" >> \"$AITASK_TEST_OPENCLAW_LOG\"\n",
            encoding="utf-8",
        )
        fake_openclaw.chmod(0o755)
        env["PATH"] = f"{fake_bin}{os.pathsep}{env['PATH']}"
        env["AITASK_TEST_OPENCLAW_LOG"] = str(send_log)
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        (config_dir / "config.json").write_text(
            '{"notifications":{"feishu_channel":"feishu","feishu_account":"aitask","feishu_target":"user:ou_test"}}\n',
            encoding="utf-8",
        )
        db_path = tmp_path / "data" / "tasks.db"

        store = Store(db_path)
        try:
            task = store.create_task(
                title="storage task",
                status="RUNNING",
                session="store-test",
                cwd=str(tmp_path),
                command="codex",
            )
            task_id = int(task["id"])
            store.update_runtime(task_id, window_id=None, pane_id="pane-test")
        finally:
            store.close()

        listed = run([*AITASK, "list"], env)
        assert "RUNNING" in listed.stdout and "storage task" in listed.stdout, listed.stdout

        payload = f'{{"type":"agent-turn-complete","task_id":{task_id},"id":"store-turn-1","message":"done"}}'
        run(NOTIFY, env, input_text=payload)

        waiting = run([*AITASK, "list", "--status", "WAIT"], env)
        assert "WAIT" in waiting.stdout and "storage task" in waiting.stdout, waiting.stdout
        sends = send_log.read_text(encoding="utf-8")
        assert sends.count("message send ") == 1, sends
        assert "--account aitask" in sends and "--target user:ou_test" in sends, sends

        run([*AITASK, "_tmux-pane-monitor", str(task_id), "pane-test"], env, input_text="• Working (3s • esc to interrupt)\n")
        running = run([*AITASK, "list", "--status", "RUNNING"], env)
        assert "RUNNING" in running.stdout and "storage task" in running.stdout, running.stdout

        run(NOTIFY, env, input_text='{"type":"agent-turn-complete","task_id":%d,"id":"store-turn-2"}' % task_id)
        waiting_again = run([*AITASK, "list", "--status", "WAIT"], env)
        assert "WAIT" in waiting_again.stdout and "storage task" in waiting_again.stdout, waiting_again.stdout
        sends = send_log.read_text(encoding="utf-8")
        assert sends.count("message send ") == 2, sends

        # Duplicate event should be accepted but not create a second transition.
        run(NOTIFY, env, input_text=payload)
        sends = send_log.read_text(encoding="utf-8")
        assert sends.count("message send ") == 2, sends
        print("OK: storage/notify smoke test passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
