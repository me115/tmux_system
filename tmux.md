# 我就是 飞书 + tmux +codex 工作的配置。给我详细的配置方案（我还不会使用 tmux）
可以。下面这套我建议你按 **三层** 来配：

```text
第 1 层：SSH 安全远程进入 Mac mini
第 2 层：tmux 固化工作现场
第 3 层：飞书做入口 + 通知 + 状态提醒
```

其中真正交互式 coding 仍然走 `SSH → tmux → codex`，飞书不要直接承载终端。飞书自定义机器人更适合通过 webhook 向群里推送消息；如果要在飞书里接收命令，需要做企业自建应用/事件回调，复杂度会明显上升。飞书官方文档也把自定义机器人定位为“当前群聊内使用、通过 webhook 完成消息推送”。([open.larksuite.com][1])

---

# 一、最终推荐架构

```text
手机 / iPad / 外部电脑
        |
        | SSH
        v
Mac mini / 开发机
        |
        v
tmux session: codex
        |
        ├── window 1: Codex CLI
        ├── window 2: shell
        ├── window 3: server
        ├── window 4: logs
        └── window 5: git/test

飞书
  ├── 收到 Codex / 脚本推送的状态通知
  ├── 保存远程连接命令
  └── 作为“远程工作入口面板”
```

OpenAI 官方对 Codex CLI 的定位是：在本地终端运行的 coding agent，可以读取、修改并运行你当前目录下的代码；所以它非常适合放在 tmux 里长期运行。([OpenAI 开发者][2])

---

# 二、Mac mini 上启用 SSH

## 1. 开启远程登录

Mac 上：

```text
系统设置 → 通用 → 共享 → 远程登录
```

打开后，macOS 会显示类似：

```bash
ssh colin@192.168.x.x
```

Apple 官方说明里也是通过“系统设置 → 通用 → 共享 → 远程登录”开启 SSH/SFTP 远程访问。([苹果支持][3])

---

## 2. 强烈建议用 Tailscale，不要直接暴露公网 SSH

推荐：

```text
外部设备 → Tailscale 私有网络 → Mac mini SSH
```

不要把家里路由器的 `22` 端口直接映射到公网。Tailscale 官方 macOS 文档说明可以在 macOS 上安装客户端；Tailscale SSH 还可以让 Tailscale 接管来自 Tailscale 网络的 22 端口 SSH 连接，并通过 WireGuard 和节点密钥进行认证加密。([Tailscale][4])

你可以先这样：

```bash
# Mac mini 上安装 Tailscale
brew install --cask tailscale
```

然后登录 Tailscale。

在手机/iPad/另一台电脑也安装 Tailscale，登录同一个账号。之后你可以用 Mac mini 的 Tailscale IP 连接：

```bash
ssh colin@100.x.y.z
```

---

# 三、安装 tmux 和 Codex CLI

在 Mac mini 上：

```bash
brew install tmux
```

安装 Codex CLI：

```bash
# 方式一：Homebrew
brew install --cask codex

# 或方式二：npm
npm i -g @openai/codex
```

OpenAI 官方 Codex CLI 页面列出了 npm 和 Homebrew 安装方式；Codex CLI 的参数和配置也可以通过 `~/.codex/config.toml` 管理。([OpenAI 开发者][2])

验证：

```bash
tmux -V
codex --version
```

---

# 四、tmux 入门：你只需要先掌握 10 个命令

tmux 的核心概念：

| 概念      | 类比           | 用途                          |
| ------- | ------------ | --------------------------- |
| session | 一个工作区        | 一个项目一个 session              |
| window  | terminal tab | codex / server / logs / git |
| pane    | 分屏           | 同屏看多个命令                     |

tmux 官方文档也强调它可以管理 sessions、windows、panes，并支持选择、切换和关闭这些对象。([GitHub][5])

---

## 1. 新建 session

```bash
tmux new -s codex
```

这里 `codex` 是 session 名字。

---

## 2. 退出但不中断任务

在 tmux 里按：

```text
Ctrl-b 然后按 d
```

这叫 detach。

你的 Codex、server、logs 都不会停。tmux 的经典用法就是 detach 之后，长任务仍然在后台继续运行。([红帽][6])

---

## 3. 重新进入

```bash
tmux attach -t codex
```

如果你忘了名字：

```bash
tmux ls
```

---

## 4. 创建新窗口

在 tmux 里按：

```text
Ctrl-b 然后按 c
```

---

## 5. 切换窗口

```text
Ctrl-b 然后按 n    # 下一个 window
Ctrl-b 然后按 p    # 上一个 window
Ctrl-b 然后按 0-9  # 切到指定编号
```

---

## 6. 当前窗口改名

```text
Ctrl-b 然后按 ,
```

比如改成：

```text
codex
server
logs
git
```

---

## 7. 左右分屏

```text
Ctrl-b 然后按 %
```

---

## 8. 上下分屏

```text
Ctrl-b 然后按 "
```

---

## 9. pane 之间移动

```text
Ctrl-b 然后按方向键
```

---

## 10. 关闭当前 pane

```bash
exit
```

或者：

```text
Ctrl-d
```

---

# 五、推荐你的 tmux 配置

先创建配置文件：

```bash
vim ~/.tmux.conf
```

写入：

```tmux
# 鼠标支持：可以点 pane、滚动历史
set -g mouse on

# 历史滚动行数
set -g history-limit 50000

# window 从 1 开始编号，更符合直觉
set -g base-index 1
setw -g pane-base-index 1

# 关闭 window 后自动重新编号
set -g renumber-windows on

# 状态栏刷新频率
set -g status-interval 5

# 更容易看懂的状态栏
set -g status-left '[#S] '
set -g status-right '%Y-%m-%d %H:%M'

# vi 风格复制模式
setw -g mode-keys vi

# 使用 Ctrl-a 作为 tmux 前缀键
unbind C-b
set -g prefix C-a
bind C-a send-prefix

# Ctrl-a ; / Ctrl-a ' 左右切换 pane
unbind-key \;
unbind-key "'"
bind-key \; select-pane -L
bind-key "'" select-pane -R

# Ctrl-a [ / Ctrl-a ] 上下切换 pane
bind-key [ select-pane -U
bind-key ] select-pane -D

# Ctrl-a v 新建左右分屏；Ctrl-a s 新建上下分屏
bind-key v split-window -h
bind-key s split-window -v

# 保留旧的自定义分屏键
bind-key | split-window -h
bind-key - split-window -v

# 重新加载配置
bind-key r source-file ~/.tmux.conf \; display-message "tmux config reloaded"
```

生效：

```bash
tmux source-file ~/.tmux.conf
```

之后你在 tmux 里可以按：

```text
Ctrl-a 然后按 r
```

重新加载配置。

---

# 六、为 Codex 创建固定工作区

假设你的项目在：

```bash
~/repos/clipcap-next
```

你可以手动这样用：

```bash
cd ~/repos/clipcap-next
tmux new -s clipcap
codex
```

但我建议你写一个启动脚本。

---

## 1. 创建脚本目录

```bash
mkdir -p ~/bin
```

如果 `~/bin` 还不在 PATH 里，把这行加入 `~/.zshrc`：

```bash
export PATH="$HOME/bin:$PATH"
```

生效：

```bash
source ~/.zshrc
```

---

## 2. 创建 `codex-tmux`

