---
name: thermos
description: "Launch both thermo-nuclear review subagents in parallel, then synthesize their findings. Use for thermos, double thermo review, or combined bug/security and code-quality branch audits."
---

# Thermos

Run two independent review passes as concurrent Codex subagents, then synthesize their results.

## Workflow

1. Use an explicit review scope from the user request as-is. If none is supplied, use the pull request's base branch when reviewing a pull request; otherwise resolve the repository's default branch from `origin/HEAD`. If no base can be resolved, ask the user instead of assuming a branch name.
2. Spawn two subagents concurrently in the same turn:
   - Ask the correctness and security reviewer to load DCS's `thermo-nuclear-review` skill, inspect the scoped diff and related code, and return prioritized findings with file and line evidence.
   - Ask the maintainability reviewer to load DCS's `thermo-nuclear-code-quality-review` skill, inspect the same scope, and return prioritized findings with file and line evidence.
3. Give both agents the same base, ref, and scope. Tell them the task is review-only and that they must not modify files.
4. Let each agent inspect the repository directly. Do not copy large diffs or file contents into their prompts.
5. Wait for both reviewers to finish.
6. Synthesize their results with findings first and deduplicate overlaps. Weight independently reported findings more heavily, resolve disagreements with your own judgment, and keep the summary brief.

If individual background summaries are already visible to the user, do not restate them wholesale. Surface the unified verdict, the highest-signal findings, and any remaining uncertainty.
