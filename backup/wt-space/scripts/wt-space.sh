#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
usage:
  wt-space.sh start <space-slug> [base-branch]
  wt-space.sh update <space-slug> [source-branch] [merge|rebase]
  wt-space.sh merge-back <space-slug> [target-branch] [no-ff|ff-only|squash]
  wt-space.sh finish <space-slug> [target-branch] [no-ff|ff-only|squash]
  wt-space.sh status <space-slug> [compare-branch]

Long-lived Codex git worktree spaces. Worktrees are kept under:
  <repo-parent>/.codex-worktrees/<repo>/<space-slug>

finish is an alias for merge-back and does not delete the worktree.
USAGE
}

die() {
  echo "ERROR: $*" >&2
  exit 1
}

warn() {
  echo "WARN: $*" >&2
}

slugify() {
  printf '%s' "${1:-}" \
    | tr '[:upper:]' '[:lower:]' \
    | sed -E 's#[^a-z0-9._-]+#-#g; s#-+#-#g; s#(^-|-$)##g'
}

require_git_repo() {
  git rev-parse --show-toplevel >/dev/null 2>&1 || die "current directory is not inside a git repository"
}

current_branch() {
  local repo="$1"
  local branch
  branch="$(git -C "$repo" rev-parse --abbrev-ref HEAD)"
  [[ "$branch" != "HEAD" ]] || die "detached HEAD is not supported in $repo"
  printf '%s\n' "$branch"
}

is_clean() {
  local repo="$1"
  [[ -z "$(git -C "$repo" status --porcelain)" ]]
}

require_clean() {
  local repo="$1"
  local label="$2"
  if ! is_clean "$repo"; then
    echo "STATUS_${label}:"
    git -C "$repo" status --short
    die "$label checkout has uncommitted changes: $repo"
  fi
}

fetch_origin() {
  local repo="$1"
  git -C "$repo" remote get-url origin >/dev/null 2>&1 || return 0
  git -C "$repo" fetch origin >/dev/null 2>&1 || warn "fetch origin failed in $repo; continuing with local refs"
}

resolve_main_root() {
  local root meta line path
  root="$(git rev-parse --show-toplevel)"

  if [[ -d "$root/.git" ]]; then
    printf '%s\n' "$root"
    return 0
  fi

  meta="$(git -C "$root" rev-parse --git-dir)/codex-worktree-space.env"
  if [[ -f "$meta" ]]; then
    # shellcheck disable=SC1090
    source "$meta"
    if [[ -n "${MAIN_ROOT:-}" && -d "$MAIN_ROOT/.git" ]]; then
      printf '%s\n' "$MAIN_ROOT"
      return 0
    fi
  fi

  meta="$root/.codex/worktree-space.env"
  if [[ -f "$meta" ]]; then
    # Backward compatibility for spaces created by early versions of this skill.
    # shellcheck disable=SC1090
    source "$meta"
    if [[ -n "${MAIN_ROOT:-}" && -d "$MAIN_ROOT/.git" ]]; then
      printf '%s\n' "$MAIN_ROOT"
      return 0
    fi
  fi

  while IFS= read -r line; do
    if [[ "$line" == worktree\ * ]]; then
      path="${line#worktree }"
      if [[ -d "$path/.git" ]]; then
        printf '%s\n' "$path"
        return 0
      fi
    fi
  done < <(git -C "$root" worktree list --porcelain)

  die "could not find the main checkout for $root"
}

worktree_base() {
  local main_root="$1"
  local repo_name parent
  repo_name="$(basename "$main_root")"
  parent="$(dirname "$main_root")"
  printf '%s\n' "${CODEX_WORKTREE_ROOT:-$parent/.codex-worktrees/$repo_name}"
}

space_branch() {
  printf 'codex/space/%s\n' "$1"
}

default_space_path() {
  local main_root="$1"
  local slug="$2"
  printf '%s/%s\n' "$(worktree_base "$main_root")" "$slug"
}

find_worktree_for_branch() {
  local main_root="$1"
  local branch="$2"
  local line path=""
  local branch_ref="refs/heads/$branch"

  while IFS= read -r line; do
    if [[ "$line" == worktree\ * ]]; then
      path="${line#worktree }"
    elif [[ "$line" == branch\ * && "${line#branch }" == "$branch_ref" ]]; then
      printf '%s\n' "$path"
      return 0
    fi
  done < <(git -C "$main_root" worktree list --porcelain)

  return 1
}

write_meta() {
  local main_root="$1"
  local wt_path="$2"
  local slug="$3"
  local branch="$4"
  local base_branch="$5"
  local created_at="$6"

  local meta_dir
  meta_dir="$(git -C "$wt_path" rev-parse --git-dir)"
  mkdir -p "$meta_dir"
  {
    printf 'MAIN_ROOT=%q\n' "$main_root"
    printf 'WT_PATH=%q\n' "$wt_path"
    printf 'SPACE_SLUG=%q\n' "$slug"
    printf 'SPACE_BRANCH=%q\n' "$branch"
    printf 'BASE_BRANCH=%q\n' "$base_branch"
    printf 'CREATED_AT=%q\n' "$created_at"
  } > "$meta_dir/codex-worktree-space.env"
}