```bash
cat > ~/bin/codex-tmux <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

SESSION="${1:-codex}"
REPO="${2:-$PWD}"

REPO="$(cd "$REPO" && pwd)"
QUOTED_REPO="$(printf "%q" "$REPO")"

if tmux has-session -t "$SESSION" 2>/dev/null; then
  tmux attach -t "$SESSION"
  exit 0
fi

tmux new-session -d -s "$SESSION" -n codex -c "$REPO"
tmux send-keys -t "$SESSION":codex "cd $QUOTED_REPO && codex" C-m

tmux new-window -t "$SESSION" -n shell -c "$REPO"
tmux new-window -t "$SESSION" -n server -c "$REPO"
tmux new-window -t "$SESSION" -n logs -c "$REPO"
tmux new-window -t "$SESSION" -n git -c "$REPO"

tmux select-window -t "$SESSION":codex
tmux attach -t "$SESSION"
EOF

chmod +x ~/bin/codex-tmux
```

---

## 3. 使用方式

```bash
codex-tmux clipcap ~/repos/clipcap-next
```

它会自动创建：

```text
session: clipcap

window 1: codex
window 2: shell
window 3: server
window 4: logs
window 5: git
```

下次远程回来：

```bash
ssh colin@你的机器
codex-tmux clipcap ~/repos/clipcap-next
```

如果 session 已经存在，它会直接 attach，不会重复创建。

---

# 七、推荐的日常工作流

## 本地开始工作

```bash
codex-tmux clipcap ~/repos/clipcap-next
```

在 tmux 里：

```text
window 1: codex
window 2: shell
window 3: pnpm dev / go run / make dev
window 4: tail logs
window 5: git diff / tests
```

---

## 出门前

按：

```text
Ctrl-b d
```

不要关 terminal。

---

## 远程继续

手机/iPad/另一台电脑：

```bash
ssh colin@100.x.y.z
tmux attach -t clipcap
```

你会看到之前的 Codex 会话、日志、server 都还在。

---

# 八、飞书做“入口”和“通知”

这里我建议先做 **轻量版**：

```text
飞书群：AI 工作站
  ├── 固定置顶 SSH 命令
  ├── 接收 Mac mini 状态通知
  ├── 接收任务完成提醒
  └── 接收 tmux session 状态
```

不要一上来就做“飞书里输入命令，然后自动操作 shell”。那个权限风险高，而且交互体验不如直接 SSH。

---

## 1. 创建飞书群机器人

在飞书里：

```text
创建一个群：AI 工作站
群设置 → 群机器人 → 添加机器人 → 自定义机器人
```

复制 webhook。

建议开启：

```text
签名校验
```

飞书自定义机器人文档说明可以在安全设置里开启签名校验，并由系统提供 secret。([飞书开放平台][7])

---

## 2. 在 Mac mini 保存 webhook

```bash
mkdir -p ~/.config/codex-workstation
chmod 700 ~/.config/codex-workstation

cat > ~/.config/codex-workstation/feishu.env <<'EOF'
FEISHU_WEBHOOK='你的飞书 webhook'
FEISHU_SECRET='你的飞书签名 secret，如果没开签名就留空'
EOF

chmod 600 ~/.config/codex-workstation/feishu.env
```

---

## 3. 创建飞书推送脚本 `fsay`

```bash
cat > ~/bin/fsay <<'PY'
#!/usr/bin/env python3
import base64
import hashlib
import hmac
import json
import os
import sys
import time
import urllib.request
from pathlib import Path

env_path = Path.home() / ".config/codex-workstation/feishu.env"

if env_path.exists():
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("'\""))

webhook = os.getenv("FEISHU_WEBHOOK", "")
secret = os.getenv("FEISHU_SECRET", "")

if not webhook:
    print("FEISHU_WEBHOOK is not set", file=sys.stderr)
    sys.exit(1)

text = " ".join(sys.argv[1:]).strip() or "ping from Mac mini"

payload = {
    "msg_type": "text",
    "content": {
        "text": text
    }
}

if secret:
    timestamp = str(int(time.time()))
    string_to_sign = f"{timestamp}\n{secret}".encode("utf-8")
    sign = base64.b64encode(
        hmac.new(string_to_sign, b"", digestmod=hashlib.sha256).digest()
    ).decode("utf-8")

    payload["timestamp"] = timestamp
    payload["sign"] = sign

data = json.dumps(payload, ensure_ascii=False).encode("utf-8")

req = urllib.request.Request(
    webhook,
    data=data,
    headers={"Content-Type": "application/json"},
    method="POST",
)

with urllib.request.urlopen(req, timeout=10) as resp:
    print(resp.read().decode("utf-8"))
PY

chmod +x ~/bin/fsay
```

测试：

```bash
fsay "Mac mini 已上线，可以 SSH 进入 tmux 工作区"
```

---

## 4. 创建 tmux 状态推送脚本

```bash
cat > ~/bin/tmux-report <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

HOST="$(hostname)"
NOW="$(date '+%Y-%m-%d %H:%M:%S')"

if tmux ls >/tmp/tmux-sessions.txt 2>&1; then
  MSG="[$HOST] tmux 状态 - $NOW

$(cat /tmp/tmux-sessions.txt)

远程进入：
ssh colin@你的Tailscale-IP
tmux attach -t clipcap"
else
  MSG="[$HOST] 当前没有 tmux session - $NOW"
fi

fsay "$MSG"
EOF

chmod +x ~/bin/tmux-report
```

运行：

```bash
tmux-report
```

飞书群里会收到当前 tmux session 列表。

---

# 九、让飞书每天提醒你的工作入口

你可以加一个 crontab：

```bash
crontab -e
```

加入：

```cron
0 9 * * * /Users/colin/bin/tmux-report >/tmp/tmux-report.log 2>&1
```

每天早上 9 点推送一次：

```text
Mac mini 当前 tmux session
SSH 命令
attach 命令
```

这就像一个“飞书工作站入口”。

---

# 十、可选：Codex 任务完成后自动通知飞书

比如你在 tmux 的 shell 里跑测试：

```bash
pnpm test; fsay "clipcap: pnpm test 执行完成，退出码=$?"
```

或者：

```bash
go test ./...; fsay "merchant assistant: go test ./... 已完成，退出码=$?"
```

如果是长任务：

```bash
pnpm build && fsay "build 成功" || fsay "build 失败"
```

这个会非常实用。

---

# 十一、建议你固定 3 个 tmux session

结合你的工作习惯，我建议：

```bash
codex-tmux clipcap ~/repos/clipcap-next
codex-tmux openclaw ~/repos/openclaw
codex-tmux work ~/repos/你的公司项目
```

查看：

```bash
tmux ls
```

进入：

```bash
tmux attach -t clipcap
tmux attach -t openclaw
tmux attach -t work
```

---

# 十二、手机/平板上的真实操作方式

你的远程体验应该是：

```text
飞书看到提醒
  ↓
复制 SSH 命令
  ↓
打开 SSH 客户端
  ↓
ssh colin@100.x.y.z
  ↓
tmux attach -t clipcap
  ↓
继续和 Codex 交互
```

飞书负责“入口感”和“提醒感”，tmux 负责“工作现场”。

这比“飞书直接控制 Codex”流畅很多，因为 tmux 保留的是完整终端状态，而不是把终端抽象成一轮轮聊天消息。

---

# 十三、不要一开始就做的事

我不建议你初期做这些：

```text
飞书里输入 /run rm -rf ...
飞书直接执行任意 shell
飞书直接 tmux send-keys 到 Codex
飞书 bot 自动改代码
```

如果后面你确实要做，也应该只开放白名单命令：

