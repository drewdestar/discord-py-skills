---
name: using-discord-py-skills
description: "Route any Discord bot job to the right skill in this pack. Use first when starting bot work, when the user says 'build me a Discord bot', 'my bot is broken', or 'add a feature', or when you are unsure which skill applies. Do NOT use for the work itself; load the skill this router points to and follow it."
license: MIT
compatibility: "discord.py 2.x, Python 3.10+, no paid services"
metadata:
  version: "0.4.0"
  author: "drewdestar"
---

# Using discord-py-skills

This skill is the router. It does no bot work itself. Read the job,
find the row, load that skill, and follow it. Load only the skill
the job needs; do not load all seven up front.

## Route table

| Job the user describes | Load this skill | Then |
|---|---|---|
| "build me a Discord bot", "set up a new bot", "my bot does not answer" | build-discord-bot | Scaffold or fix the skeleton, intents, and wiring |
| "add a /balance command", "my command does not show up", "interaction failed" | slash-commands | Add or fix the command, sync, and error handling |
| "add currency / gold / shop", "balances reset on restart", "gold duplicated" | economy-database | Build the ledger, atomic transfer, and backups |
| "make the bot speak Indonesian", "wrong language replies", "add /language" | i18n | Add the locale table, fallback chain, and validation |
| "keep my bot online", "my bot keeps dying", "deploy the bot" | deploy-and-monitor | systemd, watchdog, logs, health check |
| "write tests", "the test passes but the bot is broken" | testing | Write tests that can fail, then verify live |
| "check my bot project", "is this bot set up right" | deploy-and-monitor scripts/check_setup.py | Run the checker before deploying |

## Order for a new bot

1. build-discord-bot: skeleton, intents, config, logging.
2. slash-commands: the first commands, with error handling.
3. economy-database: only if the bot stores money, items, or levels.
4. i18n: only if the bot must answer in more than one language.
5. testing: tests for the commands and the economy before release.
6. deploy-and-monitor: deploy, watchdog, and health check last.

Skip steps that do not apply. Do not add an economy to a bot that
has no currency, and do not add i18n to a bot with one language.

## Rules

- If the job matches two skills, load the one for the failing part
  first. A command that never appears is a slash-commands problem,
  not a build-discord-bot problem, until the skeleton is proven.
- If a skill says to verify live, do it. A green test suite is not
  proof the bot answers in Discord.
- Never write bot code from memory of old discord.py tutorials.
  The skills carry the current patterns; follow them, and check the
  installed discord.py version before using an API you are unsure of.
- Every reply the bot sends must be real: no invented balances, no
  invented user counts, no placeholder text presented as content.

## Verify

- After routing, name the skill you loaded and the job it covers,
  in one line, before writing code.
- After finishing, run the Verify section of the skill you used.
