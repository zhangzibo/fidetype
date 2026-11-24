# What to upload to a rented GPU machine

This list names exactly the data files that a rented machine needs for each job. Upload nothing else.

Rules:
- **Upload only data whose licence allows a copy.** Every file below is checked. CC0 data has no conditions. CC BY data needs attribution only (the repository already gives it).
- **No participant identifiers.** The public datasets use code names (T15, T5). Session file names are recording dates, which the public datasets already publish. No file below holds names, contact data or clinical records.
- **No secrets.** Do not put tokens, keys, passwords or e-mail addresses in any uploaded file or in the repository. Use an SSH key pair that stays on your own computer.
- **Code comes from the public repository** (`git clone`), not from an upload.
- **Delete everything at the end** (the rented disk and any snapshot), see the README.

Sizes are from the local disk on 2026-11-23.

## Job 1: speed test and the calibration hold-out retrain (GPU part)

| local path (Windows) | upload to (example) | size | licence | why |
|---|---|---|---|---|
| `C:\Users\zhang\bci-data\derived\m4-01-02-lookahead\t15.*.npz` (45 files) | `/data/t15-derived/` | 8.58 GB | CC0 1.0 (derived from B2T '25, Card et al. 2024) | binned neural features + phoneme ids per trial |
| `C:\Users\zhang\bci-data\derived\m4-01-02-lookahead\sessions.json` | `/data/t15-derived/` | 1 KB | CC0 1.0 | session order |
| `C:\Users\zhang\bci-data\derived\m4-01-02-lookahead\texts.json` | `/data/t15-derived/` | 0.3 MB | CC0 1.0 | sentence texts (needed by the hold-out rule) |

Do **not** upload the other files in that folder (`params-*.npz`, `decode-*.json`, `logprobs-*.npz`, `run-acc.*`): they belong to other experiments and the jobs do not read them.

The split file of the hold-out (`split.json`, keys only) is made on the rented machine by `holdout.py write`; it needs only the three items above.

## Job 2: self-teaching replay on T15 (GPU + CPU)

Everything of job 1, plus the word route for decoding (CPU):

| local path | size | licence | why |
|---|---|---|---|
| `C:\Users\zhang\bci-data\lexicon\cmudict\` (`cmudict.dict`, `LICENSE`, `README`, `COMMIT`) | 3.6 MB | CMUdict licence (BSD-style, see its `LICENSE`) | phonemes of label texts |
| `C:\Users\zhang\bci-data\lm\eng_tatoeba_6gram_mkn.npz` | 3.4 MB | CC BY 2.0 FR (Tatoeba) | char LM of the word route |
| `C:\Users\zhang\bci-data\lm\eng_tatoeba_word_counts.json` | 1.2 MB | CC BY 2.0 FR (Tatoeba) | word list of the lexicon |
| `C:\Users\zhang\bci-data\corpora\tatoeba\eng_sentences.tsv.bz2` | 25 MB | CC BY 2.0 FR (Tatoeba) | word LM source of the route |

Optional stage 2 (T12): `C:\Users\zhang\bci-data\derived\2026-11-13-confirmatory-t12-v2\t12.*.npz` (24 files, 3.10 GB) and its `texts.json`; CC0 1.0 (B2T '24).

## Job 3: cross-body transfer (prefer the local GPU)

| local path | size | licence | upload? |
|---|---|---|---|
| `C:\Users\zhang\bci-data\derived\p15-08\willett\` | 729 MB | CC0 1.0 (Willett 2021) | yes |
| `C:\Users\zhang\bci-data\derived\p11-01-emg-decoder\train\generic\best.pt` | 34 MB | **research only** (derived from CC BY-NC-SA 4.0 data) | only as a private copy for non-commercial research; never share or publish; delete after. Prefer the local GPU |
| `C:\Users\zhang\bci-data\derived\p15-08\text\final.pt` (+ `licence.json`) | 33 MB | **research only** (same) | same as the row above |
| T15 files of job 1 | 8.58 GB | CC0 1.0 | yes (implant trunk pretraining) |
| `C:\Users\zhang\bci-data\raw\kt-semg\` | 20 GB | CC BY 4.0 (Nokia) | yes, only after the licence-clean EMG trunk recipe exists |

## Never upload
- The emg2qwerty raw sessions (339 GB, non-commercial): no job needs them.
- SpanishBCBL MEG data (CC BY-NC 4.0): no job needs it.
- Any file under `C:\Users\zhang\bci-data\runs\` or another experiment's derived folder that is not named above.
- The LLM file (`qwen2.5-1.5b-instruct-q4_k_m.gguf`, Apache-2.0, 1.1 GB) is allowed but not needed: run the LLM rescoring stage on the local machine.
