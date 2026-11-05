---
name: ui-hillclimb
description: Improve an existing UI through bounded cycles of rendered screenshots, independent model critiques, focused fixes, and workflow checks. Use for UI hill climbing or repeated visual polish; pair with ui-design-judge for read-only scoring.
---

# UI Hill Climb

Own the implementation and the loop. Independent judges own the critique. Optimize the product within the user's chosen direction; scores are a search signal.

Read [run-protocol.md](references/run-protocol.md) to prepare the run, invoke reviewers, and use the scorecard helper. Read [provenance.md](references/provenance.md) when explaining the connection to Theo's experiment or its limitations.

## Establish the run

1. Inspect the app and current instructions. Identify the user task, permitted surfaces, existing design direction, and protected behavior. For a substantial new visual direction, present distinct static alternatives and wait for the user's choice before implementation. Existing approval carries forward through routine polish.
2. Record a private contract in a task-local artifact directory: scope, exact source snapshot, capture recipe, required scenarios, fixed baseline/reference screenshots, rubric, target, reviewers, and stopping limits. Preserve unrelated work. Default to a target of 9/10, at most six implementation rounds, and 90 elapsed minutes unless the user specifies otherwise. Announce these defaults and proceed with authorized work. Honor any explicit money cap; record unknown cost as unknown.
3. Resolve available review models using the harness's live catalog and existing user configuration. Prefer three independent strong models from different providers when available. Keep named models exact. Report unavailable members and obtain the user's choice of a smaller panel or alternative; useful local inspection can continue. A single-model run is a pilot, not multi-model agreement.
4. Render and inspect the baseline. Cover the actual task plus relevant light/dark themes, narrow/wide sizes, long/empty/error/loading states, and keyboard/focus behavior. Select meaningful cases rather than an exhaustive Cartesian product. Use the project's supported capture mechanism. If images cannot be captured or viewed, report the visual-evidence gap and retain a code-only assessment.

The contract is ready when every required scenario has a reproducible capture recipe and the baseline artifacts are frozen. Seal that initial evidence, then start the helper's persisted run state before implementation begins. Reuse it when resuming. Keep the contract private from reviewers because it contains the score target and variant mapping.

## Iterate

For each round:

1. Capture the current rendered app with the same data, viewport, theme, and UI state as the baseline. Record commit plus dirty-diff digest, or an equivalent immutable source snapshot. Seal screenshot and check-log hashes with the helper. Prepare anonymous image copies separately for each reviewer with `review_packet.py`; keep all mappings private.
2. Start fresh read-only review agents using `$ui-design-judge`. Give them the product brief, rubric, screenshots, capture metadata, and output schema. Withhold target score, past scores, round number, other reviews, which variant is new, and the instruction to make this run succeed. Supply actual images or readable paths; a path alone is insufficient if the child cannot view it.
3. Gather independent results before sharing findings. A cheaper pilot reviewer may run between full panels, but only a complete panel on the same capture can meet the target. In T3 Code follow the delegation and wait rules in the run protocol. Reviewers never edit the app or share a mutable output file.
4. Reproduce reported defects and check screenshot evidence. Resolve disagreements against the product task and approved taste. Prioritize functional failures, illegibility, hierarchy, and consistency. Apply a small coherent batch of fixes as the single implementation owner. Do not implement every preference or broaden scope to satisfy a judge.
5. Exercise the real workflow and relevant repo checks. Preserve information density, useful color, affordances, and discoverability where they serve the brief. A cleaner screenshot does not justify hiding necessary actions, faking data, shrinking text, or deleting states. Capture again after every source change.
6. Save raw reviews, restore their canonical labels with the helper, and record evidence, changes, checks, usage, and score history. Evaluate every required reviewer/scenario/category, not an average. Missing reviews, unviewed images, and unverified workflows remain incomplete. Investigate rating drift when unchanged anchors receive materially different scores. Optional direct candidate-versus-best preferences can guide selection. Preserve the earlier best on a tie, and compare the final choice against the fixed baseline.

Stop when the full panel meets the target and checks pass, the budget is exhausted, access is blocked, or two rounds produce no concrete product improvement. Preserve the best verified source snapshot. If keeping an earlier candidate requires changing the checkout, restore only this run's owned changes and verify it again.

## Finish

After the first complete passing panel, obtain a fresh blind confirmation panel on the unchanged final capture within the remaining budget. This is another review pass, not another implementation round. If confirmation falls short, use the remaining limits or report the gap. Any later edit invalidates the capture and its reviews.

Report the final source revision, before/after artifacts, concrete user-visible improvements, checks, per-reviewer scores, remaining disagreements, and why the loop stopped. Distinguish **target met**, **budget stop**, and **blocked/incomplete**. Treat model agreement as model agreement, not user testing or measured accessibility conformance.

Open or merge a PR only when the user authorized that action. This skill authorizes local iteration and read-only delegates within the task; it does not authorize publishing or expanding product scope.
