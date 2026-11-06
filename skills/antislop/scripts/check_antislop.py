#!/usr/bin/env python3
"""Mechanical anti-slop scan for Discord bot reply drafts, docs, and source.

Adapted from upstream anti-slop v3.2.26 (miqdadbadjuber/anti-slop) plus the
wider survey behind the antislop skill (grain/windbag pattern: a
deterministic check the agent runs, not a judgment).

Usage:
    python3 scripts/check_antislop.py replies.md          # files
    echo "draft reply" | python3 scripts/check_antislop.py  # stdin
    python3 scripts/check_antislop.py --json replies.md    # machine-readable

Exit code: 0 clean, 1 warnings only, 2 errors.

What it catches: mechanical tells (em dash, R-16 buzzwords, the three v3.2.26
copywriting patterns, title-case lists, fake-stat shapes, all-caps shouting,
box-drawing banners, hedge stacks, signposting, and the Indonesian
equivalents of the runway / fake-contrast / signposting / inflated-claim
patterns). What it CANNOT catch: purpose (R-31),
substance, whether a number is real, whether a command works. A plausible
fake stat passes this scan. It never answers "was this written by AI".

Language scope: the script-based checks (em dash, box banner, all-caps,
title-case lists, fake-stat shapes) work across Latin-script languages.
The word and phrase lists are English + Indonesian (Indonesian patterns
from konten-studio/jekardah-writer, skills/no-ai-slop; the English
signposting list from upstream antislop-copywriting + Anaconda). Other
languages are not in the checker yet: add a language only by running
obi12341's translation test on each entry first, never by guessing a
translation. See skills/antislop/SKILL.md, "Works in every language".
"""

import json
import re
import sys
from dataclasses import dataclass

BUZZWORDS = [
    "AI Powered", "Next Generation", "Revolutionary", "Seamless",
    "Cutting Edge", "Intelligent", "Ultimate", "Powerful", "Effortless",
]

GENERIC_CTAS = ["Get Started", "Learn More", "Try Now", "Explore", "Discover",
                "What do you think?", "Are you ready to level up?"]

TEMPORAL_RUNWAY = [
    "in today's fast-paced",
    "in an era of",
    "in today's ever-evolving",
    "in an increasingly connected",
    "in today's digital landscape",
    "in an increasingly digital",
]

THEATRICAL = [
    "read that again",
    "let that sink in",
    "the message is clear",
    "that distinction matters",
    "the takeaway is simple",
    "here is the bottom line",
    "the bottom line:",
]

HEDGES = [
    "could potentially",
    "might possibly",
    "it might be argued",
    "it could be argued",
]

# Signposting announcements: upstream antislop-copywriting ("Let's dive in",
# "Here's what you need to know", "In this article we'll explore", "Without
# further ado") + Anaconda ("It's important to note that", "The key insight
# is"). Warning, not error: the same words can be legitimate in narrative.
SIGNPOSTING = [
    "let's dive in",
    "here's what you need to know",
    "in this article we'll explore",
    "without further ado",
    "it's important to note that",
    "the key insight is",
]

# Indonesian patterns, from konten-studio/jekardah-writer
# (skills/no-ai-slop + README Before example). The translation test
# (obi12341) was applied to each: these are press-release tells in
# Indonesian, not ordinary everyday words. Theatrical takeaways have no
# Indonesian equivalent that passes the test ("baca lagi" is ordinary
# Indonesian for "read again"), so there is no ID theatrical list.
ID_TEMPORAL_RUNWAY = [
    "di era digital",
    "di era modern",
    "di era yang",
    "di era serba",
    "di zaman digital",
    "di zaman modern",
    "di dunia yang semakin",
]

ID_FAKE_CONTRAST_RE = re.compile(r"bukan\s+(cuma|hanya|saja)\b.*\btapi\b", re.I)

ID_SIGNPOSTING = [
    "penting untuk dicatat",
    "pada akhirnya",
]

