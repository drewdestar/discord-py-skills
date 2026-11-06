#!/usr/bin/env python3
"""Tests for the newr CLI. Stdlib unittest only; run with:
    python3 tests/test_newr.py
from the repo root, or: python3 -m unittest discover -s tests.

Every test runs newr against a temporary NEWR_HOME and the local
checkout as its package source (auto-detected: the newr script sits
next to registry.json), so no network is needed. HOME is also
pointed at the temp dir, so agent skill directories land there.
"""

import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
NEWR = REPO_ROOT / "newr"
SKILLS = ("using-discord-py-skills", "build-discord-bot", "slash-commands",
          "economy-database", "i18n", "deploy-and-monitor", "testing")
SPEC_FRONTMATTER_FIELDS = {"name", "description", "license",
                           "compatibility", "metadata", "allowed-tools"}


class NewrTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name) / "home"
        self.home.mkdir(parents=True)
        self.env = dict(os.environ)
        self.env["NEWR_HOME"] = str(self.home)
        self.env["HOME"] = str(self.home)
        # Point the CLI at this checkout explicitly; auto-detection
        # would find it anyway, but the env var makes it certain.
        self.env["NEWR_LOCAL_SOURCE"] = str(REPO_ROOT)

    def tearDown(self):
        self.tmp.cleanup()

    def newr(self, *args, cwd=None, env=None):
        proc = subprocess.run(
            [sys.executable, str(NEWR), *args],
            capture_output=True, text=True, env=env or self.env,
            cwd=str(cwd or self.home),
        )
        return proc

    def test_version_and_help(self):
        self.assertIn("newr 0.3.0", self.newr("version").stdout)
        self.assertIn("install", self.newr("help").stdout)
        self.assertIn("--agent", self.newr("help").stdout)
        self.assertEqual(self.newr("bogus-command").returncode, 2)

    def test_search_lists_all_packages(self):
        out = self.newr("search").stdout
        for name in SKILLS + ("starter-bot",):
            self.assertIn(name, out)

    def test_search_filters(self):
        out = self.newr("search", "economy").stdout
        self.assertIn("economy-database", out)
        self.assertNotIn("slash-commands", out)

    def test_info_unknown_package(self):
        proc = self.newr("info", "no-such-skill")
        self.assertEqual(proc.returncode, 1)
        self.assertIn("no package named", proc.stderr)

    def test_install_one_skill(self):
        proc = self.newr("install", "slash-commands")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        dest = self.home / "skills" / "slash-commands"
        self.assertTrue((dest / "SKILL.md").is_file())
        receipt = json.loads((dest / ".newr.json").read_text())
        self.assertEqual(receipt["name"], "slash-commands")
        self.assertEqual(receipt["version"], "0.3.0")
        # Byte-identical to the source skill.
        self.assertEqual(
            (dest / "SKILL.md").read_bytes(),
            (REPO_ROOT / "skills" / "slash-commands" / "SKILL.md").read_bytes(),
        )

    def test_install_twice_is_a_noop(self):
        self.newr("install", "testing")
        proc = self.newr("install", "testing")
        self.assertIn("already installed", proc.stdout)
        self.assertEqual(self.newr("install", "--force", "testing").returncode, 0)

    def test_install_all(self):
        self.assertEqual(self.newr("install", "all").returncode, 0)
        for name in SKILLS:
            self.assertTrue((self.home / "skills" / name / "SKILL.md").is_file())
        # The template is not part of `all`.
        self.assertFalse((self.home / "skills" / "starter-bot").exists())

    def test_install_repo_name_means_all(self):
        self.assertEqual(self.newr("install", "discord-py-skills").returncode, 0)
        self.assertTrue((self.home / "skills" / "i18n" / "SKILL.md").is_file())

    def test_install_template_goes_to_cwd(self):
        work = Path(self.tmp.name) / "project"
        work.mkdir()
        proc = self.newr("install", "starter-bot", cwd=work)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertTrue((work / "starter-bot" / "bot.py").is_file())
        self.assertTrue((work / "starter-bot" / "tests" / "test_db.py").is_file())

    def test_list_and_uninstall(self):
        self.newr("install", "i18n")
        self.assertIn("i18n", self.newr("list").stdout)
        proc = self.newr("uninstall", "i18n")
        self.assertIn("uninstalled i18n", proc.stdout)
        self.assertFalse((self.home / "skills" / "i18n").exists())
        self.assertIn("nothing installed", self.newr("list").stdout)
        self.assertIn("not installed", self.newr("uninstall", "i18n").stdout)

    def test_update_upgrades_stale_receipt(self):
        self.newr("install", "i18n")
        dest = self.home / "skills" / "i18n"
        receipt = json.loads((dest / ".newr.json").read_text())
        receipt["version"] = "0.1.0"
        (dest / ".newr.json").write_text(json.dumps(receipt))
        proc = self.newr("update")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("installed i18n 0.3.0", proc.stdout)
        self.assertIn("everything is up to date", self.newr("update").stdout)

    def test_install_unknown_package_fails_cleanly(self):
        proc = self.newr("install", "no-such-skill")
        self.assertEqual(proc.returncode, 1)
        self.assertIn("no package named", proc.stderr)

    # --- multi-agent targets ---

    def test_agents_lists_supported_agents(self):
        out = self.newr("agents").stdout
        for name in ("claude-code", "codex", "cursor", "windsurf", "copilot",
                     "gemini", "opencode", "kilo", "cline", "zed", "agents", "aider"):
            self.assertIn(name, out)

    def test_install_agent_claude_code(self):
        proc = self.newr("install", "--agent", "claude-code", "testing")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        dest = self.home / ".claude" / "skills" / "testing"
        self.assertTrue((dest / "SKILL.md").is_file())
        receipt = json.loads((dest / ".newr.json").read_text())
        self.assertEqual(receipt["version"], "0.3.0")
        self.assertEqual(receipt["agent"], "claude-code")
        # The default dir is untouched by an agent install.
        self.assertFalse((self.home / "skills" / "testing").exists())

    def test_install_agent_all_covers_each_dir(self):
        proc = self.newr("install", "--agent", "all", "i18n")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        expected = [
            self.home / ".claude" / "skills" / "i18n",
            self.home / ".agents" / "skills" / "i18n",
            self.home / ".codex" / "skills" / "i18n",
            self.home / ".cursor" / "skills" / "i18n",
            self.home / ".config" / "devin" / "skills" / "i18n",
            self.home / ".copilot" / "skills" / "i18n",
            self.home / ".gemini" / "skills" / "i18n",
            self.home / ".config" / "opencode" / "skills" / "i18n",
            self.home / ".cline" / "skills" / "i18n",
        ]
        for dest in expected:
            self.assertTrue((dest / "SKILL.md").is_file(), str(dest))
        # `all` excludes aider: no conventions file is written.
        self.assertFalse((self.home / ".newr" / "aider" / "CONVENTIONS.md").exists())

    def test_install_agent_auto_detects_markers(self):
        # Fake installed agents with marker dirs. PATH is emptied so
        # no real binary on this machine (codex, opencode) is detected.
        (self.home / ".claude").mkdir()
        (self.home / ".cursor").mkdir()
        empty_bin = Path(self.tmp.name) / "emptybin"
        empty_bin.mkdir()
        env = dict(self.env)
        env["PATH"] = str(empty_bin)
        proc = self.newr("install", "--agent", "auto", "testing", env=env)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertTrue((self.home / ".claude" / "skills" / "testing" / "SKILL.md").is_file())
        self.assertTrue((self.home / ".cursor" / "skills" / "testing" / "SKILL.md").is_file())
        self.assertFalse((self.home / ".copilot" / "skills" / "testing").exists())

    def test_install_agent_auto_with_nothing_detected_fails(self):
        empty_bin = Path(self.tmp.name) / "emptybin"
        empty_bin.mkdir()
        env = dict(self.env)
        env["PATH"] = str(empty_bin)
        proc = self.newr("install", "--agent", "auto", "testing", env=env)
        self.assertEqual(proc.returncode, 1)
        self.assertIn("no agent detected", proc.stderr)

    def test_install_agent_project(self):
        work = Path(self.tmp.name) / "project"
        work.mkdir()
        proc = self.newr("install", "--agent", "copilot", "--project", "testing", cwd=work)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertTrue((work / ".github" / "skills" / "testing" / "SKILL.md").is_file())

    def test_install_project_defaults_to_agents_dir(self):
        work = Path(self.tmp.name) / "project"
        work.mkdir()
        proc = self.newr("install", "--project", "testing", cwd=work)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertTrue((work / ".agents" / "skills" / "testing" / "SKILL.md").is_file())

    def test_install_agent_aider_writes_conventions(self):
        proc = self.newr("install", "--agent", "aider", "all")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        dest = self.home / ".newr" / "aider" / "CONVENTIONS.md"
        self.assertTrue(dest.is_file())
        text = dest.read_text()
        for name in SKILLS:
            self.assertIn(name, text)
        self.assertIn(".aider.conf.yml", proc.stdout)

    def test_install_agent_aider_project_writes_cwd_conventions(self):
        work = Path(self.tmp.name) / "project"
        work.mkdir()
        proc = self.newr("install", "--agent", "aider", "--project", "all", cwd=work)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertTrue((work / "CONVENTIONS.md").is_file())

    def test_install_template_with_agent_fails(self):
        proc = self.newr("install", "--agent", "claude-code", "starter-bot")
        self.assertEqual(proc.returncode, 1)
        self.assertIn("templates cannot install", proc.stderr)

    def test_install_unknown_agent_fails(self):
        proc = self.newr("install", "--agent", "no-such-agent", "testing")
        self.assertEqual(proc.returncode, 1)
        self.assertIn("unknown agent", proc.stderr)

    def test_list_and_uninstall_agent(self):
        self.newr("install", "--agent", "gemini", "i18n")
        self.assertIn("i18n", self.newr("list", "--agent", "gemini").stdout)
        proc = self.newr("uninstall", "--agent", "gemini", "i18n")
        self.assertIn("uninstalled i18n (for gemini)", proc.stdout)
        self.assertFalse((self.home / ".gemini" / "skills" / "i18n").exists())

    def test_update_upgrades_agent_install(self):
        self.newr("install", "--agent", "cursor", "i18n")
        dest = self.home / ".cursor" / "skills" / "i18n"
        receipt = json.loads((dest / ".newr.json").read_text())
        receipt["version"] = "0.1.0"
        (dest / ".newr.json").write_text(json.dumps(receipt))
        proc = self.newr("update")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("installed i18n 0.3.0", proc.stdout)

    def test_info_shows_agent_installs(self):
        self.newr("install", "--agent", "opencode", "testing")
        out = self.newr("info", "testing").stdout
        self.assertIn("opencode", out)

    # --- skill format (Agent Skills spec) ---

    def parse_frontmatter(self, path: Path) -> dict:
        text = path.read_text(encoding="utf-8")
        match = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
        self.assertIsNotNone(match, "missing frontmatter in %s" % path)
        fields: dict = {}
        for line in match.group(1).splitlines():
            if re.match(r"^[a-z-]+:", line):
                key, _, value = line.partition(":")
                fields[key.strip()] = value.strip().strip('"')
        return fields

    def test_skill_frontmatter_is_spec_valid(self):
        for name in SKILLS:
            skill = REPO_ROOT / "skills" / name
            fields = self.parse_frontmatter(skill / "SKILL.md")
            self.assertEqual(fields.get("name"), name, name)
            desc = fields.get("description", "")
            self.assertGreaterEqual(len(desc), 1, name)
            self.assertLessEqual(len(desc), 1024, name)
            self.assertTrue(set(fields) <= SPEC_FRONTMATTER_FIELDS, name)
            self.assertEqual(fields.get("license"), "MIT", name)
            self.assertIn("0.3.0", (skill / "SKILL.md").read_text(), name)

    def test_skill_script_copies_match_root(self):
        pairs = [
            ("skills/build-discord-bot/scripts/make_cog.py", "scripts/make_cog.py"),
            ("skills/deploy-and-monitor/scripts/check_setup.py", "scripts/check_setup.py"),
        ]
        for copy, root in pairs:
            self.assertEqual(
                (REPO_ROOT / copy).read_bytes(),
                (REPO_ROOT / root).read_bytes(),
                copy,
            )

    # --- npx packaging ---

    def test_package_json_for_npx(self):
        pkg = json.loads((REPO_ROOT / "package.json").read_text())
        self.assertEqual(pkg["version"], "0.3.0")
        self.assertEqual(pkg["bin"], {"newr": "./newr"})
        self.assertIn("newr", pkg["files"])
        self.assertIn("skills/", pkg["files"])
        self.assertTrue(os.access(NEWR, os.X_OK), "newr must be executable (npx bin)")


if __name__ == "__main__":
    unittest.main(verbosity=2)
