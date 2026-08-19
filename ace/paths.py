"""Lexical workspace-path checks that work on Python 3.8 without resolving links."""
import os
import stat
from pathlib import Path


def absolute(path):
    """Return an absolute, normalized lexical path without resolving symlinks."""
    return Path(os.path.abspath(os.fspath(path)))


def relative_to(root, path):
    """Return a lexical workspace-relative path, or None when it is outside."""
    try:
        return absolute(path).relative_to(absolute(root))
    except ValueError:
        return None


def explicit_regular_file(root, value, label):
    """Validate an explicit input before any operation can follow its final link.

    Workspace inputs also reject a symlink in any descendant component, so a
    lexically in-workspace spelling cannot escape the workspace while read.
    """
    path = absolute(value)
    relative = relative_to(root, path)
    try:
        mode = path.lstat().st_mode
    except OSError:
        raise ValueError(label + " is missing or unreadable")
    if stat.S_ISLNK(mode):
        raise ValueError(label + " symlink is unsafe")
    if not stat.S_ISREG(mode):
        raise ValueError(label + " is missing or unreadable")
    if relative is not None:
        current = absolute(root)
        for part in relative.parts:
            current = current / part
            if current.is_symlink():
                raise ValueError(label + " symlink is unsafe")
    return path, relative is not None
