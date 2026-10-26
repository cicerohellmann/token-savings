#!/usr/bin/env python3
"""Install or undo the token-savings rules, helper types and helper gate. Standard library only.

usage:
  install.py --scope user [--dry-run]                 your config folder ($CLAUDE_CONFIG_DIR, else ~/.claude)
  install.py --scope project --project DIR [--dry-run]   DIR/CLAUDE.md and DIR/.claude/
  add --undo to remove it again; --config DIR to name the config folder; --replace-agents to overwrite
  worker.md, reviewer.md and scout.md if you already have different ones (default: keep yours)

What it changes:
  CLAUDE.md             appends adopt/CLAUDE-rules.md (one blank line, then the marked block), once
  agents/               worker.md, reviewer.md, scout.md
  hooks/helper_gate.py  a copy, installed only if its tests pass
  settings.json         one PreToolUse entry (matcher Agent|Task); every other key and entry is kept
  hooks/token-savings-install.json   what was there before, so --undo puts it back exactly

--dry-run prints every change and writes nothing.
"""
import argparse, difflib, json, os, shutil, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
RULES = os.path.join(HERE, "CLAUDE-rules.md")
AGENTS = ("worker.md", "reviewer.md", "scout.md")
HOOK = "helper_gate.py"
STATE = "token-savings-install.json"
BEGIN, END = "<!-- token-savings:begin -->", "<!-- token-savings:end -->"


def tilde(path):
    home = os.path.expanduser("~")
    return "~" + path[len(home):] if path.startswith(home + os.sep) else path


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def dump(obj):
    return json.dumps(obj, indent=2, ensure_ascii=False) + "\n"


def diff(old, new, name):
    return "".join(difflib.unified_diff(old.splitlines(True), new.splitlines(True), name, name))


class Plan:
    """Collects changes, prints them, then applies them unless dry-run."""

    def __init__(self, dry, base):
        self.dry, self.steps, self.base = dry, [], base

    def write(self, path, text, why):
        self.steps.append(("write", path, text, why))

    def copy(self, src, path, why):
        self.steps.append(("copy", path, src, why))

    def remove(self, path, why):
        self.steps.append(("remove", path, None, why))

    def rmdir(self, path, why):
        self.steps.append(("rmdir", path, None, why))

    def run(self):
        if not self.steps:
            print("Nothing to change.")
            return
        print(("Would change" if self.dry else "Changing") + ":")
        for op, path, arg, why in self.steps:
            print(f"- {op} {os.path.relpath(path, self.base)}: {why}")
            if self.dry:
                continue
            if op == "write":
                os.makedirs(os.path.dirname(path), exist_ok=True)
                with open(path, "w", encoding="utf-8", newline="") as f:
                    f.write(arg)
            elif op == "copy":
                os.makedirs(os.path.dirname(path), exist_ok=True)
                shutil.copyfile(arg, path)
            elif op == "remove":
                os.remove(path)
            elif op == "rmdir":
                try:
                    os.rmdir(path)
                except OSError:
                    pass
        if self.dry:
            print("\nDry run: nothing written. Run again without --dry-run to apply.")


def config_dir(scope, dest):
    """The hook keeps its state in the config folder of the Claude Code that runs it."""
    if scope == "user":
        return dest
    return os.environ.get("CLAUDE_CONFIG_DIR") or os.path.expanduser("~/.claude")


def hook_command(scope, dest):
    py = "python3" if shutil.which("python3") else sys.executable
    if scope == "project":
        return f'{py} "$CLAUDE_PROJECT_DIR/.claude/hooks/{HOOK}" hook'
    if os.name != "nt" and os.path.abspath(dest) == os.path.abspath(os.path.expanduser("~/.claude")):
        return f'{py} "$HOME/.claude/hooks/{HOOK}" hook'
    return f'{py} "{os.path.join(dest, "hooks", HOOK)}" hook'


def is_gate(entry):
    return any(HOOK in str(h.get("command", "")) for h in entry.get("hooks", []) if isinstance(h, dict))


