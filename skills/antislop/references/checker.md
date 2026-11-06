## The checker: run it before a reply ships

`scripts/check_antislop.py` (stdlib only; a copy lives in
`skills/antislop/scripts/`, byte-identical) scans reply drafts, docs, or bot
source for mechanical tells. It is the grain/windbag pattern: a deterministic
check the agent runs, not a judgment call.

```bash
python3 scripts/check_antislop.py replies.md          # files
echo "Your balance is 120 coins." | python3 scripts/check_antislop.py
python3 scripts/check_antislop.py --json replies.md   # machine-readable
```

Exit code: 0 clean, 1 warnings only, 2 errors. Errors are the hard bans
(em dash, R-16 buzzwords, temporal runway and theatrical takeaways).
Warnings need a human look (title-case lists, fake-stat shapes, all-caps,
box banners, signposting — `SIGNPOSTING` in English, `ID_SIGNPOSTING` in
Indonesian — plus the Indonesian-only checks `ID_TEMPORAL_RUNWAY`,
`ID_FAKE_CONTRAST`, `ID_INFLATED`). Quoted examples inside this skill itself will trip the scan;
that is expected, the same way upstream exempts documentation of its own
rules (R-02 carve-out): the checker scans bot output, not the rulebook.

**What the checker cannot do (honest limits).** It cannot judge purpose
(R-31), substance, or whether a number is real: a plausible fake stat passes
it. It cannot tell whether a command works. It never answers "was this
written by AI": LLM judges agree with human slop labels at chance (Shaib et
al., arXiv 2509.19163), and detectors are biased against non-native writers
(Stowe et al., ACL 2026). The checker is the floor. The gate below is the
ceiling: sourced claims, working commands, live verification.
