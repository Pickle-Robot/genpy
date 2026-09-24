"""Tests for the build-time version composition in _pickle_version.py."""

import pytest
from packaging.version import Version

import _pickle_version as pv


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    """Pin the branch so tests are independent of the checkout state."""
    monkeypatch.delenv(pv.RELEASE_ENV_VAR, raising=False)
    monkeypatch.setenv(pv.BRANCH_ENV_VAR, pv.RELEASE_BRANCH)


def test_local_build_on_main_defaults_to_release_zero():
    assert pv.get_version() == f"{pv.GENPY_VERSION}+pickle.0"


def test_release_number_comes_from_environment(monkeypatch):
    monkeypatch.setenv(pv.RELEASE_ENV_VAR, "42")
    assert pv.get_version() == f"{pv.GENPY_VERSION}+pickle.42"


@pytest.mark.parametrize("bad", ["", "-1", "1.0", "abc", "42 "])
def test_release_number_must_be_a_non_negative_integer(monkeypatch, bad):
    monkeypatch.setenv(pv.RELEASE_ENV_VAR, bad)
    with pytest.raises(ValueError):
        pv.get_version()


def test_branch_is_appended_off_main(monkeypatch):
    monkeypatch.setenv(pv.RELEASE_ENV_VAR, "7")
    monkeypatch.setenv(pv.BRANCH_ENV_VAR, "jon/Wheel_CI")
    assert pv.get_version() == f"{pv.GENPY_VERSION}+pickle.7.jon.wheel.ci"


@pytest.mark.parametrize(
    ("branch", "segment"),
    [
        ("main", ""),
        ("", ""),
        ("   ", ""),
        ("///", ""),
        ("feature/scopes", "feature.scopes"),
        ("Jon--Test__Branch", "jon.test.branch"),
        ("dependabot/pip/gitpython-3.1.59", "dependabot.pip.gitpython.3.1.59"),
        ("a" * 60, "a" * pv.MAX_BRANCH_SEGMENT_LENGTH),
    ],
)
def test_branch_sanitization(branch, segment):
    assert pv.sanitize_branch(branch) == segment


def test_truncation_never_leaves_a_trailing_dot():
    branch = "a" * (pv.MAX_BRANCH_SEGMENT_LENGTH - 1) + "/b"
    assert pv.sanitize_branch(branch) == "a" * (pv.MAX_BRANCH_SEGMENT_LENGTH - 1)


@pytest.mark.parametrize("branch", ["main", "jon/Wheel_CI", "x" * 80])
def test_versions_are_valid_and_normalized_pep440(monkeypatch, branch):
    monkeypatch.setenv(pv.RELEASE_ENV_VAR, "123")
    monkeypatch.setenv(pv.BRANCH_ENV_VAR, branch)
    version = pv.get_version()
    parsed = Version(version)
    assert str(parsed) == version
    assert parsed.local.startswith("pickle.123")


def test_published_wheels_sort_above_local_builds_and_upstream(monkeypatch):
    monkeypatch.setenv(pv.RELEASE_ENV_VAR, "0")
    local = Version(pv.get_version())
    monkeypatch.setenv(pv.RELEASE_ENV_VAR, "9")
    older = Version(pv.get_version())
    monkeypatch.setenv(pv.RELEASE_ENV_VAR, "10")
    newer = Version(pv.get_version())
    assert Version(pv.GENPY_VERSION) < local < older < newer
