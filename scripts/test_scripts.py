"""Smoke tests for scripts/make_cog.py and scripts/check_setup.py.

Run from the repo root: python -m pytest scripts/test_scripts.py -q
"""

import importlib.util
import subprocess
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
REPO_ROOT = SCRIPTS.parent
TEMPLATE = REPO_ROOT / "templates" / "starter-bot"


def run_script(script: str, *args: str, cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPTS / script), *args],
        capture_output=True,
        text=True,
        cwd=str(cwd or REPO_ROOT),
    )


def load_generated_cog(path: Path):
    spec = importlib.util.spec_from_file_location("generated_cog", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_make_cog_creates_importable_file(tmp_path):
    result = run_script("make_cog.py", "--name", "shop", "--out-dir", str(tmp_path))
    assert result.returncode == 0, result.stderr
    target = tmp_path / "shop.py"
    assert target.is_file()
    module = load_generated_cog(target)
    assert hasattr(module, "setup")
    assert hasattr(module, "Shop")
    assert "async def setup" in target.read_text(encoding="utf-8")


def test_make_cog_rejects_bad_name(tmp_path):
    result = run_script("make_cog.py", "--name", "Shop!", "--out-dir", str(tmp_path))
    assert result.returncode == 1
    assert "error" in result.stderr


def test_make_cog_refuses_overwrite_without_force(tmp_path):
    run_script("make_cog.py", "--name", "shop", "--out-dir", str(tmp_path))
    result = run_script("make_cog.py", "--name", "shop", "--out-dir", str(tmp_path))
    assert result.returncode == 1
    assert "already exists" in result.stderr


def test_make_cog_force_overwrites(tmp_path):
    run_script("make_cog.py", "--name", "shop", "--out-dir", str(tmp_path))
    result = run_script(
        "make_cog.py", "--name", "shop", "--out-dir", str(tmp_path), "--force"
    )
    assert result.returncode == 0, result.stderr


def test_check_setup_passes_on_starter_bot():
    result = run_script("check_setup.py", "--path", str(TEMPLATE))
    assert result.returncode == 0, result.stdout
    assert "6/6 checks passed" in result.stdout


def test_check_setup_fails_on_broken_project(tmp_path):
    (tmp_path / "bot.py").write_text(
        'import discord\nTOKEN = "ABCDEFGHIJKLMNOPQRSTUV.wxyz12.abcdefghijklmnopqrstuvwxyz0123456789"\n',
        encoding="utf-8",
    )
    result = run_script("check_setup.py", "--path", str(tmp_path))
    assert result.returncode == 1
    assert "[FAIL]" in result.stdout
    assert "requirements" in result.stdout
    assert "token-handling" in result.stdout