def tests_pass():
    r = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", os.path.join(HERE, "hooks")],
                       capture_output=True, text=True)
    print("Hook tests: " + ("pass" if r.returncode == 0 else "FAIL\n" + r.stderr[-2000:]))
    return r.returncode == 0


def install(scope, dest, claude_md, plan, replace_agents):
    state = {"dirs": [], "claude_md": None, "settings": None, "agents": []}
    for sub in ("", "agents", "hooks"):
        d = os.path.join(dest, sub) if sub else dest
        if not os.path.isdir(d):
            state["dirs"].append(d)

    # Rules
    block = read(RULES)
    old = read(claude_md) if os.path.exists(claude_md) else None
    if old is not None and BEGIN in old:
        print(f"Rules already in {claude_md}: skipped.")
    else:
        sep = "" if not old else ("\n" if old.endswith("\n") else "\n\n")
        state["claude_md"] = {"existed": old is not None, "sep": sep}
        plan.write(claude_md, (old or "") + sep + block,
                   f"append the token rules ({block.count(chr(10))} lines, between the token-savings markers)")

    # Agents
    for a in AGENTS:
        src, dst = os.path.join(HERE, "agents", a), os.path.join(dest, "agents", a)
        if os.path.exists(dst):
            if read(dst) == read(src):
                print(f"{dst} already installed: skipped.")
                continue
            if not replace_agents:
                print(f"{dst} exists and differs: kept yours (use --replace-agents to overwrite).")
                continue
            state["agents"].append({"name": a, "old": read(dst)})
        else:
            state["agents"].append({"name": a, "old": None})
        plan.copy(src, dst, "helper type " + a[:-3])

    # Hook and settings
    sp = os.path.join(dest, "settings.json")
    old_s = read(sp) if os.path.exists(sp) else None
    try:
        cfg = json.loads(old_s) if old_s and old_s.strip() else {}
    except ValueError:
        sys.exit(f"{sp} is not valid JSON. Fix it first; nothing was changed.")
    pre = cfg.setdefault("hooks", {}).setdefault("PreToolUse", [])
    if any(is_gate(e) for e in pre):
        print(f"Helper gate already in {sp}: skipped.")
    else:
        snippet = json.loads(read(os.path.join(HERE, "hooks", "settings-snippet.json")))
        entry = snippet["hooks"]["PreToolUse"][0]
        entry["hooks"][0]["command"] = hook_command(scope, dest)
        pre.append(entry)
        new_s = dump(cfg)
        state["settings"] = {"old": old_s}
        print(f"settings.json change:\n{diff(old_s or '', new_s, sp)}")
        if plan.dry or tests_pass():
            plan.copy(os.path.join(HERE, "hooks", HOOK), os.path.join(dest, "hooks", HOOK),
                      "the helper gate (a copy; this clone can be moved or deleted)")
            plan.write(sp, new_s, "add the helper gate PreToolUse entry; everything else kept")
        else:
            state["settings"] = None
            print("Hook tests failed: hook not installed. The rules and helper types still help.")

    if plan.steps:
        plan.write(os.path.join(dest, "hooks", STATE), dump(state), "what was there before, for --undo")
    plan.run()
    if plan.steps and not plan.dry:
        config = config_dir(scope, dest)
        print(f"\nDone. Restart Claude Code (or open /hooks) to load it.\n"
              f"Off switch: touch {tilde(os.path.join(config, 'helper-gate', 'off'))}\n"
              f"(The hook keeps its log there too, in your Claude config folder whatever the scope; "
              f"each refusal names the exact path.)")


