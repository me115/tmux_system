# aitask 安装脚本

这个仓库复制到新机器后，在仓库根目录执行：

```bash
scripts/install.sh
```

脚本会安装：

- `aitask` / `aitask-codex-notify` / `codex-notify-dispatch` 到 `~/.openclaw/bin`
- `thelp` 帮助命令
- shell PATH 和快捷 alias
- `~/.tmux.conf` 里的 `Ctrl-a` 前缀、分屏和 pane 切换快捷键
- `~/.codex/config.toml` 的 Codex notify
- `~/.config/aitask/config.json`

脚本是幂等的，shell 和 tmux 配置使用 managed block，重复执行会替换旧 block，不会不断追加重复 alias。

## 常用安装

只安装本地 tmux/Codex 能力：

```bash
scripts/install.sh --no-feishu
```

启用 OpenClaw 飞书通知：

```bash
scripts/install.sh --feishu-target user:ou_xxx
```

发送到群：

```bash
scripts/install.sh --feishu-target chat:oc_xxx
```

如果 OpenClaw 里的账号不是默认 `aitask`：

```bash
scripts/install.sh --feishu-account aitask --feishu-target user:ou_xxx
```

安装到其他 PATH 目录：

```bash
scripts/install.sh --bin-dir ~/.local/bin --shell-rc ~/.zshrc
```

## 可跳过项

```bash
scripts/install.sh --skip-tmux
scripts/install.sh --skip-codex
scripts/install.sh --skip-shell
scripts/install.sh --skip-aitask-config
```

## 安装后检查

打开新 shell，或执行：

```bash
source ~/.zshrc
```

然后检查：

```bash
aitask doctor
at
thelp
```

Codex 任务默认用：

```bash
codex --dangerously-bypass-approvals-and-sandbox
```

当任务从 `RUNNING` 变为 `WAIT` 时，如果配置了飞书 target，会通过 OpenClaw 的 `feishu` / `aitask` account 发送通知。

## 注意

脚本会在修改 `~/.codex/config.toml` 和 `~/.config/aitask/config.json` 前创建带 `bak-aitask-时间戳` 的备份。

飞书 App ID / Secret、OpenClaw 机器人账号配置不写入这个仓库。新机器需要先把 OpenClaw 对应机器人配置好，再用 `--feishu-target` 配置 aitask 的通知目的地。
