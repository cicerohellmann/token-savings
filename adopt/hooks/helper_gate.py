#!/usr/bin/env python3
"""Helper gate: a PreToolUse hook on Agent and Task (matcher "Agent|Task").

What it does, first match wins:
  Agent/Task without `model`               refused, with a short guide to pick one
                                           (also without `effort` if REQUIRE_EFFORT is on; off by default)
  Agent/Task otherwise                     `name` and `team_name` stripped (an unnamed helper ends
                                           when it reports); if REROUTE is on (off by default), reviews
                                           are lowered to sonnet/medium and lookups to haiku/low
  SendMessage to one of this chat's own    opt-in (RETASK_CHECK = True, and add SendMessage to the
  helpers                                  matcher): refused if the helper is above REUSE_CTX context,
                                           or is a reviewer: open a fresh helper instead
Forks (subagent_type "fork") pass untouched; they run on the parent's model.

Off switch: create the file OFF (default <config>/helper-gate/off). It turns the whole hook off.
Every decision is one line in LOG (default <config>/helper-gate/decisions.jsonl).
Fails open: any error lets the call through and is written to ERRLOG.
<config> is $CLAUDE_CONFIG_DIR if set, else ~/.claude. Set HELPER_GATE_HOME to move all three files.
Standard library only, Python 3.9+.

usage: helper_gate.py hook   (reads the hook JSON on stdin)
"""
import glob, json, os, re, sys, time

CONFIG = os.environ.get("CLAUDE_CONFIG_DIR") or os.path.expanduser("~/.claude")
HOME = os.environ.get("HELPER_GATE_HOME") or os.path.join(CONFIG, "helper-gate")
OFF = os.path.join(HOME, "off")
LOG = os.path.join(HOME, "decisions.jsonl")
ERRLOG = os.path.join(HOME, "errors.log")

REUSE_CTX = 100_000   # re-tasking a helper above this context is refused
REQUIRE_EFFORT = False  # True: also refuse a helper opened without `effort` (older Claude Code has none)
RETASK_CHECK = False  # True: check SendMessage re-tasks; reads undocumented transcript paths
REROUTE = False       # True: lower reviews to sonnet/medium and lookups to haiku/low (never raised)
NAME_KEYS = ("name", "team_name")
TAIL = 400_000        # bytes read per step when looking backward for a helper's last call

def tilde(path):
    home = os.path.expanduser("~")
    return "~" + path[len(home):] if path.startswith(home + os.sep) else path


OFF_NOTE = " (token-savings helper gate; turn off: touch {})"
GUIDE = ("Helper not opened: set `model` for this task, then call Agent again with the same "
         "prompt. Choose by what the task needs:\n"
         "- haiku: lookups, greps, status checks, reading logs, counting\n"
         "- sonnet: routine work with a clear brief (renames, codemods, tests, normal reviews)\n"
         "- opus: judgment (design, bugs with an unknown cause, tricky reviews)")
GUIDE_EFFORT = (GUIDE.replace("set `model`", "set `model` and `effort`")
                + "\nEffort: low for haiku, low or medium for sonnet, medium or high for opus.")
RETASK = ("Helper not re-tasked: {why}. Open a fresh helper with a short brief (Agent, with a model) "
          "instead. One task per helper.")

MODEL_RANK = {"haiku": 0, "sonnet": 1, "opus": 2}
EFFORT_RANK = {"low": 0, "medium": 1, "high": 2, "xhigh": 3, "max": 4}

# A reviewer or signer, by type, name or description. Whole words: "preview", "design", "signal" don't count.
REVIEWER = re.compile(r"(?<![a-z])(review(s|ed|er|ers|ing)?|re-?sign(s|ed|ing)?|sign-?off|signer|signers"
                      r"|re-?check(s|ed|ing)?|verif(y|ies|ied|ier|ying)|audit(s|ed|or|ing)?|land/hold)(?![a-z])", re.I)
# A lookup leads with its verb: "Count failing tests" is one, "Fix the count label" is not.
LOOKUP = re.compile(r"^\W*(find|list|count|grep|look ?up|locate|search|read (the )?logs?|which|where"
                    r"|status (of|check))\b", re.I)