```text
/status
/sessions
/notify
/tail clipcap
/restart-dev
```

不要开放：

```text
任意 shell command
任意 codex prompt
任意 repo write
```

---

# 十四、你现在最小可用版本

只做这 5 步就可以开始用了：

```bash
# 1. Mac 开启远程登录
# 系统设置 → 通用 → 共享 → 远程登录

# 2. 安装
brew install tmux
brew install --cask codex

# 3. 创建工作区
cd ~/repos/clipcap-next
tmux new -s clipcap

# 4. 在 tmux 里启动 Codex
codex

# 5. 出门前 detach
# Ctrl-b d
```

远程回来：

```bash
ssh colin@你的机器
tmux attach -t clipcap
```

这就是最核心的闭环。

---

# 我的建议优先级

你按这个顺序推进：

```text
P0：SSH + Tailscale 打通
P1：tmux 基础用熟
P2：codex-tmux 脚本固定工作区
P3：飞书自定义机器人推送状态
P4：长任务完成后 fsay 通知
P5：再考虑飞书交互式命令网关
```

对你来说，真正提升最大的不是飞书 bot，而是：

```text
tmux session 永不丢
Codex 上下文永不丢
server/logs/git/test 永远在原地
```

这套先跑顺，你的 Mac mini 就基本变成一个“个人 AI 开发工作站”了。

[1]: https://open.larksuite.com/document/client-docs/bot-v3/add-custom-bot?utm_source=chatgpt.com "Custom bot usage guide - Documentation"
[2]: https://developers.openai.com/codex/cli?utm_source=chatgpt.com "Codex CLI"
[3]: https://support.apple.com/guide/mac-help/allow-a-remote-computer-to-access-your-mac-mchlp1066/mac?utm_source=chatgpt.com "Allow a remote computer to access your Mac"
[4]: https://tailscale.com/docs/install/mac?utm_source=chatgpt.com "Install Tailscale on macOS"
[5]: https://github.com/tmux/tmux/wiki/Getting-Started?utm_source=chatgpt.com "Getting Started · tmux/tmux Wiki"
[6]: https://www.redhat.com/en/blog/introduction-tmux-linux?utm_source=chatgpt.com "A beginner's guide to tmux"
[7]: https://open.feishu.cn/document/client-docs/bot-v3/add-custom-bot?lang=zh-CN&ref=fenx.work&utm_source=chatgpt.com "Custom bot usage guide - 开发文档 - 飞书开放平台"


# 我现在使用大模型交互很多； 我托管给模型一个任务，大概要20分钟后返回，我需要有很多个这个交互终端；我希望每个交互终端和一个任务标题关联起来；这样我知道我的任务的处理进展，交互完成后也能很好的认识到解决了哪个问题；tmux能完成这个么？或者当前有没有什么好的插件能安装来实现（我当前的主力还是 iterm2）
能完成，而且你的场景非常适合用 **tmux 做“任务看板 + 持久化终端”**。

我建议你不要把它理解成“多个终端”，而是理解成：

```text
一个项目 = 一个 tmux session
一个大模型任务 = 一个 tmux window
一个任务里的不同视角 = 多个 pane
```

例如：

```text
session: clipcap

window 1: [视频工作流 DB schema 重构]
window 2: [Remotion 渲染失败排查]
window 3: [Supabase RLS 策略 Review]
window 4: [Landing page UI 优化]
window 5: [Trigger.dev preview 部署修复]
```

tmux 本身就支持 session、window、pane，并且 window 可以自定义名字；官方文档也说明每个 tmux window 都有名字，可以由用户修改。([GitHub][1])

---

# 结论先说

你这个需求我建议用：

```text
tmux 原生能力
  +
自定义启动脚本
  +
Codex notify hook
  +
iTerm2 通知 / Badge
```

插件不是核心，核心是把 **“任务标题”变成 tmux window 名字**。

---

# 推荐结构

## 1. 一个项目一个 session

比如：

```bash
tmux new -s clipcap
```

或者：

```bash
tmux new -s work
tmux new -s openclaw
tmux new -s merchant-assistant
```

---

## 2. 一个任务一个 window

每次给 Codex 一个 20 分钟任务，就新建一个 window：

```bash
tmux new-window -n "修复 Supabase RLS 策略"
```

然后在这个 window 里启动 Codex：

```bash
codex
```

这样你的任务列表就是：

```bash
tmux list-windows
```

或者在 tmux 里按：

```text
Ctrl-b w
```

你会看到所有任务标题。

---

## 3. 一个任务内部可以分 pane

比如一个任务 window 里：

```text
左边：Codex
右上：git diff
右下：pnpm test / logs
```

这样每个任务都是一个小工作台。

---

# tmux 可以很好解决的点

| 诉求                  | tmux 能否解决 | 方式                                |
| ------------------- | --------: | --------------------------------- |
| 多个大模型交互终端           |        可以 | 一个任务一个 window                     |
| 每个终端绑定任务标题          |        可以 | window name                       |
| 任务跑 20 分钟不中断        |        可以 | detach 后后台继续跑                     |
| 远程回来继续看             |        可以 | attach 回 session                  |
| 知道哪个任务有新输出          |        可以 | activity flag / bell / status bar |
| 任务完成通知              |      部分可以 | Codex notify hook + iTerm2/飞书     |
| Mac 重启后恢复           |        可以 | tmux-resurrect / continuum        |
| iTerm2 里保留原生 tab 体验 |        可以 | iTerm2 tmux integration           |

---

# 我建议你的实际方案

## Session 层级

```text
clipcap
openclaw
company-work
trend-analysis
```

## Window 命名规范

建议用这种格式：

```text
[状态] 任务标题
```

例如：

```text
⏳ Clipcap: 修复 RLS migration
⏳ OpenClaw: 飞书入口安全方案
✅ Codex: 总结 diff 并生成 PR 描述
⚠️ Trigger: preview branch deploy 报错
```

但 tmux window name 里 emoji 有时在不同终端宽度下显示不稳定，所以更稳的是：

```text
RUN clipcap-rls
WAIT trigger-preview
DONE pr-description
ERR supabase-migration
```

我建议你用：

```text
RUN-视频工作流DB重构
WAIT-Trigger预览部署
DONE-OpenClaw安全方案
ERR-Supabase连接问题
```

---

# tmux 基础配置

编辑：

```bash
vim ~/.tmux.conf
```

加入：

```tmux
# 鼠标支持
set -g mouse on

# 保留较长滚动历史
set -g history-limit 50000

# window 从 1 开始
set -g base-index 1
setw -g pane-base-index 1

# 关闭自动改名，避免你设置的任务标题被 shell/codex 覆盖
set -g allow-rename off
setw -g automatic-rename off

# 关闭窗口后自动重新编号
set -g renumber-windows on

# 监控非当前窗口的新输出
setw -g monitor-activity on
set -g visual-activity on

# 状态栏显示 session + window 列表
set -g status-left '[#S] '
set -g window-status-format ' #I:#W#F '
set -g window-status-current-format ' #[reverse]#I:#W#F#[default] '

# 状态栏右侧显示时间
set -g status-right '%Y-%m-%d %H:%M'

# 使用 Ctrl-a 作为 tmux 前缀键
unbind C-b
set -g prefix C-a
bind C-a send-prefix

# Ctrl-a ; / Ctrl-a ' 左右切换 pane
unbind-key \;
unbind-key "'"
bind-key \; select-pane -L
bind-key "'" select-pane -R

# Ctrl-a [ / Ctrl-a ] 上下切换 pane
bind-key [ select-pane -U
bind-key ] select-pane -D

# Ctrl-a v 新建左右分屏；Ctrl-a s 新建上下分屏
bind-key v split-window -h
bind-key s split-window -v

# 保留旧的自定义分屏键
bind-key | split-window -h
bind-key - split-window -v

# 快捷键：重新加载配置
bind-key r source-file ~/.tmux.conf \; display-message "tmux config reloaded"
```

