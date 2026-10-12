"""Release gates reject stale/mixed artifacts without contacting a registry."""

import hashlib
import io
import json
import runpy
import subprocess
import sys
import tarfile
import zipfile
from dataclasses import dataclass
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "check_release.py"
check_release = runpy.run_path(str(SCRIPT))["check_release"]
DIST_INFO = "qiao_mcp-0.5.0.dist-info"
SDIST_ROOT = "qiao_mcp-0.5.0"
README = "# Qiao-MCP\n\n桥梁模型工具。\n".encode()
PROJECT = b'''[project]
name = "qiao-mcp"
version = "0.5.0"
readme = "README.md"
requires-python = ">=3.11"
dependencies = ["mcp[cli]>=1.29,<2", "qtmodel>=2.6.3,!=2.9.0,<2.10"]

[project.scripts]
qiao-mcp = "qiao_mcp.server:main"
'''
METADATA = b'''Metadata-Version: 2.4
Name: qiao-mcp
Version: 0.5.0
Requires-Python: >=3.11
Requires-Dist: qtmodel!=2.9.0,<2.10,>=2.6.3
Requires-Dist: mcp[cli]<2,>=1.29
Description-Content-Type: text/markdown

''' + README


@dataclass
class ReleaseFixture:
    project: Path
    dist: Path
    wheel_files: dict[str, bytes]
    sdist_files: dict[str, bytes]

    @property
    def wheel(self):
        return self.dist / "qiao_mcp-0.5.0-py3-none-any.whl"

    @property
    def sdist(self):
        return self.dist / "qiao_mcp-0.5.0.tar.gz"

    def write_archives(self):
        with zipfile.ZipFile(self.wheel, "w") as archive:
            for name, content in self.wheel_files.items():
                archive.writestr(name, content)
        with tarfile.open(self.sdist, "w:gz") as archive:
            for name, content in self.sdist_files.items():
                member = tarfile.TarInfo(name)
                member.size = len(content)
                archive.addfile(member, io.BytesIO(content))

    def files(self, kind):
        return self.wheel_files if kind == "wheel" else self.sdist_files

    def check(self, tag="v0.5.0"):
        return check_release(self.dist, self.project, tag)

    def cli(self, *args):
        return subprocess.run(
            [sys.executable, str(SCRIPT), str(self.dist), "--project-dir", str(self.project), *map(str, args)],
            capture_output=True, text=True, check=False, timeout=15,
        )


@pytest.fixture
def release(tmp_path):
    project, dist = tmp_path / "project", tmp_path / "dist"
    project.mkdir()
    dist.mkdir()
    (project / "pyproject.toml").write_bytes(PROJECT)
    (project / "README.md").write_bytes(README)
    (project / "uv.lock").write_text('[[package]]\nname = "qiao-mcp"\nversion = "0.5.0"\n')
    (project / "server.json").write_text(json.dumps({
        "version": "0.5.0",
        "packages": [{"registryType": "pypi", "identifier": "qiao-mcp", "version": "0.5.0"}],
    }))
    modules = {"qiao_mcp/__init__.py": b"", "qiao_mcp/server.py": b"def main():\n    pass\n"}
    for name, content in modules.items():
        path = project / "src" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    result = ReleaseFixture(
        project, dist,
        {
            **modules,
            DIST_INFO + "/METADATA": METADATA,
            DIST_INFO + "/WHEEL": b"Wheel-Version: 1.0\nRoot-Is-Purelib: true\nTag: py3-none-any\n",
            DIST_INFO + "/entry_points.txt": b"[console_scripts]\nqiao-mcp = qiao_mcp.server:main\n",
        },
        {
            **{SDIST_ROOT + "/src/" + name: content for name, content in modules.items()},
            SDIST_ROOT + "/PKG-INFO": METADATA,
            SDIST_ROOT + "/README.md": README,
            SDIST_ROOT + "/pyproject.toml": PROJECT,
        },
    )
    result.write_archives()
    return result


def test_valid_release_reports_verified_version_and_artifact_hashes(release):
    # Requirement ordering differs between pyproject and both distributions.
    report = release.check()
    assert report == {
        "name": "qiao-mcp", "version": "0.5.0", "tag": "v0.5.0", "source_modules": 2,
        "artifacts": [
            {"filename": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
            for path in (release.wheel, release.sdist)
        ],
    }
    assert release.check(tag=None)["tag"] is None


@pytest.mark.parametrize("location", ["server", "server-package", "lock"])
def test_local_version_drift_is_rejected(release, location):
    if location == "lock":
        path = release.project / "uv.lock"
        path.write_text(path.read_text().replace("0.5.0", "0.4.0"))
    else:
        path = release.project / "server.json"
        data = json.loads(path.read_text())
        (data if location == "server" else data["packages"][0])["version"] = "0.4.0"
        path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="version differs"):
        release.check()


