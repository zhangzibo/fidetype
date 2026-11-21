"""Benchmark tracks v0.2: licence-clean, fixed, versioned splits for seven datasets (roadmap P6-01).

A **track** is one scored task on one public dataset. This module defines
each track (task, metrics, required controls, licence, attribution), its
committed split file, and a loader that maps the split entries to a local
copy of the dataset through the adapters in :mod:`fidetype.adapters`.

What a split file holds
-----------------------
Only salted hashes. No text, no signals, no plain trial ids. One entry per
unit (a trial, a recording, a run, a session, ...)::

    {"u": "<unit set>", "h": "<id hash>", "s": "<split>", "g": "<group hash>", "fp": "<fingerprint>"}

- ``h  = sha256("<salt>|<local id>")[:16]``: the local id is rebuilt from
  the user's own download (for example ``t12.2022.05.05|test|7``).
- ``g  = sha256("<salt>|group|<group>")[:12]``: the cluster for the
  confidence intervals (day, session, participant, run).
- ``fp = sha256("<salt>|fp|<local id>|<payload>")[:16]``: the payload is
  the normalised truth text and / or a size (bytes, bins). It lets a user
  check that the local copy matches. It does not give the text back.
- ``salt = "fidetype/tracks/0.2/<track>"``. It is public. It only stops
  the same hash from meaning the same thing in two files (the pattern of
  ``splits/halluc-v0.1``).

Schema ``fidetype.benchmark.tracksplit/0.2``::

    {"schema", "track", "version", "dataset", "licence", "research_only",
     "salt", "rule", "units": {set: description}, "counts": {set: {split: n}},
     "digest", "entries": [...]}

``digest`` is the SHA-256 of the sorted lines ``u|h|s|g|fp``.

Commands::

    python -m fidetype.benchmark.tracks list
    python -m fidetype.benchmark.tracks info <track>
    python -m fidetype.benchmark.tracks verify <track> --data <path> [--cache ... --sentences ...]
    python -m fidetype.benchmark.tracks select <track> --data <path> --split test   # local ids, never commit
    python -m fidetype.benchmark.tracks make <track> --data <path> --out <file>     # maintainers only

The v0.1 tracks (:mod:`.registry`) stay valid. Three v0.2 tracks carry the
same trials as a v0.1 track (``v01_track``); the tests check this from the
committed files alone.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from importlib import resources
from os import PathLike
from pathlib import Path
from typing import Any, Callable, Iterable, Sequence

TRACKS_VERSION = "0.2"
SCHEMA = "fidetype.benchmark.tracksplit/0.2"

#: Metrics every text track reports (see benchmark/README.md, docs/benchmark-tracks.md).
TEXT_METRICS = ("cer", "wer", "ewpm", "safe_wpm@0.05", "wrong_commit", "error_among_commits", "commit_rate")
#: Controls every entry must run (P6 rule; scorer: fidetype.benchmark.scoring).
REQUIRED_CONTROLS = ("shuffled", "zeros", "null_commit<=0.05")


# ---------------------------------------------------------------------------
# Hashes
# ---------------------------------------------------------------------------


def salt(track: str) -> str:
    return f"fidetype/tracks/{TRACKS_VERSION}/{track}"


def _h(s: str, n: int) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()[:n]


def id_hash(track: str, local_id: str) -> str:
    return _h(f"{salt(track)}|{local_id}", 16)


def group_hash(track: str, group: str) -> str:
    return _h(f"{salt(track)}|group|{group}", 12)


def fingerprint(track: str, local_id: str, payload: str) -> str:
    return _h(f"{salt(track)}|fp|{local_id}|{payload}", 16)


def entries_digest(entries: Iterable[dict[str, str]]) -> str:
    lines = sorted(f"{e['u']}|{e['h']}|{e['s']}|{e['g']}|{e['fp']}" for e in entries)
    return hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Track definitions
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TrackSpec:
    """One v0.2 benchmark track. Values are data: change them only with a new version."""

    slug: str
    title: str
    modality: str
    language: str
    task: str
    dataset: str
    dataset_title: str
    citation: str
    url: str
    licence: str
    #: True if the data licence forbids commercial use. Such tracks are research-only.
    research_only: bool
    attribution: str
    #: The unit sets of the split file: {set name: what one entry is}.
    units: dict[str, str]
    #: The unit set and split that a submission is scored on.
    scored_set: str
    scored_split: str
    #: Splits that a decoder may train or calibrate on.
    open_splits: tuple[str, ...]
    metrics: tuple[str, ...]
    controls: tuple[str, ...]
    ci_unit: str
    timing: str
    #: What ``--data`` points to.
    data_hint: str
    #: Adapter module and the call that turns one local unit into a stream or signal.
    adapter: str
    rule: str
    v01_track: str | None = None
    notes: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @property
    def split_file(self) -> str:
        return f"{self.slug}.json"


TRACKS: dict[str, TrackSpec] = {}


def _add(t: TrackSpec) -> None:
    TRACKS[t.slug] = t


_add(TrackSpec(
    slug="b2t25-t15",
    title="Intracortical attempted speech, T15 copy task (Brain-to-Text '25)",
    modality="intracortical", language="en",
    task="Decode the sentence of each trial (published per-trial RNN phoneme logits, or your own decoder on the "
         "neural features), then COMMIT / OFFER / ABSTAIN.",
    dataset="brain-to-text-25", dataset_title="Brain-to-Text '25, participant T15 copy task",
    citation="Card et al., NEJM 391 (2024), doi:10.1056/NEJMoa2314132; Dryad doi:10.5061/dryad.dncjsxm85",
    url="https://doi.org/10.5061/dryad.dncjsxm85", licence="CC0 1.0", research_only=False,
    attribution="Data: Card et al. 2024 (Dryad, CC0). No attribution is required; please cite the paper.",
    units={"trial": "one 125k-vocabulary copy-task trial (t15_copyTask.pkl)"},
    scored_set="trial", scored_split="test", open_splits=("cal",),
    metrics=TEXT_METRICS, controls=REQUIRED_CONTROLS + ("halluc: null / scrambled / swapped (optional)",),
    ci_unit="day", timing="measured per trial: speech_duration_s of the pkl",
    data_hint="path to t15_copyTask.pkl (SHA-256 checked by the adapter)",
    adapter="fidetype.adapters.b2t25: load_copytask(pkl)[index] -> trial_stream(trial)",
    rule="125k-vocabulary trials only. Per post-implant day, in file order: first half -> cal, second half -> test. "
         "Local id = t15-copytask-<index:04d>. Payload = normalised truth words.",
    v01_track="b2t25-t15-copytask",
))

_add(TrackSpec(
    slug="b2t24-t12",
    title="Intracortical attempted speech, T12 (Brain-to-Text '24 competition data)",
    modality="intracortical", language="en",
    task="Decode the sentence of each trial from the binned neural features (tx1-tx4, spikePow), then "
         "COMMIT / OFFER / ABSTAIN.",
    dataset="brain-to-text-24", dataset_title="Brain-to-Text '24 competitionData, participant T12",
    citation="Willett et al., Nature 620:1031 (2023), doi:10.1038/s41586-023-06377-x; Dryad doi:10.5061/dryad.x69p8czpq",
    url="https://doi.org/10.5061/dryad.x69p8czpq", licence="CC0 1.0", research_only=False,
    attribution="Data: Willett et al. 2023 (Dryad, CC0). No attribution is required; please cite the paper.",
    units={"trial": "one sentence trial of competitionData/<partition>/<session>.mat"},
    scored_set="trial", scored_split="test", open_splits=("train", "cal"),
    metrics=TEXT_METRICS, controls=REQUIRED_CONTROLS + ("halluc: null / scrambled / swapped (optional)",),
    ci_unit="session", timing="measured per trial: number of 20 ms bins of tx1",
    data_hint="the competitionData folder (train/, test/, competitionHoldOut/)",
    adapter="fidetype.benchmark.tracks.t12_trial_features(ref) (scipy.io.loadmat of one session file)",
    rule="Official partitions. train/ -> train, except the trials of the last block (max blockIdx) of each train "
         "session -> cal. test/ -> test (the scored split: its labels are public). competitionHoldOut/ -> holdout "
         "(labels not released: listed, never scored). Local id = <session>|<partition>|<i>. Payload = normalised "
         "truth words (holdout: empty).",
    notes=("The competition hold-out labels are not public. The track scores the public test partition.",
           "Split made from the Zenodo 8047896 copy of the Dryad DOI (MD5 a7e9d972ac5b65171a37674eb47730b8; same "
           "partitions as Dryad v9). Run verify on your copy.",
           "splits/halluc-v0.1/b2t24-t12-test.json uses another id space (the T12 v2 trust pool); it is not this split."),
))

_add(TrackSpec(
    slug="willett-hw",
    title="Intracortical handwriting, T5 sentences (Willett 2021)",
    modality="intracortical", language="en",
    task="Decode the sentence of each trial (published real-time RNN character probabilities, or your own decoder "
         "on the neural cube), then COMMIT / OFFER / ABSTAIN.",
    dataset="willett-handwriting", dataset_title="Data from: High-performance brain-to-text communication via handwriting",
    citation="Willett, Avansino, Hochberg, Henderson, Shenoy, Nature 593:249 (2021), doi:10.1038/s41586-021-03506-2; "
             "Dryad doi:10.5061/dryad.wh70rxwmv",
    url="https://doi.org/10.5061/dryad.wh70rxwmv", licence="CC0 1.0", research_only=False,
    attribution="Data: Willett et al. 2021 (Dryad / Zenodo 4695519, CC0). No attribution is required; please cite.",
    units={"trial": "one non-excluded sentence trial of Datasets/<session>/sentences.mat"},
    scored_set="trial", scored_split="test", open_splits=("train", "val", "cal"),
    metrics=TEXT_METRICS, controls=REQUIRED_CONTROLS,
    ci_unit="session", timing="measured per trial: (sentenceEndTimeBin - goCueOnsetTimeBin) x 10 ms",
    data_hint="the handwritingBCIData folder (holds Datasets/)",
    adapter="fidetype.adapters.willett_handwriting: load_sentences(file) -> trial_stream(sess, index)",
    rule="Sessions in date order. The last 3 sessions are test sessions: in each, the first third of the "
         "non-excluded trials (index order) -> cal, the rest -> test. Earlier sessions: the last 10 % of the "
         "trials (at least 1) -> val, the rest -> train. Local id = <session>|<index>. Payload = truth text | "
         "number of bins from go cue to sentence end.",
    notes=("Closed-loop trials of 9 sessions have the published RNN output (rnn_charProbTimeSeries). A submission "
           "that decodes the RNN output covers only those trials (81 of the 254 test trials); it states this.",
           "In the test sessions the cal trials come first and are open-loop (no RNN output). An RNN-output entry "
           "calibrates on the val trials of the earlier sessions instead."),
))

_add(TrackSpec(
    slug="toronto-semg",
    title="Forearm sEMG key presses (Toronto typing gestures)",
    modality="emg", language="en",
    task="Classify each key press (oracle key timing), then decode composed sentences with an LM and a trust "
         "policy (COMMIT / OFFER / ABSTAIN).",
    dataset="toronto-semg", dataset_title="Electromyographic typing gesture classification dataset",
    citation="Achituve, Beutel, Eby, Fetaya, Koivisto, Zariffa, Sci Data 12:440 (2025), doi:10.1038/s41597-025-04763-w; "
             "Borealis doi:10.5683/SP3/KV65VI",
    url="https://doi.org/10.5683/SP3/KV65VI", licence="CC BY 4.0", research_only=False,
    attribution="Contains data from Achituve et al. 2025 (University of Toronto, Borealis doi:10.5683/SP3/KV65VI), "
                "licensed CC BY 4.0. Fidetype changed nothing in the data; splits are ours.",
    units={"recording": "one Intan .rhd recording (CleanData/P<n>/T<m>/Data/<file>.rhd)",
           "sentence": "one composed sentence (v0.1 recipe: per character one real day-2 press of that character)"},
    scored_set="sentence", scored_split="test", open_splits=("train", "cal"),
    metrics=TEXT_METRICS + ("key_accuracy",), controls=REQUIRED_CONTROLS,
    ci_unit="participant", timing="track rate model: one key per 0.792 s (median inter-key interval)",
    data_hint="the extracted dataset folder (holds CleanData/); sentence set: --cache <window cache> "
              "--sentences <eng_tatoeba_heldout.txt>",
    adapter="fidetype.adapters.toronto_semg: read_rhd(path), key_events(...) -> keypress_stream(...)",
    rule="Recordings: session T1 -> train; session T2, first recording of a letter (start-time order) -> cal; "
         "T2, later recordings -> test. Local id = P<n>/T<m>/<stem>. Payload = file size in bytes. Sentences: the "
         "v0.1 composed-sentence set (cal / test). Local id = <participant>-<split>-<nn>. Payload = truth text | "
         "SHA-256 of the press ids.",
    v01_track="toronto-semg-composed",
    notes=("Composed sentences test key decoding + LM + trust. They are not natural typing.",),
))

_add(TrackSpec(
    slug="kt-semg",
    title="Forearm sEMG natural typing (KT-sEMG, Nokia Bell Labs)",
    modality="emg", language="en",
    task="Decode the key sequence of each typing burst (oracle key timing or your own key detector), then "
         "COMMIT / OFFER / ABSTAIN.",
    dataset="kt-semg", dataset_title="KT-sEMG (Keyboard Typing via Surface Electromyography)",
    citation="Crouch, Zheng, Eggleston, arXiv:2109.10743; Harvard Dataverse doi:10.7910/DVN/AV6XIR (v1.1)",
    url="https://doi.org/10.7910/DVN/AV6XIR", licence="CC BY 4.0", research_only=False,
    attribution="KT-sEMG dataset, copyright 2021 Nokia, licensed CC BY 4.0 (Harvard Dataverse doi:10.7910/DVN/AV6XIR). "
                "Fidetype changed nothing in the data; splits are ours.",
    units={"run": "one recording run (runN.csv + runN_keys.txt + runN_ts.txt)",
           "segment": "one typing burst inside a cal / test run: key presses split at pauses > 2 s, >= 5 keys"},
    scored_set="segment", scored_split="test", open_splits=("train", "cal"),
    metrics=("key_error_rate",) + TEXT_METRICS[2:], controls=REQUIRED_CONTROLS,
    ci_unit="run", timing="measured per segment: last key time - first key time + one median inter-key interval",
    data_hint="the KT-sEMG folder (run*.csv, run*_keys.txt, run*_ts.txt)",
    adapter="fidetype.adapters.kt_semg: read_emg_csv(csv), read_keys(keys) -> keypress_stream(...)",
    rule="Runs in start-time order: the last 6 -> test, the 3 before -> cal, the rest -> train. Segments: "
         "kt_semg.segment_events on the unix key times (max gap 2 s), kept if >= 5 key presses, only in cal / "
         "test runs. Local ids = run<N> and run<N>#<k>. Payloads = csv size | SHA-256 of the key file; key codes "
         "of the segment.",
    notes=("One typist. The CI unit is the run; the CIs say nothing about other people.",
           "Truth is the key-code sequence (W3C KeyboardEvent.code). Backspace and Enter are keys too."),
))

_add(TrackSpec(
    slug="spanishbcbl-meg",
    title="MEG typing, asynchronous (SpanishBCBL) - RESEARCH ONLY",
    modality="meg", language="es",
    task="Decode the typed sentence from the MEG segment (no key times at test), then COMMIT / OFFER / ABSTAIN.",
    dataset="spanishbcbl", dataset_title="SpanishBCBL typing MEG (Brain2Qwerty v1/v2 data)",
    citation="Levy et al., Nature Neuroscience 29 (2026), doi:10.1038/s41593-026-02303-2; dataset bcbl190626/SpanishBCBL",
    url="https://huggingface.co/datasets/bcbl190626/SpanishBCBL", licence="CC BY-NC 4.0", research_only=True,
    attribution="Contains data from the SpanishBCBL dataset (BCBL; Levy et al. 2026), licensed CC BY-NC 4.0. "
                "Non-commercial research use only. Fidetype ships no data and no weights trained on it.",
    units={"trial": "one typed sentence segment of the preprocessing cache (tools/data/preprocess_spanishbcbl.py)"},
    scored_set="trial", scored_split="test", open_splits=("train", "val"),
    metrics=TEXT_METRICS, controls=REQUIRED_CONTROLS,
    ci_unit="two_way:sentence,participant", timing="track rate model: 152 chars/min (Brain2Qwerty v1 typing rate)",
    data_hint="the SpanishBCBL preprocessing cache (S*/*.json + .npz sidecars)",
    adapter="fidetype.adapters.spanishbcbl_meg: segment_stream(...) on your decoder's logits",
    rule="As v0.1 spanishbcbl-meg-async: split by sentence (SHA-1 bucket of the normalised text, 80/10/10). "
         "Local id = <subject>_<session>_<block>_<trial>. Payload = normalised target text.",
    v01_track="spanishbcbl-meg-async",
    notes=("CC BY-NC 4.0: research track. Results and weights derived from it are research-only.",),
))

_add(TrackSpec(
    slug="emg2qwerty",
    title="Wrist sEMG touch typing (emg2qwerty, Meta) - RESEARCH ONLY",
    modality="emg", language="en",
    task="Decode the typed text of each prompt from wrist sEMG (no key times at test), then COMMIT / OFFER / ABSTAIN.",
    dataset="emg2qwerty", dataset_title="emg2qwerty-data-2021-08",
    citation="Sivakumar et al., emg2qwerty, NeurIPS 2024 Datasets and Benchmarks, arXiv:2410.20081",
    url="https://github.com/facebookresearch/emg2qwerty", licence="CC BY-NC-SA 4.0", research_only=True,
    attribution="Contains data from emg2qwerty (Meta Platforms, Sivakumar et al. 2024), licensed CC BY-NC-SA 4.0 "
                "(the stricter of the two licences the source states). Non-commercial research use only; derived "
                "results keep the share-alike terms.",
    units={"session": "one session file <session>.hdf5 (all prompts of that session)"},
    scored_set="session", scored_split="test", open_splits=("train", "val"),
    metrics=TEXT_METRICS + ("key_error_rate",), controls=REQUIRED_CONTROLS,
    ci_unit="user", timing="measured per prompt: from the first to the last key-down time of the prompt",
    data_hint="the emg2qwerty-data-2021-08 folder (metadata.csv + *.hdf5)",
    adapter="fidetype.adapters.emg2qwerty: Session(path), prompt_events(...) -> prompt_stream(...)",
    rule="Our own split (the upstream split lists are not copied). Per user, sessions in name order (names start "
         "with the date). Users with >= 4 sessions: last -> test, second last -> val, the rest -> train. Users "
         "with < 4 sessions: all -> train. Local id = session name. Payload = file size | keystrokes | prompts "
         "(metadata.csv).",
    notes=("Personalised regime: every test user has train sessions. Report the regime of the entry.",
           "The scored unit inside a test session is each prompt (adapter prompt_events)."),
))


def get_track(slug: str) -> TrackSpec:
    try:
        return TRACKS[slug]
    except KeyError:
        raise KeyError(f"unknown track {slug!r}; known: {sorted(TRACKS)}") from None


# ---------------------------------------------------------------------------
# Local units: what a loader rebuilds from the user's own download
# ---------------------------------------------------------------------------


@dataclass
class LocalUnit:
    """One unit of a local dataset copy. ``payload`` and ``ref`` stay local: never commit them."""

    set: str
    id: str
    group: str
    payload: str
    #: The split that the track rule gives (used by ``make`` only; ``verify`` checks it).
    split: str
    #: Where the data of this unit is (file, index, ...): input for the adapter.
    ref: dict[str, Any] = field(default_factory=dict)

    def entry(self, track: str) -> dict[str, str]:
        return {"u": self.set, "h": id_hash(track, self.id), "s": self.split,
                "g": group_hash(track, self.group), "fp": fingerprint(track, self.id, self.payload)}


def _file_sha(path: Path, n: int = 16) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:n]


# --- Brain-to-Text '25 (T15) ------------------------------------------------------------


def units_b2t25(data: str | PathLike[str], **_: Any) -> list[LocalUnit]:
    from fidetype.benchmark.prepare import b2t25_trials

    p = Path(data)
    if p.is_dir():
        p = p / "t15_copyTask.pkl"
    out = []
    for t in b2t25_trials(p):
        out.append(LocalUnit("trial", t.id, t.clusters["day"], t.text, t.split,
                             {"pkl": str(p), "index": int(t.id.rsplit("-", 1)[1])}))
    return out


# --- Brain-to-Text '24 (T12) ------------------------------------------------------------

T12_PARTITIONS = (("train", "train"), ("test", "test"), ("competitionHoldOut", "holdout"))


def _t12_root(data: str | PathLike[str]) -> Path:
    p = Path(data)
    for cand in (p, p / "competitionData", p / "extracted" / "competitionData"):
        if (cand / "train").is_dir() and (cand / "test").is_dir():
            return cand
    raise FileNotFoundError(f"no competitionData (train/, test/) under {p}")


def t12_session_texts(path: str | PathLike[str]) -> tuple[list[str], list[int]]:
    """``sentenceText`` and ``blockIdx`` of one competitionData session file (the neural cells are not read)."""
    from scipy.io import loadmat  # optional [data] extra

    d = loadmat(path, variable_names=["sentenceText", "blockIdx"])
    texts = [str(s).strip() for s in d["sentenceText"]]
    blocks = [int(b) for b in d["blockIdx"].reshape(-1)]
    if len(texts) != len(blocks):
        raise ValueError(f"{Path(path).name}: {len(texts)} sentences but {len(blocks)} block indices")
    return texts, blocks


def t12_trial_features(ref: dict[str, Any]) -> dict[str, Any]:
    """Neural features of one T12 trial (``ref`` from :func:`select`): tx1-tx4 and spikePow, 20 ms bins."""
    from scipy.io import loadmat

    d = loadmat(ref["file"], variable_names=["tx1", "tx2", "tx3", "tx4", "spikePow"])
    i = int(ref["index"])
    return {k: d[k][0, i] for k in ("tx1", "tx2", "tx3", "tx4", "spikePow")}


def units_b2t24(data: str | PathLike[str], **_: Any) -> list[LocalUnit]:
    from fidetype.adapters.b2t25 import normalize_words

    root = _t12_root(data)
    out = []
    for folder, part in T12_PARTITIONS:
        for f in sorted((root / folder).glob("t12.*.mat")):
            sess = f.stem
            texts, blocks = t12_session_texts(f)
            last = max(blocks) if blocks else None
            for i, (t, b) in enumerate(zip(texts, blocks)):
                if part == "train":
                    split = "cal" if b == last else "train"
                else:
                    split = part
                payload = "" if part == "holdout" else normalize_words(t)
                out.append(LocalUnit("trial", f"{sess}|{part}|{i}", sess, payload, split,
                                     {"file": str(f), "index": i, "partition": part}))
    return out


# --- Willett handwriting (T5) -----------------------------------------------------------

WILLETT_TEST_SESSIONS = 3


def units_willett(data: str | PathLike[str], **_: Any) -> list[LocalUnit]:
    from fidetype.adapters.willett_handwriting import list_session_files, load_sentences

    files = list_session_files(data)
    if not files:
        raise FileNotFoundError(f"no Datasets/*/sentences.mat under {data}")
    out = []
    n_sess = len(files)
    for k, f in enumerate(files):
        sess = load_sentences(f)
        name = f.parent.name
        keep = [i for i in range(sess.n_trials) if not sess.excluded[i]]
        n = len(keep)
        test_session = k >= n_sess - WILLETT_TEST_SESSIONS
        n_head = n // 3 if test_session else n - max(1, math.ceil(0.1 * n))
        for j, i in enumerate(keep):
            if test_session:
                split = "cal" if j < n_head else "test"
            else:
                split = "train" if j < n_head else "val"
            bins = int(sess.end_bin[i] - sess.go_bin[i])
            out.append(LocalUnit("trial", f"{name}|{i}", name, f"{sess.intended_text[i]}|{bins}", split,
                                 {"file": str(f), "index": i, "session_index": k,
                                  "rnn": bool(sess.has_rnn and sess.is_closed_loop(i))}))
    return out


# --- Toronto sEMG -----------------------------------------------------------------------


def units_toronto(data: str | PathLike[str], cache: str | None = None, sentences: str | None = None,
                  **_: Any) -> list[LocalUnit]:
    from fidetype.adapters.toronto_semg import list_recordings

    p = Path(data)
    root = p / "CleanData" if (p / "CleanData").is_dir() else p
    recs = list_recordings(root)
    if not recs:
        raise FileNotFoundError(f"no CleanData/P*/T*/Data/*.rhd under {p}")
    order: Counter = Counter()
    out = []
    for r in sorted(recs, key=lambda r: (int(r.participant[1:]), r.session, r.letter, r.start, r.stem)):
        order[(r.participant, r.session, r.letter)] += 1
        o = order[(r.participant, r.session, r.letter)]
        split = "train" if r.session == "T1" else ("cal" if o == 1 else "test")
        out.append(LocalUnit("recording", r.key, r.participant, str(r.path.stat().st_size), split,
                             {"file": str(r.path), "letter": r.letter, "order": o}))
    if cache and sentences:
        from fidetype.benchmark.prepare import detail_hash, toronto_trials

        for t in toronto_trials(cache, sentences):
            out.append(LocalUnit("sentence", t.id, t.clusters["participant"], f"{t.text}|{detail_hash(t.detail)}",
                                 t.split, {"presses": t.detail}))
    return out


# --- KT-sEMG ----------------------------------------------------------------------------

KT_TEST_RUNS, KT_CAL_RUNS, KT_MAX_GAP_S, KT_MIN_KEYS = 6, 3, 2.0, 5


def _kt_runs_keys_only(data: str | PathLike[str]) -> list[Any]:
    """KT-sEMG runs found by their key log and start-time file; the ``runN.csv`` may be absent."""
    from fidetype.adapters.kt_semg import RunFiles

    r = Path(data)
    out = []
    for k in r.glob("run*_keys.txt"):
        m = re.fullmatch(r"run(\d+)_keys", k.stem)
        t = r / f"run{m.group(1)}_ts.txt" if m else None
        if m and t is not None and t.is_file():
            out.append(RunFiles(int(m.group(1)), r / f"run{m.group(1)}.csv", k, t))
    return sorted(out, key=lambda x: x.run)


def units_kt(data: str | PathLike[str], keys_only: bool = False, **_: Any) -> list[LocalUnit]:
    """KT-sEMG units: runs and typing bursts (segments).

    ``keys_only=True`` (P14-46): find the runs by ``runN_keys.txt`` + ``runN_ts.txt`` and do not
    need ``runN.csv`` (about 20 GB in all). The segment units are the same. A run unit whose CSV is
    absent gets the payload ``?|<key-log hash>``, so ``verify`` reports it (verify needs the CSVs).
    """
    from fidetype.adapters.kt_semg import key_code, list_runs, parse_keys, read_start_time, segment_events

    runs = _kt_runs_keys_only(data) if keys_only else list_runs(data)
    if not runs:
        need = "run*_keys.txt + _ts.txt" if keys_only else "run*.csv + _keys.txt + _ts.txt"
        raise FileNotFoundError(f"no {need} under {data}")
    info = []
    for r in runs:
        raw = r.keys.read_bytes()
        info.append((read_start_time(r.ts), r, raw))
    info.sort(key=lambda x: (x[0], x[1].run))
    n = len(info)
    out = []
    for k, (start, r, raw) in enumerate(info):
        split = "test" if k >= n - KT_TEST_RUNS else ("cal" if k >= n - KT_TEST_RUNS - KT_CAL_RUNS else "train")
        rid = f"run{r.run}"
        size = r.csv.stat().st_size if r.csv.is_file() else "?"
        payload = f"{size}|{hashlib.sha256(raw).hexdigest()[:16]}"
        out.append(LocalUnit("run", rid, start.strftime("%Y-%m-%d"), payload, split,
                             {"csv": str(r.csv), "keys": str(r.keys), "ts": str(r.ts)}))
        if split == "train":
            continue
        keys = parse_keys(raw)
        segs = segment_events([kp.unix_s for kp in keys], max_gap_s=KT_MAX_GAP_S, min_len=1)
        j = 0
        for a, b in segs:
            if b - a < KT_MIN_KEYS:
                continue
            codes = [key_code(kp.char) or "?" for kp in keys[a:b]]
            out.append(LocalUnit("segment", f"{rid}#{j}", rid, " ".join(codes), split,
                                 {"run": rid, "key_range": [a, b], "t0_unix": keys[a].unix_s,
                                  "t1_unix": keys[b - 1].unix_s}))
            j += 1
    return out


# --- SpanishBCBL MEG --------------------------------------------------------------------


def units_spanishbcbl(data: str | PathLike[str], **_: Any) -> list[LocalUnit]:
    from fidetype.benchmark.prepare import spanishbcbl_trials

    out = []
    for t in spanishbcbl_trials(data):
        out.append(LocalUnit("trial", t.id, t.clusters["participant"], t.text, t.split, {"id": t.id}))
    return out


# --- emg2qwerty -------------------------------------------------------------------------

E2Q_MIN_SESSIONS = 4


def units_emg2qwerty(data: str | PathLike[str], **_: Any) -> list[LocalUnit]:
    from fidetype.adapters.emg2qwerty import read_metadata

    root = Path(data)
    meta = root / "metadata.csv"
    if not meta.is_file():
        raise FileNotFoundError(f"no metadata.csv under {root}")
    rows = read_metadata(meta)
    by_user: dict[str, list] = defaultdict(list)
    for r in rows:
        by_user[r.user].append(r)
    out = []
    for u in sorted(by_user):
        ss = sorted(by_user[u], key=lambda r: r.session)
        n = len(ss)
        for k, r in enumerate(ss):
            if n >= E2Q_MIN_SESSIONS and k == n - 1:
                split = "test"
            elif n >= E2Q_MIN_SESSIONS and k == n - 2:
                split = "val"
            else:
                split = "train"
            f = root / f"{r.session}.hdf5"
            size = f.stat().st_size if f.is_file() else -1
            out.append(LocalUnit("session", r.session, u, f"{size}|{r.num_keystrokes}|{r.num_prompts}", split,
                                 {"file": str(f), "present": f.is_file()}))
    return out


LOADERS: dict[str, Callable[..., list[LocalUnit]]] = {
    "b2t25-t15": units_b2t25,
    "b2t24-t12": units_b2t24,
    "willett-hw": units_willett,
    "toronto-semg": units_toronto,
    "kt-semg": units_kt,
    "spanishbcbl-meg": units_spanishbcbl,
    "emg2qwerty": units_emg2qwerty,
}


def local_units(track: str, data: str | PathLike[str], **kw: Any) -> list[LocalUnit]:
    """Rebuild the units of ``track`` from a local copy (``data``; see ``TrackSpec.data_hint``)."""
    get_track(track)
    return LOADERS[track](data, **kw)


# ---------------------------------------------------------------------------
# Split files
# ---------------------------------------------------------------------------


def split_dir() -> Path:
    return Path(str(resources.files("fidetype.benchmark").joinpath("splits", f"tracks-v{TRACKS_VERSION}")))


def split_path(track: str) -> Path:
    return split_dir() / get_track(track).split_file


def counts_of(entries: Sequence[dict[str, str]]) -> dict[str, dict[str, int]]:
    c: dict[str, dict[str, int]] = defaultdict(dict)
    for e in entries:
        c[e["u"]][e["s"]] = c[e["u"]].get(e["s"], 0) + 1
    return {u: dict(sorted(v.items())) for u, v in sorted(c.items())}


def make_split(track: str, units: Sequence[LocalUnit]) -> dict[str, Any]:
    """Build the split file content from local units (maintainers only; needs the data)."""
    t = get_track(track)
    entries = [u.entry(track) for u in units]
    keys = [(e["u"], e["h"]) for e in entries]
    if len(set(keys)) != len(keys):
        raise ValueError("duplicate unit ids (hash collision or duplicate local ids)")
    bad = {e["u"] for e in entries} - set(t.units)
    if bad:
        raise ValueError(f"unit sets {bad} are not declared for {track}")
    return {"schema": SCHEMA, "track": track, "version": TRACKS_VERSION, "dataset": t.dataset, "licence": t.licence,
            "research_only": t.research_only, "salt": salt(track), "rule": t.rule, "units": dict(t.units),
            "counts": counts_of(entries), "digest": entries_digest(entries), "entries": entries}


def save_split(d: dict[str, Any], path: str | PathLike[str]) -> None:
    """One entry per line (small, diff-friendly)."""
    head = {k: v for k, v in d.items() if k != "entries"}
    rows = d["entries"]
    txt = json.dumps(head, indent=1, ensure_ascii=False)
    lines = [txt[: txt.rstrip().rfind("}")].rstrip() + ",", ' "entries": [']
    lines += ["  " + json.dumps(r, separators=(",", ":")) + ("," if i < len(rows) - 1 else "") for i, r in enumerate(rows)]
    lines += [" ]", "}"]
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")


def check_split(d: dict[str, Any]) -> list[str]:
    """Structural checks that need no data (CI): schema, salt, counts, digest, no plain text fields."""
    probs = []
    if d.get("schema") != SCHEMA:
        probs.append(f"schema {d.get('schema')!r}")
    t = TRACKS.get(d.get("track", ""))
    if t is None:
        return probs + [f"unknown track {d.get('track')!r}"]
    if d.get("salt") != salt(t.slug):
        probs.append("salt does not match the track")
    if d.get("licence") != t.licence or bool(d.get("research_only")) != t.research_only:
        probs.append("licence / research_only differ from the track definition")
    entries = d.get("entries", [])
    allowed = {"u", "h", "s", "g", "fp"}
    for e in entries:
        if set(e) != allowed:
            probs.append(f"entry fields {sorted(e)} (only {sorted(allowed)} allowed)")
            break
        if len(e["h"]) != 16 or len(e["fp"]) != 16 or len(e["g"]) != 12 or any(
                c not in "0123456789abcdef" for c in e["h"] + e["fp"] + e["g"]):
            probs.append(f"entry {e} is not hex hashes of the right length")
            break
    if d.get("counts") != counts_of(entries):
        probs.append("counts do not match the entries")
    if d.get("digest") != entries_digest(entries):
        probs.append("digest does not match the entries")
    if t.scored_set not in d.get("counts", {}) or t.scored_split not in d["counts"].get(t.scored_set, {}):
        probs.append(f"no scored entries ({t.scored_set}/{t.scored_split})")
    if len({(e["u"], e["h"]) for e in entries}) != len(entries):
        probs.append("duplicate entries")
    return probs


def load_split(track: str) -> dict[str, Any]:
    d = json.loads(split_path(track).read_text(encoding="utf-8"))
    if d.get("schema") != SCHEMA or d.get("track") != track:
        raise ValueError(f"{split_path(track)} is not a {SCHEMA} file of {track}")
    return d


# ---------------------------------------------------------------------------
# Verify and select
# ---------------------------------------------------------------------------


@dataclass
class VerifyReport:
    track: str
    n_expected: int
    checked_sets: list[str] = field(default_factory=list)
    skipped_sets: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)  # entry hashes (u/h) with no local unit
    fp_mismatch: list[str] = field(default_factory=list)
    split_mismatch: list[str] = field(default_factory=list)
    group_mismatch: list[str] = field(default_factory=list)
    extra: int = 0  # local units not in the split file (allowed; reported)

    @property
    def ok(self) -> bool:
        return not (self.missing or self.fp_mismatch or self.split_mismatch or self.group_mismatch) and bool(self.checked_sets)

    def to_dict(self) -> dict[str, Any]:
        return {**asdict(self), "ok": self.ok}

    def summary(self) -> str:
        head = f"{self.track}: " + ("OK" if self.ok else "MISMATCH")
        parts = [f"checked {', '.join(self.checked_sets) or 'nothing'} ({self.n_expected} entries)"]
        if self.skipped_sets:
            parts.append(f"skipped {', '.join(self.skipped_sets)} (no local input given)")
        for k in ("missing", "fp_mismatch", "split_mismatch", "group_mismatch"):
            v = getattr(self, k)
            if v:
                parts.append(f"{k} {len(v)} (e.g. {v[:3]})")
        if self.extra:
            parts.append(f"{self.extra} local units not in the split")
        return head + ": " + "; ".join(parts)


def verify_units(split: dict[str, Any], units: Sequence[LocalUnit]) -> VerifyReport:
    """Check local units against a split file. Sets with no local unit are skipped (reported)."""
    track = split["track"]
    local = {(u.set, id_hash(track, u.id)): u for u in units}
    present_sets = {u.set for u in units}
    rep = VerifyReport(track, 0)
    sets = sorted({e["u"] for e in split["entries"]})
    rep.checked_sets = [s for s in sets if s in present_sets]
    rep.skipped_sets = [s for s in sets if s not in present_sets]
    seen = set()
    for e in split["entries"]:
        if e["u"] not in present_sets:
            continue
        rep.n_expected += 1
        key = (e["u"], e["h"])
        u = local.get(key)
        tag = f"{e['u']}/{e['h']}"
        if u is None:
            rep.missing.append(tag)
            continue
        seen.add(key)
        if fingerprint(track, u.id, u.payload) != e["fp"]:
            rep.fp_mismatch.append(tag)
        if u.split != e["s"]:
            rep.split_mismatch.append(tag)
        if group_hash(track, u.group) != e["g"]:
            rep.group_mismatch.append(tag)
    rep.extra = sum(1 for k in local if k not in seen and k[0] in rep.checked_sets)
    return rep


def verify(track: str, data: str | PathLike[str], **kw: Any) -> VerifyReport:
    """Check a local dataset copy against the committed split file of ``track``."""
    return verify_units(load_split(track), local_units(track, data, **kw))


def select_units(split: dict[str, Any], units: Sequence[LocalUnit], split_name: str,
                 unit_set: str | None = None) -> list[LocalUnit]:
    """The local units of one split, in split-file order. Raises if any entry has no local unit."""
    track = split["track"]
    want = unit_set or get_track(track).scored_set
    local = {(u.set, id_hash(track, u.id)): u for u in units}
    out, missing = [], []
    for e in split["entries"]:
        if e["u"] != want or e["s"] != split_name:
            continue
        u = local.get((e["u"], e["h"]))
        if u is None:
            missing.append(e["h"])
        else:
            out.append(u)
    if missing:
        raise LookupError(f"{len(missing)} {want}/{split_name} entries have no local unit (run verify)")
    return out


def select(track: str, data: str | PathLike[str], split_name: str, unit_set: str | None = None,
           **kw: Any) -> list[LocalUnit]:
    """Map the split ids of one split to the local data (``LocalUnit.ref`` is the adapter input)."""
    return select_units(load_split(track), local_units(track, data, **kw), split_name, unit_set)


def check_v01_equivalence(track: str) -> dict[str, Any]:
    """For a track with ``v01_track``: the v0.1 scored ids hash to the v0.2 entries with the same split.

    Needs only the committed files (v0.1 split files hold plain ids).
    """
    from fidetype.benchmark.splits import load_split as load_v01

    t = get_track(track)
    if not t.v01_track:
        raise ValueError(f"{track} has no v0.1 track")
    v1 = load_v01(t.v01_track)
    d = load_split(track)
    unit = "sentence" if track == "toronto-semg" else "trial"
    v2 = {e["h"]: e["s"] for e in d["entries"] if e["u"] == unit}
    v1_rows = [(r["id"], r["split"]) for r in v1.scored]
    for name, o in v1.open.items():
        for i in o.get("ids", []):
            v1_rows.append((i, name))
    mismatch = [i for i, s in v1_rows if v2.get(id_hash(track, i)) != s]
    return {"v01_track": t.v01_track, "n_v01": len(v1_rows), "n_v02": len(v2), "mismatch": mismatch}


# ---------------------------------------------------------------------------
# Command line
# ---------------------------------------------------------------------------


def _kw(a: argparse.Namespace) -> dict[str, Any]:
    return {"cache": getattr(a, "cache", None), "sentences": getattr(a, "sentences", None)}


def cmd_list(_a) -> int:
    for t in TRACKS.values():
        flag = "  RESEARCH ONLY" if t.research_only else ""
        print(f"{t.slug:16s} {t.modality:13s} {t.licence:16s}{flag}  {t.title}")
    return 0


def cmd_info(a) -> int:
    t = get_track(a.track)
    d = t.to_dict()
    try:
        s = load_split(a.track)
        d["split_counts"] = s["counts"]
        d["split_digest"] = s["digest"]
    except FileNotFoundError:
        d["split_counts"] = None
    print(json.dumps(d, indent=1, ensure_ascii=False))
    return 0


def cmd_verify(a) -> int:
    rep = verify(a.track, a.data, **_kw(a))
    print(rep.summary())
    if a.json:
        Path(a.json).write_text(json.dumps(rep.to_dict(), indent=1), encoding="utf-8")
    return 0 if rep.ok else 1


def cmd_select(a) -> int:
    units = select(a.track, a.data, a.split, a.unit, **_kw(a))
    rows = [{"id": u.id, "split": u.split, "ref": u.ref} for u in units]
    txt = "\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n"
    if a.out:
        Path(a.out).write_text(txt, encoding="utf-8")
        print(f"{len(rows)} units -> {a.out} (local file: never commit it)")
    else:
        sys.stdout.write(txt)
    return 0


def cmd_make(a) -> int:
    units = local_units(a.track, a.data, **_kw(a))
    d = make_split(a.track, units)
    out = Path(a.out) if a.out else split_path(a.track)
    out.parent.mkdir(parents=True, exist_ok=True)
    save_split(d, out)
    print(f"{a.track}: {json.dumps(d['counts'])} -> {out}")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m fidetype.benchmark.tracks", description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list").set_defaults(fn=cmd_list)
    p = sub.add_parser("info")
    p.add_argument("track")
    p.set_defaults(fn=cmd_info)
    for name, fn in (("verify", cmd_verify), ("select", cmd_select), ("make", cmd_make)):
        p = sub.add_parser(name)
        p.add_argument("track", choices=sorted(TRACKS))
        p.add_argument("--data", required=True, help="local dataset copy (see `info <track>`: data_hint)")
        p.add_argument("--cache", help="toronto-semg sentence set: the window cache folder")
        p.add_argument("--sentences", help="toronto-semg sentence set: eng_tatoeba_heldout.txt")
        if name == "verify":
            p.add_argument("--json", help="write the report as JSON")
        if name == "select":
            p.add_argument("--split", required=True)
            p.add_argument("--unit", help="unit set (default: the scored set)")
            p.add_argument("--out")
        if name == "make":
            p.add_argument("--out", help="default: the committed split file")
        p.set_defaults(fn=fn)
    a = ap.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    raise SystemExit(main())
