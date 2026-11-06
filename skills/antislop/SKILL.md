---
name: antislop
description: "Stop a discord.py bot sounding and looking AI-generated: no em dash, no invented numbers, no generic copy in replies, embeds, or code comments. Use when the user says 'my bot sounds like AI', 'make the replies sound human', 'check my bot copy', or before any reply ships. Do NOT use for visual theme or layout direction; use design-with-hallmark for web dashboards."
license: MIT
compatibility: "discord.py 2.x, Python 3.10+, no paid services"
metadata:
  version: "0.5.0"
  author: "drewdestar"
---

# Anti-slop for Discord bots

This skill is the anti-slop filter, distilled for Discord bot work. It is
adapted from upstream anti-slop v3.2.26 (miqdadbadjuber/anti-slop: 40 rules
R-01 to R-40, three tiers, Delivery Gate, ENERGY/RHYTHM/MOTION dials) plus a
wider survey of the anti-slop landscape (linters, multi-gate pipelines,
voice calibrators, and substance-first critics; key sources at the end).
Rule numbers below are upstream rule numbers, verified against the upstream
source.

Anti-slop is a **filter, not a style guide**. It removes what should not be
there. It never invents the bot's voice: the bot's voice comes from the user
and the server it serves. A filter with no voice behind it produces sterile
replies, and sterile is also slop (upstream R-37).

**Mode: always DURING in this pack.** The repo runs anti-slop while the work
happens, not as an after-the-fact audit. There is no session question. The
After/audit mode exists as a pass you can run over existing replies with the
Bot Reply Gate below; it changes nothing until the user approves specific
findings.

## The transfer: which upstream rules apply to bots

Which of upstream anti-slop's 40 rules transfer to Discord bots, and their Discord form. See `references/transfer.md`.

## Bot reply copy: the patterns that mark a reply as AI-written

The copywriting patterns that mark a reply as AI-written, from upstream antislop-copywriting. See `references/reply-copy.md`.

## Rhythm: how a reply reads (from the wider survey)

Word lists alone do not fix a reply. The structural rules below are the most
measurable AI signals in text (jalaalrd/anti-ai-slop-writing,
obi12341/anti-ai-slop-writing; they allow one em dash per 500 words, this
pack bans it in bot messages outright, R-02). This is upstream's RHYTHM dial
in Discord form: the dial is about pacing and variety, and pacing is the one
part of it that lives in text. ENERGY and MOTION are web-design dials (visual
energy, animation) and do not transfer to replies. If there is no direction
for the bot's voice at all, say so and write plain and short: never silently
fall back to a sterile default (R-37).

- **Vary sentence length.** No three consecutive sentences of the same
  length. Mix short and long; this is the single most measurable signal.
- **No parataxis chains.** Short sentence. Then another. Then another. It
  reads like a poem and signals AI authorship. Connect related thoughts with
  subordinate clauses and conjunctions.
- **No identical paragraph shape.** Not every reply follows topic sentence,
  explanation, example, transition. Start some with a blunt statement, some
  with a question, some with one sentence.
- **No excessive bullets.** Use them sparingly and make them uneven. If it
  fits in a sentence, use a sentence.
- **Answer first.** Discord replies are read on phones (attention-span). The
  answer goes first, then the detail, skimmable. Never bury the answer under
  an intro paragraph.

## Works in every language

The filter works in every language: structural rules carry over, word lists are English + Indonesian, other languages go through the translation test. See `references/languages.md`.

## Voice: a sample beats a rule list

A voice sample beats a rule list: calibrate against the user's own words before applying the rules. See `references/voice.md`.

## The agent's own narration (slopgent's idea)

An agent produces two kinds of text: the artifact (bot code and replies) and
what it tells the user while it works. The second drifts toward slop on its
own: "Fixed the auth bug", "everything should work now". Rules for narration,
adapted from ehmo/slopkit's slopgent:

