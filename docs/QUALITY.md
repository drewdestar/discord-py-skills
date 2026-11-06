# Quality Guide

This repo builds Discord bots through AI agents. The output is only
as good as the instructions, so the skills carry an explicit quality
bar, adapted from the antislop rulebook (40 rules, R-01 to R-40, at
https://github.com/miqdadbadjuber/anti-slop). Antislop was written
for UI; these are the rules that transfer to bot code. They are not
a badge. Each skill enforces them in its own Quality bar section.

## Hard rules (never break)

- **No em dash.** Never use an em dash in any message, embed, or
  reply the bot sends, or in any text the agent writes for the user.
  Use a period or a comma.
- **No invented numbers.** A balance, a member count, a latency, a
  test count, or a coverage percentage shown to anyone must come
  from the database, the library, or the tool that printed it.
  Never quote a statistic without a real source.
- **No fake content.** No placeholder text presented as real, no
  fake testimonials, no fake users. A missing value is shown as
  missing, or the feature is not shipped.
- **Every command answers.** A command that fails silently looks
  like a dead bot. Errors get a short user-facing message; the
  traceback goes to the log, never to chat.
- **No dead controls.** A command, a button, or a setting that does
  nothing is removed, not shipped.
- **No token in code, logs, or examples.** Tokens come from the
  environment only. A leaked token is reset immediately (see the
  runbook in build-discord-bot and deploy-and-monitor).

## Verify before claiming done

A bare "PASS" or "done" is void. Verification means running the
thing and reporting what was observed, step by step:

1. Run the test suite and quote its output.
2. Run the bot and invoke each command in a test guild, once.
3. Trigger one error path in Discord and confirm the user sees
   the error message.
4. Restart the bot and confirm data survives.

"Tests pass" is a statement about the suite, not about the bot.
A green suite plus a bot that never answers in Discord is a
failure, and the report must say so.

## Tests must be able to fail

- Expected values come from the spec or a worked example, never by
  recomputing the value the way the code does.
- Assert exact values, not truthiness. `assert balance == 60`,
  not `assert balance`.
- Mock the boundary (Discord, the database, the clock), never the
  code under test.
- Write the failing test before the fix, and watch it go red.
- Before trusting a suite, break something on purpose and confirm
  a test goes red. A suite that stays green is decoration.

## Every decision has a reason

If a command, a cog, a setting, or a test has no one-line reason to
exist, remove it. A bot with ten commands that all work beats a bot
with forty that half work. A technique is allowed when its purpose
is written down; technique without a purpose is slop.

## Keep skills lean

- A `SKILL.md` body stays under 500 lines. Long examples live in
  `references/` or `scripts/` inside the skill folder, not in the
  body.
- Descriptions are short, specific, and carry the user's own words
  ("my command does not show up") plus one "Do NOT use for"
  boundary, so the agent loads the right skill.
- Only the six spec frontmatter fields (`name`, `description`,
  `license`, `compatibility`, `metadata`, `allowed-tools`) are
  used. Agent-specific fields break portability.
- Each skill is self-contained: installing one skill carries its
  scripts with it. The copies in `skills/<name>/scripts/` are
  byte-identical to `scripts/` at the repo root, and a test checks
  that.

## How this guide is enforced

- `tests/test_newr.py` checks every skill's frontmatter: name
  equals the folder name, description is 1-1024 characters, only
  spec fields are present, and the script copies match the root.
- `scripts/test_scripts.py` runs the smoke tests for the scripts.
- The starter bot has its own passing suite
  (`templates/starter-bot/tests/`).
