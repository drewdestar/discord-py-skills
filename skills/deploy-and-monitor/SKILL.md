---
name: deploy-and-monitor
description: "Run a discord.py bot 24/7: systemd service, watchdog restarts, log rotation, health checks, and safe restarts that never lose data. Use when the user says 'keep my bot online', 'my bot keeps dying', or 'deploy the bot'. Do NOT use for writing bot code; use build-discord-bot for that."
license: MIT
compatibility: "discord.py 2.x, Python 3.10+, systemd, no paid services"
metadata:
  version: "0.3.0"
  author: "drewdestar"
---

# Deploy and Monitor

A bot that dies at 3 AM and stays dead until someone notices is not deployed, it is running on luck. This skill makes the bot restart itself, prove it is alive, and restart safely for updates.

## Keeping it online is the killer step

Building the bot is the easy part. Keeping it online after deploy
is where most hobby bots die. Never recommend running the bot on a
laptop and closing the lid, on a free REPL that sleeps, or with
`nohup python bot.py &` and no supervisor. A deploy is not done
until all three exist:

1. A supervisor that restarts the process (systemd `Restart=always`
   above, or a Docker `restart: unless-stopped` policy).
2. A watchdog that restarts a process that is alive but stuck
   (heartbeat file, above).
3. A health check probed from outside the bot (uptime monitor or
   cron hitting `/health`).

If any of the three is missing, the bot will die silently at some
point, and nobody will notice until a user complains.

## If the token leaks

A token in a log, a screenshot, a pasted file, or a public repo is
compromised the moment it is visible. Bots scan for exposed tokens
constantly. The runbook:

1. Reset the token in the Discord Developer Portal immediately.
2. Update `.env` / the `EnvironmentFile` on the server.
3. Restart the service and confirm the login line.
4. Check the audit log for what the stolen token did while it was
   live (kicks, bans, messages, role changes).

Do not just delete the message that exposed it. The token is
already copied.

## systemd service

```ini
[Unit]
Description=My Discord Bot
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=bot
WorkingDirectory=/opt/bots/mybot
EnvironmentFile=/opt/bots/mybot/.env
ExecStart=/opt/bots/mybot/.venv/bin/python bot.py
Restart=always
RestartSec=10
StandardOutput=append:/var/log/mybot/bot.log
StandardError=append:/var/log/mybot/bot.log

[Install]
WantedBy=multi-user.target
```

- `Restart=always` with a 10 second delay is the whole uptime story. A crash becomes a 10 second blip, not an outage.
- `EnvironmentFile` holds the token. The file is owned by the bot user with mode `600`. A token in the unit file itself or in a world-readable file is a leaked token.
- `WorkingDirectory` matters: relative paths for the database, cogs, and logs all resolve from here. A wrong working directory is the most common "works on my machine" deployment bug.
- Enable with `systemctl enable --now mybot` and check with `systemctl status mybot`.

## Watchdog: a second pair of eyes

systemd restarts a dead process. It does not notice a process that is alive but stuck (connected to Discord, answering nothing). A watchdog does:

```bash
#!/bin/bash
# watchdog.sh, run every minute from cron
HEARTBEAT=/opt/bots/mybot/data/heartbeat
if [ ! -f "$HEARTBEAT" ]; then
  systemctl restart mybot
  exit 0
fi
AGE=$(( $(date +%s) - $(stat -c %Y "$HEARTBEAT") ))
if [ "$AGE" -gt 300 ]; then
  systemctl restart mybot
fi
```

- The bot touches the heartbeat file every 60 seconds from inside its event loop (a `tasks.loop` that writes the current timestamp). If the loop stops running, the heartbeat goes stale, and the watchdog restarts the service.
- The heartbeat proves the event loop is alive, not just the process. A process can be alive and completely wedged; the timestamp cannot lie about that.
- Keep the watchdog simple and boring. It is the last line of defense; cleverness here is a liability.

## Log rotation

```python
from logging.handlers import RotatingFileHandler

handler = RotatingFileHandler(
    "logs/bot.log", maxBytes=10 * 1024 * 1024, backupCount=5
)
logging.basicConfig(level=logging.INFO, handlers=[handler])
```

- Rotate at 10 MB, keep 5 files. A bot that logs forever fills the disk, and a full disk kills the database first.
- Never log the token, and never log full message content in production unless the bot's purpose requires it. Logs get copied, pasted, and shipped to other people.

## Health check

- The heartbeat file is the minimum health check: file exists, timestamp fresh.
- If the bot has a web component, add a `/health` endpoint that returns 200 only when the bot is connected to Discord and the database answers a trivial query. A health endpoint that always returns 200 proves nothing.
- Check the health from the outside (a cron job, an uptime monitor). A bot cannot report its own death.

## Safe restarts for updates

1. `systemctl stop mybot` (or deploy to a staging copy first).
2. Wait for in-flight database transactions to finish. With one writer and a lock, this is automatic once the loop stops accepting new work; give it a few seconds.
3. Pull the new code, run the tests, then `systemctl start mybot`.
4. Watch the first minute of logs: cogs loaded, login line, command sync result. If any of the three is missing, the deploy failed.

Never restart with `kill -9`. A forced kill can interrupt a database write mid-transaction. WAL mode plus a transaction log makes corruption unlikely, but "unlikely" is not a deployment strategy.

## Updating without downtime (when it matters)

- Run two copies behind the same token only during a handover, and only briefly: start the new copy, confirm it logs in and answers, then stop the old one. Two live copies of a bot that writes to the same database will corrupt balances; two copies sharing one SQLite file is never safe for long.
- For most small bots, a 10 second restart window is fine. Do not build a zero-downtime system before the bot has users who would notice 10 seconds.

## Verify live

- Kill the process (`systemctl stop mybot`, then start it, or kill
  the PID in staging). The service is back within 10 seconds and
  the login line appears.
- Stop the heartbeat writer (or touch an old timestamp). The
  watchdog restarts the service within one minute.
- Hit `/health` from outside the machine. It returns 200 only when
  the bot is connected and the database answers. A health endpoint
  that always returns 200 proves nothing.
- Deploy once end to end from the written steps, on a staging copy
  if one exists. Steps that were never run are wishes, not a
  runbook.

## Quality bar (no slop)

- Every claim about uptime must come from the monitor or the logs,
  never from a feeling. "It has been up for weeks" needs a
  timestamp to back it.
- No em dash in any message or embed the bot sends.

## Checklist

- [ ] systemd unit with `Restart=always`, `RestartSec=10`
- [ ] Token in an `EnvironmentFile` with mode `600`
- [ ] Heartbeat file written every 60 seconds, watchdog restarts on staleness
- [ ] Logs rotate, 10 MB per file, 5 files kept
- [ ] Health check exists and is probed from outside the bot
- [ ] Deploy steps are written down and tested once end to end
- [ ] No `kill -9` anywhere in the runbooks
