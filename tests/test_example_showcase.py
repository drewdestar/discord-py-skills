#!/usr/bin/env python3
"""Tests for the showcase example: examples/showcase.newr + showcase.py.

Stdlib unittest only; run with:
    python3 tests/test_example_showcase.py
from the repo root, or: python3 -m unittest discover -s tests.

Mocked throughout: no Discord token, no network to Discord, and
no discord.py import. The parser and compiler are loaded straight
from the single `newr` file, and `newr build` is exercised only
via subprocess on temp copies (plus --check on the real file,
which writes nothing).
"""

import importlib.util
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
NEWR = REPO_ROOT / "newr"
SHOWCASE_NEWR = REPO_ROOT / "examples" / "showcase.newr"
SHOWCASE_PY = REPO_ROOT / "examples" / "showcase.py"

from importlib.machinery import SourceFileLoader

_spec = importlib.util.spec_from_file_location(
    "newr_lib", NEWR, loader=SourceFileLoader("newr_lib", str(NEWR)))
newr = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(newr)


def load_showcase():
    return newr.parse_newr(
        SHOWCASE_NEWR.read_text(encoding="utf-8"), "examples/showcase.newr")


class ShowcaseParseTest(unittest.TestCase):
    def test_files_exist(self):
        self.assertTrue(SHOWCASE_NEWR.is_file(), "examples/showcase.newr missing")
        self.assertTrue(SHOWCASE_PY.is_file(), "examples/showcase.py missing")

    def test_bot_block(self):
        parsed = load_showcase()
        self.assertEqual(parsed["bot"]["name"], "ShowcaseBot")
        self.assertEqual(parsed["bot"]["description"],
                         "A showcase bot that shows off the newr language")

    def test_four_commands_in_order(self):
        parsed = load_showcase()
        self.assertEqual([c["name"] for c in parsed["commands"]],
                         ["ping", "whereami", "secret", "rules"])

    def test_ephemeral_only_on_secret(self):
        parsed = load_showcase()
        by_name = {c["name"]: c for c in parsed["commands"]}
        self.assertTrue(by_name["secret"]["ephemeral"])
        for name in ("ping", "whereami", "rules"):
            self.assertFalse(by_name[name]["ephemeral"], name)

    def test_rules_description_defaults_to_name(self):
        parsed = load_showcase()
        by_name = {c["name"]: c for c in parsed["commands"]}
        self.assertEqual(by_name["rules"]["description"], "rules")

    def test_whereami_uses_all_three_command_placeholders(self):
        parsed = load_showcase()
        by_name = {c["name"]: c for c in parsed["commands"]}
        reply = by_name["whereami"]["reply"]
        for placeholder in ("{user}", "{guild}", "{channel}"):
            self.assertIn(placeholder, reply)

    def test_both_events_present(self):
        parsed = load_showcase()
        self.assertEqual([e["kind"] for e in parsed["events"]],
                         ["ready", "member_join"])
        by_kind = {e["kind"]: e for e in parsed["events"]}
        self.assertEqual(by_kind["ready"]["log"], "{bot} is online")
        self.assertEqual(by_kind["member_join"]["reply"],
                         "Welcome to {guild}, {user}!")


class ShowcaseCompileTest(unittest.TestCase):
    def setUp(self):
        self.code = newr.compile_newr(load_showcase(), "examples/showcase.newr")

    def test_generated_code_compiles(self):
        compile(self.code, "showcase.py", "exec")

    def test_generated_code_registers_all_four_commands(self):
        for name in ("ping", "whereami", "secret", "rules"):
            self.assertIn('tree.command(name="%s"' % name, self.code)

    def test_ephemeral_only_in_secret(self):
        secret_body = self.code.split("async def cmd_secret")[1].split("@bot.tree.error")[0]
        self.assertIn("ephemeral=True", secret_body)
        for name in ("ping", "whereami", "rules"):
            body = self.code.split("async def cmd_%s" % name)[1].split("\n\n\n")[0]
            self.assertNotIn("ephemeral", body)

    def test_whereami_uses_channel_helper(self):
        self.assertIn("_channel_text(interaction.channel)", self.code)

    def test_member_join_adds_members_intent_and_handler(self):
        self.assertIn("intents.members = True", self.code)
        self.assertIn("async def on_member_join", self.code)

    def test_ready_handler_logs_bot_name(self):
        self.assertIn("async def on_ready", self.code)
        self.assertIn('log.info(f"{self.user} is online")', self.code)

    def test_token_from_environment_only(self):
        self.assertIn("DISCORD_TOKEN", self.code)
        self.assertNotIn("paste-your-token", self.code)
        self.assertNotIn("TOKEN = ", self.code)

    def test_generated_code_names_its_source(self):
        self.assertIn("examples/showcase.newr", self.code)

    def test_generated_code_answers_errors(self):
        self.assertIn("on_app_command_error", self.code)


class ShowcaseBuildTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.work = Path(self.tmp.name)
        # No token anywhere near the build: it must not need one.
        self.env = {k: v for k, v in os.environ.items()
                    if k != "DISCORD_TOKEN"}
        self.env["NEWR_LOCAL_SOURCE"] = str(REPO_ROOT)

    def tearDown(self):
        self.tmp.cleanup()

    def build(self, *args, cwd=None):
        return subprocess.run(
            [sys.executable, str(NEWR), "build", *args],
            capture_output=True, text=True, env=self.env,
            cwd=str(cwd or self.work),
        )

    def test_build_check_on_real_file_writes_nothing(self):
        before = SHOWCASE_PY.read_bytes()
        proc = self.build("--check", str(SHOWCASE_NEWR))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("ok", proc.stdout)
        self.assertIn("4 command(s), 2 event(s)", proc.stdout)
        self.assertEqual(SHOWCASE_PY.read_bytes(), before)

    def test_build_temp_copy_compiles_and_names_its_source(self):
        src = self.work / "showcase.newr"
        src.write_text(SHOWCASE_NEWR.read_text(encoding="utf-8"),
                       encoding="utf-8")
        proc = self.build(str(src))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        out = self.work / "showcase.py"
        self.assertTrue(out.is_file())
        compile(out.read_text(encoding="utf-8"), "showcase.py", "exec")
        self.assertIn(str(src), out.read_text(encoding="utf-8"))

    def test_golden_example_is_byte_identical(self):
        code = newr.compile_newr(load_showcase(), "examples/showcase.newr")
        self.assertEqual(code, SHOWCASE_PY.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
