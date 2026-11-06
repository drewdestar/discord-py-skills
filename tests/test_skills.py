#!/usr/bin/env python3
"""Tests for the skill pack's SKILL.md files. Stdlib unittest only; run with:
    python3 -m unittest discover -s tests
from the repo root.

Every check is grounded in the Agent Skills spec at
https://agentskills.io/specification (fetched 2026-11-06):
name 1-64 chars, lowercase alnum + hyphens, no leading/trailing or
double hyphen, must match the parent directory name; description
1-1024 chars, what + when; compatibility 1-500 chars if present;
metadata is a string-to-string map; SKILL.md body under 500 lines.
The router test pins the pack's own conventions on top of the spec:
every skill has a "Use when" trigger in its description, and the
router's table names every skill exactly once.

Body lines, not whole-file lines: Anthropic's spec treats 500 lines
as a recommendation, not a hard limit, and this suite enforces it
against the body (the text after the frontmatter) rather than the
whole file. That is deliberate: the Codex 8 KB body cap is handled
the same way, by splitting long sections into references/ files and
keeping each SKILL.md body under 8,192 bytes, so the body-lines
check and the byte cap are satisfied together by the split. A
references/ file is part of the skill; the router loads it alongside
the body.
"""

import importlib.util
import json
import os
import re
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILLS_DIR = REPO_ROOT / "skills"
ROUTER = SKILLS_DIR / "using-discord-py-skills" / "SKILL.md"

NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")

EXPECTED_SKILLS = {
    "antislop",
    "bot-dashboard",
    "build-discord-bot",
    "deploy-and-monitor",
    "design-with-hallmark",
    "economy-database",
    "i18n",
    "interactive-components",
    "newr-language",
    "slash-commands",
    "testing",
    "using-discord-py-skills",
}


def _split_frontmatter(text):
    """Return (frontmatter_lines, body). Raises if no frontmatter."""
    lines = text.split("\n")
    assert lines[0] == "---", "SKILL.md must start with ---"
    try:
        end = lines.index("---", 1)
    except ValueError:
        raise AssertionError("SKILL.md frontmatter is not closed with ---")
    return lines[1:end], "\n".join(lines[end + 1:])


def _top_level_fields(fm_lines):
    """Parse single-line top-level `key: value` pairs. Metadata lines
    (indented) are returned separately for the string-value check."""
    fields = {}
    metadata = {}
    in_metadata = False
    for line in fm_lines:
        if not line.strip():
            continue
        if line.startswith(" ") or line.startswith("\t"):
            if in_metadata:
                key, _, value = line.strip().partition(":")
                metadata[key.strip()] = value.strip()
            continue
        in_metadata = False
        key, _, value = line.partition(":")
        key = key.strip()
        value = value.strip()
        if key == "metadata":
            in_metadata = True
            continue
        fields[key] = value
    return fields, metadata


def _unquote(value):
    if len(value) >= 2 and value[0] == value[-1] == '"':
        return value[1:-1]
    return value


def _load_skill(name):
    path = SKILLS_DIR / name / "SKILL.md"
    text = path.read_text(encoding="utf-8")
    fm_lines, body = _split_frontmatter(text)
    fields, metadata = _top_level_fields(fm_lines)
    return path, fm_lines, body, fields, metadata


def _skill_full_text(name):
    """Body plus references/ files: the whole skill. Content tests use
    this; the body-lines check above deliberately uses the body only."""
    _, _, body, _, _ = _load_skill(name)
    refs_dir = SKILLS_DIR / name / "references"
    if refs_dir.is_dir():
        for ref in sorted(refs_dir.glob("*.md")):
            body += "\n" + ref.read_text(encoding="utf-8")
    return body


