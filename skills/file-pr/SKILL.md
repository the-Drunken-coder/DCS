---
name: file-pr
description: Trigger this skill when the user asks to file, open, or create a new pull request. Do NOT use this skill for monitoring or updating an existing PR.
---
# File PR

You are responsible for encoding presentation standards and filing a pull request for the current branch.

## Prerequisites
1. **Check existing:** Check whether a PR for the current branch already exists.
2. **Review diff:** Review the diff against `origin/main` to understand the changes.
3. **Rebase:** Rebase onto `latest main` before opening. Stale branches conflict and burn a review round.

## Filing Rules
- **Real PRs Only:** Open a real PR rather than a draft. Draft PRs do not trigger review bots.
- **Single Concern:** One concern per PR. If you find yourself writing "also" in the description, the PR needs to be split. Address real shortcomings, but avoid scope creep.
- **Titles:** Use conventional commit titles in plain language.
  - *Bad example:* `Update threads`
  - *Good example:* `fix(web): new threads no longer spike CPU`
- **Body:** State the problem in a sentence or two, then explain how you fixed it.
- **Media:** UI changes require before/after images. Motion or timing changes require a short video. (Remind the user to add these if applicable).
- **Attribution:** End the PR description with a brief blurb identifying the AI model and harness that made the changes.
