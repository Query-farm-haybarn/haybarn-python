"""setuptools_scm integration for DuckDB Python versioning.

This module provides the setuptools_scm version scheme and handles environment variable overrides
to match the exact behavior of the original DuckDB Python package.
"""

import os
import re
from typing import Protocol

# Import from our own versioning module to avoid duplication
from ._versioning import format_version, parse_version

# MAIN_BRANCH_VERSIONING should be 'True' on main branch only
MAIN_BRANCH_VERSIONING = False

# Haybarn: setuptools_scm reads SETUPTOOLS_SCM_PRETEND_VERSION_FOR_<NORMALIZED_DIST_NAME>.
# This package's name is `haybarn` (changed from upstream `duckdb`), so the
# env var name MUST end in _FOR_HAYBARN — the old _FOR_DUCKDB suffix is silently
# ignored and setuptools_scm falls back to scanning git tags (finding the
# inherited upstream v1.5.2 tag from before the fork and bumping patch by one).
SCM_PRETEND_ENV_VAR = "SETUPTOOLS_SCM_PRETEND_VERSION_FOR_HAYBARN"
SCM_GLOBAL_PRETEND_ENV_VAR = "SETUPTOOLS_SCM_PRETEND_VERSION"
# OVERRIDE_GIT_DESCRIBE carries the upstream DuckDB tag (e.g. "v1.5.2") which
# drives storage-format compatibility on the C++ side. HAYBARN_GIT_DESCRIBE
# carries the Haybarn-specific tag (e.g. "haybarn-v1.5.2-rc1") and is what
# the *wheel version* should track. If set, we prefer it; otherwise we fall
# back to OVERRIDE_GIT_DESCRIBE so the existing behavior is preserved for
# builds that haven't been wired into the new naming yet.
OVERRIDE_GIT_DESCRIBE_ENV_VAR = "OVERRIDE_GIT_DESCRIBE"
HAYBARN_GIT_DESCRIBE_ENV_VAR = "HAYBARN_GIT_DESCRIBE"


class _VersionObject(Protocol):
    tag: object
    distance: int
    dirty: bool


def _main_branch_versioning() -> bool:
    from_env = os.getenv("MAIN_BRANCH_VERSIONING")
    return from_env == "1" if from_env is not None else MAIN_BRANCH_VERSIONING


def version_scheme(version: _VersionObject) -> str:
    """setuptools_scm version scheme that matches DuckDB's original behavior.

    Args:
        version: setuptools_scm version object

    Returns:
        PEP440 compliant version string
    """
    print(f"[version_scheme] version object: {version}")
    print(f"[version_scheme] version.tag: {version.tag}")
    print(f"[version_scheme] version.distance: {version.distance}")
    print(f"[version_scheme] version.dirty: {version.dirty}")

    # Handle case where tag is None
    if version.tag is None:
        msg = "Need a valid version. Did you set a fallback_version in pyproject.toml?"
        raise ValueError(msg)

    distance = int(version.distance or 0)
    try:
        if distance == 0 and not version.dirty:
            return _tag_to_version(str(version.tag))
        return _bump_dev_version(str(version.tag), distance)
    except Exception as e:
        msg = f"Failed to bump version: {e}"
        raise RuntimeError(msg) from e


def _tag_to_version(tag: str) -> str:
    """Bump the version when we're on a tag."""
    major, minor, patch, post, rc = parse_version(tag)
    return format_version(major, minor, patch, post=post, rc=rc)


def _bump_dev_version(base_version: str, distance: int) -> str:
    """Bump the given version."""
    if distance == 0:
        msg = "Dev distance is 0, cannot bump version."
        raise ValueError(msg)
    major, minor, patch, post, rc = parse_version(base_version)

    if post != 0:
        # We're developing on top of a post-release
        return f"{format_version(major, minor, patch, post=post + 1)}.dev{distance}"
    elif rc != 0:
        # We're developing on top of an rc
        return f"{format_version(major, minor, patch, rc=rc + 1)}.dev{distance}"
    elif _main_branch_versioning():
        return f"{format_version(major, minor + 1, 0)}.dev{distance}"
    return f"{format_version(major, minor, patch + 1)}.dev{distance}"


