"""Phoneme log-probs -> word n-best: the text decoder of the T15 trust guard (P14-01). Our own code (Apache-2.0).

The committed T15 guard (``guards/t15-m4-13.guard.json``) was calibrated with this decoder
(P14-05: ``experiments/2026-11-16-p14-05-safe-wpm``, route of ``experiments/2026-11-10-b2t25-trust``).
A different text decoder voids the guarantee, so :meth:`PretrainedDecoder.guard` builds exactly
this one from the settings in the manifest:

1. CTC prefix beam search over the phoneme stream (one character per phoneme, space = word end);
2. :class:`fidetype.lm.phoneme_words.PhonemeWordDecoder`: lexicon words within a small phoneme edit
   distance, word unigram prior, character n-gram LM rescoring;
3. the word n-best list as dicts (``text``, ``score``, ``logp_acoustic``, ``logp_lm``,
   ``char_confidences``), the user ``decode_fn`` form of :func:`fidetype.trust.calibrate`.

Text resources (not weights; each has its own licence, listed in the manifest): the CMU Pronouncing
Dictionary (BSD-2-Clause style), a 6-gram character LM and word counts built from Tatoeba English
sentences (CC BY 2.0 FR). They load from the model folder or ``<cache>/text/``.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections import Counter
from os import PathLike
from pathlib import Path
from typing import Any, Callable, Mapping

import numpy as np

__all__ = ["DECODER_ID", "make_phoneme_words_decode_fn"]

DECODER_ID = "phoneme-words-v1"


def make_phoneme_words_decode_fn(files: Mapping[str, str | PathLike[str]], settings: Mapping[str, Any]
                                 ) -> Callable[[np.ndarray], list[dict[str, Any]]]:
    """The decode function: (T, 41) phoneme log-probs -> word n-best (dicts).

    ``files``: paths of ``lexicon``, ``char_lm`` and ``word_counts``. ``settings``: ``phoneme_beam``
    (keyword arguments of the CTC beam), ``word_decoder`` (keyword arguments of
    :class:`PhonemeWordDecoder`), ``fallback_min_count``.
    """
    from fidetype.adapters import b2t25 as B
    from fidetype.lm import CharNgramLM, ctc_prefix_beam_search
    from fidetype.lm.phoneme_words import PhonemeWordDecoder, PronLexicon, unigram_logprobs
    from fidetype.streams.spec import NeuralTextStream
    from fidetype.trust.types import from_lm_hypotheses

    keep = lambda w: re.fullmatch(r"[a-z']+", w) is not None  # noqa: E731
    lex = PronLexicon.from_cmudict(str(files["lexicon"]), B.phonemes_to_symbols, keep=keep)
    wc = Counter(json.loads(Path(files["word_counts"]).read_text(encoding="utf-8")))
    uni = unigram_logprobs(wc, lex.words)
    lex.set_fallback_words(w for w in lex.words if wc.get(w, 0) >= int(settings.get("fallback_min_count", 5)))
    lm = CharNgramLM.load(str(files["char_lm"]))
    beam_kw = dict(settings["phoneme_beam"])
    wdec = PhonemeWordDecoder(lex, uni, sentence_lm=lm.score_sentence, **dict(settings["word_decoder"]))
    cache: dict[str, list[dict[str, Any]]] = {}

    def phoneme_words_decoder(log_probs: np.ndarray) -> list[dict[str, Any]]:
        lp = np.ascontiguousarray(log_probs, dtype=np.float32)
        k = hashlib.sha1(lp.tobytes()).hexdigest()
        hit = cache.get(k)
        if hit is not None:
            return hit
        st = NeuralTextStream(log_probs=lp, frame_times=np.arange(lp.shape[0]) * 0.08, vocab=list(B.SYMBOL_VOCAB),
                              blank_id=0, vocab_type="phoneme")
        nb = from_lm_hypotheses(wdec.decode(ctc_prefix_beam_search(st, None, **beam_kw)), st.meta,
                                confidence_variant=None)
        out = []
        for c in nb.candidates:
            d: dict[str, Any] = {"text": c.text, "score": float(c.score)}
            for f in ("logp_acoustic", "logp_lm"):
                v = float(getattr(c, f))
                if math.isfinite(v) and v <= 0:
                    d[f] = v
            if c.char_confidences:
                d["char_confidences"] = [min(1.0, max(0.0, float(x))) for x in c.char_confidences]
            out.append(d)
        cache[k] = out
        return out

    return phoneme_words_decoder