resolve_ref() {
  local main_root="$1"
  local ref="$2"

  if git -C "$main_root" show-ref --verify --quiet "refs/heads/${ref}"; then
    printf '%s\n' "$ref"
  elif git -C "$main_root" show-ref --verify --quiet "refs/remotes/origin/${ref}"; then
    printf 'origin/%s\n' "$ref"
  elif git -C "$main_root" rev-parse --verify --quiet "${ref}^{commit}" >/dev/null; then
    printf '%s\n' "$ref"
  else
    die "branch or ref not found: $ref"
  fi
}

resolve_existing_space_path() {
  local main_root="$1"
  local slug="$2"
  local branch path
  branch="$(space_branch "$slug")"

  if find_worktree_for_branch "$main_root" "$branch"; then
    return 0
  fi

  path="$(default_space_path "$main_root" "$slug")"
  if [[ -e "$path" ]]; then
    git -C "$path" rev-parse --show-toplevel >/dev/null 2>&1 || die "space path exists but is not a git worktree: $path"
    printf '%s\n' "$path"
    return 0
  fi

  return 1
}

ensure_space() {
  local main_root="$1"
  local slug="$2"
  local path branch actual_branch
  branch="$(space_branch "$slug")"

  path="$(resolve_existing_space_path "$main_root" "$slug")" || die "space does not exist: $slug. Run start first."
  actual_branch="$(current_branch "$path")"
  [[ "$actual_branch" == "$branch" ]] || die "space $slug is on branch $actual_branch, expected $branch"
  printf '%s\n' "$path"
}

pull_current_branch_if_origin_exists() {
  local repo="$1"
  local branch="$2"
  if git -C "$repo" show-ref --verify --quiet "refs/remotes/origin/${branch}"; then
    git -C "$repo" pull --ff-only origin "$branch"
  fi
}

cmd_start() {
  local raw_slug="${1:-}"
  [[ -n "$raw_slug" ]] || die "missing space-slug"

  local slug main_root base_branch branch wt_path existing_path base_ref created_at bootstrap_script=""
  slug="$(slugify "$raw_slug")"
  [[ -n "$slug" ]] || die "space-slug is empty after slugify"

  main_root="$(resolve_main_root)"
  base_branch="${2:-$(current_branch "$main_root")}"
  branch="$(space_branch "$slug")"

  fetch_origin "$main_root"

  if existing_path="$(resolve_existing_space_path "$main_root" "$slug")"; then
    wt_path="$existing_path"
    write_meta "$main_root" "$wt_path" "$slug" "$branch" "$base_branch" "existing"
    echo "MAIN_ROOT=$main_root"
    echo "WORKTREE_PATH=$wt_path"
    echo "SPACE_SLUG=$slug"
    echo "SPACE_BRANCH=$branch"
    echo "BASE_BRANCH=$base_branch"
    echo "RESULT=reused"
    echo "OPEN_COMMAND=code -n \"$wt_path\""
    return 0
  fi

  wt_path="$(default_space_path "$main_root" "$slug")"
  mkdir -p "$(dirname "$wt_path")"

  if git -C "$main_root" show-ref --verify --quiet "refs/heads/${branch}"; then
    git -C "$main_root" worktree add "$wt_path" "$branch"
  else
    base_ref="$(resolve_ref "$main_root" "$base_branch")"
    git -C "$main_root" worktree add -b "$branch" "$wt_path" "$base_ref"
  fi

  created_at="$(date +%Y%m%d-%H%M%S)"
  write_meta "$main_root" "$wt_path" "$slug" "$branch" "$base_branch" "$created_at"

  if [[ -x "$main_root/bootstrap-worktree.sh" ]]; then
    bootstrap_script="$main_root/bootstrap-worktree.sh"
  elif [[ -x "$main_root/scripts/bootstrap-worktree.sh" ]]; then
    bootstrap_script="$main_root/scripts/bootstrap-worktree.sh"
  fi

  if [[ -n "$bootstrap_script" ]]; then
    echo "BOOTSTRAP=$bootstrap_script"
    (cd "$wt_path" && "$bootstrap_script")
  fi

  echo "MAIN_ROOT=$main_root"
  echo "WORKTREE_PATH=$wt_path"
  echo "SPACE_SLUG=$slug"
  echo "SPACE_BRANCH=$branch"
  echo "BASE_BRANCH=$base_branch"
  echo "RESULT=created"
  echo "OPEN_COMMAND=code -n \"$wt_path\""
  echo "NEXT_UPDATE_COMMAND=bash \"\$HOME/.codex/skills/wt-space/scripts/wt-space.sh\" update \"$slug\""
}

