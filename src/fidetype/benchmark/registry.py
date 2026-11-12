"""Dataset and track registry of the open benchmark (v0.1).

A **dataset** entry says where the data lives, under which licence, which
version we tested, and how to check the download. The benchmark never
ships data: the user downloads every dataset from its original source.

A **track** is one scored task on one dataset: a fixed split, a text
normalisation, a cluster unit for the confidence intervals, and the
user model for eWPM. Split files live in ``splits/v0.1/`` next to this
module. They hold only trial ids, cluster labels and text hashes.

The values here are data, not code paths. Change them only with a new
benchmark version (see ``wiki/concepts/open-benchmark.md``).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

BENCHMARK_VERSION = "0.1"


@dataclass(frozen=True)
class Dataset:
    """A public dataset that a track uses. Download-only."""

    slug: str
    title: str
    citation: str
    url: str
    licence: str
    #: True if the licence forbids commercial use (CC BY-NC and similar).
    non_commercial: bool
    version: str
    #: Files the user must download, each {"name", "bytes", "sha256" or "md5"}.
    files: tuple[dict[str, Any], ...]
    download: str
    notice: str = ""

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["files"] = [dict(f) for f in self.files]
        return d


@dataclass(frozen=True)
class UserModel:
    """The documented simulated user that turns decisions into eWPM.

    ``config`` holds the overrides for
    :meth:`fidetype.interact.simulated_user.UserConfig.aac_gaze`. The
    neural input rate (``chars_per_min``) is set per track from the data.
    """

    name: str
    config: dict[str, Any]
    #: The no-BCI reference: typing with the fallback method only.
    gaze_chars_per_min: float = 20.0
    note: str = ""

    def user_config(self):  # -> UserConfig (lazy import: no cycle)
        from fidetype.interact.simulated_user import UserConfig

        return UserConfig.aac_gaze(**self.config)


@dataclass(frozen=True)
class Track:
    """One scored benchmark task."""

    slug: str
    title: str
    dataset: str
    modality: str
    language: str
    split_file: str
    #: The text normalisation applied to truth and hypotheses before scoring.
    normalizer: str
    #: The cluster unit for the bootstrap CIs: a key of the split clusters,
    #: or "two_way:<a>,<b>" for a crossed bootstrap over two keys.
    ci_unit: str
    user_model: UserModel
    #: The split that a submission must cover.
    scored_split: str = "test"
    #: Splits that a decoder may use for training or calibration.
    open_splits: tuple[str, ...] = ("train", "val")
    research_only: bool = False
    notes: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["user_model"] = asdict(self.user_model)
        return d


DATASETS: dict[str, Dataset] = {
    "spanishbcbl": Dataset(
        slug="spanishbcbl",
        title="SpanishBCBL typing MEG (Brain2Qwerty v1/v2 data)",
        citation="Levy et al., Nature Neuroscience 29 (2026), doi:10.1038/s41593-026-02303-2; "
        "dataset bcbl190626/SpanishBCBL",
        url="https://huggingface.co/datasets/bcbl190626/SpanishBCBL",
        licence="CC BY-NC 4.0",
        non_commercial=True,
        version="v1 (Hugging Face snapshot read 2026-11-08; 316 MEG files, 251.36 GB)",
        files=(
            {"name": "MEG/FIF/**/*.fif + MEG/logs/*.mat", "bytes": 251_360_000_000, "sha256": None,
             "note": "no single archive; verify per-file sizes against the Hugging Face file list"},
        ),
        download=(
            "Download from the original source only: `huggingface-cli download bcbl190626/SpanishBCBL "
            "--repo-type dataset --include 'MEG/*' --local-dir <root>`. Then build the cache: "
            "`python tools/data/preprocess_spanishbcbl.py --root <root> --cache <cache>`. "
            "Fidetype does not mirror or redistribute any file."
        ),
        notice=(
            "CC BY-NC 4.0: research and benchmark use only. Fidetype ships no SpanishBCBL data and no "
            "weights trained on it. Results derived from it are research-only."
        ),
    ),
    "brain-to-text-25": Dataset(
        slug="brain-to-text-25",
        title="Brain-to-Text '25, participant T15 copy task (Card et al. 2024)",
        citation="Card et al., NEJM 391 (2024), doi:10.1056/NEJMoa2314132; Dryad doi:10.5061/dryad.dncjsxm85",
        url="https://doi.org/10.5061/dryad.dncjsxm85",
        licence="CC0 1.0",
        non_commercial=False,
        version="Dryad version 2025-07-03",
        files=(
            {"name": "t15_copyTask.pkl", "bytes": 57_786_348,
             "sha256": "7313b9a1102794cfd31455a85d3d16a1aca962aa730a7134d9346fb8f5e165e3"},
        ),
        download=(
            "Download `t15_copyTask.pkl` from Dryad (login needed) or a mirror with the same SHA-256. "
            "Load it only with `fidetype.adapters.b2t25.load_copytask` (safe unpickler, digest check)."
        ),
        notice="CC0. The companion code repository has no licence; Fidetype does not copy it.",
    ),
    "toronto-semg": Dataset(
        slug="toronto-semg",
        title="Toronto forearm sEMG typing (Achituve et al. 2025)",
        citation="Achituve, Beutel, Eby, Fetaya, Koivisto, Zariffa, Sci Data 12:440 (2025); "
        "Borealis doi:10.5683/SP3/KV65VI",
        url="https://doi.org/10.5683/SP3/KV65VI",
        licence="CC BY 4.0",
        non_commercial=False,
        version="Borealis version 1 (released 2024-11-04), file id 836662",
        files=(
            {"name": "EMG typing dataset.zip", "bytes": 2_766_730_294,
             "sha256": "73c4f925b81c627643373dc271878a6fda6c0b59c521ae856a5610c8e5de7ef3",
             "md5": "27d052ee1b5dcdf1e5eb0b875c698f6d"},
        ),
        download=(
            "Download from `https://borealisdata.ca/api/access/datafile/836662`. Extract only the data "
            "files (`.rhd`, `.txt`, `.csv`). Build the window cache with "
            "`experiments/2026-11-11-emg-toronto/prep.py`."
        ),
        notice="CC BY 4.0: attribution required. The baseline code (CC BY-SA 4.0) is not copied.",
    ),
    "tatoeba-eng": Dataset(
        slug="tatoeba-eng",
        title="Tatoeba English sentences (held-out set of the Fidetype char LM)",
        citation="Tatoeba contributors, https://tatoeba.org",
        url="https://downloads.tatoeba.org/exports/per_language/eng/eng_sentences.tsv.bz2",
        licence="CC BY 2.0 FR",
        non_commercial=False,
        version="export of 2026-11-08 (24 933 870 bytes)",
        files=({"name": "eng_sentences.tsv.bz2", "bytes": 24_933_870, "sha256": None,
                "note": "see src/fidetype/lm/corpora.md for the digest prefix and the held-out rule"},),
        download="Download the export, then build the held-out list as in `src/fidetype/lm/corpora.md`.",
        notice="Sentences from Tatoeba (https://tatoeba.org), by the Tatoeba contributors, CC BY 2.0 FR.",
    ),
}

_MEG_USER = UserModel(
    name="aac-gaze-v1 @ 152 chars/min",
    config={"chars_per_min": 152.0},
    note="Word model of fidetype.interact.simulated_user (UserConfig.aac_gaze). Neural input at the "
    "Brain2Qwerty v1 typing rate.",
)
_B2T_USER = UserModel(
    name="aac-gaze-v1 @ 159.27 chars/min",
    config={"chars_per_min": 159.2741387635318},
    note="Neural input at the measured T15 speech rate of the 125k-vocabulary trials "
    "(experiments/2026-11-10-b2t25-trust/results/prep.json).",
)
_EMG_USER = UserModel(
    name="aac-gaze-v1 @ 75.76 chars/min",
    config={"chars_per_min": 60.0 / 0.792},
    note="Neural input at one key per 0.792 s (the median inter-key interval of the dataset).",
)

TRACKS: dict[str, Track] = {
    "spanishbcbl-meg-async": Track(
        slug="spanishbcbl-meg-async",
        title="MEG typing, asynchronous (SpanishBCBL)",
        dataset="spanishbcbl",
        modality="meg",
        language="es",
        split_file="spanishbcbl-meg-async.json",
        normalizer="char28",
        ci_unit="two_way:sentence,participant",
        user_model=_MEG_USER,
        research_only=True,
        notes=(
            "Async: the decoder gets the MEG segment (first key - 0.4 s to last key + 0.5 s), its length and "
            "the participant index. No key times at test.",
            "Split by sentence (SHA-1 bucket of the normalised text, 80/10/10): no test sentence is in train.",
            "S1/ses1_block1 is not in the split (its MEG file ends before the typing log).",
            "6 of the 17 test sentences have a close variant in train (short/long or singular/plural forms).",
        ),
    ),
    "b2t25-t15-copytask": Track(
        slug="b2t25-t15-copytask",
        title="Intracortical attempted speech (Brain-to-Text '25, T15)",
        dataset="brain-to-text-25",
        modality="intracortical",
        language="en",
        split_file="b2t25-t15-copytask.json",
        normalizer="words",
        ci_unit="day",
        user_model=_B2T_USER,
        open_splits=("cal",),
        notes=(
            "Input: the published per-trial RNN phoneme logits (41 classes). A submission decodes these logits "
            "or the published sentence; it does not retrain the RNN.",
            "125k-vocabulary trials only. Per day: the first half of the trials is `cal`, the second half `test`.",
        ),
    ),
    "toronto-semg-composed": Track(
        slug="toronto-semg-composed",
        title="Forearm sEMG key presses, composed sentences (Toronto)",
        dataset="toronto-semg",
        modality="emg",
        language="en",
        split_file="toronto-semg-composed.json",
        normalizer="none",
        ci_unit="participant",
        user_model=_EMG_USER,
        open_splits=("train-day1", "cal"),
        notes=(
            "COMPOSED sentences: the dataset has isolated key presses, not text. Each test sentence takes, per "
            "character, one real day-2 press of that character from the same participant. This tests key "
            "decoding plus the LM and the trust layer; it is not natural typing.",
            "Sentences come from the Tatoeba held-out set (not in the LM training text). cal and test texts "
            "are disjoint.",
            "An entry states its training regime: cross-session, session-calibrated or cross-subject.",
        ),
    ),
}


def get_track(slug: str) -> Track:
    try:
        return TRACKS[slug]
    except KeyError:
        raise KeyError(f"unknown track {slug!r}; known: {sorted(TRACKS)}") from None


def normalize(text: str, normalizer: str) -> str:
    """Apply the named text normalisation of a track."""
    if normalizer == "char28":
        from fidetype.streams.vocab import normalize_text

        return normalize_text(text)
    if normalizer == "words":
        from fidetype.adapters.b2t25 import normalize_words

        return normalize_words(text)
    if normalizer == "none":
        return " ".join(text.split())
    raise ValueError(f"unknown normalizer {normalizer!r}")
