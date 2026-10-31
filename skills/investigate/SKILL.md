---
name: investigate
description: Assess whether supplied code-review findings are real and worth fixing. Use to triage review feedback before changing code.
---

# Investigate

Treat each finding as a claim to verify. Decide whether it is true, then whether fixing it would improve this codebase. Return an assessment; leave code and external systems unchanged.

## 1. Read the context

Read the supplied review in full, the intended change, and the repository instructions. Use the preceding review when that is the clear target. Ask only if the review is missing or ambiguous.

Keep the original comment IDs, assigning IDs when absent. Record the reviewed revision when known, the current checkout, and existing local changes. Establish whether each claim still applies to the current code.

## 2. Verify the claim

Read the implementation, callers, tests, and contracts needed to follow the alleged failure. Try to disprove it. Check whether an upstream guard, invariant, or different caller changes the conclusion.

Run a narrow reproduction when practical, keeping temporary experiments outside the checkout. Distinguish observed behavior from source reasoning. Name missing evidence instead of treating a failed reproduction as proof that nothing is wrong.

Verification is complete when decisive evidence establishes the failure or disproves it. If the next necessary check is unavailable, name it and mark the claim `blocked`. Then judge the impact rather than continuing to collect equivalent evidence.

## 3. Judge the value of a fix

For a real issue, establish who encounters it and how much it matters. Compare the smallest effective repair with leaving the behavior alone. Weigh added complexity, compatibility, and regression risk against the actual impact.

Judge the reviewer's suggested fix separately. An oversized proposal can hide a small repair. A costly repair changes the plan, not the truth or severity of the defect.

Recommend a fix for confirmed security, privacy, or data-loss defects, or surface the unresolved decision explicitly. Repair cost alone does not justify deferring them.

## 4. Report the verdicts

Use one verdict per distinct claim:

- `fix`: Real and worth fixing. Describe the smallest reasonable repair.
- `defer`: Real, but not worth fixing now. Explain the tradeoff and what would change the decision.
- `not an issue`: Disproved or already addressed in the current code. Give the decisive evidence.
- `blocked`: Evidence is insufficient. Name the missing fact or check.

For each verdict, give the comment ID, practical consequence, file and line evidence, and checks performed with their limits. Group duplicate causes while retaining every source ID.

Lead with the verdicts, then a short rationale per distinct cause. Include checks that changed the decision. Expand when a tradeoff or uncertainty needs explanation.

Finish when every supplied claim has a supported verdict or an explicit evidence gap. Return the results in the conversation; problem-report files are optional when requested.
