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
    Check the manifest, the trial coverage and the conformance gate (v0.1 tracks).
``check TRACK SUBMISSION``
    v0.2 tracks (P6-02): validate a submission against the split file
    (unit hashes, coverage, row format, controls present). No truth needed.
``truth TRACK --data PATH [--cache ... --sentences ...] --out truth.jsonl``
    v0.2 tracks: rebuild the local truth of the scored units from your
    download, checked against the split fingerprints. Never commit it.
``score SUBMISSION --truth truth.jsonl [--out result.json] [--B 2000]``
    Score a submission folder and write the result JSON (v0.1 tracks).
``score TRACK SUBMISSION (--data PATH | --truth truth.jsonl) [--out card.json]``
    v0.2 tracks (P6-02): validate, check the required controls and print
    the full score card (``docs/benchmark-submission.md``). Exit code 0
    only if all required controls pass.
``safe-wpm --trials trials.jsonl (--guard guard.json | --guarantee g.json | --method ltt --alpha A ...)``
    Safe WPM at a certified wrong-commit rate (P14-05; ``docs/safe-wpm.md``)
    from a per-trial JSON Lines file.
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


def _v02(args: list[str]) -> tuple[str, str] | None:
    from fidetype.benchmark.tracks import TRACKS as V02

    if len(args) == 2 and args[0] in V02:
        return args[0], args[1]
    if len(args) != 1:
        raise SystemExit("give SUBMISSION (v0.1) or TRACK SUBMISSION (v0.2 tracks: "
                         f"{', '.join(sorted(V02))})")
    return None


def _v02_truth(a, track: str) -> dict:
    from fidetype.benchmark import scorecard as SC

    if a.truth:
        return SC.read_truth(a.truth, track)
    if not a.data:
        raise SystemExit("give --data <your dataset copy> or --truth <truth.jsonl from `truth`>")
    rows = SC.build_truth(track, a.data, cache=a.cache, sentences=a.sentences)
    return {r["unit"]: r for r in rows}


def cmd_truth(a) -> int:
    from fidetype.benchmark import scorecard as SC

    rows = SC.build_truth(a.track, a.data, cache=a.cache, sentences=a.sentences)
    n = SC.write_truth(a.out, a.track, rows)
    print(f"{a.track}: {n} scored units -> {a.out} (local file with truth text: never commit it)", file=sys.stderr)
    return 0


def cmd_check(a) -> int:
    v = _v02(a.submission)
    if v is not None:
        from fidetype.benchmark import scorecard as SC
        from fidetype.benchmark.submission import SubmissionError

        try:
            rep = SC.check_submission(*v)
        except SubmissionError as e:
            _dump({"track": v[0], "ok": False, "error": str(e)}, None)
            return 2
        _dump(rep, None)
        return 0
    a.submission = a.submission[0]
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
    v = _v02(a.submission)
    if v is not None:
        from fidetype.benchmark import scorecard as SC
        from fidetype.benchmark.submission import SubmissionError

        try:
            res = SC.score(v[0], v[1], _v02_truth(a, v[0]), B=a.B, seed=a.seed, gate=a.gate)
        except SubmissionError as e:
            print(f"REJECTED: {e}", file=sys.stderr)
            return 2
        _dump(res, a.out)
        print(SC.score_card_text(res), file=sys.stderr)
        return 0 if res["status"] == "scored" else 1
    a.submission = a.submission[0]
    if not a.truth:
        raise SystemExit("--truth is required for v0.1 tracks")
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


