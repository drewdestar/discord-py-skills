# The newr language (`.newr` files)

`newr` has its own small language for defining a Discord bot. A
`.newr` file is not a general-purpose programming language: it
describes a bot (its name, its slash commands, and two simple
events), and `newr build` compiles it into a runnable discord.py
bot. If the bot needs logic the language cannot say, write Python
with the skills in this pack instead; the language is for the
common small bot, not for everything.

Build it with:

```bash
newr build hello.newr            # writes hello.py next to it
newr build hello.newr -o bot.py  # writes bot.py instead
newr build --check hello.newr    # parse and compile, write nothing
python hello.py                  # run it (needs DISCORD_TOKEN set)
```

## A complete example

```newr
# hello.newr — a bot written in the newr language.
# Build it with: newr build hello.newr

bot "HelloBot":
  description: "A friendly bot that answers in plain words"

command ping:
  description: "Answer with pong"
  reply: "Pong! Hello {user}"

command greet:
  description: "Greet someone in this server"
  reply: "Hello {user}, welcome to {guild}!"

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
- `command <name>:` where `<name>` is lowercase letters, digits,
  and underscores, starting with a letter (Discord slash command
  names have the same rule). Command names must be unique.
- `event <kind>:` where `<kind>` is `ready` or `member_join`.
  Only those two events exist in this version.
- Inside a block, one `key: value` per line. Values are
  double-quoted strings on one line; `\"`, `\\`, and `\n` are
  escapes. Tabs are not allowed anywhere.
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
- The generated file starts with a comment naming the `.newr`
  source it came from. Edit the `.newr` file and rebuild; do not
  edit the generated file by hand.

The generated bot needs only `discord.py` installed
(`pip install discord.py`). The compiler itself needs nothing
beyond the Python standard library, and it lives inside the
single `newr` file, so `curl | sh` installs and `npx github:`
keep working unchanged.

## What it does not do (yet)

- No economy: there is no `balance` or currency block. A bot
  that keeps money uses the `economy-database` skill and the
  starter bot's `db.py` instead.
- No i18n: replies are one language. A multi-language bot uses
  the `i18n` skill.
- No arguments, no buttons, no modals, no scheduled tasks. A
  command takes no input beyond being run; anything richer is
  Python with the `slash-commands` skill.

These are deliberate limits for the first version, not oversights.
A future version can add a block when it maps cleanly onto one of
the skills, the same way `member_join` maps onto intents here.
