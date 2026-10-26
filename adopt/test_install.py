"""Tests for install.py: install then undo leaves every file as it was. Runs only in a temp folder.

run: python3 -m unittest discover -s adopt -p 'test_install.py'"""
import json, os, subprocess, sys, tempfile, unittest

SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "install.py")


def snapshot(root):
    out = {}
    for d, _, files in os.walk(root):
        out[os.path.relpath(d, root)] = None
        for f in files:
            with open(os.path.join(d, f), "rb") as fh:
                out[os.path.relpath(os.path.join(d, f), root)] = fh.read()
    return out


class InstallTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = self.tmp.name

    def tearDown(self):
        self.tmp.cleanup()

    def run_it(self, *args):
        env = dict(os.environ, CLAUDE_CONFIG_DIR=os.path.join(self.root, "unused"))
        r = subprocess.run([sys.executable, SCRIPT, *args], capture_output=True, text=True, env=env)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        return r.stdout

    def write(self, rel, text):
        path = os.path.join(self.root, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write(text)

    def test_project_round_trip_keeps_existing_hook_and_rules(self):
        self.write("p/CLAUDE.md", "# Mine\n\n- one rule")  # no trailing newline
        self.write("p/.claude/settings.json", '{"hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": []}]}}')
        before = snapshot(self.root)
        args = ["--scope", "project", "--project", os.path.join(self.root, "p")]
        self.run_it(*args, "--dry-run")
        self.assertEqual(snapshot(self.root), before)
        self.run_it(*args)
        cfg = json.load(open(os.path.join(self.root, "p/.claude/settings.json")))
        self.assertEqual([e["matcher"] for e in cfg["hooks"]["PreToolUse"]], ["Bash", "Agent|Task"])
        self.assertIn("$CLAUDE_PROJECT_DIR", cfg["hooks"]["PreToolUse"][1]["hooks"][0]["command"])
        self.assertIn("token-savings:begin", open(os.path.join(self.root, "p/CLAUDE.md")).read())
        self.assertIn("Nothing to change", self.run_it(*args))
        self.run_it(*args, "--undo")
        self.assertEqual(snapshot(self.root), before)

    def test_user_round_trip_from_empty_folder(self):
        os.makedirs(os.path.join(self.root, "c"))
        before = snapshot(self.root)
        args = ["--scope", "user", "--config", os.path.join(self.root, "c")]
        self.run_it(*args)
        cmd = json.load(open(os.path.join(self.root, "c/settings.json")))["hooks"]["PreToolUse"][0]["hooks"][0]
        self.assertIn(os.path.join(self.root, "c", "hooks", "helper_gate.py"), cmd["command"])
        self.run_it(*args, "--undo")
        self.assertEqual(snapshot(self.root), before)

    def test_edited_agent_is_kept_on_undo(self):
        args = ["--scope", "user", "--config", os.path.join(self.root, "c")]
        self.run_it(*args)
        self.write("c/agents/worker.md", "mine now\n")
        out = self.run_it(*args, "--undo")
        self.assertIn("edited after install", out)
        self.assertEqual(open(os.path.join(self.root, "c/agents/worker.md")).read(), "mine now\n")

    def test_existing_different_agent_is_kept(self):
        self.write("c/agents/scout.md", "my scout\n")
        args = ["--scope", "user", "--config", os.path.join(self.root, "c")]
        self.assertIn("kept yours", self.run_it(*args))
        self.run_it(*args, "--undo")
        self.assertEqual(open(os.path.join(self.root, "c/agents/scout.md")).read(), "my scout\n")


if __name__ == "__main__":
    unittest.main()
