#!/usr/bin/env python3
"""Tests for the antislop skill and its mechanical checker.

Stdlib unittest only; run with:
    python3 tests/test_antislop.py
from the repo root, or: python3 -m unittest discover -s tests.

The skill follows the Agent Skills spec enforced in test_newr.py
(name equals the folder name, description 1-1024 chars, only spec
frontmatter fields, license MIT, body under 500 lines). The version
line is checked against package.json dynamically, so a version bump
never needs this file edited.
"""

import json
import re
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILL = REPO_ROOT / "skills" / "antislop"
CHECKER = REPO_ROOT / "scripts" / "check_antislop.py"
SPEC_FIELDS = {"name", "description", "license", "compatibility",
               "metadata", "allowed-tools"}


def run_checker(text, extra=()):
    proc = subprocess.run(
        [sys.executable, str(CHECKER), *extra],
        input=text, capture_output=True, text=True, timeout=30)
    return proc


class SkillFormatTests(unittest.TestCase):
    def parse_frontmatter(self, path):
        text = path.read_text(encoding="utf-8")
        match = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
        self.assertIsNotNone(match, "missing frontmatter in %s" % path)
        fields = {}
        for line in match.group(1).splitlines():
            if re.match(r"^[a-z-]+:", line):
                key, _, value = line.partition(":")
                fields[key.strip()] = value.strip().strip('"')
        return fields

    def test_frontmatter_is_spec_valid(self):
        fields = self.parse_frontmatter(SKILL / "SKILL.md")
        self.assertEqual(fields.get("name"), "antislop")
        desc = fields.get("description", "")
        self.assertGreaterEqual(len(desc), 1)
        self.assertLessEqual(len(desc), 1024)
        self.assertTrue(set(fields) <= SPEC_FIELDS)
        self.assertEqual(fields.get("license"), "MIT")

    def test_version_matches_package_json(self):
        pkg = json.loads((REPO_ROOT / "package.json").read_text())
        text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn('version: "%s"' % pkg["version"], text)

    def test_body_under_500_lines(self):
        lines = (SKILL / "SKILL.md").read_text(encoding="utf-8").splitlines()
        self.assertLess(len(lines), 500, "SKILL.md body must stay under 500 lines")

    def test_script_copies_match_root(self):
        self.assertEqual(
            (SKILL / "scripts" / "check_antislop.py").read_bytes(),
            (REPO_ROOT / "scripts" / "check_antislop.py").read_bytes(),
        )

    def test_skill_cites_upstream_rules_that_exist(self):
        upstream = (Path.home() / "workspace" / "skills-docs" / "repos"
                    / "anti-slop" / "antislop.md")
        if not upstream.is_file():
            self.skipTest("upstream anti-slop clone not present on this machine")
        upstream_text = upstream.read_text(encoding="utf-8")
        # The skill is SKILL.md plus its references/ files: the rule
        # table lives in references/transfer.md, so cite-check across
        # all of them.
        text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        refs_dir = SKILL / "references"
        if refs_dir.is_dir():
            for ref in sorted(refs_dir.glob("*.md")):
                text += "\n" + ref.read_text(encoding="utf-8")
        cited = sorted(set(re.findall(r"R-(\d{2})", text)), key=int)
        self.assertGreater(len(cited), 10, "skill should cite 10+ upstream rules")
        for number in cited:
            self.assertIn("R-%s" % number, upstream_text,
                          "cited rule R-%s not found upstream" % number)


