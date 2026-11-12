"""SpanishBCBL MEG typing dataset: file discovery, log parsing, alignment, text.

This module is our own code. We read the Brain2Qwerty loader (CC BY-NC)
only to learn the file quirks. No code is copied from it.

The dataset (CC BY-NC 4.0, research use only) has this layout::

    <root>/MEG/FIF/<NN>_<code>/<yymmdd>/<name>.fif     raw MEG (Elekta, 1 kHz)
    <root>/MEG/logs/S<N>-session<k>_block<b>_list<l>.mat   behavioural log
    <root>/MEG/logs/S<N>-session<k>-<b>.mat               (S1 and S2 only)
    <root>/_filelist.tsv                                    path, size, sha256

The module has four parts:

1. File discovery: :func:`parse_fif_name`, :func:`discover_blocks`.
2. Log parsing: :func:`parse_log` (needs scipy).
3. Clock alignment: :func:`drop_start_ramp`, :func:`fit_clock`,
   :func:`align_block`. They use numpy only.
4. Text: :func:`key_char`, :func:`typed_text_from_keys`,
   :func:`align_chars`, :func:`trial_text`. They use the standard library only.

Only :func:`parse_log` needs scipy. Only the preprocessing module needs MNE.
"""

from __future__ import annotations

import difflib
import re
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable, Sequence

import numpy as np

from fidetype.streams.vocab import normalize_text

# ---------------------------------------------------------------------------
# Licence (M5-03: download-only, research only)
# ---------------------------------------------------------------------------

#: The dataset licence. Non-commercial: research and benchmark use only.
LICENCE = "CC-BY-NC-4.0"
NON_COMMERCIAL = True
#: The only source. Fidetype never mirrors, vendors or redistributes the data.
SOURCE_URL = "https://huggingface.co/datasets/bcbl190626/SpanishBCBL"
DOWNLOAD_COMMAND = (
    "huggingface-cli download bcbl190626/SpanishBCBL --repo-type dataset --include 'MEG/*' --local-dir <root>"
)
LICENCE_NOTICE = (
    "SpanishBCBL is CC BY-NC 4.0 (research use only). Download it yourself from "
    f"{SOURCE_URL}. Fidetype ships no SpanishBCBL data and no weights trained on it; "
    "anything derived from it (caches, streams, weights, results) is for non-commercial research only."
)


def licence_notice() -> str:
    """Return the licence notice that every SpanishBCBL entry point shows."""
    return LICENCE_NOTICE


# ---------------------------------------------------------------------------
# Dataset facts
# ---------------------------------------------------------------------------

#: Trigger codes (the log header fields trigstim, trigblock, triggerpause).
WORD_CODE = 10
BLOCK_CODE = 20
PAUSE_CODE = 30
#: Windows virtual-key codes with a special meaning.
VK_BACKSPACE = 8
VK_RETURN = 13

#: Groups of subject IDs that are the same person.
PARTICIPANT_GROUPS: tuple[tuple[int, ...], ...] = ((1, 18), (4, 14), (5, 10, 21))
#: Subjects to leave out completely, with the reason.
EXCLUDED_SUBJECTS: dict[int, str] = {23: "metallic implant (dataset card)"}
#: Subjects to keep, but with a note in the sidecar.
SUBJECT_NOTES: dict[int, str] = {13: "left-handed"}

#: Session folders that duplicate another folder (byte-identical files).
#: Key: "<subject folder>/<date>", value: the folder we keep.
DUPLICATE_SESSION_DIRS: dict[str, str] = {
    "02__2810/220412": "02_2810/220412",
    "04_3660/230405": "05_3660/230405",
    "14_9876/231115": "14_9875/231115",
}

#: File-name overrides: (subject folder, date, lower-case stem) -> block number.
#: S1 session 1: Block2.fif is short and has no matching log run. Block3.fif
#: is the repeated block 2. We treat Block3 as block 2, retry 9 (it wins).
BLOCK_OVERRIDES: dict[tuple[str, str, str], tuple[int, int]] = {
    ("01_9228", "220404", "block3"): (2, 9),
}

