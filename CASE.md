# Case study: one afternoon, 2026-10-09, 15:23 to 21:09

Where most of the strategies in the [README](README.md) came from. Three agent loops ran in
parallel, each a lead chat with 4 to 7 helpers, in two repos (call them A and B). A few watchers
ran next to them: a reviewer heartbeat, a message watcher and a check-in.

The session limit hit after about an hour. Where the tokens went:

| | share of tokens |
|---|---|
| text the agents actually wrote | 0.2% |
| cache writes | 4% |
| cache reads (re-sending conversations) | 96% |

By loop: repo A about 42%, the first repo B loop about 39%, the second about 12%, the watchers
about 3%. `grade.py` grades that day **36.5% avoidable, red** ([GRADES.md](GRADES.md)).

## What was not the problem

Running the loops in parallel. The loops did real work, and output grew with the number of agents.

## 1. Every step re-sends the whole conversation

A step costs about as much as the agent's current context. The helpers averaged **about 110k
tokens per step** and sat between 100k and 167k for hours (167k is where compaction kicks in). One
helper running 800 steps at 110k costs about 90M.

## 2. Long-lived helpers got new tasks again and again

One helper in repo A got 41 new tasks from its lead over the afternoon. It took about 1,100 steps
and was compacted 18 times. Its context never dropped back down, so even a one-line follow-up was
paid at 100k+ per step. Every big helper in all three loops followed the same pattern.

A fresh helper starts at about 37k (median over 930 helpers). The tasks were useful; the waste was
the baggage. Task 30 re-sent tasks 1 to 29 on every step. A 20-step follow-up costs about 2.4M in a
120k helper and about 1.2M in a fresh one: same work, half the price.

## 3. Leads get heavy too

Leads also averaged about 110k per step; one was compacted 70 times over its life. A lead should
read its helpers' short reports, never their transcripts or long logs, and hand off to a fresh lead
after heavy compaction. How to restart one: [ETIQUETTE.md §6](ETIQUETTE.md).

## 4. Fixed overhead on every step of every agent

Before doing anything, a fresh agent carried **about 40 to 50k tokens**: the system prompt, tool
schemas, the skill list, the deferred-tool list (mail, calendar, browser and plugin tools),
`MEMORY.md` and the project's instruction files. Every agent pays this on every step. Lean helper
types with only the tools they need cut it to about 10–15k ([adopt/agents/](adopt/agents/)).

## 5. Watchers re-read their whole context on every wake

A check-in at about 100k context every 15 minutes used about 1% of the day's tokens; the reviewer
heartbeat about 1.5%. Small next to the loops, but pure overhead. Give watchers long intervals and
small contexts.
