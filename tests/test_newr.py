#!/usr/bin/env python3
"""Tests for the newr CLI. Stdlib unittest only; run with:
    python3 tests/test_newr.py
from the repo root, or: python3 -m unittest discover -s tests.

Every test runs newr against a temporary NEWR_HOME and the local
checkout as its package source (auto-detected: the newr script sits
next to registry.json), so no network is needed.
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
NEWR = REPO_ROOT / "newr"


class NewrTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name) / "home"
        self.home.mkdir(parents=True)
        self.env = dict(os.environ)
        self.env["NEWR_HOME"] = str(self.home)
        # Point the CLI at this checkout explicitly; auto-detection
        # would find it anyway, but the env var makes it certain.
        self.env["NEWR_LOCAL_SOURCE"] = str(REPO_ROOT)

    def tearDown(self):
        self.tmp.cleanup()

    def newr(self, *args, cwd=None):
        proc = subprocess.run(
            [sys.executable, str(NEWR), *args],
            capture_output=True, text=True, env=self.env,
            cwd=str(cwd or self.home),
        )
        return proc

    def test_version_and_help(self):
        self.assertIn("newr 0.2.0", self.newr("version").stdout)
        self.assertIn("install", self.newr("help").stdout)
        self.assertEqual(self.newr("bogus-command").returncode, 2)

    def test_search_lists_all_packages(self):
        out = self.newr("search").stdout
        for name in ("build-discord-bot", "slash-commands", "economy-database",
                     "i18n", "deploy-and-monitor", "testing", "starter-bot"):
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
        self.assertEqual(receipt["version"], "0.2.0")
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
        for name in ("build-discord-bot", "slash-commands", "economy-database",
                     "i18n", "deploy-and-monitor", "testing"):
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
        self.assertIn("installed i18n 0.2.0", proc.stdout)
        self.assertIn("everything is up to date", self.newr("update").stdout)

    def test_install_unknown_package_fails_cleanly(self):
        proc = self.newr("install", "no-such-skill")
        self.assertEqual(proc.returncode, 1)
        self.assertIn("no package named", proc.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)
