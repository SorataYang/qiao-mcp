"""Verify a local release against the checkout before uploading any distribution.

Run with the project's development dependencies:
    uv run python scripts/check_release.py dist --tag v0.5.0
This checks artifacts only; it does not create a tag or publish anything.
"""

import argparse
import configparser
import hashlib
import json
import tarfile
import tomllib
import zipfile
from email.parser import Parser
from pathlib import Path

from packaging.requirements import Requirement
from packaging.specifiers import SpecifierSet
from packaging.utils import canonicalize_name
from packaging.version import Version


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def requirements(values: list[str]) -> set[str]:
    return {str(Requirement(value)) for value in values}


def check_release(dist: Path, project_dir: Path, tag: str | None = None) -> dict:
    """Reject version drift, stale source payloads and mixed distributions."""
    project_file = project_dir / "pyproject.toml"
    project = tomllib.loads(project_file.read_text(encoding="utf-8"))["project"]
    name, version = project["name"], project["version"]
    require(version == str(Version(version)), "Project version must use canonical PEP 440 form")
    if tag is not None:
        require(tag == f"v{version}", f"Tag {tag!r} does not match project version v{version}")

    server = json.loads((project_dir / "server.json").read_text(encoding="utf-8"))
    require(server["version"] == version, "server.json version differs from pyproject.toml")
    packages = server["packages"]
    require(bool(packages), "server.json must declare a package")
    for package in packages:
        require(package["version"] == version, "server.json package version differs from pyproject.toml")
    require(
        any(package["registryType"] == "pypi" and package["identifier"] == name for package in packages),
        "server.json does not declare the project's PyPI package",
    )
    locked = tomllib.loads((project_dir / "uv.lock").read_text(encoding="utf-8"))
    local = [package for package in locked["package"] if package["name"] == name]
    require(len(local) == 1 and local[0]["version"] == version, "uv.lock project version differs from pyproject.toml")

    wheels, sdists = sorted(dist.glob("*.whl")), sorted(dist.glob("*.tar.gz"))
    require(len(wheels) == len(sdists) == 1, "Expected exactly one wheel and one source distribution")
    wheel, sdist = wheels[0], sdists[0]
    files = {file for file in dist.iterdir() if file.is_file() and not file.name.startswith(".")}
    require(files == {wheel, sdist}, "Unexpected files in distribution directory")
    normalized_name = canonicalize_name(name).replace("-", "_")
    require(wheel.name.startswith(f"{normalized_name}-{version}-"), "Wheel filename does not match project version/name")
    require(sdist.name == f"{normalized_name}-{version}.tar.gz", "Source distribution filename does not match project version/name")

    readme_path = project["readme"]
    require(isinstance(readme_path, str), "Expected a README file path in project metadata")
    readme = (project_dir / readme_path).read_bytes()
    source_root = project_dir / "src"
    modules = {
        file.relative_to(source_root).as_posix(): file.read_bytes()
        for file in (source_root / normalized_name).rglob("*.py")
    }
    require(bool(modules), "No project Python modules found")

    def check_metadata(raw: bytes, kind: str) -> None:
        metadata = Parser().parsestr(raw.decode("utf-8"))
        require(canonicalize_name(metadata["Name"]) == canonicalize_name(name), f"{kind} metadata name mismatch")
        require(metadata["Version"] == version, f"{kind} metadata version mismatch")
        require(
            SpecifierSet(metadata.get("Requires-Python", "")) == SpecifierSet(project.get("requires-python", "")),
            f"{kind} Python requirement differs from pyproject.toml",
        )
        require(
            requirements(metadata.get_all("Requires-Dist", [])) == requirements(project.get("dependencies", [])),
            f"{kind} dependency metadata differs from pyproject.toml",
        )
        require(metadata.get_payload().rstrip() == readme.decode("utf-8").rstrip(), f"{kind} README differs from checkout")

    with zipfile.ZipFile(wheel) as archive:
        metadata_paths = [path for path in archive.namelist() if path.endswith(".dist-info/METADATA")]
        require(len(metadata_paths) == 1, "Wheel must contain exactly one distribution metadata record")
        check_metadata(archive.read(metadata_paths[0]), "Wheel")
        shipped = {
            path: archive.read(path) for path in archive.namelist()
            if path.startswith(normalized_name + "/") and path.endswith(".py")
        }
        require(shipped == modules, "Wheel Python modules differ from checkout")
        entry_points = configparser.ConfigParser(interpolation=None)
        entry_points.optionxform = str
        entry_points.read_string(archive.read(metadata_paths[0].removesuffix("METADATA") + "entry_points.txt").decode("utf-8"))
        require(dict(entry_points["console_scripts"]) == project.get("scripts", {}), "Wheel console entry points differ from pyproject.toml")

    with tarfile.open(sdist) as archive:
        metadata_paths = [member.name for member in archive.getmembers() if member.isfile() and member.name.endswith("/PKG-INFO")]
        require(len(metadata_paths) == 1, "Source distribution must contain exactly one metadata record")
        root = metadata_paths[0].removesuffix("/PKG-INFO")

        def read(path: str) -> bytes:
            stream = archive.extractfile(path)
            require(stream is not None, f"Missing source distribution file: {path}")
            return stream.read()

        check_metadata(read(metadata_paths[0]), "Source distribution")
        require(read(root + "/pyproject.toml") == project_file.read_bytes(), "Source distribution pyproject.toml differs from checkout")
        require(read(root + "/" + readme_path) == readme, "Source distribution README differs from checkout")
        prefix = root + "/src/"
        shipped = {
            member.name.removeprefix(prefix): read(member.name)
            for member in archive.getmembers()
            if member.isfile() and member.name.startswith(prefix + normalized_name + "/") and member.name.endswith(".py")
        }
        require(shipped == modules, "Source distribution Python modules differ from checkout")

    return {
        "name": name, "version": version, "tag": tag, "source_modules": len(modules),
        "artifacts": [
            {"filename": file.name, "sha256": hashlib.sha256(file.read_bytes()).hexdigest()}
            for file in (wheel, sdist)
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dist", type=Path)
    parser.add_argument("--project-dir", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--tag", help="Require this proposed/existing tag to match the package version")
    parser.add_argument("--output", type=Path, help="Write a JSON report outside the distribution directory")
    parser.add_argument("--github-output", type=Path, help="Append the verified version to a GitHub Actions output file")
    args = parser.parse_args()
    try:
        for output in (args.output, args.github_output):
            if output:
                require(not output.resolve().is_relative_to(args.dist.resolve()), "Write reports outside the distribution directory")
        report = check_release(args.dist, args.project_dir, args.tag)
        serialized = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
        if args.output:
            args.output.write_text(serialized, encoding="utf-8")
        if args.github_output:
            with args.github_output.open("a", encoding="utf-8") as output:
                output.write(f"version={report['version']}\n")
    except (KeyError, OSError, ValueError, zipfile.BadZipFile, tarfile.TarError) as exc:
        parser.error(str(exc))
    print(serialized, end="")


if __name__ == "__main__":
    main()