ID_INFLATED = [
    "masa depan sudah di sini",
]

FAKE_STAT_RES = [
    re.compile(r"\d+(?:\.\d+)?\s*(?:K|M|B)\+\s*(?:users|members|downloads|requests|players|servers)", re.I),
    re.compile(r"\d+\.\d+%\s*(?:uptime|faster|accuracy|success)", re.I),
    re.compile(r"\b\d{2,}K\+", re.I),
]

ALL_CAPS_RE = re.compile(r"(?:\b[A-Z]{2,}\b[\s,;:.!?]*){4,}")
# A decorative banner: a line of repeated =, -, _, * or box-drawing chars,
# optionally with a comment marker in front, or a label sandwiched between
# two banner runs (// -------- WORKFLOW --------). A bare line of = in
# Markdown is a setext heading underline, so the pure-banner form needs a
# comment marker or box-drawing chars to count.
BOX_BANNER_CHARS = "=\\-_\\*#\\u2500\\u2550\\u2502\\u250c\\u2510\\u2514\\u2518"
BOX_CHARS_RE = re.compile(r"[\u2500\u2550\u2502\u250c\u2510\u2514\u2518]{3,}")
LABELED_BANNER_RE = re.compile(
    r"^\s*(#|//|/\*|\*)?\s*[=\-_*]{4,}\s+\S.*\s[=\-_*]{4,}\s*$"
)


@dataclass
class Finding:
    check: str
    severity: str  # "error" or "warning"
    line: int
    message: str
    rule: str


def _contains(phrase: str, line: str) -> bool:
    return phrase.lower() in line.lower()


