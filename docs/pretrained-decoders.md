# Pretrained decoders

Load a pretrained decoder for a public dataset in one line, decode a data file into NTS in one line, and add the calibrated trust guard in a third line.

**Status:** Development: the weights are not hosted yet ([status levels](glossary.md#status-levels))

A **decoder** turns recorded signal features into text. [NTS](glossary.md#nts-neuraltextstream) (NeuralTextStream) is the output format. The **trust guard** decides for each output to [commit, offer or withhold](glossary.md#commit-offer-withhold) it.

```python
import fidetype.pretrained as ftp                 # fidetype.decoders.load is the same function

m = ftp.load("t15-m4-13")                         # checks the SHA-256 and the size of the weights
path = "t15.2023.08.13/data_val.hdf5"
print(m.n_items(path))                            # number of trials, no decoding
streams = m.decode_file(path)                     # a list: one NTS stream per trial
r = m.decide(streams[0])                          # the committed trust guard of this model
print(r.action, r.text or r.choices[:1])          # commit / offer / withhold
```

No weights yet? `ftp.toy_model(runtime)` gives a tiny random model with the runtime of a real model (`gru-ctc` by default, the runtime of `t15-m4-13`; see [toy model](#try-the-api-without-weights-the-toy-model)).

Code: [`src/fidetype/pretrained/`](../src/fidetype/pretrained/__init__.py). The weights are **not** in the package and **not** in the git repository. Hosting them is a separate maintainer step ([publishing checklist](publishing-checklist.md), section J).

## Models

`fidetype decoders list` prints this table from the packaged manifests. The datasets: [B2T '25](glossary.md#b2t-25-brain-to-text-25) and [B2T '24](glossary.md#b2t-24-brain-to-text-24) (implant speech of the participants [T15 and T12](glossary.md#t12-t15)), [KT-sEMG](glossary.md#kt-semg), [emg2qwerty](glossary.md#emg2qwerty) and [Willett handwriting](glossary.md#willett-handwriting-willett-hw). The [glossary](glossary.md#model-names) explains the model names. [CER](glossary.md#cer-wer) is the character error rate.

| Name | Task | Input file | Training data (licence) | `data.research_only` | Status |
|---|---|---|---|---|---|
| [`t15-m4-13`](glossary.md#model-names) | Implant attempted speech, phonemes (CTC), causal GRU | Brain-to-Text '25 `data_*.hdf5` (one session folder) | T15, Card et al. 2024 (CC0 1.0) | false | available; trust config packaged |
| `t12-v2` | Implant attempted speech, phonemes (CTC), causal GRU | Brain-to-Text '24 `competitionData/test/t12.*.mat` | T12, Willett et al. 2023 (CC0 1.0) | false | available; no packaged trust config yet |
| `kt-semg-lda` | Forearm sEMG typing, one key per press (LDA) | KT-sEMG `runN.csv` + key log | KT-sEMG, Nokia (CC BY 4.0, attribution) | false | available; guard is a release file |
| `emg2qwerty-p11-01` | Wrist sEMG typing, characters (CTC), causal ring-TCN, generic model | emg2qwerty session `*.hdf5` | emg2qwerty, Meta (CC BY-NC-SA 4.0) | **true** | available, **research only** |
| `willett-hw` | Implant handwriting, characters (CTC), causal TCN, our own. **Weak**: greedy test CER 0.305, no LM | Willett handwriting 2021, one session folder `Datasets/t5.*` (`sentences.mat`) | T5, Willett et al. 2021 (CC0 1.0) | false | available; weights licence CC0 1.0 (not hosted yet); guard is a release file, **offer only** (never commits) |
| `toronto-semg-cnn` | Forearm sEMG typing, key-press CNN | Toronto sEMG | CC BY 4.0 | false | planned (no runtime yet) |

Each model card (`fidetype decoders info <name>`) gives the input spec, the architecture, the release files with SHA-256 and size, the licence of the data and the proposed licence of the weights, the training run, the metrics and the limits.

All runtimes are NumPy only. They need no PyTorch and no GPU. The readers need `h5py` (`pip install fidetype[hdf5]`; the old extra name `emg2qwerty` also works) for HDF5 files and `scipy` (`pip install fidetype[data]`) for the T12 and Willett `.mat` files.

## Where the weights come from

`load()` looks for the release files in this order:

1. `weights=` (a folder with the files, or the path of the weights file);
2. `cache_dir=`, or the environment variable `FIDETYPE_PRETRAINED_DIR`;
3. `~/.cache/fidetype/pretrained` (or `$FIDETYPE_CACHE/pretrained`).

In a cache folder, the files of model `<name>` are in `<cache>/<name>/`. The text files of the T15 word decoder can also be in `<cache>/text/`. `fidetype decoders path` shows the exact paths and which files are missing. `fidetype decoders verify <name>` checks the SHA-256 and the size of each file.

Every file must match its manifest. A wrong size or hash raises `WeightsMismatch`. A missing file raises `WeightsNotFound`. The message names the folders that `load()` searched.

`download=True` fetches a missing file from the `url` of its manifest entry, then checks it before it moves into the cache. **No model has a URL yet.** On the project machine, `tools/pretrained/export_weights.py` makes the release files from our training outputs.

## The licence gate

The manifest of each model carries the keys `data.licence` and `data.research_only`. A model with `data.research_only = true` (today: `emg2qwerty-p11-01`) refuses to load or download:

```python
ftp.load("emg2qwerty-p11-01")                              # ResearchOnlyRefused
m = ftp.load("emg2qwerty-p11-01", accept_research_only=True)   # explicit opt-in
```

On the command line the opt-in is `--accept-research-only`. Use it only for non-commercial research, and only if you accept the licence. The weights keep the share-alike terms of the data. Every stream from such a model carries `data.research_only = true`, so the Collector option `refuse_research_only = true` drops it downstream ([provenance and privacy](provenance-and-privacy.md)). A manifest cannot be looser than its data licence: the parser rejects an NC licence with `data.research_only = false`.

## What `decode()` and `decode_file()` return

| Call | Result |
|---|---|
| `m.decode_file(path)` | Always a list of streams, one per trial (T15, T12), text prompt (emg2qwerty), typing burst (KT-sEMG) or sentence (Willett; a session folder or its `sentences.mat`; `blocks=` keeps some blocks) |
| `m.decode(array)` (= `m.decode_array(array)`) | One stream. T15 / T12: `(T, 512)` features of one trial plus `session=` (the session name, see `m.sessions`). emg2qwerty: `(n, 32)` raw EMG at 2 kHz. KT-sEMG: `(n, 32)` EMG plus `times=` (key onsets in seconds). Willett: `(T, 192)` threshold crossings in 10 ms bins from the go cue, plus `session=` (one of the 10 `t5.*` sessions) |
| `m.decode(path)` | **Deprecated**. It still returns the list of `decode_file(path)`, with a `DeprecationWarning`. Use `decode_file()` for files |

`m.n_items(path)` counts the items of a file without decoding (`blocks=` for Willett). For T15 it reads only the HDF5 group names. For KT-sEMG it reads only `runN_keys.txt` and `runN_ts.txt`; it does not open `runN.csv`, and the CSV may be absent. The KT-sEMG count is the `decode_file` count if the typing starts within one hour of the EMG start and no key press falls in the last 0.15 s of the recording or after it. Both are true on all 29 KT-sEMG runs (run28: 22 items in 2 ms, against 26.5 s to read the CSV). `decode_file(path, indices=[...])` (T15, T12) takes positions `0 .. n_items(path) - 1` (negative positions count from the end). A position outside this range raises `IndexError` with the item count of the file.

`decode_file(path, with_items=True)` returns `(item, stream)` pairs. `item.key` is a pseudonymous key (file name and index). `item.truth` holds the text of the file for your own evaluation. It never goes into a stream.

Each stream reaches the conformance level `provenance`. Its `meta` has `decoder.name` (`fidetype-<model>`), `decoder.version`, `decoder.weights_sha256` (the SHA-256 of the weights file), `adapter.name` and `adapter.version`, an opaque `stream.id`, `data.licence`, `data.research_only` and `fidetype.pretrained` (`<model>@<version>`). Write streams with `m.save(streams, "out/")` (NTS JSON Lines).

`m.text(stream)` gives a greedy readout without an LM: ARPAbet phonemes for T15 / T12 (`|` marks a word boundary), characters for emg2qwerty and Willett, the screen text of the argmax keys for KT-sEMG.

`willett-hw` also has an **opt-in LM readout**: `m.text(stream, readout="lm")`. It is a CTC prefix beam search (beam 8 with a Tatoeba 6-gram character LM, weight 0.5, length bonus 1; `fidetype.pretrained.lmreadout`, NumPy) after a no-signal gate (see below). `m.lm_readout()` returns the readout object (`text`, `nbest`, `decode_fn`). The LM file `eng_tatoeba_6gram_mkn_noE2Q_noWillett.npz` (every Willett text blocked from it) is the only LM of the readout, so it is the default. It is local only (manifest role `text`, SHA-256 checked; model folder or `<cache>/text/`): its build blocklist holds research-only emg2qwerty texts, so we do not release the file.

## The trust guard

`m.guard()` loads the [trust configuration](glossary.md#trust-configuration) that we calibrated for the model (`fidetype.trust.load`). The guard input differs per model. So use one call for every model: `m.decide(stream)` (the default guard is built at the first call and then kept; pass `guard=` to use your own, and `utterance_id=` for the audit log). `m.guard_input(stream)` gives the guard input, so `m.decide(stream)` is `m.guard().decide(m.guard_input(stream))`. The guarantee holds only for the decoder and the text decoder that the configuration was calibrated with. `print(m.guard().sheet)` shows the guarantee sheet, with the `config_id` of the configuration.

| Model | Guard | Input of `guard.decide` | Behaviour |
|---|---|---|---|
| `t15-m4-13` | In the package ([alpha](glossary.md#alpha-delta) 0.05, delta 0.1). Its text decoder (phoneme beam -> lexicon words -> character LM) is built automatically from three text files (CMU dictionary, Tatoeba character 6-gram LM, Tatoeba word counts) | `stream.log_probs` | Commits, offers and withholds |
| `kt-semg-lda` | A release file next to the weights | The key n-best list in screen text, `m.nbest(stream)` (this is `m.guard_input(stream)`) | The decoder is weak. The guard offers and never commits (correct behaviour) |
| `willett-hw` | A release file next to the weights (alpha 0.05, delta 0.1, built-in CTC beam, no LM) | `stream.log_probs` | **Never commits.** It offers or withholds. Two [offer gates](glossary.md#offer-gate) are on by default: frame order (`coherence`) and time direction (`lm_beam_direction`, needs the local LM file; tested on training data only) |
| `willett-hw`, LM readout | `m.guard(readout="lm")`: a second release file, `willett-hw.lm3.guard.json` (alpha 0.05, delta 0.1; the no-signal gate plus the LM readout with the Willett-blocked LM) | `stream.log_probs` | **Never commits.** The same two offer gates are on by default. `m.decide(stream)` keeps the first `willett-hw` guard |
| `t12-v2`, `emg2qwerty-p11-01` | None yet (`NoTrustConfig`) | - | Calibrate your own with [`fidetype.trust.calibrate`](trust-quickstart.md) |

For the `kt-semg` benchmark track, use `m.track_nbest(stream)`: the same n-best idea, but in the track text space (one W3C `KeyboardEvent.code` per key press, `Backspace` included). `fidetype.adapters.kt_semg.codes_from_text(text)` converts screen text to codes; it is lossy (screen text has no `Backspace`).

Why the `willett-hw` guards never commit: the 106 validation sentences give 40 [LTT](glossary.md#ltt-learn-then-test) items, and alpha 0.05 with delta 0.1 needs at least 45. So no commit threshold is certified, and [safe WPM](glossary.md#safe-wpm) v0.1 is 0 (`vacuous`). The offers are not certified. The test counts are in the collapsed section [Evidence and history](#evidence-and-history) at the end of this page.

### The offer null control in the manifest (`trust.offer_control`)

The guarantee covers commits only. An OFFER is a suggestion list, and it has no bound. The offer null control ([trust guarantee](trust-guarantee.md) section 5a) asks one question: does the guard offer less often on null input (no signal) than on real input? Each packaged guard has the result of this check in its manifest, in `trust.offer_control`. A readout guard has its own copy in `readouts.<name>.trust.offer_control` (today: `willett-hw` `readouts.lm`). `m.manifest.offer_controls` gives the blocks (key `"default"` or the readout name). `fidetype decoders info <name>` prints one `offer control` line for each guard.

| Key | Meaning |
|---|---|
| `verdict` | `"pass"` if every control passes, else `"fail"`. The parser refuses a verdict that does not agree with the `passed` flags |
| `mode` | The `offer_control` mode of the check. `"warn"`: a failure changes no guard, `config_id`, certified status or commit. Rule: a trust block that ships an `offer_gate` must have verdict `"pass"`, or the parser refuses the manifest (mode `"refuse"` for gated guards). The `calibrate` default stays `"warn"` |
| `checked` | Date of the check |
| `rule` | The pre-stated rule: a control passes if null offer rate <= 0.5 x real offer rate, and (null offers <= floor(0.05 n) or one-sided Fisher exact p <= 0.05). Real = the LTT items |
| `real` | `n` and `n_offer` on the real LTT items |
| `controls` | One entry per null control: `name` (as in the guarantee sheet), `label` (what the input is), `n`, `n_offer`, `p_value`, `passed` |
| `ltt_commits`, `commits_match_sheet` | Check of the method: the re-check gives the same commit counts as the stored sheet |
| `effect` | What the result means for the user of the guard |
| `source` | The re-check result file in the source tree (`recheck_offer_control` on the saved guard, no new calibration) |

Three guards have an offer gate ([trust guarantee](trust-guarantee.md) section 5b): `willett-hw`, its LM readout and `t15-m4-13`. The two `willett-hw` guards have a list of two gates: `coherence`, then the direction gate `lm_beam_direction >= 0`. The gate is on by default; `m.guard(offer_gate=False)` (or `m.guard(readout="lm", offer_gate=False)`) switches it off. The manifest block then shows the gated re-check, and the counts without the gate stay in `before_gate`. With the gate, the three guards pass. `kt-semg-lda` has no gate and fails the check: it offers as often on null input as on real input. So do not show the offer list of `kt-semg-lda` as evidence that the signal was read. The gate changes no commit, no `config_id` and no certified status. `tests/test_pretrained_offer_control.py` checks that the manifest values equal the re-check files. The values per guard are in [Evidence and history](#evidence-and-history).

## `willett-hw`: read this before you use it

`willett-hw` is our own Willett handwriting decoder (random init, all 506 minutes of the CC0 data, seed 0, final step). It is clean-track: Willett CC0 data only, no emg2qwerty-derived trunk.

| Fact | Value |
|---|---|
| Greedy test CER, no LM (last block of each of the 10 sessions, 80 sentences, 3,448 characters) | **0.305**, rerun with `load("willett-hw")` on CPU: 0.3051 (1,052 / 3,448), equal to the PyTorch value per sentence (80 / 80) |
| Same recipe, seed 1 | 0.920: training failed. One good seed is not a reliable method |
| Language model | none by default. Opt-in LM readout (Willett-blocked LM): test CER **0.1746** with the gate (0.1743 without it, same text on 80 / 80 sentences); val 0.127 |
| LM readout licence | the LM is built from Tatoeba English sentences: **CC BY 2.0 FR**, attribution "Sentences from Tatoeba (https://tatoeba.org), by the Tatoeba contributors" |
| LM readout test overlap | none: the LM is built with every Willett text blocked. An earlier LM held 13 of the 80 test sentences; it is no longer used |
| No-signal gate | A score gate: a small logistic score of five posterior features (emission peak probability, entropy of the non-blank frames, share of non-blank frames, emissions per second, log emissions) plus `n_keys >= 1` and a rate cap; fitted and chosen on val only. Threshold `lo` = 0.566 since 2026-11-22 (was -1.170). Test: it stops 3 / 80 real sentences (was 1 / 80), all uniform and zero inputs, and 80 / 80 time-shuffled inputs (was 78 / 80); on 10 new time-shuffled draws 0 / 800 emit text (was 18 / 800). Gated test CER 0.177 (was 0.175). It cannot see the frame order: frame-shuffled decoder frames pass (78 / 80). Treat an LM-readout text as a suggestion, not as evidence that the signal was read |
| Weights licence | CC0-1.0; not hosted yet (the upload is a separate maintainer step) |
| Direction gate (both guards) | `lm_beam_direction >= 0`, on by default after the `coherence` gate. It decodes the frames forward and in reverse time order with the LM readout, and keeps an offer only if the frames read better forward. It stops offers on streams whose frames were reversed by a software fault (`coherence` cannot see this). Threshold fixed at 0, not fitted. Cost: two extra beam searches per offer (median 0.08 to 0.25 s on one CPU core). Both guards need the local LM file for it |

- The decoder is **weak**. The published Willett et al. 2021 real-time decoder is much better (other recipe). Use the numbers as descriptive only. They are an offline replay of one participant (T5), not a user study.
- Only the 10 dataset sessions have z-score statistics (`session=`).
- **The direction gate of the built-in guard was tested on training data only.** With the threshold 0 it passed on the 781 sentences that trained the decoder (reversed frames 1 offer in 781; real offers removed 1 in 781). The dataset has no unused sentences, so a test on new data was not possible. The LM guard passed on the same sentences (0 and 0), and an earlier version of it also passed on the test set with a fitted threshold. Treat the direction gate of the built-in guard as weakly tested.
- Its split is not the split of the benchmark track `willett-hw` (last 3 sessions). 193 of that track's 254 test trials were in this model's training pool. Do not score this model on that track.
- Details: [training and evaluation record](../experiments/2026-11-19-p14-33-willett-hw/results.md).

## Command line

```sh
fidetype decoders list
fidetype decoders info t15-m4-13
fidetype decoders path t15-m4-13
fidetype decoders verify t15-m4-13
fidetype decoders decode t15-m4-13 t15.2023.08.13/data_val.hdf5 --limit 3 --out streams/
fidetype decoders decode emg2qwerty-p11-01 <session>.hdf5 --accept-research-only --out streams/
fidetype decoders decode willett-hw <handwritingBCIData>/Datasets/t5.2020.01.15 --limit 3 --out streams/
```

`decode` checks each stream with the conformance suite (`--level`, default `provenance`) and exits with code 1 if a stream is below the level. `--text` also prints the greedy readout.

## Example: a few public test items, end to end

[`examples/pretrained_decode.py`](../examples/pretrained_decode.py) loads a model, decodes a few items of a public file, checks the NTS level, runs the guard and prints an aggregate error rate. It prints no decoded text unless you pass `--show-text`.

```sh
python examples/pretrained_decode.py t15-m4-13 <b2t25>/t15.2023.08.13/data_val.hdf5 --n 5 --odd
python examples/pretrained_decode.py kt-semg-lda <kt-semg>/run28.csv --n 3
python examples/pretrained_decode.py emg2qwerty-p11-01 <session>.hdf5 --n 3 --accept-research-only
```

Output on the project machine (2026-11-19, CPU; aggregate lines only):

| Command | Items | Result |
|---|---|---|
| `t15-m4-13`, `t15.2023.08.13/data_val.hdf5 --n 5 --odd` | 5 trials | all NTS level `provenance`; guard 1 commit, 4 offers; WER of the guard's top-1 words 0.182 (6 / 33); 8 s |
| `t12-v2`, `test/t12.2022.08.25.mat --n 5` | 5 trials | all `provenance`; no guard (no packaged trust config) |
| `kt-semg-lda`, `run28.csv --n 3` | 3 bursts, 206 keys | all `provenance`; guard 3 offers; key error 0.757 (weak decoder) |
| `emg2qwerty-p11-01`, one test session `--n 3` | refused without the opt-in; with `--accept-research-only`: 3 prompts | all `provenance`, `data.research_only = true`; greedy CER 0.695 (82 / 118) |

Full reruns of the model-card metrics ([results](../experiments/2026-11-19-p14-01-pretrained/results.md)): T15 val_eval greedy PER 0.1210 (card 0.1210), guard decisions equal to the calibration run on 701 / 701 trials; T12 test PER 0.2695 (card 0.269); emg2qwerty generic prompt CER 0.5831 (card 0.5832); KT-sEMG run28 key accuracy 0.242 (card 0.248, other timing path); Willett test greedy CER 0.3051 (card 0.3051, [record](../experiments/2026-11-19-p14-33-willett-hw/results.md)).

## Try the API without weights: the toy model

The release weights are not hosted yet. To learn the API, use a toy model. There is one toy model for each runtime:

```python
import numpy as np
import fidetype.pretrained as ftp

toy = ftp.toy_model()                                   # gru-ctc; files in a new temporary folder
st = toy.decode(np.zeros((200, 16), np.float32), session=toy.sessions[0])
print(st.log_probs.shape, toy.text(st))                 # (99, 41), noise

hw = ftp.toy_model("xbody-ctc")                         # the runtime of willett-hw
st = hw.decode(np.zeros((150, 192), np.float32), session=hw.sessions[0])   # (150, 98)
emg = ftp.toy_model("crt-ctc")                          # the runtime of emg2qwerty-p11-01
st = emg.decode(np.random.randn(2000, 32))              # 1 s of 2 kHz EMG -> (97, 98)
keys = ftp.toy_model("key-lda")                         # the runtime of kt-semg-lda
st = keys.decode(np.random.randn(6000, 32), times=[0.5, 1.0, 1.5])         # one frame per key press

path = ftp.make_toy_manifest("my-folder", runtime="crt-ctc")   # or write the files yourself ...
m = ftp.load(str(path), weights="my-folder")                   # ... and load them as any model
```

| Runtime | Real model | Toy name | Input of `decode` | Default `n_in` |
|---|---|---|---|---|
| `gru-ctc` | `t15-m4-13`, `t12-v2` | `toy-gru` | (T, `n_in`) 20 ms binned features, `session=` | 16 |
| `xbody-ctc` | `willett-hw` | `toy-xbody` | (T, `n_in`) threshold crossings in 10 ms bins, `session=` | 192 |
| `crt-ctc` | `emg2qwerty-p11-01` | `toy-crt` | (n, 32) raw EMG at 2 kHz, n >= 84 | 32 (fixed) |
| `key-lda` | `kt-semg-lda` | `toy-lda` | (n, `n_in`) raw EMG at 2 kHz, `times=` (key onsets, s) | 32 |

| Fact | Value |
|---|---|
| Call | `toy_model(runtime="gru-ctc", folder=None, **options)`. The first argument is the runtime; give the folder as `folder=` |
| Weights | random numbers (`seed=`). **The output is noise**: the model has learned nothing |
| Options | `n_in` (input channels), `hidden`, `layers` (not used by `key-lda`), `sessions` (`gru-ctc` and `xbody-ctc` only), `name`, `seed` |
| Files | `<name>.weights.npz` (`key-lda`: `<name>.model.json` and `<name>.weights.json`) and `<name>.json`; `load()` checks the SHA-256 and the size, as for a real model |
| Licence | CC0-1.0, not research-only (random numbers; no data) |
| Trust | none: `toy.decide(stream)` raises `NoTrustConfig`. Calibrate a guard with [`fidetype.trust.calibrate`](trust-quickstart.md) |

## Add a model

1. Train the model. Export its weights as plain arrays (`.npz`, no pickle) or JSON.
2. Write `src/fidetype/pretrained/manifests/<name>.json` (schema `fidetype.pretrained-manifest/0.1`; see [`manifest.py`](../src/fidetype/pretrained/manifest.py)). Give each file its SHA-256 and size, and leave `url` null until the file is hosted.
3. Use an existing runtime (`gru-ctc`, `crt-ctc`, `key-lda`, `xbody-ctc`) or add one to `RUNTIMES` in [`__init__.py`](../src/fidetype/pretrained/__init__.py).
4. If the model has a trust guard, run `fidetype.trust.recheck_offer_control` on it and copy the counts into `trust.offer_control` (see above).
5. Add a test with tiny fake weights ([`tests/test_pretrained.py`](../tests/test_pretrained.py)), and rerun the metric of the model card with the real weights.

## Limits

- The models do not transfer to a new person, a new session or a new device without calibration. The T15 and T12 day layers and the Willett z-score statistics exist only for the sessions of the datasets.
- All numbers are offline replays of public recordings, not user studies.
- The weights are not hosted yet. Until then, `pip install fidetype` gives the registry and the runtimes, but not the weights.

## Evidence and history

<details>
<summary>Evidence and history</summary>

The guard counts on the test sets, and how the guards changed. The full records are linked.

- `t15-m4-13`: the guard comes from the safe-WPM baseline run ([record](../experiments/2026-11-16-p14-05-safe-wpm/results.md)).
- `willett-hw`, no LM ([record](../experiments/2026-11-20-p14-41-willett-guard/results.md)): on the 80 test sentences it offers 77 and withholds 3; safe WPM v0.1 is 0 (vacuous). All null controls pass (0 commits). Without an offer gate the guard offers as often on frame-shuffled decoder frames (77 / 80) as on real input. The manifest offer gate (`coherence >= 0.00418`, [record](../experiments/2026-11-21-p14-54-willett-order-gate/results.md)) withholds those offers: test frame-shuffled 0 / 80, real 77 / 80, time-shuffled 1 / 80.
- `willett-hw` with the LM readout ([record](../experiments/2026-11-22-p14-59-ship-lo/results.md), 2026-11-22; the file replaces `willett-hw.lm2.guard.json`): the no-signal gate ([record](../experiments/2026-11-20-p14-49-willett-gate-blocked-lm/results.md)) uses the threshold `lo` 0.566. Test: 0 commits, 77 offers, 3 withholds (the 3 inputs that the no-signal gate stops); safe WPM v0.1 0 (vacuous). Commit controls pass (0 commits on every null input). With the manifest offer gate (`coherence >= 0.003486`, refitted by the same rule as the first `willett-hw` gate; on by default): offers on frame-shuffled 0 / 80, time-shuffled 0 / 80, zero 0 / 80, uniform 0 / 80, real 77 / 80 (0 real offers removed by the offer gate).
- Direction gate, both `willett-hw` guards (2026-11-23, [record](../experiments/2026-11-23-p14-60-ship-direction-gate/results.md)): the offer null control gives the same counts with the gate added (pass). On the 80 test sentences (already used data, so for information only) the built-in guard offers on 76 real inputs (1 removed by the gate) and on 1 time-reversed input (77 without the gate); the LM guard on 75 real (2 removed) and 2 time-reversed. The rule was checked before on the 781 training sentences only ([record](../experiments/2026-11-22-p5-37-fixed-threshold/results.md)).

Offer null control values (2026-11-21; the two `willett-hw` rows were checked again on 2026-11-23 with the direction gate added, [record](../experiments/2026-11-23-p14-60-ship-direction-gate/results.md): the same counts; all checks in warn mode). Re-check without a gate: [record](../experiments/2026-11-21-p5-31-offer-control/results.md). Gate selection for `t15-m4-13` and `kt-semg-lda`: [record](../experiments/2026-11-21-p5-33-withhold/results.md).

| Guard | Offer gate | Real offers | Null offers | Verdict | Without the gate |
|---|---|---|---|---|---|
| `willett-hw` | `coherence >= 0.00418`, then `lm_beam_direction >= 0` | 40 / 40 | uniform 0 / 300; frame-shuffled 0 / 300; time-shuffled input 0 / 106 | PASS | FAIL: frame-shuffled 297 / 300 |
| `willett-hw` LM readout | `coherence >= 0.003486`, then `lm_beam_direction >= 0` | 40 / 40 | uniform 0 / 300; frame-shuffled 0 / 300; time-shuffled input 0 / 106 | PASS | FAIL (previous LM guard): frame-shuffled 289 / 300 |
| `t15-m4-13` | `coherence >= 0.187` | 212 / 271 | uniform 0 / 300; frame-shuffled 0 / 300 | PASS | FAIL: uniform 300 / 300, frame-shuffled 300 / 300 |
| `kt-semg-lda` | none (no candidate passed) | 65 / 65 | uniform 300 / 300 (FAIL); user nulls (random key windows) 173 / 173 (FAIL) | FAIL | - |

</details>