@pytest.mark.parametrize("tag", ["v0.4.0", "0.5.0", "v0.5.0rc1"])
def test_tag_must_match_the_exact_release(release, tag):
    with pytest.raises(ValueError, match="does not match project version"):
        release.check(tag)


@pytest.mark.parametrize("kind", ["wheel", "sdist"])
@pytest.mark.parametrize(("before", "after", "error"), [
    (b"Name: qiao-mcp", b"Name: other-package", "metadata name mismatch"),
    (b"Version: 0.5.0", b"Version: 0.4.0", "metadata version mismatch"),
    (b"Requires-Python: >=3.11", b"Requires-Python: >=3.12", "Python requirement differs"),
    (b"qtmodel!=2.9.0,<2.10,>=2.6.3", b"qtmodel>=2.6.3", "dependency metadata differs"),
    (README, b"# Stale documentation\n", "README differs"),
])
def test_packaged_metadata_drift_is_rejected(release, kind, before, after, error):
    path = DIST_INFO + "/METADATA" if kind == "wheel" else SDIST_ROOT + "/PKG-INFO"
    files = release.files(kind)
    files[path] = files[path].replace(before, after)
    release.write_archives()
    with pytest.raises(ValueError, match=error):
        release.check()


@pytest.mark.parametrize("kind", ["wheel", "sdist"])
@pytest.mark.parametrize("change", ["missing", "stale", "extra"])
def test_packaged_modules_must_match_checkout(release, kind, change):
    files = release.files(kind)
    prefix = "" if kind == "wheel" else SDIST_ROOT + "/src/"
    path = prefix + "qiao_mcp/server.py"
    if change == "missing":
        del files[path]
    elif change == "stale":
        files[path] = b"def outdated_main():\n    pass\n"
    else:
        files[prefix + "qiao_mcp/removed_module.py"] = b""
    release.write_archives()
    with pytest.raises(ValueError, match="Python modules differ"):
        release.check()


@pytest.mark.parametrize("filename", ["pyproject.toml", "README.md"])
def test_sdist_build_inputs_must_match_checkout(release, filename):
    release.sdist_files[SDIST_ROOT + "/" + filename] += b"\n# Stale\n"
    release.write_archives()
    with pytest.raises(ValueError, match="Source distribution .* differs from checkout"):
        release.check()


def test_wheel_entry_point_must_match_checkout(release):
    release.wheel_files[DIST_INFO + "/entry_points.txt"] = b"[console_scripts]\nqiao-mcp = qiao_mcp.old:main\n"
    release.write_archives()
    with pytest.raises(ValueError, match="console entry points differ"):
        release.check()


@pytest.mark.parametrize("kind", ["wheel", "sdist"])
def test_artifact_filename_must_match_its_version(release, kind):
    path = getattr(release, kind)
    path.rename(path.with_name(path.name.replace("0.5.0", "0.4.0")))
    with pytest.raises(ValueError, match="filename does not match"):
        release.check()


@pytest.mark.parametrize("change", ["missing-wheel", "extra-wheel", "extra-report"])
def test_incomplete_or_mixed_distribution_directory_is_rejected(release, change):
    if change == "missing-wheel":
        release.wheel.unlink()
    elif change == "extra-wheel":
        (release.dist / "qiao_mcp-0.4.0-py3-none-any.whl").write_bytes(release.wheel.read_bytes())
    else:
        (release.dist / "report.json").write_text("{}")
    with pytest.raises(ValueError, match="Expected exactly one|Unexpected files"):
        release.check()


def test_cli_writes_verified_report_and_appends_github_output(release, tmp_path):
    report_path, github_output = tmp_path / "report.json", tmp_path / "github-output"
    github_output.write_text("previous=value\n")
    result = release.cli("--tag", "v0.5.0", "--output", report_path, "--github-output", github_output)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == json.loads(report_path.read_text()) == release.check()
    assert github_output.read_text() == "previous=value\nversion=0.5.0\n"


def test_cli_failure_does_not_publish_a_version_output(release, tmp_path):
    report_path, github_output = tmp_path / "report.json", tmp_path / "github-output"
    result = release.cli("--tag", "v0.4.0", "--output", report_path, "--github-output", github_output)
    assert result.returncode != 0
    assert "does not match project version" in result.stderr
    assert not report_path.exists() and not github_output.exists()
    assert result.stdout == ""


@pytest.mark.parametrize("option", ["--output", "--github-output"])
def test_cli_does_not_add_reports_to_upload_directory(release, option):
    report_path = release.dist / "report.json"
    result = release.cli(option, report_path)
    assert result.returncode != 0
    assert "outside the distribution directory" in result.stderr
    assert not report_path.exists()
