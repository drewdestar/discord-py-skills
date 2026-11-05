#!/usr/bin/env python3
"""Generate a new discord.py cog file from a template.

Usage:
    python scripts/make_cog.py --name shop
    python scripts/make_cog.py --name shop --command buy --out-dir cogs
    python scripts/make_cog.py --name shop --force   # overwrite an existing file

The generated cog has one slash command and a setup() function, and it
imports cleanly. Fill in the command body with real logic.
"""

import argparse
import keyword
import re
import sys
from pathlib import Path

COG_TEMPLATE = '''"""Cog: {name}."""

import discord
from discord import app_commands
from discord.ext import commands


class {class_name}(commands.Cog):
    """{name} commands."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="{command}", description="{command_description}")
    async def {command}(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_message("{command_reply}")


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog({class_name}(bot))
'''


def to_class_name(name: str) -> str:
    """Convert a snake_case cog name to a PascalCase class name."""
    return "".join(part.capitalize() for part in name.split("_"))


def validate_name(name: str) -> str | None:
    """Return an error message if the name is unusable, else None."""
    if not name:
        return "cog name must not be empty"
    if not re.fullmatch(r"[a-z][a-z0-9_]*", name):
        return (
            "cog name must start with a lowercase letter and contain only "
            "lowercase letters, digits, and underscores"
        )
    if keyword.iskeyword(name):
        return f"cog name {name!r} is a Python keyword"
    return None


def generate(name: str, command: str, out_dir: Path, force: bool) -> Path:
    error = validate_name(name)
    if error:
        raise ValueError(error)
    command_error = validate_name(command)
    if command_error:
        raise ValueError(f"command name: {command_error}")

    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / f"{name}.py"
    if target.exists() and not force:
        raise FileExistsError(
            f"{target} already exists (use --force to overwrite)"
        )

    text = COG_TEMPLATE.format(
        name=name,
        class_name=to_class_name(name),
        command=command,
        command_description=f"Run the {command} command.",
        command_reply=f"{command} works.",
    )
    target.write_text(text, encoding="utf-8")
    return target


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate a discord.py cog file.")
    parser.add_argument("--name", required=True, help="cog name, e.g. shop")
    parser.add_argument(
        "--command", default="hello", help="first slash command name (default: hello)"
    )
    parser.add_argument(
        "--out-dir", default="cogs", help="directory for the cog file (default: cogs)"
    )
    parser.add_argument(
        "--force", action="store_true", help="overwrite an existing cog file"
    )
    args = parser.parse_args(argv)

    try:
        target = generate(args.name, args.command, Path(args.out_dir), args.force)
    except (ValueError, FileExistsError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(f"created {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
