"""ANSH AI GitHub Auto-Updater & Online Sync Engine.
Developed by Anshu Dubey.
"""

from __future__ import annotations

import json
import os
import platform
import subprocess
import sys
import threading
import time
from pathlib import Path
import requests

CURRENT_VERSION = "2.0.0"
DEFAULT_GITHUB_REPO = "devanshu/ANSH-AI"


class GitHubUpdater:
    def __init__(self, repo: str = DEFAULT_GITHUB_REPO):
        self.repo = repo
        self.current_version = CURRENT_VERSION

    def check_for_updates(self) -> dict:
        """Check GitHub for the latest release/tag."""
        url = f"https://api.github.com/repos/{self.repo}/releases/latest"
        try:
            resp = requests.get(url, timeout=5, headers={"User-Agent": "ANSH-AI-Updater"})
            if resp.status_code == 200:
                data = resp.json()
                latest_tag = data.get("tag_name", "").lstrip("v")
                body = data.get("body", "")
                download_url = data.get("html_url", "")
                has_update = latest_tag and latest_tag > self.current_version
                return {
                    "has_update": has_update,
                    "latest_version": latest_tag or self.current_version,
                    "current_version": self.current_version,
                    "notes": body,
                    "url": download_url,
                }
        except Exception as e:
            print(f"[Updater] Update check failed: {e}")

        return {
            "has_update": False,
            "latest_version": self.current_version,
            "current_version": self.current_version,
            "notes": "Up to date",
            "url": f"https://github.com/{self.repo}",
        }

    def sync_git_pull(self) -> tuple[bool, str]:
        """If running from git clone, perform a live git pull."""
        try:
            root = Path(__file__).resolve().parent.parent
            res = subprocess.run(
                ["git", "pull"],
                cwd=str(root),
                capture_output=True,
                text=True,
                timeout=15,
                check=False,
            )
            if res.returncode == 0:
                return True, (res.stdout or "Already up to date.").strip()
            return False, (res.stderr or res.stdout).strip()
        except Exception as e:
            return False, str(e)


_updater = GitHubUpdater()


def get_updater() -> GitHubUpdater:
    return _updater


def check_updates_async(callback=None):
    def _run():
        res = _updater.check_for_updates()
        if callback:
            callback(res)
    threading.Thread(target=_run, daemon=True).start()
