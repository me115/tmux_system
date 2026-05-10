#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'HELP'
Install aitask on this machine.

Usage:
  scripts/install.sh [options]

Options:
  --bin-dir PATH            Install command symlinks here. Default: ~/.openclaw/bin
  --shell-rc PATH           Shell rc file to update. Default: ~/.zshrc when it exists, else ~/.bashrc
  --skip-shell              Do not update shell PATH/aliases
  --skip-tmux               Do not update ~/.tmux.conf
  --skip-codex              Do not update ~/.codex/config.toml notify
  --skip-aitask-config      Do not create/update ~/.config/aitask/config.json
  --feishu-target TARGET    OpenClaw Feishu target, for example user:ou_xxx or chat:oc_xxx
  --feishu-account ID       OpenClaw Feishu account id. Default: aitask
  --feishu-channel NAME     OpenClaw channel. Default: feishu
  --desktop-notify          Enable macOS desktop notifications in aitask config
  --no-feishu               Remove Feishu target/account/channel from generated aitask config
  --help                    Show this help

Examples:
  scripts/install.sh
  scripts/install.sh --feishu-target user:ou_xxx
  scripts/install.sh --bin-dir ~/.local/bin --shell-rc ~/.zshrc
HELP
}

log() {
  printf '[aitask install] %s\n' "$*"
}

warn() {
  printf '[aitask install] WARN: %s\n' "$*" >&2
}

die() {
  printf '[aitask install] ERROR: %s\n' "$*" >&2
  exit 1
}

expand_path() {
  local value="$1"
  case "$value" in
    "~") printf '%s\n' "$HOME" ;;
    "~/"*) printf '%s/%s\n' "$HOME" "${value#~/}" ;;
    *) printf '%s\n' "$value" ;;
  esac
}

backup_file() {
  local path="$1"
  if [ -f "$path" ]; then
    cp "$path" "$path.bak-aitask-$(date +%Y%m%d%H%M%S)"
  fi
}

replace_managed_block() {
  local file="$1"
  local begin="$2"
  local end="$3"
  local block_file="$4"
  mkdir -p "$(dirname "$file")"
  touch "$file"
  python3 - "$file" "$begin" "$end" "$block_file" <<'PY'
import sys
from pathlib import Path

path = Path(sys.argv[1])
begin = sys.argv[2]
end = sys.argv[3]
block = Path(sys.argv[4]).read_text(encoding="utf-8").rstrip() + "\n"
text = path.read_text(encoding="utf-8") if path.exists() else ""
lines = text.splitlines()
out = []
inside = False
removed = False
for line in lines:
    if line.strip() == begin:
        inside = True
        removed = True
        continue
    if inside and line.strip() == end:
        inside = False
        continue
    if not inside:
        out.append(line)
if out and out[-1].strip():
    out.append("")
out.extend(block.splitlines())
path.write_text("\n".join(out).rstrip() + "\n", encoding="utf-8")
PY
}

require_command() {
  local name="$1"
  if ! command -v "$name" >/dev/null 2>&1; then
    die "$name is required but not found in PATH"
  fi
}

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BIN_DIR="$HOME/.openclaw/bin"
SHELL_RC=""
SKIP_SHELL=0
SKIP_TMUX=0
SKIP_CODEX=0
SKIP_AITASK_CONFIG=0
FEISHU_TARGET=""
FEISHU_ACCOUNT="aitask"
FEISHU_CHANNEL="feishu"
DESKTOP_NOTIFY=0
NO_FEISHU=0

if [ -f "$HOME/.zshrc" ]; then
  SHELL_RC="$HOME/.zshrc"
else
  SHELL_RC="$HOME/.bashrc"
fi