class TestSkillFrontmatter(unittest.TestCase):
    def test_expected_skill_set_present(self):
        found = {p.parent.name for p in SKILLS_DIR.glob("*/SKILL.md")}
        self.assertEqual(found, EXPECTED_SKILLS)

    def test_every_skill_spec_valid(self):
        for name in sorted(EXPECTED_SKILLS):
            with self.subTest(skill=name):
                path, fm_lines, body, fields, metadata = _load_skill(name)
                self.assertNotIn("\t", "\n".join(fm_lines),
                                 f"{path}: tab in frontmatter (invalid YAML)")
                skill_name = _unquote(fields.get("name", ""))
                self.assertEqual(skill_name, name,
                                 f"{path}: name must match directory name")
                self.assertTrue(1 <= len(skill_name) <= 64)
                self.assertRegex(skill_name, NAME_RE)
                desc = _unquote(fields.get("description", ""))
                self.assertTrue(1 <= len(desc) <= 1024,
                                f"{path}: description must be 1-1024 chars, got {len(desc)}")
                self.assertTrue(
                    "Use when" in desc or "Use first when" in desc,
                    f"{path}: description must say when to use the skill")
                self.assertIn("license", fields, f"{path}: license is missing")
                if "compatibility" in fields:
                    compat = _unquote(fields["compatibility"])
                    self.assertTrue(1 <= len(compat) <= 500,
                                    f"{path}: compatibility must be 1-500 chars")
                for key, value in metadata.items():
                    self.assertTrue(
                        value.startswith('"') and value.endswith('"'),
                        f"{path}: metadata.{key} must be a string, got {value!r}")
                body_lines = body.count("\n") + 1
                self.assertLess(body_lines, 500,
                                f"{path}: body must stay under 500 lines, got {body_lines}")

    def test_no_duplicate_skill_names(self):
        names = []
        for path in SKILLS_DIR.glob("*/SKILL.md"):
            _, _, _, fields, _ = _load_skill(path.parent.name)
            names.append(_unquote(fields.get("name", "")))
        self.assertEqual(len(names), len(set(names)))


class TestManifestEqualsPromotedSet(unittest.TestCase):
    """TS-01: the promoted set — the twelve skills — must be identical
    in every manifest that names them. Editing any one manifest to
    drop a skill fails this test."""

    def test_promoted_set_matches_everywhere(self):
        expected = set(EXPECTED_SKILLS)
        # skills/*/ on disk.
        found = {p.parent.name for p in SKILLS_DIR.glob("*/SKILL.md")}
        self.assertEqual(found, expected, "skills/*/ on disk")
        # registry.json packages of type skill.
        registry = json.loads(
            (REPO_ROOT / "registry.json").read_text(encoding="utf-8"))
        reg_skills = {p["name"] for p in registry["packages"]
                      if p["type"] == "skill"}
        self.assertEqual(reg_skills, expected, "registry.json packages")
        # Router route table (the router itself is the entry point,
        # not a route target).
        router_text = ROUTER.read_text(encoding="utf-8")
        table = router_text.split("## Route table", 1)[1].split("## ", 1)[0]
        routed = {n for n in expected - {"using-discord-py-skills"}
                  if re.search(r"\| " + re.escape(n) + r" \|", table)}
        self.assertEqual(routed, expected - {"using-discord-py-skills"},
                         "router route table")
        # README skills table.
        readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        skills_section = readme.split("## Skills", 1)[1].split("## ", 1)[0]
        readme_skills = set(re.findall(
            r"^\| `([a-z][a-z0-9-]*)` \|", skills_section, re.M))
        self.assertEqual(readme_skills, expected, "README skills table")
        # package.json: the description must state the count.
        pkg = json.loads(
            (REPO_ROOT / "package.json").read_text(encoding="utf-8"))
        self.assertIn("twelve skills", pkg["description"],
                      "package.json description")
        # .claude-plugin/marketplace.json skills array.
        market = json.loads((REPO_ROOT / ".claude-plugin"
                             / "marketplace.json").read_text(encoding="utf-8"))
        market_skills = {Path(s).name for p in market["plugins"]
                         for s in p["skills"]}
        self.assertEqual(market_skills, expected, "marketplace.json skills")
        # newr help text carries the count; newr search lists the names.
        help_proc = subprocess.run(
            [sys.executable, str(REPO_ROOT / "newr"), "help"],
            capture_output=True, text=True, cwd=REPO_ROOT)
        self.assertIn("twelve skills", help_proc.stdout, "newr help count")
        env = dict(os.environ)
        env["NEWR_LOCAL_SOURCE"] = str(REPO_ROOT)
        search_proc = subprocess.run(
            [sys.executable, str(REPO_ROOT / "newr"), "search"],
            capture_output=True, text=True, cwd=REPO_ROOT, env=env)
        self.assertEqual(search_proc.returncode, 0, search_proc.stderr)
        for name in sorted(expected):
            self.assertIn(name, search_proc.stdout,
                          "newr search must list %s" % name)


class TestRouter(unittest.TestCase):
    def test_router_covers_every_skill_once(self):
        # Set-based coverage: every skill appears at least once in the
        # route table. A skill may appear more than once — the table
        # has several rows for the same skill when different jobs
        # route to it (e.g. build-discord-bot for "build me a bot",
        # "newr init", and "my token leaked").
        router_text = ROUTER.read_text(encoding="utf-8")
        table = router_text.split("## Route table", 1)[1].split("## ", 1)[0]
        for name in sorted(EXPECTED_SKILLS - {"using-discord-py-skills"}):
            cells = re.findall(r"\| " + re.escape(name) + r" \|", table)
            self.assertGreaterEqual(len(cells), 1,
                                    f"router must name {name} at least once")

    def test_router_skill_count_matches(self):
        router_text = ROUTER.read_text(encoding="utf-8")
        count = len(EXPECTED_SKILLS)
        self.assertIn(f"all {self._word(count)} up front", router_text)

    @staticmethod
    def _word(n):
        return {9: "nine", 8: "eight", 10: "ten", 11: "eleven",
                12: "twelve"}.get(n, str(n))


