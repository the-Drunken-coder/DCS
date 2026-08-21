# DCS

Drunken Coding Skills: a deliberately small, personal library of the Agent Skills I actually use.

The repository root is a skill-only [Agent Plugins 1.0](https://agent-plugins.org/specification)
package. Its root [`plugin.json`](plugin.json) declares the portable format, and clients discover
skills from `skills/` by convention. There is intentionally no legacy client-specific plugin
manifest.

The package contains four maintainer-owned skills:

- `file-pr` opens a focused pull request for the current branch.
- `babysit-pr` monitors an existing pull request through reviews and CI.
- `ask-opus` gets a second opinion from Opus through `claude -p`.
- `wait` pauses for work that may need more time and checks again when useful.

It also tracks selected public skills:

- `anti-ui-slop` helps agents build product-specific interfaces and check them for generic UI defaults.
- `architecture-map` builds an interactive isometric map from measured repository structure and authored call paths.
- `codebase-design` provides the shared vocabulary and principles for deep-module design.
- `deslop` removes AI-generated code slop. DCS tracks the skill from Cursor's public `cursor/plugins` repository.
- `grill-with-docs` stress-tests a plan or design while sharpening its domain language and recording durable decisions. DCS also packages the `grilling` and `domain-modeling` skills it composes.
- `improve-codebase-architecture` finds architectural deepening opportunities, presents them visually, and grills the selected direction.
- `pstack` provides one explicit, evidence-first engineering workflow distilled from Lauren Tan's pstack principles, quality rubric, and core playbooks.
- `thermo-nuclear-review` performs a strict correctness and security branch audit.
- `thermo-nuclear-code-quality-review` performs a strict maintainability and structure audit.
- `thermos` runs both Thermo-Nuclear reviews concurrently and synthesizes the results.
- `unslop` mirrors P-Stack's writing cleanup skill, removing common AI tells while preserving meaning and intended tone.

Future skills belong in `skills/` and should be added only when they earn their place.

## Upstream skills

[`upstreams.json`](upstreams.json) is the complete administration file for third-party skills. Each entry names a public Git repository, a ref, the source directory, and its destination under `skills/`.

Most skill instructions are exact mirrors. Packaging adds a `DCS:` prefix to every Codex display name so its origin stays visible in skill lists. Adapted skills can also name a small adapter, patch, or file overlay under `ports/`. The `anti-ui-slop` adapter packages the last self-contained skill while upstream references runtime scripts that its source directory does not include. It fails when that upstream assumption changes so the port can be reviewed and removed. The pstack adapter tracks the complete upstream plugin but packages one Codex-native `pstack` skill instead of its Cursor-specific skill stack, agents, model router, and automations. It verifies pstack's identity and main router before packaging the port. The `grill-with-docs` port preserves manual invocation while replacing its generic Skill-tool handoff with Codex instructions. The Thermos ports remove Cursor-only invocation metadata, replace Cursor's subagent syntax with Codex instructions, and add Codex UI metadata. The Matt Pocock skills bundle their upstream MIT notice, while the architecture orchestrator drops a redundant legacy manual-invocation field and loads its bundled dependencies through Codex-native skill instructions. [`upstreams.lock.json`](upstreams.lock.json) records each adapted upstream Git tree, so a change remains visible even when an adapter produces identical packaged output. Its `managedSkills` list tracks every generated skill so removing a registry entry also removes its packaged directory.

Install the synchronizer's YAML dependency once:

```bash
python3 -m pip install -r tools/requirements.txt
```

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

The portable specification leaves installation and distribution to each client. DCS keeps
`.agents/plugins/marketplace.json` only as its Codex distribution index; it is not part of the
plugin package format.

Portable Agent Plugins installation requires Codex 0.147.0 or later. Add this repository as a
marketplace, then install and enable DCS:

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
python3 -m unittest discover -s tests -v
python3 tools/sync_upstreams.py --validate
python3 tools/sync_upstreams.py --check
```

Run the wait skill against an actual OpenCode agent without naming the skill in
the prompt:

```bash
python3 tools/run_wait_skill_trial.py foreground-explicit --duration 20
python3 tools/run_wait_skill_trial.py detached-implicit --duration 20
python3 tools/run_wait_skill_trial.py opaque-underestimate --duration 20
python3 tools/run_wait_skill_trial.py opaque-implicit --duration 20
python3 tools/run_wait_skill_trial.py opaque-buried --duration 20
python3 tools/run_wait_skill_trial.py resumable-terminal --duration 20
```

Run three reliability trials sequentially across the cheap Go model set:

```bash
python3 tools/run_wait_skill_matrix.py --repeat 3 --duration 12
```

Compare isolated discovery descriptions and names without changing the packaged
skill:

```bash
python3 tools/run_wait_skill_variants.py --repeat 2 --duration 12
```

The variant runner also accepts the `static-timeout`, `completed-build-log`, and
`async-code-review` near-miss scenarios for checking unwanted activation.

Pass `--model opencode-go/deepseek-v4-flash` to use the Go subscription model
after enabling its China-hosted models. The default uses OpenCode's free
DeepSeek V4 Flash endpoint.

The repository validator also enforces DCS release policy: a plain Semantic Versioning release,
a non-empty description, and a named author. Those requirements are intentionally stricter than
the minimum portable manifest schema.

To test the checkout directly, replace only the DCS marketplace with the local repository and reinstall:

```bash
codex plugin remove dcs@dcs
codex plugin marketplace remove dcs
codex plugin marketplace add "$PWD"
codex plugin add dcs@dcs
```
