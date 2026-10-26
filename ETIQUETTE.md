# Subagent etiquette

For every agent that runs subagents (helpers): loop leads, orchestrators, anyone using the `Agent` tool
more than once. The short version is [adopt/CLAUDE-rules.md](adopt/CLAUDE-rules.md), ready to add to your `~/.claude/CLAUDE.md`. This file has
the reasons and the evidence.

Most of the bill is one thing: **every tool call re-reads the whole context.** A helper at 100k that
makes 200 calls reads 20M tokens. Everything below either shrinks the context, cuts the number of
calls, or moves the work to a cheaper model.

## 1. One task per helper

Give each new task a fresh helper. Re-task an old one only when its context truly helps the next
task, for example a follow-up on the same files it just changed.

*Evidence:* on 2026-10-09 most of the spend went to re-tasked long-lived helpers (see
CASE.md). On 2026-10-14 a repo B loop lead re-tasked one helper about 10 times in 5 h,
each time with a new job. The helper reached 314k context and cost about as much as 15 average helpers by itself. In
the same 6 h the repo A lead gave each of its 54 helpers exactly one task.

## 2. Pick the model and effort by task

Every `Agent` call sets `model` and `effort`, chosen by what that task needs, not by the helper's title.
A reviewer of tricky domain logic needs opus; a reviewer of a rename is fine on sonnet. The examples per
model are in [MODELS.md](MODELS.md). The hook in [adopt/hooks/](adopt/hooks/) refuses a helper opened without a model.

| model | when | effort |
|---|---|---|
| haiku | no judgment needed and the answer is easy to check: lookups, greps, status checks, log reading, file moves, counting | low |
| sonnet | routine work with a clear brief: renames, codemods, UI snapshot updates, gate fixes, tests, normal reviews, mockups | low or medium |
| opus | judgment: design, architecture, bugs with an unknown cause, reviews of tricky changes, work the owner judges closely | medium or high |

If a cheaper helper fails or its work bounces at review, re-run that task one level up and note it.
Don't move the whole role back up after one miss.

*Evidence:* in repo A on 2026-10-14, every reviewer and gate helper ran on Opus.
Sonnet costs 60% of Opus for the same tokens. Lower effort mostly cuts thinking output, which was about 17%
of the helper bill.

## 3. Batch commands

One grep, one `sed -n`, one `git log` per call means a 100k re-read each time. Put related reads in one
call: several greps chained with `;`, or a short script that prints everything needed. Read the
file region you need once. Don't re-read it in small steps.

*Evidence:* the repo A helpers made about 3,300 Bash calls in 6 h, 70–300 per helper. Re-reading
context was about 60% of their cost.

## 4. Keep helpers small

- **Brief with pointers.** Give the paths, the commit, and the one-line goal. Don't paste file contents or
  long history into the prompt; the helper reads what it needs.
- **Read big things in pieces.** Logs, transcripts and build output go through `tail`, `grep` or
  `head`. Never attach full-size screenshots: save them to a file, or downscale to about 1000 px.
- **Finish with a short result.** A few lines: what changed, the commits, what's left. The lead reads that, not
  the helper's transcript.
- **Every helper starts at about 50k** (tools, CLAUDE.md, AGENTS.md, memory) before its task. Short tasks
  are still worth a fresh helper, but don't spawn a helper for something one command answers.

## 5. Parallel, but not on the same gate

Parallel helpers are good. Helpers that all wait on one lock (a build, a device, the push gate) are
not parallel. They each sit on their context and re-read it when they wake. Run as many as the
shared resource can actually serve.

## 6. The lead stays small

The lead coordinates; it doesn't code. It reads short helper results, keeps loop state in a file,
and compacts at a pause instead of drifting to 150k+. A lead that wakes on a loop pays its whole
context on every wake.

### Restart a bloated lead

When a lead has been compacted many times (CASE.md §3) or its process has grown to gigabytes, restart it:

1. The lead writes a short handoff note: its role, the next step, open items, and the crons and
   monitors it runs.
2. `/exit`.
3. Start a fresh chat briefed from the note, or resume the old one.
4. Tell the chat it was restarted, and re-arm its loops from the note.

Things that block `/exit`: a pending permission prompt, an "unsent feedback drafts" dialog, and a
"stop background tasks" dialog. Stop the background tasks only when what's left are stale waits.

1. **Situation.** One lead's process had grown to 3.1 GB of memory. *Source: the author's machine
   (private).*
