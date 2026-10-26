# Spend grades: red to green

`grade.py` reads your Claude Code transcripts and grades your spend. Each check finds the part of
spend that one rule of this lab would have saved. The grade is that part as a share of all spend.

The grade is **not** about how much you spend. Spending more while getting more work done is fine.
The grade asks how much of what you spent bought nothing.

Each check below follows [FRAMEWORK.md](FRAMEWORK.md): mechanism, what is counted, threshold and
where it comes from, our own numbers, confidence, cure.

## The scale

| | green | yellow | red |
|---|---|---|---|
| one check | under 2% of spend avoidable | 2–5% | over 5% |
| overall (each request counted once) | under 10% | 10–20% | over 20% |

**Where the thresholds come from:** they are a policy choice, not a measurement. They are
**provisional, calibrated on one person's data** (the author's Mac, Oct 2026). The overall cut-offs were
set so that the Oct 9 burn in the [case study](CASE.md) grades clearly red. The per-check cut-offs
mean "this one rule wastes more than 1 dollar in 20". Tune them once more people have run it.

**Dollars** are tokens priced at API list rates (price table: opus $5/$25 in/out, cache read
$0.50, cache write $6.25 for 5 min and $10 for 1 h; sonnet and haiku in the same ratios). That is
the API equivalent, not your bill. On a subscription it still shows where your limit goes.

**Our numbers** (all from `grade.py`, windows in local time, CET):

| window | avoidable | re-task | startup | model | hot wakes | rewrites | big outputs | bloat |
|---|---|---|---|---|---|---|---|---|
| Oct 9 (the case study) | **36.5% red** | 9.1 | 11.5 | 4.5 | 3.4 | 9.2 | 0.1 | 0.1 |
| Oct 11 – Oct 25 16:20 (baseline window) | **26.5% red** | 7.4 | 5.2 | 0.9 | 2.4 | 10.6 | 0.1 | 0.1 |
| Oct 25 16:20 – 23:28 (after the re-task gate, 7 h only) | **22.1% red** | 3.7 | 0.4 | 0.6 | 6.7 | 10.7 | 0.1 | 0.1 |

Check of the script: for Oct 11–25, its total spend and helper count (3,101) match the author's separate analysis script (3,116 helpers) within 3%; the gap is mostly 1 h cache writes, which grade.py prices higher.

**Every window of the author's data is red, even after the gate.** Re-tasking and startup fell, but cache
rewrites stay near 10% in every window and no cure for them has been measured. So today the lab can
show what keeps you red, but not yet a tested path to green.

---

## retask: re-task baggage

- **Mechanism.** Every step re-sends the whole conversation. A helper given a new task keeps all
  earlier tasks in its context and pays for them on every step of the new one.
- **What is counted.** In a helper, a new task (a new message after it went idle) that starts above
  100k context. Every step of that task pays for the context carried from earlier tasks (start of
  task minus the helper's first context), at the cache-read price. Re-tasks below 100k are not
  counted; the rules allow them when the old context helps.
- **Our numbers.** 9.1% on Oct 9, 7.4% Oct 11–25, 3.7% after the hard gate.
- **Confidence.** Mechanism high (it is how billing works). The amount is an upper bound: some of
  the carried context was useful to the next task.
- **Cure.** One task per helper; a fresh helper with a full brief. [ETIQUETTE.md §1](ETIQUETTE.md).

## startup: startup tax

- **Mechanism.** A helper starts with its tool definitions, instructions and memory files. It
  re-reads that start on every step. A general-purpose helper with every tool and MCP server loaded
  starts near 50k; a lean one with core tools starts near 10k.
- **What is counted.** For every helper step, the helper's first context above 15k, at the
  cache-read price.
- **Our numbers.** Median helper start 46k on Oct 9 (11.5%), 17k Oct 11–25 (5.2%), 14k after
  the lean helper types (0.4%).
- **Confidence.** High for the mechanism. 15k is a judgment: a lean helper plus a good brief.
- **Cure.** Lean helper types with only the tools the task needs: `adopt/agents/`. Keep briefs to
  paths and a one-line goal. [ETIQUETTE.md §4](ETIQUETTE.md).

## model: model fit

- **Mechanism.** Opus costs 5× haiku per token. A lookup (find, list, count, read a log) gets the
  same answer from haiku.
- **What is counted.** Opus helpers whose description looks like a lookup and not like judgment
  (keyword match on the description). 80% of their cost is counted.
- **Our numbers.** 4.5% on Oct 9, under 1% since the model rules and the model gate.
- **Confidence.** Medium. The keyword match on a short description misses some lookups and catches
  some real judgment tasks. The baseline window found sonnet did no worse than opus on routine work, but
  opus got harder tasks, so that is confounded.
- **Cure.** Pick model and effort per task. [MODELS.md](MODELS.md). The grader also prints how many
  helpers were opened without any model.

## hot: hot wakes

- **Mechanism.** A loop, a monitor line or a task notification wakes the chat. The wake re-reads the
  whole chat, even when the answer is "nothing changed".
- **What is counted.** Main-chat steps in a turn started by a machine wake while the context is above
  80k. Everything above 30k (what a small watcher would carry) is counted, at the cache-read price.
- **Our numbers.** 3.4% Oct 9, 2.4% Oct 11–25, 6.7% in the seven hours after the gate.
- **Confidence.** High for the mechanism. A real case: a 166k reviewer chat that woke on every
  monitor line cost 6% of a week. Medium for the amount: some wakes need the big chat.
- **Cure.** The monitor's filter decides; heartbeats 30 min or more apart; stop watching when the
  work stops; never watch from a chat above about 100k, hand it to a small helper.
  [ETIQUETTE.md §7](ETIQUETTE.md).

## rewrite: cache rewrites

- **Mechanism.** The prompt cache keeps a conversation for 5 minutes (or 1 hour). After that, the
  next step writes the whole context to the cache again at 12.5× the read price (5 min) or 20× (1 h).
- **What is counted.** A step with a cache write over 30k that is more than half its context, after
  a gap longer than the cache's life, in a helper or after a machine wake. Counted: write price minus
  read price. The whole write counts, not just the part above a small watcher's 30k (as hot wakes
  do), because waking within the cache's life avoids the whole write. Rewrites after you yourself
  come back to a chat are not counted; that pause is yours.
  The grader splits it: after waiting on a long tool (a build or test that took over 5 min) and
  after a wake or a new message.
