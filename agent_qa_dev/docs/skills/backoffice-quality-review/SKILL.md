---
name: backoffice-quality-review
description: Use when running verification, code review, testing, and release-readiness checks for this backoffice project.
---

# Backoffice Quality Review

## Overview
Run focused QA checks for backend, frontend, and scoring logic before merge or release.

## When to Use
- Reviewing PRs or local changes for regressions
- Running test suites and validation checks
- Checking release readiness after feature work

## Review Priorities
- Behavioral regressions in API contracts and job flow
- Data integrity for run, response, judge, and score outputs
- Missing tests for critical user paths
- Security issues around token/key handling

## Verification Checklist
- Run unit/integration tests for changed areas.
- Verify AQB score calculations on sample fixtures.
- Confirm frontend critical flows: upload, run status, results, export.
- Ensure no secrets are committed or logged.
