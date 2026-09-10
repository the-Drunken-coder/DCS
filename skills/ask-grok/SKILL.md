---
name: ask-grok
description: Get a second opinion from Grok 4.6 at xhigh reasoning through Grok CLI. Use when the user asks for a Grok review, asks to consult Grok, or invokes `$ask-grok`.
---

# Ask Grok

Get an advisory review through `grok` using Grok 4.6 at `xhigh`, its highest documented reasoning level.

Prepare a source snapshot outside the working checkout and a prompt containing the user's question, constraints, exact files or diff, and requested file/line findings. Include relevant surrounding source and tests, with an inventory of included files and any known omissions. Put all review inputs, including the diff, request, and inventory, inside the snapshot; every input path in the request must point inside it. Exclude secrets, dependencies, generated output, `.git`, and symlinks; copy required referenced source files explicitly.

Use the [provider runner](scripts/review.py):

```bash
python3 /absolute/path/to/ask-grok/scripts/review.py --source /absolute/path/to/snapshot --prompt /absolute/path/to/request.txt --out /absolute/path/to/new-results
```

Resolve the runner relative to this skill and replace the example paths. The output directory must not exist yet; the runner creates it. It pins `grok-4.6` with `xhigh`, uses `--output-format streaming-json`, and limits tools to `Read,Grep,Glob` with plan permissions and no sub-agents. This is a static review. Test execution and findings verification belong to the caller.

Follow the original runner process to completion. The default deadline is 1800 seconds per provider; honor a user deadline with `--timeout`. Read `status.json`, check `source_unchanged`, and read the full saved review. Completion requires exit zero, a final stream `end` event with `stopReason: end_turn`, no stream errors, and a nonempty response ending with the requested marker. The runner concatenates text deltas unchanged, including any progress prefix the CLI includes. Thoughts and tool payloads stay in the raw log. It never guesses where review text begins. A deadline retains any received text as a partial review.

If the CLI exits with progress only, cuts off mid-response, or hits a stream timeout, retain the raw output and mark it incomplete. Do not turn partial findings into a completed review or restart automatically. Report authentication failures with `grok login` as the next step. Report unsupported `xhigh` or unavailable models without silently substituting settings.

Tool failures are retained in `status.json` as `tool_errors`: a failed lookup can be followed by a successful read and a full review. Inspect those diagnostics and the review's coverage gaps before relying on its findings. A completed response does not establish complete source coverage.

Verify findings against the current source. Summarize valid findings and explain rejected suggestions. Apply fixes only within the user's authorized scope. When invoked by Ask Others' coordinator, return the artifacts unchanged and leave this assessment to the parent.

The [Grok reasoning documentation](https://docs.x.ai/developers/model-capabilities/text/reasoning) lists Grok 4.6's supported effort levels. Other models' CLI options such as `max` do not establish support for Grok 4.6.
