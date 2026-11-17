"""Build the static leaderboard from a folder of result JSON files.

    python -m fidetype.benchmark leaderboard --results benchmark/results/v0.1 benchmark/results/v0.2 --out benchmark/site

Writes ``leaderboard.json`` (all rows), ``leaderboard.md`` (Markdown
tables, one per track) and ``index.html`` (one self-contained page, no
scripts, no network). The output folder can be served as is (for example
by GitHub Pages later). Never edit the outputs by hand.
"""

from __future__ import annotations

import html
import json
import math
from os import PathLike
from pathlib import Path
from typing import Any

from fidetype.benchmark import tracks as TR2
from fidetype.benchmark.registry import BENCHMARK_VERSION, DATASETS, TRACKS
from fidetype.benchmark.scoring import RESULT_SCHEMA

RESULT_SCHEMAS = (RESULT_SCHEMA, "fidetype.benchmark.result/0.2")


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

COLUMNS = ("Decoder", "Policy", "CER", "eWPM [95% CI]", "Safe WPM @ alpha", "Wrong-commit", "Error among commits", "Commit rate",
           "Controls", "Guarantee", "Conformance", "Weights licence", "Scored from")


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


def safe_wpm_text(sw: dict[str, Any] | None) -> str:
    """The safe-WPM cell (P14-05): value [CI], bound, and a mark when the test rate is above alpha."""
    if not sw:
        return "not computed"
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
    return {
        "entry_id": d.get("entry_id"), "track": d.get("track"), "decoder": name,
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
        "safe_wpm": (d.get("safe_wpm") or {}).get("value"), "safe_wpm_status": (d.get("safe_wpm") or {}).get("status"),
        "safe_wpm_s": safe_wpm_text(d.get("safe_wpm")),
    }


def cells(r: dict[str, Any]) -> list[str]:
    return [r["decoder"], r["policy"], fmt(r["cer"]), r["ewpm_s"], r["safe_wpm_s"], fmt(r["wrong_commit_rate"]),
            fmt(r["error_among_commits"]), fmt(r["commit_rate"]), r["controls"], r["guarantee"], r["conformance"],
            r["weights_licence"], r["scored_from"]]


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


