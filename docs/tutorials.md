# Tutorials: Fidetype in 10 minutes each

Three short tutorials take you through the main jobs of Fidetype. Each one is a script in [`tutorials/`](../tutorials/) and a page that walks through it.

| # | Tutorial | You learn | Synthetic mode (CI) | Page |
|---|---|---|---|---|
| 1 | Decode text with a pretrained decoder | `fidetype.pretrained`: registry, `load()`, `decode()`, conformance check, save NTS | about 1 s | [tutorials-01-decode.md](tutorials-01-decode.md) |
| 2 | Add the trust guard and read the safe WPM | `fidetype.trust.calibrate`, `TrustGuard.decide`, the guarantee sheet, `safe_wpm()` | about 80 s | [tutorials-02-trust.md](tutorials-02-trust.md) |
| 3 | Score a decoder on the benchmark | submission folder v0.2, controls, `check_submission`, `score`, the score card, the leaderboard row | about 1 s | [tutorials-03-benchmark.md](tutorials-03-benchmark.md) |

## Rules of every tutorial

- It runs on a laptop CPU in less than 10 minutes. It needs no hardware and no GPU.
- It has a **synthetic mode**. This mode needs no download and no network. It makes its data (and, for tutorial 1, a tiny model) at run time.
- It has a **real-data mode**. The page says which public dataset to download and which command to run.
- It uses the public API only. Where the API is awkward for a newcomer, the page says so (section "API friction").

> **Synthetic numbers are toy numbers.** The synthetic mode shows each API step and each output field. It does not show how well a BCI works. Real numbers come only from the real-data mode or from the [leaderboard](../benchmark/README.md).

## Install

You need Python 3.12 or later. From a clone:

```sh
git clone https://github.com/zhangzibo/fidetype.git
cd fidetype
pip install .          # numpy is the only dependency of the synthetic mode
```

For the real-data modes, also install `h5py` (`pip install ".[emg2qwerty]"`; tutorials 1 and 2 read HDF5 files).

## Run all three

```sh
python tutorials/01_decode_pretrained.py
python tutorials/02_trust_and_safe_wpm.py
python tutorials/03_score_benchmark.py
```

Each script ends with one line, for example `TUTORIAL 2 PASS (synthetic): safe WPM status certified, 79.3 s`. Add `--out <folder>` to keep the output files (streams, guard, audit log, submission, score card). Without `--out`, the files go to a temporary folder that is deleted at the end.

## Measured wall times

The smoke test [`tutorials/test_tutorials.py`](../tutorials/test_tutorials.py) runs the three scripts in synthetic mode and times each one. The CI workflow [`tutorials.yml`](../.github/workflows/tutorials.yml) runs it on Linux and Windows, in a clean virtual environment with only the package and pytest. Done criterion (roadmap P14-43, set before the runs): all three pass, and each takes less than 10 minutes.

| Machine | Tutorial 1 | Tutorial 2 | Tutorial 3 |
|---|---|---|---|
| Project desktop (AMD Ryzen 7 9800X3D, Windows 11, Python 3.12), repo venv | 0.4 s | 79.3 s | 0.4 s |
| Same, process pinned to 2 logical CPUs | 0.4 s | 77.9 s | 0.4 s |
| Same, clean venv (`pip install .` + pytest only) | 1.6 s | 77.5 s | 0.4 s |
| GitHub Actions `ubuntu-latest`, Python 3.12, clean venv (run 44723379731) | 0.4 s | 62.5 s | 0.2 s |
| GitHub Actions `windows-latest`, Python 3.12, clean venv (run 44723379731) | 0.9 s | 94.7 s | 0.4 s |

The project desktop is faster than a normal laptop. Tutorial 2 uses one CPU core, so the pinned run gives the same time. The GitHub runners (2 to 4 virtual CPUs) are closer to a laptop. Each `tutorials` run writes its times to the job summary and to the `tutorial-times-<os>` artifact. The slowest time so far is 94.7 s, far below the 10-minute limit.

Real-data modes on the project desktop (local data and weights; not in CI):

| Tutorial | Command (short) | Items | Wall time |
|---|---|---|---|
| 1 | `--model t15-m4-13 --data t15.2023.08.13/data_val.hdf5 --n 5` | 5 trials | 12.4 s |
| 2 | `--model t15-m4-13 --data` 3 sessions (08.13, 08.18, 08.20) | 65 trials | 48.3 s |
| 3 | `--data <kt-semg> --runs run28` | 22 units | 47.4 s |

## Where the weights come from

The pretrained weights are **not hosted yet** (roadmap P14-02 and P14-30, open gap 98). So the real-data modes of tutorials 1, 2 and 3 need the release files on your machine (`--weights <folder>` or `FIDETYPE_PRETRAINED_DIR`). Until the weights are hosted, a newcomer can run only the synthetic modes. The real-data commands on each page are correct and were run on the project machine.

## Related pages

- [Getting started](getting-started.md): install, demo, emit your first stream.
- [Pretrained decoders](pretrained-decoders.md), [trust quickstart](trust-quickstart.md), [safe WPM](safe-wpm.md), [benchmark submission](benchmark-submission.md): the full reference of each tutorial's subject.
