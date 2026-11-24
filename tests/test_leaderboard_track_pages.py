"""Per-track leaderboard pages, stable anchors and entry history (P13-09, gap 80).

These tests read repository files and build into temporary folders. They publish nothing.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from fidetype.benchmark import entry_history as H
from fidetype.benchmark import leaderboard as LB

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "benchmark/site"
RESULTS = [ROOT / "benchmark/results/v0.1", ROOT / "benchmark/results/v0.2"]


def _norm(text: str) -> str:
    return text.replace("\r\n", "\n")


def test_anchors_are_derived_from_the_slug_and_the_card_name_only():
    assert LB.track_anchor("b2t25-t15") == "track-b2t25-t15"
    assert LB.track_page("toronto-semg") == "tracks/toronto-semg.html"
    assert LB.entry_anchor("b2t24-t12__t12v2__guard.json") == "e-b2t24-t12__t12v2__guard"
    assert LB.entry_anchor("A b.json") == "e-a-b"


def test_committed_track_pages_cover_every_track_and_entry():
    lb = json.loads((SITE / "leaderboard.json").read_text(encoding="utf-8"))
    pages = sorted(p.name for p in (SITE / "tracks").glob("*.html"))
    assert pages == sorted(Path(v["page"]).name for v in lb["track_pages"].values())
    main = (SITE / "index.html").read_text(encoding="utf-8")
    for slug, rows in lb["tracks"].items():
        tp = lb["track_pages"][slug]
        # Main page: the track heading has a stable id and links to the track page.
        assert f'<h3 id="{tp["anchor"]}">' in main, slug
        assert f'href="{tp["page"]}"' in main, slug
        page = (SITE / tp["page"]).read_text(encoding="utf-8")
        assert f'href="../index.html#{tp["anchor"]}"' in page  # back link to the track heading
        for anchor in ("entries", "history", "details"):
            assert f'id="{anchor}"' in page, (slug, anchor)
        for r in rows:
            assert f'<section class="entry" id="{r["anchor"]}">' in page, (slug, r["file"])
            assert r["link"] == f'{tp["page"]}#{r["anchor"]}'
            assert f'href="{tp["page"]}#{r["anchor"]}"' in main  # main page links each entry


def test_research_only_tracks_stay_in_their_own_section():
    lb = json.loads((SITE / "leaderboard.json").read_text(encoding="utf-8"))
    main = (SITE / "index.html").read_text(encoding="utf-8")
    ro_part = main.split('<section id="research-only"', 1)[1].split("</section>", 1)[0]
    for slug, tp in lb["track_pages"].items():
        inside = f'id="{tp["anchor"]}"' in ro_part
        assert inside == tp["research_only"], slug
        if tp["research_only"]:
            assert "RESEARCH ONLY" in (SITE / tp["page"]).read_text(encoding="utf-8")
    assert {s for s, t in lb["track_pages"].items() if t["research_only"]} >= {"spanishbcbl-meg", "emg2qwerty"}
    md = (SITE / "leaderboard.md").read_text(encoding="utf-8")
    assert '<a id="research-only"></a>' in md and '<a id="track-b2t25-t15"></a>' in md


def test_safe_wpm_v02_is_the_dated_headline_on_every_page():
    # safe-wpm/0.2 was adopted on 2026-11-22: it is the headline column with a dated note; v0.1 is the second column.
    for p in [*(SITE / "tracks").glob("*.html"), SITE / "index.html"]:
        text = p.read_text(encoding="utf-8")
        assert "ADOPTED on that date" in text and "since 2026-11-22" in text, p.name
        assert "Safe WPM v0.2 @ alpha" in text and "Safe WPM v0.1 @ alpha" in text, p.name
        assert "PROPOSED, NOT ADOPTED" not in text, p.name
    md = (SITE / "leaderboard.md").read_text(encoding="utf-8")
    assert "| Safe WPM v0.2 @ alpha | Safe WPM v0.1 @ alpha |" in md


def test_every_v01_number_keeps_its_value_and_label():
    # The switch adds a v0.2 block; it never changes or re-labels a v0.1 block (git HEAD~ is not needed: the
    # v0.1 block of each card is the one the leaderboard shows in the v0.1 column).
    lb = json.loads((SITE / "leaderboard.json").read_text(encoding="utf-8"))
    rows = {r["file"]: r for t in lb["tracks"].values() for r in t}
    for f in RESULTS:
        for p in f.glob("*.json"):
            card = json.loads(p.read_text(encoding="utf-8"))
            v1 = card.get("safe_wpm")
            if not v1:
                continue
            assert v1["definition"] == "safe-wpm/0.1", p.name
            r = rows[p.name]
            assert r["safe_wpm_v01"] == v1["value"] and r["safe_wpm_v01_status"] == v1["status"], p.name
            v2 = card.get("safe_wpm_v02")
            if v2 is None:
                assert r["safe_wpm"] is None and r["safe_wpm_s"].startswith("v0.1 only"), p.name
                continue
            assert v2["definition"] == "safe-wpm/0.2" and v2["adopted_headline"] is True, p.name
            assert r["safe_wpm"] == v2["value"] and r["safe_wpm_definition"] == "safe-wpm/0.2", p.name
            # Same certification, and the reading cost can only lower the value.
            assert v2["status"] == v1["status"], p.name
            if v1["value"] is not None:
                assert v2["value"] <= v1["value"] + 1e-12, p.name
                assert v2["reading_cost"]["wpm_without_reading"] == pytest.approx(v1["value"]), p.name


def test_committed_pages_are_generated_from_the_cards_and_the_history_file(tmp_path):
    # Regenerate from the committed cards + committed history.json: the pages must be identical,
    # so no number on them is typed by hand.
    hist = json.loads((SITE / "history.json").read_text(encoding="utf-8"))
    LB.build(RESULTS, tmp_path, history=hist)
    for rel in ["index.html", "leaderboard.md", "leaderboard.json",
                *[f"tracks/{p.name}" for p in (SITE / "tracks").glob("*.html")]]:
        assert _norm((tmp_path / rel).read_text(encoding="utf-8")) == _norm((SITE / rel).read_text(encoding="utf-8")), rel
    # The history lists every committed card.
    cards = sorted(p.name for f in RESULTS for p in f.glob("*.json"))
    assert sorted(hist["cards"]) == cards
    assert hist["schema"] == H.HISTORY_SCHEMA


def test_committed_history_has_dates_versions_and_rerun_levels():
    hist = json.loads((SITE / "history.json").read_text(encoding="utf-8"))
    assert hist["available"] is True
    for name, versions in hist["cards"].items():
        assert versions, name
        assert versions[-1]["action"] == "added", name
        for v in versions:
            assert v["commit"] is None or re.fullmatch(r"[0-9a-f]{7}", v["commit"]), name
            assert v["date"] is None or re.fullmatch(r"\d{4}-\d{2}-\d{2}", v["date"]), name
            assert re.fullmatch(r"tracks-v\d+\.\d+", v["split_version"]), name
            assert v["rerun_level"] in ("no", "rescore", "replay", "full"), name
            assert v["scorer_version"], name


def test_track_pages_have_no_external_resources():
    for p in [SITE / "index.html", *(SITE / "tracks").glob("*.html")]:
        html = p.read_text(encoding="utf-8")
        assert "<script" not in html, p.name
        assert not re.search(r'<(img|iframe|link)[^>]+(src|href)="(https?:)?//', html), p.name
        assert 'name="viewport"' in html and "prefers-color-scheme: dark" in html, p.name


def _fake_runner(files: dict[str, list[tuple[str, str, str, str | None]]], root: Path):
    """A git stand-in: files maps a repo path to [(hash, date, subject, content)] newest first."""
    def run(args, cwd):
        if args[:2] == ["rev-parse", "--show-toplevel"]:
            return str(root) + "\n"
        if args[:2] == ["rev-parse", "--is-shallow-repository"]:
            return "false\n"
        if args[0] == "log" and "--diff-filter=D" in args:
            return ""
        if args[0] == "ls-tree":
            return ""
        if args[0] == "log" and args[2].startswith("--format=%H"):
            rel = args[-1]
            return "".join(f"{h}\t{d}\t{s}\n" for h, d, s, _ in files.get(rel, []))
        if args[0] == "log":
            return "".join(f"{h}\n" for rel in files for h, _, _, _ in files[rel])
        if args[0] == "show":
            h, rel = args[1].split(":", 1)
            for hh, _, _, c in files.get(rel, []):
                if hh == h:
                    return c
            return None
        raise AssertionError(args)
    return run


def _card(**kw):
    c = {"schema": "fidetype.benchmark.result/0.2", "benchmark_version": "0.2", "entry_id": "x", "track": "kt-semg",
         "scorer_version": "0.2", "metrics": {"ewpm": {"value": 1.5}},
         "safe_wpm": {"definition": "safe-wpm/0.1", "value": 1.0, "status": "certified"}}
    c.update(kw)
    return c


def test_card_history_with_a_fake_git(tmp_path):
    res = tmp_path / "benchmark/results/v0.2"
    res.mkdir(parents=True)
    old, new = _card(), _card(rerun={"schema": "fidetype.hub.recipe/0.1", "level": "rescore",
                                     "track": {"split_version": "tracks-v0.2", "digest": "ab" * 32},
                                     "scorer": {"scorer_version": "0.2", "metrics": {"safe_wpm": "safe-wpm/0.1"}}})
    rel = "benchmark/results/v0.2/kt-semg__a__b.json"
    (tmp_path / rel).write_text(json.dumps(new | {"notes": ["edited"]}), encoding="utf-8")
    files = {rel: [("b" * 40, "2026-11-18", "add rerun", json.dumps(new)), ("a" * 40, "2026-11-16", "add", json.dumps(old))]}
    hist = H.build_history([res], run=_fake_runner(files, tmp_path.resolve()))
    v = hist["cards"]["kt-semg__a__b.json"]
    assert [x["action"] for x in v] == ["changed", "changed", "added"]
    assert v[0]["commit"] is None and v[0]["changed"] == ["notes"]  # a row of the commit that holds the page
    assert v[0]["subject"] == H.PENDING
    assert v[1]["commit"] == "bbbbbbb" and v[1]["changed"] == ["rerun"] and v[1]["rerun_level"] == "rescore"
    assert v[2]["date"] == "2026-11-16" and v[2]["rerun_level"] == "no" and v[2]["split_version"] == "tracks-v0.2"
    assert v[2]["metric_versions"] == {"safe_wpm": "safe-wpm/0.1"}
    ev = H.track_events(hist, {"kt-semg__a__b.json": "e-x"}, "kt-semg")
    assert [e["seq"] for e in ev] == [-1, 0, 1]


def test_no_git_means_no_history_and_the_page_says_so(tmp_path):
    hist = H.build_history([tmp_path], run=lambda args, cwd: None)
    assert hist["available"] is False and hist["cards"] == {}
    res = tmp_path / "res"
    res.mkdir()
    (res / "kt-semg__a__b.json").write_text(json.dumps(_card()), encoding="utf-8")
    LB.build([res], tmp_path / "site", history=hist)
    page = (tmp_path / "site/tracks/kt-semg.html").read_text(encoding="utf-8")
    assert "Entry history not available" in page and 'id="e-kt-semg__a__b"' in page


@pytest.mark.skipif(shutil.which("git") is None, reason="git not installed")
def test_card_history_with_a_real_git_repository(tmp_path):
    def git(*a):
        subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@example.org", "-c", "commit.gpgsign=false",
                        *a], cwd=tmp_path, check=True, capture_output=True)
    git("init", "-q")
    res = tmp_path / "res"
    res.mkdir()
    (res / "kt-semg__a__b.json").write_text(json.dumps(_card()), encoding="utf-8")
    (res / "kt-semg__c__d.json").write_text(json.dumps(_card(entry_id="gone")), encoding="utf-8")
    git("add", "-A")
    git("commit", "-q", "-m", "add two cards")
    (res / "kt-semg__a__b.json").write_text(json.dumps(_card(metrics={"ewpm": {"value": 2.5}})), encoding="utf-8")
    (res / "kt-semg__c__d.json").unlink()
    git("add", "-A")
    git("commit", "-q", "-m", "change one, remove one")
    hist = H.build_history([res])
    assert hist["available"] is True
    v = hist["cards"]["kt-semg__a__b.json"]
    assert [x["action"] for x in v] == ["changed", "added"] and v[0]["changed"] == ["metrics"]
    assert v[0]["ewpm"] == 2.5 and v[1]["ewpm"] == 1.5
    assert [(r["file"], r["action"], r["entry_id"]) for r in hist["removed"]] == [("kt-semg__c__d.json", "removed", "gone")]
    LB.build([res], tmp_path / "site", history=hist)
    page = (tmp_path / "site/tracks/kt-semg.html").read_text(encoding="utf-8")
    assert "(removed)" in page and "changed: metrics" in page


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_site_copies_the_track_pages_and_links_them(tmp_path):
    out = tmp_path / "site"
    r = subprocess.run(["node", str(ROOT / "tools/site/build.js"), "--out", str(out)],
                       capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "local links: all OK" in r.stdout
    lb = json.loads((SITE / "leaderboard.json").read_text(encoding="utf-8"))
    overview = (out / "benchmark/index.html").read_text(encoding="utf-8")
    for slug, tp in lb["track_pages"].items():
        page = out / "benchmark" / tp["page"]
        assert page.is_file(), slug
        html = page.read_text(encoding="utf-8")
        # On the site the leaderboard is benchmark/leaderboard.html, so the back link names it.
        assert f'href="../leaderboard.html#{tp["anchor"]}"' in html and 'href="../index.html#' not in html
        assert "ADOPTED" in html and "PROPOSED, NOT ADOPTED" not in html  # the dated v0.2 note
        assert f'href="{tp["page"]}"' in overview, slug  # the overview links each track row
    assert (out / "benchmark/history.json").is_file()


# --- P13-12: same-commit history rows and the freshness check ---------------------------------------------


def _git(repo: Path, *a: str) -> str:
    r = subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@example.org", "-c", "commit.gpgsign=false",
                        "-c", "core.autocrlf=false", *a], cwd=repo, check=True, capture_output=True, text=True)
    return r.stdout.strip()


@pytest.mark.skipif(shutil.which("git") is None, reason="git not installed")
def test_cards_committed_with_their_pages_stay_fresh(tmp_path):
    repo = tmp_path
    _git(repo, "init", "-q")
    res, site = repo / "res", repo / "site"
    res.mkdir()
    (res / "kt-semg__a__b.json").write_text(json.dumps(_card()), encoding="utf-8")
    (res / "kt-semg__c__d.json").write_text(json.dumps(_card(entry_id="gone")), encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "add two cards")
    # 1. Change one card, remove one, regenerate the pages and commit all in ONE commit.
    (res / "kt-semg__a__b.json").write_text(json.dumps(_card(metrics={"ewpm": {"value": 2.5}})), encoding="utf-8")
    (res / "kt-semg__c__d.json").unlink()
    info = LB.build([res], site)
    assert info["rows_in_this_commit"] == 2  # the changed card and the removed card
    page = (site / "tracks/kt-semg.html").read_text(encoding="utf-8")
    assert "this commit" in page and "with this page" in page and "working tree" not in page
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "change one card, remove one, regenerate the pages")
    held = _git(repo, "rev-parse", "--short=7", "HEAD")
    assert LB.check([res], site) == []  # the committed pages are fresh after the commit
    assert held not in (site / "tracks/kt-semg.html").read_text(encoding="utf-8")
    # 2. A later commit that does not touch cards or pages: still fresh; a rebuild changes nothing.
    (repo / "README").write_text("x", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "other file")
    assert LB.check([res], site) == []
    before = {p.name: p.read_bytes() for p in site.rglob("*.*")}
    LB.build([res], site)
    assert {p.name: p.read_bytes() for p in site.rglob("*.*")} == before
    # 3. A card commit without the pages: the check fails until the pages are regenerated and committed.
    (res / "kt-semg__a__b.json").write_text(json.dumps(_card(metrics={"ewpm": {"value": 3.5}})), encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "change the card again, no pages")
    card_commit = _git(repo, "rev-parse", "--short=7", "HEAD")
    errs = LB.check([res], site)
    assert errs and any("history.json" in e for e in errs)
    LB.build([res], site)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "regenerate the pages")
    assert LB.check([res], site) == []
    hist = json.loads((site / "history.json").read_text(encoding="utf-8"))
    v = hist["cards"]["kt-semg__a__b.json"]
    assert [x["commit"] for x in v][0] == card_commit and all(x["commit"] for x in v)  # no row without a commit
    assert v[0]["ewpm"] == 3.5 and v[1]["ewpm"] == 2.5 and v[2]["ewpm"] == 1.5


def test_check_needs_git_history(tmp_path):
    res = tmp_path / "res"
    res.mkdir()
    (res / "kt-semg__a__b.json").write_text(json.dumps(_card()), encoding="utf-8")
    LB.build([res], tmp_path / "site", history={"schema": H.HISTORY_SCHEMA, "available": False, "note": "x",
                                                 "cards": {}, "removed": []})
    errs = LB.check([res], tmp_path / "site")
    assert any("full-history checkout" in e for e in errs)


@pytest.mark.skipif(H.repo_root(ROOT) is None, reason="needs a full-history git checkout (CI: the leaderboard job)")
def test_committed_site_is_fresh():
    """What the CI job checks: the committed outputs equal a regeneration from the cards and git."""
    if subprocess.run(["git", "diff", "--quiet", "HEAD", "--", "benchmark/results", "benchmark/site"],
                      cwd=ROOT).returncode != 0:
        pytest.skip("cards or pages have uncommitted changes")
    assert LB.check(RESULTS, SITE) == []
