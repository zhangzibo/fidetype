"""Build the static leaderboard from a folder of result JSON files.

    python -m fidetype.benchmark leaderboard --results benchmark/results/v0.1 benchmark/results/v0.2 --out benchmark/site

Writes ``leaderboard.json`` (all rows), ``leaderboard.md`` (Markdown
tables, one per track), ``index.html`` (one self-contained page, no
scripts, no network), ``tracks/<track>.html`` (one page per track with its
entry history, P13-09) and ``history.json`` (the entry history from git,
see ``fidetype.benchmark.entry_history``). The output folder can be served
as is (for example by GitHub Pages later). Never edit the outputs by hand.

Entry history and freshness (P13-12): the history is read from git up to the
parent of the commit that holds the pages (``entry_history.site_base``), so a
card committed together with its regenerated pages gets a row "in the commit
that holds this page" that stays correct after the commit. ``build`` first
tries that base; if the result differs from the committed pages, the pages will
go into a new commit on top of ``HEAD``, so it builds with base ``HEAD``. CI
runs ``python -m fidetype.benchmark.leaderboard --check`` (full-history
checkout): it regenerates the outputs and fails on any difference.

Stable anchors (P13-09): ``index.html#track-<track>`` (track heading),
``tracks/<track>.html`` (track page), ``tracks/<track>.html#e-<card>``
(one entry; ``<card>`` is the card file name without ``.json``) and
``tracks/<track>.html#history``.
"""

from __future__ import annotations

import html
import json
import math
import re
from os import PathLike
from pathlib import Path
from typing import Any

from fidetype.benchmark import tracks as TR2
from fidetype.benchmark.entry_history import build_history, git_runner, repo_root, site_base, track_events
from fidetype.benchmark.hub.recipe import rerun_level
from fidetype.benchmark.registry import BENCHMARK_VERSION, DATASETS, TRACKS
from fidetype.benchmark.scoring import RESULT_SCHEMA

RESULT_SCHEMAS = (RESULT_SCHEMA, "fidetype.benchmark.result/0.2")


def track_anchor(slug: str) -> str:
    """The id of a track heading on the main page (stable: derived from the track slug only)."""
    return "track-" + re.sub(r"[^a-z0-9-]+", "-", str(slug).lower()).strip("-")


def track_page(slug: str) -> str:
    """The track page, relative to the leaderboard folder."""
    return f"tracks/{re.sub(r'[^a-z0-9-]+', '-', str(slug).lower()).strip('-')}.html"


def entry_anchor(file: str | None) -> str:
    """The id of one entry on its track page: ``e-`` + the card file name without ``.json``."""
    stem = re.sub(r"\.json$", "", str(file or "entry"))
    return "e-" + re.sub(r"[^a-z0-9_-]+", "-", stem.lower()).strip("-")


def track_info(slug: str) -> dict[str, Any] | None:
    """Title, data, licence, CI unit, user model and notes of a v0.1 or a v0.2 track."""
    t = TRACKS.get(slug)
    if t is not None:
        ds = DATASETS[t.dataset]
        return {"title": t.title, "data": ds.title, "url": ds.url, "licence": ds.licence,
                "research_only": t.research_only, "ci_unit": t.ci_unit, "user_model": t.user_model.name,
                "gaze_cpm": t.user_model.gaze_chars_per_min, "notes": list(t.notes), "version": "0.1"}
    t2 = TR2.TRACKS.get(slug)
    if t2 is not None:
        from fidetype.benchmark.scorecard import SCORE_SPECS, scoring_track

        notes = list(t2.notes)
        if SCORE_SPECS[slug].key_track:
            notes.insert(0, "Key track: one character per key, so the CER column is the key error rate.")
        return {"title": t2.title, "data": t2.dataset_title, "url": t2.url, "licence": t2.licence,
                "research_only": t2.research_only, "ci_unit": t2.ci_unit,
                "user_model": scoring_track(slug).user_model.name, "gaze_cpm": 20.0, "notes": notes, "version": "0.2"}
    return None

COLUMNS = ("Decoder", "Policy", "CER", "eWPM [95% CI]", "Safe WPM v0.2 @ alpha", "Safe WPM v0.1 @ alpha",
           "Wrong-commit", "Error among commits", "Commit rate",
           "Controls", "Guarantee", "Conformance", "Weights licence", "Scored from", "Rerun")
#: The dated note on the safe-WPM columns (the switch to v0.2, docs/safe-wpm.md section 6a).
SAFE_WPM_NOTE = ("Safe WPM v0.2 is the headline column since 2026-11-22 (ADOPTED on that date): prefix credit and a "
                 "reading cost of 0.5 s + 0.3 s per committed word for every commit (user model aac-gaze-v1). For an "
                 "entry that commits whole sentences, v0.2 is the v0.1 value with the reading time added. The v0.1 "
                 "column keeps every earlier number with its value and its v0.1 label. Entries on tracks v0.1 got "
                 "their v0.2 value on 2026-11-24 from the same per-trial decisions as their v0.1 value.")
#: The v0.2 cell of a card without a safe-wpm/0.2 block.
NO_V02 = "v0.1 only (not rescored)"


def load_results(folder: str | PathLike[str] | list) -> list[dict[str, Any]]:
    if isinstance(folder, (list, tuple)):
        return [d for f in folder for d in load_results(f)]
    out = []
    for p in sorted(Path(folder).glob("*.json")):
        d = json.loads(p.read_text(encoding="utf-8"))
        if d.get("schema") not in RESULT_SCHEMAS:
            continue
        d["_file"] = p.name
        out.append(d)
    return out


#: Versions of the committed leaderboard cards that ship in the wheel (``fidetype/_benchmark/results/<v>``).
CARD_VERSIONS = ("v0.1", "v0.2")


def results_dir(version: str = "v0.2") -> Path:
    """The folder of the committed leaderboard cards of one benchmark version (P14-46).

    A wheel install has a copy in the package (``fidetype/_benchmark/results/<version>``); a git
    checkout reads ``benchmark/results/<version>``. So ``pip install`` users can compare their card
    with the leaderboard offline: ``build_rows(load_results(results_dir()) + [card])``.
    """
    if version not in CARD_VERSIONS:
        raise ValueError(f"unknown card version {version!r}; known: {list(CARD_VERSIONS)}")
    here = Path(__file__).resolve()
    packaged = here.parents[1] / "_benchmark" / "results" / version
    if packaged.is_dir():
        return packaged
    checkout = here.parents[3] / "benchmark" / "results" / version
    if checkout.is_dir():
        return checkout
    raise FileNotFoundError(f"no committed cards of {version}: looked in {packaged} and {checkout}")


