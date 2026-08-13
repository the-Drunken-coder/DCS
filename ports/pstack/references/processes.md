# Pstack processes

Choose one primary playbook. Add another only when the task genuinely changes phase, such as diagnosis followed by an explicitly requested fix.

## Contents

- [Common spine](#common-spine)
- [Select a playbook](#select-a-playbook)
- [Investigation](#investigation)
- [Bug fix](#bug-fix)
- [Performance and runtime forensics](#performance-and-runtime-forensics)
- [Feature and architecture](#feature-and-architecture)
- [Refactor and migration](#refactor-and-migration)
- [Prototype and visual decision](#prototype-and-visual-decision)
- [Code review](#code-review)
- [Long autonomous run](#long-autonomous-run)

## Common spine

Every playbook uses this evidence chain:

1. **Frame.** State the authorized scope, intended outcome, constraints, and the evidence that will count as done.
2. **Ground.** Inspect repository instructions, live state, affected callers, types, data flow, boundaries, and existing verification paths.
3. **Choose.** Select relevant principles and the smallest coherent approach. Compare alternatives only where the decision is actually open.
4. **Bracket.** Capture a baseline before changing anything whose behavior, performance, or shape must be preserved or improved.
5. **Execute.** Work in small units. Each unit changes one thing and ends in a check.
6. **Prove.** Exercise the same real surface and compare it with the baseline. Inspect the final diff and artifacts directly.
7. **Judge.** Look for root-cause misses, structural friction, scope drift, and simpler shapes. Revert changes that evidence does not justify.
8. **Report.** Lead with the outcome, then evidence, tradeoffs, selected principle-driven decisions, and uncertainty.

Scale the ceremony to risk. A one-file obvious change may compress these into a few actions. Never omit the baseline or real proof when the claim depends on them.

## Select a playbook

| Request | Primary playbook | Deliverable |
| --- | --- | --- |
| How, why, should, are we sure | Investigation | Evidence-backed answer, no edits |
| Broken behavior | Bug fix | Reproduction, root cause, narrow fix, same-surface proof |
| Slow, leaking, spinning, trace analysis | Performance and runtime forensics | Baseline, attributed mechanism, measured treatment or diagnosis |
| New behavior or architecture | Feature and architecture | Consumer-first shape, implementation, real feature proof |
| Behavior-preserving cleanup or API migration | Refactor and migration | Pinned contract, simpler target shape, equivalence proof |
| UI direction or empirical fork | Prototype and visual decision | Throwaway alternatives and a recommendation |
| Review, challenge, stress test | Code review | Calibrated findings, no edits unless separately requested |
| Run until a checkable outcome | Long autonomous run | Iteration trail and final predicate state |

## Investigation

Use for read-only questions and recommendations.

1. Restate the question as a falsifiable claim or decision.
2. Trace entry points, types, callers, state ownership, and the input-to-output path. For motivation, inspect history, issues, docs, and other available records.
3. Separate observed facts, supported inferences, competing explanations, and unknowns.
4. For a decision, compare only viable alternatives against explicit constraints. Give your judgment rather than a neutral list.
5. Stop after the answer. Do not edit files, build speculative code, or open a PR.

Report where the behavior lives, how it works, why the evidence supports the answer, gotchas, and what remains unknown.

## Bug fix

1. Reproduce the failure on the matching runtime surface. Record the failing behavior or output.
2. Build a small set of hypotheses. Use call-path tracing, state inspection, history, and instrumentation to eliminate them. Confirm the surviving mechanism before designing the fix.
3. Identify the violated invariant and the layer that owns it. Resist guards or retries that merely hide the failure.
4. Add a focused failing test first when a cheap, stable local test path already exists. Otherwise use the closest executable reproduction and state why a new test would be weak or expensive.
5. Apply the smallest root-cause change. Search for the same pattern within scope.
6. Run the original reproduction on the same surface and nearby validation. Preserve failing-before and passing-after evidence.

Report what broke, the root cause, the fix, and the before-and-after proof.

## Performance and runtime forensics

For diagnosis-only requests, stop after attribution. Do not turn a question into a fix.

1. Capture the real baseline: a profile, trace, heap snapshot, latency distribution, allocation count, frame time, or other named metric.
2. Convert large artifacts into a queryable shape when useful. Reduce them to the dominant cost, hot call path, retainer chain, or blocked thread.
3. Form hypotheses from the evidence. Consider deleting work, changing the data structure, reducing input, caching with explicit invalidation, batching fixed overhead, deferring unused work, or moving work away from the interactive path.
4. Prove the mechanism with instrumentation or a controlled treatment before making a broad change.
5. Change one dominant cause at a time. Capture the post-change artifact under the same conditions.
6. Compare the numbers and preserve the artifact paths. Mark mismatched or noisy measurements inconclusive.

Report baseline, treatment, delta, attribution, and confidence.

## Feature and architecture

1. Ground the current subsystem and the consumer's actual workflow.
2. Write the caller's usage first. Name the inputs, outputs, domain types, invariants, state ownership, boundaries, and dominant access patterns.
3. If the shape is novel or contested, sketch two or three structurally different options. Screen for shallow modules, information leakage, temporal decomposition, pass-through layers, and shared mutable state.
4. Choose the shape with the smallest public surface that hides the right complexity. Record the accepted tradeoff and at least one rejected alternative when alternatives were real.
5. Implement in dependency order. Keep business rules in the canonical domain layer, parse at boundaries, and derive rather than synchronize.
6. Exercise the real feature from input to output, including an important failure path. Run focused static and test validation as support.
7. If implementation repeatedly needs the same cast, optional escape hatch, special branch, or hidden rule, stop and redesign. Do not keep bolting onto the wrong sketch.

Report the consumer impact, chosen shape, tradeoffs, implementation, and real proof.

## Refactor and migration

1. Pin current behavior with a characterization test, snapshot, recorded output, or equivalence harness. Type checking alone is not a behavior contract.
2. Name the missing or wrong structure and the target shape. The reshape must remove branches, invalid states, duplicated decisions, or reader load.
3. Subtract first. Delete dead paths, one-caller wrappers, redundant validation, and obsolete references.
4. Move in small green steps. When no external compatibility promise exists, migrate all callers and delete the old API in the same wave.
5. Compare old and new behavior on the real artifact or through a deterministic equivalence check.
6. Measure the reader-load change: fewer layers, less hidden state, fewer duplicated rules, or a smaller surface. Revert a refactor that only rearranges complexity.

Report the pinned contract, target shape, subtraction, equivalence proof, and reader-load reduction. Keep behavior changes out of the refactor.

## Prototype and visual decision

1. Name the decision the prototype must settle. If there is no decision, use the feature playbook.
2. Follow any repository rule that requires static mocks or user selection before production changes.
3. Build the smallest throwaway artifact in an isolated scratch location. Do not begin in production components.
4. When the direction is open, create two or three distinct variants behind one comparison surface.
5. Drive or render each variant on the matching surface. Capture screenshots, output, timing, or interaction evidence.
6. Present tradeoffs and a recommendation, then stop for the user's selection when the choice is a product preference.

State that the artifact is throwaway. Implement the chosen direction only in a later feature phase with authorization.

## Code review

Review is read-only unless the user also asks for fixes.

1. State the intended behavior and review scope. Inspect the full diff plus enough surrounding callers, types, tests, and history to judge it.
2. Apply the quality dimensions in [principles.md](principles.md): correctness, root cause, domain fit, boundaries, types, reader load, complexity, state safety, and verification.
3. Trace every suspected bug to a reachable path. Search for a structural simplification, but reject abstraction that has no current second use or concrete payoff.
4. Prefer a few high-conviction findings. Classify each as `act on`, `consider`, `noted`, or `dismissed` and explain the judgment.
5. If independent reviewers are useful, give each the same intent and evidence. Use agreement as a confidence signal, then inspect every finding yourself.

Report actionable findings first. Include dismissed high-salience claims so the user can see how noise was filtered.

## Long autonomous run

Use only when the user explicitly asks to continue until an outcome.

1. Define a checkable exit predicate before the first iteration.
2. Pick the least noisy event or interval that can reveal progress.
3. Each iteration makes the smallest evidence-backed change, checks the predicate, keeps advances, and discards failed hypotheses.
4. Keep a compact checkpoint with the iteration, evidence, decision, and predicate movement so another session can resume without reconstruction.
5. Continue until the predicate is met, authority is required, or a genuine dead end is proven. Do not relax the predicate to declare success.

Report the predicate, iterations, retained and discarded changes, final evidence, and any authority gate.
