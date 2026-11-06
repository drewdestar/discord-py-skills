#!/usr/bin/env python3
"""Tests for the design-with-hallmark skill helper. Stdlib unittest
only; run with:
    python3 tests/test_hallmark_theme.py
from the repo root, or: python3 -m unittest discover -s tests.

Covers the generated theme data (all 50 Hallmark v2.0.0 themes, with
the measured Discord-suitability numbers), the deal, the embed
builder, the Discord-limit validation, and the CLI. No Discord
token, no network: everything is computed from the data module.
"""

import ast
import json
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
HELPER_DIR = (REPO_ROOT / "skills/design-with-hallmark/scripts")
HELPER = HELPER_DIR / "hallmark_theme.py"

sys.path.insert(0, str(HELPER_DIR))
import hallmark_theme  # noqa: E402
from hallmark_themes import THEMES  # noqa: E402

DISCORD_STRONG_COUNT = 23


class ThemeDataTest(unittest.TestCase):
    def test_all_fifty_themes_present(self):
        self.assertEqual(len(THEMES), 50)

    def test_every_theme_has_core_tokens(self):
        for slug, t in THEMES.items():
            for key in ("paper", "ink", "accent"):
                self.assertIn(key, t, "%s missing %s" % (slug, key))
                self.assertRegex(t[key], r"^#[0-9a-f]{6}$",
                                 "%s %s is not a hex color" % (slug, key))

    def test_every_paper_ink_pair_passes_aa(self):
        # Lowest measured is pasteup at 7.96; the bar is 4.5.
        for slug, t in THEMES.items():
            self.assertGreaterEqual(
                t["paper_ink_contrast"], 4.5,
                "%s paper/ink contrast %.2f fails WCAG AA"
                % (slug, t["paper_ink_contrast"]))

    def test_discord_strong_count_is_23(self):
        strong = [s for s, t in THEMES.items() if t.get("discord_strong")]
        self.assertEqual(len(strong), DISCORD_STRONG_COUNT)

    def test_strong_means_visible_stripe_and_contrast(self):
        for slug, t in THEMES.items():
            if t.get("discord_strong"):
                self.assertGreaterEqual(t["accent_chroma"], 0.10, slug)
                self.assertGreaterEqual(t["accent_vs_discord_dark"], 3.0,
                                        slug)
            else:
                self.assertTrue(
                    t["accent_chroma"] < 0.10
                    or t["accent_vs_discord_dark"] < 3.0,
                    "%s is marked weak but meets both thresholds" % slug)

    def test_known_accents(self):
        # Spot checks against the upstream token blocks, converted
        # OKLCH -> hex with Hallmark's own matrix.
        self.assertEqual(THEMES["coral"]["accent"], "#ef8b7b")
        self.assertEqual(THEMES["terminal"]["accent"], "#7ef473")
        self.assertEqual(THEMES["brutal"]["accent"], "#f2e309")
        self.assertEqual(THEMES["blueprint"]["accent"], "#eef6fd")
        self.assertFalse(THEMES["blueprint"]["discord_strong"])


class LookupTest(unittest.TestCase):
    def test_theme_returns_palette(self):
        t = hallmark_theme.theme("coral")
        self.assertEqual(t["name"], "Coral")
        self.assertEqual(t["paper"], "#f8f4f1")

    def test_theme_lookup_is_case_insensitive(self):
        self.assertEqual(hallmark_theme.theme("Coral")["slug"], "coral")

    def test_theme_unknown_raises_with_hint(self):
        with self.assertRaises(KeyError):
            hallmark_theme.theme("nope")

    def test_list_strong_only(self):
        self.assertEqual(
            len(hallmark_theme.list_themes(strong_only=True)),
            DISCORD_STRONG_COUNT)
        self.assertEqual(len(hallmark_theme.list_themes()), 50)


