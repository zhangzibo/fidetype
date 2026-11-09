"""Brain-to-text decoders that emit NeuralTextStreams.

- :mod:`fidetype.decoders.dataset`: torch dataset over the MEG cache.
- :mod:`fidetype.decoders.conv_ctc`: the ConvCTC model (conv + Conformer + CTC).
- :mod:`fidetype.decoders.train`: training CLI (checkpoints, resume, early stop).
- :mod:`fidetype.decoders.infer`: checkpoint to NeuralTextStreams, plus CER/WER.
- :mod:`fidetype.decoders.synthetic`: synthetic cache for tests.
- :mod:`fidetype.decoders.keystroke`: synchronous keystroke decoder (oracle key
  timing, per-subject logistic regression), CTC-form streams. numpy only,
  except the optional shared MLP.

Only ``synthetic`` and ``keystroke`` work without torch. This file does not import torch.
"""
