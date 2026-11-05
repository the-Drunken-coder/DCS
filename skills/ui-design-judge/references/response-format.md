# Review result

Return one JSON object when the coordinator uses the scorecard helper. Copy the packet ID exactly. Score every supplied variant/scenario/category. Neutral labels are opaque identifiers, not rankings.

```json
{
  "reviewer_id": "reviewer-a",
  "provider": "actual-provider",
  "model": "actual-model-id",
  "packet_id": "sha256-from-packet",
  "scores": {
    "V1": {
      "wide-dark": {
        "hierarchy": {
          "score": 8.2,
          "evidence": "The left rail's repository names compete with the active conversation title."
        }
      }
    }
  },
  "blockers": [],
  "unverified": [],
  "preferences": [],
  "comparisons": [],
  "findings": [
    {
      "variant": "V1",
      "scenario": "wide-dark",
      "kind": "observed",
      "evidence": "Repository labels in the left rail use the same weight as the active title.",
      "impact": "Current task context is harder to scan.",
      "suggestion": "Reduce rail label emphasis while retaining readable text."
    }
  ]
}
```

The example shows one cell for brevity. A real result must include every requested cell. A blocker is an object with `variant`, `scenario`, and `evidence` strings describing a demonstrated material defect. The gate considers candidate blockers; a flawed baseline does not veto the candidate. `unverified` contains strings describing missing evidence and unsupported required judgments. `preferences` lists nonblocking taste judgments. A required image you cannot view needs null scores and an `unverified` explanation. Mention untested interactions there when interaction verification was requested; ordinary still-image scope limitations can be stated in findings without falsely claiming a workflow test occurred.

The coordinator may supply a narrower rubric. Preserve its keys. The coordinator records the delegate task identity separately; an identity field in this JSON alone does not prove independent execution.

For each requested pairwise comparison, add an object to `comparisons` with `left`, `right`, `preferred`, and `evidence`. Use the supplied anonymous labels for both sides. `preferred` is one of those labels, `"tie"` when neither is meaningfully better for the task, or null when evidence is insufficient. Judge the direct choice separately from the numeric ratings. Consider every supplied scenario for the pair and explain the tradeoff. Do not infer a winner from earlier scores or product branding.