class DealTest(unittest.TestCase):
    def test_deal_returns_three_strong_themes(self):
        picks = hallmark_theme.deal("rpg economy shop", seed=7)
        self.assertEqual(len(picks), 3)
        for p in picks:
            self.assertTrue(THEMES[p["slug"]]["discord_strong"], p["slug"])
            for key in ("slug", "name", "score", "hits", "accent",
                        "material"):
                self.assertIn(key, p)

    def test_deal_is_deterministic_for_a_seed(self):
        a = hallmark_theme.deal("music bot", seed=1)
        b = hallmark_theme.deal("music bot", seed=1)
        self.assertEqual([p["slug"] for p in a], [p["slug"] for p in b])

    def test_deal_seed_string_matches_int(self):
        # The CLI passes --seed as a string; the library takes an
        # int. The same seed value must deal the same hand.
        a = hallmark_theme.deal("shop", seed=7)
        b = hallmark_theme.deal("shop", seed="7")
        self.assertEqual([p["slug"] for p in a], [p["slug"] for p in b])

    def test_deal_scores_keyword_hits(self):
        # "shop" appears in squeeze ("farm shop") and darkroom
        # ("print shop") keywords, and alone in sticker's.
        picks = hallmark_theme.deal("shop", seed=3)
        hit_slugs = {p["slug"] for p in picks if p["hits"]}
        self.assertTrue(hit_slugs, "no pick matched the keyword 'shop'")
        self.assertIn("shop", picks[0]["hits"])

    def test_deal_with_no_keywords_still_deals_three(self):
        picks = hallmark_theme.deal("", seed=0)
        self.assertEqual(len(picks), 3)

    def test_deal_non_english_words_still_deals_three(self):
        # Keywords are English words. A job described in another
        # language matches nothing, but the deal still deals three
        # discord-strong themes with no hits instead of failing
        # or returning nothing.
        picks = hallmark_theme.deal("toko ekonomi rpg", seed=7)
        self.assertEqual(len(picks), 3)
        for p in picks:
            self.assertEqual(p["score"], 0, p["slug"])
            self.assertEqual(p["hits"], [])
            self.assertTrue(THEMES[p["slug"]]["discord_strong"], p["slug"])

    def test_deal_all_pool_can_include_weak_themes(self):
        # strong_only=False draws from all 50; with a keyword no
        # strong theme matches, a weak theme can top the deal.
        picks = hallmark_theme.deal("bakery", seed=0, strong_only=False)
        self.assertEqual(len(picks), 3)
        self.assertEqual(picks[0]["slug"], "vellum")
        self.assertFalse(THEMES["vellum"]["discord_strong"])


class EmbedTest(unittest.TestCase):
    def test_embed_color_is_discord_int(self):
        self.assertEqual(hallmark_theme.embed_color("coral"), 0xEF8B7B)
        self.assertEqual(hallmark_theme.embed_color("terminal"), 0x7EF473)
        self.assertIsInstance(hallmark_theme.embed_color("hum"), int)

    def test_dashboard_tokens_are_css_vars(self):
        tokens = hallmark_theme.dashboard_tokens("console")
        self.assertEqual(tokens["--color-paper"], "#0d1013")
        self.assertEqual(tokens["--color-ink"], "#eceff2")
        self.assertEqual(tokens["--color-accent"], "#f7b83d")
        for key, value in tokens.items():
            self.assertTrue(key.startswith("--color-"), key)
            self.assertRegex(value, r"^#[0-9a-f]{6}$")

    def test_discord_embed_builds_valid_dict(self):
        embed = hallmark_theme.discord_embed(
            "coral", title="Shop",
            description="Spend gold on things that do something.",
            fields=[("Iron Sword", "1,200 gold, +5 attack", True),
                    ("Your gold", "4,830", False)],
            footer="Prices change when the shop restocks.")
        self.assertEqual(embed["color"], 0xEF8B7B)
        self.assertEqual(embed["title"], "Shop")
        self.assertEqual(len(embed["fields"]), 2)
        self.assertEqual(embed["fields"][0]["inline"], True)
        self.assertEqual(embed["fields"][1]["inline"], False)

    def test_discord_embed_rejects_too_long_title(self):
        with self.assertRaises(ValueError) as ctx:
            hallmark_theme.discord_embed("coral", title="x" * 257)
        self.assertIn("title", str(ctx.exception))

    def test_discord_embed_rejects_unknown_theme(self):
        with self.assertRaises(KeyError):
            hallmark_theme.discord_embed("nope", title="Hi")


