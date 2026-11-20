"""Per-language configuration (P14-34, gap 106).

Every Fidetype result so far is English. The English rules (the 28-symbol
character set, accent folding, words = runs between spaces, the typing
rates of the ``aac-gaze-v1`` user model) are spread over the code. This
module puts them in one object per language, :class:`Language`, and a
registry of languages keyed by BCP 47 tag.

- ``en`` (the default) **calls** the existing objects
  (:data:`fidetype.streams.vocab.VOCAB`,
  :func:`fidetype.streams.vocab.normalize_text`, ``str.split``). It does
  not copy them, so English outputs stay bit-identical.
- ``es`` (Spanish, provisional) keeps ``ñ á é í ó ú ü ¿ ¡``.
- ``zh`` (Mandarin, stub) has no word segmentation. Words per minute is
  **not defined** for it: :meth:`Language.words` raises
  :class:`WordsNotDefinedError` (follow-up P14-39).

The audit of all English assumptions is ``docs/language-support.md``.

Example::

    from fidetype import lang
    es = lang.get("es-ES")
    es.normalize("¿Qué año es?")        # "¿qué año es" (the "?" is not in the set)
    lang.wpm_counts(["hola mundo"], "es")  # {'defined': True, 'n_words': [2], 'n_chars': [10], ...}
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Literal, Mapping, Sequence

__all__ = [
    "DEFAULT_TAG", "BCP47_RE", "Language", "WordsNotDefinedError", "available", "get", "is_bcp47", "register",
    "check_tag", "describe", "resolve", "wpm_counts",
]

#: The default language. Code that has no language setting behaves as ``en``.
DEFAULT_TAG = "en"

#: The BCP 47 syntax check of the NTS validators (spec meta ``language``; same pattern as the SDKs).
BCP47_RE = re.compile(r"^[A-Za-z]{2,8}(-[A-Za-z0-9]{1,8})*$")

BLANK_TOKEN = "<blank>"

Segmentation = Literal["spaces", "none"]
Unknown = Literal["space", "drop"]


class WordsNotDefinedError(ValueError):
    """Words (and so words per minute) are not defined for this language."""


def is_bcp47(tag: Any) -> bool:
    """True if ``tag`` is a string with BCP 47 syntax (the NTS check; not a registry check)."""
    return isinstance(tag, str) and bool(BCP47_RE.match(tag))


@dataclass(frozen=True)
class Language:
    """The language-dependent settings of the pipeline.

    ``letters`` are the vocabulary symbols other than the blank and the
    space, in id order; ``None`` means the language has no closed character
    set here (no CTC vocabulary). ``normalizer`` maps any text to the
    character set. ``word_segmentation`` is ``"spaces"`` (a word is a run of
    characters between white space) or ``"none"`` (no word boundaries in
    the text). The two rates are the ``aac-gaze-v1`` user-model rates used
    by safe WPM (correction time and the no-BCI gaze reference).
    """

    tag: str
    name: str
    script: str
    letters: str | None
    normalizer: Callable[[str, str], str] = field(repr=False, compare=False)
    word_segmentation: Segmentation = "spaces"
    vocab_id: str | None = None
    correction_chars_per_min: float | None = None
    gaze_chars_per_min: float | None = None
    rates_source: str = ""
    status: Literal["reference", "provisional", "stub"] = "provisional"
    words_not_defined_reason: str | None = None
    vocab_override: tuple[str, ...] | None = field(default=None, repr=False, compare=False)

    def __post_init__(self) -> None:
        if not is_bcp47(self.tag):
            raise ValueError(f"tag {self.tag!r} is not a BCP 47 tag")
        if self.word_segmentation not in ("spaces", "none"):
            raise ValueError("word_segmentation must be 'spaces' or 'none'")
        if self.word_segmentation == "none" and not self.words_not_defined_reason:
            raise ValueError("a language without word segmentation needs words_not_defined_reason")
        if self.letters is not None and (len(set(self.letters)) != len(self.letters) or " " in self.letters):
            raise ValueError("letters must be unique and must not hold the space")

    # --- characters ---------------------------------------------------

    @property
    def vocab(self) -> tuple[str, ...]:
        """The CTC vocabulary: blank (id 0), the letters, the space. Raise if the language has no character set."""
        if self.vocab_override is not None:
            return self.vocab_override
        if self.letters is None:
            raise NotImplementedError(f"language {self.tag!r} has no closed character set (status {self.status})")
        return (BLANK_TOKEN, *self.letters, " ")

    @property
    def charset(self) -> frozenset[str]:
        """The characters of normalised text (the letters and the space)."""
        return frozenset(t for t in self.vocab[1:])

    def normalize(self, text: str, unknown: Unknown = "space") -> str:
        """Return ``text`` in the character set of the language (single spaces, no edge spaces)."""
        if unknown not in ("space", "drop"):
            raise ValueError(f"unknown must be 'space' or 'drop', not {unknown!r}")
        return self.normalizer(text, unknown)

    def encode(self, text: str, unknown: Unknown = "space") -> list[int]:
        """Normalise ``text`` and return its vocabulary ids (no blanks)."""
        ids = {c: i for i, c in enumerate(self.vocab) if i != 0}
        return [ids[c] for c in self.normalize(text, unknown)]

    def decode(self, ids: Iterable[int]) -> str:
        """The text of vocabulary ids; blank ids (0) are skipped; repeats are not collapsed."""
        v = self.vocab
        out = []
        for i in ids:
            i = int(i)
            if not 0 <= i < len(v):
                raise ValueError(f"token id {i} is out of range 0..{len(v) - 1}")
            if i:
                out.append(v[i])
        return "".join(out)

    # --- words --------------------------------------------------------

    @property
    def wpm_defined(self) -> bool:
        """True if words (and so words per minute) are defined for this language."""
        return self.word_segmentation == "spaces"

    def words(self, text: str) -> list[str]:
        """The words of ``text``. Raise :class:`WordsNotDefinedError` without word segmentation."""
        if not self.wpm_defined:
            raise WordsNotDefinedError(f"{self.tag}: {self.words_not_defined_reason}")
        return str(text).split()

    def count_words(self, text: str) -> int:
        """``len(words(text))``: the ``words(y)`` of safe WPM v0.1."""
        return len(self.words(text))

    @staticmethod
    def count_chars(text: str) -> int:
        """Characters of ``text`` after joining white space (``len(" ".join(text.split()))``)."""
        return len(" ".join(str(text).split()))

    def to_dict(self) -> dict[str, Any]:
        """A JSON summary (for a score card or a report)."""
        return {"tag": self.tag, "name": self.name, "script": self.script, "status": self.status,
                "word_segmentation": self.word_segmentation, "vocab_id": self.vocab_id,
                "vocab_size": None if self.letters is None and self.vocab_override is None else len(self.vocab),
                "correction_chars_per_min": self.correction_chars_per_min,
                "gaze_chars_per_min": self.gaze_chars_per_min, "rates_source": self.rates_source,
                "words_not_defined_reason": self.words_not_defined_reason}


# ---------------------------------------------------------------------------
# Normalisers


def _en_normalize(text: str, unknown: str) -> str:
    from fidetype.streams.vocab import normalize_text

    return normalize_text(text, unknown)  # type: ignore[arg-type]


def _make_latin_normalizer(letters: str) -> Callable[[str, str], str]:
    """Lower case; keep ``letters`` (NFC); fold other accents to ``a``-``z``; other characters -> space or drop."""
    keep = frozenset(letters)

    def norm(text: str, unknown: str) -> str:
        out: list[str] = []
        for ch in unicodedata.normalize("NFC", str(text).lower()):
            if ch in keep or ch == " ":
                out.append(ch)
                continue
            if unicodedata.combining(ch):
                continue  # a mark with no precomposed letter (for example "b" + U+0303): drop the mark
            base = [c for c in unicodedata.normalize("NFKD", ch) if not unicodedata.combining(c)]
            if base and all(c in keep for c in base):
                out.extend(base)  # for example "à" -> "a", "ç" -> "c"
            elif ch.isspace() or unknown == "space":
                out.append(" ")
        return " ".join("".join(out).split())

    return norm


def _nfkc_normalize(text: str, unknown: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", str(text)).split())


# ---------------------------------------------------------------------------
# Registry

_REGISTRY: dict[str, Language] = {}

_RATES_EN = ("152 chars/min: Brain2Qwerty v1 typing rate (correction time 2 * 60 / 152 s per char); "
             "20 chars/min: eye-gaze user LP1 of Cai et al. 2024 (the aac-gaze-v1 no-BCI reference)")

_ZH_REASON = ("Mandarin text has no spaces between words, so splitting at spaces gives about one word per "
              "sentence. Words per minute (and safe WPM v0.1) needs a fixed word segmenter or a "
              "characters-per-minute metric; it is not defined yet (follow-up P14-39).")


def register(language: Language, *, replace: bool = False) -> Language:
    """Add ``language`` to the registry under its lower-case tag."""
    key = language.tag.lower()
    if key in _REGISTRY and not replace:
        raise ValueError(f"language {language.tag!r} is already registered (pass replace=True)")
    _REGISTRY[key] = language
    return language


def available() -> list[str]:
    """The registered tags."""
    return sorted(_REGISTRY)


def get(tag: str | None = None) -> Language:
    """The language of a BCP 47 tag: exact match, else the primary subtag (``en-US`` -> ``en``). None -> ``en``."""
    if tag is None:
        tag = DEFAULT_TAG
    if not is_bcp47(tag):
        raise ValueError(f"{tag!r} is not a BCP 47 language tag")
    key = tag.lower()
    if key in _REGISTRY:
        return _REGISTRY[key]
    primary = key.split("-", 1)[0]
    if primary in _REGISTRY:
        return _REGISTRY[primary]
    raise KeyError(f"no language config for {tag!r}; registered: {', '.join(available())}")


def resolve(x: "str | Language | None") -> Language:
    """A :class:`Language` from a tag, a :class:`Language` or None (``en``)."""
    return x if isinstance(x, Language) else get(x)


def wpm_counts(texts: Sequence[str], language: "str | Language | None" = None, *,
               on_undefined: Literal["raise", "report"] = "raise") -> dict[str, Any]:
    """Word and character counts of reference texts, the ``n_words`` / ``n_chars`` inputs of safe WPM.

    For ``en`` this equals ``load_trials_jsonl`` of
    :mod:`fidetype.benchmark.safe_wpm`: ``t = " ".join(text.split())``,
    ``n_words = len(t.split())``, ``n_chars = len(t)``. For a language
    without word segmentation it raises :class:`WordsNotDefinedError`
    (``on_undefined="raise"``) or returns ``{"defined": False, "reason": ...}``
    with no counts (``"report"``). It never returns a silent number.
    """
    L = resolve(language)
    if not L.wpm_defined:
        if on_undefined == "raise":
            raise WordsNotDefinedError(f"{L.tag}: {L.words_not_defined_reason}")
        if on_undefined != "report":
            raise ValueError("on_undefined must be 'raise' or 'report'")
        return {"defined": False, "language": L.tag, "status": "not-defined", "reason": L.words_not_defined_reason,
                "n_words": None, "n_chars": None}
    nw, nc = [], []
    for t in texts:
        s = " ".join(str(t).split())
        nw.append(L.count_words(s))
        nc.append(len(s))
    return {"defined": True, "language": L.tag, "n_words": nw, "n_chars": nc,
            "correction_chars_per_min": L.correction_chars_per_min, "gaze_chars_per_min": L.gaze_chars_per_min,
            "rates_source": L.rates_source}


def _en_vocab() -> tuple[str, ...]:
    from fidetype.streams.vocab import VOCAB

    return VOCAB


ES_LETTERS = "abcdefghijklmnopqrstuvwxyzáéíóúüñ¿¡"

register(Language(
    tag="en", name="English", script="Latn", letters="abcdefghijklmnopqrstuvwxyz", normalizer=_en_normalize,
    word_segmentation="spaces", vocab_id="char.b2q-28", correction_chars_per_min=152.0, gaze_chars_per_min=20.0,
    rates_source=_RATES_EN, status="reference", vocab_override=_en_vocab(),
))
register(Language(
    tag="es", name="Spanish", script="Latn", letters=ES_LETTERS, normalizer=_make_latin_normalizer(ES_LETTERS),
    word_segmentation="spaces", vocab_id=None, correction_chars_per_min=152.0, gaze_chars_per_min=20.0,
    rates_source="provisional: the en values copied (no Spanish gaze-typing rate yet; P15-30)", status="provisional",
))
register(Language(
    tag="zh", name="Mandarin Chinese", script="Hani", letters=None, normalizer=_nfkc_normalize,
    word_segmentation="none", status="stub", words_not_defined_reason=_ZH_REASON,
))


def check_tag(tag: Any, where: str = "language") -> str:
    """Return ``tag`` if it is BCP 47 and resolves in the registry; else raise ``ValueError``."""
    if not is_bcp47(tag):
        raise ValueError(f"{where}: {tag!r} is not a BCP 47 language tag")
    try:
        get(tag)
    except KeyError as e:
        raise ValueError(f"{where}: {e.args[0]}") from None
    return str(tag)


def describe(languages: Mapping[str, Language] | None = None) -> list[dict[str, Any]]:
    """``to_dict()`` of every registered language (for docs and the CLI)."""
    return [L.to_dict() for _, L in sorted((languages or _REGISTRY).items())]