#: S1 and S2 use log names "S<N>-session<k>-<b>.mat". In session 2 the block
#: numbers in the log names are swapped (block 1 -> "-2", block 2 -> "-1").
#: The preprocessing also checks the log choice with the alignment score.
LOG_BLOCK_SWAP: dict[int, set[int]] = {1: {2}, 2: {2}}

#: Number of training trials (with visual feedback) at the start of each block.
N_TRAINING_TRIALS = 2


def participant_id(subject: int) -> str:
    """Return the unique-participant ID for a subject number.

    The ID is "P" plus the smallest subject number of the person, with two
    digits. For example S18 gives "P01", because S1 and S18 are one person.
    """
    for group in PARTICIPANT_GROUPS:
        if subject in group:
            return f"P{min(group):02d}"
    return f"P{subject:02d}"


# ---------------------------------------------------------------------------
# 1. File discovery
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FifName:
    """The parsed meaning of one .fif file name.

    ``kind`` is one of:

    - ``"block"``: a typing block (``block``, ``retry`` set),
    - ``"split"``: a split continuation (``name-1.fif``) of another file,
    - ``"localizer"``: a tapping or typing localizer,
    - ``"excluded"``: a known bad or extra file (``block2fail``, ``testdavid``,
      ``Emptyroom``),
    - ``"unknown"``: no rule matches.
    """

    kind: str
    block: int | None = None
    retry: int = 0
    base_stem: str = ""
    part: int = 0


_SPLIT_RE = re.compile(r"^(?P<base>.+)-(?P<part>\d+)$")
# "block", "Block", or the typo "bolck"; one block digit; then an optional
# retry number, with or without "_" ("block2_1", "block22").
_BLOCK_RE = re.compile(r"b(?:lo|ol)ck(?P<block>\d)(?:_?(?P<retry>\d+))?$")


def parse_fif_name(filename: str) -> FifName:
    """Parse a .fif file name (with or without the folder) into a :class:`FifName`.

    Examples: ``block1.fif`` -> block 1; ``bolck2.fif`` -> block 2;
    ``block22.fif`` -> block 2, retry 2; ``block2_1.fif`` -> block 2, retry 1;
    ``d2_block1.fif`` -> block 1; ``block1-1.fif`` -> split part 1 of
    ``block1``; ``tapping.fif`` -> localizer; ``block2fail.fif`` -> excluded.
    """
    stem = Path(filename).name
    if stem.lower().endswith(".fif"):
        stem = stem[:-4]
    low = stem.lower()
    m = _SPLIT_RE.match(low)
    if m:
        return FifName("split", base_stem=m.group("base"), part=int(m.group("part")))
    if "tapping" in low or "typing" in low:
        return FifName("localizer", base_stem=low)
    if "fail" in low or "testdavid" in low or "emptyroom" in low:
        return FifName("excluded", base_stem=low)
    m = _BLOCK_RE.search(low)
    if m:
        retry = int(m.group("retry")) if m.group("retry") else 0
        return FifName("block", block=int(m.group("block")), retry=retry, base_stem=low)
    return FifName("unknown", base_stem=low)


_LOG_RE_A = re.compile(r"^S(?P<sub>\d+)-session(?P<ses>\d+)_block(?P<block>\d+)_list(?P<list>\d+)\.mat$")
_LOG_RE_B = re.compile(r"^S(?P<sub>\d+)-session(?P<ses>\d+)-(?P<block>\d+)\.mat$")


def parse_log_name(filename: str) -> tuple[int, int, int] | None:
    """Return (subject, session, block) for a log file name, or None.

    For S1 and S2 (names ``S<N>-session<k>-<b>.mat``) the function applies the
    known block swap of session 2 (see :data:`LOG_BLOCK_SWAP`).
    """
    name = Path(filename).name
    m = _LOG_RE_A.match(name)
    if m:
        return int(m.group("sub")), int(m.group("ses")), int(m.group("block"))
    m = _LOG_RE_B.match(name)
    if m:
        sub, ses, blk = int(m.group("sub")), int(m.group("ses")), int(m.group("block"))
        if ses in LOG_BLOCK_SWAP.get(sub, set()) and blk in (1, 2):
            blk = 3 - blk
        return sub, ses, blk
    return None