cmd_update() {
  local raw_slug="${1:-}"
  [[ -n "$raw_slug" ]] || die "missing space-slug"

  local slug main_root wt_path source_branch strategy source_ref branch
  slug="$(slugify "$raw_slug")"
  main_root="$(resolve_main_root)"
  wt_path="$(ensure_space "$main_root" "$slug")"
  source_branch="${2:-$(current_branch "$main_root")}"
  strategy="${3:-merge}"
  branch="$(space_branch "$slug")"

  require_clean "$main_root" "MAIN"
  require_clean "$wt_path" "SPACE"
  fetch_origin "$main_root"

  if [[ "$source_branch" == "$(current_branch "$main_root")" ]]; then
    pull_current_branch_if_origin_exists "$main_root" "$source_branch"
  fi

  source_ref="$(resolve_ref "$main_root" "$source_branch")"

  case "$strategy" in
    merge)
      git -C "$wt_path" merge --no-edit "$source_ref"
      ;;
    rebase)
      git -C "$wt_path" rebase "$source_ref"
      ;;
    *)
      die "unknown update strategy: $strategy"
      ;;
  esac

  echo "MAIN_ROOT=$main_root"
  echo "WORKTREE_PATH=$wt_path"
  echo "SPACE_SLUG=$slug"
  echo "SPACE_BRANCH=$branch"
  echo "SOURCE_BRANCH=$source_branch"
  echo "UPDATE_STRATEGY=$strategy"
  echo "RESULT=updated"
  echo "NEXT_MERGE_BACK_COMMAND=bash \"\$HOME/.codex/skills/wt-space/scripts/wt-space.sh\" merge-back \"$slug\""
}

cmd_merge_back() {
  local raw_slug="${1:-}"
  [[ -n "$raw_slug" ]] || die "missing space-slug"

  local slug main_root wt_path target_branch mode branch
  slug="$(slugify "$raw_slug")"
  main_root="$(resolve_main_root)"
  wt_path="$(ensure_space "$main_root" "$slug")"
  target_branch="${2:-$(current_branch "$main_root")}"
  mode="${3:-no-ff}"
  branch="$(space_branch "$slug")"

  require_clean "$main_root" "MAIN"
  require_clean "$wt_path" "SPACE"
  fetch_origin "$main_root"

  git -C "$main_root" switch "$target_branch"
  pull_current_branch_if_origin_exists "$main_root" "$target_branch"

  case "$mode" in
    no-ff)
      git -C "$main_root" merge --no-ff "$branch" -m "merge: $slug workspace"
      ;;
    ff-only)
      git -C "$main_root" merge --ff-only "$branch"
      ;;
    squash)
      warn "squash is not recommended for long-lived spaces unless explicitly intended"
      git -C "$main_root" merge --squash "$branch"
      if ! git -C "$main_root" diff --cached --quiet; then
        git -C "$main_root" commit -m "merge: $slug workspace"
      fi
      ;;
    *)
      die "unknown merge mode: $mode"
      ;;
  esac

  echo "MAIN_ROOT=$main_root"
  echo "WORKTREE_PATH=$wt_path"
  echo "SPACE_SLUG=$slug"
  echo "SPACE_BRANCH=$branch"
  echo "TARGET_BRANCH=$target_branch"
  echo "MERGE_MODE=$mode"
  echo "RESULT=merged-back"
  echo "PERSISTED=true"
  echo "NEXT_UPDATE_COMMAND=bash \"\$HOME/.codex/skills/wt-space/scripts/wt-space.sh\" update \"$slug\" \"$target_branch\""
}

cmd_status() {
  local raw_slug="${1:-}"
  [[ -n "$raw_slug" ]] || die "missing space-slug"

  local slug main_root wt_path compare_branch branch counts
  slug="$(slugify "$raw_slug")"
  main_root="$(resolve_main_root)"
  wt_path="$(ensure_space "$main_root" "$slug")"
  compare_branch="${2:-$(current_branch "$main_root")}"
  branch="$(space_branch "$slug")"

  counts="$(git -C "$main_root" rev-list --left-right --count "$compare_branch...$branch" 2>/dev/null || true)"

  echo "MAIN_ROOT=$main_root"
  echo "WORKTREE_PATH=$wt_path"
  echo "SPACE_SLUG=$slug"
  echo "SPACE_BRANCH=$branch"
  echo "COMPARE_BRANCH=$compare_branch"
  if [[ -n "$counts" ]]; then
    echo "BEHIND_AHEAD=$counts"
  fi
  echo "MAIN_STATUS:"
  git -C "$main_root" status --short
  echo "SPACE_STATUS:"
  git -C "$wt_path" status --short
}

main() {
  require_git_repo

  local cmd="${1:-}"
  shift || true

  case "$cmd" in
    start)
      cmd_start "$@"
      ;;
    update)
      cmd_update "$@"
      ;;
    merge-back|merge_back)
      cmd_merge_back "$@"
      ;;
    finish)
      cmd_merge_back "$@"
      ;;
    status)
      cmd_status "$@"
      ;;
    -h|--help|help|"")
      usage
      ;;
    *)
      usage >&2
      die "unknown command: $cmd"
      ;;
  esac
}

main "$@"