def committed_results(version: str = "v0.2") -> list[dict[str, Any]]:
    """The committed leaderboard cards of one version (:func:`load_results` of :func:`results_dir`)."""
    return load_results(results_dir(version))


def _v(m: dict[str, Any], key: str) -> float | None:
    x = (m.get(key) or {}).get("value")
    return None if x is None or (isinstance(x, float) and not math.isfinite(x)) else x


def _ci(m: dict[str, Any], key: str) -> list[float] | None:
    c = (m.get(key) or {}).get("ci")
    if not c or any(x is None for x in c):
        return None
    return c


def fmt(x: float | None, nd: int = 3) -> str:
    return "n/a" if x is None else f"{x:.{nd}f}"


def fmt_pct(x: float | None) -> str:
    return "n/a" if x is None else f"{100 * x:.1f}%"


def controls_text(c: dict[str, Any]) -> str:
    if not c:
        return "n/a"
    parts = []
    for k, label in (("shuffled", "shuf"), ("zeros", "zeros"), ("null_commit", "null")):
        st = (c.get(k) or {}).get("status", "missing")
        parts.append(f"{label} {st}")
    head = "yes" if c.get("passed") else "no"
    return f"{head} ({', '.join(parts)})"


def guarantee_text(g: dict[str, Any]) -> str:
    if not g or g.get("method", "none") == "none":
        return "none"
    s = f"{g['method'].upper()} a={g.get('alpha')}"
    if g.get("delta") is not None and g["method"] == "ltt":
        s += f" d={g['delta']}"
    if g.get("n_cal") is not None:
        s += f", n_cal={g['n_cal']}"
    if g.get("measured_wrong_commit") is not None:
        s += f"; test {fmt(g['measured_wrong_commit'])}"
        if g.get("met_on_test") is not None:
            s += " (met)" if g["met_on_test"] else " (NOT met)"
    return s


def safe_wpm_blocks(d: dict[str, Any]) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    """(safe-wpm/0.2 block, safe-wpm/0.1 block) of a card, each found by its ``definition`` label.

    Cards keep the v0.1 block under ``safe_wpm``; the v0.2 block (the headline since 2026-11-22) is
    ``safe_wpm_v02``. Cards scored before that have no v0.2 block (None).
    """
    v1 = v2 = None
    for k in ("safe_wpm", "safe_wpm_v02"):
        b = d.get(k)
        if not isinstance(b, dict):
            continue
        if b.get("definition") == "safe-wpm/0.2":
            v2 = v2 or b
        elif k == "safe_wpm":
            v1 = b
    return v2, v1


def safe_wpm_text(sw: dict[str, Any] | None, missing: str = "not computed") -> str:
    """The safe-WPM cell (P14-05): value [CI], bound, and a mark when the test rate is above alpha."""
    if not sw:
        return missing
    st = sw.get("status")
    if st == "not-certified":
        return "n/a (no certified bound)"
    v, ci = sw.get("value"), sw.get("ci")
    s = fmt(v, 2) + (f" [{ci[0]:.2f}, {ci[1]:.2f}]" if ci and all(x is not None for x in ci) else "")
    g = f"{str(sw.get('method', '')).upper()} a={sw.get('alpha')}"
    if sw.get("delta") is not None:
        g += f" d={sw['delta']}"
    if st == "vacuous":
        return f"{s} (vacuous: no commits; {g})"
    if st == "above-alpha":
        return f"{s} ! ABOVE alpha (test {fmt(sw.get('measured_wrong_commit'))}; {g})"
    return f"{s} ({g})"


def card_target(d: dict[str, Any]) -> str | None:
    """The scoring target of a card (P11-13): its ``target`` block, else the track default (None: no targets)."""
    tg = (d.get("target") or {}).get("name")
    if tg:
        return tg
    from fidetype.benchmark.scorecard import SCORE_SPECS

    spec = SCORE_SPECS.get(str(d.get("track")))
    return spec.targets[0] if spec is not None and spec.targets else None


def _default_target(slug: str) -> str | None:
    from fidetype.benchmark.scorecard import SCORE_SPECS

    spec = SCORE_SPECS.get(slug)
    return spec.targets[0] if spec is not None and spec.targets else None


def target_groups(slug: str, rows: list[dict[str, Any]]) -> list[tuple[str | None, list[dict[str, Any]]]]:
    """Rows of one track split by scoring target (P11-13). Entries with different targets are never ranked in one
    table: each target gets its own table and its own no-BCI reference. One group ``(None, rows)`` when every
    entry uses the track default (the table then looks as before)."""
    from fidetype.benchmark.scorecard import SCORE_SPECS

    spec = SCORE_SPECS.get(slug)
    default = _default_target(slug)
    if not rows or all(r.get("target") in (None, default) for r in rows):
        return [(None, rows)]
    order = list(spec.targets) if spec is not None else []
    names = sorted({r.get("target") or default for r in rows}, key=lambda t: (order.index(t) if t in order else 99, t))
    return [(t, [r for r in rows if (r.get("target") or default) == t]) for t in names]


def target_label(name: str) -> str:
    from fidetype.benchmark.scorecard import TARGETS

    version, _, rule = TARGETS.get(name, (name, "", ""))
    return f"Target {name} ({version}): {rule}."