def undo(scope, dest, claude_md, plan):
    sp_state = os.path.join(dest, "hooks", STATE)
    state = json.loads(read(sp_state)) if os.path.exists(sp_state) else {}

    # Rules: the block, and the separator install added before it
    if os.path.exists(claude_md):
        text = read(claude_md)
        b, e = text.find(BEGIN), text.find(END)
        if b >= 0 and e > b:
            head = text[:b]
            if head.endswith("# Token rules (from the token-savings repo)\n"):  # older layout
                head = head[: -len("# Token rules (from the token-savings repo)\n")]
            tail = text[e + len(END):]
            tail = tail[1:] if tail.startswith("\n") else tail
            info = state.get("claude_md") or {}
            sep = info.get("sep", "\n" if head.endswith("\n\n") else "")
            if sep and head.endswith(sep) and not tail:
                head = head[: -len(sep)]
            new = head + tail
            if not new and info.get("existed") is False:
                plan.remove(claude_md, "only the token rules were in it")
            else:
                plan.write(claude_md, new, "remove the token rules block")

    # Agents: remove ours, put back the ones --replace-agents overwrote
    olds = {a["name"]: a["old"] for a in state.get("agents", [])}
    for a in AGENTS:
        dst = os.path.join(dest, "agents", a)
        if not os.path.exists(dst):
            continue
        if read(dst) != read(os.path.join(HERE, "agents", a)):
            print(f"{dst} was edited after install: kept. Delete it yourself if you want it gone.")
        elif olds.get(a):
            plan.write(dst, olds[a], "put back your earlier " + a)
        elif a in olds or not state:
            plan.remove(dst, "helper type " + a[:-3])

    # Hook
    hp = os.path.join(dest, "hooks", HOOK)
    if os.path.exists(hp):
        plan.remove(hp, "the helper gate")

    # Settings: drop only the helper gate entry
    sp = os.path.join(dest, "settings.json")
    if os.path.exists(sp):
        try:
            cfg = json.loads(read(sp))
        except ValueError:
            sys.exit(f"{sp} is not valid JSON. Fix it first; nothing was changed.")
        pre = cfg.get("hooks", {}).get("PreToolUse")
        if isinstance(pre, list) and any(is_gate(e) for e in pre):
            cfg["hooks"]["PreToolUse"] = [x for x in pre if not is_gate(x)]
            if not cfg["hooks"]["PreToolUse"]:
                del cfg["hooks"]["PreToolUse"]
            if not cfg["hooks"]:
                del cfg["hooks"]
            old_s = (state.get("settings") or {}).get("old", False)
            if old_s is None and not cfg:
                plan.remove(sp, "only the helper gate was in it")
            else:
                same = old_s and json.loads(old_s) == cfg
                new_s = old_s if same else dump(cfg)
                print(f"settings.json change:\n{diff(read(sp), new_s, sp)}")
                plan.write(sp, new_s, "remove the helper gate entry; everything else kept")

    if os.path.exists(sp_state):
        plan.remove(sp_state, "install record")
    for d in sorted(state.get("dirs", []) or [os.path.join(dest, "agents"), os.path.join(dest, "hooks")],
                    key=len, reverse=True):
        if os.path.isdir(d):
            plan.rmdir(d, "if empty")
    plan.run()
    logs = os.path.join(config_dir(scope, dest), "helper-gate")
    if os.path.isdir(logs):
        print(f"\nThe hook's log folder {tilde(logs)} is left; delete it if you want.")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--scope", choices=("user", "project"), required=True)
    ap.add_argument("--project", help="project folder (scope project)")
    ap.add_argument("--config", help="config folder (scope user; default $CLAUDE_CONFIG_DIR, else ~/.claude)")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--undo", action="store_true")
    ap.add_argument("--replace-agents", action="store_true")
    o = ap.parse_args()
    if o.scope == "project":
        if not o.project:
            ap.error("--scope project needs --project DIR")
        proj = os.path.abspath(os.path.expanduser(o.project))
        if not os.path.isdir(proj):
            ap.error(f"no such folder: {proj}")
        dest, claude_md = os.path.join(proj, ".claude"), os.path.join(proj, "CLAUDE.md")
    else:
        dest = os.path.abspath(os.path.expanduser(
            o.config or os.environ.get("CLAUDE_CONFIG_DIR") or "~/.claude"))
        claude_md = os.path.join(dest, "CLAUDE.md")
    base = os.path.dirname(claude_md)
    print(f"Target: {tilde(base)} (paths below are relative to it)")
    plan = Plan(o.dry_run, base)
    if o.undo:
        undo(o.scope, dest, claude_md, plan)
    else:
        install(o.scope, dest, claude_md, plan, o.replace_agents)


if __name__ == "__main__":
    main()