class ValidateEmbedTest(unittest.TestCase):
    def test_clean_embed_passes(self):
        self.assertEqual(
            hallmark_theme.validate_embed({"title": "Shop",
                                           "description": "Buy things.",
                                           "fields": [{"name": "Gold",
                                                       "value": "100",
                                                       "inline": True}]}),
            [])

    def test_each_limit_is_reported(self):
        bad = {"title": "x" * 300,
               "description": "y" * 5000,
               "fields": [{"name": "n" * 300, "value": "v" * 2000,
                           "inline": False}] * 26,
               "footer": {"text": "f" * 3000},
               "author": {"name": "a" * 300}}
        problems = hallmark_theme.validate_embed(bad)
        self.assertTrue(any("title" in p for p in problems))
        self.assertTrue(any("description" in p for p in problems))
        self.assertTrue(any("26 fields" in p for p in problems))
        self.assertTrue(any("field name" in p for p in problems))
        self.assertTrue(any("footer" in p for p in problems))
        self.assertTrue(any("author" in p for p in problems))

    def test_whitespace_only_text_is_reported(self):
        # Discord trims before checking; whitespace-only counts as empty.
        problems = hallmark_theme.validate_embed(
            {"title": "Shop",
             "fields": [{"name": "Gold", "value": "   ", "inline": True}]})
        self.assertTrue(any("whitespace-only" in p for p in problems))
        problems = hallmark_theme.validate_embed({"title": "   "})
        self.assertTrue(any("whitespace-only" in p for p in problems))

    def test_total_over_6000_is_reported(self):
        embed = {"title": "T", "description": "d" * 4096,
                 "fields": [{"name": "f", "value": "v" * 1024,
                             "inline": False}] * 2}
        problems = hallmark_theme.validate_embed(embed)
        self.assertTrue(any("totals" in p for p in problems))


class CliTest(unittest.TestCase):
    def _run(self, *args):
        return subprocess.run([sys.executable, str(HELPER), *args],
                              capture_output=True, text=True,
                              cwd=str(HELPER_DIR))

    def test_cli_deal(self):
        proc = self._run("deal", "--keywords", "rpg economy shop",
                         "--seed", "7")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(len(proc.stdout.strip().splitlines()), 3)

    def test_cli_deal_all(self):
        proc = self._run("deal", "--keywords", "bakery", "--seed", "0",
                         "--all")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("Vellum", proc.stdout)

    def test_cli_theme(self):
        proc = self._run("theme", "coral")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(json.loads(proc.stdout)["accent"], "#ef8b7b")

    def test_cli_embed_color(self):
        proc = self._run("embed-color", "terminal")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("0x7EF473", proc.stdout)

    def test_cli_list_strong(self):
        proc = self._run("list", "--strong")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(len(proc.stdout.strip().splitlines()),
                         DISCORD_STRONG_COUNT + 2)  # + legend line + blank

    def test_cli_unknown_command_fails(self):
        proc = self._run("bogus")
        self.assertNotEqual(proc.returncode, 0)


class PortabilityTest(unittest.TestCase):
    def test_helper_imports_no_os_specific_modules(self):
        # The helper must run on any OS with Python 3.10+: no
        # OS-specific imports and no sys.platform check.
        source = (HELPER_DIR / "hallmark_theme.py").read_text()
        tree = ast.parse(source)
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])
            elif (isinstance(node, ast.Attribute)
                    and isinstance(node.value, ast.Name)
                    and node.value.id == "sys"
                    and node.attr == "platform"):
                self.fail("helper reads sys.platform")
        forbidden = {"os", "subprocess", "ctypes", "locale", "winreg",
                     "msvcrt", "posix", "nt", "platform"}
        self.assertFalse(imported & forbidden,
                         "OS-specific imports: %s"
                         % sorted(imported & forbidden))

    def test_helper_data_is_ascii_only(self):
        # Theme data with no non-ASCII bytes prints cleanly on any
        # console, including a Windows console on a legacy code page.
        for slug, t in THEMES.items():
            for key, value in t.items():
                if isinstance(value, str):
                    self.assertTrue(value.isascii(),
                                    "%s.%s has non-ASCII text" % (slug, key))
                elif isinstance(value, list):
                    for item in value:
                        self.assertTrue(item.isascii(),
                                        "%s.%s has non-ASCII text"
                                        % (slug, key))


class RegistryTest(unittest.TestCase):
    def test_registry_has_the_skill(self):
        registry = json.loads((REPO_ROOT / "registry.json").read_text())
        entry = next((p for p in registry["packages"]
                      if p["name"] == "design-with-hallmark"), None)
        self.assertIsNotNone(entry, "design-with-hallmark missing from registry")
        self.assertEqual(entry["version"], "0.5.0")
        self.assertEqual(entry["path"],
                         "skills/design-with-hallmark")
        self.assertEqual(entry["type"], "skill")

    def test_skill_frontmatter_version(self):
        text = (REPO_ROOT / "skills/design-with-hallmark/SKILL.md"
                ).read_text()
        self.assertIn('version: "0.5.0"', text)


if __name__ == "__main__":
    unittest.main()
