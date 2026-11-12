"""Score a submission folder end to end (one command).

    python -m fidetype.benchmark score <submission> --truth truth.jsonl --out result.json

Steps: read the manifest; load the committed split; check the local truth
against the split hashes; check every stream file with the conformance
suite (entry gate: ``trust-ready``); read the outputs; score them and the
controls; write the result JSON.
"""

from __future__ import annotations

from collections import Counter
from os import PathLike
from pathlib import Path
from typing import Any

from fidetype.benchmark.prepare import read_truth, text_hash
from fidetype.benchmark.registry import get_track
from fidetype.benchmark.scoring import CONFORMANCE_GATE, DEFAULT_B, build_result, score_trials
from fidetype.benchmark.splits import load_split
from fidetype.benchmark.submission import (
    CONTROL_KINDS,
    SubmissionError,
    load_manifest,
    stream_files,
    trial_output,
)


def check_truth(track: str, truth: dict[str, dict[str, Any]], ids: list[str]) -> None:
    """Every scored id must have a truth whose hash matches the split file."""
    split = load_split(track)
    want = {r["id"]: r["text_sha256"] for r in split.scored}
    bad = [i for i in ids if i not in truth or text_hash(truth[i]["text"]) != want[i]]
    if bad:
        raise SubmissionError(f"truth file does not match the split file for {len(bad)} trial(s), e.g. {bad[:3]}; "
                              "rebuild it with `python -m fidetype.benchmark prepare`")


def conformance_gate(files: dict[str, Path], truth: dict[str, dict[str, Any]], level: str = CONFORMANCE_GATE) -> dict[str, Any]:
    """Run the conformance suite on every stream file. The weakest file sets the level."""
    from fidetype.conformance import check_file
    from fidetype.conformance.checks import LEVELS

    order = {"none": -1, **{lv: i for i, lv in enumerate(LEVELS)}}
    levels: Counter = Counter()
    worst, worst_file, fails = "provenance", None, []
    for tid, path in files.items():
        rep = check_file(path, truth=[truth[tid]["text"]] if tid in truth else None)
        lv = rep.level
        levels[lv] += 1
        if order[lv] < order[worst]:
            worst, worst_file = lv, path.name
        if order[lv] < order[level] and len(fails) < 5:
            fails.append({"file": path.name, "level": lv,
                          "failed": [r.check_id for r in rep.results if r.status == "fail"][:6]})
    return {"level": worst if files else "none", "gate": level, "passed": bool(files) and order[worst] >= order[level],
            "n_files": len(files), "levels": dict(levels), "worst_file": worst_file, "examples": fails,
            "checked": "stream files of the submission"}


def score_submission(folder: str | PathLike[str], truth_path: str | PathLike[str], *, B: int = DEFAULT_B,
                     seed: int = 0, gate: bool = True) -> dict[str, Any]:
    folder = Path(folder)
    man = load_manifest(folder)
    track = get_track(man.track)
    split = load_split(track.slug)
    ids = split.ids(track.scored_split)
    truth = read_truth(truth_path)
    check_truth(track.slug, truth, ids)
    files = stream_files(folder / "streams")
    missing = [i for i in ids if i not in files]
    if missing:
        raise SubmissionError(f"{len(missing)} scored trial(s) have no stream file, e.g. {missing[:3]}")
    files = {i: files[i] for i in ids}
    conf = conformance_gate(files, truth) if gate else {"level": "not checked", "passed": None}
    texts = {i: truth[i]["text"] for i in ids}
    clusters = split.clusters(track.scored_split)
    real = score_trials(track, {i: trial_output(p) for i, p in files.items()}, texts, clusters, ids)
    controls = {}
    for kind in CONTROL_KINDS:
        cf = stream_files(folder / "controls" / kind)
        if cf:
            have = [i for i in ids if i in cf]
            controls[kind] = score_trials(track, {i: trial_output(cf[i]) for i in have}, texts, clusters, have)
    cal_name = man.guarantee.get("calibration_split")
    res = build_result(
        track, real, decoder=man.decoder, policy=man.policy, guarantee=man.guarantee, controls=controls,
        conformance=conf, scored_from="stream-submission", sources=[str(folder.name)],
        notes=[man.notes] if man.notes else [], B=B, seed=seed,
        n_cal_split=split.counts.get(cal_name) if cal_name else None,
    )
    res["submitter"] = man.submitter
    res["status"] = "scored" if (conf.get("passed") or not gate) else "rejected: conformance gate"
    return res
