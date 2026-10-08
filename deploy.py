#!/usr/bin/env python3

import os
import sys
import json
import shutil
import subprocess
from pathlib import Path
from getpass import getpass

import requests


# =========================
# CONFIG
# =========================

CPANEL_USER = "hazardst"
DOMAIN = "hazardstudio.ir"
CPANEL_HOST = DOMAIN
REMOTE_ROOT = "/home/hazardst/public_html"

GITHUB_API = "https://api.github.com"


# =========================
# COLORS
# =========================

RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
RESET = "\033[0m"


def ok(msg):
    print(f"{GREEN}[✓]{RESET} {msg}")


def info(msg):
    print(f"{CYAN}[→]{RESET} {msg}")


def warn(msg):
    print(f"{YELLOW}[!]{RESET} {msg}")


def error(msg):
    print(f"{RED}[✗]{RESET} {msg}")


# =========================
# COMMAND
# =========================

def run(cmd, cwd=None, check=True):
    return subprocess.run(
        cmd,
        cwd=cwd,
        check=check,
        text=True
    )


# =========================
# CREATE PACKAGE FILES
# =========================

def create_package():
    info("Checking Python package...")

    package_dir = Path("hazardstudio")
    package_dir.mkdir(exist_ok=True)

    init_file = package_dir / "__init__.py"

    if not init_file.exists():
        init_file.write_text(
            '''"""
Hazard Studio CLI
"""

__version__ = "0.1.0"
''',
            encoding="utf-8"
        )
        ok("Created hazardstudio/__init__.py")

    cli_file = package_dir / "cli.py"

    if not cli_file.exists():
        cli_file.write_text(
            '''def main():
    print("Hazard Studio CLI")


if __name__ == "__main__":
    main()
''',
            encoding="utf-8"
        )
        ok("Created hazardstudio/cli.py")

    pyproject = Path("pyproject.toml")

    if not pyproject.exists():
        pyproject.write_text(
            '''[build-system]
requires = ["setuptools>=61"]
build-backend = "setuptools.build_meta"

[project]
name = "hazardstudio-cli"
version = "0.1.0"
description = "Hazard Studio CLI"
requires-python = ">=3.9"
dependencies = [
    "requests>=2.31.0"
]

[project.scripts]
hazardstudio = "hazardstudio.cli:main"

[tool.setuptools]
packages = ["hazardstudio"]
''',
            encoding="utf-8"
        )

        ok("Created pyproject.toml")

    req = Path("requirements.txt")

    if not req.exists():
        req.write_text(
            "requests>=2.31.0\n",
            encoding="utf-8"
        )
        ok("Created requirements.txt")


# =========================
# GITIGNORE
# =========================

def create_gitignore():
    gitignore = Path(".gitignore")

    if gitignore.exists():
        return

    gitignore.write_text(
        """__pycache__/
*.pyc
*.pyo
*.pyd

.venv/
venv/
env/

.env
.env.*
*.token
*.secret

*.db
*.sqlite
*.sqlite3

.DS_Store

.vscode/
.idea/

dist/
build/
*.egg-info/

__pycache__/
""",
        encoding="utf-8"
    )

    ok("Created .gitignore")


# =========================
# CPANEL
# =========================

def cpanel_headers(token):
    return {
        "Authorization": f"cpanel {CPANEL_USER}:{token}"
    }


def cpanel_request(token, module, function, data=None, files=None):
    url = (
        f"https://{CPANEL_HOST}:2083"
        f"/execute/{module}/{function}"
    )

    response = requests.post(
        url,
        headers=cpanel_headers(token),
        data=data,
        files=files,
        timeout=120
    )

    try:
        result = response.json()
    except Exception:
        error(response.text)
        response.raise_for_status()
        return None

    if result.get("status") != 1:
        print(json.dumps(result, indent=2, ensure_ascii=False))
        raise RuntimeError("cPanel API request failed")

    return result


