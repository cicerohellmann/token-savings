# token-savings: what to do when someone opens Claude here

This folder is a lab on Claude Code token spend: the rules, the evidence behind them, and a grader.
People come here to ask "evaluate our token spend" or "set me up with your improvements".

## "Evaluate my token spend" (or "grade", "check", "how am I doing")

1. Run `python3 grade.py` (last 7 days). It reads `$CLAUDE_CONFIG_DIR/projects` if that is set, else
   `~/.claude/projects`; if their transcripts live elsewhere, add `--root PATH`. If it prints that it found
   no requests, say so plainly ("no transcripts to grade") and stop. Don't invent a grade. Use `--days N` or `--since/--until` (local time) if they name a window.
   If they name repos, add `--repo PATH:BRANCH` for each, with the branch work really lands on (without `:BRANCH` it uses `main`).
   Run it as is. Don't read their transcripts yourself; the script reads gigabytes of transcripts in under a minute, and you
   would burn tokens reading a fraction of it.
2. Show the grade table as printed.
3. For each yellow or red check, in order of $ avoidable, explain from [GRADES.md](GRADES.md):
   - what the check found, with its $ and share
   - why it costs (the mechanism)
   - where it comes from (the chats the script lists)
   - the cure, with its link to [ETIQUETTE.md](ETIQUETTE.md) or [MODELS.md](MODELS.md)
   - how sure we are (the confidence line). Say so plainly when a cure is untested.
4. Say what would turn the overall grade green: the one or two checks that hold most of the avoidable share.
5. End with the limits: the $ is API list price, the thresholds are provisional (one person's data),
   and the grade says nothing about whether the work was worth it.

Don't grade on total spend or spend per day. More spend with more work done is not worse.

## "Give me your improvements" (or "adopt", "inherit", "set me up")

`adopt/install.py` does the install; you don't copy or edit their files by hand. Only macOS and Linux
are tested (on Windows run it with `python` or `py`).

1. **Ask the scope** unless they said it. Whole machine: `--scope user` (their config folder:
   `$CLAUDE_CONFIG_DIR` if set, else `~/.claude`; if they name another, add `--config PATH`). One project:
   `--scope project --project PATH`.
2. **Dry run.** `python3 adopt/install.py <scope args> --dry-run`. Show them what it prints: the rules
   appended to their `CLAUDE.md` (between `token-savings` markers), the `worker`, `reviewer` and `scout`
   helper types, a copy of the helper gate hook, and the `settings.json` diff (one new `PreToolUse`
   entry; every other key, hook and `statusLine` is kept). If it says a helper type of theirs differs,
   ask whether to replace it (`--replace-agents`).
3. **Install** on their yes: the same command without `--dry-run`. It runs the hook tests first and
   skips the hook if they fail. If `python3` is missing, say so: nothing can be installed.
4. **Explain** in a few lines: the hook refuses a helper opened without a `model` (built-in and plugin
   agents that set one pass) and strips `name`; effort checks, rerouting and the re-task check are
   opt-in ([adopt/hooks/README.md](adopt/hooks/README.md)). Give the off-switch line it printed. Tell
   them to restart Claude Code (or open `/hooks`).
5. Suggest a re-grade in a week: `python3 grade.py --days 7`, to compare against today.

Keep the rules and the hook together: the rules stop most bad calls, the hook catches the rest.

## "Undo the token-savings changes" (or "uninstall", "remove")

Same scope arguments as install, with `--undo`: dry run first (`--undo --dry-run`), show it, then run it.
It removes the rules block, the helper types it installed (an edited one is kept and named), the hook,
and the helper gate entry in `settings.json`, and leaves their files as they were before. It also works
on an install made by hand from the steps this file used to give. If it names a hook log folder it
left, pass that on (they may delete it); if it names none, there is none. To keep the hook but silence
it instead: `touch <config folder>/helper-gate/off`.

The author's budget guard is not in this repo, because it depends on that machine's limits and
spend tools. Say so if asked.

## How claims are written here

Every lesson follows [FRAMEWORK.md](FRAMEWORK.md): situation, mechanism, proposal, prediction,
measurement, result, confounders, status. When you explain a rule, give its evidence and its
confidence, not just the rule. If the evidence is missing, say it's missing.
