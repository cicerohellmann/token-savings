# How every lesson is written

No lesson is "we did X and it helped". Each lesson goes through these eight steps, in this order. Each step names its source: file and section, the script that produces the number, or the transcript or commit. If a step has no data, write **missing** and why. Don't fill the gap with a guess.

The goal being measured is **work done per token**, not spend per day. More spend with more work landing can be a win. Less spend with less work done is not one by itself.

## The steps

1. **Situation.** What was observed, when, and how big it was. Numbers, the window, and the source.
2. **Mechanism.** Why it happens: the cause, not the symptom. What in how Claude Code bills or behaves produces it?
3. **Proposal.** The change, and how it acts on the mechanism in step 2.
4. **Prediction.** Written before the change lands:
   - which cost metric should move, which way, and roughly how much
   - which work metric must not get worse: landed commits, rework, HOLD rate, redos
5. **Measurement.** How to check the prediction:
   - metric definitions
   - baseline window and after window
   - the command that reproduces the numbers, for example `grade.py --since "…" --until "…"`
6. **Result.** Before and after, for both the cost metric and the work metric.
7. **Confounders and confidence.**
   - what else changed in the same window
   - how much work ran: compare per call or per helper, not per hour or per day (see below)
   - sample size
   - what would make the result wrong
   - a rating: high / medium / low
8. **Status.** Kept, made a hard gate, reverted, or waiting for a re-measure, with the date.

---

## Worked example: one task per helper

1. **Situation.** On 2026-10-09, from 15:23 to 21:09, three loops ran for 6 hours. 96% of their tokens were cache reads, meaning re-sent conversations; output was under 0.2%. Helpers averaged about 110k context per step and sat between 100k and 167k for hours. One helper in repo A got 41 tasks, took about 1,100 steps and was compacted 18 times. *Source: CASE.md §1–2.*
2. **Mechanism.** Every step re-sends the whole conversation, so a step costs about as much as the current context. A helper that is re-tasked never drops back down: task 30 re-sends tasks 1–29 on every step, even when it doesn't need them. A fresh helper starts at about 37k (median of 930 helpers). *Source: README.md §1–2.*
3. **Proposal.** Give each helper one task. Re-task a helper only when the next task builds directly on what it just did. Otherwise start a fresh helper with a full brief. The brief carries the context; the old conversation doesn't have to.
4. **Prediction.** **Missing.** No prediction was written down before the change. Implied after the fact:
   - cost per helper should fall
   - a 20-step follow-up should cost about 1.2M instead of 2.4M
   - no work metric was named
5. **Measurement.** Dollars per helper from transcripts priced at list rates (the author's token tool, private). Baseline Oct 8–9, after Oct 15–16. Work metric: dollars per landed commit and rework within 48h, split by the helper's peak context (the author's analysis script, private; 14 days Oct 11–25).
6. **Result.**
   - Cost per helper fell by 60–67% from Oct 8–9 to Oct 15–16. *Source: the author's change log (private), row 10-09.*
   - Work, by peak context: helpers that peaked over 150k cost 1.8–2.3× as much per landed commit as helpers under 100k, with 38% rework against 8–23% (622 helpers and 1,367 landed commits, against 2,003 helpers and 393 landed). *Source: the author's lever study (private) §3; re-run of its analysis script on 2026-10-25, table "helpers by peak ctx".*
   - Work, by number of tasks (same run, table "helpers by segments"): cost per landed commit relative to 1-task helpers: 2–3 tasks 0.6×, 4–10 tasks 0.7×, 11+ tasks 2.7×; rework 27% (1 task), 34%, 41%, 21%. Counted by tasks, re-tasking does **not** clearly do worse except at 11+. Only the peak-context split supports the rule.
   - How the numbers are made:
     - **Cost** is the transcript's tokens priced at list API rates, not what was billed.
     - **Commit → helper:** The script reads `[branch hash] subject` lines that git printed inside the helper's transcript, kept if the commit time is within 1h of that line.
     - **Landed:** the hash is on `main`/`master`, or a commit with the exact same subject is there within 96h. The code uses 96h; the study's text says 48h. Only `main`/`master` counts, so work still on a long-lived feature branch (one was 779 commits ahead of main on 10-25) counts as not landed.
     - **Rework:** a later main commit within 48h touches the same source file and its subject matches `fix|revert|re-|again|hotfix|follow-up|regress`, or the commit was reverted. 31% of all 4,357 main commits since 10-11 match this, so it measures "how often the file got a fix-like commit soon after", not proven defects.
7. **Confounders and confidence.**
   - Between Oct 9 and Oct 16 many other changes landed:
     - the budget guard (10-11/12), which also cut how much work ran
     - the watcher rule (10-14)
     - sonnet for reviewers (10-15)
     - lean helper types and startup cuts (10-16)

     So the drop in cost per helper can't be credited to this rule alone.
   - The work split is confounded by task size: big tasks both grow context and need more rework. The tasks-per-helper table points the other way, which fits task size being the driver.
   - Small samples at the cheap end: the <50k band has 96 landed commits and 19 reviewed verdicts.
   - Even after the rule, long-lived helpers still made up 60% of 14-day spend, so the rule wasn't fully followed. *Source: the lever study, §3.*
   - Confidence that the mechanism is right: **high** (it follows from how billing works). Confidence in the measured size of the effect: **low**.
8. **Status.** The rule was ignored in practice (a lead acknowledged it and still re-tasked). On 2026-10-25 it became a hard gate: a PreToolUse hook (a portable version is in [adopt/hooks/](adopt/hooks/)) refuses re-tasking a helper above 100k context, and refuses re-tasking a reviewer or signer at all. **Waiting:** re-measure dollars per landed commit and rework for helpers after 2026-10-25 16:20, against the Oct 11–25 baseline.

---

## Confounder: measure per call, not per hour

1. **Situation.** Two evenings, A before the helper gates and B after. Spend per hour fell from about
   $270 to $75, and calls per hour from 3,700 to 1,200. *Source: the author's transcripts (private).*
2. **Mechanism.** Spend per hour is cost per call × calls per hour. Calls per hour move with how much
   work ran, and that has nothing to do with the rule. On evening B:
   - it was a quieter evening;
   - builds were held while the machine ran on battery;
   - a weekly limit was near.
3. **Proposal.** Judge a change by cost per call, context per call and cost per helper. Report spend
   per hour only next to calls per hour, as a sign of how busy the window was.
4. **Prediction.** **Missing**: none was written before the gates.
5. **Measurement.** The same two evenings, from transcripts priced at list rates. The exact windows
   are missing from this write-up.
6. **Result.**
   - context per call: 95k → 74k (−22%)
   - cost per call: $0.073 → $0.061 (−16%)
   - cost per helper: $9–17 → $1.2–2.9

   The per-hour drop (about −72%) is mostly less work running, for the reasons in step 2. The per-call drop is the fair one.
   Work metric: **missing**.
7. **Confounders and confidence.** Two evenings. Several gates landed together, so their shares
   can't be split. Confidence that per call is the fairer measure:
   **high**. Confidence in the size of the gates' effect: **low**.
8. **Status.** Kept as a rule for every write-up here.

---

## Gaps this framework shows in the lab today

- **Predictions:** no change-log row has a prediction written before the change. Add a "prediction" column.
- **Work metrics:** most rows measure only cost. The nightly report records no work metric. Add landed commits, dollars per landed commit, rework %, HOLD % and redos to the nightly run.
- **Confounders:** many changes landed on the same days (Oct 16–17 especially), so most effects can't be separated. Space out changes, or note the overlap in each row.
