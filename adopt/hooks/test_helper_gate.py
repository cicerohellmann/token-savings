"""Tests for helper_gate.py. Run from the repo root: python3 -m unittest discover -s adopt/hooks -v
Everything runs in a temp folder; your real ~/.claude is never read or written."""
import json, os, subprocess, sys, tempfile, unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import helper_gate as g  # noqa: E402


class GateTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = self.tmp.name
        self.setUp_paths()
        self.transcript = os.path.join(root, "projects", "-proj", "chat1.jsonl")
        os.makedirs(self.transcript[:-6] + "/subagents")
        open(self.transcript, "w").close()

    def setUp_paths(self):
        g.HOME = os.path.join(self.tmp.name, "state")
        g.OFF, g.LOG, g.ERRLOG = (os.path.join(g.HOME, n) for n in ("off", "decisions.jsonl", "errors.log"))
        g.REROUTE = True
        g.RETASK_CHECK = True
        g.REQUIRE_EFFORT = False

    def tearDown(self):
        self.tmp.cleanup()

    def helper(self, aid, ctx, name=None, kind="worker", description="", ts="2026-10-25T10:00:00Z"):
        base = os.path.join(self.transcript[:-6], "subagents", "agent-" + aid)
        with open(base + ".meta.json", "w") as f:
            json.dump({"agentType": kind, "name": name, "description": description}, f)
        with open(base + ".jsonl", "w") as f:
            f.write(json.dumps({"type": "assistant", "timestamp": ts, "message": {"usage": {
                "input_tokens": 10, "cache_read_input_tokens": ctx - 10, "cache_creation_input_tokens": 0}}}) + "\n")

    def agent(self, **inp):
        return g.hook_event({"tool_name": "Agent", "tool_input": dict({"prompt": "p"}, **inp),
                             "transcript_path": self.transcript})

    def send(self, to, message="next task"):
        return g.hook_event({"tool_name": "SendMessage", "tool_input": {"to": to, "message": message},
                             "transcript_path": self.transcript})

    def decision(self, out):
        return out and out["hookSpecificOutput"]["permissionDecision"]

    # Agent
    def test_reroute_is_off_by_default(self):
        import importlib
        self.assertFalse(importlib.reload(g).REROUTE)
        self.setUp_paths()

    def test_following_the_guide_passes(self):
        for model, effort in (("haiku", "low"), ("sonnet", "low"), ("sonnet", "medium"),
                              ("opus", "medium"), ("opus", "high")):
            self.assertIn(model, g.GUIDE)
            self.assertNotEqual(self.decision(self.agent(model=model, effort=effort, description="Add login form")),
                                "deny")

    def test_no_model_is_refused(self):
        self.assertEqual(self.decision(self.agent(effort="low", description="Add login form")), "deny")

    def test_no_effort_passes_by_default(self):
        self.assertIsNone(self.agent(model="sonnet", description="Add login form"))

    def test_no_effort_refused_when_required(self):
        g.REQUIRE_EFFORT = True
        self.assertEqual(self.decision(self.agent(model="sonnet", description="Add login form")), "deny")

    def test_refusal_names_the_off_switch(self):
        out = self.agent(description="Add login form")
        self.assertIn("touch " + g.OFF, out["hookSpecificOutput"]["permissionDecisionReason"])

    def test_reroute_without_effort_adds_none(self):
        new = self.agent(model="opus", description="Review the login fix")["hookSpecificOutput"]["updatedInput"]
        self.assertEqual((new["model"], "effort" in new), ("sonnet", False))

    def test_retask_check_is_off_by_default(self):
        import importlib
        self.assertFalse(importlib.reload(g).RETASK_CHECK)
        self.setUp_paths()

    def test_fork_passes_without_model(self):
        self.assertIsNone(self.agent(subagent_type="fork", description="Add login form"))

    def test_plain_call_passes_untouched(self):
        self.assertIsNone(self.agent(model="opus", effort="high", description="Design the sync layer"))

    def test_name_is_stripped_and_rest_kept(self):
        out = self.agent(model="opus", effort="high", description="Design the sync layer", name="sync",
                         team_name="t", subagent_type="worker")
        new = out["hookSpecificOutput"]["updatedInput"]
        self.assertEqual(self.decision(out), "allow")
        self.assertNotIn("name", new)
        self.assertNotIn("team_name", new)
        self.assertEqual((new["prompt"], new["subagent_type"], new["model"]), ("p", "worker", "opus"))

    def test_review_goes_to_sonnet_medium(self):
        new = self.agent(model="opus", effort="high", description="Review the login fix")["hookSpecificOutput"]
        self.assertEqual((new["updatedInput"]["model"], new["updatedInput"]["effort"]), ("sonnet", "medium"))

    def test_lookup_goes_to_haiku_low(self):
        new = self.agent(model="opus", effort="high", description="Find where the cache is set")
        self.assertEqual(new["hookSpecificOutput"]["updatedInput"]["model"], "haiku")

    def test_reroute_never_raises(self):
        self.assertIsNone(self.agent(model="haiku", effort="low", subagent_type="reviewer", description="Review X"))

    def test_fix_then_verify_is_not_a_review(self):
        self.assertIsNone(self.agent(model="opus", effort="high", description="Fix X and verify tests"))

    def test_builtin_agent_without_effort_passes(self):
        self.assertIsNone(self.agent(model="sonnet", subagent_type="Explore", description="Map the repo"))

    def test_reroute_off_keeps_model(self):
        g.REROUTE = False
        self.assertIsNone(self.agent(model="opus", effort="high", description="Review the login fix"))

    # SendMessage
    def test_retask_above_100k_is_refused(self):
        self.helper("a1", 150_000, name="builder")
        self.assertEqual(self.decision(self.send("builder")), "deny")

    def test_retask_below_100k_passes(self):
        self.helper("a1", 60_000, name="builder")
        self.assertIsNone(self.send("builder"))

    def test_retask_of_reviewer_is_refused_even_small(self):
        self.helper("a1", 20_000, name="r1", kind="reviewer")
        self.assertEqual(self.decision(self.send("r1")), "deny")

    def test_addressed_by_id_with_ref_suffix(self):
        self.helper("a1b2", 150_000)
        self.assertEqual(self.decision(self.send("agent-a1b2 [x9]")), "deny")

    def test_reused_name_checks_the_newest(self):
        self.helper("old", 150_000, name="builder", ts="2026-10-25T09:00:00Z")
        self.helper("new", 30_000, name="builder", ts="2026-10-25T11:00:00Z")
        self.assertIsNone(self.send("builder"))

    def test_peer_and_protocol_replies_pass(self):
        self.helper("a1", 150_000, name="builder")
        self.assertIsNone(self.send("some-other-chat"))
        out = g.hook_event({"tool_name": "SendMessage", "transcript_path": self.transcript,
                            "tool_input": {"to": "builder", "message": {"type": "shutdown_response"}}})
        self.assertIsNone(out)

    # whole hook
    def test_off_switch_turns_everything_off(self):
        self.helper("a1", 150_000, name="builder")
        os.makedirs(g.HOME, exist_ok=True)
        open(g.OFF, "w").close()
        self.assertIsNone(self.agent(description="no model at all", name="x"))
        self.assertIsNone(self.send("builder"))

    def test_decisions_are_logged(self):
        self.agent(effort="low")
        self.agent(model="sonnet", effort="low", description="Add login form")
        with open(g.LOG) as f:
            rows = [json.loads(l) for l in f]
        self.assertEqual([r["decision"] for r in rows], ["deny-no-model", "pass"])

    def test_garbage_input_fails_open(self):
        env = dict(os.environ, HELPER_GATE_HOME=g.HOME)
        for stdin in ("not json", "[]", '{"tool_name": "Agent", "tool_input": 3}'):
            r = subprocess.run([sys.executable, os.path.join(HERE, "helper_gate.py"), "hook"], input=stdin,
                               capture_output=True, text=True, env=env, timeout=10)
            self.assertEqual((r.returncode, r.stdout), (0, ""), stdin)


if __name__ == "__main__":
    unittest.main()
