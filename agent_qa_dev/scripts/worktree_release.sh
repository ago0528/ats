#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
SCRIPT_REPO_CANDIDATE="$(cd "${SCRIPT_DIR}/.." && pwd -P)"

log() {
  printf '[worktree-release] %s\n' "$*"
}

warn() {
  printf '[worktree-release][WARN] %s\n' "$*" >&2
}

die() {
  printf '[worktree-release][ERROR] %s\n' "$*" >&2
  exit 1
}

usage() {
  cat <<'EOF'
Usage:
  scripts/worktree_release.sh prepare --handoff <branch> [options]
  scripts/worktree_release.sh verify [options]
  scripts/worktree_release.sh promote [options]
  scripts/worktree_release.sh cleanup [options]
  scripts/worktree_release.sh status [options]

Common options:
  --repo-root <path>        Git repo root (default: auto-detect)
  --worktree <path>         Preview worktree path (default: /tmp/ats-merge-check)
  --frontend <path>         Frontend relative path (auto-detect if omitted)
  --base <branch>           Base branch (default: main)
  --remote <name>           Remote name (default: origin)

prepare options:
  --handoff <branch>        REQUIRED. Handoff branch to merge
  --preview <branch>        Preview branch name (default: auto-generated)
  --skip-install            Skip pnpm install even when node_modules is missing

verify options:
  (none beyond common options)

promote options:
  --skip-verify             Skip test/build before push

cleanup options:
  --preview <branch>        Preview branch to delete (default: from state)
  --handoff <branch>        Handoff branch (default: from state)
  --delete-handoff-local    Delete local handoff branch
  --delete-handoff-remote   Delete remote handoff branch
  --keep-state              Keep state file after cleanup

Examples:
  scripts/worktree_release.sh prepare --handoff codex/my-feature
  scripts/worktree_release.sh promote
  scripts/worktree_release.sh cleanup --delete-handoff-local
EOF
}

ensure_cmd() {
  command -v "$1" >/dev/null 2>&1 || die "Required command not found: $1"
}

detect_repo_root() {
  local candidate="${1:-}"
  if [ -n "$candidate" ]; then
    git -C "$candidate" rev-parse --show-toplevel >/dev/null 2>&1 || die "Invalid --repo-root: $candidate"
    git -C "$candidate" rev-parse --show-toplevel
    return
  fi

  if git rev-parse --show-toplevel >/dev/null 2>&1; then
    git rev-parse --show-toplevel
    return
  fi

  if git -C "$SCRIPT_REPO_CANDIDATE" rev-parse --show-toplevel >/dev/null 2>&1; then
    git -C "$SCRIPT_REPO_CANDIDATE" rev-parse --show-toplevel
    return
  fi

  die "Could not detect git repository root. Run inside repo or pass --repo-root."
}

canonical_path() {
  local input="$1"
  local base dir file

  if [ -e "$input" ]; then
    (cd "$input" && pwd -P)
    return
  fi

  dir="$(dirname "$input")"
  file="$(basename "$input")"

  if [ "$dir" = "." ]; then
    base="$(pwd -P)"
  else
    base="$(cd "$dir" 2>/dev/null && pwd -P)" || die "Parent directory does not exist: $dir"
  fi

  printf '%s/%s\n' "$base" "$file"
}

state_file_path() {
  printf '%s/.git/worktree-release-state.env\n' "$1"
}

save_state() {
  local repo_root="$1"
  local worktree_path="$2"
  local preview_branch="$3"
  local handoff_branch="$4"
  local base_branch="$5"
  local remote_name="$6"
  local frontend_dir="$7"
  local state_file

  state_file="$(state_file_path "$repo_root")"
  {
    printf 'WORKTREE_PATH=%q\n' "$worktree_path"
    printf 'PREVIEW_BRANCH=%q\n' "$preview_branch"
    printf 'HANDOFF_BRANCH=%q\n' "$handoff_branch"
    printf 'BASE_BRANCH=%q\n' "$base_branch"
    printf 'REMOTE_NAME=%q\n' "$remote_name"
    printf 'FRONTEND_DIR=%q\n' "$frontend_dir"
  } > "$state_file"
}

load_state() {
  local repo_root="$1"
  local state_file
  state_file="$(state_file_path "$repo_root")"
  if [ -f "$state_file" ]; then
    # shellcheck disable=SC1090
    source "$state_file"
  fi
}

