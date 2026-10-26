# Helper gate (a PreToolUse hook)

Rules get ignored. This hook enforces the helper rules from [../CLAUDE-rules.md](../CLAUDE-rules.md).
Keep the rules too: they stop most bad calls before they are made, and every refused call still costs
a full step. The hook catches what slips past. The evidence is in [ETIQUETTE.md §9](../../ETIQUETTE.md).

## What it does

On `Agent` (and the older `Task`):

- **No model: refused.** The refusal carries a short guide to pick one and the off-switch line, and
  the agent calls again. Built-in agents (Explore, Plan, general-purpose) and plugin agents pass when
  they set a model. `effort` is not required, because older Claude Code has no such field; set
  `REQUIRE_EFFORT = True` in the script to require it too.
- **`name` and `team_name` are stripped.** A named helper stays open in the chat until it is shut
  down; an unnamed one ends when it reports.
- **Reroute (off by default; set `REROUTE = True` to opt in).** Reviews go to sonnet/medium, lookups
  (scout type, or a description that starts with find/list/count/grep/…) to haiku/low. It only
  lowers: a helper asked cheaper keeps what it asked. Leave it off if your tricky reviews need opus
  ([MODELS.md](../../MODELS.md)): the keyword match can't tell a tricky review from a routine one.
- Forks (`subagent_type: "fork"`) pass untouched.

Opt-in only (`RETASK_CHECK = True` in the script, and change the settings matcher to
`Agent|Task|SendMessage`): on `SendMessage` to one of this chat's own helpers:

- **Refused** if the helper is above 100k context (`REUSE_CTX`), or is a reviewer (by type, name or
  description). Messages to the lead, to peer chats and protocol replies pass.

A rewrite answers `allow` with `updatedInput`, so that call skips the permission prompt.

## Install

`python3 adopt/install.py --scope user --dry-run` (or `--scope project --project PATH`) does all of
this and can undo it (`--undo`). By hand:

Your config folder is `~/.claude`, or `$CLAUDE_CONFIG_DIR` if you set it.

1. Copy `helper_gate.py` to `<config>/hooks/`.
2. Merge the entry in [settings-snippet.json](settings-snippet.json) (matcher `Agent|Task`) into the `PreToolUse` list of
   `<config>/settings.json`. Add it next to the hooks you have; don't replace them. If your config
   folder is not `~/.claude`, put its full path in the command instead of `$HOME/.claude`.
3. Run the tests: `python3 -m unittest discover -s adopt/hooks -v` from the repo root.

Needs Python 3.9+, standard library only.

## Off, logs, errors

The hook keeps its files in `<config>/helper-gate/`.

- **Off switch:** `touch ~/.claude/helper-gate/off` (or `<config>/helper-gate/off`) turns the whole hook off. Delete the file to turn
  it on again.
- **Log:** one line per decision in `~/.claude/helper-gate/decisions.jsonl`.
- **Fails open:** any error lets the call through and adds a line to `~/.claude/helper-gate/errors.log`.
- `HELPER_GATE_HOME` moves all three files.

## Limits

- The re-task check (opt-in) reads Claude Code's undocumented helper layout
  (`<chat>/subagents/agent-<id>.meta.json` next to the chat's transcript). If that layout changes,
  it finds no helper and lets every message through. That is why it is off by default.
- Reviews and lookups are found by keywords in the description. Some get missed, some get caught
  wrongly.
- A broadcast (`SendMessage` to `"*"`) passes untouched. With names stripped, few teammates are
  left for it to reach.
- Not ported: the author's budget guard, which depends on that machine's limits and spend tools.
