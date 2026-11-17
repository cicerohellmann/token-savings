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
model. The text the agent writes to you barely matters: on the author's data, visible prose was
about 1% of the bill, while reading and writing context was about 74% (see [Results](#results)).

## The strategies

Each strategy is one check in the grader, except those marked "not graded". "Effect" is what
happened on the author's data after the rule was adopted: the share of spend each check found
avoidable on 5–9 Oct 2026, before the rules, and on 9–16 Nov 2026, after them
([GRADES.md](GRADES.md) has the mechanism, thresholds and confidence for each, with the original October counts).

| strategy | the waste it stops | check | effect so far |
|---|---|---|---|
| **One task per helper.** A fresh helper with a full brief for each new task. | A helper given task 30 re-reads tasks 1–29 on every step. | re-task | 2.5% → under 0.1% of spend |
| **Lean helper types.** Helpers that load only the tools their job needs. | Every step of every helper re-reads 40–50k of tool schemas and instructions it never uses. | startup | 9.3% → 1.5% |
| **Model by task.** haiku for lookups, sonnet for routine work, opus for judgment ([MODELS.md](MODELS.md)). | Opus at 40× the price of Haiku doing a grep. | model | 4.3% → 1.6% |
| **Small, rare watchers.** Heartbeats 30+ min apart, a filter that only wakes on real news, never watch from a big chat. | A 150k chat re-reading itself to say "nothing changed". | hot wakes | grew: 1.1% → 4.1% |
| **Wake inside the cache's life, or small.** Don't let a big chat sit idle past 5 minutes and then wake. | After the cache expires, the whole context is written again at 12.5–40× the read price. | rewrites | 6.9% → 4.1%, no tested cure yet |
| **Read big output in pieces.** `tail`, `grep`, small screenshots. | A 50k log stays in context and is re-read on every later step. | big outputs | 0.1% → 0.2% (rule was already in place) |
| **Compact at a pause; the lead stays small.** The lead coordinates from short reports and keeps state in a file. | A chat working at 150k+ pays for all of it on every step. | bloat | 0.1% → under 0.1% (already in place) |
| **Open helpers without a name.** An unnamed helper ends itself when it reports. | A named helper stays open in the chat until shut down, and its name invites re-tasking it. | not graded | named: 99% of one lead's helpers before; 1 ask in about 180 helpers after a hook began stripping names |

Two more rules in [ETIQUETTE.md](ETIQUETTE.md) aren't graded yet: **batch commands** (one call
with five greps instead of five calls) and **don't run more helpers than a shared lock can serve**
(helpers queued on one build or device sit on their context while the cache expires).

On the author's data the overall avoidable share went from 23.3% (red) to 11.3% (yellow). The two
checks that hold most of what's left, hot wakes and cache rewrites, have no measured cure yet.

## Results

On the author's machine, 5 Oct – 16 Nov 2026: about 500,000 model calls, priced at today's API list
prices for every model.

**Each step got about 17% cheaper.** The average day cost $0.053 per step before the rules
(5–16 Oct, 8 full days) and $0.044 after (17 Oct – 16 Nov, 29 full days), leaving out Fable
(see limits). A permutation test on the daily figures puts the chance of this being luck below 0.1%.

**Because context got smaller.** Each step re-sent about 107k tokens of context before and about
81k after. Output per step did not fall in the same way (about 760 tokens per step early October,
560 late October, 760 again mid November).

**Where the money goes** (17 Oct – 16 Nov):

| part of the bill | share of $ |
|---|---|
| reading and writing context (cache reads and writes) | 74% |
| output tokens | 26% |
| … of which visible prose, the only part terse "caveman" prompting cuts | about 1% |
| … the rest: thinking and tool calls (mostly shell commands) | about 25% |

Prose also stays in context and is re-read on later steps, so 1% is a floor, but even a few times
that is small next to context. Making context smaller cut cost per step by 17%; cutting prose in
half would cut it by about half a percent. To see this split for your own chats, run
`python3 grade.py --split` (same window options as the grade).

The grade above prices each model at its own list price at the time (October's Opus 4.8 at the
older, higher rates). The 17% and the context figures price every model at today's rates, so the
change in price doesn't count as a saving. Don't compare the two sets of dollars directly.

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
`--repo PATH:BRANCH`, `--json`, `--split`). It reads `~/.claude/projects` (or `$CLAUDE_CONFIG_DIR/projects` if you set that) and nothing else, and sends nothing
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

- The evidence comes from one person's machine, running many multi-agent loops, in October and November 2026.
  The grade thresholds are calibrated on that data only.
- Each check is an upper bound: some carried context or late wakes were really needed.
- Other changes landed in the same weeks, so the effects above can't all be credited to one rule.
- Shares are of spend priced at API list rates. On a subscription they show where your limit goes,
  not a bill.
- The 17% leaves out Claude Fable 5.2, which the author started using in November at twice
  Opus's price; with it included, cost per step for 9–16 Nov was back to about where it started.
  It also says nothing about work done per step: that wasn't measured.
- Versions of `grade.py` before 17 Nov 2026 used old prices, under-counted output and misread when
  a chat was idle. The strategy table, the overall share and the `--split` figures come from the
  fixed version. The 17% and the context figures come from the author's separate analysis scripts,
  which are not in this repo.
- The grade says nothing about whether the work was worth doing.
