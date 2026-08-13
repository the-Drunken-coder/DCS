---
name: babysit-pr
description: Trigger this skill when the user asks to monitor, watch, or babysit an existing pull request, or to handle CI checks, auto-rebasing, and PR review comments.
---
# Babysit PR

You govern the post-merge-prep stage of a pull request. Your job is to monitor the PR, respond to reviews, and ensure it becomes green and ready to merge.

## Loop & Monitor
- Poll for new review comments and CI checks.
- Only act on items **newer than the latest push**. Stay quiet when nothing is new.
- Rebase or pull `main` as needed.
- Loop until the PR is green (all CI checks pass) and all reviewers have approved. Stop when the bots are green on the latest commit.

## Required Reviewers
- Require a latest-commit review from CodeRabbit, Greptile, and Codex on every PR. If one has not run, trigger it with the PR comment `@coderabbitai review`, `@greptileai`, or `@codex review`, respectively.
- If a reviewer is unavailable, unauthorized, unresponsive, or reports a rate, usage, or quota limit, mark that reviewer as skipped and continue with the others.
- Do not finish until every required reviewer has either completed against the latest commit or been skipped with a recorded reason. Name every skipped reviewer and its reason in the final report.

## Handling Checks and Reviews
- **Verify Findings:** Verify every bot finding against the source before changing code. Distinguish real repo failures from infrastructure flakes.
- **False Positives:** If dismissing a false positive, you must provide a written reason. Do not silently ignore it.
- **Reply Formatting:** When replying to and resolving bot or human comments deemed not worth a code change, format your comment exactly as: `[model slug] responding on behalf of Theo`.
- **Obsolete PRs:** If an overriding PR makes the one being babysat obsolete, stop and ask the user before closing it, unless closure was explicitly authorized.
