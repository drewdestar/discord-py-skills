## Works in every language

The filter is not English-only. The structural rules above need no
translation at all: sentence-length variation, parataxis, the rule of
three, the hedging seesaw, passive constructions, and paragraph-shape
monotony are measured in syntax, so they carry over untouched into
every language (obi12341/anti-ai-slop-writing,
`references/other-languages.md`). Two more of its findings:

- **The translation test.** Take a banned English entry, render it
  literally into the target language, and ask where that word actually
  lives. If native speakers meet it mostly in press releases,
  consultancy decks, and SEO blog posts, it is banned in that language
  too. If the translation lands on an ordinary everyday word, it is
  fine: *nutzen* is not *leverage*, and *usar* is not *utilize*.
  Run this test before adding any new language to the checker.
- **Drop one register below formal.** Models reach for the most formal
  register a language offers; real people write a notch below that,
  and in most languages the gap is wider than in English. Also watch
  for translationese: a text that keeps English sentence rhythm, short
  declaratives in a row, English comma habits, or an em dash where the
  language would use a comma reads as machine-translated even when
  every word is native. Rebuild the sentence in the target language
  instead of carrying the English skeleton across.

Indonesian, the language this pack's users write in, has its own
attested patterns (konten-studio/jekardah-writer, `skills/no-ai-slop`):

| Pattern | Indonesian signal | Repair |
|---|---|---|
| Canned opening | "Di era..." ("Di era digital yang semakin berkembang pesat") | Start at the concrete claim, scene, or action. |
| Fake contrast | "bukan cuma X, tapi Y" where X/Y are vague or not opposed | State the real distinction or delete the frame. |
| Over-signposting | "penting untuk dicatat", "pada akhirnya" | Remove the label, make the point directly. |
| Inflated claim | "game-changing", "revolutionary", "unlock", "masa depan sudah di sini" | Use the supported outcome and calibrated certainty. |
| Generic CTA | "What do you think?", "Are you ready to level up?" | Ask one answerable question tied to the tension. |

For code-mixed Indonesian/English replies, check translations that
repeat the same idea, abrupt register shifts, and English inserted for
prestige rather than precision; do not purge established technical
terms. And do not perform slang: never sprinkle `literally`, `jujurly`,
`bestie`, `sih`, or local slang merely to appear human (jekardah).

Other languages: obi12341's `other-languages.md` carries verified banned
lists for German, Spanish, French, Italian, Portuguese, and Dutch
(including the German note that the Gedankenstrich is a spaced en dash
with the same limit as the English em dash, which the checker already
flags). The checker in this skill covers English and Indonesian; any
other language goes through the translation test first, and its list is
added only after that test, never by guessing a translation.
