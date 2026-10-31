# Writing Investigate and Detective

These are original DCS skills. This note records the authoring lessons used to
revise them, rather than importing either author's workflow.

## Sources

Reviewed on 2026-10-31. Matt Pocock's installed package is version 1.3.2.
The installed t3-pstack package is version 2.2.0, a T3 adaptation of Lauren Tan's
pstack. The links below distinguish original pstack from that adaptation.

- Matt Pocock's [writing-for-agents](https://github.com/mattpocock/skills/blob/main/skills/productivity/writing-for-agents/SKILL.md) defines context pointers, information hierarchy, completion criteria, and pruning.
- His [code-review](https://github.com/mattpocock/skills/blob/main/skills/engineering/code-review/SKILL.md) separates review responsibilities, pins inputs, gives each worker a brief, and specifies aggregation.
- His [diagnosing-bugs](https://github.com/mattpocock/skills/blob/main/skills/engineering/diagnosing-bugs/SKILL.md) puts an observable completion criterion on reproduction before moving to diagnosis.
- Lauren Tan's [authoring playbook](https://github.com/cursor/plugins/blob/main/pstack/skills/poteto-mode/playbooks/authoring-a-skill.md) keeps instructions that change decisions and delegates to other skills by path.
- Her [Prove It Works](https://github.com/cursor/plugins/blob/main/pstack/skills/principle-prove-it-works/SKILL.md) requires checking the actual artifact rather than relying on a proxy.
- Her [Bugbot triage reference](https://github.com/cursor/plugins/blob/main/pstack/skills/poteto-mode/references/bugbot-triage.md) requires evidence for dismissals and distinguishes low-risk noise from serious defects.

## Lessons applied

### Make the description choose the right task

Matt's context-pointer guidance treats the description as a routing decision.
Investigate now points to assessing supplied feedback. Detective points to fresh
parallel investigations. Their descriptions omit the detailed verdict contract.

### Make the sequence visible

Matt's code-review skill uses numbered stages with one responsibility per stage.
The revised Detective replaces six dense numbered paragraphs with headings for
pinning inputs, dispatching workers, checking conclusions, and returning results.

### Make completion observable

Matt's completion-criteria guidance and debugging skill demand evidence that a
stage is complete. Investigate requires a supported verdict or an explicit gap
for every claim. Detective must account for every original comment, including
workers that could not finish.

### Keep one owner for each rule

Poteto's authoring playbook delegates by path rather than restating instructions.
Investigate owns the verdicts and evidence standard. Detective requires workers
to read it and owns dispatch, reconciliation, and any requested fixes. The reverse
pointer from Investigate to Detective was removed so workers stay on assessment.

### Put optional work after the default outcome

Matt's information-hierarchy guidance separates material needed on every path
from material needed on one branch. Detective's fixes are now a separate final
section. Assessment-only use reaches a clear result without requiring code edits
or a problem-report convention.

### Report decisions with their evidence

Poteto's authoring guidance prunes instructions that do not change behavior.
Investigate keeps the distinction between truth, impact, and repair cost. Its
reporting instructions now request concise rationales and the checks that changed
the decision, rather than an exhaustive investigation diary.

### Bound verification and follow-up

Matt's completion-criteria guidance distinguishes finishing the actual work from
merely producing an output. Poteto's [swarm](https://github.com/cursor/plugins/blob/main/pstack/skills/swarm/SKILL.md)
allows one retry for an incomplete report before recording a gap. The source
review identified two further improvements for DCS: a per-claim verification
stop and a limit on Detective's follow-up investigations. Investigate now stops
once verification is decisive or the next necessary check is unavailable.
Detective allows one targeted follow-up per disputed comment, then reports any
remaining uncertainty.

The two authors do not prescribe one formatting template. Their short principles
and longer diagnostic workflows solve different problems. This revision uses
headings and concise verdict definitions where they expose the decisions; it
does not target a line count or copy T3's provider and model routing into DCS.

## Behavioral checks

The checks use isolated Python repositories with supplied reviews and an existing
local edit. They exercise the skills through fresh delegated agents. They are
bounded exercises, not an accuracy benchmark or evidence of improvement across
models. The delegation service labels the agents as testing agents, so these
runs are not blinded.

The source research and both completed exercises ran on
`claudeAgent/claude-opus-5-5`. An independent assessment review ran on
`grok/grok-4.7`.

The original Investigate draft correctly handled six comments covering a shared
iterator bug, a guarded-input false positive, an unjustified cache, unknown
provider behavior, and a tenant-isolation failure. Source hashes confirmed that
the assessment preserved the repository and its existing local edit. Its lengthy
response motivated the narrower reporting instruction.

The independent reviewer agreed with the substantive verdicts and checked the
reproductions against the source. It noted one imprecise statement in the report:
the iterator bug returns zero for non-empty reports, but all-zero inputs still
happen to have the correct result. That does not change the defect or repair.

The revised Detective handled three comments with a shared cause and a false
positive. The parent independently verified that only the calculation helper
changed, the false-positive path stayed unchanged, and the existing local note
was preserved. Direct calls confirmed that both lists and one-shot iterators now
produce the required average. Activity records contain three distinct worker
results and show the parent reproducing the failure before editing. Each worker's
recorded initial prompt contains only its assigned comment and neutral context;
its tool activity shows that it read Investigate. The workers' activity overlaps
in time, with a separate scratch directory for each.

The final fresh-agent exercise could not run because Claude reached its API rate
limit. A direct check of that fixture confirmed the intended distinction: a guard
after the payment callback still permits the effect before raising, while the
guard before the refund callback prevents it. That check verifies the fixture,
not the skill's ability to reach the right verdict. Stale-review handling and the
new follow-up limit therefore remain unverified behaviorally.

These results support keeping the revised skills as first versions. They establish
the exercised decisions and the successful delegation-and-fix path. They do not
establish broad accuracy, reliable automatic discovery, behavior on large reviews,
or a measured improvement over the original wording.
