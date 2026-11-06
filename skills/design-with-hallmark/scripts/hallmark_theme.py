#!/usr/bin/env python3
"""Apply a Hallmark theme to a Discord bot surface. Stdlib only.
Runs on any OS with Python 3.10+; no OS-specific calls, no network,
no token.

Hallmark is a web-design skill (Nutlope/hallmark v2.0.0): 50 material
themes, a hard Floor of rules, and a linter for web pages. Almost none
of that transfers to Discord directly. Discord renders embeds in its
own font on its own surfaces, with no CSS, no textures, no radii.
What does transfer, and what this helper carries:

  * the theme's accent color -> the embed's one color stripe
    (discord.Embed(color=...)); one accent only, never a gradient.
  * the theme's paper/ink pair -> a web dashboard's page colors
    (every Hallmark theme passes WCAG AA 4.5:1 here; lowest is
    pasteup at 7.96, measured, not claimed).
  * the theme's voice (its material line) -> the words in the embed.
  * the deal: three themes that fit the bot's job, dealt fresh each
    time, so consecutive surfaces do not converge on one look.

Discord limits enforced by validate_embed() (Discord API docs,
https://discord.com/developers/docs/resources/message#embed-limits):
  title 256, description 4096, fields 25 per embed, field name 256,
  field value 1024, footer text 2048, author name 256, 6000 total
  characters across all embeds in one message, 10 embeds per message.

Usage as a library:

    from hallmark_theme import deal, theme, embed_color, discord_embed

    picks = deal("rpg economy shop")          # three discord-strong themes
    color = embed_color("coral")              # 0xEF8B7B as an int
    embed = discord_embed("coral", title="Shop",
                          description="...", fields=[("Gold", "1,200", True)])

Usage as a CLI (run from this directory):

    python3 hallmark_theme.py deal --keywords "rpg economy shop"
    python3 hallmark_theme.py deal --keywords "music bot" --seed 7
    python3 hallmark_theme.py theme coral
    python3 hallmark_theme.py list --strong
    python3 hallmark_theme.py embed-color terminal
"""

import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from hallmark_themes import THEMES  # noqa: E402

DISCORD_DARK_BG = "#313338"  # Discord dark chat background (client value,
# widely documented; Discord publishes no official client hex). The
# 3.0 accent-vs-dark threshold in the theme data is measured
# against this background.

# Discord API embed limits (verified against the official docs, 2026-11-06).
EMBED_LIMITS = {
    "title": 256,
    "description": 4096,
    "fields": 25,
    "field_name": 256,
    "field_value": 1024,
    "footer_text": 2048,
    "author_name": 256,
    "total_chars": 6000,
    "embeds_per_message": 10,
}


def theme(slug):
    """Return one theme's palette dict, or raise KeyError naming the fix."""
    key = str(slug).strip().lower()
    if key in THEMES:
        return THEMES[key]
    close = [s for s in THEMES if s.startswith(key[:4])]
    hint = (" Did you mean: %s?" % ", ".join(sorted(close)[:3])) if close else ""
    raise KeyError("no Hallmark theme named %r.%s Run `list` for all 50." % (slug, hint))


def list_themes(strong_only=False):
    """All themes, or only the 23 that survive Discord's dark client."""
    return [t for t in (THEMES[s] for s in sorted(THEMES))
            if not strong_only or t.get("discord_strong")]


def _words(text):
    return [w for w in "".join(
        c.lower() if c.isalnum() or c == " " else " " for c in text
    ).split() if len(w) > 2]


def _stem(word):
    x = word[:-3] if word.endswith("ing") else word[:-2] if word.endswith("ed") else word
    if len(x) < 3:
        x = word
    return x[:-1] if x.endswith("s") and not x.endswith("ss") else x


def _normalize_seed(seed):
    """One seed value, one hand: the CLI passes seeds as strings,
    library callers pass ints. A numeric string becomes the same
    int, so `deal(..., seed=7)` and `--seed 7` agree. A non-numeric
    string stays a string (random.Random seeds on it deterministically).
    """
    if isinstance(seed, str):
        try:
            return int(seed)
        except ValueError:
            return seed
    return seed


