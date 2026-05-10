# tmux_system

本仓库提供 `aitask`：一个基于 tmux 的本地 AI 任务管理器。它用 tmux 保存每个 Codex 交互现场，用 SQLite 保存任务列表和状态，适合本机 terminal，也适合手机 SSH 远程操作。

## 快速安装

复制仓库到新机器后执行：

```bash
scripts/install.sh
```

如果不需要飞书通知：

```bash
scripts/install.sh --no-feishu
```

如果要通过 OpenClaw 的 `aitask` 飞书机器人接收 `RUNNING -> WAIT` 通知：

```bash
scripts/install.sh --feishu-target user:ou_xxx
```

更多安装选项见 [docs/install.md](docs/install.md)。

## 常用命令

```bash
atn "任务标题"       # 创建任务
at                  # 查看任务列表
atwait              # 只看 WAIT 任务
ato <id>            # 推送最近输出到飞书并进入 tmux 任务
ats                 # 同步 tmux 和任务状态
td                  # detach tmux，任务继续运行
thelp               # 查看快捷键
```

详细使用见 [docs/aitask.md](docs/aitask.md)。