while [ "$#" -gt 0 ]; do
  case "$1" in
    --bin-dir)
      [ "$#" -ge 2 ] || die "--bin-dir requires a value"
      BIN_DIR="$(expand_path "$2")"
      shift 2
      ;;
    --shell-rc)
      [ "$#" -ge 2 ] || die "--shell-rc requires a value"
      SHELL_RC="$(expand_path "$2")"
      shift 2
      ;;
    --skip-shell)
      SKIP_SHELL=1
      shift
      ;;
    --skip-tmux)
      SKIP_TMUX=1
      shift
      ;;
    --skip-codex)
      SKIP_CODEX=1
      shift
      ;;
    --skip-aitask-config)
      SKIP_AITASK_CONFIG=1
      shift
      ;;
    --feishu-target)
      [ "$#" -ge 2 ] || die "--feishu-target requires a value"
      FEISHU_TARGET="$2"
      shift 2
      ;;
    --feishu-account)
      [ "$#" -ge 2 ] || die "--feishu-account requires a value"
      FEISHU_ACCOUNT="$2"
      shift 2
      ;;
    --feishu-channel)
      [ "$#" -ge 2 ] || die "--feishu-channel requires a value"
      FEISHU_CHANNEL="$2"
      shift 2
      ;;
    --desktop-notify)
      DESKTOP_NOTIFY=1
      shift
      ;;
    --no-feishu)
      NO_FEISHU=1
      shift
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      die "unknown option: $1"
      ;;
  esac
done

require_command python3
require_command tmux

for file in "$REPO_DIR/bin/aitask" "$REPO_DIR/bin/aitask-codex-notify" "$REPO_DIR/bin/codex-notify-dispatch"; do
  [ -f "$file" ] || die "missing required file: $file"
  chmod +x "$file"
done

mkdir -p "$BIN_DIR"
ln -sfn "$REPO_DIR/bin/aitask" "$BIN_DIR/aitask"
ln -sfn "$REPO_DIR/bin/aitask-codex-notify" "$BIN_DIR/aitask-codex-notify"
ln -sfn "$REPO_DIR/bin/codex-notify-dispatch" "$BIN_DIR/codex-notify-dispatch"

tmp_dir="$(mktemp -d)"
trap 'rm -rf "$tmp_dir"' EXIT

cat > "$BIN_DIR/thelp" <<'EOF'
#!/usr/bin/env bash
cat <<'HELP'
tmux / AI 任务快捷命令

Session:
  td                         退出当前 tmux，任务继续运行

Pane 分屏:
  Ctrl-a v                   新建左右分屏
  Ctrl-a s                   新建上下分屏
  Ctrl-a ;                   切到左侧 pane
  Ctrl-a '                   切到右侧 pane
  Ctrl-a [                   切到上方 pane
  Ctrl-a ]                   切到下方 pane
  Ctrl-a z                   当前 pane 放大/恢复
  Ctrl-d                     关闭当前 pane

AI Task:
  at                         aitask
  atn "任务标题"              创建 AI 任务
  atl                        查看任务列表
  atwait                     只看 WAIT 任务
  ato <id>                   推送主 pane 到飞书并进入任务
  atw <id>                   标记等待
  atr <id>                   标记运行中
  atd <id>                   标记完成
  ate <id> "原因"            标记错误
  ats                        修复 tmux/任务状态漂移
  atdoc                      检查 aitask 环境

Reload:
  Ctrl-a r                   重新加载 ~/.tmux.conf
HELP
EOF
chmod +x "$BIN_DIR/thelp"

if [ "$SKIP_SHELL" -eq 0 ]; then
  cat > "$tmp_dir/shell-block" <<EOF
# >>> aitask managed block >>>
export PATH="$BIN_DIR:\$PATH"

alias td='tmux detach'
alias at='aitask'
alias atn='aitask new'
alias atl='aitask list'
alias atw='aitask wait'
alias atr='aitask running'
alias ato='aitask open --feishu'
alias atd='aitask done'
alias ate='aitask err'
alias ats='aitask sync'
alias atdoc='aitask doctor'
alias atcfg='aitask notify-config'
alias atwait='aitask list --status WAIT'
# <<< aitask managed block <<<
EOF
  replace_managed_block "$SHELL_RC" "# >>> aitask managed block >>>" "# <<< aitask managed block <<<" "$tmp_dir/shell-block"
  log "updated shell rc: $SHELL_RC"
fi