is_registered_worktree() {
  local repo_root="$1"
  local target="$2"
  git -C "$repo_root" worktree list --porcelain | awk '/^worktree /{print $2}' | grep -Fx "$target" >/dev/null 2>&1
}

resolve_handoff_ref() {
  local repo_root="$1"
  local remote_name="$2"
  local handoff_branch="$3"

  if git -C "$repo_root" rev-parse --verify "${handoff_branch}^{commit}" >/dev/null 2>&1; then
    printf '%s\n' "$handoff_branch"
    return
  fi

  if git -C "$repo_root" rev-parse --verify "${remote_name}/${handoff_branch}^{commit}" >/dev/null 2>&1; then
    printf '%s/%s\n' "$remote_name" "$handoff_branch"
    return
  fi

  die "Handoff branch not found: $handoff_branch"
}

detect_frontend_dir() {
  local root="$1"
  local preferred="${2:-}"

  if [ -n "$preferred" ]; then
    [ -f "$root/$preferred/package.json" ] || die "Invalid --frontend path (package.json missing): $preferred"
    printf '%s\n' "$preferred"
    return
  fi

  if [ -f "$root/agent_qa_dev/backoffice/frontend/package.json" ]; then
    printf '%s\n' "agent_qa_dev/backoffice/frontend"
    return
  fi

  if [ -f "$root/backoffice/frontend/package.json" ]; then
    printf '%s\n' "backoffice/frontend"
    return
  fi

  die "Could not auto-detect frontend path. Pass --frontend."
}

sanitize_branch_slug() {
  local branch="$1"
  printf '%s\n' "$branch" | sed -E 's#[^A-Za-z0-9._/-]#-#g; s#/#-#g'
}

run_frontend_verify() {
  local worktree_path="$1"
  local frontend_dir="$2"
  local frontend_abs="$worktree_path/$frontend_dir"

  ensure_cmd pnpm

  if [ ! -f "$frontend_abs/package.json" ]; then
    die "package.json not found: $frontend_abs"
  fi

  if [ ! -d "$frontend_abs/node_modules" ]; then
    log "node_modules missing -> running pnpm install"
    pnpm -C "$frontend_abs" install
  fi

  log "Running frontend tests"
  pnpm -C "$frontend_abs" test

  log "Running frontend build"
  pnpm -C "$frontend_abs" build
}