WORK = re.compile(r"\b(build|fix|fixes|fixing|tests?|implement|write|edit|add|refactor|create|change|update"
                  r"|migrate|commit|rename|design|debug|investigate|unknown|diagnose|why|bugs?|crash\w*"
                  r"|fail\w*|flak\w*|broken|errors?|plan|architecture)\b", re.I)
THEN_WORK = re.compile(r"\b(and|then)\s+(fix|build|implement|write|edit|add|refactor)\b", re.I)


def is_review(desc):
    """"Review the login fix" is a review; "Fix X and verify tests" and "Verify and fix Y" are not."""
    r = REVIEWER.search(desc)
    if not r:
        return False
    w = WORK.search(desc)
    return not w or (r.start() < w.start() and not THEN_WORK.search(desc))


def log(path, row):
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "a") as f:
            f.write((json.dumps(row) if isinstance(row, dict) else row) + "\n")
    except Exception:
        pass


def deny(reason):
    reason += OFF_NOTE.format(tilde(OFF))
    return {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                   "permissionDecisionReason": reason}}


# ---- Agent / Task --------------------------------------------------------------------------------------

def family(model):
    m = str(model or "").lower()
    return next((k for k in MODEL_RANK if k in m), None)


def lower(asked_model, asked_effort, model, effort):
    """The rule's model and effort, but never above what was asked."""
    a = family(asked_model)
    if a is None or MODEL_RANK[a] < MODEL_RANK[model]:
        model = asked_model
    if asked_effort is None:
        effort = None
    elif (asked_effort not in EFFORT_RANK or EFFORT_RANK[asked_effort] < EFFORT_RANK[effort]):
        effort = asked_effort
    return model, effort


def reroute(inp):
    """(rule, model, effort) for an Agent call that has a model and an effort."""
    kind = inp.get("subagent_type") or "general-purpose"
    desc, name = str(inp.get("description") or ""), str(inp.get("name") or "")
    model, effort = inp.get("model"), inp.get("effort")
    if not REROUTE:
        return "pass", model, effort
    if kind == "reviewer" or REVIEWER.search(name) or is_review(desc):
        return ("review",) + lower(model, effort, "sonnet", "medium")
    if kind == "scout" or (LOOKUP.search(desc) and not WORK.search(desc)):
        return ("lookup",) + lower(model, effort, "haiku", "low")
    return "pass", model, effort


def agent_event(ev, inp):
    kind = inp.get("subagent_type") or "general-purpose"
    row = {"t": time.time(), "session": ev.get("session_id"), "tool": ev.get("tool_name"), "type": kind,
           "description": inp.get("description"), "name": inp.get("name"),
           "asked_model": inp.get("model"), "asked_effort": inp.get("effort")}
    if kind == "fork":
        log(LOG, dict(row, decision="fork"))
        return None
    if not inp.get("model") or (REQUIRE_EFFORT and not inp.get("effort")):
        log(LOG, dict(row, decision="deny-no-model"))
        return deny(GUIDE_EFFORT if REQUIRE_EFFORT else GUIDE)
    rule, model, effort = reroute(inp)
    unnamed = {k: v for k, v in inp.items() if k not in NAME_KEYS}
    stripped = unnamed != inp
    changed = (model, effort) != (inp.get("model"), inp.get("effort"))
    log(LOG, dict(row, decision=rule, model=model, effort=effort, changed=changed, stripped=stripped))
    if not changed and not stripped:
        return None
    why = "Helper gate."
    if changed:
        why += f" {rule}: {inp.get('model')}/{inp.get('effort')} -> {model}/{effort}."
    if stripped:
        why += " Name removed: unnamed helpers end when they report."
    return {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "allow",
                                   "permissionDecisionReason": why,
                                   "updatedInput": dict(unnamed, model=model, **({"effort": effort} if effort else {}))}}


# ---- SendMessage ---------------------------------------------------------------------------------------

def usage_ctx(line):
    """Context of one transcript line's API call (input + cache), or 0."""
    if '"usage"' not in line:
        return 0
    try:
        u = json.loads(line)["message"]["usage"]
        return sum(int(u.get(k) or 0) for k in
                   ("input_tokens", "cache_read_input_tokens", "cache_creation_input_tokens"))
    except Exception:
        return 0


