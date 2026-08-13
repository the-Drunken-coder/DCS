# DCS project guidance

- Keep the first version extremely small and easy to understand.
- Build one skill-only Codex plugin named `dcs` at the repository root.
- Add one repository marketplace file that exposes that plugin.
- Keep the maintainer-owned `file-pr`, `babysit-pr`, and `ask-opus` skills.
- Add third-party skills only when the user explicitly requests them and register them in `upstreams.json`.
- Treat registered third-party skill directories as vendored output. Update them with `tools/sync_upstreams.py`, not by hand.
- Keep upstream synchronization deterministic, reviewable, and free of external AI services or secrets.
- Nightly automation may detect drift and fail. It must never modify `main` or merge an upstream update automatically.
- Keep the registry, synchronizer, and workflow small. Do not add a package manager, overlay system, or lockfile unless the simple system stops being sufficient.
- Use the built-in `plugin-creator` skill and its validation tooling.
- Document the exact commands for adding this GitHub repository as a Codex marketplace and installing DCS.
- Keep changes on `main` unless the user asks for a branch or pull request.
