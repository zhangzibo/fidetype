"""Adapters: convert the output of third-party decoders into NeuralTextStream.

Each adapter is our own code (Apache-2.0). It reads a public dataset file
and emits streams that follow ``spec/neuraltextstream-v0.1.md``.

- :mod:`fidetype.adapters.b2t25`: Brain-to-Text '25 (Card et al. 2024,
  intracortical attempted speech, participant T15). Phoneme CTC logits.
- :mod:`fidetype.adapters.toronto_semg`: Toronto sEMG typing dataset
  (Achituve et al. 2025, forearm sEMG, 19 participants, CC BY 4.0). Own
  Intan RHD reader, keylog alignment, key-press streams
  (``vocab_type="key"``) and their CTC character form.
- :mod:`fidetype.adapters.willett_handwriting`: Willett et al. 2021
  handwriting BCI (intracortical, CC0). The real-time RNN character
  output of the closed-loop sentences (one frame per emitted character)
  and its CTC form. Reads ``sentences.mat`` with scipy (``[data]``).
- :mod:`fidetype.adapters.kt_semg`: KT-sEMG (Nokia, forearm sEMG during
  natural typing, CC BY 4.0). CSV and key-log readers, UTC-offset
  inference, key-press streams (32 W3C key codes) and a small LDA
  reference decoder.
- :mod:`fidetype.adapters.lsl`: Lab Streaming Layer, live. LSL inlets ->
  NTS events -> the streaming trust layer; NTS files -> LSL outlets.
  Needs the optional ``pylsl`` (extra ``[lsl]``) only for the network.
- :mod:`fidetype.adapters.ctc_logits`: generic. The ``(T, V)`` CTC
  scores of any decoder (logits, probabilities or log-probabilities;
  batches with lengths; JSON / ``vocab.json`` / ``tokens.txt``
  vocabularies) -> a validated frame stream. CLI for ``.npy`` / ``.npz``.
- :mod:`fidetype.adapters.text_nbest`: generic. The text output of any
  decoder (CSV ``id,text`` or JSON Lines n-best lists) -> a
  hypothesis-only stream (``vocab = []``, spec HDR-12, 4.7).
"""
