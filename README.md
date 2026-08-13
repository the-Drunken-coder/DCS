# DCS

Drunken Coding Skills: a deliberately small, personal library of the Codex skills I actually use.

The repository root is a skill-only Codex plugin. It starts with no skills; future skills belong in `skills/`.

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
```

To test the checkout directly, replace only the DCS marketplace with the local repository and reinstall:

```bash
codex plugin remove dcs@dcs
codex plugin marketplace remove dcs
codex plugin marketplace add "$PWD"
python3 ~/.codex/skills/.system/plugin-creator/scripts/update_plugin_cachebuster.py .
codex plugin add dcs@dcs
```