cmd_prepare() {
  local repo_root_opt=""
  local worktree_path="/tmp/ats-merge-check"
  local preview_branch=""
  local handoff_branch=""
  local base_branch="main"
  local remote_name="origin"
  local frontend_dir=""
  local skip_install=0
  local repo_root handoff_ref slug

  while [ $# -gt 0 ]; do
    case "$1" in
      --repo-root) [ $# -ge 2 ] || die "Missing value for --repo-root"; repo_root_opt="$2"; shift 2 ;;
      --worktree) [ $# -ge 2 ] || die "Missing value for --worktree"; worktree_path="$2"; shift 2 ;;
      --preview) [ $# -ge 2 ] || die "Missing value for --preview"; preview_branch="$2"; shift 2 ;;
      --handoff) [ $# -ge 2 ] || die "Missing value for --handoff"; handoff_branch="$2"; shift 2 ;;
      --base) [ $# -ge 2 ] || die "Missing value for --base"; base_branch="$2"; shift 2 ;;
      --remote) [ $# -ge 2 ] || die "Missing value for --remote"; remote_name="$2"; shift 2 ;;
      --frontend) [ $# -ge 2 ] || die "Missing value for --frontend"; frontend_dir="$2"; shift 2 ;;
      --skip-install) skip_install=1; shift ;;
      -h|--help) usage; exit 0 ;;
      *) die "Unknown option for prepare: $1" ;;
    esac
  done

  [ -n "$handoff_branch" ] || die "--handoff is required"
  repo_root="$(detect_repo_root "$repo_root_opt")"
  worktree_path="$(canonical_path "$worktree_path")"

  if [ -z "$preview_branch" ]; then
    slug="$(sanitize_branch_slug "$handoff_branch")"
    preview_branch="preview/${slug}-$(date +%Y%m%d-%H%M%S)"
  fi

  log "Repo root: $repo_root"
  log "Fetching $remote_name"
  git -C "$repo_root" fetch "$remote_name" --prune

  if ! git -C "$repo_root" rev-parse --verify "${base_branch}^{commit}" >/dev/null 2>&1; then
    if git -C "$repo_root" rev-parse --verify "${remote_name}/${base_branch}^{commit}" >/dev/null 2>&1; then
      log "Creating local $base_branch from $remote_name/$base_branch"
      git -C "$repo_root" branch "$base_branch" "$remote_name/$base_branch"
    else
      die "Base branch not found: $base_branch"
    fi
  fi

  handoff_ref="$(resolve_handoff_ref "$repo_root" "$remote_name" "$handoff_branch")"

  if is_registered_worktree "$repo_root" "$worktree_path"; then
    log "Reusing existing worktree: $worktree_path"
  else
    if [ -e "$worktree_path" ]; then
      die "Path exists but is not a registered worktree: $worktree_path"
    fi
    log "Creating worktree: $worktree_path"
    git -C "$repo_root" worktree add --detach "$worktree_path" "$base_branch"
  fi

  if git -C "$worktree_path" show-ref --verify --quiet "refs/heads/$preview_branch"; then
    git -C "$worktree_path" switch "$preview_branch"
  else
    git -C "$worktree_path" switch -c "$preview_branch"
  fi

  log "Merging $handoff_ref into $preview_branch"
  git -C "$worktree_path" merge --no-ff --no-edit "$handoff_ref"

  frontend_dir="$(detect_frontend_dir "$worktree_path" "$frontend_dir")"

  if [ "$skip_install" -eq 0 ]; then
    ensure_cmd pnpm
    if [ ! -d "$worktree_path/$frontend_dir/node_modules" ]; then
      log "Installing frontend dependencies"
      pnpm -C "$worktree_path/$frontend_dir" install
    else
      log "node_modules already present: skip install"
    fi
  fi

  save_state "$repo_root" "$worktree_path" "$preview_branch" "$handoff_branch" "$base_branch" "$remote_name" "$frontend_dir"

  cat <<EOF
Prepared successfully.
  Worktree: $worktree_path
  Preview branch: $preview_branch
  Handoff branch: $handoff_branch
  Frontend dir: $frontend_dir

Run manual QA:
  pnpm -C "$worktree_path/$frontend_dir" dev

After QA passes:
  scripts/worktree_release.sh promote --repo-root "$repo_root"
EOF
}

cmd_verify() {
  local repo_root_opt=""
  local worktree_path=""
  local frontend_dir=""
  local base_branch="main"
  local remote_name="origin"
  local repo_root

  while [ $# -gt 0 ]; do
    case "$1" in
      --repo-root) [ $# -ge 2 ] || die "Missing value for --repo-root"; repo_root_opt="$2"; shift 2 ;;
      --worktree) [ $# -ge 2 ] || die "Missing value for --worktree"; worktree_path="$2"; shift 2 ;;
      --frontend) [ $# -ge 2 ] || die "Missing value for --frontend"; frontend_dir="$2"; shift 2 ;;
      --base) [ $# -ge 2 ] || die "Missing value for --base"; base_branch="$2"; shift 2 ;;
      --remote) [ $# -ge 2 ] || die "Missing value for --remote"; remote_name="$2"; shift 2 ;;
      -h|--help) usage; exit 0 ;;
      *) die "Unknown option for verify: $1" ;;
    esac
  done

  repo_root="$(detect_repo_root "$repo_root_opt")"
  load_state "$repo_root"

  worktree_path="${worktree_path:-${WORKTREE_PATH:-/tmp/ats-merge-check}}"
  frontend_dir="${frontend_dir:-${FRONTEND_DIR:-}}"
  base_branch="${BASE_BRANCH:-$base_branch}"
  remote_name="${REMOTE_NAME:-$remote_name}"
  worktree_path="$(canonical_path "$worktree_path")"
  frontend_dir="$(detect_frontend_dir "$worktree_path" "$frontend_dir")"

  run_frontend_verify "$worktree_path" "$frontend_dir"
  save_state "$repo_root" "$worktree_path" "${PREVIEW_BRANCH:-}" "${HANDOFF_BRANCH:-}" "$base_branch" "$remote_name" "$frontend_dir"
  log "Verification passed."
}