class CheckerTests(unittest.TestCase):
    def test_clean_text_exits_zero(self):
        proc = run_checker("Your balance is 60 coins. Use /shop to spend them.\n")
        self.assertEqual(proc.returncode, 0, proc.stdout)
        self.assertIn("clean", proc.stdout)

    def test_em_dash_is_error(self):
        proc = run_checker("Fast, secure \u2014 and built for you.\n")
        self.assertEqual(proc.returncode, 2, proc.stdout)
        self.assertIn("EMDASH", proc.stdout)
        self.assertIn("R-02", proc.stdout)

    def test_buzzword_is_error(self):
        proc = run_checker("Our Revolutionary AI Powered engine!\n")
        self.assertEqual(proc.returncode, 2, proc.stdout)
        self.assertIn("BUZZWORD", proc.stdout)

    def test_temporal_runway_v326_is_error(self):
        proc = run_checker("In today's fast-paced world, bots need to be fast.\n")
        self.assertEqual(proc.returncode, 2, proc.stdout)
        self.assertIn("TEMPORAL_RUNWAY", proc.stdout)

    def test_theatrical_takeaway_v326_is_error(self):
        proc = run_checker("Rollbacks cut downtime by 40%. Read that again.\n")
        self.assertEqual(proc.returncode, 2, proc.stdout)
        self.assertIn("THEATRICAL", proc.stdout)

    def test_titlecase_list_v326_is_warning(self):
        proc = run_checker("- Comprehensive Security Audits Across All Repositories\n")
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertIn("TITLECASE_LIST", proc.stdout)

    def test_sentence_case_list_is_clean(self):
        proc = run_checker("- Comprehensive security audits across all repositories\n")
        self.assertEqual(proc.returncode, 0, proc.stdout)

    def test_fake_stat_shape_is_warning(self):
        proc = run_checker("Join 10K+ users with 99.9% uptime!\n")
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertIn("FAKE_STAT", proc.stdout)

    def test_box_banner_is_warning(self):
        proc = run_checker("# ========================\n# Auth\n")
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertIn("BOX_BANNER", proc.stdout)
        # Labelled separator (// -------- WORKFLOW --------) is a banner too.
        proc = run_checker("// -------- WORKFLOW --------\n")
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertIn("BOX_BANNER", proc.stdout)
        # A bare line of = in Markdown is a setext heading underline, not a
        # comment banner, so it stays clean.
        self.assertEqual(run_checker("Heading\n========\n").returncode, 0)

    def test_all_caps_is_warning(self):
        proc = run_checker("The launch is ready and WE NEED TO MOVE NOW today.\n")
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertIn("ALL_CAPS", proc.stdout)

    def test_signposting_is_warning(self):
        proc = run_checker("Let's dive in and see the commands.\n")
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertIn("SIGNPOSTING", proc.stdout)

    def test_generic_cta_jekardah_is_warning(self):
        proc = run_checker("What do you think?\n")
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertIn("GENERIC_CTA", proc.stdout)

    def test_indonesian_runway_is_error(self):
        proc = run_checker(
            "Di era digital yang semakin berkembang pesat, personal branding penting.\n")
        self.assertEqual(proc.returncode, 2, proc.stdout)
        self.assertIn("ID_TEMPORAL_RUNWAY", proc.stdout)

    def test_indonesian_runway_historical_is_clean(self):
        # "Di era 90-an" is ordinary historical Indonesian, not a runway:
        # the pattern is narrow on purpose.
        proc = run_checker("Di era 90-an, game ini populer.\n")
        self.assertEqual(proc.returncode, 0, proc.stdout)

    def test_indonesian_fake_contrast_is_error(self):
        proc = run_checker("Ini bukan cuma bot, tapi temanmu.\n")
        self.assertEqual(proc.returncode, 2, proc.stdout)
        self.assertIn("ID_FAKE_CONTRAST", proc.stdout)

    def test_indonesian_signposting_is_warning(self):
        proc = run_checker("Penting untuk dicatat, saldo kamu 60 koin.\n")
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertIn("ID_SIGNPOSTING", proc.stdout)

    def test_indonesian_inflated_is_warning(self):
        proc = run_checker("Masa depan sudah di sini.\n")
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertIn("ID_INFLATED", proc.stdout)

    def test_json_output_parses(self):
        proc = run_checker("Fast \u2014 and Seamless!\n", extra=("--json",))
        self.assertEqual(proc.returncode, 2, proc.stdout)
        data = json.loads(proc.stdout)
        self.assertTrue(all(set(d) == {"check", "severity", "line", "message", "rule"}
                            for d in data))
        self.assertEqual({d["check"] for d in data}, {"EMDASH", "BUZZWORD"})

    def test_file_argument(self):
        target = REPO_ROOT / "tests" / "test_antislop.py"
        proc = subprocess.run([sys.executable, str(CHECKER), str(target)],
                              capture_output=True, text=True, timeout=30)
        self.assertIn(proc.returncode, (0, 1, 2))


if __name__ == "__main__":
    unittest.main()