生效：

```bash
tmux source-file ~/.tmux.conf
```

关键是这两行：

```tmux
set -g allow-rename off
setw -g automatic-rename off
```

否则你辛苦设置的任务标题，可能会被 shell 当前命令自动覆盖掉。

---

# 最小手动工作流

进入项目：

```bash
cd ~/repos/clipcap-next
tmux new -s clipcap
```

新建一个任务：

```text
Ctrl-b c
```

重命名当前 window：

```text
Ctrl-b ,
```

输入：

```text
RUN-修复视频生成工作流
```

启动 Codex：

```bash
codex
```

让它跑 20 分钟后，你切到别的 window：

```text
Ctrl-b n
```

查看所有任务：

```text
Ctrl-b w
```

detach：

```text
Ctrl-b d
```

回来：

```bash
tmux attach -t clipcap
```

---

# 更适合你的脚本化方案

你可以写一个 `aitask` 命令，以后每次这样创建任务：

```bash
aitask clipcap "修复 Supabase RLS 策略" ~/repos/clipcap-next
```

它自动创建 tmux window，并用任务标题命名。

---

## 创建脚本

```bash
mkdir -p ~/bin
vim ~/bin/aitask
```

写入：

```bash
#!/usr/bin/env bash
set -euo pipefail

SESSION="${1:?usage: aitask <session> <task-title> [repo-dir]}"
TITLE="${2:?usage: aitask <session> <task-title> [repo-dir]}"
REPO="${3:-$PWD}"

REPO="$(cd "$REPO" && pwd)"

WINDOW_NAME="RUN-${TITLE}"

if ! tmux has-session -t "$SESSION" 2>/dev/null; then
  tmux new-session -d -s "$SESSION" -n dashboard -c "$REPO"
fi

tmux new-window -t "$SESSION" -n "$WINDOW_NAME" -c "$REPO"

# 左侧启动 Codex，右侧留给命令/测试/日志
tmux send-keys -t "$SESSION:$WINDOW_NAME" "cd '$REPO' && codex" C-m
tmux split-window -h -t "$SESSION:$WINDOW_NAME" -c "$REPO"
tmux send-keys -t "$SESSION:$WINDOW_NAME".2 "cd '$REPO' && git status" C-m

tmux select-pane -t "$SESSION:$WINDOW_NAME".1
tmux select-window -t "$SESSION:$WINDOW_NAME"
tmux attach -t "$SESSION"
```

授权：

```bash
chmod +x ~/bin/aitask
```

确保 `~/bin` 在 PATH：

```bash
echo 'export PATH="$HOME/bin:$PATH"' >> ~/.zshrc
source ~/.zshrc
```

---

## 使用方式

```bash
aitask clipcap "修复 Supabase RLS 策略" ~/repos/clipcap-next
aitask clipcap "优化 Remotion storyboard 生成" ~/repos/clipcap-next
aitask openclaw "设计飞书 tmux 入口" ~/repos/openclaw
```

这样每个任务都是一个独立 tmux window。

---

# 再加一个任务状态修改命令

创建：

```bash
vim ~/bin/tstat
```

写入：

```bash
#!/usr/bin/env bash
set -euo pipefail

STATUS="${1:?usage: tstat <RUN|WAIT|DONE|ERR> <title>}"
TITLE="${2:?usage: tstat <RUN|WAIT|DONE|ERR> <title>}"

tmux rename-window "${STATUS}-${TITLE}"
```

授权：

```bash
chmod +x ~/bin/tstat
```

使用：

```bash
tstat WAIT "等待 Codex 回复"
tstat DONE "Supabase RLS 修复完成"
tstat ERR "Trigger preview 部署失败"
```

你在任务结束后手动敲一下，就可以把 window 状态变成：

```text
DONE-Supabase RLS 修复完成
```

---

# 再做一个任务列表面板

创建：

```bash
vim ~/bin/tasks
```

写入：

```bash
#!/usr/bin/env bash
set -euo pipefail

tmux list-sessions -F '#S' | while read -r session; do
  echo
  echo "== $session =="
  tmux list-windows -t "$session" -F '  #I. #W #{window_active}'
done
```

授权：

```bash
chmod +x ~/bin/tasks
```

以后你直接：

```bash
tasks
```

看到：

```text
== clipcap ==
  1. dashboard 0
  2. RUN-修复 Supabase RLS 策略 1
  3. WAIT-Remotion storyboard 生成 0
  4. DONE-PR 描述生成 0

== openclaw ==
  1. RUN-飞书入口安全方案 0
```

---

# Codex 完成后通知你

这是你场景里很关键的一步。

Codex 官方支持 `notify`，可以在 Codex 发出支持的事件时调用外部程序，目前官方文档说明支持的外部 notify 事件是 `agent-turn-complete`；这适合接桌面通知、chat webhook、CI 更新等。([OpenAI开发者][2])

你可以配置：

```bash
vim ~/.codex/config.toml
```

加入：

```toml
notify = ["bash", "/Users/colin/bin/codex-notify"]

[tui]
notifications = ["agent-turn-complete", "approval-requested"]
notification_method = "auto"
notification_condition = "always"
```

官方文档也区分了 `notify` 和 `tui.notifications`：前者调用外部程序，适合 webhook/桌面通知；后者是 TUI 内建通知，并可以过滤事件类型。([OpenAI开发者][2])

---

## 创建 Codex 通知脚本

```bash
vim ~/bin/codex-notify
```

写入：

```bash
#!/usr/bin/env bash
set -euo pipefail

PAYLOAD="${1:-{}}"

TITLE="$(python3 - <<'PY' "$PAYLOAD"
import json, sys, os
try:
    p = json.loads(sys.argv[1])
    cwd = p.get("cwd", "")
    task = os.path.basename(cwd) if cwd else "Codex"
    print(f"Codex 完成: {task}")
except Exception:
    print("Codex 完成")
PY
)"

MESSAGE="$(python3 - <<'PY' "$PAYLOAD"
import json, sys
try:
    p = json.loads(sys.argv[1])
    msg = p.get("last-assistant-message") or "Agent turn complete"
    print(msg[:300])
except Exception:
    print("Agent turn complete")
PY
)"

osascript -e "display notification \"$MESSAGE\" with title \"$TITLE\""
```

授权：

```bash
chmod +x ~/bin/codex-notify
```

这样 Codex 一个 turn 完成后，macOS 会弹通知。

---

# 如果你要飞书通知

你前面已经考虑了飞书入口。这里可以把 `codex-notify` 改成推送飞书：

```bash
fsay "Codex 完成：$TITLE

$MESSAGE"
```

这样你在手机飞书上也知道哪个任务完成了。

不过有个问题：Codex notify payload 里未必天然包含你 tmux window 的任务标题。所以我建议启动任务时写一个环境变量：

```bash
export AI_TASK_TITLE="修复 Supabase RLS 策略"
codex
```

然后通知脚本读取：

```bash
AI_TASK_TITLE
```

我们可以稍微改一下 `aitask`：

