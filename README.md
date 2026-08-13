# DCS

Drunken Coding Skills: a deliberately small, personal library of the Codex skills I actually use.

The repository root is a skill-only Codex plugin. It contains three maintainer-owned skills:

- `file-pr` opens a focused pull request for the current branch.
- `babysit-pr` monitors an existing pull request through reviews and CI.
- `ask-opus` gets a second opinion from Opus through `claude -p`.

It also vendors selected public skills:

- `deslop` removes AI-generated code slop. DCS tracks the skill from Cursor's public `cursor/plugins` repository.

Future skills belong in `skills/` and should be added only when they earn their place.

## Upstream skills

[`upstreams.json`](upstreams.json) is the complete administration file for third-party skills. Each entry names a public Git repository, a ref, the source directory, and its destination under `skills/`.

Check for upstream changes without modifying the repository:

```bash
python3 tools/sync_upstreams.py --check
```

Synchronize registered skills locally:

```bash
python3 tools/sync_upstreams.py --sync
```

The `Upstream skills` GitHub Actions workflow runs the check every night. A changed upstream makes the run fail so normal GitHub Actions notifications can alert you. Its manual `sync` operation imports exact upstream directory contents, bumps the DCS patch version, pushes a dedicated update branch, and puts a one-click pull request link in the run summary. It never changes `main` or merges anything.

The workflow uses only the repository's built-in `GITHUB_TOKEN`. It needs no personal access token, AI API key, or other secret.

## Install

Add this repository as a marketplace, then install and enable DCS:

```bash
codex plugin marketplace add the-Drunken-coder/DCS --ref main
codex plugin add dcs@dcs
```

Verify the installation:

```bash
codex plugin list --marketplace dcs
```

## Update

Refresh the marketplace snapshot and reinstall DCS:

```bash
codex plugin marketplace upgrade dcs
codex plugin add dcs@dcs
```

## Disable or remove

To disable DCS without uninstalling it, open DCS in the Codex Plugins Directory and turn it off. The current CLI has no plugin-disable subcommand.

To uninstall DCS while keeping its marketplace configured:

```bash
codex plugin remove dcs@dcs
```

To also remove the marketplace:

```bash
codex plugin marketplace remove dcs
```

## Local development

Clone and validate the plugin:

```bash
git clone https://github.com/the-Drunken-coder/DCS.git
cd DCS
python3 ~/.codex/skills/.system/plugin-creator/scripts/validate_plugin.py .
python3 tools/sync_upstreams.py --validate
```

To test the checkout directly, replace only the DCS marketplace with the local repository and reinstall:

```bash
codex plugin remove dcs@dcs
codex plugin marketplace remove dcs
codex plugin marketplace add "$PWD"
python3 ~/.codex/skills/.system/plugin-creator/scripts/update_plugin_cachebuster.py .
codex plugin add dcs@dcs
```