def subject_number(folder: str) -> int:
    """Return the subject number of a subject folder ("08_11374" -> 8)."""
    return int(folder.split("_")[0])


@dataclass
class BlockSpec:
    """One typing block: the raw file, its split parts and its log."""

    subject: str  # "S25"
    subject_num: int
    participant: str  # "P25"
    session: str  # "ses1"
    session_num: int
    session_dir: str  # "25_12032/240529"
    block: str  # "block1"
    block_num: int
    fif: str  # path relative to the data root, forward slashes
    split_parts: list[str] = field(default_factory=list)
    log: str | None = None  # path relative to the data root
    alt_logs: list[str] = field(default_factory=list)  # other logs of the same session
    retry: int = 0
    notes: list[str] = field(default_factory=list)

    @property
    def key(self) -> str:
        return f"{self.subject}/{self.session}_{self.block}"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Discovery:
    blocks: list[BlockSpec]
    excluded: list[dict[str, str]]  # {"path": ..., "reason": ...}


def discover_blocks(fif_paths: Iterable[str], log_names: Iterable[str]) -> Discovery:
    """Find all typing blocks and match each one to its log.

    ``fif_paths`` are paths relative to the data root, for example
    ``"MEG/FIF/25_12032/240529/block1.fif"``. ``log_names`` are the file names
    in ``MEG/logs``. The function reads no files, so it works on any list of
    names (for tests, or from ``_filelist.tsv``).
    """
    excluded: list[dict[str, str]] = []
    logs_by_key: dict[tuple[int, int, int], list[str]] = defaultdict(list)
    logs_by_session: dict[tuple[int, int], list[str]] = defaultdict(list)
    for name in sorted(set(log_names)):
        parsed = parse_log_name(name)
        if parsed is None:
            continue
        logs_by_key[parsed].append(name)
        logs_by_session[parsed[:2]].append(name)

    # Group files by (subject number, date folder). Drop duplicate folders.
    by_session: dict[tuple[int, str], list[tuple[str, str, str]]] = defaultdict(list)
    for rel in sorted(set(p.replace("\\", "/") for p in fif_paths)):
        parts = rel.split("/")
        if len(parts) < 3 or not rel.lower().endswith(".fif"):
            continue
        sub_dir, date, fname = parts[-3], parts[-2], parts[-1]
        sess_key = f"{sub_dir}/{date}"
        if sess_key in DUPLICATE_SESSION_DIRS:
            excluded.append({"path": rel, "reason": f"duplicate session folder of {DUPLICATE_SESSION_DIRS[sess_key]}"})
            continue
        try:
            num = subject_number(sub_dir)
        except ValueError:
            excluded.append({"path": rel, "reason": "subject folder name not understood"})
            continue
        if num in EXCLUDED_SUBJECTS:
            excluded.append({"path": rel, "reason": f"subject S{num} excluded: {EXCLUDED_SUBJECTS[num]}"})
            continue
        by_session[(num, date)].append((rel, sub_dir, fname))

    # Session number = rank of the date folder within the subject number.
    dates_by_subject: dict[int, list[str]] = defaultdict(list)
    for num, date in by_session:
        dates_by_subject[num].append(date)
    blocks: list[BlockSpec] = []
    for (num, date), files in sorted(by_session.items()):
        ses_num = sorted(dates_by_subject[num]).index(date) + 1
        splits: dict[str, list[str]] = defaultdict(list)
        cands: dict[int, list[tuple[int, str, str]]] = defaultdict(list)  # block -> (retry, rel, sub_dir)
        for rel, sub_dir, fname in files:
            fn = parse_fif_name(fname)
            if fn.kind == "split":
                splits[f"{sub_dir}/{fn.base_stem}"].append(rel)
                continue
            if fn.kind == "localizer":
                excluded.append({"path": rel, "reason": "localizer (tapping/typing), not a typing block"})
                continue
            if fn.kind in ("excluded", "unknown"):
                excluded.append({"path": rel, "reason": f"{fn.kind} file name"})
                continue
            blk, retry = BLOCK_OVERRIDES.get((sub_dir, date, fn.base_stem), (fn.block, fn.retry))
            cands[blk].append((retry, rel, sub_dir))
        for blk, lst in sorted(cands.items()):
            lst.sort()
            for retry, rel, _ in lst[:-1]:
                excluded.append({"path": rel, "reason": f"superseded by a later recording of block {blk}"})
            retry, rel, sub_dir = lst[-1]
            stem = Path(rel).name[:-4].lower()
            parts = sorted(splits.get(f"{sub_dir}/{stem}", []))
            log_list = logs_by_key.get((num, ses_num, blk), [])
            notes = [SUBJECT_NOTES[num]] if num in SUBJECT_NOTES else []
            if not log_list:
                excluded.append({"path": rel, "reason": f"no log for S{num} session {ses_num} block {blk}"})
                continue
            if len(log_list) > 1:
                notes.append(f"several logs match: {log_list}; first one used")
            blocks.append(
                BlockSpec(
                    subject=f"S{num}",
                    subject_num=num,
                    participant=participant_id(num),
                    session=f"ses{ses_num}",
                    session_num=ses_num,
                    session_dir=f"{sub_dir}/{date}",
                    block=f"block{blk}",
                    block_num=blk,
                    fif=rel,
                    split_parts=parts,
                    log=f"MEG/logs/{log_list[0]}",
                    alt_logs=[f"MEG/logs/{n}" for n in logs_by_session[(num, ses_num)] if n != log_list[0]],
                    retry=retry,
                    notes=notes,
                )
            )
        # Split parts whose main file was not kept are already covered by the
        # main file's reason. Report orphans only.
        kept_or_listed = {Path(r).name[:-4].lower() for r, _, _ in files}
        for base, rels in splits.items():
            if base.split("/")[-1] not in kept_or_listed:
                for rel in rels:
                    excluded.append({"path": rel, "reason": "split part without a main file"})
    blocks.sort(key=lambda b: (b.subject_num, b.session_num, b.block_num))
    return Discovery(blocks=blocks, excluded=excluded)


