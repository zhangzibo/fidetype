# LM training corpora: provenance

This note records the source, licence, size and date of each text corpus that trains a `CharNgramLM`.
The raw files and the trained models are **outside the repo** (`C:\Users\zhang\bci-data\`). They are not committed.
The script `experiments/2026-11-08-lm-beam/build_lms.py` rebuilds everything from the raw files.

## Corpora

| Corpus | Source URL | Licence | Downloaded | Raw file (bytes, SHA-256) | Sentences (unique, normalised) |
|---|---|---|---|---|---|
| Tatoeba English | https://downloads.tatoeba.org/exports/per_language/eng/eng_sentences.tsv.bz2 | CC BY 2.0 FR (Tatoeba default; some sentences CC0) | 2026-11-08 | `corpora/tatoeba/eng_sentences.tsv.bz2` (24 933 870, `1a2d75ac…cc9ef6020`) | 2 032 357 |
| Tatoeba Spanish | https://downloads.tatoeba.org/exports/per_language/spa/spa_sentences.tsv.bz2 | CC BY 2.0 FR (Tatoeba default; some sentences CC0) | 2026-11-08 | `corpora/tatoeba/spa_sentences.tsv.bz2` (6 374 211, `7bbafb2a…22d9fbe7`) | 439 445 |

- Licence terms: https://tatoeba.org/en/terms_of_use (checked 2026-11-08). The default sentence licence is CC BY 2.0 FR. Re-use needs attribution to the authors.
- Attribution: "Sentences from Tatoeba (https://tatoeba.org), by the Tatoeba contributors, CC BY 2.0 FR."
- We do not redistribute the sentences. A trained model holds n-gram statistics of the text. If we publish a model, we will give the attribution above with it.

## Processing

1. Read column 3 of the TSV. Normalise with `fidetype.streams.vocab.normalize_text` (lower case, accents folded, other characters become a space). Drop empty and duplicate sentences.
2. Shuffle with seed 20261108.
3. Remove the blocklist sentences (see below), with `fidetype.lm.ngram.exclude_sentences`.
4. Keep the first 5 000 sentences as a held-out set. The benchmark draws its dev and test sentences from this held-out set only.
5. Train on the rest. English: the first 600 000 sentences (23.4 M characters), to limit memory. Spanish: all 434 443 (17.0 M characters).

## Test-set exclusion (leak guard)

| Model | Blocklist | Rule | Removed |
|---|---|---|---|
| English | the 2 000 sentences of `fidetype.streams.corpus.sentences(2000)` | exact match after normalisation | 10 |
| Spanish | the 226 SpanishBCBL target sentences | exact match, and any corpus sentence that contains a target (or is contained in one), for strings of 15+ characters | 2 |

- The SpanishBCBL targets come from the 84 experiment logs `SpanishBCBL/MEG/logs/*.mat`: fields `pr_trials.sequence` (all trials, with the training trials) and `pr_trials.sequences`. All 84 files loaded. The list is in `C:\Users\zhang\bci-data\lm\spanishbcbl_blocklist.txt` (normalised, 226 lines).
- The sidecar JSONs in `C:\Users\zhang\bci-data\cache\spanishbcbl\v1\` did not exist on 2026-11-08. `build_lms.py` also reads them if they exist. Re-run it after the cache is built, and check that the blocklist does not grow.
- Exact and substring matching does not catch paraphrases. The SpanishBCBL perplexity (3.78) is above the Tatoeba held-out perplexity (3.45), so there is no sign of a leak.

## Models

| File (`C:\Users\zhang\bci-data\lm\`) | Order | Smoothing | Size | Held-out perplexity (per symbol, 2 000 sentences) |
|---|---|---|---|---|
| `eng_tatoeba_6gram_mkn.npz` | 6 | interpolated modified KN | 3.4 MB | 3.16 (unigram: 18.1) |
| `spa_tatoeba_6gram_mkn.npz` | 6 | interpolated modified KN | 2.6 MB | 3.45 (unigram: 16.9); SpanishBCBL targets: 3.78 |

Each `.npz` file holds its provenance in `header_json["meta"]`. `build_report.json` in the same folder holds the full numbers.

## Known limits

- Tatoeba sentences are short and conversational. Many are near-duplicates ("tom is ..."). The held-out perplexity is therefore optimistic for other text.
- Apostrophes become spaces (`don't` becomes `don t`). This follows `normalize_text`.
- Brain2Qwerty used larger corpora (v1: Spanish Wikipedia, 9-gram; v2: WikiText-103, 6-gram). Wikipedia is CC BY-SA. We did not use it.