def cmd_safe_wpm(a) -> int:
    import math

    from fidetype.benchmark.safe_wpm import (CorrectionRule, controls_from_sheet, format_line, guarantee_from_sheet,
                                             load_trials_jsonl, model_neural_s, safe_wpm)

    cols = load_trials_jsonl(a.trials)
    controls = None
    if a.guard:
        g = json.loads(Path(a.guard).read_text(encoding="utf-8"))
        sheet = g.get("sheet", g)
        guarantee = guarantee_from_sheet(sheet)
        controls = controls_from_sheet(sheet)
    elif a.guarantee:
        guarantee = json.loads(Path(a.guarantee).read_text(encoding="utf-8")) if Path(a.guarantee).exists()             else json.loads(a.guarantee)
    else:
        guarantee = {"method": a.method, "alpha": a.alpha, "delta": a.delta, "n_cal": a.n_cal}
    ns = cols["neural_s"]
    missing = [i for i, x in enumerate(ns) if math.isnan(x)]
    if missing and a.chars_per_min is None:
        print(f"{len(missing)} trial(s) have no neural_s; give --chars-per-min for the rate model", file=sys.stderr)
        return 2
    if missing:
        model = model_neural_s(cols["n_chars"], a.chars_per_min)
        ns = [model[i] if math.isnan(x) else x for i, x in enumerate(ns)]
        timing = (f"rate model {a.chars_per_min:g} chars/min" if len(missing) == len(ns) else
                  f"measured for {len(ns) - len(missing)} trials, rate model {a.chars_per_min:g} chars/min for "
                  f"{len(missing)}")
    else:
        timing = "measured per-trial durations (neural_s)"
    clusters = [{"cluster": c} for c in cols["cluster"]] if all(cols["cluster"]) else None
    v02 = {}
    if a.metric_version == "0.2":  # P14-26: proposed, not adopted
        sp = cols["speech_s"]
        v02 = {"committed_words": cols["committed_words"], "complete": cols["complete"],
               "penalty_chars": cols["penalty_chars"]}
        if not any(math.isnan(x) for x in sp):
            v02.update(speech_s=sp, speech_timing="per-trial speech_s")
    ok = cols["correct_v02"] if a.metric_version == "0.2" else cols["correct"]
    res = safe_wpm(cols["committed"], ok, cols["n_words"], cols["n_chars"], ns, guarantee=guarantee,
                   rule=CorrectionRule(name=a.correction), timing=timing, clusters=clusters,
                   ci_unit="cluster" if clusters else None, controls=controls, B=a.B, seed=a.seed,
                   metric_version=a.metric_version, **v02)
    _dump(res, a.out)
    print(format_line(res), file=sys.stderr)
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
    p = sub.add_parser("check", help="v0.1: SUBMISSION [--truth]; v0.2 tracks: TRACK SUBMISSION")
    p.add_argument("submission", nargs="+", metavar="[TRACK] SUBMISSION")
    p.add_argument("--truth", default=None)
    p.set_defaults(fn=cmd_check)
    p = sub.add_parser("truth", help="v0.2 tracks: rebuild the local truth file (never commit it)")
    p.add_argument("track")
    p.add_argument("--data", required=True)
    p.add_argument("--cache", default=None, help="toronto-semg: window cache folder")
    p.add_argument("--sentences", default=None, help="toronto-semg: eng_tatoeba_heldout.txt")
    p.add_argument("--out", required=True)
    p.set_defaults(fn=cmd_truth)
    p = sub.add_parser("score", help="v0.1: SUBMISSION --truth; v0.2 tracks: TRACK SUBMISSION (--data | --truth)")
    p.add_argument("submission", nargs="+", metavar="[TRACK] SUBMISSION")
    p.add_argument("--truth", default=None)
    p.add_argument("--data", default=None, help="v0.2: your dataset copy (truth is rebuilt and checked)")
    p.add_argument("--cache", default=None, help="v0.2 toronto-semg: window cache folder")
    p.add_argument("--sentences", default=None, help="v0.2 toronto-semg: eng_tatoeba_heldout.txt")
    p.add_argument("--out", default=None)
    p.add_argument("--B", type=int, default=2000)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--no-gate", action="store_true", help="v0.1: score even if the conformance gate fails")
    p.add_argument("--gate", action="store_true", help="v0.2 stream submissions: reject below trust-ready")
    p.set_defaults(fn=cmd_score)
    p = sub.add_parser("safe-wpm", help="safe WPM at a certified wrong-commit rate (P14-05; docs/safe-wpm.md)")
    p.add_argument("--trials", required=True, help="per-trial JSON Lines: committed, correct, truth (or n_words + "
                   "n_chars), neural_s, optional cluster")
    g = p.add_mutually_exclusive_group()
    g.add_argument("--guard", default=None, help="a saved drop-in TrustGuard JSON (guard.save): alpha, delta, n_cal "
                   "and null controls from its sheet")
    g.add_argument("--guarantee", default=None, help="guarantee JSON (file or inline): method, alpha, delta, n_cal")
    p.add_argument("--method", default="none", choices=("none", "crc", "ltt"))
    p.add_argument("--alpha", type=float, default=None)
    p.add_argument("--delta", type=float, default=None)
    p.add_argument("--n-cal", type=int, default=None)
    p.add_argument("--chars-per-min", type=float, default=None, help="rate model for trials without neural_s")
    p.add_argument("--correction", default="rewrite", choices=("rewrite", "none"))
    p.add_argument("--metric-version", default="0.1", choices=("0.1", "0.2"),
                   help="0.1 (default, the headline) or 0.2 (PROPOSED, not adopted: prefix credit and speech time; "
                   "docs/safe-wpm-v0.2-proposal.md)")
    p.add_argument("--out", default=None)
    p.add_argument("--B", type=int, default=2000)
    p.add_argument("--seed", type=int, default=0)
    p.set_defaults(fn=cmd_safe_wpm)
    p = sub.add_parser("verify", add_help=False,
                       help="tracks v0.2 (P6-01): check a local dataset copy against the split hashes; "
                       "same as `python -m fidetype.benchmark.tracks verify`")
    p.add_argument("rest", nargs=argparse.REMAINDER)
    p.set_defaults(fn=lambda a: __import__("fidetype.benchmark.tracks", fromlist=["main"]).main(["verify", *a.rest]))
    p = sub.add_parser("leaderboard")
    p.add_argument("--results", nargs="+", default=["benchmark/results/v0.1", "benchmark/results/v0.2"])
    p.add_argument("--out", default="benchmark/site")
    p.set_defaults(fn=cmd_leaderboard)
    a = ap.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    raise SystemExit(main())
