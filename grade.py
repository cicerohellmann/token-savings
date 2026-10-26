#!/usr/bin/env python3
"""Grade your Claude Code token spend, red to green. Deterministic, stdlib only, no model calls.

Reads only Claude Code transcripts ($CLAUDE_CONFIG_DIR/projects, else ~/.claude/projects, or --root). Each check estimates the share
of spend that a lab rule would have saved. The rubric, the reasons and the cures: GRADES.md.

usage:
  grade.py                         last 7 days
  grade.py --days 14
  grade.py --since 2026-10-09 --until 2026-10-10   (local time)
  grade.py --repo ~/code/app:main  also count landed commits per $ (ungraded, repeatable)
  grade.py --json                  machine-readable
"""
import argparse, collections, datetime as dt, glob, json, os, re, subprocess, sys

# $ per million tokens at API list price: input, output, cache read, cache write 5m, cache write 1h
P = {'opus': (5, 25, .5, 6.25, 10), 'sonnet': (3, 15, .3, 3.75, 6), 'haiku': (1, 5, .1, 1.25, 2)}
SHARE = (2, 5)       # a check: green below 2% of spend avoidable, red above 5%
OVERALL = (10, 20)   # all checks together: green below 10%, red above 20%
RETASK_CTX = 100e3   # re-tasking a helper above this is against the rules
STARTUP = 15e3       # a lean helper starts near 10k; anything above 15k is startup tax
BIG_OUT = 10e3       # tool output above this many tokens is "big"; the part above KEEP is avoidable
KEEP = 2e3
HOT_CTX = 80e3       # a machine wake (loop, monitor, notification) at this context is hot
WATCHER = 30e3       # what a small watcher would carry instead
BLOAT = 150e3        # main-chat context above this is carried, not used
REWRITE = 30e3       # a cache write this big after the cache expired is a full rewrite
LOOKUP = r'\b(find|locate|list|count|grep|lookup|look up|where|scan|inventory|status|summar|read (the )?log|check (if|whether))'
JUDGE = r'\b(design|architect|investigat|debug|flaky|plan|spec|research|implement|feature|build|rewrite|root cause|why|review)'
CHECKS = [
    ('retask', 're-task baggage', 'helpers re-tasked carry earlier tasks on every step'),
    ('startup', 'startup tax', 'helpers start with more than ~15k of tools and instructions'),
    ('model', 'model fit', 'opus helpers doing lookups a haiku could do'),
    ('hot', 'hot wakes', 'loops, monitors and notifications wake big chats'),
    ('rewrite', 'cache rewrites', 'machine wakes after the cache expired write it all again'),
    ('bigout', 'big tool outputs', 'large outputs stay in context and are re-read on every step'),
    ('bloat', 'bloated chats', 'main chats run above 150k instead of compacting at a pause'),
]


def fam(m):
    m = m or ''
    return next((k for k in P if k in m), None if 'synthetic' in m else 'opus')


def text_of(c):
    if isinstance(c, str): return c
    if isinstance(c, list): return ' '.join((b.get('text') or '') for b in c if isinstance(b, dict) and b.get('type') == 'text')
    return ''


def trig(s):
    """What started a turn: 'human' or a machine trigger."""
    s = re.sub(r'^\s*<system-reminder[^>]*>\s*', '', s or '')
    if s.startswith(('<task-notification', '<scheduled', '# /loop', '<<autonomous-loop')) or 'ScheduleWakeup' in s[:200]: return 'wake'
    if s.startswith(('<teammate-message', '<agent-message', '<cross-session-message', 'Another Claude session')): return 'message'
    if s.startswith('This session is being continued'): return 'compaction'
    if s.startswith(('<command-', '<local-command', 'Base directory for this skill', '[Request interrupted')): return 'command'
    return 'human'


def stamp(ts): return dt.datetime.fromisoformat(ts.replace('Z', '+00:00')).timestamp()