2. **Mechanism.** Compaction shrinks what a chat sends, not everything the process holds, for
   example named helpers that never closed (§8). Which part made up the 3.1 GB was not measured.
3. **Proposal.** The restart above.
4. **Prediction.** **Missing.**
5. **Measurement.** Process memory before and after; the share of named helpers the chat asked for
   afterwards.
6. **Result.** Started fresh, the lead's process was 0.33 GB, and it asked for 0 named helpers in its
   first 81. Fresh against resume: **pending**. Tokens per step before and after: **missing**.
7. **Confounders and confidence.** One restart. If the fresh chat started with the no-name rule
   already loaded, the 0 named asks may be the rule, not the restart. Confidence: **low**.
8. **Status.** Kept as a manual procedure. Pending: compare a fresh start with a resume.

## 7. Watchers, loops and heartbeats

These rules are in [adopt/CLAUDE-rules.md](adopt/CLAUDE-rules.md):
- the monitor's filter decides what is worth a wake;
- heartbeats at least 30 min apart;
- stop when the watched work stops;
- never watch from a big chat.

*Evidence:* a reviewer chat at 166k context woke on every monitor line plus a 20-min heartbeat. It cost 6% of the week.

## 8. Open helpers without a name

Leave out `name` when you call `Agent`. An unnamed helper ends itself when it reports. For the next
task, open a fresh one. What is proven: unnamed helpers close and free their memory. The effect on
tokens is **unmeasured**; the saving is indirect, since an unnamed helper can't be re-tasked.

1. **Situation.** Before the rule, one lead opened 99% of its helpers with a name, and another chat
   43%. One lead had 1,352 named helpers over its life. *Source: the author's transcripts (private).*
2. **Mechanism.** An `Agent` call with `name` makes an in-process teammate. It doesn't finish when it
   reports: it stays in the chat's memory until it is shut down. Its name also invites re-tasking it,
   which §1 is against.
3. **Proposal.** Open helpers without a name. A hook strips `name` from every `Agent` call
   ([adopt/hooks/](adopt/hooks/)).
4. **Prediction.** **Missing**: none was written before the change.
5. **Measurement.** Named asks, and helpers still open, in the hours after the hook started
   stripping names. Counted from the hook's log and the helpers' metadata. The exact window is
   missing from this write-up.
6. **Result.** About 180 helpers were opened. 1 was asked with a name, and the hook stripped it.
   Every unnamed helper closed when it reported. The only helpers still open were 2 named before
   the strip. Work metric: **missing**.
7. **Confounders and confidence.** The rule and the hook landed together, so their shares can't be
   split. A few hours, one machine. The tokens and memory saved weren't measured. Confidence that
   unnamed helpers close: **high** (seen on every one). Confidence in the savings: **missing**.
8. **Status.** Kept, as a rule and a hook.

## 9. Rules get ignored: keep the rule, add a hook

A PreToolUse hook enforces the helper rules: [adopt/hooks/](adopt/hooks/). It refuses a helper
opened without a model and strips `name`; refusing a re-task of a helper above about 100k or of a
reviewer is opt-in. Keep the written rules as well.

1. **Situation.** The rules were written down and still broken. A lead acknowledged the re-task rule
   and re-tasked anyway ([FRAMEWORK.md](FRAMEWORK.md), step 8). One lead opened 99% of its helpers
   with a name (§8). *Source: the author's transcripts (private).*
2. **Mechanism.** A rule is a few lines in a big context, next to a task that pulls the other way. A
   hook runs outside the model and can't be talked past. But a refusal isn't free: the refused call
   already cost a full step, and the agent makes another.
3. **Proposal.** Both. The rule stops most bad calls before they are made. The hook catches what
   slips past.
4. **Prediction.** **Missing**: none was written before the change.
5. **Measurement.** The re-task check in `grade.py`, before and after the gate went live
   (2026-10-25 16:20). The number of refused calls: **missing**.
6. **Result.** Re-task baggage fell from 7.4% of spend (Oct 11–25) to 3.7% in the 7 h after the gate
   ([GRADES.md](GRADES.md)). Named asks: §8. Work metric: **missing**.
7. **Confounders and confidence.** Only 7 h after the gate. Startup cost fell in the same window. A
   hook only judges the call in front of it, by keywords and file layout, so it misses some cases.
   Re-task baggage after the gate is 3.7%, not 0, and why is not explained yet. Confidence that the
   hook stops what it targets: **medium**. Confidence in the size of the saving: **low**.
8. **Status.** Kept as a hard gate. Waiting for a re-measure over a longer window.