def row(d: dict[str, Any]) -> dict[str, Any]:
    m = d.get("metrics", {})
    ew, ci = _v(m, "ewpm"), _ci(m, "ewpm")
    ew_s = fmt(ew, 2) + (f" [{ci[0]:.2f}, {ci[1]:.2f}]" if ci else "")
    dec = d.get("decoder", {})
    name = dec.get("name", "?")
    if dec.get("training_regime"):
        name += f" ({dec['training_regime']})"
    cov = d.get("coverage") or {}
    if cov.get("partial"):
        name += f" [partial: {cov.get('n_covered')}/{cov.get('n_scored_units')} units]"
    if (d.get("track_info") or {}).get("research_only"):
        name += " [RESEARCH ONLY]"
    # P6-10: train / test overlap check (cards scored before P6-10 have no block and get no mark).
    ov = d.get("overlap_check")
    if ov and ov.get("status") == "overlap":
        name += f" [TRAIN/TEST OVERLAP: {ov.get('n_overlapping_units')}/{ov.get('n_scored_units')} units]"
    elif ov and ov.get("status") == "not checked":
        name += " [overlap not checked]"
    tgt = card_target(d)
    if tgt is not None and tgt != _default_target(str(d.get("track"))):
        name += f" [target: {tgt}]"
    sw2, sw1 = safe_wpm_blocks(d)
    return {
        "entry_id": d.get("entry_id"), "track": d.get("track"), "decoder": name, "target": tgt,
        "policy": d.get("policy", {}).get("name", ""),
        "cer": _v(m, "cer"), "wer": _v(m, "wer"), "ewpm": ew, "ewpm_ci": ci, "gaze_ewpm": _v(m, "gaze_ewpm"),
        "wrong_commit_rate": _v(m, "wrong_commit_rate"), "error_among_commits": _v(m, "error_among_commits"),
        "commit_rate": _v(m, "commit_rate"),
        "controls_passed": (d.get("controls") or {}).get("passed"), "controls": controls_text(d.get("controls") or {}),
        "guarantee": guarantee_text(d.get("guarantee") or {}),
        "conformance": (d.get("conformance") or {}).get("level", "unknown"),
        "weights_licence": dec.get("weights_licence", "?"), "scored_from": d.get("scored_from", "?"),
        "n_trials": d.get("n_trials"), "ci_unit": (d.get("ci") or {}).get("unit"), "notes": d.get("notes", []),
        "file": d.get("_file"), "ewpm_s": ew_s,
        # Headline: safe-wpm/0.2 (adopted 2026-11-22). Second column: safe-wpm/0.1 (values and labels kept).
        "safe_wpm_definition": (sw2 or {}).get("definition"),
        "safe_wpm": (sw2 or {}).get("value"), "safe_wpm_status": (sw2 or {}).get("status"),
        "safe_wpm_s": safe_wpm_text(sw2, NO_V02) if sw1 else safe_wpm_text(sw2),
        "safe_wpm_v01": (sw1 or {}).get("value"), "safe_wpm_v01_status": (sw1 or {}).get("status"),
        "safe_wpm_v01_s": safe_wpm_text(sw1),
        # P13-06: rerun level (design section 5.2) and the full recipe; "no" when the card has none.
        "rerun_level": rerun_level(d), "rerun": d.get("rerun"),
        "overlap_status": (ov or {}).get("status"),
        # P13-09: stable link of this entry (relative to the leaderboard folder).
        "anchor": entry_anchor(d.get("_file")),
        "link": f"{track_page(d.get('track', '?'))}#{entry_anchor(d.get('_file'))}",
    }


def cells(r: dict[str, Any]) -> list[str]:
    return [r["decoder"], r["policy"], fmt(r["cer"]), r["ewpm_s"], r["safe_wpm_s"], r["safe_wpm_v01_s"],
            fmt(r["wrong_commit_rate"]),
            fmt(r["error_among_commits"]), fmt(r["commit_rate"]), r["controls"], r["guarantee"], r["conformance"],
            r["weights_licence"], r["scored_from"], r["rerun_level"]]


