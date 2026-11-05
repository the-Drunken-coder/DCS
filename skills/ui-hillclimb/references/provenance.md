# Origin and adaptations

Source: Theo's [Agents Sucked At UI (Until Today)](https://www.youtube.com/watch?v=xq0eB8vxeqk), published November 3, 2026. This skill is an independent implementation of the workflow, not an official Theo skill.

The demonstrated pattern is screenshot critique by several model providers, implementation changes, fresh reviews, and repeated scoring. At 06:18–08:40 he introduces the council; at 13:42–17:40 he adds competitor references and stages expensive reviewers after a cheaper reviewer; at 18:34–21:10 he escalates the target. His published [T-Stack council skill](https://github.com/t3dotgg/tstack/blob/main/skills/council/SKILL.md) is the related generic review workflow.

Important observations from the video:

- 15:19–16:05: a fresh comparison context changes a previous 9 to 7.4, and unchanged competitor screenshots later score higher.
- 20:03–20:43: Theo identifies target leakage as a possible influence and suggests withholding the target from reviewers.
- 21:16–23:20: runtime and dollar figures are rough account/usage estimates, with an unknown model price proxy. They are not a reproducible budget or incremental bill.
- 23:47–24:50: he explicitly restores color after the score-driven process drifted too far toward grayscale. Human taste remains part of the process.
- 26:48–30:25: he prefers programmatic evaluation when available, using historical MCP failures as a separate example.

This implementation adds neutral labels, withheld targets/history, immutable evidence packets, required scenario/category coverage, real workflow checks, a fresh final confirmation, and bounded execution. Those are engineering adaptations to the observed weaknesses, not claims that Theo used all these controls. It omits the joke extra reviewer and automatic PR creation. Model names in the video are historical examples; select currently available models from the user's environment.

The November 5 comparison also inspected other public implementations. [interface-design's packet builder](https://github.com/3xC1ibR/interface-design/blob/192e8f232b17763117fb053d78581b37c54e4a9a/skills/design-hill-climb/scripts/new_round.py) informed per-reviewer anonymous copies outside the workspace. [Abhay's judging protocol](https://github.com/abhaymettu/hill-climb/blob/79e673c83c7696970b79ab4b22112cb0213763b8/skills/hill-climb/references/judging.md) informed optional direct candidate-versus-best preferences. The DCS helpers are independently implemented with the Python standard library. DCS retains complete-panel, immutable-anchor, workflow-gate, budget, and confirmation requirements instead of importing either alternative's acceptance policy.
