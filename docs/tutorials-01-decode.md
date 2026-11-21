# Tutorial 1: decode text with a pretrained decoder

Time: about 1 s (synthetic mode), about 15 s (real data, 5 trials). Script: [`tutorials/01_decode_pretrained.py`](../tutorials/01_decode_pretrained.py). Index: [tutorials](tutorials.md).

At the end you can load a pretrained decoder, decode neural data into NeuralTextStream (NTS) streams, check each stream with the conformance suite, read the greedy text and save the streams.

## Run it

```sh
python tutorials/01_decode_pretrained.py                     # synthetic mode
```

The last line is `TUTORIAL 1 PASS (synthetic): 3 streams, 0.1 s`.

## What the synthetic mode does

The packaged models need weights that are not hosted yet (open gap 98). So the synthetic mode makes a **tiny random model** with the same runtime as `t15-m4-13` (`gru-ctc`). The model has learned nothing. Its text is noise. The API steps are the same as for a real model.

| Step | Code | What you see |
|---|---|---|
| 1. List the registry | `ftp.list_models()` | The six packaged models, their status and the `research_only` flag. No weights needed |
| 2. Make a toy model | `ftp.make_toy_manifest(folder)` (or in one line: `ftp.toy_model()`) | A weights file (`.npz`, plain arrays) and a manifest JSON that lists its SHA-256 and size |
| 3. Load | `ftp.load("toy-gru.json", weights=folder)` | `load()` checks the size and the SHA-256 of every file. A wrong file raises `WeightsMismatch` |
| 4. Decode | `model.decode(x, session=model.sessions[0])` | One `(T, channels)` array of 20 ms bins gives one stream: `log_probs` `(frames, 41)` over 39 ARPAbet phonemes, a word boundary and the CTC blank |
| 5. Check | `fidetype.conformance.check(stream).passes("provenance")` | Each stream reaches the level `provenance` (decoder name, version, weights SHA-256, licence keys) |
| 6. Read | `model.text(stream)` | A greedy phoneme readout without a language model, for example `JH OW JH SH ...` (noise) |
| 7. Save | `model.save(streams, folder)` | One NTS JSON Lines file per stream |
| 8. Guard | `model.decide(stream)` (the same call for every model) | `NoTrustConfig`: the toy model has no trust config. [Tutorial 2](tutorials-02-trust.md) calibrates one |

The main lines:

```python
import fidetype.conformance as conformance
import fidetype.pretrained as ftp

manifest = ftp.make_toy_manifest(out)                 # random weights + manifest (or: model = ftp.toy_model())
model = ftp.load(str(manifest), weights=out)          # a packaged name works the same: ftp.load("t15-m4-13")
stream = model.decode(x, session=model.sessions[0])   # x: (T, 16) float32, 20 ms bins -> one stream
assert conformance.check(stream).passes("provenance")
print(model.text(stream))
model.save([stream], out / "streams")
```

## Real data

| What | Value |
|---|---|
| Dataset | Brain-to-Text '25, participant T15 (Card et al. 2024), CC0 1.0 |
| Download | Dryad [doi:10.5061/dryad.dncjsxm85](https://doi.org/10.5061/dryad.dncjsxm85), file `t15_copyTask_neuralData.zip`; one session folder is enough, for example `t15.2023.08.13` |
| Extra package | `pip install ".[hdf5]"` (gives `h5py`) |
| Weights | `t15-m4-13` release files: not hosted yet (gap 98). Put them in a folder and pass `--weights`, or set `FIDETYPE_PRETRAINED_DIR` |

```sh
python tutorials/01_decode_pretrained.py --model t15-m4-13 \
    --weights <folder with the release files> \
    --data <b2t25>/t15.2023.08.13/data_val.hdf5 --n 5
```

For T15 the script counts the trials with `model.n_items(path)` and decodes the odd ones (the `val_eval` half). Each guard decision is `model.decide(stream)`. Other models (`t12-v2`, `kt-semg-lda`, `willett-hw`, `emg2qwerty-p11-01` with `--accept-research-only`) take their own files; see [pretrained decoders](pretrained-decoders.md). `--show-text` prints the greedy text and the truth.

Output on the project machine (2026-11-20, CPU, 12.4 s): 5 streams, all at level `provenance`; the packaged guard gave 1 commit and 4 offers.

## What this shows, and what it does not show

- The synthetic mode shows the API and the NTS output. Its text has no meaning.
- The real mode shows an offline replay of one participant's public recordings. It is not a user study. The model does not transfer to a new person or session without calibration.

## API friction (found while writing this tutorial)

Gap 129 (roadmap P14-44) listed these points. The API now has a fix for each one, and this tutorial uses them:

| Friction | Fix |
|---|---|
| No toy model helper: the script had to know the GRU parameter names and write a manifest with a SHA-256 by hand | `ftp.toy_model()` and `ftp.make_toy_manifest(folder)` ([pretrained decoders](pretrained-decoders.md#try-the-api-without-weights-the-toy-model)) |
| No item count, and `decode_file(indices=[...])` past the end raised a bare `IndexError` | `model.n_items(path)`; a bad index raises `IndexError` with the item count of the file |
| `decode()` returned one stream for an array but a list for a file | `decode(array)` gives one stream; `decode_file(path)` gives a list. `decode(path)` still works, with a `DeprecationWarning` |
| The guard input differed per model (`stream.log_probs`, `model.nbest(stream)`) | `model.decide(stream)` for every model; `model.guard_input(stream)` gives the input |
| `h5py` came with the extra `emg2qwerty`, also for T15 and T12 files | the extra `hdf5` (the old name still works) |
