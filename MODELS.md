# Which model for a helper

Pick by what the task needs, not by the helper's title. If you're unsure between two models, pick the cheaper one. If it fails or its work bounces at review, re-run that task one level up.

Pick the type the same way: `scout` for lookups, `reviewer` for reviews, `worker` for edits. They start at about 20k context; `general-purpose` starts at 55k because it carries every skill, MCP tool name and the Artifact/Workflow schemas. Use it only when the task needs those.

## haiku (effort low): no judgment needed, and the answer is easy to check
- Find where something is defined or used; list files that match a pattern.
- Read a log or a test report and return the failing test names.
- Status checks: git status, current branch, whether a device is connected, whether the build daemon is up.
- Move or rename files without changing code; regenerate an index.
- Count things: lines, usages, changed snapshots.
- Summarize a short file or a diff in a few lines.
- Check docs or strings for a word your style guide bans.

## sonnet (effort low or medium): routine work with a clear brief
- Mechanical code edits: renames across files, fixing imports after a move, applying a codemod.
- Re-record UI snapshot tests for named tests and report the diff.
- Run the quality gate or the tests, then fix lint and formatting.
- Write tests for code that already works.
- Fix a small bug whose cause is already known.
- Review a routine change: does it match the brief, is there an obvious bug.
- Mockups and screenshot captures of an approved design (effort medium).
- String and translation updates.
- Update docs from facts given in the brief.

## opus (effort medium or high): judgment, design, unknowns
- Design a new feature or screen; architecture and module boundaries.
- A bug with an unknown cause: flaky tests, concurrency, networking.
- Review a tricky change: domain-heavy logic, state machines, migrations, security, money.
- Core domain logic, where the rules or the math are the product.
- Work the owner will judge closely, or a task that already failed on sonnet.
- Write the plan or brief that other helpers will follow.
