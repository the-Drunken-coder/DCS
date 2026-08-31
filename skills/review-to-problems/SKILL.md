---
name: review-to-problems
description: Turn a completed review or supplied finding list into repository-native problem reports, with one subagent investigating each finding and the parent checking every verdict and file. Use only when explicitly invoked.
---

# Review findings into problem reports

Convert alleged issues into checked, short-lived problem reports. Investigate only. Leave product code, tests, configuration, pull requests, and external systems unchanged.

## Freeze the findings

Take findings from the user's current message or the review immediately preceding this invocation. Record a finite list before dispatching workers.

- Preserve each finding's source ID, claim, evidence pointer, and severity when supplied. Otherwise assign stable IDs such as `F01`, `F02`, and `F03`.
- When one source finding contains distinct root causes, give them child IDs such as `F07a` and `F07b`. When several findings share one root cause, retain every source ID on the merged entry.
- Merge only findings that describe the same root cause. Keep distinct failures separate even when they touch the same file.
- Treat suggestions, questions, and unverified concerns as allegations until the investigation confirms an observable problem.
- If no concrete findings are available, ask the user to supply or identify the review. Stop before creating files.

Every frozen finding must finish as `confirmed`, `not confirmed`, `duplicate`, or `blocked`. Use the stable IDs in worker assignments and the final ledger so every source finding remains traceable.

## Discover the repository contract

Before assigning report paths:

1. Confirm the repository root, checkout, branch, and existing dirty state.
2. Read every applicable `AGENTS.md` and the repository documentation that routes temporary problems, bugs, or blockers.
3. Find the active problem-report convention. Prefer, in order:
   - a location the user named;
   - a location named by repository instructions or documentation;
   - a repository template such as `_EXAMPLE_PROBLEM_.md` inside a problems directory.
4. Read the full template, its directory index or README when present, and a small sample of active reports.
5. Extract the required directory, filename rule, fields, severity vocabulary, evidence standard, lifecycle, and applicable documentation formatter or checks.

Use the repository's current contract rather than a format remembered from another project. If no contract exists, or several contracts apply and the correct one is ambiguous, ask the user where reports belong. Do not invent a new issue system during this run.

Snapshot existing report files and the initial working-tree status. Match the frozen findings against active reports before dispatch:

- Reuse an existing report only when it describes the same root cause.
- Assign an existing report for evidence refresh when its contract says active reports should stay current.
- Reserve one unique output path per remaining finding using the repository's naming rule. Never overwrite an unrelated file.

## Dispatch one owner per finding

Use the available in-turn subagent mechanism, not separate user-owned threads. Dispatch workers in batches when findings exceed the available child slots. Assign each worker exactly one finding and one report path. Workers must not spawn more agents.

Tell each worker:

- the finding's stable ID and source mapping;
- the repository root and exact checkout state;
- the allegation and its original evidence;
- the report template and assigned output path;
- whether the path is new or an existing matching report;
- the applicable report formatter or check, or that none was found;
- that it owns only that report file and may not edit product code or other reports;
- that it must return its verdict, evidence, commands or tests run, formatting result, and output path.

File ownership is exclusive for the duration of the run. The parent coordinates shared reads and keeps the initial dirty state out of worker diffs.

## Worker investigation gate

Each worker must try to disprove the allegation before accepting it. It should trace the relevant code or documentation, inspect callers and tests, and run the narrowest safe reproduction available. It must distinguish current checkout behavior from a hypothetical risk or stale review comment.

The worker then acts on one verdict:

- `confirmed`: Write or refresh the assigned report in the repository's exact format. State observable expected and actual behavior, precise locations, a repeatable reproduction, and a severity justified by the repository rubric. Use the current timestamp convention. Keep notes factual and useful to the agent that will fix it.
- `not confirmed`: Leave no new report. Return the disconfirming evidence and any limits of the reproduction.
- `duplicate`: Leave the matching report as the single record. Refresh it only when current evidence has drifted and the repository contract calls for updates.
- `blocked`: Leave no new report unless the repository contract explicitly permits blocked investigations. Return the missing evidence or environment boundary.

A strong code path can confirm a deterministic defect when executing it would be unsafe or impractical, but the report must say that the reproduction is a focused test or source trace rather than claiming an execution that did not happen.

For a written report, run the applicable formatter and narrow documentation check on the owned path before returning. If the repository command cannot target one report without touching other files, leave it for the parent and say so.

## Parent review gate

Wait for every worker, then check the artifacts rather than trusting worker summaries.

For every finding:

1. Read the worker's evidence and inspect the cited source, tests, or documentation.
2. Reopen the whole assigned report when one exists.
3. Check the report against every required template field, filename rule, severity definition, and lifecycle rule.
4. Check that expected and actual behavior are distinct, the reproduction can falsify the claim, and the location names the real failure path.
5. Check for duplicates across both old and newly generated reports.
6. Repeat the narrow reproduction when safe, especially for high-severity claims or evidence that rests on an assumption.
7. Compare final working-tree state with the initial snapshot. Only assigned problem reports may have changed because of this run.

Send concrete revision requests back to the owning worker when a report fails the gate. Recheck the revised file. If the parent disproves a newly created report, have its owner remove only that new file and return `not confirmed`. Never delete a report that existed before the run without the user's explicit instruction.

Finish with the repository's narrow documentation checks, including link or path checks when relevant and `git diff --check` for the report changes. Do not commit, push, file issues, or fix the underlying problems.

## Completion

The run is complete only when:

- every frozen finding has one checked verdict;
- every confirmed root cause has exactly one current report;
- every generated or refreshed report passes the repository contract and parent review;
- no unrelated file changed because of the run.

Report a compact ledger with the stable ID, source mapping, finding, verdict, report path when present, and any remaining investigation limit.
