# aitask

`aitask` 是一个本地命令行任务管理器，用 tmux 保存交互现场，用 SQLite 保存任务索引。它适合本地 iTerm2，也适合手机 SSH。

## 安装入口

复制仓库到新机器后，在仓库根目录执行：

```bash
scripts/install.sh
```

如果不需要飞书通知：

```bash
scripts/install.sh --no-feishu
```

更多选项见 [install.md](install.md)。

当前 repo 提供三个命令入口：

```bash
/Users/Shared/openclaw-share/repos/tmux_system/bin/aitask
/Users/Shared/openclaw-share/repos/tmux_system/bin/aitask-codex-notify
/Users/Shared/openclaw-share/repos/tmux_system/bin/codex-notify-dispatch
```

安装脚本默认会把它们软链接到 PATH 内的：

```bash
/Users/openclaw/.openclaw/bin/aitask
/Users/openclaw/.openclaw/bin/aitask-codex-notify
/Users/openclaw/.openclaw/bin/codex-notify-dispatch
```

如果在其他机器或 shell 中不可见，可以加到 shell：

```bash
export PATH="/Users/Shared/openclaw-share/repos/tmux_system/bin:$PATH"
```

## 常用命令

```bash
aitask new "修复登录超时问题"
aitask new "设计飞书路由" --session openclaw --cwd ~/repos/openclaw
aitask list
aitask list --status WAIT
aitask open 12
aitask wait 12
aitask running 12
aitask done 12
aitask err 12 "tests failed"
aitask sync
aitask doctor
```

默认情况下，`aitask new` 会让 Codex 跳过审批和沙箱启动：

```bash
codex --dangerously-bypass-approvals-and-sandbox
```

如果某个任务要使用其他命令，可以显式传：

```bash
atn "只读调研" --command "codex --sandbox read-only"
```

任务列表里的 `UPDATED` 按本机时区显示；旧的 UTC 记录也会在展示时转换成本机时间。

## 快捷 alias

`~/.zshrc` 已加入：

```bash
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
```

示例：

```bash
atn "修复登录超时问题"
atl
atwait
ato 12
atd 12
```

注意：`at` 会在交互 shell 中覆盖系统的 `/usr/bin/at`。如果需要系统原命令，直接运行 `/usr/bin/at`。

退出当前 tmux 任务窗口但不停止任务：

```bash
td
```

默认数据位置：

```text
~/.local/share/aitask/tasks.db
~/.config/aitask/config.json
~/.config/aitask/feishu.env
```

可以用环境变量覆盖：

```bash
AITASK_DATA_DIR=/tmp/aitask-data
AITASK_CONFIG_DIR=/tmp/aitask-config
AITASK_DB=/tmp/aitask/tasks.db
```

## Codex notify

把下面配置加入 `~/.codex/config.toml`：

```toml
notify = ["python3", "/Users/Shared/openclaw-share/repos/tmux_system/bin/codex-notify-dispatch"]
```

也可以运行：

```bash
aitask notify-config
```

`aitask new` 启动 Codex 时会注入：

```bash
AITASK_ID=<id>
AITASK_TITLE=<title>
```

当 Codex 发出 `agent-turn-complete` 通知时，handler 会把任务改为 `WAIT`，重命名 tmux window，并尝试把 WAIT window 移到前面。

`ato <id>` 只负责进入 task window，不会自动把 `WAIT` 改成 `RUNNING`。查看任务、切 pane、执行日常命令都不代表模型正在运行。

`aitask` 会对 Codex 主 pane 启用 `tmux pipe-pane` 监听。当 Codex TUI 输出进入 `Working ... / esc to interrupt` 这类运行状态时，task 会自动从 `WAIT` 转为 `RUNNING`。因为 Codex 的状态行可能是原地刷新、不带换行，监听器按字节块读取；`aitask list` / `sync` 也会用当前 pane 屏幕内容兜底同步运行态。

如果监听没有捕获到，或者你不是在 Codex 主 pane 里继续任务，可以手动执行：

```bash
atr <id>
```

这样状态语义更明确：`WAIT` 表示等你交互，`RUNNING` 表示 Codex 已经开始处理。

## 通知配置

桌面通知：

```bash
export AITASK_NOTIFY_DESKTOP=1
```

飞书通知可放到 `~/.config/aitask/feishu.env`：

```bash
FEISHU_WEBHOOK='https://open.feishu.cn/open-apis/bot/v2/hook/...'
FEISHU_SECRET='...'
```

如果要复用 OpenClaw 已配置好的飞书发送通道，用目标会话代替 webhook：

```bash
AITASK_FEISHU_CHANNEL='feishu'
AITASK_FEISHU_ACCOUNT='aitask'
AITASK_FEISHU_TARGET='chat:oc_xxx 或 user:ou_xxx'
```

当任意任务从 `RUNNING` 变为 `WAIT` 时，`aitask` 会自动发送提醒。这个触发点不只来自 Codex `agent-turn-complete`，也包括 `aitask sync` 发现 Codex 已回到输入态、或手动执行 `atw <id>` 的状态流转；重复处理同一个完成事件不会重复提醒。

`ato <id>` 现在等价于：

```bash
aitask open --feishu <id>
```

它会先抓取该 task 的 Codex 主 pane 最近输出并发到飞书，然后再切入 tmux。需要只打开不转发时：

```bash
aitask open --no-feishu <id>
```

没有外部通知配置时，状态流转仍然会正常发生，只是不会向飞书发送消息。

## 飞书 Bot 交互

OpenClaw 的 live `openclaw-lark` handler 已接入 `aitask` 短命令。你可以在已配置的飞书机器人对话里发送：

```text
at
at wait
at running
at all
at new 修复登录超时问题
at new /Users/Shared/openclaw-share/repos/clipcap-next | 修复登录超时问题
at show 6
at tail 6
at open 6
at send 6 继续按刚才的方案执行
at 6 继续按刚才的方案执行
```

语义：

- `at` / `at wait`：查看任务列表和等待交互的任务。
- `at new`：创建新的 tmux/Codex task；不 attach，适合机器人调用。
- `at open`：激活本机 tmux window，并把该任务主 pane 最近输出回到飞书。
- `at send` / `at <id> <内容>`：把内容输入到 task 的 Codex 主 pane。若 Codex 首屏卡在 trust prompt，会先确认；只有检测到 Codex 进入 `Working` 才把状态置为 `RUNNING`，否则保持 `WAIT`。
- `aitask sync` / `at` 会避免用历史 scrollback 里的旧 `Working` 误判状态；如果 Codex 已回到输入提示符，会把 stale `RUNNING` 修正为 `WAIT`。

## 恢复和排错

如果 tmux 和数据库状态不一致：

```bash
aitask sync
```

如果任务窗口已经被清理或丢失，`aitask list` / `sync` 会把 active task 标记为 `DONE`，默认列表不再展示；需要追溯时用 `aitask list --all`。

检查环境：

```bash
aitask doctor
```

如果 Codex 完成后没有变成 `WAIT`：

1. 确认 `~/.codex/config.toml` 有 `notify` 配置。
2. 确认任务是通过 `aitask new` 启动的，这样 Codex 进程才有 `AITASK_ID`。
3. 手动运行 `aitask-codex-notify` 测试 payload：

```bash
echo '{"type":"agent-turn-complete","task_id":1,"id":"manual-test"}' | aitask-codex-notify
```
