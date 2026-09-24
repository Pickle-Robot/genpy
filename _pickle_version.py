"""Compose the wheel version for Pickle's fork of genpy.

This module is only used at build time. Hatchling executes it (see
``[tool.hatch.version]`` in ``pyproject.toml``) and evaluates
:func:`get_version` for the wheel version. It is not shipped in the wheel;
installed code reads its version from package metadata instead.

The version is upstream's release plus a PEP 440 local segment::

    0.6.16+pickle.<N>[.<branch>]

``pickle``
    Marks the wheel as Pickle's fork so it is distinguishable from ROS's
    ``genpy 0.6.16`` in filenames, pip output and Artifact Registry listings.
    A local segment also makes the wheel unpublishable to PyPI.

``<N>``
    Monotonic release counter from the ``GENPY_PICKLE_RELEASE`` environment
    variable. The release workflow sets it to its GitHub run number, which
    only ever increases, so every publish is a distinct, correctly ordered
    version and ``genpy==<exact>`` pins one publish. Local builds default to
    ``0`` so any published wheel sorts above them. Mirrors the
    ``+pickle.N`` convention used by nvblox, curobo and punq.

``<branch>``
    Present only for wheels not built from ``main``, so a developer can
    publish a branch wheel for testing without it being mistaken for (or
    ordered against) a mainline release. Taken from ``GENPY_PICKLE_BRANCH``
    when set, otherwise from ``.git/HEAD`` (detached HEAD gives no segment).
    PEP 440 local segments allow only ``[a-z0-9]`` separated by dots, so the
    branch name is lower-cased and every run of other characters becomes a
    dot.
"""

import os
import re

# Upstream release this fork is based on.
GENPY_VERSION = "0.6.16"

LOCAL_VERSION_LABEL = "pickle"
RELEASE_ENV_VAR = "GENPY_PICKLE_RELEASE"
BRANCH_ENV_VAR = "GENPY_PICKLE_BRANCH"
RELEASE_BRANCH = "main"
MAX_BRANCH_SEGMENT_LENGTH = 40


def get_release_number() -> str:
    """Get the monotonic release counter (``0`` for local builds).

    Returns:
        The value of ``GENPY_PICKLE_RELEASE``, or ``"0"`` when unset.

    Raises:
        ValueError: If ``GENPY_PICKLE_RELEASE`` is not a non-negative integer.
    """
    release = os.environ.get(RELEASE_ENV_VAR, "0")
    if not release.isdigit():
        raise ValueError(
            f"{RELEASE_ENV_VAR} must be a non-negative integer, got {release!r}"
        )
    return release


def get_git_branch() -> str:
    """Get the checked-out branch name from ``.git/HEAD``.

    Returns:
        The branch name, or ``""`` when HEAD is detached, when ``.git`` is a
        worktree pointer file rather than a directory, or when there is no
        ``.git`` at all. Pass ``GENPY_PICKLE_BRANCH`` explicitly (as the
        release workflow does) whenever the branch matters.
    """
    head_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".git", "HEAD")
    try:
        with open(head_path, encoding="utf-8") as f:
            head = f.read().strip()
    except (FileNotFoundError, NotADirectoryError):
        return ""
    prefix = "ref: refs/heads/"
    return head[len(prefix) :] if head.startswith(prefix) else ""


def sanitize_branch(branch: str) -> str:
    """Turn a git branch name into a PEP 440 local-version segment.

    Args:
        branch: The branch name, e.g. ``"jon/Wheel_CI"``.

    Returns:
        The segment, e.g. ``"jon.wheel.ci"``, or ``""`` for ``main`` and for
        names with no usable characters.
    """
    branch = branch.strip()
    if branch in ("", RELEASE_BRANCH):
        return ""
    segment = re.sub(r"[^a-z0-9]+", ".", branch.lower()).strip(".")
    return segment[:MAX_BRANCH_SEGMENT_LENGTH].rstrip(".")


def get_branch_segment() -> str:
    """Get the branch segment for the current build (``""`` on ``main``).

    Returns:
        The sanitized branch segment from ``GENPY_PICKLE_BRANCH`` or
        ``.git/HEAD``.
    """
    branch = os.environ.get(BRANCH_ENV_VAR)
    if branch is None:
        branch = get_git_branch()
    return sanitize_branch(branch)


def get_version() -> str:
    """Get the full wheel version.

    Returns:
        ``0.6.16+pickle.<N>`` on ``main``, ``0.6.16+pickle.<N>.<branch>``
        elsewhere.
    """
    version = f"{GENPY_VERSION}+{LOCAL_VERSION_LABEL}.{get_release_number()}"
    branch_segment = get_branch_segment()
    if branch_segment:
        version += f".{branch_segment}"
    return version


if __name__ == "__main__":
    print(get_version())