```bash
tmux send-keys -t "$SESSION:$WINDOW_NAME" "cd '$REPO' && export AI_TASK_TITLE='$TITLE' && codex" C-m
```

这样飞书通知里就能显示准确任务标题。

---

# iTerm2 怎么配合

你当前主力是 iTerm2，这很好。iTerm2 和 tmux 是强组合。

## 方式一：普通 tmux 模式

也就是：

```bash
tmux attach -t clipcap
```

优点：

```text
最稳定
远程/本地一致
iPhone SSH 也一致
tmux 原生快捷键都可用
```

这是我最推荐你的默认方式。

---

## 方式二：iTerm2 tmux integration

iTerm2 有官方 tmux integration，可以用原生 iTerm2 UI 享受 tmux 的持久化能力；官方文档明确说它允许用 native UI 获得 tmux persistence。([iTerm2][3])

用法大致是：

```bash
tmux -CC new -s clipcap
```

或：

```bash
tmux -CC attach -t clipcap
```

它会把 tmux window 映射成 iTerm2 tab，把 pane 映射成 iTerm2 split pane。

适合：

```text
你在 Mac 本机 iTerm2 上工作
想用 Cmd+数字切 tab
想用 iTerm2 原生分屏和搜索
```

但我对你的主工作流建议是：

```text
本机 iTerm2 可以试 tmux -CC
远程/iPhone/飞书入口场景仍然用普通 tmux attach
```

因为普通 tmux 行为最可预测。

---

# iTerm2 Badge 也可以用

iTerm2 有 Badge 功能，可以在 terminal 右上角显示动态状态，比如 host、git branch、任务名；官方文档说 badge 是 terminal session 右上角的大文本标签，可以显示动态状态。([iTerm2][4])

如果你不用 tmux，也可以用 iTerm2 Badge 给每个 tab 标任务名。

但你的场景是远程 + 持久 + 多终端，所以我建议：

```text
tmux window name 是主索引
iTerm2 badge 是辅助视觉提示
```

---

# iTerm2 通知也可以开

iTerm2 支持通过 triggers 对匹配到的输出执行动作，官方文档里提到 trigger 可以在终端接收到匹配文本时执行操作。([iTerm2][5])

你可以让 Codex 或脚本输出：

```text
TASK_DONE: 修复 Supabase RLS 策略
```

然后 iTerm2 trigger 匹配：

```text
TASK_DONE:
```

动作选择：

```text
Post Notification
```

这适合本机 iTerm2；如果你远程在 iPhone 上，就还是飞书通知更好。

---

# 推荐安装的 tmux 插件

插件不是必须，但这几个值得装。

## 1. TPM：tmux 插件管理器

TPM 是 tmux plugin manager，用来安装和加载 tmux 插件。([GitHub][6])

安装：

```bash
git clone https://github.com/tmux-plugins/tpm ~/.tmux/plugins/tpm
```

在 `~/.tmux.conf` 加：

```tmux
set -g @plugin 'tmux-plugins/tpm'
set -g @plugin 'tmux-plugins/tmux-sensible'
set -g @plugin 'tmux-plugins/tmux-resurrect'
set -g @plugin 'tmux-plugins/tmux-continuum'

run '~/.tmux/plugins/tpm/tpm'
```

然后在 tmux 里：

```text
Ctrl-b I
```

安装插件。

---

## 2. tmux-resurrect

这个很适合你。它可以保存 tmux 环境细节，并在重启后恢复 session；项目 README 也说明它能保存 tmux 环境并恢复，甚至可以配合 tmux-continuum 自动保存。([GitHub][7])

你的场景里，如果 Mac mini 重启，至少可以恢复：

```text
session
window
pane
工作目录
部分运行命令
```

注意：它不一定能恢复 Codex TUI 的完整运行状态，但能恢复你的工作布局。

---

## 3. tmux-continuum

tmux-continuum 支持连续保存 tmux 环境、开机自动启动 tmux、tmux 启动时自动恢复；README 也写明它支持 Linux、OSX 和 Cygwin。([GitHub][8])

推荐配置：

```tmux
set -g @continuum-restore 'on'
set -g @continuum-save-interval '15'
```

---

## 4. tmuxp / tmuxinator

如果你想把一个项目的 session 布局写成配置文件，可以用 tmuxp 或 tmuxinator。tmuxp 是通过配置文件保存和加载 tmux sessions 的 session manager。([GitHub][9]) tmuxinator 也是常见的复杂 tmux session 管理工具。([GitHub][10])

但我建议你暂时不用它们。

你的需求不是“固定项目布局”，而是“动态创建很多 AI 任务”。所以先用我上面给你的 `aitask` 脚本更合适。

---

# 我给你的最终推荐组合

```text
核心：
tmux window name = 任务标题

辅助：
aitask 脚本 = 一键创建任务窗口
tstat 脚本 = 修改任务状态
tasks 脚本 = 查看全部任务

通知：
Codex notify hook → macOS 通知 / 飞书通知

持久化：
tmux-resurrect + tmux-continuum

本机体验：
iTerm2 普通 attach 为主
可试 tmux -CC，但不要作为唯一方案
```

---

# 你最终会怎么用

创建任务：

```bash
aitask clipcap "修复 Supabase RLS 策略" ~/repos/clipcap-next
```

创建第二个任务：

```bash
aitask clipcap "优化 Remotion storyboard 生成" ~/repos/clipcap-next
```

查看任务：

```bash
tasks
```

切换任务：

```text
Ctrl-b w
```

任务完成后改状态：

```bash
tstat DONE "修复 Supabase RLS 策略"
```

远程回来：

```bash
ssh colin@mac-mini
tmux attach -t clipcap
```

---

# 我的判断

你的需求不需要找一个很复杂的“AI 终端管理插件”。
最稳的范式是：

```text
tmux 负责工作现场
window name 负责任务标题
Codex notify 负责完成提醒
iTerm2/飞书负责通知展示
```

这套方案非常贴合你现在的“多 Codex 任务并行 + 20 分钟异步等待 + 远程接力工作”的模式。

[1]: https://github.com/tmux/tmux/wiki/Getting-Started?utm_source=chatgpt.com "Getting Started · tmux/tmux Wiki"
[2]: https://developers.openai.com/codex/config-advanced "Advanced Configuration – Codex | OpenAI Developers"
[3]: https://iterm2.com/documentation-tmux-integration.html?utm_source=chatgpt.com "tmux Integration - Documentation"
[4]: https://iterm2.com/documentation-badges.html?utm_source=chatgpt.com "Badges - Documentation"
[5]: https://iterm2.com/documentation-triggers.html?utm_source=chatgpt.com "Triggers - Documentation"
[6]: https://github.com/tmux-plugins/tpm?utm_source=chatgpt.com "Tmux Plugin Manager"
[7]: https://github.com/tmux-plugins/tmux-resurrect?utm_source=chatgpt.com "tmux-plugins/tmux-resurrect"
[8]: https://github.com/tmux-plugins/tmux-continuum?utm_source=chatgpt.com "tmux-plugins/tmux-continuum: Continuous saving of ..."
[9]: https://github.com/tmux-python/tmuxp?utm_source=chatgpt.com "tmux-python/tmuxp: 🖥️ Session manager for ..."
[10]: https://github.com/tmuxinator/tmuxinator?utm_source=chatgpt.com "tmuxinator/tmuxinator: Manage complex tmux sessions easily"

# 分panel，扩大化panel，缩小到split pannel模式，是什么快捷键
tmux 里叫 **pane**，不是 panel。常用快捷键如下。

# 1. 分屏

