# DCS project guidance

- Keep the first version extremely small and easy to understand.
- Build one skill-only Codex plugin named `dcs` at the repository root.
- Add one repository marketplace file that exposes that plugin.
- Keep only the maintainer-owned `file-pr`, `babysit-pr`, and `ask-opus` skills for now.
- Do not add another skill unless the user explicitly requests it.
- Do not add an updater, lockfile, source manifest, CLI, package manager, scheduled workflow, overlay system, or test framework.
- Use the built-in `plugin-creator` skill and its validation tooling.
- Document the exact commands for adding this GitHub repository as a Codex marketplace and installing DCS.
- Keep changes on `main` unless the user asks for a branch or pull request.