cmd_promote() {
  local repo_root_opt=""
  local worktree_path=""
  local frontend_dir=""
  local base_branch="main"
  local remote_name="origin"
  local skip_verify=0
  local repo_root generated_file current_branch

  while [ $# -gt 0 ]; do
    case "$1" in
      --repo-root) [ $# -ge 2 ] || die "Missing value for --repo-root"; repo_root_opt="$2"; shift 2 ;;
      --worktree) [ $# -ge 2 ] || die "Missing value for --worktree"; worktree_path="$2"; shift 2 ;;
      --frontend) [ $# -ge 2 ] || die "Missing value for --frontend"; frontend_dir="$2"; shift 2 ;;
      --base) [ $# -ge 2 ] || die "Missing value for --base"; base_branch="$2"; shift 2 ;;
      --remote) [ $# -ge 2 ] || die "Missing value for --remote"; remote_name="$2"; shift 2 ;;
      --skip-verify) skip_verify=1; shift ;;
      -h|--help) usage; exit 0 ;;
      *) die "Unknown option for promote: $1" ;;
    esac
  done

  repo_root="$(detect_repo_root "$repo_root_opt")"
  load_state "$repo_root"

  worktree_path="${worktree_path:-${WORKTREE_PATH:-/tmp/ats-merge-check}}"
  frontend_dir="${frontend_dir:-${FRONTEND_DIR:-}}"
  base_branch="${BASE_BRANCH:-$base_branch}"
  remote_name="${REMOTE_NAME:-$remote_name}"
  worktree_path="$(canonical_path "$worktree_path")"
  frontend_dir="$(detect_frontend_dir "$worktree_path" "$frontend_dir")"

  if [ "$skip_verify" -eq 0 ]; then
    run_frontend_verify "$worktree_path" "$frontend_dir"
  fi

  generated_file="$frontend_dir/tsconfig.tsbuildinfo"
  if git -C "$worktree_path" status --porcelain -- "$generated_file" | grep -q .; then
    log "Restoring generated file: $generated_file"
    git -C "$worktree_path" restore -- "$generated_file"
  fi

  if git -C "$worktree_path" status --porcelain | grep -q .; then
    git -C "$worktree_path" status --short
    die "Worktree is dirty. Commit/stash/revert changes before promote."
  fi

  log "Fetching $remote_name"
  git -C "$worktree_path" fetch "$remote_name" --prune

  log "Diff: $remote_name/$base_branch...HEAD"
  git -C "$worktree_path" log --oneline --left-right "$remote_name/$base_branch...HEAD" || true

  log "Pushing HEAD -> $remote_name/$base_branch"
  if git -C "$worktree_path" push "$remote_name" "HEAD:$base_branch"; then
    log "Promote completed."
  else
    current_branch="$(git -C "$worktree_path" branch --show-current || true)"
    warn "Push to $base_branch failed. Likely branch protection."
    if [ -n "$current_branch" ]; then
      warn "Fallback:"
      warn "  git -C \"$worktree_path\" push -u \"$remote_name\" \"$current_branch\""
      warn "  Then create PR: $current_branch -> $base_branch"
    fi
    exit 1
  fi

  save_state "$repo_root" "$worktree_path" "${PREVIEW_BRANCH:-}" "${HANDOFF_BRANCH:-}" "$base_branch" "$remote_name" "$frontend_dir"
}

