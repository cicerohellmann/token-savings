<!-- token-savings:begin -->
# Token rules (from the token-savings repo)

Every step re-sends the whole conversation: cost is context × steps × model price.

## Helpers (subagents)

1. **One task per helper.** Give each new task a fresh helper with a full brief. Re-task one only when its old context helps the next task, and never when it is above about 100k.
2. **Model and effort by task.** haiku (low effort) for lookups, greps, status, logs, counting. sonnet (low or medium) for routine work with a clear brief: renames, codemods, tests, normal reviews. opus for judgment: design, unknown bugs, tricky reviews. Always set the model (and the effort, if your Claude Code has that field) when you open a helper. If a cheaper helper fails, re-run the task one level up.
3. **Lean helper types.** Use `worker` (coding), `reviewer` (read-only, answers LAND or HOLD) or `scout` (lookups). They start near 10k context. Use `general-purpose` only when the task needs web, artifacts, skills or its own helpers.
4. **Batch commands.** Put related greps and reads in one call.
5. **Keep helpers small.** Brief them with paths and a one-line goal. Read big output through `tail`/`grep`. End with a few-line result.
6. **Parallel, not on one gate.** Don't run more helpers than the shared lock (build, device, push) can serve. Helpers waiting on a lock sit on their context, and the cache expires while they wait.
7. **Keep your main chat small.** It coordinates and doesn't code. Keep loop state in a file and compact at a pause.
8. **Open helpers without a name.** Leave out `name` when you call `Agent`. An unnamed helper closes when it reports and frees its memory; a named one stays open until shut down. (Effect on tokens: not measured; it works indirectly, since an unnamed helper can't be re-tasked.) For the next task, open a fresh one.

## Watchers, loops and heartbeats (only if you use loops, /loop, ScheduleWakeup or Monitor)

Every wake (cron, `ScheduleWakeup`, a `Monitor` line, a task notification) re-reads the whole chat.

- The monitor's filter decides: it prints only lines you must act on.
- Heartbeats at least 30 min apart, unless you ask for more.
- Stop watching when the work stops, is done or waits on you.
- Never watch from a chat above about 100k. Write state to a file and hand the watching to a small helper, or compact first.
<!-- token-savings:end -->
