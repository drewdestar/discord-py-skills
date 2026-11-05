#!/usr/bin/env python3
"""Check a discord.py bot project for common setup mistakes.

Usage:
    python scripts/check_setup.py [--path PROJECT_DIR]

Checks:
  1. requirements.txt exists and mentions discord.py
  2. .gitignore exists and covers .env, *.db, __pycache__
  3. An entry point exists with intents, a setup_hook (or load_extension),
     and an async run (bot.run / asyncio.run)
  4. A cogs directory exists with at least one cog module defining setup()
  5. The token comes from the environment, never from a literal in source
  6. No token-shaped string appears in any tracked source file

Exit code 0 when every check passes, 1 otherwise. Each check prints
PASS or FAIL with one line explaining the result.
"""

import argparse
import re
import sys
from pathlib import Path

# A Discord bot token looks like 24 chars . 6 chars . 27+ chars.
TOKEN_SHAPE = re.compile(r"[A-Za-z0-9_-]{24}\.[A-Za-z0-9_-]{6}\.[A-Za-z0-9_-]{27,}")
# A literal token assignment, e.g. TOKEN = "abc..." (placeholders excluded).
TOKEN_ASSIGN = re.compile(
    r"""(?i)\bTOKEN\s*=\s*["']([^"']{20,})["']"""
)
PLACEHOLDER_WORDS = ("your-", "example", "placeholder", "change-me", "xxx")


def is_placeholder(value: str) -> bool:
    lowered = value.lower()
    return any(word in lowered for word in PLACEHOLDER_WORDS)


def check_requirements(root: Path) -> tuple[bool, str]:
    req = root / "requirements.txt"
    if not req.is_file():
        return False, "requirements.txt is missing"
    text = req.read_text(encoding="utf-8", errors="ignore")
    if "discord.py" not in text:
        return False, "requirements.txt does not mention discord.py"
    return True, "requirements.txt lists discord.py"


def check_gitignore(root: Path) -> tuple[bool, str]:
    ignore = root / ".gitignore"
    if not ignore.is_file():
        return False, ".gitignore is missing"
    text = ignore.read_text(encoding="utf-8", errors="ignore")
    missing = [p for p in (".env", "*.db", "__pycache__") if p not in text]
    if missing:
        return False, f".gitignore does not cover: {', '.join(missing)}"
    return True, ".gitignore covers .env, *.db, __pycache__"


def check_entrypoint(root: Path) -> tuple[bool, str]:
    candidates = [root / "bot.py", root / "main.py"]
    entry = next((p for p in candidates if p.is_file()), None)
    if entry is None:
        return False, "no entry point found (bot.py or main.py)"
    text = entry.read_text(encoding="utf-8", errors="ignore")
    problems = []
    if "Intents" not in text:
        problems.append("no Intents declared")
    if "setup_hook" not in text and "load_extension" not in text:
        problems.append("no setup_hook or load_extension (cogs may never load)")
    if "bot.run(" not in text and "asyncio.run(" not in text:
        problems.append("no bot.run() or asyncio.run() entry call")
    if problems:
        return False, f"{entry.name}: " + "; ".join(problems)
    return True, f"{entry.name} declares intents, loads cogs, and runs the bot"


def check_cogs(root: Path) -> tuple[bool, str]:
    cogs_dir = root / "cogs"
    if not cogs_dir.is_dir():
        return False, "cogs/ directory is missing"
    cog_files = [p for p in cogs_dir.glob("*.py") if p.name != "__init__.py"]
    if not cog_files:
        return False, "cogs/ has no cog modules"
    with_setup = [
        p for p in cog_files
        if "async def setup" in p.read_text(encoding="utf-8", errors="ignore")
    ]
    if not with_setup:
        return False, "no cog module defines async def setup(bot)"
    names = ", ".join(sorted(p.stem for p in with_setup))
    return True, f"cogs/ has {len(with_setup)} cog(s) with setup(): {names}"


def check_token_handling(root: Path) -> tuple[bool, str]:
    py_files = sorted(root.rglob("*.py"))
    config_hits = [
        p for p in py_files
        if re.search(r"os\.environ\[[\"']DISCORD_TOKEN[\"']\]", p.read_text(encoding="utf-8", errors="ignore"))
        or re.search(r"os\.getenv\([\"']DISCORD_TOKEN[\"']", p.read_text(encoding="utf-8", errors="ignore"))
    ]
    for path in py_files:
        text = path.read_text(encoding="utf-8", errors="ignore")
        for match in TOKEN_ASSIGN.finditer(text):
            if not is_placeholder(match.group(1)):
                return False, f"{path.relative_to(root)} assigns a literal token value"
        for match in TOKEN_SHAPE.finditer(text):
            if not is_placeholder(match.group(0)):
                return False, f"{path.relative_to(root)} contains a token-shaped string"
    if not config_hits:
        return False, "no file reads DISCORD_TOKEN from the environment"
    names = ", ".join(sorted(p.name for p in config_hits))
    return True, f"token comes from the environment in: {names}"


def check_env_example(root: Path) -> tuple[bool, str]:
    example = root / ".env.example"
    if not example.is_file():
        return False, ".env.example is missing (document the variables the bot needs)"
    text = example.read_text(encoding="utf-8", errors="ignore")
    if "DISCORD_TOKEN" not in text:
        return False, ".env.example does not document DISCORD_TOKEN"
    for match in TOKEN_SHAPE.finditer(text):
        if not is_placeholder(match.group(0)):
            return False, ".env.example contains a real-looking token"
    return True, ".env.example documents DISCORD_TOKEN with a placeholder value"


CHECKS = [
    ("requirements", check_requirements),
    ("gitignore", check_gitignore),
    ("entrypoint", check_entrypoint),
    ("cogs", check_cogs),
    ("token-handling", check_token_handling),
    ("env-example", check_env_example),
]


def run_checks(root: Path) -> int:
    failures = 0
    for name, func in CHECKS:
        ok, message = func(root)
        status = "PASS" if ok else "FAIL"
        if not ok:
            failures += 1
        print(f"[{status}] {name}: {message}")
    print(f"{len(CHECKS) - failures}/{len(CHECKS)} checks passed")
    return 0 if failures == 0 else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check a discord.py bot project setup.")
    parser.add_argument(
        "--path", default=".", help="project directory to check (default: .)"
    )
    args = parser.parse_args(argv)
    return run_checks(Path(args.path))


if __name__ == "__main__":
    raise SystemExit(main())