def context_of(jsonl):
    """Context of a helper's last API call, read backward from the end of its transcript."""
    try:
        with open(jsonl, "rb") as f:
            end, carry = f.seek(0, 2), b""
            while end > 0:
                start = max(0, end - TAIL)
                f.seek(start)
                lines = (f.read(end - start) + carry).split(b"\n")
                carry = lines.pop(0) if start > 0 else b""
                for line in reversed(lines):
                    ctx = usage_ctx(line.decode(errors="ignore"))
                    if ctx:
                        return ctx
                end = start
    except Exception:
        pass
    return 0


def first_time(jsonl):
    try:
        with open(jsonl, errors="ignore") as f:
            for _ in range(5):
                try:
                    ts = json.loads(f.readline()).get("timestamp")
                    if ts:
                        return ts  # ISO 8601 strings sort in time order
                except Exception:
                    continue
    except Exception:
        pass
    return ""


def recipient(to):
    """A SendMessage target without a " [ref]" suffix, "@" or spaces, lower case."""
    if not isinstance(to, str):
        return ""
    return re.sub(r"\s*\[[^\]]*\]\s*$", "", to.strip()).lstrip("@").strip().lower()


def own_helper(transcript, to):
    """This chat's helper that `to` names (its name or agent id); the newest one if a name was reused.
    Relies on Claude Code's layout <transcript>/subagents/agent-<id>.meta.json; if that changes, nothing
    is found and the call passes."""
    best = None
    for meta in glob.glob(transcript[:-len(".jsonl")] + "/subagents/agent-*.meta.json"):
        aid = os.path.basename(meta)[len("agent-"):-len(".meta.json")]
        try:
            with open(meta) as f:
                m = json.load(f)
        except Exception:
            m = {}
        if not isinstance(m, dict):
            m = {}
        if to not in {str(x).lower() for x in (m.get("name"), aid, "agent-" + aid) if x}:
            continue
        jsonl = meta[:-len(".meta.json")] + ".jsonl"
        key = (first_time(jsonl), os.path.getmtime(jsonl) if os.path.exists(jsonl) else 0)
        if best is None or key > best[0]:
            best = (key, dict(m, jsonl=jsonl))
    return best[1] if best else None


def is_reviewer(m):
    types = (m.get("agentType"), m.get("customAgentType"), m.get("spawnedAgentType"))
    if any(str(t or "").lower() == "reviewer" for t in types):
        return True
    return bool(REVIEWER.search(f"{m.get('name') or ''} {m.get('description') or ''}"))


def send_event(ev, inp):
    if not RETASK_CHECK:
        return None
    if not isinstance(inp.get("message"), str):
        return None  # protocol replies (shutdown, plan approval) pass
    to = recipient(inp.get("to") or inp.get("recipient"))
    transcript = ev.get("transcript_path")
    if not to or to == "*" or not isinstance(transcript, str) or not transcript.endswith(".jsonl"):
        return None
    m = own_helper(transcript, to)
    if not m:
        return None  # the lead, a peer chat, or someone else's helper
    ctx = context_of(m["jsonl"])
    why = None
    if ctx > REUSE_CTX:
        why = f"it is already at {ctx // 1000}k context (limit {REUSE_CTX // 1000}k)"
    elif is_reviewer(m):
        why = "it is a reviewer, and every review gets a fresh one"
    log(LOG, {"t": time.time(), "session": ev.get("session_id"), "tool": "SendMessage", "to": inp.get("to"),
              "ctx": ctx, "decision": "deny-retask" if why else "allow-retask"})
    return deny(RETASK.format(why=why)) if why else None


# ---- entry ---------------------------------------------------------------------------------------------

def hook_event(ev):
    """The hook's answer for one event (a dict), or None to let the call through untouched."""
    if not isinstance(ev, dict) or os.path.exists(OFF):
        return None
    inp = ev.get("tool_input")
    if not isinstance(inp, dict):
        return None
    if ev.get("tool_name") in ("Agent", "Task"):
        return agent_event(ev, inp)
    if ev.get("tool_name") == "SendMessage":
        return send_event(ev, inp)
    return None


def main():
    try:
        out = hook_event(json.load(sys.stdin))
    except Exception as e:
        log(ERRLOG, f"{time.strftime('%Y-%m-%d %H:%M:%S')} let through: {e!r}"[:400])
        return
    if out:
        print(json.dumps(out))


if __name__ == "__main__":
    if sys.argv[1:] == ["hook"]:
        main()
    else:
        sys.exit(__doc__)
