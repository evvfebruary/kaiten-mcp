#!/usr/bin/env python3
"""Validate release versions shared by package and MCP Registry metadata."""

from __future__ import annotations

import argparse
import json
import re
import tomllib
from pathlib import Path
from typing import Any

SEMVER_RE = re.compile(
    r"^(?P<version>0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)"
    r"(?:-[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?"
    r"(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?$"
)
ROOT = Path(__file__).resolve().parents[1]


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path.name} must contain a JSON object")
    return value


def _project_version() -> str:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    version = pyproject.get("project", {}).get("version")
    if not isinstance(version, str):
        raise ValueError("pyproject.toml project.version must be a string")
    return version


def _registry_versions() -> tuple[str, str]:
    manifest = _load_json(ROOT / "server.json")
    server_version = manifest.get("version")
    packages = manifest.get("packages")
    if not isinstance(server_version, str):
        raise ValueError("server.json version must be a string")
    if not isinstance(packages, list):
        raise ValueError("server.json packages must be an array")

    pypi_packages = [
        package
        for package in packages
        if isinstance(package, dict) and package.get("registryType") == "pypi"
    ]
    if len(pypi_packages) != 1:
        raise ValueError("server.json must contain exactly one PyPI package")
    package_version = pypi_packages[0].get("version")
    if not isinstance(package_version, str):
        raise ValueError("server.json PyPI package version must be a string")
    return server_version, package_version


def validate(tag: str | None = None) -> str:
    """Return the validated release version."""
    project_version = _project_version()
    server_version, package_version = _registry_versions()
    versions = {
        "pyproject.toml": project_version,
        "server.json": server_version,
        "server.json PyPI package": package_version,
    }

    if len(set(versions.values())) != 1:
        details = ", ".join(f"{source}={version}" for source, version in versions.items())
        raise ValueError(f"release versions do not match: {details}")
    if not SEMVER_RE.fullmatch(project_version):
        raise ValueError(f"release version is not valid SemVer: {project_version}")

    if tag is not None:
        expected_tag = f"v{project_version}"
        if tag != expected_tag:
            raise ValueError(f"release tag {tag!r} does not match {expected_tag!r}")
    return project_version


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tag", help="Optional release tag, expected in vX.Y.Z form")
    args = parser.parse_args()
    try:
        version = validate(args.tag)
    except (OSError, ValueError, json.JSONDecodeError, tomllib.TOMLDecodeError) as exc:
        parser.exit(1, f"release metadata error: {exc}\n")
    print(f"Release metadata OK: {version}")


if __name__ == "__main__":
    main()
