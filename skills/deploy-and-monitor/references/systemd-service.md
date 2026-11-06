## systemd service

```ini
[Unit]
Description=My Discord Bot
After=network-online.target
Wants=network-online.target
StartLimitIntervalSec=300
StartLimitBurst=3

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

- `StartLimitIntervalSec` + `StartLimitBurst` stop a crash loop from burning Discord's 1,000 IDENTIFY-per-day budget (a 10-second restart loop would exhaust it in under 3 hours, and exceeding it resets the bot token). Three failed starts in 5 minutes means the unit stays down until you fix the cause.
- **Prerequisites — the unit fails without all four, and systemd's error will not name them:** (1) the `bot` user exists (`useradd -r -m bot`); (2) `/opt/bots/mybot` exists and is owned by `bot`; (3) `/var/log/mybot` exists and is writable by `bot`; (4) `/opt/bots/mybot/.venv/bin/python` exists and `/opt/bots/mybot/.env` exists. Create them before enabling the unit.

- `Restart=always` with a 10 second delay is the whole uptime story. A crash becomes a 10 second blip, not an outage.
- `EnvironmentFile` holds the token. The file is owned by the bot user with mode `600`. A token in the unit file itself or in a world-readable file is a leaked token.
- `WorkingDirectory` matters: relative paths for the database, cogs, and logs all resolve from here. A wrong working directory is the most common "works on my machine" deployment bug.
- Enable with `systemctl enable --now mybot` and check with `systemctl status mybot`.
