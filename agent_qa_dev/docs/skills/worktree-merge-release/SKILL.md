---
name: worktree-merge-release
description: Use when a user wants to merge a handoff branch in a temporary worktree, run manual QA on the merged preview branch, then execute test/build and promote to main safely.
---

# Worktree Merge Release

## Overview

Standardize "handoff -> preview merge -> QA -> promote -> cleanup" into one repeatable flow.

**Core principle:** Human QA gate first, automated verification/promotion second.

**Announce at start:** "I'm using the worktree-merge-release skill to run the handoff promotion flow."

## Required Script

Use `scripts/worktree_release.sh` for all steps.  
Do not manually improvise git commands unless the script fails.

## Workflow

### 1) Prepare Preview

```bash
scripts/worktree_release.sh prepare --handoff <branch>
```

Expected result:
- Temporary worktree ready
- Preview branch created/switched
- Handoff branch merged with `--no-ff --no-edit`
- Frontend dependency install completed (if needed)

Then ask user to run manual UI QA in that preview worktree.

### 2) Wait for QA Confirmation

Do not push to `main` before explicit user confirmation like:
- "QA 끝"
- "테스트 완료"
- "승격해줘"

### 3) Verify + Promote

```bash
scripts/worktree_release.sh promote
```

This runs:
- `pnpm test`
- `pnpm build`
- clean check (`git status --porcelain` must be empty)
- `git push origin HEAD:main`

If push fails because of branch protection, report fallback:
- push preview branch
- create PR to `main`

### 4) Cleanup

```bash
scripts/worktree_release.sh cleanup --delete-handoff-local
```

Optional remote deletion:

```bash
scripts/worktree_release.sh cleanup --delete-handoff-local --delete-handoff-remote
```

## Safety Rules

- Never promote without explicit QA-complete signal from user.
- Stop immediately if test/build fails; report failure output.
- Stop immediately if merge conflicts occur; report conflicted files.
- Do not force-push.

## Quick Examples

### Standard

```bash
scripts/worktree_release.sh prepare --handoff codex/my-feature
# (user manual QA)
scripts/worktree_release.sh promote
scripts/worktree_release.sh cleanup --delete-handoff-local
```

### Custom Worktree Path

```bash
scripts/worktree_release.sh prepare \
  --handoff codex/my-feature \
  --worktree /tmp/ats-my-feature
```

## Output Contract

After each step, report:
- Worktree path
- Active branch
- Next single command user should run

Keep status concise and command-first.