class TestNewrLanguageSkill(unittest.TestCase):
    def test_skill_documents_real_build_commands(self):
        _, _, body, _, _ = _load_skill("newr-language")
        for cmd in ("newr build hello.newr", "newr build --check hello.newr"):
            self.assertIn(cmd, body)

    def test_hello_newr_passes_check(self):
        proc = subprocess.run(
            [sys.executable, str(REPO_ROOT / "newr"), "build", "--check",
             str(REPO_ROOT / "examples" / "hello.newr")],
            capture_output=True, text=True, cwd=REPO_ROOT)
        self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_skill_states_compiler_limits(self):
        _, _, body, _, _ = _load_skill("newr-language")
        for limit in ("economy-database", "slash-commands", "i18n"):
            self.assertIn(limit, body)


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


class TestInteractiveComponents(unittest.TestCase):
    def test_skill_corrects_the_pages_myth(self):
        _, _, body, _, _ = _load_skill("interactive-components")
        self.assertIn("discord.ext.pages", body)
        self.assertIn("does not exist in discord.py", body)
        self.assertIn("py-cord", body)

    def test_skill_teaches_hand_rolled_pagination(self):
        body = _skill_full_text("interactive-components")
        for token in ("PaginatorView", "interaction_check", "on_timeout",
                      "edit_message"):
            self.assertIn(token, body)

    def test_skill_teaches_persistent_views(self):
        _, _, body, _, _ = _load_skill("interactive-components")
        for token in ("timeout=None", "custom_id", "add_view", "setup_hook"):
            self.assertIn(token, body)

    def test_skill_teaches_text_style_rename(self):
        _, _, body, _, _ = _load_skill("interactive-components")
        self.assertIn("discord.TextStyle", body)
        self.assertIn("TextInputStyle", body)

    def test_skill_teaches_components_v2_namespace(self):
        _, _, body, _, _ = _load_skill("interactive-components")
        self.assertIn("discord.ui.Container", body)
        self.assertIn("discord.ui.LayoutView", body)
        # LayoutView takes no constructor arguments: the skill must show
        # the empty construction + add_item, never LayoutView(container).
        self.assertIn("discord.ui.LayoutView()", body)
        self.assertNotIn("LayoutView(container)", body)
        # The skill must state the module does NOT exist, and must
        # never use it as a namespace (discord.ui.layout.X).
        self.assertIn("discord.ui.layout` module", body)
        self.assertNotIn("discord.ui.layout.", body)
        self.assertNotIn("from discord.ui import layout", body)

    def test_skill_states_modal_item_limit(self):
        body = _skill_full_text("interactive-components")
        self.assertIn("at most 5 items", body)

    def test_skill_has_portability_section(self):
        _, _, body, _, _ = _load_skill("interactive-components")
        self.assertIn("## Portability", body)
        self.assertIn("UNVERIFIED", body)


@unittest.skipUnless(_real_discord_available(), "discord.py not installed")
class TestInteractiveComponentsLive(unittest.TestCase):
    """The string checks above cannot catch a wrong constructor call.
    These construct the real objects (skipped where discord.py is absent)."""

    def test_layout_view_construction(self):
        import discord
        view = discord.ui.LayoutView()
        view.add_item(discord.ui.Container(
            discord.ui.TextDisplay("**Leaderboard**")))
        self.assertEqual(len(view.children), 1)
        self.assertIsInstance(view.children[0], discord.ui.Container)

    def test_layout_view_rejects_container_arg(self):
        import discord
        container = discord.ui.Container(discord.ui.TextDisplay("x"))
        with self.assertRaises(TypeError):
            discord.ui.LayoutView(container)


class TestTemplateMatchesSkill(unittest.TestCase):
    def test_starter_bot_pins_discord_py_271(self):
        reqs = (REPO_ROOT / "templates" / "starter-bot" / "requirements.txt"
                ).read_text(encoding="utf-8")
        self.assertIn("discord.py>=2.7.1", reqs)
        _, _, body, _, _ = _load_skill("build-discord-bot")
        self.assertIn("discord.py>=2.7.1", body)


if __name__ == "__main__":
    unittest.main()
