## Embeds: the mapping

```python
import discord
from hallmark_theme import discord_embed

embed = discord.Embed.from_dict(discord_embed(
    "coral",
    title="Shop",
    description="Spend gold on things that do something.",
    fields=[
        ("Iron Sword", "1,200 gold, +5 attack", True),
        ("Healing Potion", "150 gold, restores 50 HP", True),
        ("Your gold", str(balance), False),  # real balance, from the ledger
    ],
    footer="Prices change when the shop restocks.",
))
await interaction.response.send_message(embed=embed)
```

`discord_embed()` builds the dict and raises `ValueError` listing
every Discord limit it breaks. Fix the copy; do not catch the
error and send anyway. `validate_embed()` checks a dict without
building one.

Discord's embed limits (official API docs,
`discord.com/developers/docs/resources/message#embed-limits`):

| Part | Limit |
|---|---|
| Title | 256 characters |
| Description | 4,096 characters |
| Fields per embed | 25 |
| Field name / value | 256 / 1,024 characters |
| Footer text | 2,048 characters |
| Author name | 256 characters |
| All embed text in one message | 6,000 characters |
| Embeds per message | 10 |

Rules for the copy:

- Title: what this embed is, in plain words. Description: one
  sentence, twelve words or fewer, saying what the user can do
  here. Fields: facts, each with its unit ("1,200 gold", not
  "1200"). Footer: the one thing that changes, or the credit for
  a photo. Nothing else.
- Inline fields sit side by side in threes. A field that must
  stand alone (a balance, a warning) is not inline.
- A thumbnail is the bot's or the user's avatar, or the item's
  picture. An image is a real picture of the thing, served over
  https, or an attachment the bot just uploaded. Never a
  hotlinked stock photo, never a drawn placeholder.
- A photo from Hallmark's library is a Wikimedia Commons URL,
  credited in the footer ("Photo: \<author\>, Wikimedia Commons").
  Footers carry no links, so the page link goes in the
  description when it matters. The helper does not ship the
  library; pick from it with Hallmark's own `theme.mjs photos`
  when Hallmark is installed, or use the bot's own art.
