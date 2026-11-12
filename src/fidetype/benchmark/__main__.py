"""Command line of the open benchmark: ``python -m fidetype.benchmark``.

Sub-commands:

``tracks``
    List the tracks, their datasets and licences.
``info TRACK``
    Print the dataset entry (source, licence, version, checksum, download
    steps), the split counts and the user model of a track.
``prepare TRACK --data PATH [--sentences FILE] [--out truth.jsonl]``
    Rebuild the truth of a track from your downloaded data, check it
    against the committed split file, and write it (local file; never
    commit it). Without ``--out`` it only verifies.
``check SUBMISSION [--truth truth.jsonl]``
    Check the manifest, the trial coverage and the conformance gate.
``score SUBMISSION --truth truth.jsonl [--out result.json] [--B 2000]``
    Score a submission folder and write the result JSON.
``leaderboard [--results DIR] [--out DIR]``
    Build the static leaderboard (``index.html``, ``leaderboard.json``,
    ``leaderboard.md``).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from fidetype.benchmark.registry import DATASETS, TRACKS, get_track


def _dump(obj, out: str | None) -> None:
    from fidetype.benchmark.scoring import to_jsonable

    text = json.dumps(to_jsonable(obj), indent=1, ensure_ascii=False)
    if out in (None, "-"):
        sys.stdout.write(text + "\n")
    else:
        Path(out).parent.mkdir(parents=True, exist_ok=True)
        Path(out).write_text(text + "\n", encoding="utf-8")


def cmd_tracks(_a) -> int:
    for slug, t in TRACKS.items():
        ds = DATASETS[t.dataset]
        flag = " [research only]" if t.research_only else ""
        print(f"{slug:24s} {t.modality:14s} {ds.licence:12s}{flag}  {t.title}")
    return 0


def cmd_info(a) -> int:
    from fidetype.benchmark.splits import load_split

    t = get_track(a.track)
    ds = DATASETS[t.dataset]
    sp = load_split(t.slug)
    _dump({"track": t.to_dict(), "dataset": ds.to_dict(), "split_counts": sp.counts, "split_rule": sp.rule}, None)
    return 0


def cmd_prepare(a) -> int:
    from fidetype.benchmark.prepare import build_trials, write_truth
    from fidetype.benchmark.splits import load_split, verify

    t = get_track(a.track)
    print(DATASETS[t.dataset].notice, file=sys.stderr)
    trials = build_trials(t.slug, a.data, a.sentences)
    rep = verify(load_split(t.slug), trials)
    print(rep.summary(), file=sys.stderr)
    if not rep.ok:
        return 1
    if a.out:
        scored = {t.scored_split} | {r for r in ("val", "cal")}
        n = write_truth(trials, a.out, splits=tuple(sorted(scored)))
        print(f"wrote {n} trials to {a.out} (local file: do not commit it)", file=sys.stderr)
    return 0


def cmd_check(a) -> int:
    from fidetype.benchmark.harness import conformance_gate
    from fidetype.benchmark.prepare import read_truth
    from fidetype.benchmark.splits import load_split
    from fidetype.benchmark.submission import load_manifest, stream_files

    man = load_manifest(a.submission)
    t = get_track(man.track)
    ids = load_split(t.slug).ids(t.scored_split)
    files = stream_files(Path(a.submission) / "streams")
    missing = [i for i in ids if i not in files]
    truth = read_truth(a.truth) if a.truth else {}
    gate = conformance_gate({i: files[i] for i in ids if i in files}, truth)
    out = {"track": t.slug, "n_scored": len(ids), "missing": len(missing), "missing_examples": missing[:5],
           "conformance": gate, "ok": not missing and gate["passed"]}
    _dump(out, None)
    return 0 if out["ok"] else 1


def cmd_score(a) -> int:
    from fidetype.benchmark.harness import score_submission

    res = score_submission(a.submission, a.truth, B=a.B, seed=a.seed, gate=not a.no_gate)
    _dump(res, a.out)
    m = res["metrics"]
    print(f"{res['track']}: CER {m['cer']['value']:.3f}  eWPM {m['ewpm']['value']:.2f} "
          f"(no-BCI {m['gaze_ewpm']['value']:.2f})  wrong-commit {m['wrong_commit_rate']['value']:.3f}  "
          f"controls {'passed' if res['controls']['passed'] else 'NOT passed'}  status {res['status']}", file=sys.stderr)
    return 0 if res["status"] == "scored" else 1


def cmd_leaderboard(a) -> int:
    from fidetype.benchmark.leaderboard import build

    info = build(a.results, a.out)
    print(json.dumps(info), file=sys.stderr)
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m fidetype.benchmark", description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("tracks").set_defaults(fn=cmd_tracks)
    p = sub.add_parser("info")
    p.add_argument("track")
    p.set_defaults(fn=cmd_info)
    p = sub.add_parser("prepare")
    p.add_argument("track")
    p.add_argument("--data", required=True, help="cache dir (MEG, EMG) or t15_copyTask.pkl (B2T)")
    p.add_argument("--sentences", default=None, help="Tatoeba held-out list (Toronto only)")
    p.add_argument("--out", default=None)
    p.set_defaults(fn=cmd_prepare)
    p = sub.add_parser("check")
    p.add_argument("submission")
    p.add_argument("--truth", default=None)
    p.set_defaults(fn=cmd_check)
    p = sub.add_parser("score")
    p.add_argument("submission")
    p.add_argument("--truth", required=True)
    p.add_argument("--out", default=None)
    p.add_argument("--B", type=int, default=2000)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--no-gate", action="store_true", help="score even if the conformance gate fails")
    p.set_defaults(fn=cmd_score)
    p = sub.add_parser("leaderboard")
    p.add_argument("--results", default="benchmark/results/v0.1")
    p.add_argument("--out", default="benchmark/site")
    p.set_defaults(fn=cmd_leaderboard)
    a = ap.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    raise SystemExit(main())
