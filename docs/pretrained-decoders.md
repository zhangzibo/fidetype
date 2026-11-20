# Pretrained decoders

Fidetype has a small registry of pretrained decoders for public datasets. One line loads a model. One line decodes a public data file into NeuralTextStream (NTS). An optional third line adds the trust guard that we calibrated for the model.

```python
import fidetype.pretrained as ftp                 # fidetype.decoders.load is the same function

m = ftp.load("t15-m4-13")                         # checks the SHA-256 and the size of the weights
streams = m.decode("t15.2023.08.13/data_val.hdf5")     # one NTS stream per trial
guard = m.guard()                                 # the committed trust config of this model
r = guard.decide(streams[0].log_probs)
print(r.action, r.text or r.choices[:1])          # commit / offer / withhold
```

Code: [`src/fidetype/pretrained/`](../src/fidetype/pretrained/__init__.py). Roadmap task P14-01. The weights are **not** in the package and **not** in the git repository. Hosting is a separate user step (P14-02, [publishing checklist section J](publishing-checklist.md#j-pretrained-weights-optional-45-min-roadmap-p14-02)).

## Models

`fidetype decoders list` prints this table from the packaged manifests.

| Name | Task | Input file | Training data (licence) | `data.research_only` | Status |
|---|---|---|---|---|---|
| `t15-m4-13` | Implant attempted speech, phonemes (CTC), causal GRU | Brain-to-Text '25 `data_*.hdf5` (one session folder) | T15, Card et al. 2024 (CC0 1.0) | false | available; trust config packaged |
| `t12-v2` | Implant attempted speech, phonemes (CTC), causal GRU | Brain-to-Text '24 `competitionData/test/t12.*.mat` | T12, Willett et al. 2023 (CC0 1.0) | false | available; no packaged trust config (gap) |
| `kt-semg-lda` | Forearm sEMG typing, one key per press (LDA) | KT-sEMG `runN.csv` + key log | KT-sEMG, Nokia (CC BY 4.0, attribution) | false | available; guard is a release file |
| `emg2qwerty-p11-01` | Wrist sEMG typing, characters (CTC), causal ring-TCN, generic model | emg2qwerty session `*.hdf5` | emg2qwerty, Meta (CC BY-NC-SA 4.0) | **true** | available, **research only** |
| `willett-hw` | Implant handwriting, characters (CTC), causal TCN, our own (P15-08 run R-all-s0). **Weak**: greedy test CER 0.305, no LM | Willett handwriting 2021, one session folder `Datasets/t5.*` (`sentences.mat`) | T5, Willett et al. 2021 (CC0 1.0) | false | available; weights licence CC0 1.0 **provisional** (user decision D11); no packaged trust config (gap 121) |
| `toronto-semg-cnn` | Forearm sEMG typing, key-press CNN | Toronto sEMG | CC BY 4.0 | false | planned (no runtime yet) |

Each model card (`fidetype decoders info <name>`) gives the input spec, the architecture, the release files with SHA-256 and size, the licence of the data and the proposed licence of the weights, the training run, the metrics and the limits.

All runtimes are NumPy only. They need no PyTorch and no GPU. The readers need `h5py` (`pip install fidetype[emg2qwerty]`) for HDF5 files and `scipy` (`pip install fidetype[data]`) for the T12 and Willett `.mat` files.

## Where the weights come from

`load()` looks for the release files in this order:

1. `weights=` (a folder with the files, or the path of the weights file);
2. `cache_dir=`, or the environment variable `FIDETYPE_PRETRAINED_DIR`;
3. `~/.cache/fidetype/pretrained` (or `$FIDETYPE_CACHE/pretrained`).

In a cache folder, the files of model `<name>` are in `<cache>/<name>/`. The text files of the T15 word decoder can also be in `<cache>/text/`. `fidetype decoders path` shows the exact paths and which files are missing. `fidetype decoders verify <name>` checks the SHA-256 and the size of each file.

Every file must match its manifest. A wrong size or hash raises `WeightsMismatch`. A missing file raises `WeightsNotFound`. The message names the folders that `load()` searched.

`download=True` fetches a missing file from the `url` of its manifest entry, then checks it before it moves into the cache. **No model has a URL yet.** On the project machine, `tools/pretrained/export_weights.py` makes the release files from our training outputs.

## The licence gate

The manifest of each model carries the FEP-0010 keys `data.licence` and `data.research_only`. A model with `data.research_only = true` (today: `emg2qwerty-p11-01`) refuses to load or download:

```python
ftp.load("emg2qwerty-p11-01")                              # ResearchOnlyRefused
m = ftp.load("emg2qwerty-p11-01", accept_research_only=True)   # explicit opt-in
```

On the command line the opt-in is `--accept-research-only`. Use it only for non-commercial research, and only if you accept the licence. The weights keep the share-alike terms of the data. Every stream from such a model carries `data.research_only = true`, so the Collector option `refuse_research_only = true` drops it downstream ([provenance and privacy](provenance-and-privacy.md)). A manifest cannot be looser than its data licence: the parser rejects an NC licence with `data.research_only = false`.

## What `decode()` returns

| Input | Result |
|---|---|
| A file path (str or `Path`) | A list of streams, one per trial (T15, T12), text prompt (emg2qwerty), typing burst (KT-sEMG) or sentence (Willett; a session folder or its `sentences.mat`; `blocks=` keeps some blocks) |
| An array | One stream. T15 / T12: `(T, 512)` features of one trial plus `session=` (the session name). emg2qwerty: `(n, 32)` raw EMG at 2 kHz. KT-sEMG: `(n, 32)` EMG plus `times=` (key onsets in seconds). Willett: `(T, 192)` threshold crossings in 10 ms bins from the go cue, plus `session=` (one of the 10 `t5.*` sessions) |

`decode_file(path, with_items=True)` returns `(item, stream)` pairs. `item.key` is a pseudonymous key (file name and index). `item.truth` holds the text of the file for your own evaluation. It never goes into a stream.

Each stream reaches the conformance level `provenance`. Its `meta` has `decoder.name` (`fidetype-<model>`), `decoder.version`, `decoder.weights_sha256` (the SHA-256 of the weights file), `adapter.name` and `adapter.version`, an opaque `stream.id`, `data.licence`, `data.research_only` and `fidetype.pretrained` (`<model>@<version>`). Write streams with `m.save(streams, "out/")` (NTS JSON Lines).

`m.text(stream)` gives a greedy readout without an LM: ARPAbet phonemes for T15 / T12 (`|` marks a word boundary), characters for emg2qwerty and Willett, the screen text of the argmax keys for KT-sEMG.

## The trust guard

`m.guard()` loads the trust config that we committed for the model (`fidetype.trust.load`). The guarantee holds only for the decoder and the text decoder that the config was calibrated with:

- `t15-m4-13`: the P14-05 guard (`tcfg-1016759f08a3f9a1`, alpha 0.05, delta 0.1) is in the package. Its text decoder (phoneme beam -> lexicon words -> character LM) is built automatically from three text files (CMU dictionary, Tatoeba character 6-gram LM, Tatoeba word counts). Input: `guard.decide(stream.log_probs)`.
- `kt-semg-lda`: the guard is a release file next to the weights. Input: the key n-best list, `guard.decide(m.nbest(stream))`. This decoder is weak; its guard offers and never commits (correct behaviour).
- `t12-v2`, `emg2qwerty-p11-01`, `willett-hw`: no packaged trust config yet (`NoTrustConfig`). Calibrate your own with [`fidetype.trust.calibrate`](trust-quickstart.md). For `willett-hw` the guard is open gap 121 (P14-41).

## `willett-hw`: read this before you use it

`willett-hw` is our own Willett handwriting decoder: P15-08 run `R-all-s0` (random init, all 506 minutes of the CC0 data, seed 0, final step). It is clean-track: Willett CC0 data only, no emg2qwerty-derived trunk.

| Fact | Value |
|---|---|
| Greedy test CER, no LM (last block of each of the 10 sessions, 80 sentences, 3,448 characters) | **0.305**, rerun with `load("willett-hw")` on CPU: 0.3051 (1,052 / 3,448), equal to the PyTorch value per sentence (80 / 80) |
| Same recipe, seed 1 | 0.920: training failed. One good seed is not a reliable method |
| Language model | none |
| Weights licence | CC0-1.0, provisional (user decision D11); not hosted |

- The decoder is **weak**. The published Willett et al. 2021 real-time decoder is much better (other recipe). Use the numbers as descriptive only. They are an offline replay of one participant (T5), not a user study.
- Only the 10 dataset sessions have z-score statistics (`session=`).
- Its split is not the split of the benchmark track `willett-hw` (last 3 sessions). 193 of that track's 254 test trials were in this model's training pool. Do not score this model on that track.
- Details: [P14-33 results](../experiments/2026-11-19-p14-33-willett-hw/results.md).

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

Full reruns of the model-card metrics ([results](../experiments/2026-11-19-p14-01-pretrained/results.md)): T15 val_eval greedy PER 0.1210 (card 0.1210), guard decisions equal to P14-05 on 701 / 701 trials; T12 test PER 0.2695 (card 0.269); emg2qwerty generic prompt CER 0.5831 (card 0.5832); KT-sEMG run28 key accuracy 0.242 (card 0.248, other timing path); Willett test greedy CER 0.3051 (card 0.3051, [P14-33](../experiments/2026-11-19-p14-33-willett-hw/results.md)).

## Add a model

1. Train the model. Export its weights as plain arrays (`.npz`, no pickle) or JSON.
2. Write `src/fidetype/pretrained/manifests/<name>.json` (schema `fidetype.pretrained-manifest/0.1`; see [`manifest.py`](../src/fidetype/pretrained/manifest.py)). Give each file its SHA-256 and size, and leave `url` null until the file is hosted.
3. Use an existing runtime (`gru-ctc`, `crt-ctc`, `key-lda`, `xbody-ctc`) or add one to `RUNTIMES` in [`__init__.py`](../src/fidetype/pretrained/__init__.py).
4. Add a test with tiny fake weights ([`tests/test_pretrained.py`](../tests/test_pretrained.py)), and rerun the metric of the model card with the real weights.

## Limits

- The models do not transfer to a new person, a new session or a new device without calibration. The T15 and T12 day layers and the Willett z-score statistics exist only for the sessions of the datasets.
- All numbers are offline replays of public recordings, not user studies.
- The weights are not hosted yet (P14-02). Until then, `pip install fidetype` gives the registry and the runtimes, but not the weights.