def read_filelist(root: str | Path) -> dict[str, int]:
    """Read ``_filelist.tsv``. Return {relative path: size in bytes}."""
    out: dict[str, int] = {}
    with open(Path(root) / "_filelist.tsv", encoding="utf-8") as fh:
        next(fh, None)
        for line in fh:
            cols = line.rstrip("\n").split("\t")
            if len(cols) >= 2 and cols[1].isdigit():
                out[cols[0]] = int(cols[1])
    return out


def is_complete(root: str | Path, rel: str, sizes: dict[str, int]) -> bool:
    """True if the local file exists and its size equals the listed size."""
    p = Path(root) / rel
    return rel in sizes and p.is_file() and p.stat().st_size == sizes[rel]


def complete_subjects(root: str | Path, sizes: dict[str, int] | None = None) -> dict[int, bool]:
    """Return {subject number: all .fif files of the subject are complete}.

    Duplicate session folders do not count, because we never read them.
    """
    sizes = read_filelist(root) if sizes is None else sizes
    state: dict[int, bool] = {}
    for rel in sizes:
        parts = rel.split("/")
        if not (rel.startswith("MEG/FIF/") and rel.lower().endswith(".fif") and len(parts) == 5):
            continue
        if f"{parts[2]}/{parts[3]}" in DUPLICATE_SESSION_DIRS:
            continue
        try:
            num = subject_number(parts[2])
        except ValueError:
            continue
        state[num] = state.get(num, True) and is_complete(root, rel, sizes)
    return state


