---
layout: home
hero:
  name: discord-py-skills
  text: Agent skills for building Discord bots with discord.py.
  tagline: Twelve skills, one router, one installer. The router reads the job, loads the one skill the job needs, and each skill teaches one job.
  actions:
    - theme: brand
      text: Install
      link: /install
    - theme: alt
      text: Browse the skills
      link: /skills/
features:
  - title: Router first
    details: using-discord-py-skills reads the job and loads only the skill the job needs — never the whole pack up front.
  - title: Verified, not claimed
    details: Every pattern was run against real discord.py 2.7.1. A green test suite is not proof the bot answers; live verification is.
  - title: One installer
    details: newr installs skills into 33 agents, scaffolds a bot with newr init, and speaks JSON for scripts and agents.
---

## Install

```bash
curl -fsSL https://raw.githubusercontent.com/drewdestar/discord-py-skills/main/install.sh | sh
newr init                          # scaffold a working bot
newr install all                   # all twelve skills
```

See the [install guide](/install) for the full walkthrough, the
`--agent` matrix, and machine-readable output.

## Skills

Twelve skills: scaffolding, slash commands, buttons and modals, a
SQLite economy that cannot create money, honest i18n, deploys that
restart themselves, tests that can fail, a web dashboard, antislop
copy, the .newr language, and Hallmark design for the bot's look.
[ Browse them all](/skills/).
