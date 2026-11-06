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
- `command <name>:` where `<name>` follows Discord's slash
  command rule: 1-32 characters, lowercase letters, digits, `_`
  and `-`, in any script — Japanese, Thai, Hindi, and Arabic
  names are all valid, and a name may start with a digit or a
  hyphen. If a letter has a lowercase form, use it (`Ping` is
  invalid). Command names must be unique, and two names that
  differ only by `-` vs `_` (`foo-bar` vs `foo_bar`) are
  rejected, because both would generate the same `cmd_foo_bar`
  function.
- `event <kind>:` where `<kind>` is `ready` or `member_join`.
  Only those two events exist in this version.
- Inside a block, one `key: value` per line. Values are
  double-quoted strings on one line; `\"`, `\\`, and `\n` are
  escapes. Tabs are not allowed anywhere.
- Unknown blocks, unknown keys, and unknown event kinds are
  errors, reported with the file and line number. When the typo
  is close to a real name the error suggests it (`did you mean
  'ephemeral'?`), and `newr build` prints the offending source
  line under the error. `newr` never silently ignores a line it
  does not understand.
- A key may appear only once in a block, and an event kind only
  once in a file. A second `reply:` or a second `event ready:`
  is an error, not a silent overwrite.
- Command descriptions are at most 100 characters and replies
  at most 2000 characters, because Discord rejects longer ones
  at sync/send time. Placeholders count at their longest
  possible expansion (`{user}` and `{channel}` as 22 characters,
  `{guild}` as 100), so a build that passes never fails at send
  time. Bots always get the 2000-character limit; Nitro's 4000
  does not apply to them.

### Any language, any line ending, any OS

- Replies, descriptions, and the bot name may be in any language:
  Indonesian, Japanese, Arabic, Thai, emoji — `.newr` is UTF-8
  text throughout and the generated bot is a normal Python 3
  file, so non-ASCII strings just work. Command names follow
  Discord's rule above, which already allows any script's
  letters (source: https://docs.discord.com/developers/interactions/application-commands).
- A `.newr` file saved with Windows CRLF line endings builds
  exactly like one with LF endings (verified by test).
- The `newr` CLI is stdlib-only Python and uses `pathlib`
  throughout, so `python newr build bot.newr` is expected to work
  on Windows and macOS the same way it works on Linux — but that
  has NOT been verified by running it there. What is known:
  there is no Windows launcher yet (no `.bat` / `.cmd` / `.ps1`;
  `install.sh` is POSIX shell), and the `npx` install currently
  excludes Windows (`"os"` in `package.json`). Until those land,
  Windows users run `newr` through Python directly. The CLI's
  own error messages are English-only; localizing them is future
  work, not part of this version.

### Keys

| Block | Key | Required | What it means |
|---|---|---|---|
| `bot` | `description` | no | Shown in the generated file header |
| `command` | `description` | no | The slash command description (defaults to the command name). Max 100 characters. |
| `command` | `reply` | yes | What the bot answers when the command runs. Max 2000 characters, counting placeholders at their longest expansion. |
| `command` | `ephemeral` | no | `true` or `false`; when true only the caller sees the reply (default `false`) |
| `event ready` | `log` | yes | One line written to the log when the bot connects |
| `event member_join` | `reply` | yes | Sent to the guild's system channel when a member joins (skipped silently when the guild has no system channel). Max 2000 characters, same counting. |

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
