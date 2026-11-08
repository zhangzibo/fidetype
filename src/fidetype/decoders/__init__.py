"""Brain-to-text decoders that emit NeuralTextStreams.

- :mod:`fidetype.decoders.dataset`: torch dataset over the MEG cache.
- :mod:`fidetype.decoders.conv_ctc`: the ConvCTC model (conv + Conformer + CTC).
- :mod:`fidetype.decoders.train`: training CLI (checkpoints, resume, early stop).
- :mod:`fidetype.decoders.infer`: checkpoint to NeuralTextStreams, plus CER/WER.
- :mod:`fidetype.decoders.synthetic`: synthetic cache for tests.

Only ``synthetic`` works without torch. This file does not import torch.
"""