def check_line(line: str, lineno: int, findings: list) -> None:
    stripped = line.strip()
    if "\u2014" in line:
        findings.append(Finding("EMDASH", "error", lineno,
                                "em dash found; use a period or a comma instead", "R-02"))
    if "\u2013" in line and re.search(r"\s\u2013\s", line):
        findings.append(Finding("ENDASH", "warning", lineno,
                                "spaced en dash reads as an em dash; use a comma instead", "R-02"))
    for word in BUZZWORDS:
        if re.search(r"\b" + re.escape(word) + r"\b", line, re.I):
            findings.append(Finding("BUZZWORD", "error", lineno,
                                    "marketing buzzword %r; say the specific benefit" % word, "R-16"))
    if stripped:
        plain = re.sub(r"[*_`#>\[\]()]", "", stripped).strip().lower()
        if plain in [c.lower() for c in GENERIC_CTAS]:
            findings.append(Finding("GENERIC_CTA", "warning", lineno,
                                    "generic call to action %r; say the specific action" % stripped, "R-15"))
    for phrase in TEMPORAL_RUNWAY:
        if _contains(phrase, line):
            findings.append(Finding("TEMPORAL_RUNWAY", "error", lineno,
                                    "temporal runway cliche %r; start with the subject" % phrase, "R-16, R-36"))
    for phrase in THEATRICAL:
        if _contains(phrase, line):
            findings.append(Finding("THEATRICAL", "error", lineno,
                                    "theatrical takeaway %r; let the claim stand on its evidence" % phrase, "R-36"))
    for phrase in HEDGES:
        if _contains(phrase, line):
            findings.append(Finding("HEDGE", "warning", lineno,
                                    "stacked hedge %r; pick a side and state it plainly" % phrase, "R-36"))
    for phrase in SIGNPOSTING:
        if _contains(phrase, line):
            findings.append(Finding("SIGNPOSTING", "warning", lineno,
                                    "signposting announcement %r; delete the signpost, keep the content" % phrase, "R-36"))
    for phrase in ID_TEMPORAL_RUNWAY:
        if _contains(phrase, line):
            findings.append(Finding("ID_TEMPORAL_RUNWAY", "error", lineno,
                                    "Indonesian temporal runway cliche %r; start with the subject" % phrase, "R-16, R-36"))
    if ID_FAKE_CONTRAST_RE.search(line):
        findings.append(Finding("ID_FAKE_CONTRAST", "error", lineno,
                                "Indonesian fake contrast ('bukan cuma X, tapi Y'); state the real distinction or delete the frame", "R-36"))
    for phrase in ID_SIGNPOSTING:
        if _contains(phrase, line):
            findings.append(Finding("ID_SIGNPOSTING", "warning", lineno,
                                    "Indonesian signposting %r; remove the label, make the point directly" % phrase, "R-36"))
    for phrase in ID_INFLATED:
        if _contains(phrase, line):
            findings.append(Finding("ID_INFLATED", "warning", lineno,
                                    "Indonesian inflated claim %r; use the supported outcome" % phrase, "R-36"))
    for rx in FAKE_STAT_RES:
        if rx.search(line):
            findings.append(Finding("FAKE_STAT", "warning", lineno,
                                    "statistic shape with no visible source; verify the number or cut it", "R-17"))
    if ALL_CAPS_RE.search(line):
        findings.append(Finding("ALL_CAPS", "warning", lineno,
                                "all-caps shouting; write the emphasis into the sentence", "R-36"))
    # Decorative banner: pure banner line (needs a comment marker so a
    # Markdown setext underline is not flagged), labelled banner, or a run
    # of box-drawing characters.
    marker = re.match(r"^\s*(#|//|/\*|\*)\s*(.*)$", line)
    code = marker.group(2) if marker else line
    if (
        (marker and re.fullmatch(r"[" + BOX_BANNER_CHARS + r"]{8,}", code or ""))
        or LABELED_BANNER_RE.match(line)
        or BOX_CHARS_RE.search(line)
    ):
        findings.append(Finding("BOX_BANNER", "warning", lineno,
                                "decorative banner in a comment; use one plain line or remove it", "R-31"))
    if stripped.startswith(("- ", "* ")) or re.match(r"^\d+[.)]\s", stripped):
        item = re.sub(r"^(\s*[-*]|\s*\d+[.)])\s*", "", stripped)
        item = re.sub(r"[*_`]", "", item)
        words = [w for w in re.split(r"\s+", item) if any(c.isalpha() for c in w)]
        cased = [w for w in words if w[0].isalpha()]
        if len(cased) >= 3 and all(w[0].isupper() for w in cased) and any(len(w) > 3 for w in cased):
            findings.append(Finding("TITLECASE_LIST", "warning", lineno,
                                    "list item in title case on every word; use sentence case", "R-36"))


def scan_text(text: str, source: str) -> list:
    findings: list = []
    for i, line in enumerate(text.splitlines(), start=1):
        check_line(line, i, findings)
    for f in findings:
        f.message = f"{source}:{f.line}: [{f.severity}] {f.check}: {f.message} ({f.rule})"
    return findings


def main(argv: list) -> int:
    as_json = "--json" in argv
    paths = [a for a in argv if a != "--json"]
    findings: list = []
    if not paths:
        findings = scan_text(sys.stdin.read(), "<stdin>")
    else:
        for path in paths:
            try:
                with open(path, encoding="utf-8") as handle:
                    findings.extend(scan_text(handle.read(), path))
            except OSError as exc:
                print("check_antislop: cannot read %s: %s" % (path, exc), file=sys.stderr)
                return 2
    if as_json:
        print(json.dumps([
            {"check": f.check, "severity": f.severity, "line": f.line,
             "message": f.message, "rule": f.rule}
            for f in findings
        ], indent=2))
    else:
        for f in findings:
            print(f.message)
        if not findings:
            print("check_antislop: clean (no mechanical tells found)")
        else:
            print("check_antislop: %d finding(s); this scan catches mechanical "
                  "tells only, never purpose or substance" % len(findings))
    if any(f.severity == "error" for f in findings):
        return 2
    if findings:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