def discover_from_root(root: str | Path) -> Discovery:
    """Run :func:`discover_blocks` on the file list of a data root."""
    root = Path(root)
    sizes = read_filelist(root)
    fifs = [p for p in sizes if p.startswith("MEG/FIF/")]
    logs = [p.split("/")[-1] for p in sizes if p.startswith("MEG/logs/")]
    if not logs:  # fall back to the folder
        logs = [p.name for p in (root / "MEG" / "logs").glob("*.mat")]
    return discover_blocks(fifs, logs)


# ---------------------------------------------------------------------------
# 2. Log parsing
# ---------------------------------------------------------------------------


@dataclass
class KeyPress:
    keycode: int  # Windows virtual-key code (= the MEG trigger value)
    cooked: int  # CookedKey (character code, -1 or 0 if none)
    char: str  # see key_char()
    t_trig: float  # trigger send time (log trigger clock, s)
    t_queue: float  # keyboard-queue time (other clock, s)


@dataclass
class Word:
    text: str
    t_trig: float


@dataclass
class LogTrial:
    idx: int
    sentence: str  # raw target sentence from the log
    is_training: bool
    keys: list[KeyPress]
    words: list[Word]


@dataclass
class BlockLog:
    trials: list[LogTrial]
    block_trig: list[float]
    codes: dict[str, int]

    def events(self) -> tuple[np.ndarray, np.ndarray, list[tuple[str, int, int]]]:
        """Return (times, codes, refs) of all trigger-like log events, sorted by time.

        ``refs[i]`` is (kind, trial, index in the trial), kind in word | key | block.
        """
        rows: list[tuple[float, int, tuple[str, int, int]]] = []
        for tr in self.trials:
            for j, w in enumerate(tr.words):
                rows.append((w.t_trig, self.codes["word"], ("word", tr.idx, j)))
            for j, k in enumerate(tr.keys):
                rows.append((k.t_trig, k.keycode, ("key", tr.idx, j)))
        for j, t in enumerate(self.block_trig):
            rows.append((t, self.codes["block"], ("block", -1, j)))
        rows.sort(key=lambda r: r[0])
        return (
            np.array([r[0] for r in rows], float),
            np.array([r[1] for r in rows], int),
            [r[2] for r in rows],
        )


def _records(x: Any) -> list[dict]:
    """Turn one loadmat struct (array) into a list of dicts."""
    if x is None:
        return []
    if isinstance(x, dict):
        return [x]
    if hasattr(x, "_fieldnames"):
        return [{k: getattr(x, k) for k in x._fieldnames}]
    if isinstance(x, (list, tuple, np.ndarray)):
        out: list[dict] = []
        for item in x.ravel() if isinstance(x, np.ndarray) else x:
            out.extend(_records(item))
        return out
    return []


def parse_log(path: str | Path) -> BlockLog:
    """Read a block log (.mat) with ``scipy.io.loadmat(simplify_cells=True)``."""
    import scipy.io

    mat = scipy.io.loadmat(str(path), simplify_cells=True)
    pr = mat["pr_trials"]
    codes = {
        "word": int(mat.get("trigstim", WORD_CODE)),
        "block": int(mat.get("trigblock", BLOCK_CODE)),
        "pause": int(mat.get("triggerpause", PAUSE_CODE)),
    }
    seqs = pr["sequence"]
    seqs = [seqs] if isinstance(seqs, str) else list(seqs)
    trials: list[LogTrial] = []
    for i in range(len(seqs)):
        presses = _records(pr["kp"][i])
        ktrig = np.atleast_1d(np.asarray(pr["keyTrig"][i], dtype=float)).ravel()
        n = min(len(presses), len(ktrig))
        keys = []
        for p, tt in zip(presses[:n], ktrig[:n]):
            kc, ck = int(p["Keycode"]), int(p["CookedKey"])
            keys.append(KeyPress(kc, ck, key_char(ck, kc), float(tt), float(p["Time"])))
        words = [Word(str(w["stim"]), float(w["trigTime"])) for w in _records(pr["rsvp"][i])]
        trials.append(LogTrial(i, str(seqs[i]), i < N_TRAINING_TRIALS, keys, words))
    block_trig = [float(t) for t in np.atleast_1d(np.asarray(pr["blockTrig"], dtype=float)).ravel()]
    return BlockLog(trials, block_trig, codes)


