#!/usr/bin/env python3
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""
Test for uv python upgrade behavior.

This test reproduces the issue from https://github.com/astral-sh/uv/issues/16370
where `uv python pin 3.12` followed by `uv python upgrade` should result in
Python 3.12 being used, not a different version like 3.11.
"""

import subprocess
import sys
import tempfile
from pathlib import Path


def run_command(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess:
    """Run a command and return the result."""
    print(f"$ {' '.join(cmd)}")
    result = subprocess.run(
        cmd,
        cwd=cwd,
        capture_output=True,
        text=True,
    )
    if result.stdout:
        print(result.stdout)
    if result.stderr:
        print(result.stderr, file=sys.stderr)
    return result


def test_python_upgrade_respects_pin():
    """
    Test that `uv python upgrade` respects the pinned version.

    Steps:
    1. Create a fresh directory
    2. Run `uv python pin 3.12`
    3. Run `uv python upgrade`
    4. Verify the python version is 3.12.x
    """
    with tempfile.TemporaryDirectory() as td:
        workdir = Path(td)

        # Step 1: Pin to Python 3.12
        print("\n=== Step 1: Pin to Python 3.12 ===")
        result = run_command(["uv", "python", "pin", "3.12"], cwd=workdir)
        if result.returncode != 0:
            print(f"FAIL: uv python pin 3.12 failed with code {result.returncode}")
            return False

        # Verify .python-version file was created
        python_version_file = workdir / ".python-version"
        if not python_version_file.exists():
            print("FAIL: .python-version file was not created")
            return False

        pinned_version = python_version_file.read_text().strip()
        print(f"Pinned version in .python-version: {pinned_version}")

        # Step 2: Run uv python upgrade
        print("\n=== Step 2: Run uv python upgrade ===")
        result = run_command(["uv", "python", "upgrade"], cwd=workdir)
        if result.returncode != 0:
            print(f"FAIL: uv python upgrade failed with code {result.returncode}")
            return False

        # Step 3: Verify the Python version is 3.12.x
        print("\n=== Step 3: Verify Python version ===")

        # Read the updated .python-version file
        upgraded_version = python_version_file.read_text().strip()
        print(f"Version after upgrade: {upgraded_version}")

        # Check that we still have 3.12
        if not upgraded_version.startswith("3.12"):
            print(f"FAIL: Expected Python 3.12.x but got {upgraded_version}")
            return False

        # Also verify by running uv run python --version
        print("\n=== Step 4: Verify with uv run python --version ===")
        result = run_command(["uv", "run", "python", "--version"], cwd=workdir)
        if result.returncode != 0:
            print(f"FAIL: uv run python --version failed with code {result.returncode}")
            return False

        # Parse the Python version from output
        version_output = result.stdout.strip()
        print(f"Python version output: {version_output}")

        # Expected format: "Python 3.12.x"
        if "3.12" not in version_output:
            print(f"FAIL: Expected Python 3.12.x in output but got: {version_output}")
            return False

        print("\n=== PASS: uv python upgrade correctly uses Python 3.12 ===")
        return True


def main():
    print("Testing uv python upgrade behavior (issue #16370)")
    print("=" * 60)

    # Check that uv is available
    try:
        result = subprocess.run(
            ["uv", "--version"],
            capture_output=True,
            text=True,
        )
        print(f"uv version: {result.stdout.strip()}")
    except FileNotFoundError:
        print("ERROR: uv is not installed or not in PATH")
        return 1

    success = test_python_upgrade_respects_pin()

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
