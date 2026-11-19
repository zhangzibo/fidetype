"""Brain-to-text decoders that emit NeuralTextStreams.

- :mod:`fidetype.decoders.dataset`: torch dataset over the MEG cache.
- :mod:`fidetype.decoders.conv_ctc`: the ConvCTC model (conv + Conformer + CTC).
- :mod:`fidetype.decoders.train`: training CLI (checkpoints, resume, early stop).
- :mod:`fidetype.decoders.infer`: checkpoint to NeuralTextStreams, plus CER/WER.
- :mod:`fidetype.decoders.restamp_meg`: re-write old cached `infer.py` stream headers
  to the current adapter meta (no torch, log_probs unchanged).
- :mod:`fidetype.decoders.synthetic`: synthetic cache for tests.
- :mod:`fidetype.decoders.keystroke`: synchronous keystroke decoder (oracle key
  timing, per-subject logistic regression), CTC-form streams. numpy only,
  except the optional shared MLP.
- :mod:`fidetype.decoders.sentence_context`: sentence-context keystroke decoder
  (per-key conv encoder + Transformer over the keys of a sentence; M1-15), with
  :mod:`~fidetype.decoders.train_sentence` and :mod:`~fidetype.decoders.infer_sentence`.

Only ``synthetic`` and ``keystroke`` work without torch. This file does not import torch.

Pretrained decoders (P14-01): :func:`load` (same as :func:`fidetype.pretrained.load`) and
:func:`list_models`, for example ``fidetype.decoders.load("t15-m4-13").decode(path)``.
"""

from typing import Any


def load(name: str, **kwargs: Any) -> Any:
    """Load a pretrained decoder by name: see :func:`fidetype.pretrained.load`."""
    from fidetype.pretrained import load as _load

    return _load(name, **kwargs)


def list_models(status: str | None = None) -> list:
    """The manifests of the pretrained decoders: see :func:`fidetype.pretrained.list_models`."""
    from fidetype.pretrained import list_models as _list

    return _list(status)
