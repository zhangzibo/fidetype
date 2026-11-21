"""Submission format v0.2 and the one-command scorer of the v0.2 tracks (roadmap P6-02).

    python -m fidetype.benchmark check <track> <submission>
    python -m fidetype.benchmark truth <track> --data <path> --out truth.jsonl      # local file: never commit
    python -m fidetype.benchmark score <track> <submission> (--data <path> | --truth truth.jsonl) [--out card.json]

Full guide: ``docs/benchmark-submission.md``.

Submission folder (schema ``fidetype.benchmark.submission/0.2``)
-----------------------------------------------------------------
::

    submission.json          manifest: track, decoder, policy, guarantee, regime, controls, coverage
    units.jsonl              one row per scored unit (NTS-derived), or
    streams/<unit>.jsonl     one NTS stream per scored unit (.jsonl / .npz; v0.1 hypothesis-event rules)
    controls/shuffled.jsonl  the same decoder + policy on time-shuffled input (or controls/shuffled/<unit>.jsonl)
    controls/zeros.jsonl     the same decoder + policy on all-zero (null) input (or controls/zeros/<unit>.jsonl)

A **unit key** is the salted unit hash ``h`` of the track split file
(``splits/tracks-v0.2/<track>.json``, entries with the scored unit set and
split). The emg2qwerty track scores prompts inside test sessions: the key
is ``<session h>#<prompt index>``.

One row of ``units.jsonl`` (optional first row: a header with ``schema``)::

    {"unit": "3f9c0b6a1d2e4f58", "action": "commit",
     "nbest": [{"text": "the decoded text", "score": -1.2}, ...],
     "offer_k": 3, "score_semantics": "logprob", "latency_s": 0.31}

- ``action``: ``commit``, ``offer`` or ``abstain`` (the trust decision).
- ``nbest[0].text`` is the top-1 text (CER / WER); ``nbest[:offer_k]``
  are the choices of an OFFER.
- Text is in the track text space: words (speech tracks), characters
  (handwriting, sEMG sentences, MEG), or space-separated W3C
  ``KeyboardEvent.code`` names (key tracks ``kt-semg``, ``emg2qwerty``).
- Only the keys above (and keys that start with ``x-``) are allowed. So a
  row cannot carry truth text by accident (NTS spec 5.3 leakage rule).

The truth stays local. ``truth`` rebuilds it from your own download and
checks every unit against the split fingerprints. Timing (neural input
time) comes from the truth (the dataset), never from the submission.

Score card
----------
The scorer reuses :mod:`fidetype.benchmark.scoring` (CER / WER, eWPM vs the
no-BCI reference, wrong-commit, error among commits, commit rate, silent
errors, cluster-bootstrap CIs, controls, guarantee echo, safe WPM). The CI
cluster is the track CI unit (the split group hash). On key tracks CER is
the key error rate (one character per key).

Required controls (P6 rule): ``shuffled`` and ``zeros`` must each give a
higher top-1 CER than real input (lower CI bound of the paired gap > 0),
and the commit rate on zeros must be at most 5 % (``null_commit``). The
card status is ``scored`` only when all three pass; else
``scored: controls missing`` or ``scored: controls failed`` (exit code 1).
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass, field
from os import PathLike
from pathlib import Path
from typing import Any, Sequence

from fidetype.benchmark import overlap as OV
from fidetype.benchmark import tracks as TR
from fidetype.benchmark.registry import Track, UserModel
from fidetype.benchmark.scoring import DEFAULT_B, build_result, score_trials
from fidetype.benchmark.submission import (
    ACTIONS,
    CONTROL_KINDS,
    DEFAULT_OFFER_K,
    SUBMISSION_SCHEMA as SUBMISSION_SCHEMA_V01,
    Manifest,
    SubmissionError,
    TrialOutput,
    stream_files,
    trial_output,
)

SUBMISSION_SCHEMA = "fidetype.benchmark.submission/0.2"
UNITS_SCHEMA = "fidetype.benchmark.units/0.2"
TRUTH_SCHEMA = "fidetype.benchmark.truth/0.2"
RESULT_SCHEMA_V02 = "fidetype.benchmark.result/0.2"
SCORER_VERSION = "0.2"
REGIMES = ("cross-session", "session-calibrated", "cross-subject", "personalised", "other")
ROW_KEYS = {"unit", "action", "nbest", "offer_k", "score_semantics", "latency_s", "stream"}
#: Prompts with fewer key presses are not scored units (emg2qwerty).
E2Q_MIN_KEYS = 3
_UNIT_RE = re.compile(r"^[0-9a-f]{16}(#\d+)?$")


# ---------------------------------------------------------------------------
# Scoring parameters per track (text space, neural input rate)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ScoreSpec:
    """How the scorer treats one v0.2 track. Values are data: change only with a new scorer version."""

    normalizer: str
    #: Neural input rate of the eWPM user model (chars or keys per minute) and its source.
    chars_per_min: float
    rate_source: str
    key_track: bool = False
    #: Unit keys are ``<parent h>#<k>`` (sub-units of a scored parent unit).
    sub_units: bool = False
    #: Scoring targets a submission may declare (``submission.json`` ``target``), first = default. Empty: the
    #: track has one target and a manifest must not name one (P11-13).
    targets: tuple[str, ...] = ()


#: Scoring targets (P11-13): {name: (version, normalizer applied to truth AND hypotheses, rule)}.
TARGETS: dict[str, tuple[str, str, str]] = {
    "raw_keys": ("raw-keys/1", "keycodes",
                 "the key sequence as typed: one character per key code; Backspace and Enter are keys"),
    "intended_text": ("intended-text/1", "keycodes_intended",
                      "Backspace applied (registry.keycodes_to_intended_text, rule intended-text/1): a character "
                      "key appends, Backspace removes the last character if any, Enter is ignored, then runs of "
                      "spaces are joined and the ends stripped"),
}


SCORE_SPECS: dict[str, ScoreSpec] = {
    "b2t25-t15": ScoreSpec("words", 159.2741387635318, "measured T15 speech rate, 125k trials (v0.1 track)"),
    "b2t24-t12": ScoreSpec("words", 303.98331077672157,
                           "measured T12 speech rate of the decoder-train trials "
                           "(experiments/2026-11-13-confirmatory-t12-v2/results/prep.json)"),
    "willett-hw": ScoreSpec("none", 67.64021832754295,
                            "measured: characters / (go cue to sentence end) over the 254 test trials"),
    "toronto-semg": ScoreSpec("none", 60.0 / 0.792, "one key per 0.792 s (median inter-key interval; v0.1 track)"),
    "kt-semg": ScoreSpec("keycodes", 390.5578319125804,
                         "measured: keys / (first to last key + one median inter-key interval) over the 172 test "
                         "bursts", key_track=True),
    "spanishbcbl-meg": ScoreSpec("char28", 152.0, "Brain2Qwerty v1 typing rate (v0.1 track)"),
    "emg2qwerty": ScoreSpec("keycodes", 301.3306670286988,
                            "measured: keys / (first to last key-down time) over the 15867 scored test prompts",
                            key_track=True, sub_units=True, targets=("raw_keys", "intended_text")),
}


def resolve_target(slug: str, target: str | None) -> str | None:
    """The scoring target of a submission: its declared ``target``, else the track default (None: no targets)."""
    s = SCORE_SPECS[slug]
    if target is None:
        return s.targets[0] if s.targets else None
    if target not in s.targets:
        allowed = f"one of {list(s.targets)}" if s.targets else "absent (this track has one target)"
        raise SubmissionError(f"submission.json: target {target!r} is not valid for {slug}; it must be {allowed}")
    return target


def target_block(target: str) -> dict[str, str]:
    """The ``target`` block of a score card (P11-13)."""
    version, norm, rule = TARGETS[target]
    return {"name": target, "version": version, "normalizer": norm, "rule": rule}


def scoring_track(slug: str, target: str | None = None) -> Track:
    """A :class:`~fidetype.benchmark.registry.Track` view of a v0.2 track for :mod:`.scoring`.

    The bootstrap cluster key is ``group`` (the split group hash); the MEG
    track keeps its crossed sentence x participant bootstrap. ``target``
    (P11-13) selects the normalizer of a track with several targets.
    """
    t = TR.get_track(slug)
    s = SCORE_SPECS[slug]
    tgt = resolve_target(slug, target)
    norm = TARGETS[tgt][1] if tgt else s.normalizer
    ci = "two_way:sentence,group" if t.ci_unit.startswith("two_way:") else "group"
    um = UserModel(name=f"aac-gaze-v1 @ {s.chars_per_min:.2f} {'keys' if s.key_track else 'chars'}/min",
                   config={"chars_per_min": float(s.chars_per_min)}, note=s.rate_source)
    return Track(slug=t.slug, title=t.title, dataset=t.dataset, modality=t.modality, language=t.language,
                 split_file=t.split_file, normalizer=norm, ci_unit=ci, user_model=um,
                 scored_split=t.scored_split, open_splits=t.open_splits, research_only=t.research_only,
                 notes=t.notes)


def scored_entries(split: dict[str, Any]) -> dict[str, dict[str, str]]:
    """{unit hash: split entry} of the scored unit set and split, in file order."""
    t = TR.get_track(split["track"])
    return {e["h"]: e for e in split["entries"] if e["u"] == t.scored_set and e["s"] == t.scored_split}


# ---------------------------------------------------------------------------
# Manifest
# ---------------------------------------------------------------------------


@dataclass
class ManifestV02:
    base: Manifest
    regime: str
    controls: dict[str, str] = field(default_factory=dict)
    coverage: dict[str, Any] = field(default_factory=dict)
    raw: dict[str, Any] = field(default_factory=dict)
    #: The declared scoring target (P11-13), or None (the track default).
    target: str | None = None
    #: The parsed ``training_data`` declaration (P6-10): None (missing), {"none": True} or the listed sources.
    training_data: dict[str, Any] | None = None

    @property
    def track(self) -> str:
        return self.base.track


def manifest_dict(track: str, decoder: dict[str, Any], *, policy: dict[str, Any] | None = None,
                  guarantee: dict[str, Any] | None = None, regime: str, controls: dict[str, str] | None = None,
                  coverage: dict[str, Any] | None = None, submitter: dict[str, Any] | None = None,
                  notes: str = "", target: str | None = None, training_data: Any = None) -> dict[str, Any]:
    """Build a v0.2 manifest dict (validated by :func:`parse_manifest`).

    ``training_data`` (P6-10): ``"none"`` or a declaration dict (:mod:`fidetype.benchmark.overlap`).
    Without it the score card says the overlap check was ``not checked``."""
    d = {"schema": SUBMISSION_SCHEMA, "track": track, "benchmark_version": TR.TRACKS_VERSION, "decoder": decoder,
         "policy": policy or {}, "guarantee": guarantee or {"method": "none"}, "regime": regime,
         "controls": controls or {}, "submitter": submitter or {}, "notes": notes}
    if coverage:
        d["coverage"] = coverage
    if target is not None:
        d["target"] = target
    if training_data is not None:
        d["training_data"] = training_data
    parse_manifest(d)
    return d


def parse_manifest(d: dict[str, Any], folder: str | PathLike[str] | None = None) -> ManifestV02:
    if d.get("schema") != SUBMISSION_SCHEMA:
        raise SubmissionError(f"submission.json: schema must be {SUBMISSION_SCHEMA!r}")
    if d.get("track") not in TR.TRACKS:
        raise SubmissionError(f"submission.json: track must be one of {sorted(TR.TRACKS)}")
    base = Manifest.from_dict({**d, "schema": SUBMISSION_SCHEMA_V01})
    base.benchmark_version = str(d.get("benchmark_version", TR.TRACKS_VERSION))
    regime = d.get("regime")
    if regime not in REGIMES:
        raise SubmissionError(f"submission.json: regime must be one of {REGIMES}")
    ctl = d.get("controls") or {}
    if not isinstance(ctl, dict) or any(k not in CONTROL_KINDS for k in ctl):
        raise SubmissionError(f"submission.json: controls is a dict with keys from {CONTROL_KINDS} "
                              "(how each control input was made)")
    cov = d.get("coverage") or {}
    if cov and not (isinstance(cov, dict) and isinstance(cov.get("subset"), str) and cov["subset"].strip()):
        raise SubmissionError("submission.json: coverage must be {'subset': '<why some units are missing>'}")
    tgt = d.get("target")
    if tgt is not None:
        resolve_target(d["track"], tgt)
    td = OV.parse_declaration(d.get("training_data"), folder)
    return ManifestV02(base, regime, dict(ctl), dict(cov), dict(d), tgt, td)


def load_manifest(folder: str | PathLike[str]) -> ManifestV02:
    p = Path(folder) / "submission.json"
    if not p.is_file():
        raise SubmissionError(f"no submission.json in {folder}")
    return parse_manifest(json.loads(p.read_text(encoding="utf-8")), folder)


# ---------------------------------------------------------------------------
# Unit rows
# ---------------------------------------------------------------------------


def unit_row(unit: str, texts: Sequence[str], scores: Sequence[float] | None = None, *, action: str = "commit",
             offer_k: int | None = None, score_semantics: str | None = None,
             latency_s: float | None = None) -> dict[str, Any]:
    """One ``units.jsonl`` row (see the module docstring)."""
    if action not in ACTIONS:
        raise ValueError(f"action must be one of {ACTIONS}")
    sc = list(scores) if scores is not None else [None] * len(texts)
    nb = []
    for t, s in zip(texts, sc):
        x: dict[str, Any] = {"text": str(t)}
        if s is not None and math.isfinite(float(s)):
            x["score"] = round(float(s), 6)
        nb.append(x)
    r: dict[str, Any] = {"unit": unit, "action": action, "nbest": nb}
    if offer_k is not None:
        r["offer_k"] = int(offer_k)
    if score_semantics:
        r["score_semantics"] = score_semantics
    if latency_s is not None:
        r["latency_s"] = round(float(latency_s), 4)
    return r


def write_units(path: str | PathLike[str], rows: Sequence[dict[str, Any]], *, track: str,
                kind: str = "real") -> int:
    """Write a ``units.jsonl`` (or ``controls/<kind>.jsonl``) file with a header row."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        f.write(json.dumps({"schema": UNITS_SCHEMA, "track": track, "kind": kind}) + "\n")
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    return len(rows)