- Report what ran, lead with the action, then the evidence. Never claim a
  PASS without the recorded observation behind it (R-35).
- "Should work" is not a result. If it was not run, say "not run".
- Do not narrate the build ("First I did X, then I did Y") unless the user
  asked for a log. The user asked for the outcome.

## Code comments: what stays and what goes

Adapted from upstream antislop-code and the windbag/grain linters. Comments
document the constraint that makes the current code correct, never the history
of the change, never a restatement of the line below.

Remove: decorative separators (`// =====`), box-drawing banners, emoji in
comments, comments that restate the obvious (`# increment the counter` above
`counter += 1`), workflow narration ("First we load the config, then we..."),
history narration ("used to be X, now Y", "was missing", ticket IDs), vague
TODOs that name no task, hedging ("should work", "not sure why"), empty
labels ("Main logic", "Important: please read"), end markers.

Keep: why this constraint exists, the platform trap, the silent failure, the
protocol rule, the performance cost, business logic and intent, architectural
decisions, security considerations. One line, two at most, never three. Never
touch the code while cleaning comments.

## The checker: run it before a reply ships

The deterministic checker script, what it flags, and what it cannot do. See `references/checker.md`.

## The Bot Reply Gate (run before any reply ships)

A Delivery Gate sized for one reply. Every line is PASS/FAIL with evidence;
a FAIL means do not ship, fix it first.

- [ ] No em dash anywhere in the reply (R-02).
- [ ] Every number in the reply has a real source (R-17). No "10K+ users",
  no "99.9% uptime" without a measurement.
- [ ] No buzzwords, no generic CTA, no temporal runway opening, no
  theatrical takeaway, no title-case list (R-15, R-16, R-36; v3.2.26).
- [ ] No chatbot closer, no fake-candid opener, no signposting (R-36).
- [ ] Every button, select, and link in the reply works or is removed
  (R-24, R-26). No dead controls.
- [ ] The reply has an empty state, a loading state, and an error state
  where it shows data (R-27). A failure answers the user; the traceback
  goes to the log.
- [ ] Sentence lengths vary; no rule-of-three default; no parataxis chain.
- [ ] The answer is first. The reply fits a phone screen.
- [ ] The checker ran: `python3 scripts/check_antislop.py` on the draft,
  exit code 0 or warnings reviewed.
- [ ] The reply was verified live in a test guild (R-35), or the report says
  "not run" instead of claiming it.

## What this skill does not cover

- Visual theme, layout, or direction for a web dashboard: that is
  design-with-hallmark's job. This skill is the filter; Hallmark is a
  direction source.
- Translation quality: that is i18n's job. The filter itself works in
  every language: structural rules carry over untouched, word lists are
  English + Indonesian, and any other language goes through the
  translation test in "Works in every language" above.
- Whether a command works: that is testing's job, and the live verification
  in R-35.

## Sources

- Upstream anti-slop v3.2.26: https://github.com/miqdadbadjuber/anti-slop
  (`antislop.md`, `skills/antislop-*/SKILL.md`, `GUIDE.md`, `ROADMAP.md`).
- Wider survey (full notes live outside this skill pack). Notable:
  jalaalrd/anti-ai-slop-writing (structural rules),
  obi12341/anti-ai-slop-writing (structural rules; every-language
  mechanism, `references/other-languages.md`),
  konten-studio/jekardah-writer (Indonesian patterns, `skills/no-ai-slop`),
  ehmo/slopkit (slopgent: the agent's own narration),
  AgriciDaniel/anti-slop (substance over surface; Shaib arXiv 2509.19163,
  Stowe ACL 2026, DAMAGE COLING 2025), dmmulroy/anti-slop and
  TinyFrontier/anti-slop-py (linter pattern), mmartoccia/grain and
  scale-venture-partners/windbag (agent-executable checks, comment rules),
  alexgreensh/attention-span (answer-first), Anaconda "Deslopping AI Prose"
  (voice sample beats rule lists).
