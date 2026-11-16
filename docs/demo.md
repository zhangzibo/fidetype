# Live demo: recorded decoder output, trust decisions on screen

`fidetype demo live` starts a small local server and opens a page in your browser. The page replays decoder output that was **recorded earlier**, at the speed it was recorded. For each utterance the trust layer decides:

| Decision | What the user gets | Mark on the page |
|---|---|---|
| COMMIT | the text is typed | solid text, green underline (red with "wrong" if it does not match the intended text) |
| OFFER | the text is only a suggestion; the user accepts or rejects it | dashed box, italic |
| WITHHOLD (ABSTAIN, ASK) | nothing is typed | grey hatched box with the score |

This is **not** live decoding. Every lane says "Replay of recorded data" (or "Synthetic data, not a recording").

![The live demo page on the synthetic track (no recording)](img/demo-live-synthetic.png)

*The screenshot shows the synthetic track. It contains no participant data.*

## Run it

```sh
pip install ".[ws]"          # the page uses the WebSocket server (websockets, BSD-3-Clause)
fidetype demo live           # default tracks; opens http://127.0.0.1:8770/
fidetype demo live --tracks synthetic     # needs no data
fidetype demo live --check                # which tracks have their data
```

Options: `--speed 2` (twice real time), `--start K` (begin at utterance K), `--no-browser`, `--port N`, `--no-loop`, `--duration S`, `--config FILE`. Press Ctrl+C to stop. The server binds to 127.0.0.1 only. Nothing leaves your computer.

## What the page shows
- **Live text:** the decisions of the lane, in order, with the marks above.
- **Now decoding:** a progress bar for the signal time, the raw decoder output so far (grey; phonemes for the implant track, keys for the EMG track), and the intended text (used only to score the decisions).
- **Counts:** committed, offered and withheld so far, and the wrong commits so far.
- **Whole replay set:** the wrong-commit rate over all utterances of the track (wrong commits / all utterances) with a 95 % Clopper-Pearson interval, the commit rate, the share of wrong commits among commits, how many offers contain the intended text, and the "always commit" baseline (type every top-1 text). These numbers do not depend on how far the replay is.
- **Latency:** the trust-layer time after the end of the signal for the last decision, and the median.
- **Dataset and licence** of each lane, and "Research use only" where the licence is non-commercial.

## Tracks (default configuration)

| Track | Data | Licence | Decoder and trust configuration |
|---|---|---|---|
| `t15` | Brain-to-Text '25, participant T15 (intracortical), 701 held-out `val_eval` sentences | CC0-1.0 | M4-12 GRU-CTC phoneme decoder + word decoder; recorded decisions of trust config `tcfg-e7e8c472f6d9ab33` (M2-19) |
| `emg2qwerty` | emg2qwerty wrist sEMG, P4-01 baseline streams (8 users x 2 sessions, held-out half), 700 prompts | CC BY-NC-SA 4.0, **research use only** | P4-01 LDA key classifier; trust config fitted by `--prepare emg2qwerty` on the first half of the prompts of each session |
| `synthetic` | simulated decoder streams (M7-01) | Apache-2.0 | packaged demo config |
| `p11-01-emg` | template, disabled | CC BY-NC-SA 4.0 | the P11-01 EMG decoder, when it writes NTS files |

The real tracks read data from `${DATA}` = the environment variable `FIDETYPE_DATA` (default `~/bci-data`). If a file is missing, the command names it and does not start that track. A track that you ask for by name (`--tracks t15`) and that is missing stops the command with exit code 2.

The `emg2qwerty` track needs a one-time preparation (about 15 seconds; it reads only the keylogger attributes of the raw files, not the EMG):

```sh
fidetype demo live --prepare emg2qwerty
```

It writes `truth.json`, `split.json`, the trust configuration and `eval.json` to `${DATA}/derived/p14-06-demo/emg2qwerty/`. These files are derived from research-only data. They never go into the repository.

## Honest numbers (2026-11-15)

| Track | Commits | Wrong commits / all (95 % CI) | Wrong among commits | Always commit, wrong |
|---|---|---|---|---|
| `t15` | 9 of 701 | 6 / 701 = 0.86 % (0.31 % to 1.85 %) | 6 of 9 | 640 of 701 |
| `emg2qwerty` | 3 of 700 | 3 / 700 = 0.43 % (0.09 % to 1.25 %) | 3 of 3 | 700 of 700 |

Both are below the target alpha 0.05, but the commits are rare and most of them are wrong. The decoders are weak: the trust layer keeps the wrong-commit rate low mainly by offering almost everything. M2-19 also found that the T15 config needs the M2-18 commit gate before real use. The page shows these numbers next to the replay.

## Add your own decoder (no code change)

Write your decoder output as NTS files (for CTC logits: `fidetype.adapters.ctc_logits`), freeze a trust configuration (`fidetype.api.calibrate(...).save(...)`), and add a track of kind `nts-streams` to a copy of the configuration file ([`src/fidetype/demo/live/live-demo.json`](../src/fidetype/demo/live/live-demo.json)):

```json
{"id": "my-decoder", "kind": "nts-streams", "title": "My decoder",
 "dataset": {"name": "my recordings", "licence": "CC-BY-4.0"},
 "streams_dir": "${DATA}/my/nts", "trust_config": "${DATA}/my/trust.json", "decoder": "greedy",
 "truth": {"format": "json-map", "path": "${DATA}/my/truth.json", "field": "text"}}
```

Then run `fidetype demo live --config my-demo.json --tracks my-decoder`. `decoder` is `greedy` (CTC greedy), `keys` (key-press streams) or `demo`. Without `truth`, the page says that the wrong-commit rate is unknown. The P11-01 EMG decoder plugs in the same way (template track `p11-01-emg`).

## For app developers

The same server also sends only the `trust_decision` events (FEP-0001) on `ws://127.0.0.1:<port>/decisions` (FEP-0004 binding `nts-ws/0.1`), as an AAC app would read them. The page itself uses `/events` (demo messages) and `/state/state.json`.

## Code
- [`src/fidetype/demo/live/`](../src/fidetype/demo/live/): configuration, tracks, server, key decoder, emg2qwerty preparation, page (`web/index.html`).
- Tests: [`tests/test_demo_live.py`](../tests/test_demo_live.py) (synthetic data only).
