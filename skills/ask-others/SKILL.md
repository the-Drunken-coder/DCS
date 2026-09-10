---
name: ask-others
description: Collect full independent reviews from Opus, Antigravity Flash, and Grok through one Codex coordinator sub-agent. Use when the user asks to ask others, requests these reviewers together, or invokes `$ask-others`.
---

# Ask others

Use one coordinator to invoke the individual review skills and return their full responses unchanged. The parent owns interpretation and fixes.

1. Select [ask-opus](../ask-opus/SKILL.md), [ask-antigravity](../ask-antigravity/SKILL.md), and [ask-grok](../ask-grok/SKILL.md), or the user's requested subset. Resolve all three paths relative to this installed skill. Report a missing skill for that provider while continuing the others.
2. Prepare one neutral request with the user's question, intended behavior, constraints, and exact source scope. Include base/head SHAs and the diff for a branch review. Capture relevant source, tests, untracked files, and known omissions in a fixed snapshot outside the checkout. Place every reviewer-readable input, including the diff, request, and inventory, inside that snapshot. Every input path in the request must point inside it. Exclude secrets, dependencies, generated output, `.git`, and symlinks. Keep suspected findings and other reviews out of the request unless the user asks to evaluate them.
3. Spawn one coordinator with `model: "gpt-5.6-luna"`, `reasoning_effort: "low"`, and `fork_turns: "none"`, unless the user explicitly overrides those settings. Pass only the request, snapshot, selected skill paths, a new artifact directory, any user deadline, and [the coordinator contract](references/coordinator.md). The coordinator owns the artifacts; the snapshot stays unchanged.
4. Leave skill execution and process waiting to that coordinator. Wait through the collaboration tools using the original agent ID. Keep CLI logs out of the parent's context. Continue independent work or wait without repeated status requests, duplicate runs, or unchanged progress messages. Report unavailable delegation or model settings instead of silently substituting them.
5. Read the returned handoff and every completed review in full from its saved file. Account for every requested provider, including failures and partial responses. Check source integrity, provider diagnostics, and coverage gaps before relying on a review. Completion means a response arrived, not that its findings are correct.

The individual skills own model selection, CLI commands, permissions, timeouts, output parsing, and completion checks. Ask Others adds delegation and unchanged artifact handoff. Follow the same provider path used when that skill is invoked directly.

Present the full reviews with provider labels when requested. Keep the parent's assessment separate, verify findings against the current source, and apply fixes only within the user's authorized scope.