def scan(path, lo, hi):
    """One transcript -> list of requests in [lo, hi) with avoidable $ per check, plus facts."""
    helper = '/subagents/' in path
    meta = {}
    if helper:
        try: meta = json.load(open(path[:-6] + '.meta.json'))
        except Exception: pass
    F = dict(path=path, helper=helper, meta=meta, title=meta.get('description'), cwd=None, reqs=[])
    seen = set(); base = None; seg = 0; seg_carry = 0; called = False; idle = True
    turn = 'human'; prev_t = None; live = []  # live: [excess tokens of big outputs not yet compacted]
    try: fh = open(path, errors='ignore')
    except Exception: return F
    for l in fh:
        head = l[:300]
        if '"queued_command"' in head:
            try: a = json.loads(l).get('attachment') or {}
            except Exception: continue
            t = trig(text_of(a.get('prompt')))
            if called and idle and t in ('human', 'message', 'wake'):
                turn = t
                if helper: seg += 1; seg_carry = None
            continue
        if '"custom-title"' in head[:60] or '"agent-name"' in head[:60]:
            try: d = json.loads(l); F['name'] = d.get('customTitle') or d.get('agentName') or F.get('name')
            except Exception: pass
            continue
        if '"usage"' not in l and '"type":"user"' not in l: continue
        try: d = json.loads(l)
        except Exception: continue
        F['cwd'] = F['cwd'] or d.get('cwd')
        m = d.get('message') or {}
        if d.get('type') == 'user':
            c = m.get('content')
            if isinstance(c, list) and any(isinstance(b, dict) and b.get('type') == 'tool_result' for b in c):
                for b in c:
                    if not isinstance(b, dict) or b.get('type') != 'tool_result': continue
                    rt = text_of(b.get('content')) if isinstance(b.get('content'), list) else str(b.get('content') or '')
                    if len(rt) / 4 > BIG_OUT: live.append(len(rt) / 4 - KEEP)
                continue
            if d.get('isMeta'): continue
            s = text_of(c)
            t = 'wake' if 'scheduledTaskId' in l[:3000] else trig(s)
            if t == 'compaction' or d.get('isCompactSummary'): live = []; continue
            if t == 'command': continue
            if F['title'] is None and t == 'human' and not helper: F['title'] = s.strip()[:60]
            turn = t
            if helper and called and t in ('human', 'message', 'wake'): seg += 1; seg_carry = None
            continue
        u = m.get('usage')
        if not u or m.get('id') in seen: continue
        seen.add(m.get('id'))
        f = fam(m.get('model'))
        if f is None: continue
        waited = not idle
        idle = not any(isinstance(b, dict) and b.get('type') == 'tool_use' for b in (m.get('content') or []))
        ts = d.get('timestamp') or ''
        i, o, cr, cw = (u.get(k, 0) or 0 for k in ('input_tokens', 'output_tokens', 'cache_read_input_tokens', 'cache_creation_input_tokens'))
        w1h = ((u.get('cache_creation') or {}).get('ephemeral_1h_input_tokens') or 0)
        ctx = i + cr + cw; p = P[f]
        t = stamp(ts) if ts else 0
        gap = t - prev_t if prev_t else 0; prev_t = t
        if base is None: base = ctx
        if seg_carry is None: seg_carry = max(0, ctx - base) if ctx > RETASK_CTX else 0
        seg_carry = min(seg_carry, max(0, ctx - base))  # compaction shrinks what is carried
        first, called = not called, True
        if not (lo <= ts < hi): continue
        cost = (i * p[0] + o * p[1] + cr * p[2] + (cw - w1h) * p[3] + w1h * p[4]) / 1e6
        rd = p[2] / 1e6
        a = collections.Counter()
        if helper:
            if seg and seg_carry: a['retask'] = seg_carry * rd
            a['startup'] = max(0, min(base, ctx) - STARTUP) * rd
            desc = (meta.get('description') or '').lower()
            if f == 'opus' and re.search(LOOKUP, desc) and not re.search(JUDGE, desc): a['model'] = cost * (1 - P['haiku'][0] / P['opus'][0])
        else:
            if turn == 'wake' and ctx > HOT_CTX: a['hot'] = (ctx - WATCHER) * rd
            if ctx > BLOAT and turn != 'wake': a['bloat'] = (ctx - BLOAT) * rd
        ttl = 3600 if w1h > cw / 2 else 300
        if cw > REWRITE and cw > ctx / 2 and gap > ttl and (helper or turn != 'human'):
            a['rewrite_tool' if waited else 'rewrite_wake'] = 1
            a['rewrite'] = (cw - w1h) * (p[3] - p[2]) / 1e6 + w1h * (p[4] - p[2]) / 1e6
        if live and not first: a['bigout'] = min(sum(live), ctx) * rd
        F['reqs'].append((ts, cost, a, ctx, first))
    return F


