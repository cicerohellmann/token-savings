# Token savings

Find the Claude Code tokens that bought nothing, and stop spending them.

This repo does three things:

1. **Measures.** `grade.py` reads your local Claude Code transcripts and works out, check by check,
   how much of your spend a known rule would have saved. Each check gets a grade, red to green, and
   so does the total.
2. **Explains.** Open Claude Code here and it turns the grade into plain advice: what each red check
   found, why it costs, which of your chats caused it, and what to change.
3. **Fixes.** It hands you the rules and lean helper types that cure each check, ready to install,
   and you re-grade a week later to see if the grade moved.

The grade is about waste, not volume. Spending more while getting more done is fine; the question
is how much of what you spent bought nothing.

**Words used here.** *Helper*: a Claude Code subagent, started with the `Agent` tool. *Main chat* (the
"lead" in the evidence files): the chat you type in, which starts helpers. *Loop*: an agent that
repeats work on its own, often through helpers. *Watcher*: a loop, `/loop` or `Monitor` that keeps
checking something. *Wake*: one such check, which re-reads the whole chat.

**Which rules apply to me.** One chat and no helpers: only "read big output in pieces", "batch
commands" and "compact at a pause"; the rest does nothing for you. You use helpers: add one task per
helper, lean types, model by task and unnamed helpers (all in [adopt/CLAUDE-rules.md](adopt/CLAUDE-rules.md)).
You run loops, `/loop`, `ScheduleWakeup` or `Monitor`: also the watcher rules, which are marked in that file.


## Why tokens get wasted

Every step an agent takes re-sends its whole conversation. So the cost of a step is roughly its
**context size × model price**, and the cost of a task is that **× the number of steps**. Almost
every saving here comes from one of three levers: a smaller context, fewer steps, or a cheaper
model. Output text is a rounding error: in the case study, 96% of all tokens were the same
conversations being re-read.

## The strategies

Each strategy is one check in the grader, except those marked "not graded". "Effect" is what
happened on the author's data after the rule was adopted ([GRADES.md](GRADES.md) has the numbers,
thresholds and confidence for each).

| strategy | the waste it stops | check | effect so far |
|---|---|---|---|
| **One task per helper.** A fresh helper with a full brief for each new task. | A helper given task 30 re-reads tasks 1–29 on every step. | re-task | 9.1% → 3.7% of spend |
| **Lean helper types.** Helpers that load only the tools their job needs. | Every step of every helper re-reads 40–50k of tool schemas and instructions it never uses. | startup | 11.5% → 0.4% |
| **Model by task.** haiku for lookups, sonnet for routine work, opus for judgment ([MODELS.md](MODELS.md)). | Opus at 5× the price of haiku doing a grep. | model | 4.5% → under 1% |
| **Small, rare watchers.** Heartbeats 30+ min apart, a filter that only wakes on real news, never watch from a big chat. | A 150k chat re-reading itself to say "nothing changed". | hot wakes | not yet lower (2–7%) |
| **Wake inside the cache's life, or small.** Don't let a big chat sit idle past 5 minutes and then wake. | After the cache expires, the whole context is written again at 12.5–20× the read price. | rewrites | ~10%, no tested cure yet |
| **Read big output in pieces.** `tail`, `grep`, small screenshots. | A 50k log stays in context and is re-read on every later step. | big outputs | ~0.1% (rule was already in place) |
| **Compact at a pause; the lead stays small.** The lead coordinates from short reports and keeps state in a file. | A chat working at 150k+ pays for all of it on every step. | bloat | ~0.1% (already in place) |
| **Open helpers without a name.** An unnamed helper ends itself when it reports. | A named helper stays open in the chat until shut down, and its name invites re-tasking it. | not graded | named: 99% of one lead's helpers before; 1 ask in about 180 helpers after a hook began stripping names |

Two more rules in [ETIQUETTE.md](ETIQUETTE.md) aren't graded yet: **batch commands** (one call
with five greps instead of five calls) and **don't run more helpers than a shared lock can serve**
(helpers queued on one build or device sit on their context while the cache expires).

On the author's data the overall avoidable share went from 36.5% (red) to 22% (still red). The two
checks that hold most of what's left, hot wakes and cache rewrites, have no measured cure yet.

## Use it

You need Claude Code and Python 3.9+.

```
git clone https://github.com/cicerohellmann/token-savings
cd token-savings
claude
```

Then say one of:

- **"Evaluate my token spend."** It runs `grade.py` on your last 7 days, shows the grade table, and
  explains every non-green check with its cure. Name a window ("the last 14 days") or your repos
  (to also see work per dollar) if you like.
- **"Give me your improvements."** It asks whether you want the whole machine or one project, then offers to add [adopt/CLAUDE-rules.md](adopt/CLAUDE-rules.md)
  to your `CLAUDE.md` and copy the `worker`, `reviewer` and `scout` helper types in
  [adopt/agents/](adopt/agents/) to your `agents/` folder, and to install the helper gate hook from
  [adopt/hooks/](adopt/hooks/). It does this with `adopt/install.py`: a dry run shows each change, and it applies them only when you say yes. "Undo the token-savings changes" removes it again.

Or run the grader yourself: `python3 grade.py` (`--days N`, `--since/--until "YYYY-MM-DD HH:MM"`,
`--repo PATH:BRANCH`, `--json`). It reads `~/.claude/projects` (or `$CLAUDE_CONFIG_DIR/projects` if you set that) and nothing else, and sends nothing
anywhere. Claude Code deletes transcripts after 30 days by default, so that is as far back as it
can grade.

## What's here

| file | what it is |
|---|---|
| [GRADES.md](GRADES.md) | the grade scale and every check: mechanism, what is counted, thresholds, confidence, cure |
| [ETIQUETTE.md](ETIQUETTE.md) | the rules for running helpers (subagents), with the evidence for each |
| [MODELS.md](MODELS.md) | which model and effort for which kind of helper task |
| [CASE.md](CASE.md) | the afternoon that started it: three agent loops and where their tokens went |
| [FRAMEWORK.md](FRAMEWORK.md) | how every lesson here is written up: situation → mechanism → proposal → prediction → measurement → result → confounders → status |
| [adopt/](adopt/) | the rules block, the lean helper types, the helper gate hook, and `install.py` that installs and undoes them |
| `grade.py` | the grader (standard library only) |
| [CLAUDE.md](CLAUDE.md) | what Claude does when you open it here |

## Limits

- The evidence comes from one person's machine, running many multi-agent loops, in October 2026.
  The grade thresholds are calibrated on that data only.
- Each check is an upper bound: some carried context or late wakes were really needed.
- Other changes landed in the same weeks, so the effects above can't all be credited to one rule.
- Shares are of spend priced at API list rates. On a subscription they show where your limit goes,
  not a bill.
- The grade says nothing about whether the work was worth doing.
