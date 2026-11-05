# Starter Bot

A minimal working discord.py bot: two slash commands (`/ping`, `/balance`)
backed by the small SQLite economy in `db.py`. It is the runnable example
for the skills in the parent repo.

## Run

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # then put your real bot token in .env
python bot.py
```

Set `TEST_GUILD_ID` in `.env` to sync commands instantly to one guild
while developing. Without it, commands sync globally (up to 1 hour to
appear everywhere).

## Test

```bash
pip install pytest pytest-asyncio
python -m pytest -q
```

## Files

- `bot.py`: entry point, intents, cog loading, command sync
- `config.py`: reads `DISCORD_TOKEN`, `TEST_GUILD_ID`, `DATABASE_PATH`
- `db.py`: SQLite economy (WAL, atomic transfers, idempotency keys)
- `cogs/general.py`: `/ping` and `/balance`
- `tests/`: pytest suite for the database layer and the commands
