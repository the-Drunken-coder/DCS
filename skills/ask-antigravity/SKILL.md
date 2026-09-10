---
name: ask-antigravity
description: Get a second opinion from Gemini 3.8 Flash High through Antigravity CLI. Use when the user asks for an Antigravity review, asks to consult Flash through Antigravity, or invokes `$ask-antigravity`.
---

# Ask Antigravity

Get an advisory review through `agy` using Gemini 3.8 Flash High.

Prepare a source snapshot outside the working checkout and a prompt containing the user's question, constraints, exact files or diff, and requested file/line findings. Include relevant surrounding source and tests, with an inventory of included files and any known omissions. Put all review inputs, including the diff, request, and inventory, inside the snapshot; every input path in the request must point inside it. Exclude secrets, dependencies, generated output, `.git`, and symlinks; copy required referenced source files explicitly.

Use the [provider runner](scripts/review.py):

```bash
python3 /absolute/path/to/ask-antigravity/scripts/review.py --source /absolute/path/to/snapshot --prompt /absolute/path/to/request.txt --out /absolute/path/to/new-results
```

Resolve the runner relative to this skill and replace the example paths. The output directory must not exist yet; the runner creates it. It uses `gemini-3.8-flash-high` with high effort, a temporary agent limited to `view_file` and `grep_search`, and explicit snapshot access through `--add-dir`. Normal permission checks stay enabled; global CLI settings remain unchanged. This is a static review. Test execution and findings verification belong to the caller.

Follow the original runner process to completion. The default deadline is 900 seconds per provider; honor a user deadline with `--timeout`. Read `status.json`, check `source_unchanged`, and read the full saved review. The runner checks exit status, JSON completion, denied actions, and the requested final marker; `SUCCESS` alone can accompany an empty, permission-blocked response. A failed or incomplete result is unavailable, not approval. Report authentication or model errors without substituting another harness or model.

Verify findings against the current source. Summarize valid findings and explain rejected suggestions. Apply fixes only within the user's authorized scope. When invoked by Ask Others' coordinator, return the artifacts unchanged and leave this assessment to the parent.

See the [Antigravity headless CLI documentation](https://www.antigravity.google/docs/cli/headless/) for authentication and output details.
