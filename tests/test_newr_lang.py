#!/usr/bin/env python3
"""Tests for the .newr language: parser, compiler, and `newr build`.

Stdlib unittest only; run with:
    python3 tests/test_newr_lang.py
from the repo root, or: python3 -m unittest discover -s tests.

The mocked-interaction round-trip runs only when discord.py is
importable, so the suite stays green without it. The parser and
compiler are loaded straight from the single `newr` file, so these
tests prove the language lives in that file and nowhere else.
"""

import asyncio
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
NEWR = REPO_ROOT / "newr"

from importlib.machinery import SourceFileLoader

_spec = importlib.util.spec_from_file_location(
    "newr_lib", NEWR, loader=SourceFileLoader("newr_lib", str(NEWR)))
newr = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(newr)

HELLO = """\
bot "HelloBot":
  description: "A friendly bot"

command ping:
  description: "Answer with pong"
  reply: "Pong! Hello {user}"

command greet:
  description: "Greet someone in this server"
  reply: "Hello {user}, welcome to {guild}!"
  ephemeral: true

event ready:
  log: "{bot} is online"

event member_join:
  reply: "Welcome to {guild}, {user}!"
"""


class ParseTest(unittest.TestCase):
    def test_minimal_bot_parses(self):
        parsed = newr.parse_newr('bot "Tiny":\n', "tiny.newr")
        self.assertEqual(parsed["bot"]["name"], "Tiny")
        self.assertEqual(parsed["commands"], [])
        self.assertEqual(parsed["events"], [])

    def test_full_sample_parses(self):
        parsed = newr.parse_newr(HELLO, "hello.newr")
        self.assertEqual(parsed["bot"]["name"], "HelloBot")
        self.assertEqual(parsed["bot"]["description"], "A friendly bot")
        self.assertEqual([c["name"] for c in parsed["commands"]],
                         ["ping", "greet"])
        ping, greet = parsed["commands"]
        self.assertEqual(ping["reply"], "Pong! Hello {user}")
        self.assertFalse(ping["ephemeral"])
        self.assertTrue(greet["ephemeral"])
        self.assertEqual(greet["description"], "Greet someone in this server")
        self.assertEqual([e["kind"] for e in parsed["events"]],
                         ["ready", "member_join"])
        self.assertEqual(parsed["events"][0]["log"], "{bot} is online")

    def test_comments_and_blank_lines_ignored(self):
        parsed = newr.parse_newr(
            "# a comment\n\nbot \"B\":\n  # inner comment\n", "c.newr")
        self.assertEqual(parsed["bot"]["name"], "B")

    def test_command_description_defaults_to_name(self):
        parsed = newr.parse_newr(
            'bot "B":\n\ncommand ping:\n  reply: "Pong"\n', "d.newr")
        self.assertEqual(parsed["commands"][0]["description"], "ping")

    def test_string_escapes(self):
        parsed = newr.parse_newr(
            'bot "B":\n\ncommand ping:\n  reply: "Say \\"hi\\"\\\\nbye"\n',
            "e.newr")
        self.assertEqual(parsed["commands"][0]["reply"], 'Say "hi"\\nbye')

    # --- errors: each names the line ---

    def assert_lang_error(self, source, needle):
        with self.assertRaises(newr.NewrError) as caught:
            newr.parse_newr(source, "bad.newr")
        self.assertIn(needle, str(caught.exception))

    def test_empty_file_errors(self):
        self.assert_lang_error("", "no bot block")

    def test_missing_bot_block_errors(self):
        self.assert_lang_error('command ping:\n  reply: "Pong"\n',
                               "no bot block")

    def test_bot_block_must_come_first(self):
        self.assert_lang_error(
            'command ping:\n  reply: "Pong"\n\nbot "B":\n', "bot block")

    def test_unknown_placeholder_errors(self):
        self.assert_lang_error(
            'bot "B":\n\ncommand ping:\n  reply: "Hi {foo}"\n', "{foo}")

    def test_missing_reply_errors(self):
        self.assert_lang_error(
            'bot "B":\n\ncommand ping:\n  description: "No reply"\n',
            "reply")

    def test_duplicate_command_errors(self):
        self.assert_lang_error(
            'bot "B":\n\ncommand ping:\n  reply: "one"\n\n'
            'command ping:\n  reply: "two"\n', "duplicate")

    def test_bad_command_name_errors(self):
        for name in ("Ping", "has space", "9lives", "has-dash"):
            self.assert_lang_error(
                'bot "B":\n\ncommand %s:\n  reply: "x"\n' % name, name)

    def test_unknown_event_kind_errors(self):
        self.assert_lang_error(
            'bot "B":\n\nevent typing:\n  log: "x"\n', "typing")

    def test_unknown_key_errors(self):
        self.assert_lang_error(
            'bot "B":\n\ncommand ping:\n  reply: "x"\n  colour: "red"\n',
            "colour")

    def test_unknown_top_level_block_errors(self):
        self.assert_lang_error('bot "B":\n\nwidget w:\n  reply: "x"\n',
                               "widget")

    def test_unclosed_quote_errors(self):
        self.assert_lang_error('bot "B":\n\ncommand ping:\n  reply: "never closed\n',
                               "line 4")

    def test_tab_indentation_errors(self):
        self.assert_lang_error('bot "B":\n\t description: "tabbed"\n', "tab")

    def test_bad_indent_errors(self):
        self.assert_lang_error(
            'bot "B":\n   description: "three spaces"\n', "line 2")

    def test_ready_log_placeholders_limited(self):
        # {user} makes no sense in a ready log: there is no user.
        self.assert_lang_error(
            'bot "B":\n\nevent ready:\n  log: "hi {user}"\n', "{user}")

    def test_ephemeral_must_be_boolean(self):
        self.assert_lang_error(
            'bot "B":\n\ncommand ping:\n  reply: "x"\n  ephemeral: maybe\n',
            "ephemeral")


