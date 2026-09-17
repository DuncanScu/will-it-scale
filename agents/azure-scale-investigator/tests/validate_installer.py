"""Validate user-scoped installation without changing the real home directory."""

from __future__ import annotations

import os
import stat
import subprocess
import tempfile
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
INSTALLER = (
    REPOSITORY_ROOT
    / "agents"
    / "azure-scale-investigator"
    / "scripts"
    / "install-user-agent.sh"
)
SOURCE_PROFILE = (
    REPOSITORY_ROOT
    / ".github"
    / "agents"
    / "azure-scale-investigator.agent.md"
)
SOURCE_RUNNER = (
    REPOSITORY_ROOT
    / "agents"
    / "azure-scale-investigator"
    / "scripts"
    / "run-assessment.sh"
)


def run_installer(home: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    """Run the installer against an isolated home directory."""

    environment = os.environ.copy()
    environment["HOME"] = str(home)
    return subprocess.run(
        [str(INSTALLER), *arguments],
        check=True,
        capture_output=True,
        text=True,
        env=environment,
    )


def main() -> None:
    """Verify dry-run, idempotency, modes, and collision-safe backups."""

    with tempfile.TemporaryDirectory() as temporary_directory:
        home = Path(temporary_directory)
        dry_run = run_installer(home, "--dry-run")
        if "Would install:" not in dry_run.stdout:
            raise AssertionError("Dry-run output is missing.")
        if (home / ".copilot").exists() or (home / ".local").exists():
            raise AssertionError("Dry-run changed the target home directory.")

        run_installer(home)
        target_profile = (
            home / ".copilot" / "agents" / "azure-scale-investigator.agent.md"
        )
        target_runner = home / ".local" / "bin" / "will-it-scale-azure"
        if target_profile.read_bytes() != SOURCE_PROFILE.read_bytes():
            raise AssertionError("Installed profile differs from its source.")
        if target_runner.read_bytes() != SOURCE_RUNNER.read_bytes():
            raise AssertionError("Installed runner differs from its source.")
        if not target_runner.stat().st_mode & stat.S_IXUSR:
            raise AssertionError("Installed runner is not executable.")

        second_run = run_installer(home)
        if second_run.stdout.count("Already current:") != 2:
            raise AssertionError("Identical artifacts were not left unchanged.")
        if list(home.rglob("*.backup.*")):
            raise AssertionError("Idempotent installation created backups.")

        target_runner.write_text("locally modified\n", encoding="utf-8")
        run_installer(home)
        backups = list(target_runner.parent.glob("will-it-scale-azure.backup.*"))
        if len(backups) != 1:
            raise AssertionError(f"Expected one runner backup, found {backups}")
        if backups[0].read_text(encoding="utf-8") != "locally modified\n":
            raise AssertionError("Runner backup did not preserve prior content.")
        if target_runner.read_bytes() != SOURCE_RUNNER.read_bytes():
            raise AssertionError("Modified runner was not replaced correctly.")

        target_profile.unlink()
        symlink_target = home / "profile-target"
        symlink_target.write_text("do not replace\n", encoding="utf-8")
        target_profile.symlink_to(symlink_target)
        symlink_run = subprocess.run(
            [str(INSTALLER)],
            check=False,
            capture_output=True,
            text=True,
            env={**os.environ, "HOME": str(home)},
        )
        if symlink_run.returncode == 0:
            raise AssertionError("Installer replaced a symbolic link.")
        if "Refusing to replace symbolic link" not in symlink_run.stderr:
            raise AssertionError("Symbolic-link refusal was not explained.")
        if symlink_target.read_text(encoding="utf-8") != "do not replace\n":
            raise AssertionError("Symbolic-link target was modified.")

        print("Installer is idempotent and preserves changed artifacts.")


if __name__ == "__main__":
    main()
