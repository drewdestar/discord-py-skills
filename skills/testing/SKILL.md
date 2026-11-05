---
name: testing
description: "Test a discord.py bot: unit tests for pure logic, mocked interactions for commands, and async tests with pytest-asyncio. Use when adding tests or when a bot change needs proof it works."
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

## Checklist

- [ ] Pure logic has plain pytest tests with independent expected values
- [ ] Database tests use a fresh temp database per test
- [ ] Commands are tested through the callback with a mocked interaction
- [ ] Assertions check what the user sees, not internal calls
- [ ] No test touches the network or a real token
- [ ] `pytest -q` passes locally and in CI