def write_submission(folder: str | PathLike[str], manifest: dict[str, Any], rows: Sequence[dict[str, Any]],
                     controls: dict[str, Sequence[dict[str, Any]]] | None = None) -> Path:
    """Write a complete v0.2 submission folder (manifest, units, controls)."""
    m = parse_manifest(manifest)
    out = Path(folder)
    out.mkdir(parents=True, exist_ok=True)
    (out / "submission.json").write_text(json.dumps(manifest, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    write_units(out / "units.jsonl", rows, track=m.track)
    for kind, rs in (controls or {}).items():
        if kind not in CONTROL_KINDS:
            raise ValueError(f"control kind must be one of {CONTROL_KINDS}")
        write_units(out / "controls" / f"{kind}.jsonl", rs, track=m.track, kind=kind)
    return out


def _row_output(r: dict[str, Any], where: str) -> TrialOutput:
    bad = [k for k in r if k not in ROW_KEYS and not str(k).startswith("x-")]
    if bad:
        raise SubmissionError(f"{where}: keys {bad} are not allowed (allowed: {sorted(ROW_KEYS)} and 'x-*')")
    u = r.get("unit")
    if not isinstance(u, str) or not _UNIT_RE.match(u):
        raise SubmissionError(f"{where}: 'unit' must be a 16-hex unit hash (or '<hash>#<n>'), got {u!r}")
    a = r.get("action", "commit")
    if a not in ACTIONS:
        raise SubmissionError(f"{where}: action must be one of {ACTIONS}, not {a!r}")
    nb = r.get("nbest", [])
    if not isinstance(nb, list) or any(not isinstance(x, dict) or not isinstance(x.get("text"), str) for x in nb):
        raise SubmissionError(f"{where}: nbest must be a list of {{'text': str, 'score': number}}")
    if a in ("commit", "offer") and not nb:
        raise SubmissionError(f"{where}: a {a} needs at least one nbest text")
    k = r.get("offer_k", DEFAULT_OFFER_K)
    if not isinstance(k, int) or k < 1:
        raise SubmissionError(f"{where}: offer_k must be an integer >= 1")
    sc = nb[0].get("score") if nb else None
    return TrialOutput(u, [x["text"] for x in nb], a, k, score=sc, score_semantics=r.get("score_semantics"))


def read_units(path: str | PathLike[str]) -> tuple[dict[str, TrialOutput], dict[str, Any]]:
    """Read a units file: ({unit key: output}, {"n_rows", "latency_s": [...], "header": {...}})."""
    p = Path(path)
    outs: dict[str, TrialOutput] = {}
    lat: list[float] = []
    header: dict[str, Any] = {}
    for ln, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        r = json.loads(line)
        if "schema" in r and "unit" not in r:
            if r["schema"] != UNITS_SCHEMA:
                raise SubmissionError(f"{p.name}: header schema must be {UNITS_SCHEMA!r}")
            header = r
            continue
        o = _row_output(r, f"{p.name}:{ln}")
        if o.trial_id in outs:
            raise SubmissionError(f"{p.name}:{ln}: duplicate unit {o.trial_id}")
        outs[o.trial_id] = o
        if isinstance(r.get("latency_s"), (int, float)):
            lat.append(float(r["latency_s"]))
    return outs, {"n_rows": len(outs), "latency_s": lat, "header": header}


def read_outputs(folder: Path, kind: str = "real") -> tuple[dict[str, TrialOutput], dict[str, Any]] | None:
    """Real outputs (``units.jsonl`` or ``streams/``) or one control (``controls/<kind>.jsonl`` or folder)."""
    if kind == "real":
        jl, sd = folder / "units.jsonl", folder / "streams"
    else:
        jl, sd = folder / "controls" / f"{kind}.jsonl", folder / "controls" / kind
    if jl.is_file() and sd.is_dir() and stream_files(sd):
        raise SubmissionError(f"give {jl.name} or {sd.name}/, not both")
    if jl.is_file():
        o, info = read_units(jl)
        info["format"] = "units-jsonl"
        return o, info
    files = stream_files(sd)
    if files:
        outs = {}
        for key, p in files.items():
            if not _UNIT_RE.match(key):
                raise SubmissionError(f"{sd.name}/{p.name}: the file name must be the unit key")
            o = trial_output(p)
            outs[key] = o
        return outs, {"n_rows": len(outs), "latency_s": [], "format": "nts-streams", "files": files}
    return None


# ---------------------------------------------------------------------------
# Check (no truth needed)
# ---------------------------------------------------------------------------


def _parent(key: str) -> str:
    return key.split("#", 1)[0]


def check_keys(track: str, keys: Sequence[str], scored: dict[str, Any], where: str) -> dict[str, Any]:
    spec = SCORE_SPECS[track]
    bad_form = [k for k in keys if ("#" in k) != spec.sub_units]
    if bad_form:
        form = "'<session hash>#<prompt index>'" if spec.sub_units else "the 16-hex unit hash"
        raise SubmissionError(f"{where}: unit keys of {track} are {form}; e.g. {bad_form[:2]}")
    unknown = sorted({_parent(k) for k in keys if _parent(k) not in scored})
    if unknown:
        raise SubmissionError(f"{where}: {len(unknown)} unit(s) are not scored units of {track} "
                              f"(test split), e.g. {unknown[:3]}")
    covered = {_parent(k) for k in keys}
    missing = [h for h in scored if h not in covered]
    return {"n_rows": len(keys), "n_parent_units": len(scored), "n_parent_covered": len(covered),
            "missing_parent_units": len(missing), "missing_examples": missing[:5]}


def check_submission(track: str, folder: str | PathLike[str], split: dict[str, Any] | None = None) -> dict[str, Any]:
    """Validate a submission against the committed split, without truth. Raises :class:`SubmissionError`."""
    folder = Path(folder)
    man = load_manifest(folder)
    if man.track != track:
        raise SubmissionError(f"submission.json names track {man.track!r}, not {track!r}")
    split = split or TR.load_split(track)
    scored = scored_entries(split)
    real = read_outputs(folder, "real")
    if real is None:
        raise SubmissionError("no units.jsonl and no streams/ folder")
    outs, info = real
    rep: dict[str, Any] = {"track": track, "format": info["format"], "regime": man.regime,
                           "research_only": TR.get_track(track).research_only, **check_keys(track, list(outs), scored, "units")}
    if rep["missing_parent_units"] and not man.coverage:
        raise SubmissionError(f"{rep['missing_parent_units']} scored unit(s) have no output, e.g. "
                              f"{rep['missing_examples'][:3]}; cover every unit or declare coverage.subset")
    rep["coverage"] = {"partial": bool(rep["missing_parent_units"]), **man.coverage}
    ctl: dict[str, Any] = {}
    for kind in CONTROL_KINDS:
        c = read_outputs(folder, kind)
        if c is None:
            ctl[kind] = {"present": False}
            continue
        co, _ = c
        check_keys(track, list(co), scored, f"controls/{kind}")
        miss = [k for k in outs if k not in co]
        ctl[kind] = {"present": True, "n_rows": len(co), "missing_units": len(miss),
                     "basis": man.controls.get(kind, "not stated")}
    rep["controls"] = ctl
    rep["controls_complete"] = all(c["present"] and c["missing_units"] == 0 for c in ctl.values())
    # P6-10: train / test overlap by unit id and partition (the text check needs the truth: `score`).
    rep["overlap_check"] = OV.check_overlap(track, man.training_data, list(outs), None, split=split)
    rep["ok"] = True
    return rep


# ---------------------------------------------------------------------------
# Truth (local; rebuilt from the user's download and checked against the split)
# ---------------------------------------------------------------------------


def _b2t25_durations(pkl: str) -> dict[int, float]:
    from fidetype.adapters.b2t25 import load_copytask

    out = {}
    for t in load_copytask(pkl, verify=True):
        d = getattr(t, "speech_duration_s", None)
        if d is not None and math.isfinite(float(d)):
            out[int(t.index)] = float(d)
    return out


def _t12_bins(files: set[str]) -> dict[tuple[str, int], int]:
    from scipy.io import loadmat

    out = {}
    for f in sorted(files):
        d = loadmat(f, variable_names=["tx1"])
        for i in range(d["tx1"].shape[1]):
            out[(f, i)] = int(d["tx1"][0, i].shape[0])
    return out


def _kt_key_times(units: Sequence[TR.LocalUnit], runs: dict[str, TR.LocalUnit]) -> dict[str, list[float]]:
    from fidetype.adapters.kt_semg import parse_keys

    out: dict[str, list[float]] = {}
    for u in units:
        r = u.ref["run"]
        if r not in out:
            out[r] = [kp.unix_s for kp in parse_keys(Path(runs[r].ref["keys"]).read_bytes())]
    return out


def _e2q_prompts(path: str) -> list[tuple[int, str, float]]:
    """(prompt index, key codes, neural_s) of the scored prompts of one session (in-vocabulary key presses)."""
    from fidetype.adapters import emg2qwerty as E

    out = []
    with E.Session(path) as s:
        ev = E.key_events(s)
        for pr in s.prompts:
            pe = [e for e in E.prompt_events(s, pr, ev) if E.key_class(e.key) is not None]
            if len(pe) < E2Q_MIN_KEYS:
                continue
            out.append((int(pr.index), " ".join(E.key_code(e.key) for e in pe), float(pe[-1].t - pe[0].t)))
    return out


def build_truth(track: str, data: str | PathLike[str], *, split: dict[str, Any] | None = None,
                **kw: Any) -> list[dict[str, Any]]:
    """Rebuild the truth rows of the scored units from a local dataset copy. Local only: never commit them.

    ``split``: a split dict (:func:`fidetype.benchmark.tracks.make_split` or a split file); default:
    the committed split of ``track``. Pass the same split to :func:`score` and :func:`check_submission`.
    ``kw``: options of the track loader. For ``kt-semg`` the truth needs only the key logs and the
    start-time files (``runN_keys.txt``, ``runN_ts.txt``): the ``runN.csv`` EMG files may be absent
    (``keys_only=True`` is the default here; P14-46).
    """
    t = TR.get_track(track)
    split = TR.load_split(track) if split is None else split
    if split.get("track") != track:
        raise ValueError(f"the split is of track {split.get('track')!r}, not {track!r}")
    if track == "kt-semg":
        kw.setdefault("keys_only", True)
    all_units = TR.local_units(track, data, **kw)
    units = TR.select_units(split, all_units, t.scored_split)
    rows: list[dict[str, Any]] = []

    def add(u: TR.LocalUnit, text: str, neural_s: float | None, key: str | None = None) -> None:
        r = {"unit": key or TR.id_hash(track, u.id), "id": u.id, "payload": u.payload, "group": u.group,
             "text": text, "neural_s": neural_s}
        rows.append(r)

    if track == "b2t25-t15":
        durs = _b2t25_durations(units[0].ref["pkl"]) if units else {}
        for u in units:
            add(u, u.payload, durs.get(int(u.ref["index"])))
    elif track == "b2t24-t12":
        bins = _t12_bins({u.ref["file"] for u in units})
        for u in units:
            add(u, u.payload, bins[(u.ref["file"], int(u.ref["index"]))] * 0.02)
    elif track == "willett-hw":
        for u in units:
            text, nb = u.payload.rsplit("|", 1)
            add(u, text, int(nb) * 0.01)
    elif track == "toronto-semg":
        for u in units:
            add(u, u.payload.rsplit("|", 1)[0], None)
    elif track == "kt-semg":
        runs = {u.id: u for u in all_units if u.set == "run"}
        kt = _kt_key_times(units, runs)
        for u in units:
            a, b = u.ref["key_range"]
            ts = kt[u.ref["run"]][a:b]
            gaps = sorted(y - x for x, y in zip(ts[:-1], ts[1:]))
            iki = gaps[len(gaps) // 2] if gaps else 0.0
            add(u, u.payload, float(ts[-1] - ts[0] + iki))
    elif track == "spanishbcbl-meg":
        for u in units:
            add(u, u.payload, None)
    elif track == "emg2qwerty":
        for u in units:
            h = TR.id_hash(track, u.id)
            for k, codes, ns in _e2q_prompts(u.ref["file"]):
                add(u, codes, ns, key=f"{h}#{k}")
    else:  # pragma: no cover - every track has a branch
        raise KeyError(track)
    return rows


def write_truth(path: str | PathLike[str], track: str, rows: Sequence[dict[str, Any]]) -> int:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        f.write(json.dumps({"schema": TRUTH_SCHEMA, "track": track, "note": "local file: holds truth text, never "
                            "commit or share it"}) + "\n")
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    return len(rows)


def read_truth(path: str | PathLike[str], track: str, split: dict[str, Any] | None = None) -> dict[str, dict[str, Any]]:
    """Read a truth file and check each row against the split (id hash, fingerprint, group)."""
    split = split or TR.load_split(track)
    scored = scored_entries(split)
    out: dict[str, dict[str, Any]] = {}
    bad: list[str] = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        if "schema" in r and "unit" not in r:
            if r.get("schema") != TRUTH_SCHEMA or r.get("track") != track:
                raise SubmissionError(f"{path}: not a {TRUTH_SCHEMA} file of {track}")
            continue
        out[r["unit"]] = r
    for key, r in out.items():
        h = _parent(key)
        e = scored.get(h)
        if (e is None or TR.id_hash(track, r["id"]) != h or TR.fingerprint(track, r["id"], r["payload"]) != e["fp"]
                or TR.group_hash(track, r["group"]) != e["g"]):
            bad.append(key)
    if bad:
        raise SubmissionError(f"truth does not match the {track} split for {len(bad)} unit(s), e.g. {bad[:3]}; "
                              "rebuild it with `python -m fidetype.benchmark truth`")
    return out


# ---------------------------------------------------------------------------
# Score
# ---------------------------------------------------------------------------


def _clusters(track: str, keys: Sequence[str], scored: dict[str, Any], truth: dict[str, dict[str, Any]],
              norm: str | None = None) -> dict[str, dict[str, str]]:
    from fidetype.benchmark.registry import normalize

    norm = norm or SCORE_SPECS[track].normalizer
    out = {}
    for k in keys:
        txt = normalize(truth[k]["text"], norm)
        out[k] = {"group": scored[_parent(k)]["g"], "sentence": hashlib.sha256(txt.encode("utf-8")).hexdigest()[:12]}
    return out


def _latency(lat: Sequence[float]) -> dict[str, Any] | None:
    if not lat:
        return None
    x = sorted(lat)
    return {"n": len(x), "median_s": x[len(x) // 2], "p95_s": x[min(len(x) - 1, int(math.ceil(0.95 * len(x))) - 1)]}


def score(track: str, folder: str | PathLike[str], truth: dict[str, dict[str, Any]], *, B: int = DEFAULT_B,
          seed: int = 0, gate: bool = False, split: dict[str, Any] | None = None) -> dict[str, Any]:
    """Validate and score one submission. Returns the score card (result dict)."""
    folder = Path(folder)
    split = split or TR.load_split(track)
    chk = check_submission(track, folder, split)
    man = load_manifest(folder)
    spec, tdef = SCORE_SPECS[track], TR.get_track(track)
    st = scoring_track(track, man.target)
    scored = scored_entries(split)
    outs, info = read_outputs(folder, "real")  # type: ignore[misc]
    # Units to score: every truth unit (sub-units: of the covered parents too), unless coverage is a declared subset.
    truth_keys = [k for k in truth if _parent(k) in scored]
    if not truth_keys:
        raise SubmissionError("the truth holds no scored unit")
    extra = [k for k in outs if k not in truth]
    if extra:
        raise SubmissionError(f"{len(extra)} output unit(s) are not in the truth (e.g. {extra[:3]}): for "
                              f"{track} the scored units are the truth rows")
    if man.coverage:
        ids = [k for k in truth_keys if k in outs]
    else:
        miss = [k for k in truth_keys if k not in outs]
        if miss:
            raise SubmissionError(f"{len(miss)} scored unit(s) have no output, e.g. {miss[:3]}")
        ids = truth_keys
    order = {h: i for i, h in enumerate(scored)}
    ids.sort(key=lambda k: (order[_parent(k)], int(k.split("#")[1]) if "#" in k else 0))
    texts = {k: truth[k]["text"] for k in ids}
    durs = {k: float(truth[k]["neural_s"]) for k in ids if truth[k].get("neural_s") is not None}
    durations = durs if len(durs) == len(ids) else None
    clusters = _clusters(track, ids, scored, truth, st.normalizer)
    conf: dict[str, Any] = {"level": "not checked (units JSONL: NTS-derived rows)"}
    if info["format"] == "nts-streams":
        from fidetype.benchmark.harness import conformance_gate

        conf = conformance_gate({k: info["files"][k] for k in ids}, {k: {"text": texts[k]} for k in ids})
        if gate and not conf["passed"]:
            raise SubmissionError(f"conformance gate failed: weakest file {conf['worst_file']} at {conf['level']}")
    real = score_trials(st, outs, texts, clusters, ids, durations=durations)
    controls = {}
    for kind in CONTROL_KINDS:
        c = read_outputs(folder, kind)
        if c is None:
            continue
        co, _ = c
        have = [k for k in ids if k in co]
        controls[kind] = score_trials(st, co, texts, clusters, have)
    cal = man.base.guarantee.get("calibration_split")
    # Calibration split size in scored units (not for sub-unit tracks: the split counts parents, not prompts).
    n_cal = (split["counts"].get(tdef.scored_set, {}).get(cal)
             if cal in ("train", "val", "cal") and not spec.sub_units else None)
    decoder = dict(man.base.decoder)
    decoder.setdefault("training_regime", man.regime)
    res = build_result(
        st, real, decoder=decoder, policy=man.base.policy, guarantee=man.base.guarantee, controls=controls,
        conformance=conf, scored_from=f"submission/0.2 ({info['format']})", sources=[folder.name],
        notes=[man.base.notes] if man.base.notes else [], B=B, seed=seed, n_cal_split=n_cal,
        entry_id=man.raw.get("entry_id"))
    if not man.raw.get("entry_id"):
        res["entry_id"] = f"{track}/{decoder.get('name', 'decoder')}/{man.base.policy.get('name', 'policy')}"
    m = res["metrics"]
    res["schema"] = RESULT_SCHEMA_V02
    res["benchmark_version"] = TR.TRACKS_VERSION
    res["scorer_version"] = SCORER_VERSION
    res["track_info"] = {"title": tdef.title, "licence": tdef.licence, "research_only": tdef.research_only,
                         "modality": tdef.modality, "ci_unit": tdef.ci_unit, "split_digest": split["digest"],
                         "rate_source": spec.rate_source, "key_track": spec.key_track}
    res["ci"]["unit_name"] = tdef.ci_unit
    if man.target is not None:
        # P11-13: the declared target (a manifest without one keeps the track default and the old card form).
        res["target"] = target_block(man.target)
    if spec.key_track and st.normalizer == "keycodes":
        m["key_error_rate"] = dict(m["cer"])
        res["notes"].append("Key track: one character per key, so CER = key error rate.")
    elif spec.key_track:
        res["notes"].append(f"Target {man.target} ({TARGETS[man.target][0]}): truth and outputs are compared after "
                            "Backspace is applied, so CER is the character error rate of the intended text and the "
                            "no-BCI reference is gaze typing of the intended text. Not ranked with raw-key entries.")
    res["coverage"] = {"n_scored_units": len(truth_keys), "n_covered": len(ids), "partial": len(ids) < len(truth_keys),
                       **({"subset": man.coverage["subset"]} if man.coverage else {})}
    res["regime"] = man.regime
    res["controls"]["basis"] = {k: man.controls.get(k, "not stated") for k in CONTROL_KINDS}
    res["latency"] = _latency(info.get("latency_s", []))
    res["timing"] = ("measured per unit (truth neural_s)" if durations is not None
                     else f"track rate model ({spec.chars_per_min:.2f} per min)")
    res["submitter"] = man.base.submitter
    res["check"] = {k: chk[k] for k in ("format", "n_rows", "n_parent_units", "n_parent_covered")}
    # P6-10: train / test overlap (ids, committed maps and text hashes of the scored units). It warns; it does
    # not change any number or the status.
    ov = OV.check_overlap(track, man.training_data, ids, {k: OV.text_hash(track, texts[k]) for k in ids},
                          split=split)
    res["overlap_check"] = ov
    if ov["status"] == "overlap":
        res["notes"].append(f"WARNING (train / test overlap, P6-10): {ov['message']}")
    elif ov["status"] == "not checked":
        res["notes"].append(f"Train / test overlap not checked (P6-10): {ov['message']}")
    ctl = res["controls"]
    missing = [k for k in ("shuffled", "zeros", "null_commit") if ctl[k]["status"] in ("missing", "incomplete")]
    res["status"] = ("scored" if ctl["passed"] else
                     "scored: controls missing" if missing else "scored: controls failed")
    res["certification"] = (res.get("safe_wpm") or {}).get("status")
    if tdef.research_only:
        res["notes"].append(f"RESEARCH ONLY: {tdef.licence} data. Results and weights are non-commercial.")
    # Rerun recipe (P13-06, docs/hub-design.md section 5): every versioned input and the exact command.
    from fidetype.benchmark.hub.recipe import RESCORE_INPUTS, make_recipe, score_command

    res["rerun"] = make_recipe(res, command=score_command(track, B=B, seed=seed), level="rescore",
                               inputs=RESCORE_INPUTS)
    if man.target is not None:
        res["rerun"].setdefault("scorer", {})["target"] = TARGETS[man.target][0]
    return res


def score_card_text(res: dict[str, Any]) -> str:
    """A short human-readable score card."""
    m = res["metrics"]

    def v(k: str, nd: int = 3, pct: bool = False) -> str:
        x = (m.get(k) or {}).get("value")
        ci = (m.get(k) or {}).get("ci")
        if x is None or (isinstance(x, float) and not math.isfinite(x)):
            return "n/a"
        f = (lambda y: f"{100 * y:.1f}%") if pct else (lambda y: f"{y:.{nd}f}")
        s = f(x)
        if ci and all(c is not None and math.isfinite(c) for c in ci):
            s += f" [{f(ci[0])}, {f(ci[1])}]"
        return s

    ti = res.get("track_info", {})
    sw = res.get("safe_wpm") or {}
    c = res["controls"]
    keys = ti.get("key_track") and "key_error_rate" in m
    err = "key error" if keys else "CER"
    tg = res.get("target")
    lines = [
        f"{res['track']}  {res['entry_id']}  ({res['n_trials']} units; CI unit {ti.get('ci_unit')})"
        + ("  RESEARCH ONLY" if ti.get("research_only") else "") + (f"  target {tg['name']}" if tg else ""),
        f"  {err} {v('cer')}" + ("" if keys else f"   WER {v('wer')}"),
        f"  eWPM {v('ewpm', 2)}   no-BCI {v('gaze_ewpm', 2)}   difference {v('ewpm_minus_gaze', 2)}",
        (f"  safe WPM @ {sw.get('alpha')}: " if sw.get("alpha") is not None else "  safe WPM: ")
        + f"{('n/a' if sw.get('value') is None else format(sw['value'], '.2f'))} ({sw.get('status')})",
        f"  wrong-commit {v('wrong_commit_rate')}   error among commits {v('error_among_commits')}   "
        f"commit rate {v('commit_rate')}",
        f"  controls: shuffled {c['shuffled']['status']}, zeros {c['zeros']['status']}, "
        f"null-commit {c['null_commit']['status']}"
        + (f" ({c['null_commit'].get('commit_rate_zeros'):.3f})" if c['null_commit'].get('commit_rate_zeros') is not None else ""),
        f"  coverage {res['coverage']['n_covered']}/{res['coverage']['n_scored_units']}"
        + (" (partial)" if res["coverage"]["partial"] else "") + f"   status: {res['status']}",
        f"  {OV.overlap_text(res.get('overlap_check'))}",
    ]
    return "\n".join(lines)


__all__ = ["SUBMISSION_SCHEMA", "UNITS_SCHEMA", "TRUTH_SCHEMA", "RESULT_SCHEMA_V02", "SCORE_SPECS", "ScoreSpec",
           "TARGETS", "resolve_target", "target_block",
           "scoring_track", "scored_entries", "manifest_dict", "parse_manifest", "load_manifest", "unit_row",
           "write_units", "write_submission", "read_units", "read_outputs", "check_submission", "build_truth",
           "write_truth", "read_truth", "score", "score_card_text"]
