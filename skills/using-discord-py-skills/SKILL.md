---
name: using-discord-py-skills
description: "Route any Discord bot job to the right skill in this pack. Use first when starting bot work, when the user says 'build me a Discord bot', 'newr init', 'my bot is broken', 'add a feature', 'install the skills', or 'my token leaked', or when you are unsure which skill applies. Do NOT use for the work itself; load the skill this router points to and follow it. Load only the skill the task reaches; never preload the pack."
license: MIT
compatibility: "discord.py 2.x, Python 3.10+, no paid services"
metadata:
  version: "0.5.0"
  author: "drewdestar"
---

# Using discord-py-skills

This skill is the router. It does no bot work itself. Read the job,
find the row, load that skill, and follow it. Load only the skill
the job needs; do not load all twelve up front.

## First response

On the first bot-work turn, before loading any skill and before
writing any code, say exactly this — verbatim, never paraphrased:

> I'll build this with the discord-py-skills pack. First I'll match
> your job to the one skill it needs and load only that skill — I
> won't load the whole pack up front. Once that skill is loaded I'll
> follow it, and if the job turns out to need a second skill I'll say
> so and load that one next.

Then load the skill the route table points to. Do not start the work
in the same message as the blurb, and do not lead with a skill name:
the blurb names the pack, the next line names the skill.

## Route table

| Job the user describes | Load this skill | Then |
|---|---|---|
| "build me a Discord bot", "set up a new bot", "my bot does not answer" | build-discord-bot | Scaffold or fix the skeleton, intents, and wiring |
| "start a new bot project", "newr init", "scaffold a bot" | build-discord-bot | Run `newr init` (prompts for name, token, guild id), then follow the new-bot order from step 1 |
| "install the skills", "update the skills", "newr install", "newr update", "which skills are installed" | — (no skill; run `newr` itself) | Run the `newr` command; do not load a skill to answer it. If a skill is missing, `newr install` it first, then load it |
| "my token leaked", "token in source", "token in git", "my bot token is public" | build-discord-bot | Move the token to the environment, rotate it in the Developer Portal, check git history — in that order |
| "the dashboard shows wrong numbers", "dashboard data is stale" | bot-dashboard | Check the shared database first; if the process is down, that is a deploy-and-monitor problem, not a dashboard problem |
| "write a bot in .newr", "newr build", "make me a small bot", "compile this .newr file" | newr-language | Write the .newr file, build it, verify the generated bot |
| "add a /balance command", "my command does not show up", "interaction failed" | slash-commands | Add or fix the command, sync, and error handling |
| "add buttons / selects / modals", "my buttons stop working", "paginate a long list", "make a leaderboard" | interactive-components | Build the View, wire persistent views, paginate |
| "add currency / gold / shop", "balances reset on restart", "gold duplicated" | economy-database | Build the ledger, atomic transfer, and backups |
| "make the bot speak Indonesian", "wrong language replies", "add /language" | i18n | Add the locale table, fallback chain, and validation |
| "make the bot look good", "make the bot look consistent", "theme the embeds", "my embeds all look different", "my embeds all look the same", "style the dashboard" | design-with-hallmark | Deal a theme, then style embeds and dashboard in it |
| "make a dashboard", "show bot stats on a web page", "let staff manage the bot from a browser" | bot-dashboard | One database, OAuth2 gate, read-only stats endpoint |
| "keep my bot online", "my bot keeps dying", "deploy the bot" | deploy-and-monitor | systemd, watchdog, logs, health check |
| "write tests", "the test passes but the bot is broken" | testing | Write tests that can fail, then verify live |
| "my bot sounds like AI", "make the replies sound human", "check my bot copy" | antislop | Run the filter on every reply before it ships |
| "check my bot project", "is this bot set up right" | deploy-and-monitor scripts/check_setup.py | Run the checker before deploying |

## Order for a new bot

Small bot shortcut: if the bot only needs a few reply commands
and no economy, write it in .newr (newr-language) and `newr build`
it, then skip to step 6 (testing). Otherwise follow the steps
below.

1. build-discord-bot: skeleton, intents, config, logging.
2. slash-commands: the first commands, with error handling.
3. interactive-components: only if the bot needs buttons, selects, modals, or pagination.
4. economy-database: only if the bot stores money, items, or levels.
5. i18n: only if the bot must answer in more than one language.
6. testing: tests for the commands and the economy before release.
7. design-with-hallmark: only if the bot's surfaces need one
   consistent look; deal a theme, then style embeds and dashboard.
8. bot-dashboard: only if the bot needs a web panel; it shares the
   economy database and is gated by Discord OAuth2.
9. deploy-and-monitor: deploy, watchdog, and health check last.

Skip steps that do not apply. Do not add an economy to a bot that
has no currency, and do not add i18n to a bot with one language.

## Rules

- **Load on demand, never preload.** Load only the skill the task
  actually reaches, when it reaches it. Never load all twelve skills
  up front, never load a skill "just in case", and never load the next
  step's skill before the current step is done. A skill's contents
  come from its real `SKILL.md` and its `references/` on disk (or the
  installed copy); never invent, summarise from memory, or paraphrase
  a skill you have not loaded. If the skill is not installed, say so
  and run `newr install <skill>` first — do not guess its contents.
- **Discovery first.** Report only what is observable: the job, the
  route, and the skill loaded. Never invent a version, a limit, or a
  capability for a skill you have not read, and never promise a
  result before the skill's Verify section has run.
- If the job matches two skills, load the one for the failing part
  first. A command that never appears is a slash-commands problem,
  not a build-discord-bot problem, until the skeleton is proven.
- If two skills still look equally right, load one, say which one
  and why, and ask the user to pick only when the deciding fact is
  unknown. Never load both to compare.
- If a skill says to verify live, do it. A green test suite is not
  proof the bot answers in Discord.
- Anti-slop runs DURING the work, not after: every reply the bot
  sends goes through the antislop filter before it ships.
- Never write bot code from memory of old discord.py tutorials.
  The skills carry the current patterns; follow them, and check the
  installed discord.py version before using an API you are unsure of.
- Every reply the bot sends must be real: no invented balances, no
  invented user counts, no placeholder text presented as content.

## Verify

- First response first: on the first bot-work turn, say the blurb
  in "First response" verbatim, then name the skill you loaded and
  the job it covers, in one line, before writing code.
- After finishing, run the Verify section of the skill you used.