## 左右分屏

```text
Ctrl-b %
```

也就是：

```text
先按 Ctrl-b，松开，再按 %
```

## 上下分屏

```text
Ctrl-b "
```

也就是：

```text
先按 Ctrl-b，松开，再按 "
```

如果你已经用了我前面给你的配置，也可以用：

```text
Ctrl-b |
```

左右分屏。

```text
Ctrl-b -
```

上下分屏。

---

# 2. 在 pane 之间切换

```text
Ctrl-b 方向键
```

例如：

```text
Ctrl-b ←
Ctrl-b →
Ctrl-b ↑
Ctrl-b ↓
```

---

# 3. 放大当前 pane

这个非常重要：

```text
Ctrl-b z
```

作用是：把当前 pane 临时放大成全屏。

再按一次：

```text
Ctrl-b z
```

就会恢复到 split pane 模式。

所以你问的：

> 扩大 pane / 缩小回 split pane

就是：

```text
Ctrl-b z
```

这是一个 toggle。

---

# 4. 调整 pane 大小

默认快捷键：

```text
Ctrl-b 然后按住 Ctrl + 方向键
```

例如：

```text
Ctrl-b Ctrl-←
Ctrl-b Ctrl-→
Ctrl-b Ctrl-↑
Ctrl-b Ctrl-↓
```

有些终端里这个不好用，可以用命令模式。

按：

```text
Ctrl-b :
```

然后输入：

```text
resize-pane -L 10
resize-pane -R 10
resize-pane -U 5
resize-pane -D 5
```

含义：

```text
-L 向左扩大/缩小
-R 向右扩大/缩小
-U 向上调整
-D 向下调整
```

---

# 5. 关闭当前 pane

```text
Ctrl-d
```

或者输入：

```bash
exit
```

---

# 你最常用的记这几个就够了

```text
Ctrl-a v     新建左右分屏
Ctrl-a s     新建上下分屏
Ctrl-a ;     切到左侧 pane
Ctrl-a '     切到右侧 pane
Ctrl-a [     切到上方 pane
Ctrl-a ]     切到下方 pane
Ctrl-a z     当前 pane 全屏/恢复
Ctrl-d       关闭当前 pane
```

你用 Codex 的时候，最常见组合是：

```text
左边：codex
右上：git diff
右下：pnpm test / go test / logs
```

然后需要专注看 Codex 时：

```text
Ctrl-b z
```

看完再按一次：

```text
Ctrl-b z
```

# 不输入目录，默认就是使用当前目录。 另外，给我增加一些快捷命令： tns tmux new -s xxx_session tls tmux ls tks tmux kill-session -t test tn tmux new-window -n "taskname" tl tmux list-windows (Ctrl-b w) : 你会看到所有任务标题。 ta tmux attach -t clipcap 它自动创建 tmux window，并用任务标题命名。: aitask clipcap "修复 Supabase RLS 策略" ~/repos/clipcap-next 类似这样： alias gsta='git stash push -u'
可以，建议做成一个独立命令 `thelp`，以后直接输入：

```bash
thelp
```

就能展示你的 tmux 快捷命令帮助文档。

---

# 1. 创建 `thelp` 命令

执行：

```bash
cat > ~/bin/thelp <<'EOF'
#!/usr/bin/env bash

cat <<'HELP'
============================================================
 tmux / AI Task 快捷命令帮助
============================================================

一、Session 相关
------------------------------------------------------------
tns <session>
  新建 tmux session

  示例：
    tns clipcap

tls
  查看所有 tmux session

  示例：
    tls

ta <session>
  attach 进入某个 session

  示例：
    ta clipcap

tks <session>
  删除某个 session

  示例：
    tks clipcap


二、Window / 任务窗口相关
------------------------------------------------------------
tn "<taskname>"
  在当前 session 中新建一个 window，并命名为任务名

  示例：
    tn "修复 Supabase RLS 策略"

tl
  查看当前 session 的所有 window

  示例：
    tl

tw
  交互式选择 window
  等价于：
    Ctrl-b w

  示例：
    tw


三、Pane / 分屏相关
------------------------------------------------------------
tsh
  左右分屏
  等价于：
    tmux split-window -h

tsv
  上下分屏
  等价于：
    tmux split-window -v

tz
  当前 pane 放大 / 恢复
  等价于：
    Ctrl-b z

  示例：
    tz


四、AI Task 相关
------------------------------------------------------------
at <session> "<task-title>"
  自动创建一个 AI 任务 window
  默认使用当前目录
  自动启动 codex
  自动把 window 命名为：
    RUN-<task-title>

  示例：
    at clipcap "修复 Supabase RLS 策略"

at <session> "<task-title>" <repo-dir>
  指定项目目录创建 AI 任务 window

  示例：
    at clipcap "修复 Supabase RLS 策略" ~/repos/clipcap-next

aitask <session> "<task-title>" [repo-dir]
  at 的完整命令形式

  示例：
    aitask clipcap "优化 Remotion storyboard 生成"


五、tmux 原生快捷键
------------------------------------------------------------
Ctrl-b d
  detach，退出 tmux 但不关闭任务

Ctrl-b c
  新建 window

Ctrl-b ,
  重命名当前 window

Ctrl-b w
  查看 / 选择所有 window

Ctrl-b n
  切换到下一个 window

Ctrl-b p
  切换到上一个 window

Ctrl-b 0-9
  切换到指定编号 window

Ctrl-b %
  左右分屏

Ctrl-b "
  上下分屏

Ctrl-b 方向键
  在 pane 之间切换

Ctrl-b z
  当前 pane 全屏 / 恢复

Ctrl-d
  关闭当前 pane


六、推荐日常流程
------------------------------------------------------------
进入项目目录：

  cd ~/repos/clipcap-next

创建 AI 任务：

  at clipcap "修复 Trigger preview branch 部署问题"

再创建一个任务：

  at clipcap "优化 Remotion storyboard 生成逻辑"

查看任务窗口：

  tl

选择任务窗口：

  tw

临时离开：

  Ctrl-b d

回来继续：

  ta clipcap


七、常见问题
------------------------------------------------------------
1. Ctrl-b 没反应？

  先确认是否在 tmux 内：

    echo $TMUX

  如果没有输出，需要先进入 tmux：

    tns clipcap
    或
    ta clipcap

2. tmux 任务标题被自动覆盖？

  确认 ~/.tmux.conf 中有：

    set -g allow-rename off
    setw -g automatic-rename off

3. 当前 pane 想全屏看 Codex？

    Ctrl-b z

  再按一次恢复。


八、我的推荐命名规范
------------------------------------------------------------
RUN-xxx
  正在执行

WAIT-xxx
  等待模型 / 等待外部结果

DONE-xxx
  已完成

ERR-xxx
  出错，需要处理

示例：

  RUN-修复 Supabase RLS 策略
  WAIT-等待 Codex 生成 PR 描述
  DONE-优化 Remotion storyboard
  ERR-Trigger preview 部署失败

============================================================
HELP
EOF

chmod +x ~/bin/thelp
```

---

# 2. 确认 `~/bin` 在 PATH 里

执行：

```bash
echo $PATH | grep "$HOME/bin"
```

如果没有输出，执行：

```bash
echo 'export PATH="$HOME/bin:$PATH"' >> ~/.zshrc
source ~/.zshrc
```

---

# 3. 使用

以后直接输入：

```bash
thelp
```

就会展示完整帮助文档。

---

# 4. 顺手确认你的 alias 是否已配置

