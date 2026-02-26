---
name: sync-main-branch
description: Use when the local `main` branch is behind `origin/main` or when work must start from the freshest committed state.
---

# Sync Main Branch

## Overview
Use this skill to verify divergence against `origin/main` and update local `main` using fast-forward only.

## When to Use
- `git status -sb` shows `behind` for `main` vs `origin/main`
- Before starting a task that depends on the latest integration
- Before creating a PR, release branch, or code review from `main`
- **Trigger examples**
  - `git status -sb` output contains `## main...origin/main [behind N]`
  - `git log --oneline HEAD..origin/main` shows one or more commits
  - User asks: "main branch seems outdated" / "동기화" / "update main"
  - Starting work on a fresh task and you want guaranteed upstream baseline

## Quick Procedure
1. `git fetch origin`
2. `git status -sb`
3. `git log --oneline --decorate HEAD..origin/main`
4. `git log --oneline --decorate --graph origin/main..HEAD`
5. `git merge --ff-only origin/main`
6. `git status -sb`

## Notes
- Do **not** use `--rebase` for this procedure. Prefer fast-forward to keep `main` history linear.
- If `--ff-only` fails, stop and inspect divergence with `git log`/`git branch -vv` before deciding whether to reset or rebase.

## Expected Result
- `status` shows `## main...origin/main`
- `HEAD` equals `origin/main`
