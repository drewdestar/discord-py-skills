# Contributing

Contributions are welcome. Keep them small, tested, and honest.

## How to contribute

1. Fork the repo and create a branch from `main`.
2. Make one change per pull request: one skill fix, one script fix, or
   one template improvement.
3. Run the tests before opening the pull request:
   - `python -m pytest scripts/test_scripts.py -q`
   - `python -m pytest templates/starter-bot -q`
4. Describe what changed and why in the pull request. Link the issue
   if one exists.

## Rules for skills

- Every claim in a skill must be verifiable against the current
  discord.py documentation or a runnable example. If you cannot run
  it, do not write it as fact.
- Code examples must be complete enough to copy and run, or labeled
  as a fragment.
- No fake statistics, no invented benchmarks, no "best" claims.
- No em dashes in user-facing text. Use commas, colons, or
  parentheses instead.
- Frontmatter uses only the six Agent Skills spec fields (`name`,
  `description`, `license`, `compatibility`, `metadata`,
  `allowed-tools`). The `name` must equal the folder name and the
  description must stay under 1024 characters.
- Script copies in `skills/<name>/scripts/` must stay byte-identical
  to `scripts/` at the repo root; `tests/test_newr.py` checks this.

## Rules for code

- Python 3.11 or newer. Type hints on public functions.
- No blocking calls inside async code (`time.sleep`, `requests`,
  synchronous database drivers in commands).
- All SQL parameterized. Never build SQL with f-strings.
- No secrets in code, tests, or examples. Tokens in examples are
  always placeholders such as `your-bot-token-here`.

## Reporting problems

Open an issue with the discord.py version, the Python version, the
exact error (with traceback), and the smallest reproduction you can
write. A report without a reproduction is still welcome, but it takes
longer to fix.
