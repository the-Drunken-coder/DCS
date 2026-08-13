# Pstack principles and quality rubric

This reference condenses pstack's 21 principles and its architecture and review lenses. Treat the principles as decision tools, not slogans or a compliance checklist.

## Contents

- [How to judge code](#how-to-judge-code)
- [Core principles](#core-principles)
- [Architecture principles](#architecture-principles)
- [Verification principles](#verification-principles)
- [Execution principles](#execution-principles)
- [Review calibration](#review-calibration)

## How to judge code

Good code satisfies the intended behavior with a direct model, clear ownership, earned complexity, and proof. Bad code forces maintainers to carry hidden rules, coordinate duplicated decisions, or trust claims the system could check.

| Dimension | Strong evidence | Warning signs |
| --- | --- | --- |
| Correctness | A traced input-to-output path covers success, failure, boundaries, and retries. | A hypothetical warning with no reachable caller, swallowed errors, stale state, or half-applied updates. |
| Root cause | The change restores the violated invariant at the layer that owns it. | A nil guard, retry, cast, fallback, or comment that silences the symptom. |
| Domain model | Types and structures encode variants, lifecycle, access patterns, and ownership. | Boolean combinations, bags of optional fields, duplicated shape assumptions, or branches spread across files. |
| Boundaries | Raw external data is parsed once into domain values. Internal code trusts those values. | Repeated defensive checks, framework logic mixed with business rules, or wire and storage types leaking through APIs. |
| Type integrity | Invalid states are unrepresentable, matches are exhaustive, and types derive from authoritative schemas. | `any`, unsafe casts, lying guards, duplicated schema types, or optionality used to avoid modeling variants. |
| Reader load | A small interface hides meaningful policy, state is local, and the call path is short. | One-caller wrappers, pass-through layers, broad shallow interfaces, globals, or several files required to answer a local question. |
| Complexity | The implementation is the smallest one that is correct today. | Speculative configuration, unused extension points, dual old and new APIs, dead code, or a framework for a single use. |
| Concurrency | Writers own separate state, or a real shared invariant has structural serialization. | Multiple writers coordinated by instructions, shared files with unrelated fields, or locks added before questioning the shared object. |
| Idempotency | Running twice or resuming after any partial failure converges to the same end state. | Results depend on stale locks, creation order, partial files, or whether a prior run reached a hidden phase. |
| Verification | A repeatable baseline and treatment exercise the real artifact and contract. | Compile-only claims, self-report, cached proxies, test mocks that replace the behavior under test, or a different runtime surface. |

These are causal tests. File size, coverage, branch count, and abstraction count can point to a problem, but they do not prove one.

## Core principles

### Laziness protocol

Borrow a maintainer's fatigue. Prefer deletion, a flat call path, one source of truth, and the smallest diff that solves the real problem. A rich interface can still be simple when it hides substantial policy behind one boundary.

### Foundational thinking

Choose the core data shape before logic. Trace the dominant reads and writes, preserve option value, and build shared foundations only when every later step benefits. Repeated lines are cheaper than a premature abstraction.

### Redesign from first principles

Integrate a new requirement as if it had existed from day one. Read the affected system as a whole, then propagate the resulting contract through types, callers, docs, and examples. Do not bolt a special case onto an obsolete shape.

### Subtract before you add

Remove dead paths, redundant validation, obsolete references, and unused options before building. A simpler base often makes the needed addition smaller and more obvious.

### Minimize reader load

Track two costs: layers a reader must trace and mutable state a reader must remember. Collapse pass-through boundaries, shrink state scope, derive instead of synchronize, and demand that each layer hide more complexity than it introduces.

### Outcome-oriented execution

For a planned rewrite or migration, optimize for the verified target state. Allow scoped and reversible intermediate breakage at explicit phase boundaries rather than adding compatibility code that outlives the migration.

### Experience first

Judge the result from the consumer's seat and the next maintainer's seat. Fewer polished capabilities beat many rough ones. Implementation convenience does not justify a worse product or API.

### Exhaust the design space

For a novel interaction or consequential architecture with no strong precedent, build two or three structurally different sketches and compare them. Skip this for mechanical work, clear bug fixes, and decisions already forced by constraints.

### Build the lever

When repeatability or reviewability matters, create the smallest codemod, script, generator, query, or verification tool that does or proves the work. Prove the lever against one known unit, make it safe to rerun, and keep it only when it earns its maintenance cost.

## Architecture principles

### Model the domain

Replace scattered conditionals with the structure the domain calls for, such as a state machine, discriminated union, registry, reducer, queue, graph, or normalized collection. Do not force an abstraction when boring local code is already clear.

### Boundary discipline

Validate and narrow at CLI, config, network, storage, and framework boundaries. Convert external representations into domain concepts there. Keep the shell thin and mechanical, and keep business logic pure where practical.

### Type-system discipline

Use types as proofs. Construct only valid states, brand semantic primitives when mix-ups are plausible, parse unknown inputs at boundaries, exhaust variants, and derive types from the source schema. Strengthen a type only where a real operation would otherwise be partial.

### Make operations idempotent

Ask what happens on a second run and after a crash at every mutation point. Reconcile stale state, use content equivalence where order is unreliable, and design startup and retry paths to converge.

### Migrate callers, then delete legacy APIs

When no external compatibility contract exists, inventory callers, move them in one coordinated wave, and delete the old internal API and its implementation-detail tests. Time-box any truly necessary adapter.

### Separate before serializing shared state

Give concurrent actors distinct files, keys, branches, or ownership whenever they publish independent facts. Use a single writer, lock, or compare-and-swap only when one shared object is a true invariant.

### Architecture red flags

- A shallow module exposes many controls while hiding little capability.
- Information leakage makes several modules know the same representation, policy, or protocol detail.
- Temporal decomposition splits code into load, validate, transform, and save modules that all repeat the same domain rules.
- A pass-through method forwards the same shape without adding policy, adaptation, or compression.
- Repeated implementation deviations, casts, optional escape hatches, or special cases show that the chosen model is fighting the domain.

One hard edge case does not condemn a design. Repeated friction of the same shape does.

## Verification principles

### Prove it works

Builds and tests are necessary support, not the final claim. Run the real feature path, read the real value, inspect the actual diff, and verify integrations end to end when available. Trust artifacts from delegated work, not summaries.

### Fix root causes

Reproduce first. Form competing hypotheses, instrument when state is unclear, and eliminate explanations with runtime evidence. Fix the contract or invariant that produced the symptom, then search for the same pattern elsewhere in scope.

### Sequence verifiable units

Bracket each unit with a known baseline, one change, and one check. Keep the check green before advancing. Order commits and delivery so a reviewer can replay the argument, such as failing proof before fix or subtraction before reshape.

## Execution principles

### Guard the context window

Read only what the decision needs. Isolate large payloads and keep reduced findings in the lead context. Keep frequently used rules inline and move occasional detail into direct references.

### Never block on the human

Proceed on reversible implementation details when intent is inferable. Ask for genuine product preferences, missing authority, irreversible actions, or ambiguity that a quick experiment cannot answer. Local instructions and explicit user boundaries always win.

### Encode lessons in structure

When a correction recurs, replace memory and prose with the strongest practical mechanism: an unrepresentable state, lint, banned API, canonical helper, runtime check, or script. Keep prose for rules that truly require judgment.

## Review calibration

For a finding to be actionable, it should identify a reachable path or concrete maintenance burden, name the violated contract or cost, and propose a proportionate fix.

Use four buckets:

- `act on` for concrete correctness, security, data-loss, concurrency, or maintainability problems that block the intended result.
- `consider` for a real tradeoff whose fix may cost more than it returns now.
- `noted` for valid low-impact context that does not warrant a change.
- `dismissed` for unreachable hypotheticals, personal preferences, premature abstractions, scope escapes, and claims contradicted by the code.

Independent agreement increases confidence, but never replaces tracing. A single reviewer with a concrete security or correctness path can matter more than several reviewers repeating a style preference. Keep the actionable set small enough to fix and verify.