def deal(keywords, n=3, seed=None, strong_only=True):
    """Deal n themes that fit the bot's job, fresh each time.

    Scores each theme by keyword overlap with its Hallmark keyword list
    (the same idea as theme.mjs deal, simplified: one point per query
    word that matches a theme keyword, +2 when a query word appears
    in the theme name). Ties break by seeded random, so the same keywords
    with a different seed deal a different hand. Only discord_strong
    themes are dealt unless strong_only=False: a theme whose accent
    stripe is faint on Discord's dark client is never a good first
    pick, however well its keywords match.
    """
    pool = [t for t in THEMES.values()
            if not strong_only or t.get("discord_strong")]
    query = {_stem(w) for w in _words(keywords or "")}
    scored = []
    for t in pool:
        keys = {_stem(w) for k in t["keywords"] for w in _words(k)}
        hits = sorted(query & keys)
        score = len(hits)
        if any(q in t["slug"] for q in query):
            score += 2
        scored.append((score, hits, t))
    rng = random.Random(_normalize_seed(seed) if seed is not None
                        else random.randrange(1 << 30))
    # Shuffle first so equal scores break randomly instead of
    # alphabetically; then take the top n by score.
    rng.shuffle(scored)
    scored.sort(key=lambda s: s[0], reverse=True)
    picks = [{"slug": t["slug"], "name": t["name"], "score": s,
              "hits": h, "accent": t["accent"],
              "material": t["material"]} for s, h, t in scored[:n]]
    return picks


def embed_color(slug):
    """A theme's accent as a Discord color int (0xRRGGBB)."""
    return int(theme(slug)["accent"].lstrip("#"), 16)


def dashboard_tokens(slug):
    """A theme's paper/ink pair as CSS custom properties for a dashboard."""
    t = theme(slug)
    return {
        "--color-paper": t["paper"],
        "--color-paper-2": t.get("paper2", t["paper"]),
        "--color-paper-3": t.get("paper3", t["paper"]),
        "--color-ink": t["ink"],
        "--color-ink-2": t.get("ink2", t["ink"]),
        "--color-muted": t.get("muted", t["ink"]),
        "--color-rule": t.get("rule", t["paper"]),
        "--color-accent": t["accent"],
        "--color-accent-ink": t.get("accent_ink", t["ink"]),
        "--color-focus": t.get("focus", t["accent"]),
    }


def embed_total_chars(embed):
    """Characters counted toward the 6000 total: title, description,
    field names and values, footer text, author name. Raw lengths;
    Discord trims whitespace first, so this is the stricter count."""
    total = len(embed.get("title") or "") + len(embed.get("description") or "")
    for f in embed.get("fields") or []:
        total += len(f.get("name") or "") + len(f.get("value") or "")
    total += len((embed.get("footer") or {}).get("text") or "")
    total += len((embed.get("author") or {}).get("name") or "")
    return total


def validate_embed(embed):
    """Return a list of Discord limit violations (empty means it sends).

    Checks the hard limits only. It cannot check taste: whether the
    accent fits the bot, whether the copy is real, whether one fact is
    repeated in four places. Those are the skill's job, not this file's.

    Discord trims leading and trailing whitespace before checking
    limits, and a field that is only whitespace counts as empty and
    is rejected. A whitespace-only title, description, field name or
    value is therefore reported here even though its raw length
    looks fine.
    """
    problems = []
    lim = EMBED_LIMITS
    for label, value in (("title", embed.get("title")),
                         ("description", embed.get("description")),
                         ("footer text",
                          (embed.get("footer") or {}).get("text")),
                         ("author name",
                          (embed.get("author") or {}).get("name"))):
        # Empty means "not set" for these parts; only a non-empty
        # whitespace-only string is a problem.
        if value and not str(value).strip():
            problems.append("%s is whitespace-only "
                            "(Discord rejects it as empty)" % label)
    if len(embed.get("title") or "") > lim["title"]:
        problems.append("title is %d chars (max %d)"
                        % (len(embed["title"]), lim["title"]))
    if len(embed.get("description") or "") > lim["description"]:
        problems.append("description is %d chars (max %d)"
                        % (len(embed["description"]), lim["description"]))
    fields = embed.get("fields") or []
    if len(fields) > lim["fields"]:
        problems.append("%d fields (max %d)" % (len(fields), lim["fields"]))
    for f in fields:
        if not str(f.get("name") or "").strip():
            problems.append("a field name is blank or whitespace-only "
                            "(Discord rejects it as empty)")
        if not str(f.get("value") or "").strip():
            problems.append("field %r value is blank or whitespace-only "
                            "(Discord rejects it as empty)"
                            % (f.get("name") or ""))
        if len(f.get("name") or "") > lim["field_name"]:
            problems.append("field name %r is %d chars (max %d)"
                            % (f.get("name"), len(f.get("name") or ""),
                               lim["field_name"]))
        if len(f.get("value") or "") > lim["field_value"]:
            problems.append("field %r value is %d chars (max %d)"
                            % (f.get("name"), len(f.get("value") or ""),
                               lim["field_value"]))
    footer = (embed.get("footer") or {}).get("text") or ""
    if len(footer) > lim["footer_text"]:
        problems.append("footer is %d chars (max %d)"
                        % (len(footer), lim["footer_text"]))
    author = (embed.get("author") or {}).get("name") or ""
    if len(author) > lim["author_name"]:
        problems.append("author name is %d chars (max %d)"
                        % (len(author), lim["author_name"]))
    total = embed_total_chars(embed)
    if total > lim["total_chars"]:
        problems.append("embed totals %d chars (max %d across the message)"
                        % (total, lim["total_chars"]))
    return problems