# ---------------------------------------------------------------------------
# 3. Clock alignment (numpy only)
# ---------------------------------------------------------------------------


def drop_start_ramp(times: np.ndarray, codes: np.ndarray, max_gap: float = 0.1, min_len: int = 16) -> int:
    """Return the number of leading events that form the start-up test ramp.

    The ramp starts with code 1 and has events less than ``max_gap`` s apart.
    It counts only if it has at least ``min_len`` events.
    """
    if len(codes) == 0 or codes[0] != 1:
        return 0
    n = 1
    while n < len(times) and times[n] - times[n - 1] < max_gap:
        n += 1
    return n if n >= min_len else 0


@dataclass
class ClockFit:
    slope: float
    intercept: float  # meg_t = slope * log_t + intercept
    match: np.ndarray  # per log event: index into the MEG events, or -1
    n_seq_pairs: int
    resid_ms_median: float
    resid_ms_p95: float
    resid_ms_max: float

    def predict(self, log_t: np.ndarray | float) -> np.ndarray:
        return self.slope * np.asarray(log_t, float) + self.intercept


def _line_fit(x: np.ndarray, y: np.ndarray) -> tuple[float, float]:
    # Centre x for numerical stability (log times are about 1e3-1e5 s).
    x0 = float(np.mean(x))
    slope, icpt = np.polyfit(x - x0, y, 1)
    return float(slope), float(icpt - slope * x0)


def fit_clock(
    meg_t: np.ndarray,
    meg_code: np.ndarray,
    log_t: np.ndarray,
    log_code: np.ndarray,
    tol: float = 0.02,
) -> ClockFit:
    """Fit ``meg_t = slope * log_t + intercept`` and match events one to one.

    Steps:

    1. Match the two code sequences in order (``difflib`` matching blocks).
    2. Fit a line on the matched pairs. Drop pairs that are more than ``tol``
       off the line, and fit again (3 rounds).
    3. Match again by time: each log event takes the nearest unused MEG event
       with the same code within ``tol`` of the line.
    4. Fit a final line on these pairs and compute the residuals.

    Raises ``ValueError`` if fewer than 3 pairs match.
    """
    meg_t = np.asarray(meg_t, float)
    meg_code = np.asarray(meg_code, int)
    log_t = np.asarray(log_t, float)
    log_code = np.asarray(log_code, int)
    sm = difflib.SequenceMatcher(None, meg_code.tolist(), log_code.tolist(), autojunk=False)
    pairs = [(b.a + k, b.b + k) for b in sm.get_matching_blocks() for k in range(b.size)]
    if len(pairs) < 3:
        raise ValueError(f"only {len(pairs)} code-sequence pairs; cannot fit the clock")
    mi = np.array([p[0] for p in pairs])
    li = np.array([p[1] for p in pairs])
    slope, icpt = _line_fit(log_t[li], meg_t[mi])
    for _ in range(3):
        keep = np.abs(meg_t[mi] - (slope * log_t[li] + icpt)) < tol
        if keep.sum() < 3:
            # Coarse fit failed (sequence pairs mostly wrong). Use the median
            # offset of the pairs with slope 1, then try again.
            slope, icpt = 1.0, float(np.median(meg_t[mi] - log_t[li]))
            keep = np.abs(meg_t[mi] - (log_t[li] + icpt)) < max(tol, 1.0)
            if keep.sum() < 3:
                raise ValueError("clock fit failed: no consistent pairs")
        slope, icpt = _line_fit(log_t[li[keep]], meg_t[mi[keep]])

    pred = slope * log_t + icpt
    order = np.argsort(meg_t)
    st = meg_t[order]
    used = np.zeros(len(meg_t), bool)
    match = np.full(len(log_t), -1)
    for i in np.argsort(pred):
        lo, hi = np.searchsorted(st, [pred[i] - tol, pred[i] + tol])
        cand = order[lo:hi]
        cand = cand[(meg_code[cand] == log_code[i]) & ~used[cand]]
        if len(cand):
            j = cand[np.argmin(np.abs(meg_t[cand] - pred[i]))]
            used[j] = True
            match[i] = j
    ok = match >= 0
    if ok.sum() >= 3:
        slope, icpt = _line_fit(log_t[ok], meg_t[match[ok]])
        resid = np.abs(meg_t[match[ok]] - (slope * log_t[ok] + icpt)) * 1000
    else:
        resid = np.array([np.nan])
    return ClockFit(
        slope=slope,
        intercept=icpt,
        match=match,
        n_seq_pairs=len(pairs),
        resid_ms_median=float(np.median(resid)),
        resid_ms_p95=float(np.percentile(resid, 95)),
        resid_ms_max=float(np.max(resid)),
    )


