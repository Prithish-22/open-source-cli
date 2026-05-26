#!/usr/bin/env python3
"""
release.py
──────────
Automates bumping the version of Biju across:
- package.json
- setup.py
- tui/updater.py

Also handles Git committing, tagging, pushing, and publishing instructions.
"""

import json
import re
import os
import subprocess
import sys
from pathlib import Path

# Paths to update
ROOT = Path(__file__).resolve().parent
PACKAGE_JSON = ROOT / "package.json"
SETUP_PY     = ROOT / "setup.py"
UPDATER_PY   = ROOT / "tui" / "updater.py"

def read_current_version() -> str:
    # Read from package.json
    try:
        with open(PACKAGE_JSON, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data["version"]
    except Exception as e:
        print(f"Error reading version from package.json: {e}")
        sys.exit(1)

def bump_version(old_ver: str, new_ver: str):
    print(f"\nBumping version: {old_ver} ──> {new_ver}...\n")

    # 1. Update package.json
    with open(PACKAGE_JSON, "r", encoding="utf-8") as f:
        data = json.load(f)
    data["version"] = new_ver
    with open(PACKAGE_JSON, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    print("  [✓] Updated package.json")

    # 2. Update setup.py
    setup_content = SETUP_PY.read_text(encoding="utf-8")
    new_setup_content = re.sub(
        r"(version\s*=\s*['\"])[^'\"]+(['\"])",
        rf"\g<1>{new_ver}\g<2>",
        setup_content
    )
    SETUP_PY.write_text(new_setup_content, encoding="utf-8")
    print("  [✓] Updated setup.py")

    # 3. Update tui/updater.py
    updater_content = UPDATER_PY.read_text(encoding="utf-8")
    new_updater_content = re.sub(
        r'(CURRENT_VERSION\s*=\s*")[^"]+(")',
        rf"\g<1>{new_ver}\g<2>",
        updater_content
    )
    UPDATER_PY.write_text(new_updater_content, encoding="utf-8")
    print("  [✓] Updated tui/updater.py")

def main():
    if not PACKAGE_JSON.exists() or not SETUP_PY.exists() or not UPDATER_PY.exists():
        print("Error: Missing required package files. Run this script from the project root directory.")
        sys.exit(1)

    # Check Git status first
    status = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True)
    if status.stdout.strip():
        print("⚠️ Warning: You have uncommitted files in your git repository.")
        confirm = input("Do you want to continue anyway? [y/N]: ").strip().lower()
        if confirm != "y":
            print("Aborted.")
            sys.exit(0)

    current_version = read_current_version()
    print(f"Current version is: {current_version}")

    # Recommend next version (simple patch increment)
    parts = current_version.split(".")
    try:
        next_patch = str(int(parts[-1]) + 1)
        recommended = ".".join(parts[:-1] + [next_patch])
    except Exception:
        recommended = ""

    prompt = f"Enter new version number [{recommended}]: " if recommended else "Enter new version number: "
    new_version = input(prompt).strip()
    if not new_version:
        if recommended:
            new_version = recommended
        else:
            print("Error: Version number cannot be empty.")
            sys.exit(1)

    # Do the file updates
    bump_version(current_version, new_version)

    # Git operations
    print("\nStarting Git release process...")
    try:
        subprocess.run(["git", "add", "package.json", "setup.py", "tui/updater.py"], check=True)
        commit_msg = f"chore: bump version to {new_version}"
        subprocess.run(["git", "commit", "-m", commit_msg], check=True)
        print(f"  [✓] Committed: {commit_msg}")

        tag_name = f"v{new_version}"
        subprocess.run(["git", "tag", "-a", tag_name, "-m", f"Release {tag_name}"], check=True)
        print(f"  [✓] Tagged: {tag_name}")

        print("\nPushing to GitHub...")
        subprocess.run(["git", "push", "origin", "main"], check=True)
        subprocess.run(["git", "push", "origin", "--tags"], check=True)
        print("  [✓] Pushed main branch and tags to GitHub successfully!")

        print("\n🎉 Version bump complete & pushed to GitHub!")
        print("─" * 60)
        print("🔴 NEXT STEP: Publish to NPM registry")
        print("Make sure you are logged in to your npm account, then run:")
        print(f"  npm publish")
        print("─" * 60)

    except subprocess.CalledProcessError as e:
        print(f"\n❌ Error during git release steps: {e}")
        print("Please check your repository state manually.")

if __name__ == "__main__":
    main()
