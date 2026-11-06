# Security Policy

## Supported versions

| Version | Supported |
|---|---|
| 0.5.0 | Yes |
| 0.4.0 | Yes (security fixes only) |
| < 0.4.0 | No |

## Reporting a vulnerability

Do not open a public issue for a security problem. Report it
privately through GitHub Security Advisories on this repo
(**Security → Report a vulnerability**). Include the version, the
exact steps to reproduce, and what an attacker could do with it.

What counts: a vulnerability in the pack itself — the `newr`
installer (it downloads and executes code), the starter bot, the
dashboard demo server, or a skill's code sample. A bug in
discord.py, VitePress, or another dependency belongs upstream;
report it there, and open an issue here only if the pack needs a
workaround or a pin change.

The maintainer will confirm receipt, fix the issue, and credit the
reporter in the release notes unless the reporter asks not to be
named. There is no bug bounty and no fixed response time; this is a
one-person project.