@dataclass
class BlockAlignment:
    """Sample indices (0 = first sample of the recording) for each log event."""

    key_samples: dict[int, np.ndarray]  # trial -> raw sample index per key press
    key_matched: dict[int, np.ndarray]  # trial -> bool per key press
    word_samples: dict[int, np.ndarray]  # trial -> raw sample index per word
    qc: dict[str, Any]


def align_block(
    events: np.ndarray,
    first_samp: int,
    sfreq: float,
    log: BlockLog,
    tol: float = 0.02,
) -> BlockAlignment:
    """Align a block log to the MEG events (``mne.find_events`` output).

    Every key press and word onset gets a sample index at ``sfreq``, counted
    from the first sample of the recording (so ``raw.times[idx]`` is its
    time). A matched event uses the MEG trigger sample. An unmatched event
    uses the fitted line (error below 1 ms in practice).
    """
    events = np.asarray(events)
    meg_t_all = (events[:, 0] - first_samp) / sfreq
    meg_code_all = events[:, 2].astype(int)
    n_ramp = drop_start_ramp(meg_t_all, meg_code_all)
    meg_t, meg_code = meg_t_all[n_ramp:], meg_code_all[n_ramp:]
    log_t, log_code, refs = log.events()
    fit = fit_clock(meg_t, meg_code, log_t, log_code, tol=tol)
    times = np.where(fit.match >= 0, meg_t[np.maximum(fit.match, 0)], fit.predict(log_t))
    samples = np.round(times * sfreq).astype(np.int64)

    key_s = {tr.idx: np.zeros(len(tr.keys), np.int64) for tr in log.trials}
    key_m = {tr.idx: np.zeros(len(tr.keys), bool) for tr in log.trials}
    word_s = {tr.idx: np.zeros(len(tr.words), np.int64) for tr in log.trials}
    n = Counter()
    n_ok = Counter()
    for (kind, trial, j), s, m in zip(refs, samples, fit.match):
        n[kind] += 1
        n_ok[kind] += int(m >= 0)
        if kind == "key":
            key_s[trial][j] = s
            key_m[trial][j] = m >= 0
        elif kind == "word":
            word_s[trial][j] = s
    used = np.zeros(len(meg_t), bool)
    used[fit.match[fit.match >= 0]] = True
    qc = {
        "n_ramp_dropped": int(n_ramp),
        "n_meg_events": int(len(meg_t)),
        "n_log_events": int(len(log_t)),
        "n_seq_pairs": int(fit.n_seq_pairs),
        "n_matched": int((fit.match >= 0).sum()),
        "matched_fraction": float((fit.match >= 0).mean()) if len(log_t) else 0.0,
        "key_matched_fraction": float(n_ok["key"] / n["key"]) if n["key"] else 0.0,
        "word_matched_fraction": float(n_ok["word"] / n["word"]) if n["word"] else 0.0,
        "n_keys": int(n["key"]),
        "n_words": int(n["word"]),
        "slope": float(fit.slope),
        "drift_ms_per_1000s": float((fit.slope - 1) * 1e6),
        "offset_s": float(fit.intercept + (fit.slope - 1) * (log_t[0] if len(log_t) else 0.0)),
        "resid_ms_median": fit.resid_ms_median,
        "resid_ms_p95": fit.resid_ms_p95,
        "resid_ms_max": fit.resid_ms_max,
        "n_unmatched_meg": int((~used).sum()),
        "tol_ms": tol * 1000,
    }
    return BlockAlignment(key_samples=key_s, key_matched=key_m, word_samples=word_s, qc=qc)


