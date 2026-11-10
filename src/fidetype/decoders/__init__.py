"""Brain-to-text decoders that emit NeuralTextStreams.

- :mod:`fidetype.decoders.dataset`: torch dataset over the MEG cache.
- :mod:`fidetype.decoders.conv_ctc`: the ConvCTC model (conv + Conformer + CTC).
- :mod:`fidetype.decoders.train`: training CLI (checkpoints, resume, early stop).
- :mod:`fidetype.decoders.infer`: checkpoint to NeuralTextStreams, plus CER/WER.
- :mod:`fidetype.decoders.synthetic`: synthetic cache for tests.
- :mod:`fidetype.decoders.keystroke`: synchronous keystroke decoder (oracle key
  timing, per-subject logistic regression), CTC-form streams. numpy only,
  except the optional shared MLP.
- :mod:`fidetype.decoders.sentence_context`: sentence-context keystroke decoder
  (per-key conv encoder + Transformer over the keys of a sentence; M1-15), with
  :mod:`~fidetype.decoders.train_sentence` and :mod:`~fidetype.decoders.infer_sentence`.

Only ``synthetic`` and ``keystroke`` work without torch. This file does not import torch.
"""