def forced_version_from_env() -> str:
    """Handle getting versions from environment variables.

    Prefers HAYBARN_GIT_DESCRIBE (e.g. "haybarn-v1.5.2-rc1-34-g111577c34c") when
    set — that's the Haybarn-specific tag and is what the wheel version should
    track. The leading "haybarn-v" prefix is stripped so the value matches the
    "v…"-prefixed shape that _git_describe_override_to_pep_440 expects (i.e.
    "v1.5.2-rc1-34-g111577c34c"). Falls back to OVERRIDE_GIT_DESCRIBE for
    upstream-compatible builds that pass the DuckDB tag directly.

    If SETUPTOOLS_SCM_PRETEND_VERSION* is set without a corresponding describe
    override, it gets unset to avoid masking the real version.
    """
    haybarn_value = os.getenv(HAYBARN_GIT_DESCRIBE_ENV_VAR)
    override_value = os.getenv(OVERRIDE_GIT_DESCRIBE_ENV_VAR)
    describe_value = None
    describe_source = None

    if haybarn_value:
        # "haybarn-v1.5.2-rc1-34-g111577c34c" -> "v1.5.2-rc1-34-g111577c34c"
        # If something else is passed (e.g. a bare sha from --always fallback),
        # leave it alone and let the parser raise — better than silently masking.
        describe_value = re.sub(r"^haybarn-", "", haybarn_value)
        describe_source = HAYBARN_GIT_DESCRIBE_ENV_VAR
    elif override_value:
        describe_value = override_value
        describe_source = OVERRIDE_GIT_DESCRIBE_ENV_VAR

    pep440_version = None

    if describe_value:
        print(f"[versioning] Found {describe_source}={describe_value}")
        pep440_version = _git_describe_override_to_pep_440(describe_value)
        os.environ[SCM_PRETEND_ENV_VAR] = pep440_version
        print(f"[versioning] Injected {SCM_PRETEND_ENV_VAR}={pep440_version}")
    elif SCM_PRETEND_ENV_VAR in os.environ:
        _remove_unsupported_env_var(SCM_PRETEND_ENV_VAR)

    # Always check and remove unsupported SETUPTOOLS_SCM_PRETEND_VERSION
    if SCM_GLOBAL_PRETEND_ENV_VAR in os.environ:
        _remove_unsupported_env_var(SCM_GLOBAL_PRETEND_ENV_VAR)

    return pep440_version


def _git_describe_override_to_pep_440(override_value: str) -> str:
    """Process the OVERRIDE_GIT_DESCRIBE value."""
    describe_pattern = re.compile(
        r"""
        ^v(?P<tag>\d+\.\d+\.\d+(?:-post\d+|-rc\d+)?) # vX.Y.Z or vX.Y.Z-postN or vX.Y.Z-rcN
        (?:-(?P<distance>\d+))?                      # optional -N
        (?:-g(?P<hash>[0-9a-fA-F]+))?                # optional -g<sha>
        $""",
        re.VERBOSE,
    )

    match = describe_pattern.match(override_value)
    if not match:
        msg = f"Invalid git describe override: {override_value}"
        raise ValueError(msg)

    version, distance, commit_hash = match.groups()

    # Convert version format to PEP440 format (v1.3.1-post1 -> 1.3.1.post1)
    if "-post" in version:
        version = version.replace("-post", ".post")
    elif "-rc" in version:
        version = version.replace("-rc", "rc")

    # Bump version and format according to PEP440
    distance = int(distance or 0)
    pep440_version = _tag_to_version(str(version)) if distance == 0 else _bump_dev_version(str(version), distance)
    if commit_hash:
        pep440_version += f"+g{commit_hash.lower()}"

    return pep440_version


def _remove_unsupported_env_var(env_var: str) -> None:
    """Remove an unsupported environment variable with a warning."""
    print(f"[versioning] WARNING: We do not support {env_var}! Removing.")
    del os.environ[env_var]
