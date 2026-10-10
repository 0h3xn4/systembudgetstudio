"""The per-user Linux install and uninstall scripts, run against a stub bundle in a temp HOME."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(sys.platform == "win32", reason="POSIX shell scripts")

SCRIPTS = Path(__file__).resolve().parents[2] / "packaging" / "linux"


@pytest.fixture
def bundle(tmp_path: Path) -> Path:
    """A fake extracted bundle: two executables that answer --self-test, a library folder."""
    folder = tmp_path / "bundle" / "system-budget-studio"
    (folder / "_internal").mkdir(parents=True)
    (folder / "_internal" / "lib.so").write_text("x")
    for name in ("system-budget-studio", "budget"):
        exe = folder / name
        exe.write_text('#!/bin/sh\n[ "$1" = "--self-test" ] && echo "Self-test passed."\nexit 0\n')
        exe.chmod(0o755)
    for script in ("install.sh", "uninstall.sh"):
        shutil.copy(SCRIPTS / script, folder / script)
    return folder


def run(script: Path, home: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = {"PATH": os.environ["PATH"], "HOME": str(home)}
    return subprocess.run(
        ["sh", str(script), *args], env=env, capture_output=True, text=True, check=False
    )


def test_install_creates_program_links_and_menu_entry(bundle: Path, tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    result = run(bundle / "install.sh", home)
    assert result.returncode == 0, result.stderr
    prefix = home / ".local/opt/system-budget-studio"
    assert (prefix / "_internal/lib.so").is_file()
    assert (prefix / "uninstall.sh").is_file() and (prefix / "install-manifest.txt").is_file()
    for name in ("system-budget-studio", "budget"):
        link = home / ".local/bin" / name
        assert link.is_symlink() and os.readlink(link) == str(prefix / name)
    entry = (home / ".local/share/applications/system-budget-studio.desktop").read_text()
    assert f'Exec="{prefix}/system-budget-studio" %f' in entry
    assert "Terminal=false" in entry
    assert "Self-test passed." in result.stdout


def test_uninstall_removes_exactly_what_was_installed(bundle: Path, tmp_path: Path) -> None:
    home = tmp_path / "home"
    (home / ".local/bin").mkdir(parents=True)
    other = home / ".local/bin/other-tool"
    other.write_text("keep me")
    project = home / "projects" / "mine" / "project.yaml"
    project.parent.mkdir(parents=True)
    project.write_text("keep me too")
    assert run(bundle / "install.sh", home).returncode == 0
    prefix = home / ".local/opt/system-budget-studio"
    result = run(prefix / "uninstall.sh", home)
    assert result.returncode == 0, result.stderr
    assert not prefix.exists()
    assert not (home / ".local/bin/budget").exists()
    assert not (home / ".local/share/applications/system-budget-studio.desktop").exists()
    assert other.read_text() == "keep me" and project.read_text() == "keep me too"


def test_uninstall_leaves_a_link_that_points_elsewhere(bundle: Path, tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    assert run(bundle / "install.sh", home).returncode == 0
    link = home / ".local/bin/budget"
    link.unlink()
    link.symlink_to("/bin/true")
    assert run(home / ".local/opt/system-budget-studio/uninstall.sh", home).returncode == 0
    assert link.is_symlink() and os.readlink(link) == "/bin/true"


def test_upgrade_replaces_the_installation(bundle: Path, tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    assert run(bundle / "install.sh", home).returncode == 0
    (bundle / "_internal" / "lib.so").write_text("new version")
    result = run(bundle / "install.sh", home)
    assert result.returncode == 0, result.stderr
    prefix = home / ".local/opt/system-budget-studio"
    assert (prefix / "_internal/lib.so").read_text() == "new version"
    assert (home / ".local/bin/budget").is_symlink()


def test_custom_prefix_without_links_or_menu(bundle: Path, tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    prefix = tmp_path / "apps" / "sbs"
    result = run(bundle / "install.sh", home, "--prefix", str(prefix), "--no-links", "--no-desktop")
    assert result.returncode == 0, result.stderr
    assert (prefix / "budget").is_file()
    assert not (home / ".local").exists()
    assert run(prefix / "uninstall.sh", home).returncode == 0
    assert not prefix.exists()


def test_foreign_folder_is_never_overwritten(bundle: Path, tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    prefix = tmp_path / "precious"
    prefix.mkdir()
    (prefix / "data.txt").write_text("mine")
    result = run(bundle / "install.sh", home, "--prefix", str(prefix))
    assert result.returncode == 1
    assert (prefix / "data.txt").read_text() == "mine"


def test_home_is_refused_as_prefix(bundle: Path, tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    assert run(bundle / "install.sh", home, "--prefix", str(home)).returncode == 1


def test_running_outside_a_bundle_is_refused(tmp_path: Path) -> None:
    folder = tmp_path / "empty"
    folder.mkdir()
    shutil.copy(SCRIPTS / "install.sh", folder / "install.sh")
    result = run(folder / "install.sh", tmp_path)
    assert result.returncode == 1 and "bundle" in result.stderr


def test_uninstall_refuses_a_folder_it_did_not_install(tmp_path: Path) -> None:
    folder = tmp_path / "other"
    folder.mkdir()
    shutil.copy(SCRIPTS / "uninstall.sh", folder / "uninstall.sh")
    (folder / "keep.txt").write_text("x")
    assert run(folder / "uninstall.sh", tmp_path).returncode == 1
    assert (folder / "keep.txt").exists()


# ---- audit follow-up -------------------------------------------------------------------------
def installed(bundle: Path, home: Path, *args: str) -> Path:
    home.mkdir(exist_ok=True)
    result = run(bundle / "install.sh", home, *args)
    assert result.returncode == 0, result.stderr
    return home / ".local/opt/system-budget-studio"


def test_running_the_installed_copy_never_destroys_the_installation(
    bundle: Path, tmp_path: Path
) -> None:
    home = tmp_path / "home"
    prefix = installed(bundle, home)
    result = run(prefix / "install.sh", home)
    assert result.returncode != 0 and "installed copy" in result.stderr
    assert (prefix / "budget").is_file() and (prefix / "_internal/lib.so").is_file()
    assert (home / ".local/bin/budget").is_symlink()


def test_a_broken_old_uninstaller_does_not_block_an_upgrade(bundle: Path, tmp_path: Path) -> None:
    home = tmp_path / "home"
    prefix = installed(bundle, home)
    (prefix / "uninstall.sh").unlink()
    (prefix / "stale-file").write_text("old", encoding="utf-8")
    (bundle / "_internal" / "lib.so").write_text("v2", encoding="utf-8")
    installed(bundle, home)
    assert (prefix / "_internal/lib.so").read_text(encoding="utf-8") == "v2"
    assert not (prefix / "stale-file").exists()  # nothing of the old version is mixed in


def test_trailing_slash_and_relative_prefixes_are_normalised(bundle: Path, tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    target = tmp_path / "apps" / "sbs"
    result = run(bundle / "install.sh", home, "--prefix", f"{target}/")
    assert result.returncode == 0, result.stderr
    link = home / ".local/bin/budget"
    assert os.readlink(link) == str(target.resolve() / "budget")
    assert run(target / "uninstall.sh", home).returncode == 0
    assert not link.exists() and not link.is_symlink() and not target.exists()


def test_relative_prefix_gives_absolute_links(bundle: Path, tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    env = {"PATH": os.environ["PATH"], "HOME": str(home)}
    work = tmp_path / "work"
    work.mkdir()
    done = subprocess.run(
        ["sh", str(bundle / "install.sh"), "--prefix", "rel/sbs"],
        env=env,
        cwd=work,
        capture_output=True,
        text=True,
        check=False,
    )
    assert done.returncode == 0, done.stderr
    assert os.path.isabs(os.readlink(home / ".local/bin/budget"))
    assert (work / "rel/sbs/budget").is_file()


def test_an_existing_command_of_the_user_is_not_replaced(bundle: Path, tmp_path: Path) -> None:
    home = tmp_path / "home"
    (home / ".local/bin").mkdir(parents=True)
    mine = home / ".local/bin/budget"
    mine.write_text("my own tool", encoding="utf-8")
    result = run(bundle / "install.sh", home)
    assert result.returncode == 0, result.stderr
    assert mine.read_text(encoding="utf-8") == "my own tool" and not mine.is_symlink()
    assert "not replacing" in (result.stdout + result.stderr).lower()
    prefix = home / ".local/opt/system-budget-studio"
    assert run(prefix / "uninstall.sh", home).returncode == 0
    assert mine.read_text(encoding="utf-8") == "my own tool"  # uninstall leaves it too


def test_force_replaces_an_existing_command(bundle: Path, tmp_path: Path) -> None:
    home = tmp_path / "home"
    (home / ".local/bin").mkdir(parents=True)
    (home / ".local/bin/budget").write_text("old", encoding="utf-8")
    result = run(bundle / "install.sh", home, "--force")
    assert result.returncode == 0, result.stderr
    assert (home / ".local/bin/budget").is_symlink()


def test_desktop_entry_escapes_special_characters(bundle: Path, tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    prefix = tmp_path / "100%" / "a$b" / "c d"
    result = run(bundle / "install.sh", home, "--prefix", str(prefix))
    assert result.returncode == 0, result.stderr
    entry = (home / ".local/share/applications/system-budget-studio.desktop").read_text("utf-8")
    exec_line = next(line for line in entry.splitlines() if line.startswith("Exec="))
    assert "100%%" in exec_line  # a literal percent sign is %%
    assert "a\\\\$b" in exec_line  # a literal dollar sign: \$ inside quotes, written as \\$
    assert exec_line.startswith('Exec="') and exec_line.endswith('" %f')


def test_the_installer_can_be_started_through_a_symlink(bundle: Path, tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    os.symlink(bundle / "install.sh", elsewhere / "install.sh")
    result = run(elsewhere / "install.sh", home)
    assert result.returncode == 0, result.stderr
    assert (home / ".local/opt/system-budget-studio/budget").is_file()


def test_help_shows_only_the_usage(bundle: Path, tmp_path: Path) -> None:
    result = run(bundle / "install.sh", tmp_path, "--help")
    assert result.returncode == 0
    assert "Usage" in result.stdout and "set -eu" not in result.stdout
