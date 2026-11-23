# Glossary

The terms that the Fidetype documentation uses, in alphabetical order, each with a short meaning.

**Status:** Beta ([status levels](#status-levels))

The normative term list of the format is in [spec section 1.4](../spec/nts-1.0-rc4.md#14-terms). This page explains the words in plain language. If the two disagree, the spec is right.

## Status levels

Each documentation page has a status line under its title. It tells you how stable the part is that the page describes. Fidetype uses one ladder for all parts:

| Level | Meaning |
|---|---|
| Development | Work in progress. Names, files and behaviour can change at any time. Do not build on it |
| Alpha | It works for the documented cases. The API can still change without notice. Tell us what breaks |
| Beta | Feature complete for this release. Breaking changes are rare and the changelog records them |
| Release Candidate | Frozen for review. Only fixes from the review change it |
| Stable | Breaking changes only in a new major version, with a deprecation period |
| Deprecated | Still works, but will be removed. The page names the replacement |

"Beta, except ..." means that the named parts have a lower level. Fidetype is research software. **It is not a medical device**, at every level.

## Terms

### ABSTAIN, ASK

Two NTS trust actions. ABSTAIN: use nothing. ASK: ask the user to try again. The drop-in guard reports both as **withhold**.

### Adapter

Code that reads one device or one recording format and gives NTS (or the input of a decoder). See [adapters](adapters.md).

### Alpha, delta

The two numbers (α and δ) of the trust guarantee. α is the largest wrong-commit rate that you accept (default 0.05 = 5 % of all utterances). δ is the probability that the calibration data were unlucky and the bound does not hold (default 0.1). See [trust guarantee](trust-guarantee.md#1-the-guarantee-in-one-sentence).

### B2T '24 (Brain-to-Text '24)

The earlier public benchmark of attempted speech from an intracortical implant (participant T12). File form: `competitionData/.../t12.*.mat`.

### B2T '25 (Brain-to-Text '25)

A public benchmark dataset of attempted speech decoded from an intracortical implant (participant T15). File form: `data_*.hdf5`, one folder per session.

### Calibration

Fitting the thresholds of the trust layer on labelled utterances of one user and one decoder. The result is a frozen trust configuration.

### CER, WER

Character error rate and word error rate: the edit distance between the decoded text and the true text, divided by the length of the true text. 0 is perfect. Lower is better.

### Collector

One service that reads NTS from several sources (receivers), changes or checks it (processors) and writes it to several targets (exporters). It copies the structure of the OpenTelemetry Collector. See [Collector](collector.md).

### Commit, offer, withhold

The three answers of the drop-in trust guard for one utterance. **Commit**: type the text. **Offer**: show a short list; the user picks one or none. **Withhold**: type nothing. In NTS they are the actions `COMMIT`, `OFFER` and `ABSTAIN` / `ASK`.

### `config_id`

The content id of a frozen trust configuration (a hash of the file). Each decision names it, so an auditor can reproduce the decision.

### Conformance kit

Example files (golden vectors) with the expected verdict, and the `nts-conform` tool that checks files and validators against them. See [conformance](conformance.md).

### CTC

Connectionist temporal classification: a way to train a decoder that gives one probability distribution per time step, without a time alignment of the labels.

### Decoder

A model that turns signal features into text, keys or commands. Fidetype ships [pretrained decoders](pretrained-decoders.md) for public datasets.

### EEG, MEG, EMG, sEMG

Ways to record body signals without surgery. EEG: electrical brain activity from the scalp. MEG: magnetic fields of brain activity (a large, shielded machine). EMG: electrical muscle activity. sEMG: surface EMG, from electrodes on the skin (for example a wristband).

### eWPM

Effective words per minute: correct text per minute, with the time for corrections and choices of a simulated user included.

### emg2qwerty

A public dataset from Meta of typing on a keyboard, recorded with sEMG wristbands. Licence CC BY-NC-SA 4.0, so models trained on it are research only.

### FEP

Fidetype Enhancement Proposal. A written proposal for a change to the NTS spec. It goes through Draft, Under review, Accepted, Implemented and Final. See [spec proposals](../spec/README.md#proposals-feps).

### Fluent-wrong

Output that reads like correct, natural text but is not what the person intended, often written by the language model with no support from the signal. The [hallucination benchmark](hallucination-benchmark.md) measures it.

### Golden vector

A small synthetic test file with an expected verdict (accept or reject).

### Guard, TrustGuard

The drop-in trust layer object. `fidetype.trust.calibrate(...)` returns a `TrustGuard`. `guard.decide(...)` gives commit, offer or withhold. See [trust quickstart](trust-quickstart.md).

### Intracortical implant

Small electrode arrays placed in the brain by surgery. The T12, T15 and Willett handwriting datasets come from such implants. Fidetype does not need one: it uses the public recordings.

### KT-sEMG

A public dataset from Nokia of keyboard typing with forearm sEMG (`runN.csv` and a key log). Licence CC BY 4.0.

### LSL

Lab Streaming Layer: a common lab transport for time series, with clock synchronisation. NTS can travel over LSL.

### LTT (Learn then Test)

The statistical method that sets the commit threshold. It tests thresholds from strict to loose on held-out calibration data and stops at the first one that fails. The result has the α / δ guarantee. See [trust guarantee](trust-guarantee.md#2-how-the-guard-gets-the-guarantee).

### Model names

A pretrained decoder name has the form `<dataset or participant>-<variant>`. Examples: `t15-m4-13` (participant T15; `m4-13` is the internal build name of that model version, kept for stable loading), `t12-v2`, `kt-semg-lda`, `emg2qwerty-p11-01`, `willett-hw`. The names are part of the API and do not change.

### NTS (NeuralTextStream)

The open data format for the output of a neural input decoder: probabilities per time step, text hypotheses, intents, control and trust decisions. Bindings: JSON Lines, NPZ, LSL, WebSocket. See [concepts](concepts.md).

### Offer gate

A check before an offer. It shows a list only if the list probably holds the right text. Otherwise the guard withholds.

### Producer, consumer

Software that writes NTS (a decoder, an adapter), and software that reads NTS (an app, a trust layer, a benchmark).

### Profile

A set of event kinds that extends the NTS core: text, intent, control.

### Research only

A model or file that comes from data with a non-commercial licence. Fidetype refuses to load it unless you opt in with `accept_research_only=True`.

### Safe WPM

The headline metric: the words per minute that the system types by itself and exactly right, counted only when the trust layer has a certified limit on the wrong-commit rate. See [safe WPM](safe-wpm.md).

### T12, T15

Codes of two participants of the BrainGate clinical trial. Both have intracortical implants and attempt to speak. Their public recordings are B2T '24 (T12) and B2T '25 (T15).

### Trust configuration

The frozen file with all thresholds of a guard, identified by its `config_id`. It holds its guarantee only for the decoder and the user it was calibrated with.

### Trust decision

The NTS event `trust_decision`: the final action of the trust layer for one utterance.

### Trust layer

The part between the decoder and the user. It decides for each utterance whether to commit, offer or withhold, so that wrong text rarely reaches the user. See [trust quickstart](trust-quickstart.md).

### Utterance

One unit of decoder output that gets one decision: a sentence, a word or a typing burst.

### Willett handwriting (`willett-hw`)

A public dataset of attempted handwriting from an intracortical implant (Willett et al., 2021). `willett-hw` is also the name of our pretrained decoder for it.

### Wrong commit, wrong-commit rate

A wrong commit: the guard commits a text that is not exactly the true text. The rate: wrong commits divided by **all** utterances.
