"""Producer conformance runs for the adapters in this repository.

Each target builds small **synthetic** inputs (fixed seed, no data from
people, no download), runs the adapter and returns its streams together
with the synthetic ground truth. The suite checks every stream, and also
checks that no truth text leaks into the header or ``meta`` (5.3.1).

Targets (``python -m fidetype.conformance check adapter:<name>``):

``spanishbcbl``
    :func:`fidetype.adapters.spanishbcbl_meg.segment_stream` (the stream
    that :mod:`fidetype.decoders.infer` writes for the MEG ConvCTC), in
    offline and causal mode, with a weights hash and a stream id.
``b2t25``
    :func:`fidetype.adapters.b2t25.trial_stream` on synthetic copy-task
    trials (41-class phoneme logits), and its one-character symbol form.
``toronto``
    :func:`fidetype.adapters.toronto_semg.keypress_stream` (``key``
    vocabulary) and :func:`~fidetype.adapters.toronto_semg.to_ctc_char_stream`
    (``char`` CTC form), offline and with a window latency.
``ctc-logits``
    :mod:`fidetype.adapters.ctc_logits` (generic CTC scores): a padded
    ``(T, B, V)`` logits batch with lengths, a probability matrix with
    a Hugging Face style ``{token: id}`` vocabulary, a bounded-lookahead
    stream with a frame temperature, and an offline (non-causal) stream.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Callable

import numpy as np

from fidetype.streams.spec import NeuralTextStream


@dataclass
class ProducedStream:
    name: str
    stream: NeuralTextStream
    truth: list[str] = field(default_factory=list)


def _fake_weights_sha(tag: str) -> str:
    """SHA-256 of a synthetic weights blob (stands in for a real weights file)."""
    return hashlib.sha256(f"synthetic-weights/{tag}".encode()).hexdigest()


def _lsm(x: np.ndarray) -> np.ndarray:
    m = x.max(axis=1, keepdims=True)
    return x - m - np.log(np.exp(x - m).sum(axis=1, keepdims=True))


def produce_spanishbcbl(seed: int = 0) -> list[ProducedStream]:
    from fidetype.adapters import spanishbcbl_meg as A

    rng = np.random.default_rng(seed)
    truth = "el perro come pan"
    out = []
    for mode, la in (("offline", None), ("causal", 2)):
        lp = _lsm(rng.standard_normal((60, 28)) * 2.0).astype(np.float32)
        s = A.segment_stream(
            lp, 0.04, subject="S99", session="ses1", participant="P99", block="block1", trial_idx=3, split="test",
            run_name=f"synthetic-{mode}", checkpoint="best.pt", segment_start_s=12.5, conformer_layers=4,
            lookahead_frames=la, weights_sha256=_fake_weights_sha(mode),
            stream_id=A.opaque_stream_id("synthetic", mode, 3),
        )
        out.append(ProducedStream(f"spanishbcbl-convctc/{mode}", s, [truth]))
    return out


def _synthetic_trials(n: int, seed: int) -> list:
    from fidetype.adapters import b2t25 as B

    rng = np.random.default_rng(seed)
    sentences = ["the cat sat on the mat", "please bring me water", "i need some help now"]
    d: dict[str, list] = {k: [] for k in B.COPYTASK_KEYS}
    for i in range(n):
        T = int(rng.integers(20, 60))
        sent = sentences[i % len(sentences)]
        phon = [p for w in sent.split() for p in (*rng.choice(B.PHONEMES, size=3), "SIL")]
        d["post_implant_day"].append(100 + i)
        d["vocab_size"].append(125000)
        d["cue_sentence"].append(sent)
        d["cue_sentence_phonemes"].append(phon)
        d["decoded_logits"].append((rng.standard_normal((T, len(B.VOCAB))) * 3).astype(np.float32))
        d["decoded_phonemes_raw"].append(phon)
        d["decoded_sentence"].append(sent)
        d["decoded_sentence_phonemes"].append(phon)
        d["speech_duration_s"].append(T * 0.08)
    return B.trials_from_dict(d)


def produce_b2t25(seed: int = 1) -> list[ProducedStream]:
    from fidetype.adapters import b2t25 as B

    out = []
    for tr in _synthetic_trials(3, seed):
        s = B.trial_stream(tr)
        truth = [tr.cue_sentence, tr.decoded_sentence, " ".join(tr.cue_phonemes)]
        out.append(ProducedStream(f"b2t25/trial{tr.index}", s, truth))
        if tr.index == 0:
            out.append(ProducedStream(f"b2t25/trial{tr.index}-symbol", B.to_symbol_stream(s), truth + [tr.truth_symbols]))
    return out


def produce_toronto(seed: int = 2) -> list[ProducedStream]:
    from fidetype.adapters import toronto_semg as T

    rng = np.random.default_rng(seed)
    text = "hello world"
    logits = rng.standard_normal((len(text), len(T.KEY_VOCAB))) * 2.0
    for i, c in enumerate(text):
        logits[i, T.KEY_CHARS.index(c)] += 4.0
    times = T.compose_times(len(text), 0.79)
    out = []
    for mode, lat in (("offline", None), ("window", 0.3)):
        meta = T.stream_meta("P99", "T2", decoder_name="fidetype-emg-convnet-synthetic", personalized=True,
                             composed=True, weights_sha256=_fake_weights_sha(f"emg-{mode}"),
                             stream_id=hashlib.sha256(f"toronto/{mode}".encode()).hexdigest()[:32])
        ks = T.keypress_stream(logits, times, meta, latency=lat)
        out.append(ProducedStream(f"toronto-semg/key-{mode}", ks, [text]))
        out.append(ProducedStream(f"toronto-semg/ctc-char-{mode}", T.to_ctc_char_stream(ks), [text]))
    return out


def produce_ctc_logits(seed: int = 3) -> list[ProducedStream]:
    from fidetype.adapters import ctc_logits as C

    rng = np.random.default_rng(seed)
    letters = list("abcdefghijklmnopqrstuvwxyz")
    out = []
    vocab = C.vocab_from_list(["<blank>", " ", *letters], 0)
    dec = C.DecoderInfo(modality="eeg", name="synthetic-ctc", version="1", weights_sha256=_fake_weights_sha("ctc"))
    batch = rng.standard_normal((40, 2, len(vocab))) * 2.0
    for i, s in enumerate(C.from_batch(batch, vocab, dec, lengths=[40, 25], layout="TBV", frame_period=0.04,
                                       latency=0.0)):
        out.append(ProducedStream(f"ctc-logits/batch-item{i}", s, ["hello world"]))
    hf = C.vocab_from_json_map({"<pad>": 0, "|": 1, **{c: i + 2 for i, c in enumerate(letters)}})
    probs = np.exp(_lsm(rng.standard_normal((30, len(hf))) * 2.0))
    dec_hf = C.DecoderInfo(modality="emg", name="synthetic-hf-ctc", version="2", weights_sha256=_fake_weights_sha("hf"))
    out.append(ProducedStream("ctc-logits/hf-probs", C.from_array(probs, hf, dec_hf, frame_period=0.02, latency=0.0,
                                                                   input_kind="probs"), ["hello world"]))
    dec_la = C.DecoderInfo(modality="meg", name="synthetic-lookahead", version="3",
                           weights_sha256=_fake_weights_sha("lookahead"), calibration_id="temp-fit-synthetic")
    out.append(ProducedStream("ctc-logits/lookahead-temperature",
                              C.from_array(rng.standard_normal((20, len(vocab))), vocab, dec_la, frame_period=0.05,
                                           latency=0.5, temperature=1.5), ["hello world"]))
    dec_off = C.DecoderInfo(modality="meg", name="synthetic-bidir", version="4", causal=False,
                            weights_sha256=_fake_weights_sha("bidir"))
    out.append(ProducedStream("ctc-logits/offline",
                              C.from_array(rng.standard_normal((20, len(vocab))), vocab, dec_off, frame_period=0.05),
                              ["hello world"]))
    return out


TARGETS: dict[str, Callable[[], list[ProducedStream]]] = {
    "spanishbcbl": produce_spanishbcbl,
    "b2t25": produce_b2t25,
    "toronto": produce_toronto,
    "ctc-logits": produce_ctc_logits,
}