if [ "$SKIP_TMUX" -eq 0 ]; then
  cat > "$tmp_dir/tmux-block" <<'EOF'
# >>> aitask managed block >>>
set -g mouse on
set -g history-limit 50000
set -g base-index 1
setw -g pane-base-index 1
set -g renumber-windows on
set -g status-interval 5
setw -g mode-keys vi
set -g allow-rename off
setw -g automatic-rename off

unbind C-b
set -g prefix C-a
bind C-a send-prefix

set -g status-left '[#S] '
set -g window-status-format ' #I:#W#F '
set -g window-status-current-format ' #[reverse]#I:#W#F#[default] '
set -g status-right '%Y-%m-%d %H:%M'

unbind-key \;
unbind-key "'"
bind-key \; select-pane -L
bind-key "'" select-pane -R
bind-key [ select-pane -U
bind-key ] select-pane -D
bind-key v split-window -h
bind-key s split-window -v
bind-key | split-window -h
bind-key - split-window -v
bind-key z resize-pane -Z
bind-key r source-file ~/.tmux.conf \; display-message "tmux config reloaded"

set-hook -gu after-select-window
set-hook -gu client-attached
# <<< aitask managed block <<<
EOF
  replace_managed_block "$HOME/.tmux.conf" "# >>> aitask managed block >>>" "# <<< aitask managed block <<<" "$tmp_dir/tmux-block"
  log "updated tmux config: $HOME/.tmux.conf"
fi

if [ "$SKIP_CODEX" -eq 0 ]; then
  mkdir -p "$HOME/.codex"
  CODEX_CONFIG="$HOME/.codex/config.toml"
  backup_file "$CODEX_CONFIG"
  python3 - "$CODEX_CONFIG" "$REPO_DIR/bin/codex-notify-dispatch" <<'PY'
import json
import re
import sys
from pathlib import Path

path = Path(sys.argv[1])
notify_script = sys.argv[2]
notify_line = "notify = " + json.dumps(["python3", notify_script], ensure_ascii=False)
text = path.read_text(encoding="utf-8") if path.exists() else ""
lines = text.splitlines()
out = []
replaced = False
for line in lines:
    if re.match(r"^\s*notify\s*=", line):
        if not replaced:
            out.append(notify_line)
            replaced = True
        continue
    out.append(line)
if not replaced:
    if out and out[-1].strip():
        out.append("")
    out.append(notify_line)
path.write_text("\n".join(out).rstrip() + "\n", encoding="utf-8")
PY
  log "updated Codex notify: $CODEX_CONFIG"
fi

if [ "$SKIP_AITASK_CONFIG" -eq 0 ]; then
  mkdir -p "$HOME/.config/aitask"
  AITASK_CONFIG="$HOME/.config/aitask/config.json"
  backup_file "$AITASK_CONFIG"
  python3 - "$AITASK_CONFIG" "$FEISHU_CHANNEL" "$FEISHU_ACCOUNT" "$FEISHU_TARGET" "$DESKTOP_NOTIFY" "$NO_FEISHU" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
channel, account, target = sys.argv[2], sys.argv[3], sys.argv[4]
desktop = sys.argv[5] == "1"
no_feishu = sys.argv[6] == "1"
config = {}
if path.exists():
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(loaded, dict):
            config = loaded
    except json.JSONDecodeError:
        config = {}
notifications = config.get("notifications")
if not isinstance(notifications, dict):
    notifications = {}
config["notifications"] = notifications
if desktop:
    notifications["desktop"] = True
if no_feishu:
    for key in ("feishu_channel", "feishu_account", "feishu_target"):
        notifications.pop(key, None)
elif target:
    notifications["feishu_channel"] = channel
    notifications["feishu_account"] = account
    notifications["feishu_target"] = target
path.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
PY
  log "updated aitask config: $AITASK_CONFIG"
fi

if command -v "$BIN_DIR/aitask" >/dev/null 2>&1; then
  "$BIN_DIR/aitask" doctor || true
else
  "$REPO_DIR/bin/aitask" doctor || true
fi

log "installation complete"
log "open a new shell or run: source \"$SHELL_RC\""
