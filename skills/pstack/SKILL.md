---
name: pstack
description: Apply a rigorous, evidence-first engineering workflow distilled from pstack. Use when the user invokes $pstack or asks for pstack, poteto-mode, a deep engineering pass, root-cause debugging, verified architecture or refactoring, or a strict evidence-backed judgment of good and bad code.
---

# Pstack

Use one Codex-native skill for pstack's useful core: task routing, engineering principles, and proof-driven execution. This is a condensed port of Lauren Tan's pstack from `cursor/plugins`, not a mirror of its Cursor-specific model router, agents, automations, or Graphite workflows.

## Start

1. Read the active repository instructions and inspect live state before reasoning from assumptions.
2. Classify the request as read-only or change-authorized. A question produces an answer, not edits.
3. Open [processes.md](references/processes.md), select the smallest matching playbook, and follow only that playbook plus the common spine.
4. For design, code, debugging, or review, open [principles.md](references/principles.md). Select the principles that materially constrain the task. Do not invoke every principle by rote.
5. State a checkable outcome and the strongest available proof before doing multi-step work.

## Operating contract

- Prefer the smallest coherent change. Delete or flatten before adding structure.
- Ground judgments in actual callers, data flow, runtime behavior, types, history, and tests. Never call code bad because it differs from a preferred style.
- Name the data shape, invariants, state ownership, and system boundaries before writing nontrivial logic.
- Use alternatives only when the decision is genuinely open. Established patterns and mechanical changes do not need a design tournament.
- Reproduce bugs and capture performance baselines before treatment. Verify afterward on the same surface.
- Build a script, codemod, generator, or repeatable check when it makes the work safer to rerun or easier to review. Do not build a framework for a one-line edit.
- Sequence work into units that each end in evidence. Do not defer all verification to the end.
- Treat compilation, self-report, green CI, and code inspection as supporting evidence. They are not substitutes for checking the real artifact when that path is available.
- Preserve useful comments that explain a non-obvious constraint. Remove narration and stale justification, not documentation by reflex.
- Respect the user's authority boundaries. Do not automatically create a PR, merge, deploy, send messages, delete data, or expand scope.
- Use subagents only when parallel breadth, independent verification, or adversarial review materially improves the result. The lead agent owns the final judgment and checks the artifacts.

## How pstack judges code

Judge an implementation on evidence across these dimensions:

1. **Correctness.** Trace a real input-to-output path and the failure paths. A hypothetical edge case is not a finding until a caller can reach it.
2. **Root cause.** Prefer restoring the violated invariant or contract over guards, retries, casts, or comments that hide the symptom.
3. **Domain fit.** Prefer a data structure that represents the domain over scattered booleans, optional-field bags, and repeated branching.
4. **Boundary and type integrity.** Parse untrusted data once at the edge. Keep transport details private. Make invalid internal states hard or impossible to construct.
5. **Reader load.** Count layers to trace and hidden state to remember. A boundary earns its place only when it hides meaningful decisions.
6. **Complexity budget.** Every abstraction, option, compatibility path, and feature branch must pay for itself in current behavior.
7. **State safety.** Give concurrent actors separate ownership when possible. Make retried operations converge after partial runs.
8. **Proof.** Require baseline and treatment evidence against the real behavior. Tests should assert contracts rather than mirror implementation details.

Read the full rubric in [principles.md](references/principles.md). Metrics such as line count, branch count, file size, and test count are clues. None is a verdict by itself.

## Review calibration

For each potential issue:

1. Trace the concrete execution path, caller, or maintenance burden.
2. Name the broken contract, invariant, or measurable cost.
3. Describe the smallest improvement and its tradeoff.
4. Classify it as `act on`, `consider`, `noted`, or `dismissed`.

Dismiss preferences presented as defects, unreachable hypotheticals, abstraction for imagined future callers, and findings that ignore local constraints. Give extra scrutiny to concrete correctness, security, data-loss, and concurrency paths even when only one reviewer finds them.

## Finish

Report the outcome first. Include the evidence, the decisions that changed because of the selected principles, the real verification performed, and any remaining uncertainty. Do not list principle names unless they changed a concrete choice.
