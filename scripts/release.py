#!/usr/bin/env python3
"""
Automated release script for echr-extractor.

This script helps create releases by:
1. Checking if working directory is clean
2. Creating a Git tag
3. Pushing the tag to trigger GitHub Actions

Usage:
    python scripts/release.py patch    # 1.0.45 -> 1.0.46
    python scripts/release.py minor    # 1.0.45 -> 1.1.0
    python scripts/release.py major    # 1.0.45 -> 2.0.0
    python scripts/release.py 1.2.3    # Set specific version
"""

import argparse
import subprocess
import sys
from pathlib import Path


def run_command(cmd, check=True):
    """Run a shell command and return the result."""
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if check and result.returncode != 0:
        print(f"Error running command: {cmd}")
        print(f"Error: {result.stderr}")
        sys.exit(1)
    return result


def get_current_version():
    """Get the current version from the latest Git tag."""
    result = run_command("git describe --tags --abbrev=0", check=False)
    if result.returncode != 0:
        return "0.0.0"
    return result.stdout.strip().lstrip("v")


def increment_version(version, bump_type):
    """Increment version based on bump type."""
    parts = [int(x) for x in version.split(".")]

    if bump_type == "major":
        parts[0] += 1
        parts[1] = 0
        parts[2] = 0
    elif bump_type == "minor":
        parts[1] += 1
        parts[2] = 0
    elif bump_type == "patch":
        parts[2] += 1
    else:
        raise ValueError(f"Invalid bump type: {bump_type}")

    return ".".join(map(str, parts))


def check_working_directory_clean():
    """Check if the working directory is clean."""
    result = run_command("git status --porcelain")
    if result.stdout.strip():
        print("Error: Working directory is not clean. Please commit or stash changes.")
        print("Uncommitted changes:")
        print(result.stdout)
        print("\nThis is required to ensure clean version numbers for PyPI releases.")
        sys.exit(1)
    
    # Also check that we're on main branch
    result = run_command("git branch --show-current")
    current_branch = result.stdout.strip()
    if current_branch != "main":
        print(f"Error: You must be on the 'main' branch to create releases.")
        print(f"Current branch: {current_branch}")
        print("Please switch to main branch: git checkout main")
        sys.exit(1)


def create_and_push_tag(version):
    """Create a Git tag and push it."""
    tag_name = f"v{version}"

    print(f"Creating tag: {tag_name}")
    run_command(f"git tag -a {tag_name} -m 'Release {version}'")

    print(f"Pushing tag: {tag_name}")
    run_command(f"git push origin {tag_name}")

    print(f"✅ Successfully created and pushed tag {tag_name}")
    print(f"🚀 GitHub Actions will now build and release version {version}")


def main():
    parser = argparse.ArgumentParser(description="Create a new release")
    parser.add_argument(
        "version_or_bump",
        help="Version bump type (major, minor, patch) or specific version (e.g., 1.2.3)",
    )

    args = parser.parse_args()

    # Check if working directory is clean
    check_working_directory_clean()

    # Determine new version
    if args.version_or_bump in ["major", "minor", "patch"]:
        current_version = get_current_version()
        new_version = increment_version(current_version, args.version_or_bump)
        print(f"Current version: {current_version}")
        print(f"New version: {new_version}")
    else:
        new_version = args.version_or_bump
        print(f"Setting version to: {new_version}")

    # Confirm with user
    response = input(f"Create release {new_version}? [y/N]: ")
    if response.lower() != "y":
        print("Release cancelled.")
        sys.exit(0)

    # Create and push tag
    create_and_push_tag(new_version)


if __name__ == "__main__":
    main()