你的 `~/.zshrc` 里建议有这些：

```bash
# ===== tmux shortcuts =====

alias tns='tmux new -s'
alias tls='tmux ls'
alias tks='tmux kill-session -t'
alias ta='tmux attach -t'
alias td='tmux detach'

alias tn='tmux new-window -n'
alias tl='tmux list-windows'
alias tw='tmux choose-window'

alias tz='tmux resize-pane -Z'
alias tsh='tmux split-window -h'
alias tsv='tmux split-window -v'

alias trc='tmux source-file ~/.tmux.conf'

alias at='aitask'
```

生效：

```bash
source ~/.zshrc
```

现在你的常用入口就是：

```bash
thelp
```

# alias 都配置了。thelp 要简洁。不要有大段空行 
可以，把 `thelp` 改成这个简洁版：

```bash
cat > ~/bin/thelp <<'EOF'
#!/usr/bin/env bash

cat <<'HELP'
tmux / AI Task shortcuts

Session:
  tns <session>              new session
  tls                        list sessions
  ta <session>               attach session
  tks <session>              kill session

Window:
  tn "<task>"                new window with task name
  tl                         list windows
  tw                         choose window, same as Ctrl-a w

Pane:
  Ctrl-a v                   split horizontally
  Ctrl-a s                   split vertically
  Ctrl-a ; / '               move left / right
  Ctrl-a [ / ]               move up / down
  tz                         zoom/unzoom pane, same as Ctrl-a z

AI Task:
  at                         aitask
  atn "<task>"               create AI task
  atl                        list tasks
  atwait                     list WAIT tasks
  ato <id>                   open task
  atw <id>                   mark WAIT
  atr <id>                   mark RUNNING
  atd <id>                   mark DONE
  ate <id> "reason"          mark ERR
  ats                        sync task/tmux state

tmux keys:
  Ctrl-a d                   detach
  td                         detach current tmux client
  Ctrl-a c                   new window
  Ctrl-a ,                   rename window
  Ctrl-a w                   choose window
  Ctrl-a n / p               next / previous window
  Ctrl-a v                   split horizontally
  Ctrl-a s                   split vertically
  Ctrl-a ; / '               move left / right
  Ctrl-a [ / ]               move up / down
  Ctrl-a z                   zoom/unzoom pane
  Ctrl-d                     close pane

Status naming:
  RUN-xxx                    running
  WAIT-xxx                   waiting
  DONE-xxx                   done
  ERR-xxx                    error

Examples:
  cd ~/repos/clipcap-next
  at clipcap "修复 Supabase RLS 策略"
  tl
  tw
  ta clipcap
HELP
EOF

chmod +x ~/bin/thelp
```

然后直接执行：

```bash
thelp
```

输出会比较紧凑。

# help 内容用中文
可以，改成中文简洁版：

```bash
cat > ~/bin/thelp <<'EOF'
#!/usr/bin/env bash

cat <<'HELP'
tmux / AI 任务快捷命令

Session 会话:
  tns <session>              新建会话
  tls                        查看所有会话
  ta <session>               进入会话
  tks <session>              删除会话

Window 窗口/任务:
  tn "<任务名>"              新建窗口并命名
  tl                         查看当前会话的所有窗口
  tw                         选择窗口，等价于 Ctrl-a w

Pane 分屏:
  Ctrl-a v                   新建左右分屏
  Ctrl-a s                   新建上下分屏
  Ctrl-a ; / '               左 / 右切换分屏
  Ctrl-a [ / ]               上 / 下切换分屏
  tz                         当前分屏放大/恢复，等价于 Ctrl-a z

AI Task:
  at                         aitask
  atn "任务标题"              创建 AI 任务
  atl                        查看任务列表
  atwait                     只看 WAIT 任务
  ato <id>                   进入任务
  atw <id>                   标记等待
  atr <id>                   标记运行中
  atd <id>                   标记完成
  ate <id> "原因"            标记错误
  ats                        修复 tmux/任务状态漂移
  atdoc                      检查 aitask 环境

tmux 原生快捷键:
  Ctrl-a d                   暂时退出 tmux，任务继续运行
  td                         同上，退出当前 tmux，任务继续运行
  Ctrl-a c                   新建窗口
  Ctrl-a ,                   重命名当前窗口
  Ctrl-a w                   选择窗口
  Ctrl-a n / p               下一个 / 上一个窗口
  Ctrl-a v                   新建左右分屏
  Ctrl-a s                   新建上下分屏
  Ctrl-a ; / '               左 / 右切换分屏
  Ctrl-a [ / ]               上 / 下切换分屏
  Ctrl-a z                   当前分屏放大/恢复
  Ctrl-d                     关闭当前分屏

任务状态命名:
  RUN-xxx                    正在执行
  WAIT-xxx                   等待中
  DONE-xxx                   已完成
  ERR-xxx                    出错

常用示例:
  cd ~/repos/clipcap-next
  at clipcap "修复 Supabase RLS 策略"
  tl
  tw
  ta clipcap
HELP
EOF

chmod +x ~/bin/thelp
```

执行：

```bash
thelp
```

# 将 tmux 前缀改为 Ctrl-a，并用 ; / ' 切换左右 pane
当前已经按这个方案配置：

```text
Ctrl-a ;    切到左侧 pane
Ctrl-a '    切到右侧 pane
Ctrl-a [    切到上方 pane
Ctrl-a ]    切到下方 pane
Ctrl-a v    新建左右分屏
Ctrl-a s    新建上下分屏
```

不建议直接把裸键 `;` 和 `'` 绑定成切换 pane，因为这样你在 shell 里就没法正常输入 `;` 和 `'` 了。

---

# 1. 修改 `~/.tmux.conf`

执行：

```bash
vim ~/.tmux.conf
```

当前 `~/.tmux.conf` 使用这组关键配置：

```tmux
# 使用 Ctrl-a 作为 tmux 前缀键
unbind C-b
set -g prefix C-a
bind C-a send-prefix

# 使用 Ctrl-a ; / Ctrl-a ' 切换左右 pane
unbind-key \;
unbind-key "'"
bind-key \; select-pane -L
bind-key "'" select-pane -R

# Ctrl-a [ / Ctrl-a ] 切换上下 pane
bind-key [ select-pane -U
bind-key ] select-pane -D

# Ctrl-a v 新建左右分屏；Ctrl-a s 新建上下分屏
bind-key v split-window -h
bind-key s split-window -v
```

---

# 2. 重新加载配置

在 tmux 外执行：

```bash
tmux source-file ~/.tmux.conf
```

或者在 tmux 里执行：

```text
Ctrl-a r
```

前提是你之前配置了：

```tmux
bind-key r source-file ~/.tmux.conf \; display-message "tmux config reloaded"
```

---

# 3. 使用方式

现在切换 pane：

```text
Ctrl-a ;    切到左侧 pane
Ctrl-a '    切到右侧 pane
```

如果加了上下：

```text
Ctrl-a [    切到上方 pane
Ctrl-a ]    切到下方 pane
```

新建分屏：

```text
Ctrl-a v    新建左右分屏
Ctrl-a s    新建上下分屏
```

---

# 4. 更新 `thelp`

你可以把 `thelp` 里的这行：

```text
Ctrl-b 方向键              切换分屏
```

改成：

```text
Ctrl-a v                   新建左右分屏
Ctrl-a s                   新建上下分屏
Ctrl-a ; / '               左 / 右切换分屏
Ctrl-a [ / ]               上 / 下切换分屏
```

也可以直接：

