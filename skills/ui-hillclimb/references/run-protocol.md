# Run protocol

## Files and capture

Keep one private run contract and append a new directory for each capture. The coordinator is the only writer to app files and the run ledger. Each reviewer has a separate result artifact. Store the start time, user authorization, scope, source snapshot, capture recipes, chosen models, delegated task IDs, checks, and stop reason in the ledger. Resume from those artifacts and verify source/capture freshness rather than restarting or discarding failures.

For Git, identify the source as commit SHA plus a digest of the tracked diff and relevant untracked source files. Include all files that affect the rendered app. The helper binds that identifier to evidence but cannot prove that the running app corresponds to it. Verify the app's build/reload state yourself. Use the same fixtures and capture conditions across variants; preserve fixed baseline/reference files.

Use the project's installed capture runner or host browser tools. Record viewport, pixel ratio, theme, route, fixture data, and the actions needed to reach each state. Wait for fonts and actual content readiness. Keep animation and clock conditions stable when they affect the capture. Reuse local authentication state when required without putting it in reviewer packets. This skill does not install a browser or replace the project's capture system.

A private `contract.json` can look like this. Replace model identifiers using the live catalog; example names are not model selections:

```json
{
  "candidate": "V1",
  "variants": {
    "V1": ["wide-dark", "narrow-light"],
    "V2": ["wide-dark", "narrow-light"],
    "V3": ["wide-dark"]
  },
  "categories": ["hierarchy", "typography", "density", "color_contrast", "consistency", "affordance"],
  "target_score": 9,
  "reviewers": [
    {"id": "judge-a", "provider": "provider-a", "model": "catalog-model-a"},
    {"id": "judge-b", "provider": "provider-b", "model": "catalog-model-b"},
    {"id": "judge-c", "provider": "provider-c", "model": "catalog-model-c"}
  ],
  "checks": ["core-workflow", "repo-checks"],
  "fixed_variants": ["V2", "V3"],
  "prefer_over": [],
  "must_beat": [],
  "max_rounds": 6,
  "max_minutes": 90,
  "max_spend_usd": null
}
```

Privately map V1 to the candidate, V2 to the unchanged baseline, and V3 to an optional comparable product reference. Labels should be neutral; filenames, overlays, and a `before/after` annotation can reveal the answer. Keep original images for judging and create annotated comparisons separately for the user. Reference scenario coverage may differ, but only compare matching tasks/states. Populate `must_beat` with reference labels only when the user wants that objective; it enforces a strictly higher candidate score in every matching category/scenario. The default improves the app against its own brief without requiring a competitor win.

By default every noncandidate variant is fixed for the entire run. `fixed_variants` can explicitly select the unchanged baseline and product references when another variant represents the evolving best candidate. Keep the baseline in that list. The helper stores image-content hashes at run start and rejects a changed anchor even if it was resealed into a new packet.

For a pairwise objective, set `prefer_over` to the comparison labels. Each reviewer must return a direct preference with evidence, and a strict majority must prefer the candidate for each requested pair. A tie retains the earlier best. Scores still need to meet the declared target. An evolving-best comparison can guide which source snapshot to keep between rounds. Keep the fixed baseline in the final comparison so a sequence of local preferences does not hide drift. This option is separate from `must_beat`, which compares numeric category scores.

For `capture-spec.json`, supply paths relative to that file, or absolute paths:

```json
{
  "revision": "commit-sha + source-digest",
  "images": {
    "V1": {"wide-dark": "candidate-wide.png", "narrow-light": "candidate-narrow.png"},
    "V2": {"wide-dark": "baseline-wide.png", "narrow-light": "baseline-narrow.png"},
    "V3": {"wide-dark": "reference-wide.png"}
  },
  "checks": {
    "core-workflow": {"passed": true, "path": "workflow.log"},
    "repo-checks": {"passed": true, "path": "checks.log"}
  }
}
```

Run the bundled helper from the installed skill directory:

```bash
python3 scripts/scorecard.py seal /absolute/capture-spec.json /absolute/packet.json
```

It hashes every image and check log and refuses to overwrite a packet. Seal the initial baseline evidence before implementation, then start the persisted run:

```bash
python3 scripts/scorecard.py start /absolute/contract.json /absolute/run-state.json --packet /absolute/initial-packet.json
```

The initial packet uses the same shape as subsequent captures. The helper freezes the contract and comparison image hashes and starts the elapsed clock. Resume with the same state file. It rejects contract changes, reset totals, reused review task IDs, and confirmation without a preceding passing full panel. Keep the state after a stop. Begin a new run only when the user's scope or renewed budget authorizes one.

Store capture metadata and source snapshot per variant alongside the private packet. Its `revision` identifies the candidate source. Keep this packet private because it contains original paths and check outcomes.

## Anonymous reviewer copies

Prepare a separate image directory for each reviewer outside the project workspace. Keep its mapping in the private run directory:

```bash
python3 scripts/review_packet.py prepare /absolute/packet.json /tmp/hillclimb-judge-a --map /absolute/run/judge-a-map.json --reviewer judge-a --workspace /absolute/project
```

