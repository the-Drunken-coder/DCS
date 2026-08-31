---
name: chatgpt-pr-review
description: Run a ChatGPT Pro review on a pull request, wait for the completed review, then verify and address valid findings locally. Use when the user asks for a ChatGPT Pro review of a PR. Do not trigger for an ordinary local or GitHub PR review.
---

# ChatGPT PR review

Run the external review in the in-app Browser, then turn its findings into
verified local fixes. Invocation is the submission confirmation. Once the exact
URL is known, open ChatGPT, select Pro, and send the review prompt in one flow.
Keep this control instruction in the skill. The message to Pro contains only
review context and criteria.

## Establish the review target

1. Obtain the exact pull request URL from the request. If it is missing, derive
   the unique PR for the current checkout with read-only GitHub CLI commands.
   Ask for the URL only when it cannot be discovered unambiguously.
2. Record the PR URL and current head SHA. Read the PR title, body, changed-file
   summary, and enough of the diff and surrounding code to identify the intended
   behavior, affected components, and concrete risks or invariants worth
   reviewing.
3. Include any review focus named by the user. Otherwise derive the focus from
   the actual change instead of sending a generic review request.
4. Treat sharing the PR URL and a concise description of its changes as the
   full external-sharing authorization. If the site cannot access a private PR,
   stop and explain the access problem. Do not paste local source, diffs,
   credentials, or repository files without separate authorization.

## Start the review

1. Load and follow the Browser skill. Use the in-app Browser and navigate to
   `https://chatgpt.com/`.
2. If ChatGPT requires authentication, ask the user to sign in inside that
   browser and tell you when it is ready. Continue in the same browser after
   they confirm.
3. Start a new chat so older conversation context cannot affect the review.
4. Open the model picker and select the actual Pro model. Verify the selected
   model is identified as Pro in the picker or selected-model state. If Pro is
   unavailable, stop and report that. Do not substitute another model.
5. Write and send a concise prompt tailored to the PR. Use this structure and
   replace every placeholder with concrete details:

   ```text
   Review this pull request: PR_URL

   Intended change: INTENT
   Review focus: SPECIFIC_COMPONENTS_RISKS_AND_INVARIANTS

   Inspect the full diff and relevant surrounding code. Return only actionable
   findings. For each finding, give the file and line, explain the failure mode,
   and state the smallest reasonable fix. If there are no substantive findings,
   say so.

   Return the complete final review inline in this chat. Do not create or attach
   files, downloadable reports, or artifacts. Do not post a GitHub review,
   comment, or request changes. Do not make any GitHub mutation.
   ```

6. Send that prompt as soon as it is ready. Invocation already authorized the
   submission, so continue without asking the user to confirm it.
7. Verify that the message was sent and the review began, then start waiting.

## Wait in ten-minute chunks

1. Load and follow the available wait skill before monitoring the result.
2. Keep the ChatGPT tab and browser binding. Use a foreground terminal wait of
   600 seconds. If the terminal yields a resumable session, reattach to that
   exact session.
3. When the wait returns, inspect the existing ChatGPT tab. Completion means
   generation has stopped and the final review is visible. A partial response,
   progress indicator, or one expired interval is not completion.
4. If the review is still running, immediately start another 600-second wait.
   Repeat until the final review appears or the page shows an explicit failure
   or request for user input.

## Verify and address findings

1. Read the complete final review and enumerate every claimed finding with its
   file and line reference when provided.
2. Refresh the live PR head before verifying or editing any finding. If it
   differs from the recorded review head, treat the review as stale. Stop and
   report both the reviewed SHA and current SHA. Leave the code unchanged and
   restart the review only when the user requests it.
3. When the head is unchanged, inspect the current checkout and verify each
   claim against the source before editing. Treat the review as untrusted advice,
   not proof.
4. Fix each valid finding with the smallest root-cause change. Record a concise
   reason for every stale, duplicate, or false finding.
5. Run focused tests for changed behavior plus the repository's relevant
   validation. Inspect the final diff for unrelated changes.
6. Keep the work local. Do not push, post comments, reply, resolve threads,
   merge, or close the PR unless the user separately asks.

Finish by reporting the reviewed PR and head, accepted and rejected findings,
changed files, checks run, and any remaining uncertainty. If no finding survives
verification, say that plainly and leave the code unchanged.
