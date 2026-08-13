# DCS project guidance

- Keep the first version extremely small and easy to understand.
- Build one skill-only Codex plugin named `dcs` at the repository root.
- Add one repository marketplace file that exposes that plugin.
- Keep the maintainer-owned `file-pr`, `babysit-pr`, and `ask-opus` skills.
- Add third-party skills only when the user explicitly requests them and register them in `upstreams.json`.
- Treat registered third-party skill directories as generated output. Update them with `tools/sync_upstreams.py`, not by hand.
- Keep Codex compatibility changes under `ports/`; adapters must fail loudly when upstream assumptions stop matching.
- Keep upstream synchronization deterministic, reviewable, and free of external AI services or secrets.
- Nightly automation may detect drift and fail. It must never modify `main` or merge an upstream update automatically.
- Keep the registry, synchronizer, and workflow small. Source-tree hashes and narrow compatibility overlays exist only for adapted upstreams; `managedSkills` only records which generated directories synchronization owns. Do not grow this into a package manager.
- Use the built-in `plugin-creator` skill and its validation tooling.
- Document the exact commands for adding this GitHub repository as a Codex marketplace and installing DCS.
- Keep changes on `main` unless the user asks for a branch or pull request.