def discord_embed(slug, title="", description="", fields=None,
                  footer=None, author=None, url=None, thumbnail=None,
                  image=None, timestamp=None):
    """Build a discord.py-ready embed dict in a Hallmark theme.

    Returns the dict (pass it to discord.Embed.from_dict). Raises
    ValueError listing every Discord limit the embed breaks. Fix the
    copy, do not catch and send anyway.
    """
    t = theme(slug)
    embed = {"color": int(t["accent"].lstrip("#"), 16)}
    if title:
        embed["title"] = title
    if description:
        embed["description"] = description
    if url:
        embed["url"] = url
    if fields:
        embed["fields"] = [{"name": n, "value": v, "inline": bool(i)}
                           for n, v, i in fields]
    if footer:
        embed["footer"] = {"text": footer}
    if author:
        embed["author"] = {"name": author}
    if thumbnail:
        embed["thumbnail"] = {"url": thumbnail}
    if image:
        embed["image"] = {"url": image}
    if timestamp:
        # Embed.from_dict only accepts ISO strings: a datetime (or int)
        # raises TypeError fromisoformat. Normalize here so callers can
        # pass a datetime.
        embed["timestamp"] = (
            timestamp.isoformat() if hasattr(timestamp, "isoformat")
            else str(timestamp))
    problems = validate_embed(embed)
    if problems:
        raise ValueError("embed in theme %s breaks Discord limits: %s"
                         % (t["slug"], "; ".join(problems)))
    return embed


def _cli(argv):
    if not argv or argv[0] in ("-h", "--help", "help"):
        print(__doc__.split("Usage as a CLI")[0].rstrip())
        print("Usage as a CLI (run from this directory):\n")
        print(__doc__.split("Usage as a CLI (run from this directory):")[1].lstrip("\n").rstrip())
        return 0
    cmd = argv[0]
    if cmd == "list":
        strong = "--strong" in argv
        for t in list_themes(strong_only=strong):
            mark = " *" if t.get("discord_strong") else ""
            print("%-12s %-7s %-14s %s%s" % (t["slug"], t["accent"],
                  t["genre"], t["name"], mark))
        print("\n* = discord-strong: accent stripe reads on Discord dark.")
        return 0
    if cmd == "theme":
        if len(argv) < 2:
            print("usage: hallmark_theme.py theme <slug>", file=sys.stderr)
            return 2
        try:
            t = theme(argv[1])
        except KeyError as e:
            print(e, file=sys.stderr)
            return 1
        print(json.dumps(t, indent=2))
        return 0
    if cmd == "embed-color":
        if len(argv) < 2:
            print("usage: hallmark_theme.py embed-color <slug>", file=sys.stderr)
            return 2
        try:
            print("0x%06X (%d)" % (embed_color(argv[1]), embed_color(argv[1])))
        except KeyError as e:
            print(e, file=sys.stderr)
            return 1
        return 0
    if cmd == "deal":
        keywords = ""
        seed = None
        strong = True
        i = 1
        while i < len(argv):
            if argv[i] == "--keywords" and i + 1 < len(argv):
                keywords = argv[i + 1]
                i += 2
            elif argv[i] == "--seed" and i + 1 < len(argv):
                seed = argv[i + 1]
                i += 2
            elif argv[i] == "--all":
                strong = False
                i += 1
            else:
                i += 1
        picks = deal(keywords, seed=seed, strong_only=strong)
        for n, p in enumerate(picks, 1):
            hits = ("fits: %s" % ", ".join(p["hits"])) if p["hits"] else "no keyword hit"
            print("%d. %s (%s) · %s · %s · %s"
                  % (n, p["name"], p["slug"], p["accent"], hits, p["material"]))
        return 0
    print("unknown command %r (try: list, theme, embed-color, deal)" % cmd,
          file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(_cli(sys.argv[1:]))