- **Our numbers.** 9.2% Oct 9, 10.6% Oct 11–25 (22% of it after long tools, 78% after wakes or
  messages), 10.7% after the gate. Now the biggest red check on the author's data.
- **Confidence.** High for the mechanism and the amount. **No cure has been measured yet.**
- **Cure (untested).** Wake a chat either within 5 minutes or with a small context, never big and
  late: heartbeats under 5 min only for tiny watchers; a lead that waits long on helpers should
  compact first. Do long builds in a small helper so the big chat doesn't sit waiting.

## bigout: big tool outputs

- **Mechanism.** A tool output stays in the context until compaction, and every later step re-reads it.
- **What is counted.** Outputs over 10k tokens; the part above 2k is counted on every later step
  until the next compaction, at the cache-read price.
- **Our numbers.** 0.1% in every window.
- **Confidence.** High. Low on the author's data because the rules already say "read big output through
  `tail`/`grep`".
- **Cure.** `tail`, `grep`, `head`, small screenshots. [ETIQUETTE.md §3–4](ETIQUETTE.md).

## bloat: bloated chats

- **Mechanism.** A chat that keeps working above 150k pays for all of it on every step, even
  the parts it no longer needs.
- **What is counted.** Main-chat steps above 150k context (not wakes; those are under hot); the part
  above 150k, at the cache-read price.
- **Our numbers.** 0.1% or less: the author's chats auto-compact earlier.
- **Confidence.** Medium: some work really needs a big context.
- **Cure.** Compact at a pause. [ETIQUETTE.md §6](ETIQUETTE.md).

---

## work: work done per dollar (not graded)

The goal of this lab is more work per dollar, so the grade should one day include it. It doesn't
yet, because the measure is not good enough to color anyone red:

- **What is counted.** $ = every chat whose working folder is inside the repo (worktrees too).
  Landed = non-merge commits on the branch you name with a commit date in the window, by anyone.
  Human commits count too; in repos where agents make nearly all commits, that is small.
- **Why not count each agent's own commits.** The lab tried that (commit lines in transcripts). It missed whole repos: repo C had 458 commits in the week of Oct 18–25 and
  the transcript method found none of them.
- $ per landed commit depends on the repo, the task size and commit habits. It can't be compared
  between people or repos (Oct 18–25: repo B cost about 12× as much per landed commit as repo C, repo A about 2×).
  Compare **your own** numbers week to week instead.
- Rework (a fix commit on the same file within 48 h) is too noisy: 31% of all of the author's main
  commits match it. See the evidence in [FRAMEWORK.md](FRAMEWORK.md).

Run it with `grade.py --repo PATH:BRANCH` (one `--repo` per repo; use the branch work really lands
on, not always `main`).

## What the grader can't see

- Whether the work was worth doing. A green grade on useless work is still waste.
- Spend outside Claude Code transcripts (API scripts, the web app).
- Re-tasks below 100k that carried useless context, and wakes or rewrites that were really needed.
  Each check is a share of spend a rule *would* have saved, so the checks are upper bounds.
