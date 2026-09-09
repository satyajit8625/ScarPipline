# -*- coding: utf-8 -*-
"""Synchronize studio licenses registry to GitHub cloud repository."""

from __future__ import absolute_import, division, print_function

import os
import subprocess
import sys

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
REGISTRY_FILE = os.path.join(CURRENT_DIR, "studio_licenses_registry.json")
DEFAULT_REPO = "https://github.com/satyajit8625/scartools-licenses.git"


def sync_to_github():
    print("=" * 65)
    print("  [SCARTOOLS GITHUB CLOUD LICENSE SYNC]")
    print("=" * 65)
    print("  Target Repository : " + DEFAULT_REPO)
    print("  Registry File     : " + REGISTRY_FILE)
    print("-" * 65)

    if not os.path.isfile(REGISTRY_FILE):
        print("  [ERROR] Registry file not found: " + REGISTRY_FILE)
        return False

    git_dir = os.path.join(CURRENT_DIR, ".git")
    if not os.path.isdir(git_dir):
        print("  [1/4] Initializing local git in admin_tools...")
        subprocess.call(["git", "init"], cwd=CURRENT_DIR)
        subprocess.call(["git", "remote", "add", "origin", DEFAULT_REPO], cwd=CURRENT_DIR)
    else:
        print("  [1/4] Git repository verified.")

    # Abort any stale/interrupted rebase state
    subprocess.call(["git", "rebase", "--abort"], cwd=CURRENT_DIR, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # Configure user identity
    subprocess.call(["git", "config", "user.name", "satyajit8625"], cwd=CURRENT_DIR)
    subprocess.call(["git", "config", "user.email", "satyajit@scartools.studio"], cwd=CURRENT_DIR)

    # Ensure clean branch main
    subprocess.call(["git", "checkout", "-B", "main"], cwd=CURRENT_DIR)

    print("  [2/4] Staging studio_licenses_registry.json...")
    subprocess.call(["git", "add", "studio_licenses_registry.json"], cwd=CURRENT_DIR)

    print("  [3/4] Committing license changes...")
    subprocess.call(["git", "commit", "-m", "Update license registry [Cloud Sync]"], cwd=CURRENT_DIR)

    print("  [4/4] Pushing to GitHub (main)...")
    res = subprocess.call(["git", "push", "-u", "origin", "main", "--force"], cwd=CURRENT_DIR)

    if res == 0:
        print("=" * 65)
        print("  [OK] CLOUD SYNC COMPLETE! Worldwide remote artists are now synced.")
        print("=" * 65)
        return True
    else:
        print("=" * 65)
        print("  [NOTE] Git push returned " + str(res) + ". Authenticate if prompted.")
        print("=" * 65)
        return False


if __name__ == "__main__":
    sync_to_github()
