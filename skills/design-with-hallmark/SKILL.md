---
name: design-with-hallmark
description: "Apply a Hallmark theme to a Discord bot's surfaces: embeds, web dashboard, README visuals. Use when the bot needs a look that is not Discord's default blurple on everything, when embeds from different features should feel like one bot, or when a dashboard or README page should carry the same theme. Do NOT use for the bot's logic, commands, or economy; load the skill for that job instead."
license: MIT
compatibility: "discord.py 2.x, Python 3.10+ on any OS, no paid services"
metadata:
  version: "0.5.0"
  author: "drewdestar"
---

# Design with Hallmark

Hallmark (Nutlope/hallmark v2.0.0, MIT) is a design skill for web
pages: 50 material themes, a hard Floor of rules, and a linter for
the tells that make AI-built pages look generated. This skill is not
Hallmark itself. It is the honest part of Hallmark that survives
inside Discord, where there is no CSS, no font choice, no texture,
and no layout to control.

## What transfers, what does not

| Hallmark piece | In Discord | Notes |
|---|---|---|
| Theme accent color | Embed color stripe, one per embed | `discord.Embed(color=0xEF8B7B)`; one accent only, never a gradient (Discord has no gradients) |
| Theme paper/ink pair | Web dashboard page colors | Every theme passes WCAG AA 4.5:1 here; lowest is pasteup at 7.96, measured |
| Theme voice (material line) | The words in the embed | Write in the theme's voice, in plain sentences |
| The deal (three themes) | Picking a look per feature | Deal fresh each time so features do not converge |
| The Floor copy rules | Embed copy | No invented numbers, no eyebrow labels, no middle-dot meta, no em dash |
| Fonts, textures, radii, spacing | Does not transfer | Discord renders embeds in its own font on its own surfaces |
| Hero, fold, section rhythm | Does not transfer | An embed is one card; there is no page to compose |
| sloplint | Does not transfer | It lints HTML/CSS; use `validate_embed()` here instead |
| Photo library (755 photos) | Embed image URL, with credit | Only a Wikimedia Commons URL from the library, credited in the footer |

## The Floor, adapted for Discord

These are Hallmark gates, restated for embeds. They bind every
surface this skill builds.

1. **No invented numbers.** A balance, a price, a count, a rank:
   read it from the ledger or the database, or do not print it.
   (Hallmark gate 46a.)
2. **No eyebrow labels.** No small label above a title announcing
   it ("PROFILE", "SHOP"), no tracked-caps field names. A field
   name says what the value is ("Gold", not "YOUR GOLD"). (Gate 54.)
3. **No middle-dot meta strings.** No "Level 12 · 4,830 gold ·
   Rank 3" line. One fact per line, or one fact per field.
   (Gate 63.)
4. **No em dash** in any message, embed, or reply the bot sends.
   Repo-wide rule, not just this skill.
5. **One accent per embed.** The theme's accent is the stripe.
   A second color in the same embed is decoration without a job.
   (Each theme carries one accent token; gates 2a and 23 bound
   gradients and accent spread.)
6. **No emoji as an icon.** An emoji in a field name is not a
   design. Use a real custom emoji the server owns, or plain text.
   (Gate 30a.)
7. **One idea per embed.** One embed answers one question. Do not
   send 10 embeds in one message because the limit allows 10; a
   list belongs in fields, not in ten cards. (Gate 58, adapted.)
8. **Every fact once.** A price in the title, in a field, and in
   the footer is filler. Say it where it does work. (Gate 69.)

## The deal

Deal three themes that fit the bot's job, then pick one, from the discord-strong pool. See `references/deal.md`.

## Embeds: the mapping

The embed mapping: `discord_embed()`, Discord's embed limits, and the copy rules. See `references/embeds.md`.

## Dashboard: the mapping

A dashboard is a web page, so the full theme applies there. Take
the tokens from the helper and use them as the page's CSS
variables; do not invent colors alongside them.

```python
from hallmark_theme import dashboard_tokens

tokens = dashboard_tokens("console")
# {"--color-paper": "#0d1013", "--color-ink": "#eceff2",
#  "--color-accent": "#f7b83d", "--color-accent-ink": ...}
```

- Page background is `--color-paper`, text is `--color-ink`.
  Their contrast is 4.5:1 or better in all 50 themes.
- The primary button is `--color-accent` with
  `--color-accent-ink` text. One button style per page.
- Focus rings are `--color-focus`, shown instantly.
- The theme's display face names a web font; load it only if the
  dashboard already loads web fonts, and fall back to the system
  stack when it does not. A dashboard that cannot load fonts
  keeps the colors and drops the faces; that is a valid subset.
- Run Hallmark's own `sloplint` on the dashboard when Hallmark
  is installed. This skill does not re-implement it, and the
  helper cannot lint a page.

## README visuals: the mapping

Diagrams and banners in the README use the theme's paper as the
background and its accent as the one signal color. A banner for a
bot themed Coral is warm grey `#f8f4f1` with a coral `#ef8b7b`
mark, not Discord blurple. The theme's display face may set the
banner's words when the image is rendered with web fonts;
otherwise use a plain grotesque and keep the colors.

## What this skill never does

- It never picks a theme for a bot it has not seen. Deal from
  the bot's job words, or use blurple.
- It never claims a font, a texture, a radius, or a layout
  inside Discord. Those do not exist there.
- It never invents a price, a balance, a count, or a quote to
  fill an embed. An empty field is honest; a filled lie is not.
- It never sends an embed the helper rejected. A `ValueError`
  from `discord_embed()` is a broken embed, not a suggestion.

## Portability

The helper is stdlib-only Python 3.10+, with no OS-specific
calls, no network, and no token, so it should run wherever Python
3.10+ runs: macOS, Linux, and Windows. On Windows, `python`
(or `py`) runs the helper where this page says `python3`.
Colors and the deal do not depend on language; keyword
matching is English-only (see The deal). The embed example
on this page runs on discord.py 2.7.1, and `from_dict` is
discord.py 2.x API, not a version-specific trick.

What was not run here: execution on Windows and macOS, and
live rendering on mobile Discord clients, were not run from
the Linux machine this skill was built on. The mechanics are
OS-independent by construction; the clients are not verified
here. If a theme's stripe looks faint on a client, pick a
stronger theme from the strong pool.

## Verify

- `python3 tests/test_hallmark_theme.py` passes (stdlib
  unittest; also runs under `python3 -m unittest discover -s tests`).
- `python3 skills/design-with-hallmark/scripts/hallmark_theme.py deal --keywords "<the bot's job>"`
  deals three discord-strong themes.
- `python3 skills/design-with-hallmark/scripts/hallmark_theme.py embed-color <slug>`
  prints the exact int the embed sends.
- Build one embed with `discord_embed()`, then confirm
  discord.py accepts it (`discord.Embed.from_dict(...)` must
  build without error), then verify it live in Discord: the
  stripe is the theme's accent, the title fits, no field is cut
  off, and every number in it is real. A green test suite is
  not proof the bot answers.
