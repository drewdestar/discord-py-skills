---
name: newr-language
description: "Write a small Discord bot in the .newr language and compile it with `newr build` into runnable discord.py: one bot block, slash commands with replies, and ready/member-join events. Use when the user says 'write a bot in .newr', 'newr build', 'make me a small bot', or hands you a .newr file. Do NOT use for bots that need currency, command arguments, buttons, modals, scheduled tasks, or multiple languages; use economy-database, slash-commands, or i18n for those."
license: MIT
compatibility: "discord.py 2.x, Python 3.10+, no paid services"
metadata:
  version: "0.5.0"
  author: "drewdestar"
---

# The newr Language

A `.newr` file describes a bot. It is not a general-purpose
language: it says the bot's name, its slash commands, and two
simple events, and `newr build` compiles it into a runnable
discord.py bot. If the bot needs logic the language cannot say,
write Python with the skills in this pack instead. The language
is for the common small bot, not for everything.

## When to use it, and when not to

Use `.newr` when the bot is small: a few commands that answer
with fixed replies, an optional welcome message, an optional
ready log line. It is the fastest path from "I want a bot" to
a bot that answers in Discord.

Do not use `.newr` when the bot needs any of these; use the
skill named instead:

- Currency, shop, balances: economy-database
- Command arguments, buttons, modals: slash-commands
- More than one reply language: i18n
- Scheduled tasks, background work: write Python with
  build-discord-bot

If you are unsure whether the bot fits, it does not fit. Write
Python. A `.newr` file that strains against its limits is worse
than a small Python bot.

## Build commands

```bash
newr build hello.newr            # writes hello.py next to it
newr build hello.newr -o bot.py  # writes bot.py instead
newr build --check hello.newr    # parse and compile, write nothing
python hello.py                  # run it (needs DISCORD_TOKEN set)
```

Run `--check` before anything else. It catches every syntax
error without writing a file. The generated file starts with a
comment naming the `.newr` source it came from. Edit the `.newr`
file and rebuild; never edit the generated file by hand.

## A complete example

`examples/hello.newr` in this repo is the reference. It builds
clean with `newr build --check` and its output is golden-tested:

```newr
# hello.newr — a bot written in the newr language.

bot "HelloBot":
  description: "A friendly bot that answers in plain words"

command ping:
  description: "Answer with pong"
  reply: "Pong! Hello {user}"

command greet:
  description: "Greet someone in this server"
  reply: "Hello {user}, welcome to {guild}!"
  ephemeral: true

event ready:
  log: "{bot} is online"

event member_join:
  reply: "Welcome to {guild}, {user}!"
```

## Syntax

- A file is lines. Blank lines and `#` comments are ignored.
- Three top-level blocks: `bot`, `command`, `event`. A block
  opens with a line ending in `:` and its body is indented two
  spaces.
- Exactly one `bot` block, and it comes first. Its name is a
  quoted string, 1-32 characters.
- `command <name>:` where `<name>` follows Discord's slash command name rule: 1-32 characters, lowercase letters, digits, `_` and `-`; any language's letters count, including Thai and Devanagari (the compiler checks this with the same character table discord.py uses). Names need not start with a letter (`9lives` is valid). Command names must be unique, and two names must not sanitize to the same function name (`foo-bar` and `foo_bar` collide).
- `event <kind>:` where `<kind>` is `ready` or `member_join`.
  Only those two events exist in this version.
- Inside a block, one `key: value` per line. Values are
  double-quoted strings on one line; `\"`, `\\`, and `\n` are
  escapes. Tab indentation is not allowed; use two spaces. (A tab
  inside a quoted string value is allowed, but keep values
  tab-free: Discord shows them as wide gaps.)
- Unknown blocks, unknown keys, and unknown event kinds are
  errors, reported with the file and line number. `newr` never
  silently ignores a line it does not understand.

### Keys

| Block | Key | Required | What it means |
|---|---|---|---|
| `bot` | `description` | no | Shown in the generated file header |
| `command` | `description` | no | The slash command description (defaults to the command name) |
| `command` | `reply` | yes | What the bot answers when the command runs |
| `command` | `ephemeral` | no | `true` or `false`; when true only the caller sees the reply (default `false`) |
| `event ready` | `log` | yes | One line written to the log when the bot connects |
| `event member_join` | `reply` | yes | Sent to the guild's system channel when a member joins (skipped silently when the guild has no system channel) |

### Placeholders

`reply` and `log` strings can contain placeholders, which the
generated bot fills in when it runs:

| Placeholder | Where it works | What it becomes |
|---|---|---|
| `{user}` | command replies, member-join replies | the user, mentioned |
| `{guild}` | command replies, member-join replies | the server name |
| `{channel}` | command replies | the channel, mentioned |
| `{bot}` | ready log | the bot's own name |

Any other `{...}` is an error naming the placeholder. A literal
brace must not appear in a string; the compiler rejects it rather
than guessing what was meant.

## What the compiler generates

`newr build` writes one Python file that follows the same rules
as the starter bot in `templates/starter-bot/`:

- `commands.Bot` with slash commands registered on the tree and
  synced in `setup_hook`.
- Intents are derived from the source: default intents always,
  plus the members intent only when a `member_join` event exists.
- The token comes from the `DISCORD_TOKEN` environment variable.
  No token is ever written into the generated file.
- Command errors are answered with a short message instead of
  failing silently.

The generated bot needs only `discord.py` installed
(`pip install discord.py`). The compiler itself needs nothing
beyond the Python standard library, and it lives inside the
single `newr` file.

## Common mistakes

1. **Editing the generated `.py` file.** The next build
   overwrites it. Change the `.newr` source and rebuild.
2. **A placeholder in the wrong place.** `{channel}` in a
   member-join reply and `{bot}` in a command reply are both
   errors. The table above is the whole list; there are no
   others.
3. **Forgetting `reply`.** Every command needs one and every
   event needs its required key. A block without it fails
   `--check` with the file and line number.
4. **Tabs for indentation.** Tabs are rejected anywhere in the
   file. Two spaces, always.
5. **Growing past the language.** The moment a command needs
   an argument, a button, or a database lookup, stop adding
   `.newr` and write Python with slash-commands or
   economy-database. Do not invent syntax the compiler does
   not have; it will error, and working around the error by
   hand-editing the generated file breaks the rebuild cycle.

## Verify live

1. `newr build --check bot.newr` passes with no errors.
2. `newr build bot.newr` writes the `.py` file next to it.
3. Run it with `DISCORD_TOKEN` set. The ready log line
   appears.
4. Run each command once in Discord. It answers within
   3 seconds with exactly the reply in the source.
5. If a `member_join` event exists, have a user join the
   test guild. The welcome reply appears in the system
   channel.

Report what you observed for each step. "It should work" is not
an observation.

## Quality bar (no slop)

- Every reply the bot sends comes from the `.newr` source.
  No invented text, no placeholder presented as real content.
- No em dash in any message or reply the bot sends.
- Every command answers. A command that fails silently looks
  like a dead bot.

## Checklist

- [ ] `newr build --check` passes on the `.newr` file
- [ ] Exactly one `bot` block, first, name 1-32 characters
- [ ] Every command has a `reply`; every event has its required key
- [ ] Placeholders only from the table above, in the places listed
- [ ] No tab indentation (two spaces only)
- [ ] Generated bot runs, logs in, and every command answers live