class CompileTest(unittest.TestCase):
    def setUp(self):
        self.parsed = newr.parse_newr(HELLO, "hello.newr")
        self.code = newr.compile_newr(self.parsed, "hello.newr")

    def test_generated_code_compiles(self):
        compile(self.code, "hello.py", "exec")

    def test_generated_code_registers_both_commands(self):
        self.assertIn('tree.command(name="ping"', self.code)
        self.assertIn('tree.command(name="greet"', self.code)
        self.assertIn("send_message", self.code)

    def test_ephemeral_only_where_set(self):
        ping_body = self.code.split("async def cmd_ping")[1].split("@bot.tree.command")[0]
        self.assertNotIn("ephemeral", ping_body)
        greet_body = self.code.split("async def cmd_greet")[1].split("@bot.tree.error")[0]
        self.assertIn("ephemeral=True", greet_body)

    def test_member_join_adds_members_intent(self):
        self.assertIn("intents.members = True", self.code)

    def test_no_member_join_means_no_members_intent(self):
        parsed = newr.parse_newr(
            'bot "B":\n\ncommand ping:\n  reply: "Pong"\n', "b.newr")
        code = newr.compile_newr(parsed, "b.newr")
        self.assertNotIn("intents.members", code)

    def test_token_from_environment_only(self):
        self.assertIn('DISCORD_TOKEN', self.code)
        self.assertNotIn("paste-your-token", self.code)
        self.assertNotIn("TOKEN = ", self.code)

    def test_generated_code_names_its_source(self):
        self.assertIn("hello.newr", self.code)

    def test_generated_code_answers_errors(self):
        self.assertIn("on_app_command_error", self.code)


class BuildCommandTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.work = Path(self.tmp.name)
        self.env = dict(os.environ)
        self.env["NEWR_LOCAL_SOURCE"] = str(REPO_ROOT)

    def tearDown(self):
        self.tmp.cleanup()

    def build(self, *args, cwd=None):
        return subprocess.run(
            [sys.executable, str(NEWR), "build", *args],
            capture_output=True, text=True, env=self.env,
            cwd=str(cwd or self.work),
        )

    def write_source(self, name="hello.newr", text=HELLO):
        src = self.work / name
        src.write_text(text, encoding="utf-8")
        return src

    def test_build_writes_py_next_to_source(self):
        src = self.write_source()
        proc = self.build(str(src))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        out = self.work / "hello.py"
        self.assertTrue(out.is_file())
        compile(out.read_text(encoding="utf-8"), "hello.py", "exec")
        self.assertIn("hello.py", proc.stdout)

    def test_build_output_flag(self):
        src = self.write_source()
        proc = self.build(str(src), "-o", str(self.work / "bot.py"))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertTrue((self.work / "bot.py").is_file())
        self.assertFalse((self.work / "hello.py").exists())

    def test_build_check_writes_nothing(self):
        src = self.write_source()
        proc = self.build("--check", str(src))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertFalse((self.work / "hello.py").exists())
        self.assertIn("ok", proc.stdout)

    def test_build_error_exits_1_with_line(self):
        src = self.write_source(text='bot "B":\n\ncommand ping:\n  reply: "Hi {nope}"\n')
        proc = self.build(str(src))
        self.assertEqual(proc.returncode, 1)
        self.assertIn("hello.newr", proc.stderr)
        self.assertIn("line 4", proc.stderr)
        self.assertIn("{nope}", proc.stderr)
        self.assertFalse((self.work / "hello.py").exists())

    def test_build_missing_file_fails(self):
        proc = self.build(str(self.work / "nope.newr"))
        self.assertEqual(proc.returncode, 1)
        self.assertIn("no such file", proc.stderr)

    def test_build_unknown_command_line(self):
        proc = self.build()
        self.assertEqual(proc.returncode, 1)
        self.assertIn("usage", proc.stderr)

    def test_help_mentions_build(self):
        proc = subprocess.run(
            [sys.executable, str(NEWR), "help"],
            capture_output=True, text=True, env=self.env)
        self.assertIn("build", proc.stdout)

    def test_golden_example_is_byte_identical(self):
        example = REPO_ROOT / "examples" / "hello.newr"
        golden = REPO_ROOT / "examples" / "hello.py"
        self.assertTrue(example.is_file(), "examples/hello.newr missing")
        self.assertTrue(golden.is_file(), "examples/hello.py missing")
        parsed = newr.parse_newr(example.read_text(encoding="utf-8"),
                                 "examples/hello.newr")
        code = newr.compile_newr(parsed, "examples/hello.newr")
        self.assertEqual(code, golden.read_text(encoding="utf-8"))


@unittest.skipUnless(importlib.util.find_spec("discord") is not None,
                     "discord.py not installed")
class LiveRoundTripTest(unittest.TestCase):
    """Compile the sample, import it, and drive the command
    callbacks with fake interactions: a real round-trip of the
    command logic without connecting to Discord."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.work = Path(self.tmp.name)
        parsed = newr.parse_newr(HELLO, "hello.newr")
        code = newr.compile_newr(parsed, "hello.newr")
        (self.work / "hello.py").write_text(code, encoding="utf-8")
        sys.path.insert(0, str(self.work))
        import hello as hello_mod
        self.mod = hello_mod

    def tearDown(self):
        sys.path.remove(str(self.work))
        sys.modules.pop("hello", None)
        self.tmp.cleanup()

    def test_ping_round_trip(self):
        interaction = FakeInteraction()
        asyncio.run(self.mod.bot.tree.get_command("ping").callback(interaction))
        self.assertEqual(len(interaction.response.sent), 1)
        text, kwargs = interaction.response.sent[0]
        self.assertEqual(text, "Pong! Hello @TestUser")
        self.assertNotIn("ephemeral", kwargs)

    def test_greet_round_trip_is_ephemeral(self):
        interaction = FakeInteraction()
        asyncio.run(self.mod.bot.tree.get_command("greet").callback(interaction))
        text, kwargs = interaction.response.sent[0]
        self.assertEqual(text, "Hello @TestUser, welcome to Test Guild!")
        self.assertTrue(kwargs.get("ephemeral"))

    def test_member_join_round_trip(self):
        member = FakeMember()
        asyncio.run(self.mod.bot.on_member_join(member))
        self.assertEqual(member.guild.system_channel.sent,
                         ["Welcome to Test Guild, @TestUser!"])


class FakeResponse:
    def __init__(self):
        self.sent = []

    async def send_message(self, content, **kwargs):
        self.sent.append((content, kwargs))


class FakeUser:
    mention = "@TestUser"


class FakeGuild:
    name = "Test Guild"

    def __init__(self):
        self.system_channel = FakeChannel()


class FakeChannel:
    mention = "#general"

    def __init__(self):
        self.sent = []

    async def send(self, content):
        self.sent.append(content)


class FakeInteraction:
    def __init__(self):
        self.user = FakeUser()
        self.guild = FakeGuild()
        self.channel = FakeChannel()
        self.response = FakeResponse()


class FakeMember:
    def __init__(self):
        self.mention = "@TestUser"
        self.guild = FakeGuild()


if __name__ == "__main__":
    unittest.main(verbosity=2)