def landed(repo, branch, lo, hi):
    """Commits (no merges) that reached `branch` with a commit date in [lo, hi)."""
    r = subprocess.run(['git', '-C', repo, 'rev-list', '--count', '--no-merges', f'--since={lo}Z', f'--until={hi}Z', branch],
                       capture_output=True, text=True)
    return int(r.stdout.strip()) if r.returncode == 0 else None


def chat_key(F, root):
    """Helpers count under the chat that opened them."""
    rel = os.path.relpath(F['path'], root).split(os.sep)
    return rel[0] + '/' + rel[1].replace('.jsonl', '')


def chat_name(F, root):
    proj = os.path.basename((F['cwd'] or '').rstrip('/')) or chat_key(F, root).split('/')[0]
    title = (F.get('name') or F['title'] or '').replace('\n', ' ')[:40]
    return f"{proj}/{chat_key(F, root).split('/')[1][:8]} {title}".strip()


def color(x, cut): return 'GREEN' if x < cut[0] else 'RED' if x > cut[1] else 'YELLOW'


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--days', type=float, default=7)
    ap.add_argument('--since'); ap.add_argument('--until')
    ap.add_argument('--root', default=os.path.join(os.environ.get('CLAUDE_CONFIG_DIR') or os.path.expanduser('~/.claude'), 'projects'))
    ap.add_argument('--repo', action='append', default=[], help='PATH[:BRANCH], repeatable; branch defaults to main')
    ap.add_argument('--json', action='store_true')
    o = ap.parse_args()
    now = dt.datetime.now(dt.timezone.utc)
    local = lambda x: dt.datetime.fromisoformat(x).astimezone(dt.timezone.utc)  # --since/--until are local time
    hi_d = local(o.until) if o.until else now
    lo_d = local(o.since) if o.since else hi_d - dt.timedelta(days=o.days)
    iso = lambda x: x.strftime('%Y-%m-%dT%H:%M:%S')
    lo, hi = iso(lo_d), iso(hi_d)
    files = glob.glob(o.root + '/*/*.jsonl') + glob.glob(o.root + '/*/*/subagents/*.jsonl')
    chats = [scan(f, lo, hi) for f in files if os.path.getmtime(f) >= lo_d.timestamp()]
    chats = [F for F in chats if F['reqs']]
    total = sum(r[1] for F in chats for r in F['reqs'])
    if not total:
        print(f'No Claude Code requests found in {o.root} between {lo} and {hi}. Nothing to grade.'
              ' (Claude Code deletes transcripts after 30 days by default; --root PATH reads another folder.)'); return
    by = {k: 0.0 for k, _, _ in CHECKS}; top = {k: collections.Counter() for k in by}; avoid = 0.0
    names = {chat_key(F, o.root): chat_name(F, o.root) for F in chats if not F['helper']}
    rw = collections.Counter()
    for F in chats:
        name = names.get(chat_key(F, o.root)) or chat_name(F, o.root)
        for ts, cost, a, ctx, first in F['reqs']:
            for k in ('rewrite_tool', 'rewrite_wake'):
                if a.pop(k, 0): rw[k] += a['rewrite']
            for k, v in a.items(): by[k] += v; top[k][name] += v
            avoid += min(cost, sum(a.values()))  # checks can overlap on one request; never count more than it cost
    helpers = [F for F in chats if F['helper']]
    hs = sum(r[1] for F in helpers for r in F['reqs'])
    starts = sorted(F['reqs'][0][3] for F in helpers if F['reqs'][0][4])
    nomodel = sum(1 for F in helpers if F['meta'] and not F['meta'].get('model'))
    res = dict(window=[lo, hi], spend_usd=round(total, 2), helper_share=round(100 * hs / total, 1), chats=len(chats) - len(helpers),
               helpers=len(helpers), requests=sum(len(F['reqs']) for F in chats), avoidable_usd=round(avoid, 2),
               avoidable_pct=round(100 * avoid / total, 1), grade=color(100 * avoid / total, OVERALL),
               rewrite_after_tool_usd=round(rw['rewrite_tool'], 2), rewrite_after_wake_usd=round(rw['rewrite_wake'], 2),
               median_helper_start=int(starts[len(starts) // 2]) if starts else None, helpers_without_model=nomodel, checks=[], work=[])
    for k, label, why in CHECKS:
        pct = 100 * by[k] / total
        res['checks'].append(dict(key=k, label=label, why=why, usd=round(by[k], 2), pct=round(pct, 1), grade=color(pct, SHARE),
                                  top=[(n, round(v, 2)) for n, v in top[k].most_common(3) if v > 0]))
    for spec in o.repo:
        path, _, branch = spec.partition(':')
        path = os.path.abspath(os.path.expanduser(path)); branch = branch or 'main'
        mine = [F for F in chats if (F['cwd'] or '').startswith(path)]
        n = landed(path, branch, lo, hi)
        usd = sum(r[1] for F in mine for r in F['reqs'])
        res['work'].append(dict(repo=path, branch=branch, usd=round(usd, 2), landed=n,
                                usd_per_landed=round(usd / n, 2) if n else None))
    if o.json:
        print(json.dumps(res, indent=1)); return
    show = lambda x: x.astimezone().strftime('%Y-%m-%d %H:%M')
    print(f"Token spend grade, {show(lo_d)} to {show(hi_d)} local time")
    print(f"Spend ${total:,.0f} (API list-price equivalent, not your bill). {res['chats']} chats, {res['helpers']} helpers "
          f"({res['helper_share']:.0f}% of spend), {res['requests']:,} requests.")
    print(f"\nOVERALL {res['grade']}: about {res['avoidable_pct']:.0f}% (${avoid:,.0f}) looks avoidable. "
          f"Green below {OVERALL[0]}%, red above {OVERALL[1]}%.\n")
    print(f"{'check':<18}{'grade':<8}{'avoidable':>11}{'share':>8}   rubric")
    for c in res['checks']:
        print(f"{c['label']:<18}{c['grade']:<8}{'$' + format(c['usd'], ',.0f'):>11}{c['pct']:>7.1f}%   GRADES.md#{c['key']}")
    print(f"\n(A check is green below {SHARE[0]}% of spend, red above {SHARE[1]}%. Checks overlap; the overall share counts each request once.)")
    if res['median_helper_start']: print(f"Median helper starts at {res['median_helper_start'] / 1e3:.0f}k context. {nomodel} helpers were opened without a model.")
    if by['rewrite']: print(f"Cache rewrites: ${rw['rewrite_tool']:,.0f} after waiting on a long tool (builds, tests), ${rw['rewrite_wake']:,.0f} after a wake or a new message.")
    bad = [c for c in res['checks'] if c['grade'] != 'GREEN' and c['top']]
    if bad: print('\nWhere it comes from (helpers counted under the chat that opened them):')
    for c in bad:
        print(f"  {c['label']}: " + '; '.join(f"{n} ${v:,.0f}" for n, v in c['top']))
    for w in res['work']:
        if w['landed'] is None: print(f"\nWork: can't read branch {w['branch']} in {w['repo']}."); continue
        per = f"${w['usd_per_landed']:.2f} per landed commit" if w['usd_per_landed'] else 'no commits landed'
        print(f"\nWork (ungraded, see GRADES.md#work): {os.path.basename(w['repo'])}@{w['branch']}: ${w['usd']:,.0f} spent in chats under this repo, "
              f"{w['landed']} commits landed, {per}.")


if __name__ == '__main__':
    main()
