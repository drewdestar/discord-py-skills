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
        # Discord's rule: 1-32 chars, lowercase letters/digits/_/-
        # in any script. Uppercase, spaces, dots, emoji, and a
        # 33-character name are all invalid.
        for name in ("Ping", "has space", "has.dot", "a" * 33, "emoji🎉"):
            self.assert_lang_error(
                'bot "B":\n\ncommand %s:\n  reply: "x"\n' % name, name)

    def test_unicode_command_names_parse(self):
        # Discord allows any script's letters in a command name:
        # Japanese, Thai, Devanagari, Arabic. The generated code
        # must still compile, with the name kept verbatim.
        src = ('bot "B":\n\ncommand こんにちは:\n  reply: "x"\n\n'
               'command สวัสดี:\n  reply: "y"\n\n'
               'command नमस्ते:\n  reply: "z"\n\n'
               'command مرحبا:\n  reply: "w"\n')
        parsed = newr.parse_newr(src, "uni.newr")
        code = newr.compile_newr(parsed, "uni.newr")
        compile(code, "uni.py", "exec")
        for name in ("こんにちは", "สวัสดี", "नमस्ते", "مرحبا"):
            self.assertIn('tree.command(name="%s"' % name, code)
            self.assertIn("async def cmd_%s(" % name, code)

    def test_dash_and_digit_command_names_ok(self):
        # Discord allows a leading digit and a hyphen; the
        # generated function name just swaps - for _.
        src = ('bot "B":\n\ncommand 9lives:\n  reply: "x"\n\n'
               'command has-dash:\n  reply: "y"\n')
        parsed = newr.parse_newr(src, "dash.newr")
        code = newr.compile_newr(parsed, "dash.newr")
        compile(code, "dash.py", "exec")
        self.assertIn('tree.command(name="has-dash"', code)
        self.assertIn("async def cmd_has_dash(", code)

    def test_sanitized_fn_name_collision_errors(self):
        # foo-bar and foo_bar would both become cmd_foo_bar, so
        # the second one is an error at parse time, not a silent
        # shadow at runtime.
        self.assert_lang_error(
            'bot "B":\n\ncommand foo-bar:\n  reply: "x"\n\n'
            'command foo_bar:\n  reply: "y"\n', "collides")

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

    def test_duplicate_event_errors(self):
        self.assert_lang_error(
            'bot "B":\n\nevent ready:\n  log: "one"\n\nevent ready:\n  log: "two"\n',
            "duplicate event 'ready'")

    def test_duplicate_member_join_event_errors(self):
        self.assert_lang_error(
            'bot "B":\n\nevent member_join:\n  reply: "one"\n'
            'event member_join:\n  reply: "two"\n',
            "duplicate event 'member_join'")

    def test_duplicate_key_errors(self):
        self.assert_lang_error(
            'bot "B":\n\ncommand ping:\n  reply: "one"\n  reply: "two"\n',
            "duplicate key 'reply'")

    def test_command_description_over_100_errors(self):
        self.assert_lang_error(
            'bot "B":\n\ncommand ping:\n  description: "' + "x" * 101
            + '"\n  reply: "Pong"\n', "100")

    def test_command_description_exactly_100_ok(self):
        parsed = newr.parse_newr(
            'bot "B":\n\ncommand ping:\n  description: "' + "x" * 100
            + '"\n  reply: "Pong"\n', "d.newr")
        self.assertEqual(len(parsed["commands"][0]["description"]), 100)

    def test_reply_over_2000_errors(self):
        self.assert_lang_error(
            'bot "B":\n\ncommand ping:\n  reply: "' + "y" * 2001 + '"\n',
            "2000")

    def test_reply_exactly_2000_ok(self):
        parsed = newr.parse_newr(
            'bot "B":\n\ncommand ping:\n  reply: "' + "y" * 2000 + '"\n',
            "r.newr")
        self.assertEqual(len(parsed["commands"][0]["reply"]), 2000)

    def test_reply_placeholder_expansion_counts(self):
        # {guild} can be a 100-character server name at runtime.
        self.assert_lang_error(
            'bot "B":\n\ncommand ping:\n  reply: "' + "y" * 1950
            + ' {guild}"\n', "2000")
        parsed = newr.parse_newr(
            'bot "B":\n\ncommand ping:\n  reply: "' + "y" * 1890
            + ' {guild}"\n', "r.newr")
        self.assertEqual(len(parsed["commands"][0]["reply"]),
                         1890 + len(" {guild}"))

    def test_member_join_reply_over_2000_errors(self):
        self.assert_lang_error(
            'bot "B":\n\nevent member_join:\n  reply: "' + "y" * 2001 + '"\n',
            "2000")

    def test_empty_description_errors(self):
        self.assert_lang_error(
            'bot "B":\n\ncommand ping:\n  description: ""\n  reply: "Pong"\n',
            "empty description")

    def test_empty_reply_errors(self):
        self.assert_lang_error(
            'bot "B":\n\ncommand ping:\n  reply: ""\n',
            "empty reply")

    def test_empty_member_join_reply_errors(self):
        self.assert_lang_error(
            'bot "B":\n\nevent member_join:\n  reply: ""\n',
            "empty reply")

    def test_unclosed_brace_never_loops(self):
        # _newr_expanded_len used to loop forever on 'hi {oops'.
        self.assertEqual(newr._newr_expanded_len("hi {oops"), 8)
        self.assertEqual(newr._newr_fstring("hi {oops", {"user": "x"}),
                         'f"hi {{oops"')

    def test_unknown_key_suggests(self):
        self.assert_lang_error(
            'bot "B":\n\ncommand ping:\n  reply: "x"\n  ephemral: true\n',
            "did you mean 'ephemeral'")

    def test_unknown_event_suggests(self):
        self.assert_lang_error(
            'bot "B":\n\nevent redy:\n  log: "x"\n', "did you mean 'ready'")

    def test_unknown_placeholder_suggests(self):
        self.assert_lang_error(
            'bot "B":\n\ncommand ping:\n  reply: "Hi {usr}"\n',
            "did you mean {user}?")

    def test_unknown_block_suggests(self):
        self.assert_lang_error(
            'bot "B":\n\ncommnad ping:\n  reply: "x"\n',
            "did you mean 'command'")


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

    def test_guild_fallback_uses_single_quotes(self):
        # The {guild} fallback must be 'DM' in single quotes: the
        # generated f-string is double-quoted, so double quotes inside
        # the expression are a SyntaxError on Python 3.10/3.11 (PEP 701
        # only lifted that in 3.12).
        parsed = newr.parse_newr(
            'bot "B":\n\ncommand hi:\n  reply: "Hello {guild}!"\n', "b.newr")
        code = newr.compile_newr(parsed, "b.newr")
        self.assertIn("else 'DM'", code)
        compile(code, "hi.py", "exec")


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

    def test_build_crlf_source(self):
        # A .newr file saved with Windows CRLF line endings
        # builds exactly like one with LF endings.
        src = self.work / "crlf.newr"
        src.write_bytes(HELLO.replace("\n", "\r\n").encode("utf-8"))
        proc = self.build(str(src))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        out = self.work / "crlf.py"
        self.assertTrue(out.is_file())
        compile(out.read_text(encoding="utf-8"), "crlf.py", "exec")

    def test_build_multilingual_replies(self):
        # Replies, descriptions, and the bot name may be in any
        # language: Indonesian, Japanese, Arabic, Thai, emoji.
        # The generated code must compile and keep every literal.
        text = (
            'bot "BotMulti":\n'
            '  description: "Bot berbahasa apa saja"\n\n'
            'command halo:\n'
            '  description: "Sapa dalam Bahasa Indonesia"\n'
            '  reply: "Halo {user}, selamat datang di {guild}! 🎉"\n\n'
            'command konnichiwa:\n'
            '  description: "日本語で挨拶"\n'
            '  reply: "こんにちは {user} さん、{guild} へようこそ！"\n\n'
            'command marhaba:\n'
            '  description: "ترحيب بالعربية"\n'
            '  reply: "مرحباً {user} في {guild}!"\n\n'
            'command sawatdee:\n'
            '  description: "ทักทายภาษาไทย"\n'
            '  reply: "สวัสดี {user} ยินดีต้อนรับสู่ {guild}"\n')
        src = self.write_source(name="multi.newr", text=text)
        proc = self.build(str(src))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        out = self.work / "multi.py"
        code = out.read_text(encoding="utf-8")
        compile(code, "multi.py", "exec")
        for literal in ("Halo", "こんにちは", "مرحباً", "สวัสดี", "🎉"):
            self.assertIn(literal, code)

    def test_build_error_exits_1_with_line(self):
        src = self.write_source(text='bot "B":\n\ncommand ping:\n  reply: "Hi {nope}"\n')
        proc = self.build(str(src))
        # A build error is exit 4 (typed exit codes: 1 usage, 2
        # environment, 3 network, 4 build).
        self.assertEqual(proc.returncode, 4)
        self.assertIn("hello.newr", proc.stderr)
        self.assertIn("line 4", proc.stderr)
        self.assertIn("{nope}", proc.stderr)
        self.assertFalse((self.work / "hello.py").exists())

    def test_build_error_shows_source_line(self):
        src = self.write_source(text='bot "B":\n\ncommand ping:\n  reply: "Hi {nope}"\n')
        proc = self.build(str(src))
        self.assertEqual(proc.returncode, 4)
        self.assertIn('reply: "Hi {nope}"', proc.stderr)

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


def _real_discord_available() -> bool:
    """True only if a real discord.py is importable. A test stub left in
    sys.modules (or a spec-less one, which makes find_spec raise
    ValueError) must not count as the library being installed."""
    mod = sys.modules.get("discord")
    if mod is not None and getattr(mod, "_is_test_stub", False):
        return False
    try:
        return importlib.util.find_spec("discord") is not None
    except ValueError:
        return False


@unittest.skipUnless(_real_discord_available(), "discord.py not installed")
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
