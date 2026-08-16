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
- Loop until all required CI checks pass and all actionable review feedback on the latest commit is resolved.

## Optional Review Tools
- Use CodeRabbit, Greptile, Codex, and Macroscope when they are already available to the repository. To request a latest-commit review, comment `@coderabbitai review`, `@greptile-apps review`, `@codex review`, or `@macroscope-app review`, respectively.
- Treat these tools as optional enhancements, not readiness gates. Do not install or configure them unless the user asks.
- If a tool is unavailable, unauthorized, unresponsive, or reports a rate, usage, or quota limit, record the reason and continue. Do not block completion or keep polling solely for an optional review tool.

## Handling Checks and Reviews
- **Verify Findings:** Verify every bot finding against the source before changing code. Distinguish real repo failures from infrastructure flakes.
- **False Positives:** If dismissing a false positive, you must provide a written reason. Do not silently ignore it.
- **Reply Formatting:** When replying to and resolving bot or human comments deemed not worth a code change, format your comment exactly as: `[model slug] responding on behalf of Theo`.
- **Obsolete PRs:** If an overriding PR makes the one being babysat obsolete, stop and ask the user before closing it, unless closure was explicitly authorized.
