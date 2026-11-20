# Contributing to Fidetype

Thank you for your interest. This file tells you how to set up the project, how to send a change, and which rules apply.

All contributors must follow the [Code of Conduct](CODE_OF_CONDUCT.md). The decision process is in [GOVERNANCE.md](GOVERNANCE.md).

## 1. Set up

### 1.1 CPU environment (all contributors)
You need Python 3.12 and [uv](https://docs.astral.sh/uv/).

```sh
git clone https://github.com/zhangzibo/fidetype.git
cd fidetype
uv sync --extra dev        # create .venv and install fidetype + pytest
uv run pytest -q           # run the tests
```

The `data` extra (`uv sync --extra dev --extra data`) adds MNE and SciPy. You need it only for the dataset loaders and preprocessing.

### 1.2 GPU environment (optional)
The decoders train on a GPU. CI and most tests do not need a GPU.

On Windows with an AMD GPU, run:

```powershell
powershell -ExecutionPolicy Bypass -File tools\env\setup_rocm.ps1
```

The script creates a separate venv at a short path (default `C:\venvs\fidetype-rocm`). Read the comments at the top of the script before you run it. All code must also run on the CPU.

## 2. Branches and pull requests
1. Fork the repository, or create a branch if you have write access. Use a short branch name, for example `fix-npz-reader` or `adapter-openbci`.
2. Make one change per pull request (PR). Keep PRs small.
3. Add or update tests for each code change.
4. Run `uv run pytest -q` locally.
5. Sign off each commit (see section 9).
6. Open a PR against `main`. Fill in the PR checklist.
7. A maintainer reviews the PR. Answer the review comments with new commits. Do not force-push during a review.
8. A maintainer merges the PR when CI is green and the review is approved.

For a large change, open an issue or a Discussion first. Then the maintainers can agree with the direction before you write the code.

## 3. Tests and CI
- GitHub Actions runs on every push to `main` and on every PR ([workflow](.github/workflows/tests.yml)): the Python tests (`uv run pytest -q`), the TypeScript and Rust SDK tests, the Python = TypeScript = Rust parity checks, the proto schema checks, the packaging dry runs and the repository hygiene check.
- Run `node tools/hygiene/check.js` and `node tools/hygiene/links.js` before you push. They fail on caches, data files, secrets, private e-mail addresses, files over 5 MB and broken relative links.
- **All tests must pass in CI.** A maintainer does not merge a PR with a red CI.
- CI has no GPU and no datasets. Tests that need them must skip cleanly when they are not available.
- Tests must be fast. Use small synthetic data or the noisy-decoder simulator.

## 4. Writing style
- Write documentation in **"80% ASD-STE100"** (Simplified Technical English):
  - short sentences, one idea per sentence;
  - active voice;
  - simple words with one meaning each;
  - no idioms and no filler.
- Keep exact technical terms (CTC, log-softmax, BCP 47).
- Use a table or a diagram when it explains better than prose.
- Code comments and docstrings follow the same style.

## 5. Data and licences
- **Never commit datasets.** This includes raw recordings, preprocessed caches, participant data, model weights trained on third-party data, and third-party PDFs. The `data/` folder is git-ignored.
- **Research-only data.** Some datasets that we use (for example, SpanishBCBL and emg2qwerty) are **CC BY-NC**. Use them only for research and benchmarks. Dataset loaders must download from the original source. They must not redistribute data.
- **Experiment results: aggregates only.** New experiments must not commit per-trial decoded text or stimulus (target) text. Write per-trial outputs outside the repository (for example `~/bci-data/derived/<experiment>/`, or the folder that `FIDETYPE_DERIVED` names). Commit only `plan.md`, `results.md` and aggregate numbers. See [LICENSES/DATA.md](LICENSES/DATA.md).
- **Provenance.** Weights for any product use come only from CC0 data or from consented data that we own. Record which data trained which weights.
- **Code.** All code is Apache-2.0. Do not copy code with an incompatible licence. For example, Meta's Brain2Qwerty code is CC BY-NC, so Fidetype contains none of it.

## 6. No hidden magic
Every trust decision must be inspectable.
- A decision (commit, offer choices, ask, abstain, flag) must come with the scores and thresholds that caused it.
- No hidden prompts, no hidden thresholds, no undocumented heuristics.
- Configuration must be explicit and serialisable.
- A user or an auditor must be able to reproduce a decision from the logged inputs.

A PR that adds a decision without an explanation of its inputs will not be merged.

## 7. Adapters: add a decoder or a device
An adapter connects a decoder or a device to Fidetype. The contract is the [NeuralTextStream spec](spec/neuraltextstream-v0.1.md) (current release; the 1.0 draft is [RC2](spec/nts-1.0-rc2.md)). The user guide is [docs/getting-started.md](docs/getting-started.md).

**Decoder adapter.**
1. Make your decoder output `log_softmax` scores, shape [T, V].
2. Build a `fidetype.streams.spec.NeuralTextStream` with the frame times, the vocabulary, `vocab_type` and `blank_id` (`None` if the decoder is not CTC).
3. Fill `meta` with the [semantic conventions](spec/neuraltextstream-v0.1.md#4-semantic-conventions-for-meta) (`device.modality`, `decoder.name`, `decoder.causal`, ...).
4. Do not put ground-truth text or personal data in the stream.
5. Add a test that builds a stream from a small synthetic input and checks that it validates.

**Device adapter** (for example, a live stream through LSL):
1. Put the adapter code in its own module. Heavy dependencies go in an optional extra in `pyproject.toml`.
2. The adapter must not require the device in CI. Use recorded or synthetic samples in the tests.
3. Document the device, the modality, the sample rate and the licence of any example data.

### 7.1 Add a new adapter in about 50 lines
The [adapter catalogue](docs/adapters.md) lists every adapter and the planned ones. Pick a planned row, or propose a new one. The steps below are for a **signal source** (a device or a file format). A decoder adapter follows the same steps with the NTS helper (step 4).

1. **Copy the template.** Run `uv run python -m fidetype.adapters.registry new my-device` (kebab-case id). This writes `src/fidetype/adapters/my_device.py` and `tests/test_adapter_my_device.py` from [templates/adapter/](templates/adapter/).
2. **Fill in `ADAPTER_INFO`** at the top of the module: `id`, `kind`, `target` (the device, format or dataset), `signal` (an NTS `device.modality` value, or `any`), `status`, `licence`, `tests`, `docs`. Use `status: "experimental"` until the adapter has read real files or run on a real device. Never claim a device that you did not test: `hardware_tested` lists only real devices that it ran on.
3. **Write the reader.** Replace `read_my_device()`. Return the signal `(N, C)`, the sample rate in Hz, the channel labels and units, and the markers `(time, text)`. `open_source()` wraps them in an `ArraySource` (the source protocol of `fidetype live`: `info`, `start()`, `poll()`, `close()`). Put only NTS meta keys (spec 4.2) or keys in your own namespace (for example `mydevice.firmware`) in `meta`. Never put truth text or personal data there (file header fields such as "patient" often hold names). Bad input must raise `ValueError` with a clear message.
4. **Write the test on synthetic data.** Make `_write()` produce a small file in your format. The test calls `fidetype.adapters.testing.assert_source_conforms(...)` with `require_units=True` and at least one bad input. The helper checks the `info` keys, the `meta` keys (NTS 4.1 / 4.2 rules), the channel labels and units, the sample dtype and shape, strictly increasing times that match the sample rate, the markers, the end of the stream and the `ValueError` on bad input. A decoder adapter calls `assert_nts_conforms(...)` instead: it runs the NTS conformance suite at the level you give (default `trust-ready`).
5. **Check licences.** Do not copy code with an incompatible licence. Do not commit real recordings, participant data or third-party files. Heavy dependencies go in an optional extra in `pyproject.toml`; import them inside the function.
6. **Regenerate the catalogue.** Run `uv run python -m fidetype.adapters.registry`. Commit `docs/adapters.md` and `docs/adapters.json` with your code. If your adapter was a planned row, delete that row from `src/fidetype/adapters/planned.py` (the registry refuses an id that is both planned and implemented).
7. **Run the tests:** `uv run pytest -q tests/test_adapter_my_device.py tests/test_adapter_registry.py`. `tests/test_adapter_registry.py` fails when the catalogue is stale, when a field is wrong, or when a test or docs path does not exist.

Examples made from the template: [`edf.py`](src/fidetype/adapters/edf.py) (EDF / EDF+ / BDF files) and [`openbci_gui.py`](src/fidetype/adapters/openbci_gui.py) (OpenBCI GUI recordings), with their tests.

Use the "Adapter request" issue template to propose an adapter. In the future, adapter owners can be listed in a `CODEOWNERS` file. Then they review the changes to their adapter.

## 8. Spec changes: FEPs
A change to a spec in [`spec/`](spec/) needs a **FEP** (Fidetype Enhancement Proposal).
1. Copy [`spec/feps/0000-template.md`](spec/feps/0000-template.md) to `spec/feps/NNNN-short-title.md`.
2. Fill in all sections. Explain the compatibility impact.
3. Open a PR with the FEP alone.
4. When the FEP is accepted, a second PR changes the spec, the reference implementation, the tests and the changelog.

Small fixes (typos, broken links, clearer wording with the same meaning) do not need a FEP.

## 9. Developer Certificate of Origin (DCO)
Fidetype uses the [Developer Certificate of Origin](https://developercertificate.org/) instead of a Contributor Licence Agreement (CLA). By signing off, you state that you have the right to submit the change under the project licence.

Sign off each commit with `-s`:

```sh
git commit -s -m "Fix the NPZ reader for old files"
```

This adds a line `Signed-off-by: Your Name <you@example.com>` to the commit message. Use a name and an address that you are willing to make public. A GitHub `noreply` address is acceptable.

## 10. Security issues
Do not report a vulnerability in a public issue. Follow [SECURITY.md](SECURITY.md).
