#!/usr/bin/env python3
# SPDX-License-Identifier: WTFPL
#
# This program is free software. It comes without any warranty, to the
# extent permitted by applicable law. You can redistribute it and/or modify
# it under the terms of the Do What The Fuck You Want To Public License,
# Version 2, as published by Sam Hocevar. See LICENSE.md for more details.

"""Build the release zip of OpenGroundnut with the program files only.

    python tools/make_release.py

The zip is written to release/opengroundnut-<version>.zip. It never holds
the files a running program creates for its user: the database folder
(settings with the access code and passwords, logbook, RadioID list), the
images folder, the log, recordings, the Python environment and caches.

Inside a Git working copy the files tracked by Git are packed. Without Git,
the folders and files listed in PROGRAM_PATHS are packed. In both cases
every path matching USER_DATA_PATTERNS is left out.
"""

import fnmatch
import os
import re
import subprocess
import sys
import zipfile

# Project root: the folder above this tools folder.
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# What makes up the program when Git is not available.
PROGRAM_PATHS = (
    "opengroundnut.py",
    "opengroundnut.spec",
    "requirements.txt",
    "pyproject.toml",
    "README.md",
    "CHANGELOG.md",
    "LICENSE.md",
    "Peanut_Protocol_Overview.md",
    ".gitignore",
    "install_linux.sh",
    "install_windows.bat",
    "run_linux.sh",
    "run_windows.bat",
    "src",
    "lang",
    "data",
    "flags",
    "fonts",
    "tests",
    "tools",
)

# Files and folders that belong to a user and never go into a release.
USER_DATA_PATTERNS = (
    "database/*",
    "images/*",
    "peanut.log*",
    "*.wav.part",
    "*/__pycache__/*",
    "__pycache__/*",
    "*.pyc",
    ".venv/*",
    "build/*",
    "dist/*",
    "release/*",
    ".git/*",
    ".pytest_cache/*",
    ".ruff_cache/*",
)

# Sounds shipped with the program are kept even though recordings are not.
KEEP_PATTERNS = ("data/*",)


def program_version():
    """The display version written in src/bootstrap.py (APP_DISPLAY_VERSION)."""
    with open(os.path.join(ROOT, "src", "bootstrap.py"), encoding="utf-8") as source:
        match = re.search(r'^APP_DISPLAY_VERSION\s*=\s*"([^"]+)"', source.read(), re.MULTILINE)
    return match.group(1) if match else "unknown"


def tracked_files():
    """Files tracked by Git, or None when this is not a Git working copy."""
    try:
        output = subprocess.run(
            ["git", "ls-files", "-z"], cwd=ROOT, capture_output=True, check=True
        ).stdout.decode("utf-8")
    except (OSError, subprocess.CalledProcessError):
        return None
    return [name for name in output.split("\0") if name]


def listed_files():
    """Files of PROGRAM_PATHS that exist, as paths relative to the project root."""
    found = []
    for entry in PROGRAM_PATHS:
        full = os.path.join(ROOT, entry)
        if os.path.isfile(full):
            found.append(entry)
        elif os.path.isdir(full):
            for folder, _subfolders, files in os.walk(full):
                for name in files:
                    found.append(os.path.relpath(os.path.join(folder, name), ROOT).replace(os.sep, "/"))
    return found


def is_user_data(relative_path):
    """True when a path belongs to a user's data instead of the program."""
    if any(fnmatch.fnmatch(relative_path, pattern) for pattern in KEEP_PATTERNS) and not relative_path.endswith(".pyc"):
        return False
    if relative_path.endswith(".wav") and "/" not in relative_path:
        # Recordings saved next to the program.
        return True
    return any(fnmatch.fnmatch(relative_path, pattern) for pattern in USER_DATA_PATTERNS)


# Every entry of the zip gets this date, so the archive does not record when
# or in which time zone the files were last edited, and two builds of the
# same files are identical byte for byte.
ARCHIVE_DATE = (2024, 1, 1, 0, 0, 0)


def _archive_entry(relative_path):
    """Zip entry of a program file: fixed date, plain permissions, no owner or extra fields."""
    entry = zipfile.ZipInfo(os.path.join("opengroundnut", relative_path).replace(os.sep, "/"), ARCHIVE_DATE)
    entry.compress_type = zipfile.ZIP_DEFLATED
    entry.create_system = 3
    executable = relative_path.endswith((".sh", ".py")) and os.access(os.path.join(ROOT, relative_path), os.X_OK)
    entry.external_attr = (0o100755 if executable else 0o100644) << 16
    return entry


def _read_bytes(relative_path):
    with open(os.path.join(ROOT, relative_path), "rb") as source:
        return source.read()


def main():
    files = tracked_files()
    source = "Git"
    if files is None:
        files = listed_files()
        source = "the program file list"
    files = sorted(name for name in files if not is_user_data(name) and os.path.isfile(os.path.join(ROOT, name)))
    if not files:
        print("No files to pack.", file=sys.stderr)
        return 1

    release_dir = os.path.join(ROOT, "release")
    os.makedirs(release_dir, exist_ok=True)
    zip_path = os.path.join(release_dir, "opengroundnut-{}.zip".format(program_version()))
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name in files:
            archive.writestr(_archive_entry(name), _read_bytes(name))
    print("{} files from {} packed into {}".format(len(files), source, zip_path))
    return 0


if __name__ == "__main__":
    sys.exit(main())
