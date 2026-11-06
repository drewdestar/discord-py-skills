## The deal

Deal three themes that fit the bot's job, then pick one. The helper
is `scripts/hallmark_theme.py` (stdlib only; run it from its own
directory, or import it).

```bash
python3 scripts/hallmark_theme.py deal --keywords "rpg economy shop"
python3 scripts/hallmark_theme.py deal --keywords "music bot" --seed 7
python3 scripts/hallmark_theme.py list --strong
python3 scripts/hallmark_theme.py theme coral
python3 scripts/hallmark_theme.py embed-color terminal
```

The deal draws only from the **23 discord-strong themes**: accent
chroma 0.10 or higher AND accent contrast 3.0 or higher against
Discord's dark chat background `#313338`. A theme whose stripe is
faint on the default dark client is never a good first pick,
however well its keywords match. The other 27 themes stay
available by name (`theme <slug>`), and all 50 work for dashboards.

Say the pick in one line before writing code: "Shop embeds use
Coral, dealt 1/3 for 'rpg economy shop'." Keep one theme per
feature, and one theme for the whole bot when the features share
an audience. If no theme fits, the default is Discord's own
blurple `#5865F2`, not a random pick.

Honest limit: Hallmark's keywords are web-category words
("saas", "billing", "dashboard", "bakery"), not bot words. A bot
job like "economy" matches nothing, and the deal falls back to
seeded variety inside the strong pool. The keywords are English
words: a job described in another language ("toko ekonomi")
matches nothing either, and the deal still deals three themes
with no keyword hits. Describe the job in English when a
keyword match matters. The deal is a starting hand, not a
verdict; read the three material lines and pick the one whose
voice fits the feature.