def remote_dir_exists(token, path):
    try:
        result = cpanel_request(
            token,
            "Fileman",
            "list_files",
            data={
                "dir": path
            }
        )

        return result is not None

    except Exception:
        return False


def make_remote_dir(token, path):
    try:
        cpanel_request(
            token,
            "Fileman",
            "mkdir",
            data={
                "path": path
            }
        )

        ok(f"Created: {path}")

    except Exception as e:
        # If it already exists, continue.
        if "already exists" in str(e).lower():
            return
        raise


def upload_file(token, local_file, remote_dir):
    with open(local_file, "rb") as f:
        result = cpanel_request(
            token,
            "Fileman",
            "upload_files",
            data={
                "dir": remote_dir
            },
            files={
                "file-1": (
                    Path(local_file).name,
                    f
                )
            }
        )

    return result


# =========================
# FILE FILTER
# =========================

SKIP_DIRS = {
    ".git",
    ".venv",
    "venv",
    "env",
    "__pycache__",
    ".idea",
    ".vscode",
    "node_modules",
    "build",
    "dist"
}

SKIP_FILES = {
    ".env",
    ".env.local",
    "deploy.py"
}


def should_skip(path):
    parts = set(path.parts)

    if parts & SKIP_DIRS:
        return True

    if path.name in SKIP_FILES:
        return True

    if path.name.endswith(".token"):
        return True

    if path.name.endswith(".secret"):
        return True

    if path.suffix in {
        ".db",
        ".sqlite",
        ".sqlite3"
    }:
        return True

    return False


# =========================
# UPLOAD PROJECT
# =========================

def upload_project(token):
    root = Path.cwd()

    info(f"Uploading project to {DOMAIN}")

    uploaded = 0

    # First create directories
    for current, dirs, files in os.walk(root):

        current_path = Path(current)
        relative = current_path.relative_to(root)

        if relative != Path("."):
            if should_skip(relative):
                dirs[:] = []
                continue

            remote = (
                Path(REMOTE_ROOT)
                / relative
            )

            try:
                make_remote_dir(
                    token,
                    str(remote)
                )
            except Exception as e:
                warn(f"Directory error: {relative}: {e}")

    # Then upload files
    for current, dirs, files in os.walk(root):

        current_path = Path(current)
        relative = current_path.relative_to(root)

        if should_skip(relative):
            dirs[:] = []
            continue

        remote_dir = Path(REMOTE_ROOT) / relative

        for filename in files:
            local = current_path / filename

            if should_skip(local.relative_to(root)):
                continue

            try:
                info(f"Uploading {local}")

                upload_file(
                    token,
                    str(local),
                    str(remote_dir)
                )

                uploaded += 1
                ok(str(local))

            except Exception as e:
                error(
                    f"{local}: {e}"
                )

    ok(f"{uploaded} files uploaded")


# =========================
# GITHUB
# =========================

def github_headers(token):
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28"
    }


def github_create_repo(token, repo_name, private=False):
    info("Creating GitHub repository...")

    response = requests.post(
        f"{GITHUB_API}/user/repos",
        headers=github_headers(token),
        json={
            "name": repo_name,
            "description": "Hazard Studio project",
            "private": private,
            "auto_init": False
        },
        timeout=60
    )

    if response.status_code == 201:
        data = response.json()

        ok(
            f"GitHub repository created: "
            f"{data['html_url']}"
        )

        return data

    if response.status_code == 422:
        warn("Repository already exists")

        me = requests.get(
            f"{GITHUB_API}/user",
            headers=github_headers(token),
            timeout=60
        )

        me.raise_for_status()

        username = me.json()["login"]

        return {
            "html_url":
                f"https://github.com/{username}/{repo_name}",
            "clone_url":
                f"https://github.com/{username}/{repo_name}.git"
        }

    error(response.text)
    response.raise_for_status()


# =========================
# GIT
# =========================