```bash
vim ~/bin/thelp
```

手动改这一小段最稳。

# 关闭任务窗口是什么 
关闭“任务窗口”在 tmux 里就是 **关闭当前 window**。

# 最常用方式

在当前任务窗口里执行：

```bash
exit
```

如果这个 window 里只有一个 pane，它会直接关闭这个任务窗口。

也可以按：

```text
Ctrl-d
```

---

# tmux 原生快捷键关闭当前 window

```text
Ctrl-b &
```

然后 tmux 会问你是否确认：

```text
kill-window? y/n
```

按：

```text
y
```

即可关闭当前任务窗口。

---

# 命令方式

关闭当前 window：

```bash
tmux kill-window
```

关闭指定 window：

```bash
tmux kill-window -t clipcap:3
```

或者按名字关闭：

```bash
tmux kill-window -t 'clipcap:RUN-修复 Supabase RLS 策略'
```

---

# 建议你加一个 alias

在 `~/.zshrc` 加：

```bash
alias tkw='tmux kill-window'
```

生效：

```bash
source ~/.zshrc
```

以后关闭当前任务窗口：

---

# aitask 落地版：tmux + Codex 任务管理器

这个 repo 现在提供了一个本地 CLI：

```bash
/Users/Shared/openclaw-share/repos/tmux_system/bin/aitask
/Users/Shared/openclaw-share/repos/tmux_system/bin/aitask-codex-notify
/Users/Shared/openclaw-share/repos/tmux_system/bin/codex-notify-dispatch
```

建议加入 PATH：

```bash
export PATH="/Users/Shared/openclaw-share/repos/tmux_system/bin:$PATH"
```

## 核心工作流

创建一个 AI 任务：

```bash
atn "修复登录超时问题"
```

默认会让 Codex 跳过审批和沙箱启动：

```bash
codex --dangerously-bypass-approvals-and-sandbox
```

如果需要覆盖：

```bash
atn "只读调研" --command "codex --sandbox read-only"
```

指定 tmux session 和项目目录：

```bash
atn "设计飞书路由" --session openclaw --cwd ~/repos/openclaw
```

查看任务列表：

```bash
atl
atwait
```

`UPDATED` 按本机时区显示；旧的 UTC 时间会在展示时转换成本机时间。

已经被清理或丢失 tmux window 的 task 会在 `at` / `atl` 时自动标记为 `DONE`，默认列表不再展示；需要追溯时用 `atl --all`。

Codex 从 `WAIT` 进入执行时，`aitask` 会通过主 pane 的输出和当前屏幕内容识别 `Working ... / esc to interrupt`，自动把状态转为 `RUNNING`。

`ato <id>` 默认会先抓取该 task 主 pane 最近输出并推送到飞书，再进入 tmux。它使用 `AITASK_FEISHU_TARGET` + OpenClaw 发送通道，或退回 `AITASK_FEISHU_WEBHOOK`：

```bash
AITASK_FEISHU_CHANNEL='feishu'
AITASK_FEISHU_ACCOUNT='aitask'
AITASK_FEISHU_TARGET='chat:oc_xxx 或 user:ou_xxx'
```

当任意 task 从 `RUNNING` 变为 `WAIT` 时，会自动向配置的飞书目标发送提醒。这个流转可能来自 Codex `agent-turn-complete`，也可能来自 `aitask sync` 发现 Codex 已经回到输入提示符，或手动执行 `atw <id>`。

如果只想进入任务、不推送飞书：

```bash
aitask open --no-feishu <id>
```

飞书机器人里也可以直接操作 `aitask`：

```text
at                         查看任务列表
at wait                    只看 WAIT 任务
at new 任务标题             创建任务
at show 6                  查看任务元信息
at tail 6                  查看 Codex 主 pane 最近输出
at open 6                  激活本机 tmux window，并把最近输出回飞书
at send 6 继续执行          输入内容给 Codex
at 6 继续执行               send 的快捷写法
```

注意：飞书里的 `at open` 不会把 tmux 嵌入飞书，也不会让 gateway 进程 attach；它只会在本机 tmux 中选择对应 window，并返回最近输出和 attach 提示。
`at send` 会处理 Codex 的目录 trust prompt；只有看到 Codex 进入 `Working` 后才标记为 `RUNNING`，避免“状态 running 但其实没干活”。
`at` / `ats` 只看屏幕底部近期状态，不会因为历史 scrollback 里的旧 `Working` 把已结束任务重新误标为 `RUNNING`；如果 Codex 已回到输入提示符，会修正为 `WAIT`。

进入任务：

```bash
ato 12
```

手动改状态：

```bash
atw 12
atr 12
atd 12
ate 12 "tests failed"
```

修复 tmux 和数据库状态漂移：

```bash
ats
```

检查环境：

```bash
aitask doctor
```

## 状态设计

```text
PENDING / RUNNING / WAIT / DONE / ERR
```

`WAIT` 会排在列表最前面。任务窗口名会同步为：

```text
WAIT 修复登录超时问题
RUNNING 设计飞书路由
DONE 调研 Codex notify
```

tmux window 还会写入 metadata：

```text
@aitask_id
@aitask_status
```

## Codex 完成后自动 WAIT

把下面配置加入 `~/.codex/config.toml`：

```toml
notify = ["python3", "/Users/Shared/openclaw-share/repos/tmux_system/bin/codex-notify-dispatch"]
```

也可以用命令打印配置：

```bash
aitask notify-config
```

`aitask new` 启动 Codex 时会注入：

```bash
AITASK_ID=<id>
AITASK_TITLE=<title>
```

Codex 发出 `agent-turn-complete` 后，`codex-notify-dispatch` 会先保留原有 Computer Use notify 行为，再调用 `aitask-codex-notify`：

1. 找到对应任务。
2. 把任务状态改成 `WAIT`。
3. 重命名 tmux window。
4. 尝试把 WAIT window 移到前面。
5. 如果配置了桌面通知或飞书 OpenClaw 目标 / webhook，就发送提醒。

## WAIT 什么时候变 RUNNING

`WAIT` 表示 Codex 已经停下来，正在等你交互。即使你进入这个 task window、切 pane、执行日常命令，它仍然应该保持 `WAIT`。

`ato <id>` 只负责进入 task window，不自动改状态。

`aitask` 会对 Codex 主 pane 启用 `tmux pipe-pane` 监听。当 Codex TUI 输出进入 `Working ... / esc to interrupt` 这类运行状态时，task 会自动从 `WAIT` 转为 `RUNNING`。

如果监听没有捕获到，或者你不是在 Codex 主 pane 里继续任务，可以手动执行：

```bash
atr <id>
```

这样状态语义更清楚：

```text
WAIT     等你交互
RUNNING  Codex 已经开始处理
DONE     任务完成
ERR      任务异常
```

## 手机 SSH 使用

手机上不需要 iTerm2 特性，只要 SSH 后运行：

```bash
aitask list
aitask open <id>
```

列表是紧凑文本输出，适合窄屏。所有任务状态都存在 SQLite：

```text
~/.local/share/aitask/tasks.db
```

配置位置：

```text
~/.config/aitask/config.json
~/.config/aitask/feishu.env
```

更多细节见：

```bash
docs/aitask.md
```

```bash
tkw
```

---

# 建议更新 thelp

加到 Window 部分：

```text
  tkw                        关闭当前窗口
  Ctrl-b &                   关闭当前窗口，需要确认
```

你日常最常用的就是：

```text
Ctrl-b &
```

或者：

```bash
tkw
```