The helper randomizes variant labels independently per reviewer, uses neutral filenames, normalizes file timestamps, and verifies copied image bytes. Both the reviewer copies and private mapping must be outside the project workspace, with the mapping outside the reviewer directory. The public `packet.json` contains the original packet ID, an opaque mapping commitment, and anonymous image paths, without source filenames, check results, revision, target, or history. A private random nonce prevents guessing the commitment from a small set of label permutations. Pass only the public packet, images, scenario metadata, and brief to its reviewer. Product branding and embedded image metadata can still disclose identity; this reduces anchoring rather than guaranteeing experimental blinding.

After a review, restore the canonical labels before passing its result to the scorecard:

```bash
python3 scripts/review_packet.py unblind /absolute/judge-a-result.json /absolute/run/judge-a-map.json /absolute/run/judge-a-restored.json
```

Unblinding checks reviewer and packet IDs, the public manifest and image hashes, and the committed private label mapping. It rejects a changed or non-bijective mapping. It translates score, blocker, finding, and pairwise labels. Retain the raw review and private mapping as evidence. Output paths must be new; the helper refuses to overwrite them.

## Fresh independent reviewers

Discover the harness's available delegation tools. In T3 Code call `orchestrator_capabilities` before the first `delegate_task`; pass requested model/settings in `target.options` according to the returned schema. Use one new `delegate_task` for each reviewer for each pass. The task must be self-contained because it has no parent history. Follow the returned `next`; do not poll running delegates or repurpose their threads. Cancel delegates no longer needed. Outside T3 Code use native read-only subagents if they support the selected models; otherwise disclose the missing capability. Follow the host's tool rules if names or schemas differ.

Reviewer brief:

```text
Use ui-design-judge at <absolute installed skill path>. Stay read-only; do not delegate.
Product task and intended users: <brief>.
Approved design constraints and protected behaviors: <constraints>.
Packet ID: <exact ID>. Your reviewer ID: <ID>.
Images and scenario metadata: <neutral variants, paths or attached images, viewports/states>.
Rubric categories: <keys and definitions>.
Pairwise comparisons if requested: <unordered pairs of this reviewer's anonymous labels>.
Open all images. Return one JSON review using the skill's response-format reference.
Score every supplied variant/scenario/category independently and cite visible evidence.
Return the result to the coordinator; do not write to shared app or ledger files.
```

Add the model's actual configured identity from its task metadata, and retain both identity and task ID. A reviewer-supplied identity is not independent proof. Judges see neither implementation history nor earlier scores. Instruct them to inspect only the public evidence, even if the host exposes the private directory.

## Gate one pass

Assemble a `review-pass.json` with the restored result objects in `reviews`:

```json
{
  "round": 1,
  "stage": "full",
  "revision": "commit-sha + source-digest",
  "packet_id": "packet-sha256",
  "elapsed_minutes": 24,
  "spend_usd": null,
  "delegate_tasks": {},
  "reviews": []
}
```

`round` counts implementation/capture rounds, starting at one. `stage` is `pilot`, `full`, or `confirmation`. A fresh confirmation review of the same capture uses the same round number and cumulative elapsed time/spend. Populate `delegate_tasks` with each submitted reviewer ID mapped to its actual fresh task ID. Populate `reviews` with the raw result objects following the judge skill's [response format](../../ui-design-judge/references/response-format.md). The sibling skill must be installed beside this one.

```bash
python3 scripts/scorecard.py gate /absolute/contract.json /absolute/packet.json /absolute/review-pass.json --state /absolute/run-state.json
```

Exit 0 means `panel_met` for a full panel or `target_met` for its fresh passing confirmation. Exit 1 means `needs_work` or `budget_stop`; exit 2 means invalid input, changed evidence, or an invalid lifecycle transition. The helper appends valid passes to the state file and keeps its own elapsed clock. Declared totals can increase but cannot decrease. Source changes require a new round. A new round requires a new packet. After one full panel, another full panel needs a changed source snapshot or candidate image bytes, not renamed images or refreshed check logs. The one same-capture exception is the final confirmation after a passing full panel. A stopped run remains stopped.

The coordinator still verifies actual check execution, delegate identities, the unchanged source snapshot, and stable reference calibration. Local state protects against accidental resets, not deliberate file tampering or invented execution claims. A missing reviewer remains missing; earlier scores cannot fill it. A single-model/pilot result never establishes panel agreement.

Costs are cumulative estimates, with the estimation basis recorded. Unknown cost remains null. With an explicit money cap and unknown cost, the helper stops further work under that cap. Before dispatching, reserve capacity for a full confirmation panel. If cost cannot be bounded enough to honor the cap, obtain a feasible budget choice. Review limits apply to elapsed time including delegates, not the sum of their concurrent runtimes. Stop starting new work when a limit is reached; report incomplete validation if the remaining work does not fit.

## Calibration and real checks

Freeze baseline/reference bytes. Compare each judge's ratings for those unchanged anchors across passes. A change around a point or a reversed reference ranking is a reason to inspect calibration, not evidence the candidate improved. Keep the original rubric and concrete findings; a changed target/reference set starts a new evaluation series. Do not request repeated reviews of unchanged evidence merely to harvest a passing score.

Use direct workflow evidence for navigation, primary actions, keyboard/focus order, overflow, empty/error/loading recovery, and responsive behavior that the change can affect. Screenshots support visual review; repository tests and live interaction checks supply different evidence. List which behaviors actually ran and which remain unverified.