def markdown(by: dict[str, list[dict[str, Any]]]) -> str:
    L = [f"# Fidetype open benchmark v{BENCHMARK_VERSION}: leaderboard", "",
         "Generated by `python -m fidetype.benchmark leaderboard`. Do not edit by hand.", "",
         "Tracks v0.1 (three tracks) and tracks v0.2 (seven tracks, P6-01). v0.2 entries are scored by "
         "`python -m fidetype.benchmark score <track> <submission>` (P6-02, "
         "[docs/benchmark-submission.md](../../docs/benchmark-submission.md)). `[RESEARCH ONLY]` marks entries on "
         "non-commercial data; `[partial]` marks entries that cover only part of the scored units.", "",
         "Safe WPM @ alpha (P14-05): committed, exactly right words per minute, with a time penalty per wrong "
         "commit, only under a certified CRC / LTT bound. `! ABOVE alpha` marks a measured test wrong-commit rate "
         "above the stated alpha. Definition: [docs/safe-wpm.md](../../docs/safe-wpm.md).", ""]
    for slug, rows in by.items():
        t = track_info(slug)
        L += [f"## {t['title'] if t else slug}" + (f" (tracks v{t['version']})" if t else ""), ""]
        if t:
            L += [f"Track `{slug}`. Data: {t['data']} ({t['licence']}{', **research only**' if t['research_only'] else ''}). "
                  f"CI unit: {t['ci_unit']}. User model: {t['user_model']}.", ""]
        g = _gaze(rows)
        if g is not None:
            L += [f"No-BCI reference (gaze typing only, {t['gaze_cpm'] if t else 20:.0f} chars/min): "
                  f"**{g:.2f} eWPM**.", ""]
        if not rows:
            L += ["No entries yet.", ""]
            continue
        L += ["| " + " | ".join(COLUMNS) + " |", "|" + "---|" * len(COLUMNS)]
        L += ["| " + " | ".join(c.replace("|", "/") for c in cells(r)) + " |" for r in rows]
        L.append("")
    return "\n".join(L) + "\n"


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
             "<p>Tracks v0.1 (three tracks) and tracks v0.2 (seven tracks). v0.2 entries are scored by "
             "<code>python -m fidetype.benchmark score &lt;track&gt; &lt;submission&gt;</code> "
             "(<code>docs/benchmark-submission.md</code>). <b>[RESEARCH ONLY]</b> marks entries on non-commercial "
             "data; <b>[partial]</b> marks entries that cover only part of the scored units.</p>",
             '<p class="note">How to submit: <code>benchmark/README.md</code>. Generated by '
             "<code>python -m fidetype.benchmark leaderboard</code>; do not edit by hand.</p>"]
    for slug, rows in by.items():
        t = track_info(slug)
        ver = f" (tracks v{t['version']})" if t else ""
        parts.append(f"<h2>{html.escape(t['title'] if t else slug)}{ver}</h2>")
        if t:
            ro = ' <b class="bad">Research only (non-commercial data).</b>' if t["research_only"] else ""
            parts.append(f'<p>Track <code>{slug}</code>. Data: <a href="{html.escape(t["url"])}">'
                         f"{html.escape(t['data'])}</a>, {html.escape(t['licence'])}.{ro} CI unit: "
                         f"<code>{html.escape(t['ci_unit'])}</code>. User model: {html.escape(t['user_model'])}.</p>")
        if not rows:
            parts.append("<p>No entries yet.</p>")
            continue
        parts.append('<div class="wrap"><table><thead><tr>' + "".join(f"<th>{html.escape(c)}</th>" for c in COLUMNS)
                     + "</tr></thead><tbody>")
        g = _gaze(rows)
        if g is not None:
            cpm = t["gaze_cpm"] if t else 20.0
            parts.append('<tr class="ref">' + _td(f"No-BCI reference: gaze typing ({cpm:.0f} chars/min)") + _td("type all")
                         + _td("n/a", "num") + _td(f"{g:.2f}", "num") + _td("n/a", "num") + _td("0.000", "num")
                         + _td("n/a", "num")
                         + _td("0.000", "num") + "".join(_td("") for _ in range(5)) + "</tr>")
        for r in rows:
            c = cells(r)
            ctl_cls = "ok" if r["controls_passed"] else "bad"
            sw_cls = "bad" if r["safe_wpm_status"] == "above-alpha" else ("ok" if r["safe_wpm_status"] == "certified" else "num")
            tds = ([_td(c[0]), _td(c[1]), _td(c[2], "num"), _td(c[3], "num"), _td(c[4], sw_cls)]
                   + [_td(x, "num") for x in c[5:8]] + [_td(c[8], ctl_cls)] + [_td(x) for x in c[9:]])
            parts.append("<tr>" + "".join(tds) + "</tr>")
        parts.append("</tbody></table></div>")
        notes = sorted({n for r in rows for n in r["notes"]})
        if t:
            notes = list(t["notes"]) + notes
        if notes:
            parts.append("<ul>" + "".join(f"<li>{html.escape(n)}</li>" for n in notes) + "</ul>")
    parts.append("</main></body></html>")
    return "\n".join(parts) + "\n"


def build(results_dir: str | PathLike[str] | list, out_dir: str | PathLike[str]) -> dict[str, Any]:
    results = load_results(results_dir)
    by = build_rows(results)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    payload = {"benchmark_version": BENCHMARK_VERSION, "tracks": {k: [{kk: vv for kk, vv in r.items() if kk != "ewpm_s"}
                                                                       for r in v] for k, v in by.items()}}
    (out / "leaderboard.json").write_text(json.dumps(payload, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    (out / "leaderboard.md").write_text(markdown(by), encoding="utf-8")
    (out / "index.html").write_text(page(by), encoding="utf-8")
    return {"n_results": len(results), "tracks": {k: len(v) for k, v in by.items()}, "out": str(out)}