def build_rows(results: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    by: dict[str, list[dict[str, Any]]] = {t: [] for t in TRACKS}
    by.update({t: [] for t in TR2.TRACKS})
    for d in results:
        by.setdefault(d.get("track", "?"), []).append(row(d))
    for t in by:
        by[t].sort(key=lambda r: -(r["ewpm"] if r["ewpm"] is not None else -1))
    return by


def _gaze(rows: list[dict[str, Any]]) -> float | None:
    for r in rows:
        if r["gaze_ewpm"] is not None:
            return r["gaze_ewpm"]
    return None


SECTIONS = (
    ("tracks-v02", "Tracks v0.2: commercially clean data", ""),
    ("research-only", "Research-only tracks (non-commercial data)",
     "These datasets carry a non-commercial licence. Results, streams and weights from them are research only. "
     "They stay in this separate section (hub decision Q4)."),
    ("tracks-v01", "Tracks v0.1 (earlier splits)", ""),
)


def sections(by: dict[str, list[dict[str, Any]]]) -> list[tuple[str, str, str, list[str]]]:
    """(id, title, intro, track slugs): v0.2 clean tracks, research-only tracks (v0.2 first), v0.1 clean tracks."""
    groups: dict[str, list[str]] = {k: [] for k, _, _ in SECTIONS}
    for slug in by:
        t = track_info(slug)
        if t and t["research_only"]:
            groups["research-only"].append(slug)
        elif t and t["version"] == "0.1":
            groups["tracks-v01"].append(slug)
        else:
            groups["tracks-v02"].append(slug)
    groups["research-only"].sort(key=lambda s: 0 if (track_info(s) or {}).get("version") == "0.2" else 1)
    return [(k, title, intro, groups[k]) for k, title, intro in SECTIONS if groups[k]]


def _track_title(slug: str) -> str:
    t = track_info(slug)
    return (t["title"] if t else slug) + (f" (tracks v{t['version']})" if t else "")


def markdown(by: dict[str, list[dict[str, Any]]]) -> str:
    L = [f"# Fidetype open benchmark v{BENCHMARK_VERSION}: leaderboard", "",
         "Generated by `python -m fidetype.benchmark leaderboard`. Do not edit by hand.", "",
         "Tracks v0.1 (three tracks) and tracks v0.2 (seven tracks, P6-01). v0.2 entries are scored by "
         "`python -m fidetype.benchmark score <track> <submission>` (P6-02, "
         "[docs/benchmark-submission.md](../../docs/benchmark-submission.md)). `[RESEARCH ONLY]` marks entries on "
         "non-commercial data; `[partial]` marks entries that cover only part of the scored units. "
         "`[TRAIN/TEST OVERLAP]` marks entries whose declared training data hold scored units, and "
         "`[overlap not checked]` marks entries without a `training_data` declaration (P6-10). Entries scored "
         "before P6-10 have no overlap check and no mark.", "",
         "Safe WPM @ alpha (P14-05): committed, exactly right words per minute, with a time penalty per wrong "
         "commit, only under a certified CRC / LTT bound. `! ABOVE alpha` marks a measured test wrong-commit rate "
         "above the stated alpha. Definition: [docs/safe-wpm.md](../../docs/safe-wpm.md).", "",
         SAFE_WPM_NOTE + " Definition and history: [docs/safe-wpm.md](../../docs/safe-wpm.md) section 6a, "
         "[docs/safe-wpm-v0.2-proposal.md](../../docs/safe-wpm-v0.2-proposal.md).", "",
         "Rerun (P13-06): the rerun level of each entry (`rescore`, `replay`, `full` or `no`). Below each table, "
         "the exact rerun recipe of every entry: dataset version, split digest, adapter hash, scorer version and "
         "commands, with `<placeholders>` for local paths ([docs/hub-design.md](../../docs/hub-design.md) "
         "section 5).", "",
         "Track pages (P13-09): each track has its own page, `tracks/<track>.html`, with a stable link per entry "
         "and the entry history from git.", ""]
    for sid, stitle, intro, slugs in sections(by):
        L += [f'<a id="{sid}"></a>', "", f"## {stitle}", ""]
        if intro:
            L += [intro, ""]
        for slug in slugs:
            L += _md_track(slug, by[slug])
    return "\n".join(L) + "\n"


def _md_track(slug: str, rows: list[dict[str, Any]]) -> list[str]:
    t = track_info(slug)
    L = [f'<a id="{track_anchor(slug)}"></a>', "", f"### {_track_title(slug)}", "",
         f"Track page and entry history: [{track_page(slug)}]({track_page(slug)}).", ""]
    if t:
        L += [f"Track `{slug}`. Data: {t['data']} ({t['licence']}{', **research only**' if t['research_only'] else ''}). "
              f"CI unit: {t['ci_unit']}. User model: {t['user_model']}.", ""]
    if not rows:
        return L + ["No entries yet.", ""]
    for tgt, grp in target_groups(slug, rows):
        if tgt is not None:
            L += [f"**{target_label(tgt)}**", ""]
        g = _gaze(grp)
        if g is not None:
            L += [f"No-BCI reference (gaze typing only, {t['gaze_cpm'] if t else 20:.0f} chars/min"
                  + (f", target {tgt}" if tgt else "") + f"): **{g:.2f} eWPM**.", ""]
        L += ["| " + " | ".join(COLUMNS) + " |", "|" + "---|" * len(COLUMNS)]
        L += ["| " + " | ".join(c.replace("|", "/") for c in cells(r)) + " |" for r in grp]
        L.append("")
    L += recipes_markdown(rows)
    return L


def _recipe_steps(rc: dict[str, Any]) -> list[str]:
    steps = rc.get("steps") or [{"step": "score", "command": rc.get("command", "")}]
    return [f"[{s.get('step')}] {s.get('command')}" for s in steps]


def _recipe_facts(rc: dict[str, Any]) -> str:
    ds, ad, tr = rc.get("dataset"), rc.get("adapter"), rc.get("track") or {}
    sc = rc.get("scorer") or {}
    parts = [f"level {rc.get('level')}",
             (f"dataset {ds['id']} {ds['version']} r{ds['revision']}" if ds else "dataset not in the hub registry"),
             f"split {tr.get('split_version')} digest {str(tr.get('digest'))[:12]}",
             (f"adapter {ad['module']} {ad['package_version']} sha256 {ad['sha256'][:12]}" if ad else "adapter none"),
             f"scorer {sc.get('scorer_version')} B={sc.get('B')} seed={sc.get('seed')}"]
    dec, pol = rc.get("decoder") or {}, rc.get("policy") or {}
    if dec.get("weights_sha256"):  # P13-11: a value or the reason
        parts.append(f"weights sha256 {dec['weights_sha256'][:12]}")
    elif dec.get("weights_sha256_reason"):
        parts.append("weights: " + str(dec["weights_sha256_reason"]).split(":")[0].split(";")[0])
    if pol.get("config_id"):
        parts.append(f"policy config {pol['config_id']}")
    elif pol.get("config_id_reason"):
        parts.append("policy config: " + str(pol["config_id_reason"]).split(":")[0].split(";")[0])
    if rc.get("code_ref"):
        parts.append(f"code {rc['code_ref'].split(' (')[0]}")
    return "; ".join(parts)


def recipes_markdown(rows: list[dict[str, Any]]) -> list[str]:
    """Rerun recipes of one track (P13-06): one item per entry, the full command list in a code block."""
    have = [r for r in rows if r.get("rerun")]
    if not have:
        return []
    L = ["Rerun recipes (`python -m fidetype.benchmark.hub recipe <card>` prints one):", ""]
    for r in have:
        rc = r["rerun"]
        L += [f"- **{r['decoder']} / {r['policy']}** (`{r['file']}`): {_recipe_facts(rc)}", "",
              "  ```", *[f"  {x}" for x in _recipe_steps(rc)], "  ```", ""]
    return L


CSS = """
:root{--bg:#fbfaf8;--fg:#1d1d1f;--muted:#5c5c66;--line:#dedbd5;--card:#ffffff;--accent:#2f5d8a;--ok:#2d7a3e;--bad:#a8322d;--head:#f1efea}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){--bg:#16171a;--fg:#e8e6e1;--muted:#a3a3ad;--line:#33353b;--card:#1d1f23;--accent:#8bb6e0;--ok:#7fc58d;--bad:#ef8a84;--head:#24262b}}
:root[data-theme="dark"]{--bg:#16171a;--fg:#e8e6e1;--muted:#a3a3ad;--line:#33353b;--card:#1d1f23;--accent:#8bb6e0;--ok:#7fc58d;--bad:#ef8a84;--head:#24262b}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif}
main{max-width:1280px;margin:0 auto;padding:24px 16px 48px}h1{font-size:1.6rem;margin:0 0 4px}h2{font-size:1.2rem;margin:32px 0 6px}
p{margin:6px 0;color:var(--muted)}a{color:var(--accent)}.wrap{overflow-x:auto;border:1px solid var(--line);border-radius:8px;background:var(--card)}
table{border-collapse:collapse;width:100%;font-size:13px}th,td{padding:7px 9px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}
th{background:var(--head);font-weight:600;white-space:nowrap}td.num{font-variant-numeric:tabular-nums;white-space:nowrap}
tr.ref td{color:var(--muted);font-style:italic}.ok{color:var(--ok);font-weight:600}.bad{color:var(--bad);font-weight:600}
.note{font-size:13px}ul{margin:6px 0 0 18px;color:var(--muted);font-size:13px}code{font-size:12.5px}
details{margin:8px 0 0}summary{cursor:pointer;color:var(--accent);font-size:13px}
pre{background:var(--card);border:1px solid var(--line);border-radius:6px;padding:8px;font-size:12px;white-space:pre-wrap;overflow-wrap:anywhere;margin:4px 0 10px}
.recipe{font-size:13px;color:var(--muted);margin:8px 0 0}
h3{font-size:1.05rem;margin:28px 0 4px}h3[id],section[id]{scroll-margin-top:12px}.cnt{color:var(--muted);font-size:12.5px}
.badge{display:inline-block;font-size:11.5px;font-weight:600;border:1px solid var(--line);border-radius:99px;padding:1px 8px;color:var(--muted)}
.badge.ro{color:var(--bad);border-color:var(--bad)}.ro-section{border-left:3px solid var(--bad);padding-left:12px;margin-top:24px}
.ro-box{border:1px solid var(--bad);border-radius:8px;padding:8px 10px;color:var(--fg)}
.toc{border:1px solid var(--line);border-radius:8px;background:var(--card);padding:8px 12px;margin:14px 0;font-size:13px}
.toc ul{margin:4px 0 0 18px}.tp{font-size:13px}.crumb{font-size:13px}
.entry{border-top:1px solid var(--line);margin-top:18px}.entry h3{margin-top:12px}a.self{text-decoration:none;color:var(--muted);font-weight:400}
table.hist td{white-space:nowrap}tbody td:first-child{min-width:11em}
"""


def _td(text: str, cls: str = "") -> str:
    c = f' class="{cls}"' if cls else ""
    return f"<td{c}>{html.escape(text)}</td>"


def page(by: dict[str, list[dict[str, Any]]]) -> str:
    parts = ["<!doctype html>", '<html lang="en"><head><meta charset="utf-8">',
             '<meta name="viewport" content="width=device-width, initial-scale=1">',
             f"<title>Fidetype Benchmark v{BENCHMARK_VERSION}</title><style>{CSS}</style></head><body><main>",
             f"<h1>Fidetype open benchmark v{BENCHMARK_VERSION}</h1>",
             "<p>Neural text entry, scored from NeuralTextStream outputs. Every eWPM sits next to the no-BCI "
             "reference (gaze typing). Wrong-commit is marginal (wrong commits / all trials); error among commits "
             "is wrong commits / commits. CIs are cluster bootstraps at the track unit. No data and no weights "
             "are shipped: every dataset is download-only.</p>",
             "<p>Safe WPM @ alpha (P14-05): words per minute of committed text that is exactly right, with a time "
             "penalty for each wrong commit, shown only when the policy has a certified CRC / LTT bound on the "
             "wrong-commit rate. Offered or withheld text counts 0 words. <b>ABOVE alpha</b> marks an entry whose "
             "measured test rate is higher than its stated alpha. Definition: <code>docs/safe-wpm.md</code>.</p>",
             f"<p><b>{html.escape(SAFE_WPM_NOTE)}</b> Definition and history: <code>docs/safe-wpm.md</code> "
             "section 6a.</p>",
             "<p>Tracks v0.1 (three tracks) and tracks v0.2 (seven tracks). v0.2 entries are scored by "
             "<code>python -m fidetype.benchmark score &lt;track&gt; &lt;submission&gt;</code> "
             "(<code>docs/benchmark-submission.md</code>). <b>[RESEARCH ONLY]</b> marks entries on non-commercial "
             "data; <b>[partial]</b> marks entries that cover only part of the scored units. "
             "<b>[TRAIN/TEST OVERLAP]</b> marks entries whose declared training data hold scored units, and "
             "<b>[overlap not checked]</b> marks entries without a <code>training_data</code> declaration (P6-10). "
             "Entries scored before P6-10 have no overlap check and no mark.</p>",
             "<p>Rerun (P13-06): the rerun level of each entry (<code>rescore</code>, <code>replay</code>, "
             "<code>full</code> or <code>no</code>). Each track lists the exact rerun recipe of every entry: "
             "dataset version, split digest, adapter hash, scorer version and commands. Local paths are "
             "<code>&lt;placeholders&gt;</code>. Design: <code>docs/hub-design.md</code> section 5.</p>",
             "<p>Track pages (P13-09): each track heading links to its own page, <code>tracks/&lt;track&gt;.html</code>, "
             "with a stable link per entry (<code>#e-&lt;card file name&gt;</code>) and the entry history from git: "
             "when each entry was added or changed, with its split, scorer and metric versions and rerun level.</p>",
             '<p class="note">How to submit: <code>benchmark/README.md</code>. Generated by '
             "<code>python -m fidetype.benchmark leaderboard</code>; do not edit by hand.</p>"]
    toc = []
    for sid, stitle, _, slugs in sections(by):
        items = "".join(f'<li><a href="#{track_anchor(s)}">{html.escape(_track_title(s))}</a> '
                        f'<span class="cnt">({len(by[s])})</span></li>' for s in slugs)
        toc.append(f'<li><a href="#{sid}">{html.escape(stitle)}</a><ul>{items}</ul></li>')
    parts.append(f'<nav class="toc" aria-label="Tracks"><b>Tracks</b><ul>{"".join(toc)}</ul></nav>')
    for sid, stitle, intro, slugs in sections(by):
        cls = ' class="ro-section"' if sid == "research-only" else ""
        parts.append(f'<section id="{sid}"{cls}><h2>{html.escape(stitle)}'
                     + (' <span class="badge ro">RESEARCH ONLY</span>' if sid == "research-only" else "") + "</h2>")
        if intro:
            parts.append(f"<p>{html.escape(intro)}</p>")
        for slug in slugs:
            parts += _html_track(slug, by[slug])
        parts.append("</section>")
    parts.append("</main></body></html>")
    return "\n".join(parts) + "\n"


def _track_meta(slug: str) -> str:
    t = track_info(slug)
    if not t:
        return ""
    ro = ' <b class="bad">Research only (non-commercial data).</b>' if t["research_only"] else ""
    return (f'<p>Track <code>{html.escape(slug)}</code>. Data: <a href="{html.escape(t["url"])}">'
            f"{html.escape(t['data'])}</a>, {html.escape(t['licence'])}.{ro} CI unit: "
            f"<code>{html.escape(t['ci_unit'])}</code>. User model: {html.escape(t['user_model'])}.</p>")


def _board_tables(slug: str, rows: list[dict[str, Any]], link: str) -> str:
    """One main table per scoring target (P11-13); one table as before when all entries use the default."""
    out = []
    for tgt, grp in target_groups(slug, rows):
        if tgt is not None:
            out.append(f'<p class="tgt"><b>{html.escape(target_label(tgt))}</b></p>')
        out.append(_board_table(slug, grp, link))
    return chr(10).join(out)


def _board_table(slug: str, rows: list[dict[str, Any]], link: str) -> str:
    """The main table of one track. ``link`` is the prefix of the entry links ("" on the track page)."""
    t = track_info(slug)
    out = ['<div class="wrap"><table><thead><tr>' + "".join(f"<th>{html.escape(c)}</th>" for c in COLUMNS)
           + "</tr></thead><tbody>"]
    g = _gaze(rows)
    if g is not None:
        cpm = t["gaze_cpm"] if t else 20.0
        out.append('<tr class="ref">' + _td(f"No-BCI reference: gaze typing ({cpm:.0f} chars/min)") + _td("type all")
                   + _td("n/a", "num") + _td(f"{g:.2f}", "num") + _td("n/a", "num") + _td("0.000", "num")
                   + _td("n/a", "num") + _td("n/a", "num")
                   + _td("0.000", "num") + "".join(_td("") for _ in range(6)) + "</tr>")
    for r in rows:
        c = cells(r)
        ctl_cls = "ok" if r["controls_passed"] else "bad"
        def cls(st: str | None) -> str:
            return "bad" if st == "above-alpha" else ("ok" if st == "certified" else "num")

        first = f'<td><a href="{html.escape(link)}#{r["anchor"]}">{html.escape(c[0])}</a></td>'
        tds = ([first, _td(c[1]), _td(c[2], "num"), _td(c[3], "num"), _td(c[4], cls(r["safe_wpm_status"])),
                _td(c[5], cls(r["safe_wpm_v01_status"]))]
               + [_td(x, "num") for x in c[6:9]] + [_td(c[9], ctl_cls)] + [_td(x) for x in c[10:]])
        out.append("<tr>" + "".join(tds) + "</tr>")
    out.append("</tbody></table></div>")
    return "\n".join(out)


def _notes_html(slug: str, rows: list[dict[str, Any]]) -> str:
    t = track_info(slug)
    notes = sorted({n for r in rows for n in r["notes"]})
    if t:
        notes = list(t["notes"]) + notes
    return ("<ul>" + "".join(f"<li>{html.escape(n)}</li>" for n in notes) + "</ul>") if notes else ""


def _html_track(slug: str, rows: list[dict[str, Any]]) -> list[str]:
    page_href = track_page(slug)
    parts = [f'<h3 id="{track_anchor(slug)}">{html.escape(_track_title(slug))}</h3>',
             f'<p class="tp"><a href="{page_href}">Track page and entry history</a> '
             f'<span class="cnt">(<code>{page_href}</code>)</span></p>']
    meta = _track_meta(slug)
    if meta:
        parts.append(meta)
    if not rows:
        parts.append("<p>No entries yet.</p>")
        return parts
    parts.append(_board_tables(slug, rows, page_href))
    have = [r for r in rows if r.get("rerun")]
    if have:
        parts.append(f"<details><summary>Rerun recipes ({len(have)} of {len(rows)} entries)</summary>")
        for r in have:
            rc = r["rerun"]
            parts.append(f'<p class="recipe"><b>{html.escape(r["decoder"])} / {html.escape(r["policy"])}</b> '
                         f"(<code>{html.escape(str(r['file']))}</code>): {html.escape(_recipe_facts(rc))}</p>"
                         f"<pre><code>{html.escape(chr(10).join(_recipe_steps(rc)))}</code></pre>")
        parts.append("</details>")
    n = _notes_html(slug, rows)
    if n:
        parts.append(n)
    return parts


# ---------------------------------------------------------------------------------------------
# Track pages (P13-09)

HISTORY_COLUMNS = ("Date", "Commit", "Entry", "Change", "Split", "Scorer", "Metric versions", "Rerun", "eWPM",
                   "Safe WPM")


def _metric_versions(v: dict[str, Any]) -> str:
    m = v.get("metric_versions") or {}
    return ", ".join(f"{k} {val}" for k, val in sorted(m.items())) or "n/a"


def _change_text(v: dict[str, Any]) -> str:
    if v["action"] == "changed":
        ch = v.get("changed") or []
        return "changed: " + (", ".join(ch) if ch else "formatting only")
    return v["action"]


def _sw_short(v: dict[str, Any]) -> str:
    """The safe-WPM cell of one card version: v0.2 when the version has it, else v0.1 (labelled)."""
    if "safe_wpm_v02_status" in v:
        st, val, lab = v.get("safe_wpm_v02_status"), v.get("safe_wpm_v02"), "v0.2"
    else:
        st, val, lab = v.get("safe_wpm_status"), v.get("safe_wpm"), "v0.1"
    if st in (None, "not-certified"):
        return f"n/a ({lab})" if st else "not computed"
    return fmt(val, 2) + (" (above alpha)" if st == "above-alpha" else "") + f" ({lab})"


def _history_rows(events: list[dict[str, Any]], names: dict[str, str], show_entry: bool) -> str:
    out = []
    for v in events:
        date = v["date"] or "with this page"
        commit = f"<code>{v['commit']}</code>" if v.get("commit") else "this commit"
        if v.get("anchor"):
            entry = f'<a href="#{v["anchor"]}">{html.escape(names.get(v["file"], v["file"]))}</a>'
        else:
            entry = f"{html.escape(str(v.get('entry_id') or v.get('file')))} <b class=\"bad\">(removed)</b>"
        tds = [f'<td class="num">{html.escape(date)}</td>', f"<td>{commit}</td>"]
        if show_entry:
            tds.append(f"<td>{entry}</td>")
        tds += [_td(_change_text(v)), _td(f"{v['split_version']} {str(v.get('split_digest') or '')[:8]}".strip()),
                _td(str(v["scorer_version"])), _td(_metric_versions(v)), _td(v["rerun_level"]),
                _td(fmt(v.get("ewpm"), 2), "num"), _td(_sw_short(v), "num")]
        title = f' title="{html.escape(v["subject"])}"' if v.get("subject") else ""
        out.append(f"<tr{title}>" + "".join(tds) + "</tr>")
    return "\n".join(out)


def _history_table(events: list[dict[str, Any]], names: dict[str, str], show_entry: bool = True) -> str:
    cols = [c for c in HISTORY_COLUMNS if show_entry or c != "Entry"]
    return ('<div class="wrap"><table class="hist"><thead><tr>' + "".join(f"<th>{c}</th>" for c in cols)
            + "</tr></thead><tbody>\n" + _history_rows(events, names, show_entry) + "\n</tbody></table></div>")


def track_page_html(slug: str, rows: list[dict[str, Any]], history: dict[str, Any]) -> str:
    """One self-contained page per track: entries with stable ids, rerun recipes and the entry history."""
    t = track_info(slug)
    title = _track_title(slug)
    back = f"../index.html#{track_anchor(slug)}"
    files = {r["file"]: r["anchor"] for r in rows}
    names = {r["file"]: f"{r['decoder']} / {r['policy']}" for r in rows}
    events = track_events(history, files, slug)
    badges = []
    if t:
        badges.append(f'<span class="badge">tracks v{t["version"]}</span>')
        if t["research_only"]:
            badges.append('<span class="badge ro">RESEARCH ONLY</span>')
    parts = ["<!doctype html>", '<html lang="en"><head><meta charset="utf-8">',
             '<meta name="viewport" content="width=device-width, initial-scale=1">',
             f"<title>{html.escape(t['title'] if t else slug)} | Fidetype Benchmark</title><style>{CSS}</style>"
             "</head><body><main>",
             f'<p class="crumb"><a href="{back}">Leaderboard</a> / track <code>{html.escape(slug)}</code></p>',
             f"<h1>{html.escape(title)}</h1>", f'<p>{" ".join(badges)}</p>' if badges else ""]
    meta = _track_meta(slug)
    if meta:
        parts.append(meta)
    if t and t["research_only"]:
        parts.append('<p class="ro-box">This track uses non-commercial data. Its results, streams and weights are '
                     "research only. On the leaderboard it is in the separate research-only section.</p>")
    parts.append(f"<p><b>{html.escape(SAFE_WPM_NOTE)}</b> Definition: <code>docs/safe-wpm.md</code> section 6a. "
                 "In the entry history, each Safe WPM value names its version.</p>")
    parts.append('<p class="note">Stable links: this page is <code>' + html.escape(track_page(slug))
                 + "</code>; each entry has the anchor <code>#e-&lt;card file name&gt;</code>; the history is "
                 "<code>#history</code>. Generated by <code>python -m fidetype.benchmark leaderboard</code>; do not "
                 "edit by hand.</p>")
    parts.append('<nav class="toc" aria-label="On this page"><ul><li><a href="#entries">Entries</a></li>'
                 '<li><a href="#history">Entry history</a></li><li><a href="#details">Entry details and rerun '
                 "recipes</a></li></ul></nav>")
    parts.append('<h2 id="entries">Entries</h2>')
    if rows:
        parts.append(_board_tables(slug, rows, ""))
    else:
        parts.append("<p>No entries yet.</p>")
    parts.append('<h2 id="history">Entry history</h2>')
    if not history.get("available"):
        parts.append(f"<p>Entry history not available: {html.escape(history.get('note', ''))}.</p>")
    elif not events:
        parts.append("<p>No entry history yet.</p>")
    else:
        parts.append("<p>Every version of every score card of this track, newest first: the commit that added or "
                     "changed the card file, and the split, scorer, metric versions and rerun level of that version. "
                     f"Source: {html.escape(history.get('note', ''))}. A changed row names the top-level card fields "
                     "that changed.</p>")
        parts.append(_history_table(events, names))
    parts.append('<h2 id="details">Entry details and rerun recipes</h2>')
    if not rows:
        parts.append("<p>No entries yet.</p>")
    for r in rows:
        mine = [v for v in (history.get("cards") or {}).get(r["file"], [])]
        added = next((v for v in reversed(mine) if v["action"] == "added"), None)
        last = mine[0] if mine else None
        parts.append(f'<section class="entry" id="{r["anchor"]}"><h3>{html.escape(r["decoder"])} / '
                     f'{html.escape(r["policy"])} <a class="self" href="#{r["anchor"]}" aria-label="Link to this entry">#</a>'
                     "</h3>")
        facts = [f"Card <code>{html.escape(str(r['file']))}</code>", f"entry id <code>{html.escape(str(r['entry_id']))}</code>",
                 f"scored from {html.escape(str(r['scored_from']))}", f"rerun level <b>{html.escape(r['rerun_level'])}</b>"]
        if added:
            facts.append(f"added {html.escape(added['date'] or 'with this page')}"
                         + (f" (<code>{added['commit']}</code>)" if added.get("commit") else ""))
        if last and last is not added:
            facts.append(f"last changed {html.escape(last['date'] or 'with this page')}"
                         + (f" (<code>{last['commit']}</code>)" if last.get("commit") else ""))
        if mine:
            facts.append(f"{len(mine)} version{'s' if len(mine) != 1 else ''}")
        parts.append("<p>" + "; ".join(facts) + ".</p>")
        if mine:
            parts.append(f"<details><summary>Versions of this entry ({len(mine)})</summary>"
                         + _history_table([{**v, "file": r["file"], "anchor": r["anchor"]} for v in mine], names,
                                          show_entry=False) + "</details>")
        rc = r.get("rerun")
        if rc:
            parts.append(f'<p class="recipe">Rerun recipe: {html.escape(_recipe_facts(rc))}</p>'
                         f"<pre><code>{html.escape(chr(10).join(_recipe_steps(rc)))}</code></pre>")
        else:
            parts.append('<p class="recipe">No rerun recipe in this card.</p>')
        parts.append("</section>")
    n = _notes_html(slug, rows)
    if n:
        parts += ['<h2 id="notes">Notes</h2>', n]
    parts.append("</main></body></html>")
    return "\n".join(p for p in parts if p) + "\n"


DEFAULT_RESULTS = ("benchmark/results/v0.1", "benchmark/results/v0.2")
DEFAULT_OUT = "benchmark/site"


def render(results_dir: str | PathLike[str] | list, history: dict[str, Any]) -> dict[str, str]:
    """All leaderboard outputs as {path relative to the output folder: text (LF line ends)}."""
    folders = list(results_dir) if isinstance(results_dir, (list, tuple)) else [results_dir]
    by = build_rows(load_results(folders))
    payload = {"benchmark_version": BENCHMARK_VERSION,
               "track_pages": {k: {"page": track_page(k), "anchor": track_anchor(k),
                                   "research_only": bool((track_info(k) or {}).get("research_only"))} for k in by},
               "tracks": {k: [{kk: vv for kk, vv in r.items() if kk != "ewpm_s"} for r in v] for k, v in by.items()}}
    files = {"leaderboard.json": json.dumps(payload, indent=1, ensure_ascii=False) + "\n",
             "leaderboard.md": markdown(by), "index.html": page(by),
             "history.json": json.dumps(history, indent=1, ensure_ascii=False) + "\n"}
    for k, v in by.items():
        files[track_page(k)] = track_page_html(k, v, history)
    return files


def _committed(out: Path, run=git_runner) -> dict[str, str] | None:
    """The leaderboard outputs as committed in ``HEAD`` ({relative path: text, LF}), or None without git."""
    root = repo_root(out if out.is_dir() else out.parent, run)
    if root is None:
        return None
    try:
        rel = out.resolve().relative_to(root).as_posix()
    except ValueError:
        return None
    names = (run(["ls-tree", "-r", "--name-only", "HEAD", f"{rel}/"], root) or "").split("\n")
    files = {}
    for n in [x for x in names if x]:
        sub = n[len(rel) + 1:]
        if sub in ("leaderboard.json", "leaderboard.md", "index.html", "history.json") or (
                sub.startswith("tracks/") and sub.endswith(".html")):
            files[sub] = (run(["show", f"HEAD:{n}"], root) or "").replace("\r\n", "\n")
    return files


def _norm(files: dict[str, str]) -> dict[str, str]:
    return {k: v.replace("\r\n", "\n") for k, v in files.items()}


def plan(results_dir: str | PathLike[str] | list, out_dir: str | PathLike[str], *,
         history: dict[str, Any] | None = None, history_base: str = "auto") -> tuple[dict[str, str], dict[str, Any]]:
    """The outputs and the history that ``build`` writes.

    ``history_base``: ``"auto"`` (default; see the module text), ``"site"`` (the parent of the newest commit
    that changed ``out_dir``: the freshness check) or a git revision."""
    folders = list(results_dir) if isinstance(results_dir, (list, tuple)) else [results_dir]
    if history is not None:
        return render(folders, history), history
    out = Path(out_dir)
    if history_base not in ("auto", "site"):
        h = build_history(folders, base=history_base)
        return render(folders, h), h
    sb = site_base(out)
    if history_base == "site" or sb is None:
        h = build_history(folders, base=sb or "HEAD")
        return render(folders, h), h
    h1 = build_history(folders, base=sb)
    f1 = render(folders, h1)
    if _norm(f1) == _committed(out):
        return f1, h1  # the committed pages are fresh: nothing changes
    h2 = build_history(folders, base="HEAD")  # the pages go into a new commit on top of HEAD
    return render(folders, h2), h2


def build(results_dir: str | PathLike[str] | list, out_dir: str | PathLike[str], *,
          history: dict[str, Any] | None = None, history_base: str = "auto") -> dict[str, Any]:
    """Write the leaderboard outputs. ``history`` (for tests) replaces the history read from git."""
    folders = list(results_dir) if isinstance(results_dir, (list, tuple)) else [results_dir]
    files, hist = plan(folders, out_dir, history=history, history_base=history_base)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    tdir = out / "tracks"
    tdir.mkdir(exist_ok=True)
    for old in tdir.glob("*.html"):
        if f"tracks/{old.name}" not in files:
            old.unlink()
    for rel, text in files.items():
        (out / rel).write_text(text, encoding="utf-8")
    lb = json.loads(files["leaderboard.json"])
    pending = sum(1 for vs in (hist.get("cards") or {}).values() for v in vs if v.get("commit") is None)
    pending += sum(1 for r in hist.get("removed") or [] if r.get("commit") is None)
    return {"n_results": len(load_results(folders)),
            "tracks": {k: len(v) for k, v in lb["tracks"].items()}, "out": str(out), "history": hist["available"],
            "rows_in_this_commit": pending}


def check(results_dir: str | PathLike[str] | list = DEFAULT_RESULTS,
          out_dir: str | PathLike[str] = DEFAULT_OUT) -> list[str]:
    """P13-12 freshness check: regenerate the outputs (history base = the parent of the commit that holds the
    pages) and compare them with the files in ``out_dir``. Returns the problems (an empty list = fresh)."""
    out = Path(out_dir)
    files, hist = plan(results_dir, out, history_base="site")
    errs = []
    if not hist.get("available"):
        errs.append(f"no git history ({hist.get('note')}); the check needs a full-history checkout (fetch-depth 0)")
    have = {p.relative_to(out).as_posix() for p in [*(out.glob("*.*")), *(out / "tracks").glob("*.html")]
            if p.name in ("leaderboard.json", "leaderboard.md", "index.html", "history.json") or p.parent.name == "tracks"}
    for rel in sorted(set(files) | have):
        if rel not in files:
            errs.append(f"{rel}: not generated any more (delete it)")
        elif rel not in have:
            errs.append(f"{rel}: missing")
        elif (out / rel).read_text(encoding="utf-8").replace("\r\n", "\n") != files[rel].replace("\r\n", "\n"):
            errs.append(f"{rel}: differs from the regenerated file")
    return errs


def main(argv: list[str] | None = None) -> int:
    import argparse
    import sys

    ap = argparse.ArgumentParser(prog="python -m fidetype.benchmark.leaderboard",
                                 description="Build the leaderboard, or check that the committed outputs are fresh.")
    ap.add_argument("--results", nargs="+", default=list(DEFAULT_RESULTS))
    ap.add_argument("--out", default=DEFAULT_OUT)
    ap.add_argument("--check", action="store_true",
                    help="regenerate and compare with --out; exit 1 on a difference (CI, P13-12)")
    a = ap.parse_args(argv)
    if a.check:
        errs = check(a.results, a.out)
        for e in errs:
            print(f"STALE {e}", file=sys.stderr)
        if errs:
            print("The leaderboard outputs are not fresh. Regenerate them: python -m fidetype.benchmark leaderboard "
                  f"--results {' '.join(a.results)} --out {a.out}; then commit {a.out}/ (with the cards or after "
                  "them).", file=sys.stderr)
            return 1
        print(f"leaderboard outputs in {a.out} are fresh", file=sys.stderr)
        return 0
    print(json.dumps(build(a.results, a.out)), file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
