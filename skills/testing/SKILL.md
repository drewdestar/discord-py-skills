---
name: testing
description: "Test a discord.py bot: unit tests for pure logic, mocked interactions for commands, and async tests with pytest-asyncio. Use when the user says 'write tests for the bot', 'the test passes but the bot is broken', or before changing anything that touches balances or permissions. Do NOT use for manual live checks alone; live verification is separate from the test suite."
license: MIT
compatibility: "discord.py 2.x, Python 3.10+, no paid services"
metadata:
  version: "0.4.0"
  author: "drewdestar"
---

# Testing Discord Bots

Tests for a bot verify behavior through public interfaces, not by hitting the real Discord API. A test suite that needs a live bot token is a test suite that never runs in CI.

## What to test, and where

| Layer | What it catches | How |
|---|---|---|
| Pure logic | Economy math, cooldown rules, parsing, formatting | Plain pytest functions, no Discord objects |
| Database | Atomic transfers, idempotency, migrations | aiosqlite against a temporary file or `:memory:` |
| Commands | The command answers, defers, or errors correctly | Call the command callback with a mocked interaction |
| Wiring | Cogs load, commands register, config validates | Import the cog module, load the extension in a test bot |

Test only at these seams. Do not mock the internals of a function to test that function; if the test needs to reach inside, the seam is wrong.

## Test setup

```toml
# pyproject.toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

For a plain `pytest.ini` the same settings use INI syntax instead
(`[pytest]` header, `asyncio_mode = auto` with no quotes). Do not
paste the TOML block into a `.ini` file: pytest will ignore it and
async tests will fail as unsupported.

```txt
# requirements-dev.txt
pytest
pytest-asyncio
discord.py
aiosqlite
```

- `asyncio_mode = "auto"` makes every `async def test_` function run without a decorator. One less thing to forget.
- Tests import the bot package from the project root. A `tests/conftest.py` that inserts the project root into `sys.path` keeps imports working from any directory.

## Pure logic first

```python
def test_transfer_rejects_zero_amount():
    with pytest.raises(ValueError):
        validate_transfer_amount(0)
```

- Pure functions (validation, formatting, cooldown math) are the cheapest tests in the codebase and the most valuable: they never need a mock and they never flake.
- Expected values come from the spec or a worked example, never by recomputing the value the way the code does. A test that asserts `add(a, b) == a + b` passes by construction and can never catch a bug.

## Database tests

```python
async def test_transfer_is_atomic(tmp_path):
    db = await connect(str(tmp_path / "test.db"))
    await init_db(db)
    await credit_once(db, asyncio.Lock(), 1, 100, "reward", "seed:1")
    await transfer(db, asyncio.Lock(), 1, 2, 40)
    assert await get_balance(db, 1) == 60
    assert await get_balance(db, 2) == 40
    with pytest.raises(ValueError, match="insufficient funds"):
        await transfer(db, asyncio.Lock(), 1, 2, 1000)
    assert await get_balance(db, 1) == 60  # failed transfer changed nothing
    await db.close()
```

- Each test gets a fresh temporary database (`tmp_path`). Tests that share one database file order-depend on each other and fail in confusing ways.
- The last two assertions are the point of the test: a failed transfer must leave both balances untouched. A test that only checks the happy path does not test atomicity.

## Mocking an interaction

```python
from unittest.mock import AsyncMock, MagicMock

def make_interaction(user_id: int = 1) -> MagicMock:
    interaction = MagicMock(spec=discord.Interaction)
    interaction.user = MagicMock()
    interaction.user.id = user_id
    interaction.response = AsyncMock()
    interaction.followup = AsyncMock()
    return interaction

async def test_ping_answers():
    cog = General(bot=MagicMock())
    interaction = make_interaction()
    await cog.ping.callback(cog, interaction)
    interaction.response.send_message.assert_awaited_once()
    text = interaction.response.send_message.await_args.args[0]
    assert text.startswith("Pong!")
```

- Call the command callback directly: `cog.ping.callback(cog, interaction)`. This exercises the real command code with a fake interaction, no network involved.
- Assert on what the user would see (the message text), not on internal calls. If the test asserts the bot called an internal helper, it breaks on every refactor.
- `AsyncMock` for `response` and `followup`: `send_message` and `defer` are coroutines, and a plain `MagicMock` for them returns a non-awaitable that fails with a confusing error.

## Tests must be able to fail

A test that cannot fail proves nothing. These are the ways tests
written by an AI usually lie:

- **Asserting what the code does, not what it should do.** Expected
  values come from the spec or a worked example, never by
  recomputing the value the way the code does. A test that asserts
  `add(a, b) == a + b` passes by construction and can never catch
  a bug.
- **Asserting truthiness instead of values.** `assert result`
  passes for any non-empty value. Assert the exact value:
  `assert balance == 60`.
- **Mocking the unit under test.** If the test mocks the function
  it is testing, it tests the mock. Mock the boundary (Discord,
  the database, the clock), never the code under test.
- **Only testing the happy path.** Every command needs an error-path
  test: `MissingPermissions`, `Forbidden`, an interaction timeout,
  invalid input. A bot crashes on the paths nobody tested.
- **Writing tests after the fix.** Write the failing test first,
  watch it fail, then fix the code. A test written after the fix
  often asserts the bug as correct behavior.

Before trusting a suite, break something on purpose: change one
expected value and confirm the test goes red. If it stays green,
the test is decoration.

## What not to test

- Do not call the real Discord API in tests. No live token, no test server, no network. A test that needs the network is flaky by definition.
- Do not test discord.py itself. If `app_commands.command` registers a command, that is the library's job to verify.
- Do not snapshot entire embeds. Assert the fields that matter (title, one value), not a byte-for-byte dump that breaks on every wording change.

## Red, green, refactor

1. Write one failing test for one behavior.
2. Write the smallest code that makes it pass.
3. Run the full suite. Everything green before the next test.

One test, one behavior, one cycle. Writing ten tests first and then the implementation tests imagined behavior, and the tests go insensitive to real changes.

## CI

```yaml
# .github/workflows/test.yml
name: tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install -r requirements.txt -r requirements-dev.txt
      - run: python -m pytest -q
```

- CI runs on every push and every pull request. A test suite that only runs on the developer's machine is a suggestion, not a gate.

## Verify live

A green suite is not proof the bot works. Tests use mocks; Discord
does not. After the suite passes:

1. Run the bot against the test guild.
2. Invoke every command the suite covers, once, in Discord.
3. Trigger one error path in Discord (for example, a command the
   user has no permission for). It must answer with the error
   message, not silence.
4. Restart the bot. Balances and data survive the restart.

Report the observed reply for each command. "Tests pass" is a
statement about the suite, not about the bot.

## Quality bar (no slop)

- **Evidence over claims.** Never report "all tests pass" without
  running them. Quote the actual output (`pytest -q`, the count,
  the failures). A number you did not measure is invented.
- **No em dash** in any message, embed, or reply the bot sends.
- **No fabricated coverage.** Do not claim a percentage of coverage
  or a number of cases unless the tool printed it.
- **Every check has a reason.** A test exists because a real failure
  mode exists. If you cannot name the failure in one line, delete
  the test.

## Checklist

- [ ] Pure logic has plain pytest tests with independent expected values
- [ ] Database tests use a fresh temp database per test
- [ ] Commands are tested through the callback with a mocked interaction
- [ ] Assertions check what the user sees, not internal calls
- [ ] No test touches the network or a real token
- [ ] `pytest -q` passes locally and in CI
