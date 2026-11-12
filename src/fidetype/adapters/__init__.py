"""Adapters: convert the output of third-party decoders into NeuralTextStream.

Each adapter is our own code (Apache-2.0). It reads a public dataset file
and emits streams that follow ``spec/neuraltextstream-v0.1.md``.

- :mod:`fidetype.adapters.b2t25`: Brain-to-Text '25 (Card et al. 2024,
  intracortical attempted speech, participant T15). Phoneme CTC logits.
- :mod:`fidetype.adapters.toronto_semg`: Toronto sEMG typing dataset
  (Achituve et al. 2025, forearm sEMG, 19 participants, CC BY 4.0). Own
  Intan RHD reader, keylog alignment, key-press streams
  (``vocab_type="key"``) and their CTC character form.
"""
