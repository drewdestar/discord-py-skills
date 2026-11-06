## The transfer: which upstream rules apply to bots

Not all 40 rules transfer. The web-UI rules do not: gradients (R-01),
background grids (R-07), glassmorphism (R-10), shadows (R-12), glow (R-13),
theme toggles (R-34), hero images and Core Web Vitals (R-40), and the
HTML-document half of R-39 (lang, title, landmarks, zoom). For a web
dashboard, those live in the design-with-hallmark skill. What transfers,
in Discord form:

| Upstream | Discord form | Where it bites |
|---|---|---|
| R-02 no em dash | No em dash in any message, embed, or reply the bot sends. Use a period or a comma. | Bot replies, embeds, help text |
| R-17, R-36, R-38 no invented numbers or claims | A balance, member count, latency, uptime, or "X users" shown to anyone must come from the database, the library, or a measured value. No number without a source; empty is better than deceptive. | Economy replies, stats commands, status messages |
| R-18 no fake testimonials | No fake users, fake reviews, fake "top members", or invented social proof. If there is no real data, there is no leaderboard section. | Leaderboards, testimonials, social proof |
| R-23 ask before creating assets | Before generating a logo, avatar, banner, or profile image without explicit instructions, ask. If asking is impossible, use a clear placeholder (`[LOGO]`, initials avatar) and never present it as final. | Bot avatar, banners, welcome images |
| R-24 no dead navigation | Every link and nav item in an embed must go somewhere real. A link to a section or page that does not exist is removed, not shipped. | Embeds, help text |
| R-26 every control works | Every button, select, and command must do something real or be removed. A command that fails silently looks like a dead bot. Errors get a short user-facing message; the traceback goes to the log, never to chat. | All commands, views |
| R-27 three states | Every view that shows data needs an empty state, a loading state, and an error state. A list command with no data says "nothing here yet", not nothing. | List, shop, inventory, profile commands |
| R-28 no generic FAQ | A help command answers the questions this bot's users actually ask. Template FAQ entries ("Is my data secure?") with no relevance are cut. | /help, FAQ commands |
| R-31 every decision has a reason | Every command, cog, button, and setting gets a one-line reason or it is removed. A bot with ten commands that all work beats a bot with forty that half work. | Bot design |
| R-32, R-39 keyboard + semantics | Discord buttons and selects must be usable by keyboard where the client allows, and every control needs a clear label and a stable `custom_id`. An icon-only button with no label is unfinished. (R-39's HTML-document requirements, lang/title/landmarks, do not transfer; its accessible-name requirement does.) | Views, components |
| R-35 verify before claiming done | Run the bot, invoke each command in a test guild, trigger one error path, restart and confirm data survives. Report what you observed, step by step. A bare "done" is void. | Every delivery |
| R-15, R-16 specific copy | No generic CTAs ("Get Started", "Learn More", "Try Now", "Explore", "Discover") and no marketing buzzwords ("AI Powered", "Next Generation", "Revolutionary", "Seamless", "Cutting Edge", "Intelligent", "Ultimate", "Powerful", "Effortless"). Say the specific action and the specific benefit. | Replies, embeds, help text |
| R-03 mobile | Embeds are read on phones. No wall of text, no table that overflows a phone screen, tap targets a thumb can hit. | Embeds, paginators |