def setup_git(github_token, repo):
    root = Path.cwd()

    git_dir = root / ".git"

    if not git_dir.exists():
        info("Initializing Git...")
        run(["git", "init"])
        ok("Git initialized")

    # Get repository URL
    repo_url = repo["clone_url"]

    # Remove old origin if exists
    result = subprocess.run(
        ["git", "remote", "get-url", "origin"],
        cwd=root,
        text=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )

    if result.returncode == 0:
        run(
            ["git", "remote", "remove", "origin"],
            cwd=root
        )

    # Ask GitHub username
    me = requests.get(
        f"{GITHUB_API}/user",
        headers=github_headers(github_token),
        timeout=60
    )

    me.raise_for_status()

    username = me.json()["login"]

    # Token-authenticated URL
    auth_url = (
        f"https://{username}:{github_token}"
        f"@github.com/"
        f"{username}/"
        f"{repo_url.split('/')[-1].replace('.git', '')}.git"
    )

    run(
        ["git", "remote", "add", "origin", auth_url],
        cwd=root
    )

    run(
        ["git", "add", "-A"],
        cwd=root
    )

    # Commit
    result = subprocess.run(
        ["git", "commit", "-m", "Initial Hazard Studio release"],
        cwd=root,
        text=True
    )

    if result.returncode != 0:
        warn("Nothing new to commit")

    # Branch
    run(
        ["git", "branch", "-M", "main"],
        cwd=root
    )

    info("Pushing to GitHub...")

    run(
        ["git", "push", "-u", "origin", "main"],
        cwd=root
    )

    # IMPORTANT:
    # Remove token-containing remote URL after push.
    run(
        ["git", "remote", "set-url", "origin", repo_url],
        cwd=root
    )

    ok("Code pushed to GitHub")


# =========================
# MAIN
# =========================

def main():

    print()
    print("======================================")
    print("       HAZARD STUDIO DEPLOY")
    print("======================================")
    print()

    root = Path.cwd()

    if not (root / "deploy.py").exists():
        error(
            "Run this script from your project root."
        )
        sys.exit(1)

    # -------------------------
    # cPanel token
    # -------------------------

    print()
    print("cPanel configuration")
    print("--------------------")

    cpanel_token = getpass(
        "Enter cPanel API token: "
    ).strip()

    if not cpanel_token:
        error("cPanel token is empty")
        sys.exit(1)

    # -------------------------
    # GitHub token
    # -------------------------

    print()
    print("GitHub configuration")
    print("--------------------")

    github_token = getpass(
        "Enter GitHub token: "
    ).strip()

    if not github_token:
        error("GitHub token is empty")
        sys.exit(1)

    repo_name = input(
        "GitHub repository name [hazardstudio]: "
    ).strip()

    if not repo_name:
        repo_name = "hazardstudio"

    private_answer = input(
        "Private repository? [y/N]: "
    ).strip().lower()

    private = private_answer == "y"

    # -------------------------
    # Create package
    # -------------------------

    print()
    info("Preparing package...")

    create_package()
    create_gitignore()

    # -------------------------
    # Upload hosting
    # -------------------------

    print()
    print("======================================")
    print("          CPANEL UPLOAD")
    print("======================================")

    upload_project(cpanel_token)

    # -------------------------
    # GitHub
    # -------------------------

    print()
    print("======================================")
    print("          GITHUB RELEASE")
    print("======================================")

    repo = github_create_repo(
        github_token,
        repo_name,
        private
    )

    setup_git(
        github_token,
        repo
    )

    # -------------------------
    # DONE
    # -------------------------

    print()
    print("======================================")
    print(f"{GREEN}       DEPLOY SUCCESS ✓{RESET}")
    print("======================================")
    print()

    print(
        f"{GREEN}Website:{RESET} "
        f"https://{DOMAIN}"
    )

    print(
        f"{GREEN}GitHub:{RESET} "
        f"{repo['html_url']}"
    )

    print()
    print("Your project has been uploaded.")
    print("GitHub repository has been created.")
    print()


if __name__ == "__main__":
    main()