cmd_cleanup() {
  local repo_root_opt=""
  local worktree_path=""
  local preview_branch=""
  local handoff_branch=""
  local base_branch="main"
  local remote_name="origin"
  local frontend_dir=""
  local delete_handoff_local=0
  local delete_handoff_remote=0
  local keep_state=0
  local repo_root state_file

  while [ $# -gt 0 ]; do
    case "$1" in
      --repo-root) [ $# -ge 2 ] || die "Missing value for --repo-root"; repo_root_opt="$2"; shift 2 ;;
      --worktree) [ $# -ge 2 ] || die "Missing value for --worktree"; worktree_path="$2"; shift 2 ;;
      --preview) [ $# -ge 2 ] || die "Missing value for --preview"; preview_branch="$2"; shift 2 ;;
      --handoff) [ $# -ge 2 ] || die "Missing value for --handoff"; handoff_branch="$2"; shift 2 ;;
      --frontend) [ $# -ge 2 ] || die "Missing value for --frontend"; frontend_dir="$2"; shift 2 ;;
      --base) [ $# -ge 2 ] || die "Missing value for --base"; base_branch="$2"; shift 2 ;;
      --remote) [ $# -ge 2 ] || die "Missing value for --remote"; remote_name="$2"; shift 2 ;;
      --delete-handoff-local) delete_handoff_local=1; shift ;;
      --delete-handoff-remote) delete_handoff_remote=1; shift ;;
      --keep-state) keep_state=1; shift ;;
      -h|--help) usage; exit 0 ;;
      *) die "Unknown option for cleanup: $1" ;;
    esac
  done

  repo_root="$(detect_repo_root "$repo_root_opt")"
  load_state "$repo_root"

  worktree_path="${worktree_path:-${WORKTREE_PATH:-}}"
  preview_branch="${preview_branch:-${PREVIEW_BRANCH:-}}"
  handoff_branch="${handoff_branch:-${HANDOFF_BRANCH:-}}"
  base_branch="${BASE_BRANCH:-$base_branch}"
  remote_name="${REMOTE_NAME:-$remote_name}"
  frontend_dir="${FRONTEND_DIR:-$frontend_dir}"

  if [ -n "$worktree_path" ]; then
    worktree_path="$(canonical_path "$worktree_path")"
    if is_registered_worktree "$repo_root" "$worktree_path"; then
      log "Removing worktree: $worktree_path"
      git -C "$repo_root" worktree remove --force "$worktree_path"
    else
      warn "Worktree not registered, skip remove: $worktree_path"
    fi
  fi

  if [ -n "$preview_branch" ] && git -C "$repo_root" show-ref --verify --quiet "refs/heads/$preview_branch"; then
    log "Deleting local preview branch: $preview_branch"
    git -C "$repo_root" branch -D "$preview_branch"
  fi

  if [ "$delete_handoff_local" -eq 1 ] && [ -n "$handoff_branch" ] && git -C "$repo_root" show-ref --verify --quiet "refs/heads/$handoff_branch"; then
    log "Deleting local handoff branch: $handoff_branch"
    git -C "$repo_root" branch -D "$handoff_branch"
  fi

  if [ "$delete_handoff_remote" -eq 1 ] && [ -n "$handoff_branch" ]; then
    log "Deleting remote handoff branch: $remote_name/$handoff_branch"
    git -C "$repo_root" push "$remote_name" --delete "$handoff_branch"
  fi

  git -C "$repo_root" worktree prune

  if [ "$keep_state" -eq 0 ]; then
    state_file="$(state_file_path "$repo_root")"
    [ -f "$state_file" ] && rm -f "$state_file"
  fi

  log "Cleanup completed."
}

cmd_status() {
  local repo_root_opt=""
  local repo_root state_file

  while [ $# -gt 0 ]; do
    case "$1" in
      --repo-root) [ $# -ge 2 ] || die "Missing value for --repo-root"; repo_root_opt="$2"; shift 2 ;;
      -h|--help) usage; exit 0 ;;
      *) die "Unknown option for status: $1" ;;
    esac
  done

  repo_root="$(detect_repo_root "$repo_root_opt")"
  state_file="$(state_file_path "$repo_root")"
  load_state "$repo_root"

  cat <<EOF
Repo root: $repo_root
State file: $state_file
WORKTREE_PATH: ${WORKTREE_PATH:-<empty>}
PREVIEW_BRANCH: ${PREVIEW_BRANCH:-<empty>}
HANDOFF_BRANCH: ${HANDOFF_BRANCH:-<empty>}
BASE_BRANCH: ${BASE_BRANCH:-<empty>}
REMOTE_NAME: ${REMOTE_NAME:-<empty>}
FRONTEND_DIR: ${FRONTEND_DIR:-<empty>}
EOF
}

main() {
  ensure_cmd git

  local cmd="${1:-}"
  shift || true

  case "$cmd" in
    prepare) cmd_prepare "$@" ;;
    verify) cmd_verify "$@" ;;
    promote) cmd_promote "$@" ;;
    cleanup) cmd_cleanup "$@" ;;
    status) cmd_status "$@" ;;
    -h|--help|help|"") usage ;;
    *) die "Unknown command: $cmd" ;;
  esac
}

main "$@"
