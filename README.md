# DCS

Drunken Coding Skills: a deliberately small, personal library of the Agent Skills I actually use.

The repository root is a skill-only [Agent Plugins 1.0](https://agent-plugins.org/specification)
package. Its root [`plugin.json`](plugin.json) declares the portable format, and clients discover
skills from `skills/` by convention. There is intentionally no legacy client-specific plugin
manifest.

The package contains thirteen maintainer-owned skills:

- `file-pr` opens a focused pull request for the current branch.
- `babysit-pr` monitors an existing pull request through reviews and CI.
- `ask-opus` gets a second opinion from Opus through `claude -p`.
- `ask-antigravity` gets a Gemini 3.8 Flash High review through Antigravity CLI.
- `ask-grok` gets a Grok 4.6 xhigh review through Grok CLI, with a 30-minute default deadline.
- `ask-others` delegates to one GPT-5.6 Luna low coordinator, which invokes those three skills and returns their full reviews unchanged.
- `chatgpt-pr-review` runs an explicit ChatGPT Pro review, waits for its final response, and applies locally verified findings.
- `wait` pauses for work that may need more time and checks again when useful.
- `investigate` checks whether supplied review findings are real and worth fixing, with evidence and explicit deferral decisions.
- `detective` runs Investigate in a fresh subagent per review comment, reconciles results, and applies verified fixes when requested.
- `review-to-problems` investigates review findings with one subagent per issue and writes checked repository-native problem reports.
- `ui-hillclimb` improves an existing UI through bounded screenshot, independent-review, fix, and workflow-check rounds.
- `ui-design-judge` gives read-only visual critiques, scenario scores, and optional direct preferences between anonymous variants.

It also tracks two public skills:

- `anti-ui-slop` helps agents build product-specific interfaces and check them for generic UI defaults.
- `architecture-map` builds an interactive isometric map from measured repository structure and authored call paths.

DCS complements separately installed Matt Pocock and pstack packages. It no longer bundles
their skills or compatibility ports. The former Cursor Team Kit `deslop` import is also
removed because pstack supplies the same instructions.

The CLI review skills require the corresponding `claude`, `agy`, or `grok` CLI installed and signed in. Antigravity and Grok use their own Python runners; Ask Others only delegates to the individual skills. Review inputs stay in a fixed snapshot, and raw responses remain available alongside the unchanged full reviews.

Future skills belong in `skills/` and should be added only when they earn their place.

The UI loop follows Theo's screenshot/council experiment with fixed comparison images, anonymous per-reviewer copies, persisted budgets, and fresh final confirmation. It uses the project's existing capture and browser tools; its helpers require only Python's standard library. Repository tests include a real Chrome/Chromium workflow fixture with synthetic review intake. That test is skipped when no browser is available; set `UI_HILLCLIMB_BROWSER` to its executable path when needed. The process is tested, but model ratings are not a benchmark of design quality.

## Upstream skills

[`upstreams.json`](upstreams.json) is the complete administration file for third-party skills. Each entry names a public Git repository, a ref, the source directory, and its destination under `skills/`.

`architecture-map` mirrors its upstream instructions. Packaging adds a `DCS:` prefix to every
Codex display name so its origin stays visible in skill lists. Adapted skills can also name a
small adapter, patch, or file overlay under `ports/`.

The `anti-ui-slop` adapter packages the last self-contained skill while upstream references
runtime scripts that its source directory does not include. It fails when that assumption
changes so the port can be reviewed and removed. [`upstreams.lock.json`](upstreams.lock.json)
records its upstream Git tree, so a change remains visible even when the adapter produces
identical packaged output. The lock's `managedSkills` list tracks every generated skill so
removing a registry entry also removes its packaged directory.

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
