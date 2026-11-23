"""Registry metadata of the three SDK packages and the static site build (publishing prep, P2-06 / P8-01).

These tests read files only. They publish nothing. See docs/publishing-checklist.md.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
REPO = "https://github.com/zhangzibo/fidetype"
AUTHOR = "Zibo Zhang"
EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}")


def _pyproject() -> dict:
    return tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))


def _cargo() -> dict:
    return tomllib.loads((ROOT / "sdk/rust/Cargo.toml").read_text(encoding="utf-8"))


def _package_json() -> dict:
    return json.loads((ROOT / "sdk/typescript/package.json").read_text(encoding="utf-8"))


def test_author_name_in_every_manifest():
    assert _pyproject()["project"]["authors"] == [{"name": AUTHOR}]
    assert _cargo()["package"]["authors"] == [AUTHOR]
    assert _package_json()["author"] == AUTHOR
    cff = (ROOT / "CITATION.cff").read_text(encoding="utf-8")
    assert "given-names: Zibo" in cff and "family-names: Zhang" in cff


def test_no_email_in_any_manifest():
    # The maintainer's e-mail address must never be in the package metadata.
    proj = _pyproject()["project"]
    assert "maintainers" not in proj
    assert all(set(a) == {"name"} for a in proj["authors"])
    for rel in ["pyproject.toml", "sdk/rust/Cargo.toml", "sdk/typescript/package.json", "CITATION.cff"]:
        text = (ROOT / rel).read_text(encoding="utf-8")
        assert not EMAIL.search(text), f"e-mail address in {rel}"


def test_homepage_and_repository_point_at_the_github_repo():
    urls = _pyproject()["project"]["urls"]
    assert urls["Homepage"] == REPO and urls["Repository"] == REPO
    pkg = _cargo()["package"]
    assert pkg["repository"] == REPO and pkg["homepage"] == REPO
    pj = _package_json()
    assert pj["homepage"].startswith(REPO)
    assert pj["repository"]["url"] == f"git+{REPO}.git" and pj["repository"]["directory"] == "sdk/typescript"


def test_licence_is_apache_and_files_ship():
    assert _pyproject()["project"]["license"] == "Apache-2.0"
    assert _cargo()["package"]["license"] == "Apache-2.0"
    assert _package_json()["license"] == "Apache-2.0"
    for rel in ["LICENSE", "sdk/rust/LICENSE", "sdk/typescript/LICENSE"]:
        assert "Apache License" in (ROOT / rel).read_text(encoding="utf-8")[:300], rel
    assert "/LICENSE" in _cargo()["package"]["include"]
    assert "LICENSE" in _package_json()["files"]


@pytest.mark.parametrize("rel", ["sdk/typescript/README.md", "sdk/rust/README.md"])
def test_sdk_readmes_use_absolute_links(rel):
    # npmjs.com and crates.io show the README out of the repository; relative links break there.
    text = (ROOT / rel).read_text(encoding="utf-8")
    relative = re.findall(r"\]\((?!https?://|#|mailto:)([^)]+)\)", text)
    assert not relative, relative


def test_python_version_matches_citation():
    init = (ROOT / "src/fidetype/__init__.py").read_text(encoding="utf-8")
    version = re.search(r'__version__ = "([^"]+)"', init)[1]
    cff = (ROOT / "CITATION.cff").read_text(encoding="utf-8")
    assert re.search(r"^version: (\S+)$", cff, re.M)[1] == version


def test_typescript_version_matches_sdk_constant():
    src = (ROOT / "sdk/typescript/src/index.ts").read_text(encoding="utf-8")
    assert re.search(r'SDK_VERSION = "([^"]+)"', src)[1] == _package_json()["version"]


def test_changelogs_have_an_unreleased_section():
    for rel in ["CHANGELOG.md", "sdk/typescript/CHANGELOG.md", "sdk/rust/CHANGELOG.md"]:
        assert "## [Unreleased]" in (ROOT / rel).read_text(encoding="utf-8"), rel


def _on_block(name):
    wf = (ROOT / ".github/workflows" / name).read_text(encoding="utf-8")
    return wf.split("\non:", 1)[1].split("\npermissions:", 1)[0]


def test_release_workflow_never_runs_by_itself():
    # Package uploads run only when the maintainer clicks "Run workflow".
    on_block = _on_block("release.yml")
    assert "workflow_dispatch" in on_block
    for trigger in ("push", "pull_request", "schedule", "release:", "workflow_run", "workflow_call"):
        assert trigger not in on_block, trigger


def test_pages_workflow_deploys_only_from_main():
    # Maintainer decision 2026-11-21: the site deploys on every push to main, and by hand.
    # Never from a pull request, a fork, a schedule or another workflow.
    on_block = _on_block("pages.yml")
    assert "workflow_dispatch" in on_block
    assert "push:" in on_block and "branches: [main]" in on_block
    for trigger in ("pull_request", "schedule", "release:", "workflow_run", "workflow_call", "tags:"):
        assert trigger not in on_block, trigger


def test_release_publish_steps_are_gated():
    wf = (ROOT / ".github/workflows/release.yml").read_text(encoding="utf-8")
    # Each upload runs only for an explicit publish target and in a protected environment.
    assert "environment: release-pypi" in wf
    assert "'release-npm'" in wf and "'release-crates'" in wf
    assert wf.count("if: inputs.target == 'publish'") >= 3  # npm publish, crates auth, crates publish
    assert "inputs.target == 'testpypi' || inputs.target == 'pypi'" in wf


def test_site_build_output_is_git_ignored():
    assert "/_site/" in (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_site_builds_with_no_broken_local_links(tmp_path):
    out = tmp_path / "site"
    r = subprocess.run(["node", str(ROOT / "tools/site/build.js"), "--out", str(out)],
                       capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "local links: all OK" in r.stdout
    for rel in ["index.html", ".nojekyll", "assets/site.css", "benchmark/index.html", "benchmark/leaderboard.html",
                "benchmark/guide.html", "hub/index.html", "hub/datasets-0.1.json", "conformance/index.html",
                "conformance/certified.json", "docs/index.html", "docs/trust-guarantee.html", "docs/collector.html",
                "docs/live-decode.html", "docs/conformance.html", "spec/index.html", "demo/index.html",
                "diagrams/index.html", "diagrams/viewer-static.min.js", "diagrams/drawio-LICENSE.txt",
                "progress/index.html"]:
        assert (out / rel).is_file(), rel
    # Landing page: generated from README.md (intro, install, quick start, status, research status).
    landing = (out / "index.html").read_text(encoding="utf-8")
    assert "types text only when it is confident" in landing and 'id="quick-start"' in landing
    assert 'id="status"' in landing and 'id="research-status"' in landing
    assert (out / "research.html").is_file()
    # Markdown pages keep GitHub heading ids, so deep links work on the site.
    assert 'id="42-rules"' in (out / "docs/hub-design.html").read_text(encoding="utf-8")
    # The metric status of the v0.2 page (adopted 2026-11-22) is shown on the benchmark page.
    assert "Adopted" in (out / "docs/safe-wpm-v0.2-proposal.html").read_text(encoding="utf-8")
    assert "ADOPTED" in (out / "benchmark/index.html").read_text(encoding="utf-8")
    # The certified list and the hub registry are generated from their JSON files.
    certified = json.loads((ROOT / "spec/conformance/certified.json").read_text(encoding="utf-8"))
    conf = (out / "conformance/index.html").read_text(encoding="utf-8")
    assert all(e["id"] in conf for e in certified["entries"])
    reg = json.loads((ROOT / "src/fidetype/benchmark/hub/datasets-0.1.json").read_text(encoding="utf-8"))
    hub = (out / "hub/index.html").read_text(encoding="utf-8")
    assert all(d["id"] in hub for d in reg["datasets"])
    # Static: no external scripts, stylesheets, images or frames (no trackers).
    for f in out.rglob("*.html"):
        html = f.read_text(encoding="utf-8")
        assert not re.search(r'<(script|img|iframe)[^>]+src="(https?:)?//', html), f
        assert not re.search(r'<link[^>]+href="(https?:)?//', html), f
    diagrams = (out / "diagrams/index.html").read_text(encoding="utf-8")
    assert "../../tools/drawio" not in diagrams
    assert not re.search(r'href="\.\./[^"]+\.md"', diagrams)  # wiki links now point at GitHub
    assert f'href="{REPO}/blob/main/wiki/' in diagrams
    # Only the expected kinds of files; no data, recordings or PDFs.
    allowed = {".html", ".json", ".md", ".js", ".txt", ".css", ".png", ""}
    for f in out.rglob("*"):
        if f.is_file():
            assert f.suffix in allowed, f
    for f in out.rglob("*.html"):
        for m in EMAIL.finditer(f.read_text(encoding="utf-8")):
            assert m.group(0).endswith(("@example.org", "@example.com")), (f, m.group(0))


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_site_link_check_finds_a_broken_link(tmp_path):
    out = tmp_path / "site"
    subprocess.run(["node", str(ROOT / "tools/site/build.js"), "--out", str(out)], check=True,
                   capture_output=True, timeout=120)
    (out / "index.html").write_text('<a href="nothing-here/">x</a><a href="#nope">y</a>', encoding="utf-8")
    r = subprocess.run(["node", str(ROOT / "tools/site/build.js"), "--out", str(out), "--check-only"],
                       capture_output=True, text=True, timeout=120)
    assert r.returncode == 1
    assert "nothing-here/" in r.stderr and "#nope" in r.stderr
