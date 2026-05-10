---
name: wt-space
description: 管理长期保存的 Git worktree 空间分支。用户提到 wt-start、wt-finish、worktree、空间分支、长期分支开发、从当前项目分支 update 到新空间、把空间分支 merge 回当前项目分支时使用。
---

# wt-space

这个 skill 用来把一个任务放进长期保存的 Git worktree 空间中开发。它替代旧的 `wt-start` / `wt-finish` 一次性流程：空间启用后默认不删除，后续反复执行 “当前项目分支 -> 空间分支” 的更新，以及 “空间分支 -> 当前项目分支” 的合并回流。

## 核心模型

- 主工作区：当前项目的常规 checkout，通常是用户日常所在目录。
- 空间工作区：保存在主工作区同级的 `.codex-worktrees/<repo>/<space>`。
- 空间分支：默认命名为 `codex/space/<space>`，长期存在。
- 默认流向：
  - `update`：把主工作区当前分支的已提交代码合入空间分支。
  - `merge-back`：把空间分支合入主工作区当前分支。

## 必须遵守

- 操作前先看 `git status --short`，主工作区或空间工作区有未提交改动时，不要强行合并、rebase 或删除。
- 遇到冲突立即停止，报告冲突状态；不要猜测解决。
- 不要自动 push，除非用户明确要求。
- 长期空间默认使用 merge 维护历史，不要默认 squash；squash 只在用户明确要求时使用。
- 用户说 `wt-finish` 时，按 `merge-back` 理解：合并回来，但不删除 worktree，也不删除空间分支，除非用户明确要求清理。
- 不要调用项目内旧的 `.agents/skills/wt-start` 或 `.agents/skills/wt-finish`；使用这个全局脚本。

## 命令

脚本路径：

```bash
bash "$HOME/.codex/skills/wt-space/scripts/wt-space.sh" --help
```

### 开启或复用空间

从主工作区执行：

```bash
bash "$HOME/.codex/skills/wt-space/scripts/wt-space.sh" start "<space-slug>" [base-branch]
```

- `space-slug` 用短横线命名，例如 `video-preview-fix`。
- `base-branch` 不传时使用主工作区当前分支。
- 如果空间已经存在，脚本会复用并输出路径，不会重建。

完成后把 `WORKTREE_PATH` 和 `OPEN_COMMAND` 返回给用户，并停止在主工作区继续编码。

### 从当前项目分支更新到空间

```bash
bash "$HOME/.codex/skills/wt-space/scripts/wt-space.sh" update "<space-slug>" [source-branch] [merge|rebase]
```

- `source-branch` 不传时使用主工作区当前分支。
- 默认策略是 `merge`，适合长期空间。
- 只有用户明确要求线性历史时才用 `rebase`。

### 将空间分支合并回来

```bash
bash "$HOME/.codex/skills/wt-space/scripts/wt-space.sh" merge-back "<space-slug>" [target-branch] [no-ff|ff-only|squash]
```

- `target-branch` 不传时使用主工作区当前分支。
- 默认模式是 `no-ff`，适合长期空间反复回流。
- 合并后空间仍然保留。下一次继续开发前，通常再执行一次 `update`。

### 查看空间状态

```bash
bash "$HOME/.codex/skills/wt-space/scripts/wt-space.sh" status "<space-slug>" [compare-branch]
```

## 返回格式

执行脚本后，把关键输出转述给用户：

- `MAIN_ROOT`
- `WORKTREE_PATH`
- `SPACE_BRANCH`
- `SOURCE_BRANCH` 或 `TARGET_BRANCH`
- `OPEN_COMMAND`
- 下一步建议命令