# ---------------------------------------------------------------------------
# 4. Text
# ---------------------------------------------------------------------------

BACKSPACE = "<bs>"
RETURN = "<ret>"
OTHER = "<?>"


def key_char(cooked: int, keycode: int) -> str:
    """Return the character of one key press in the vocabulary set.

    - ``"a"``-``"z"`` or ``" "`` for text keys (case and accents folded,
      so ``"Ñ"`` gives ``"n"``),
    - ``"<bs>"`` for backspace, ``"<ret>"`` for return,
    - ``"<?>"`` for all other keys (dead accent keys, punctuation, ...).
    """
    if keycode == VK_BACKSPACE or cooked == 8:
        return BACKSPACE
    if keycode == VK_RETURN or cooked == 13:
        return RETURN
    if cooked == 32 or (cooked <= 0 and keycode == 32):
        return " "
    if cooked > 0:
        try:
            ch = chr(cooked)
        except (ValueError, OverflowError):
            return OTHER
        folded = normalize_text(ch, unknown="drop")
        if len(folded) == 1:
            return folded
    return OTHER


def typed_text_from_keys(chars: Sequence[str]) -> tuple[str, list[int | None]]:
    """Apply backspaces and normalise. Return (typed_text, position per key).

    ``position[i]`` is the index in ``typed_text`` of the character that key
    ``i`` made, or None (backspace, return, other key, an erased key, or a
    space that normalisation removed). ``typed_text`` always equals
    ``normalize_text(typed_text)``.
    """
    alive: list[int] = []  # indices of keys whose character survives
    for i, c in enumerate(chars):
        if c == BACKSPACE:
            if alive:
                alive.pop()
        elif len(c) == 1:
            alive.append(i)
    out: list[str] = []
    pos: list[int | None] = [None] * len(chars)
    for i in alive:
        c = chars[i]
        if c == " " and (not out or out[-1] == " "):
            continue  # leading or repeated space
        pos[i] = len(out)
        out.append(c)
    if out and out[-1] == " ":
        last = len(out) - 1
        out.pop()
        pos = [None if p == last else p for p in pos]
    return "".join(out), pos


def align_chars(typed: str, target: str) -> list[int | None]:
    """Align ``typed`` to ``target`` with difflib.

    Return, for each typed character, the index of its target character, or
    None for an insertion. Equal runs map one to one. A replaced run maps
    position by position; extra typed characters in the run are insertions.
    """
    out: list[int | None] = [None] * len(typed)
    sm = difflib.SequenceMatcher(None, typed, target, autojunk=False)
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag in ("equal", "replace"):
            for k in range(min(i2 - i1, j2 - j1)):
                out[i1 + k] = j1 + k
    return out


@dataclass
class TrialText:
    target_text: str
    typed_text: str
    key_chars: list[str]
    key_target_chars: list[str | None]
    key_target_idx: list[int | None]


def trial_text(sentence: str, chars: Sequence[str]) -> TrialText:
    """Build target text, typed text and the per-key target characters."""
    target = normalize_text(sentence)
    typed, pos = typed_text_from_keys(chars)
    tmap = align_chars(typed, target)
    idx = [tmap[p] if p is not None else None for p in pos]
    return TrialText(
        target_text=target,
        typed_text=typed,
        key_chars=list(chars),
        key_target_chars=[target[j] if j is not None else None for j in idx],
        key_target_idx=idx,
    )

