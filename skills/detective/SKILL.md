---
name: detective
description: Investigate review comments in parallel, with a fresh subagent per comment. Use for independent per-comment triage or to investigate and fix supplied review feedback.
---

# Detective

Give each comment an independent investigation. Workers use [Investigate](../investigate/SKILL.md); the parent checks their conclusions and owns any fixes.

## 1. Pin the review

Read the review and repository instructions. Freeze the comment list with original IDs, assigning IDs when absent. Record the reviewed revision when known, current checkout, and existing local changes. Ask only if the review is missing or ambiguous.

## 2. Dispatch fresh workers

Start one subagent per comment with no inherited conversation history. Run them concurrently, in batches when slots are limited. Give each worker:

- Its comment, original evidence, and relevant review context.
- The change's intended behavior and constraints, without the parent's verdict or another worker's conclusions.
- The repository path, checkout state, and resolved path to Investigate.
- The instruction to read Investigate, assess only its assigned comment, and return the verdict and evidence. Workers leave source unchanged and spawn no further agents.

Keep scratch work separate per worker. Each comment gets its own worker even when two appear related. Group shared causes after the results return.

Wait for all workers before editing code. Report failed or unavailable workers as gaps; a parent's own assessment is not an independent investigation.

## 3. Check the conclusions

Read every result and inspect its decisive source evidence. Repeat a narrow check when the conclusion depends on an unverified assumption. Reconcile disagreements and shared causes while retaining every original comment ID.

If the checkout changed, recheck affected conclusions. For a material disagreement, request at most one fresh targeted investigation per comment. If it remains unresolved, report `blocked` with the missing evidence.

## 4. Return the assessment

Account for every comment using Investigate's verdicts. Give the evidence, practical impact, recommended action, and any coverage gaps. Return the assessment in the conversation; problem-report files are optional when requested.

## When fixes were requested

After all investigations finish, apply accepted `fix` findings. Recheck the current code, repair shared causes once, and sequence overlapping edits. Preserve existing local changes and run focused checks of the repaired behavior.

Report the changes and unresolved findings. Commits, pushes, and external replies require authorization from the user's request.
