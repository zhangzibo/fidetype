# Language support: audit of English assumptions

Roadmap item: P14-34 (open gap 106). Status of this page: audit (phase 1) plus the first per-language config (phase 2, section 4).

All Fidetype results so far are English: T15, T12, Willett handwriting, emg2qwerty and KT-sEMG. The only non-English data is SpanishBCBL (Spanish MEG, research only), and our pipeline folds it into the English 28-symbol alphabet. This page lists each place where the code assumes English. For each place it gives the impact for four test languages, a proposed per-language config key, and the risk of a change.

## 1. Test languages

| Tag (BCP 47) | Language | Script | What is different from English |
|---|---|---|---|
| `es` | Spanish | Latin | Extra letters `ñ á é í ó ú ü`. Inverted marks `¿ ¡`. Words are separated by spaces. |
| `zh` | Mandarin | Han (simplified `zh-Hans`, traditional `zh-Hant`) | No spaces between words. Thousands of characters. Typing goes through an input method (pinyin keys, then a character choice). |
| `ar` | Arabic | Arabic | Right to left. Letters join (contextual forms). Short vowels are optional marks. Words are separated by spaces. Clitics join to words, so a "word" holds more meaning. |
| `hi` | Hindi | Devanagari | Vowel signs and conjuncts: one visible character (grapheme) is often two or more code points. Words are separated by spaces. |

## 2. How to read the table

- **Where**: file and line at commit `dd4a367` (2026-11-19).
- **Assumes**: the English assumption.
- **Impact**: what goes wrong for `es` / `zh` / `ar` / `hi`.
- **Config key**: the proposed field of the per-language config (`fidetype.lang.Language`, section 4). "manifest" = a key of the pretrained-model manifest; "guard" = a key of the saved trust guard.
- **Risk**: the risk of changing the code. **Low**: the change cannot move an English number. **Medium**: the change touches a scoring or trust path; English must be pinned by tests. **High**: the change touches adopted metric semantics, a spec rule or a committed result.
- **State**: `done` (phase 2 threads it), `proposal` (a follow-up item does it), `ok` (no English assumption; listed for completeness).

## 3. Audit table

### 3.1 Character set, vocabulary and normalisation

| # | Where | Assumes | Impact (es / zh / ar / hi) | Config key | Risk | State |
|---|---|---|---|---|---|---|
| A1 | `src/fidetype/streams/vocab.py:30-34` (`LETTERS`, `VOCAB`) | The CTC alphabet is blank + `a`-`z` + space (28 classes, `char.b2q-28`) | es: `ñ` becomes `n`, so "año" and "ano" are the same string. zh / ar / hi: every letter is outside the set, so all text maps to spaces | `Language.letters`, `Language.vocab` | High (every char decoder and committed result uses it) | done: `en` reuses `VOCAB` unchanged; `es` has its own 37-class vocabulary |
| A2 | `src/fidetype/streams/vocab.py:41-66` (`normalize_text`) | Lower case, NFKD, remove every combining mark, keep `a`-`z` | es: removes the accents that change meaning (`sí` / `si`). hi: removes the vowel signs (they are combining marks), so the words break. ar: removes the letters. zh: removes all characters | `Language.normalize` | High (split hashes, LM training text and scores use it) | done: `en.normalize` calls this function; `es.normalize` keeps the Spanish letters |
| A3 | `src/fidetype/adapters/b2t25.py:141-148` (`normalize_words`) | Keep `a`-`z` and `'` | Same as A2. The apostrophe rule is English (`that's`) | `Language.normalize` (word mode) | Medium (T15 track normaliser `words`) | proposal (follow-up P14-38) |
| A4 | `src/fidetype/lm/llm.py:58-61` (`normalize_text`) | Keep `a`-`z` and `'` | Same as A3 | `Language.normalize` (word mode) | Medium (P15-05 LLM rescoring) | proposal (P14-40) |
| A5 | `src/fidetype/benchmark/registry.py:261-297` (`normalize`, `_KEY_CHARS`) | Track normalisers `char28`, `words`, `keycodes` (US key codes `KeyA`-`KeyZ`) | The SpanishBCBL track is `language="es"` but uses `char28`, so the scorer compares accent-folded text. Key codes are US QWERTY; a Spanish keyboard has a `ñ` key (`Semicolon` position) | `Language.normalize`; track field `language` already exists | High (benchmark scorer; P11-13 edits this area now) | proposal (P14-38) |
| A6 | `src/fidetype/streams/vocab.py:89-104` (`KEY_POS`) | ANSI US QWERTY geometry for the simulator | es: ISO Spanish layout (extra `ñ`, dead-key accents). zh: pinyin on QWERTY plus a candidate choice. ar / hi: other layouts | `Language.keyboard` (layout id) | Low (simulator only) | proposal (P14-40) |
| A7 | `src/fidetype/streams/simulator.py:71-103` (`LETTER_FREQ`, `chars_per_min = 152.0`) | English letter frequencies (Lewand 2000) set the error model | Wrong confusion statistics for any other language | `Language.letter_freq` | Low (synthetic data only) | proposal (P14-40) |
| A8 | `src/fidetype/streams/corpus.py:1` | English demo and test sentences | Demos stay English | `Language.demo_corpus` | Low | proposal (P14-40) |
| A9 | `src/fidetype/data/spanishbcbl.py:702`, `:765`; `src/fidetype/data/preprocess.py:116` | Spanish targets go through the English `normalize_text` | The SpanishBCBL cache and its split hash fold accents | `Language.normalize` | High (the split rule hashes this text; committed M1 results) | ok for now: keep for the v0.1 track; a Spanish-config track is P15-30's job (gap 107) |
| A10 | `src/fidetype/trust/dropin.py:377-381` (`_norm_text`), `src/fidetype/trust/types.py:155`, `src/fidetype/benchmark/hallucination.py:307` | `" ".join(t.split())`: join white space | ok for es / ar / hi. Python `str.split()` uses Unicode white space (spec 2, "White space"). zh: no change needed (no spaces) | — | — | ok |

### 3.2 Words, word counts and rates

| # | Where | Assumes | Impact (es / zh / ar / hi) | Config key | Risk | State |
|---|---|---|---|---|---|---|
| B1 | `src/fidetype/benchmark/safe_wpm.py:16`, `:162`, `:586-587` (`words(y)`, `prefix_outcome`, `load_trials_jsonl`) | A word is a run of characters between spaces | es / hi: ok. ar: a clitic-joined word holds more meaning, so WPM is not comparable with English. zh: `len(text.split())` gives about 1 word per sentence, a silent wrong number | `Language.word_segmentation` (`spaces` / `none`), `Language.words()` | High (adopted safe-WPM v0.1; P15-29 edits this file now) | proposal (P14-38); the hook is ready (`fidetype.lang.wpm_counts`, section 4.3) |
| B2 | `src/fidetype/benchmark/safe_wpm.py:119-120` (`DEFAULT_S_PER_CHAR = 2 * 60 / 152`, `GAZE_CHARS_PER_MIN = 20`) | The correction time and the no-BCI gaze rate (`aac-gaze-v1`) in characters per minute | 152 chars/min is the Brain2Qwerty v1 typing rate (Spanish participants). 20 chars/min is one English ALS gaze user ([Cai24]). A character is not the same unit of work in zh (one Han character = several pinyin keys + a choice) or hi (one grapheme = several code points) | `Language.correction_chars_per_min`, `Language.gaze_chars_per_min`, `Language.rates_source` | High (adopted v0.1 constants) | proposal (P14-38); `en` and `es` carry the current values as data |
| B3 | `src/fidetype/interact/simulated_user.py:21`, `:165`, `:268`, `:279-283`, `:294` | Same rates; reading time per word by `split()` | Same as B1, B2 | Same as B1, B2 | Medium (eWPM simulator) | proposal (P14-38) |
| B4 | `src/fidetype/benchmark/registry.py:59`, `:177-190`; `src/fidetype/benchmark/scorecard.py:125`, `:141`; `src/fidetype/benchmark/scoring.py:138`, `:161` | `aac-gaze-v1 @ 152 chars/min`; WER by `split()`; gaze time `nchar * 60 / gaze_cpm` | Same as B1, B2 | Same as B1, B2 | High (benchmark scorer; P11-13 edits it) | proposal (P14-38) |
| B5 | `src/fidetype/eval/metrics.py:54`, `src/fidetype/eval/ewpm.py:125`, `:139`, `:207`, `src/fidetype/eval/harness.py:504` | WER and word counts by `split()` | zh: WER is not defined without a segmenter (use CER) | `Language.word_segmentation` | Medium | proposal (P14-38) |
| B6 | `src/fidetype/trust/provenance.py:575-577` (`n_words`) | Audit record counts words by `split()` | zh: wrong count in the audit record (audit data only) | `Language.words()` | Low (audit only) | proposal (P14-38) |
| B7 | `src/fidetype/benchmark/hallucination.py:41`, `:431`; `src/fidetype/trust/halluc_bound.py:184`, `:235`, `:471` | Fluency = `log p_LLM(text) / words`, words by `split()` | zh: one "word" per sentence makes the per-word log-prob very low, so nothing counts as fluent (the bound becomes too optimistic). Use per-character or per-token normalisation | `Language.fluency_unit` | High (hallucination protocol 0.2) | proposal (P14-38) |
| B8 | `src/fidetype/trust/stream_commit.py:463`, `src/fidetype/trust/testing.py:288`, `src/fidetype/lm/beam.py:866`, `:880`, `src/fidetype/trust/dropin.py:452` (lexicon filter) | Word prefixes and lexicon checks by `split()` | zh: a prefix commit (P5-24) needs a segmenter | `Language.words()` | Medium | proposal (P14-38) |

### 3.3 Language models, lexicons and prompts

| # | Where | Assumes | Impact | Config key | Risk | State |
|---|---|---|---|---|---|---|
| C1 | `src/fidetype/lm/ngram.py:67-83` (`_LUT` over `VOCAB`, `N_OUT = 28`) | The char n-gram LM has exactly the 28 English symbols, indexed by byte | es: `ñ` and accented letters are not bytes (UTF-8 has 2 bytes), so the LM cannot hold them. zh / ar / hi: impossible | `Language.vocab` (LM symbol table) | Medium (all M1 LM results use it) | proposal (P14-40) |
| C2 | `src/fidetype/lm/corpora.md`; `src/fidetype/benchmark/registry.py:163-171` (`tatoeba-eng`) | English Tatoeba training text | Needs a corpus per language (Tatoeba has `spa`, `cmn`, `ara`, `hin`; CC BY 2.0 FR) | `Language.lm_corpus` | Low (data choice) | proposal (P14-40) |
| C3 | `src/fidetype/lm/phoneme_words.py:200-225` (CMUdict reader) | English pronunciations (ARPAbet) | No CMUdict for other languages; needs a per-language lexicon (for es a rule-based grapheme-to-phoneme is enough) | `Language.lexicon` | Medium | proposal (P14-40) |
| C4 | `src/fidetype/adapters/b2t25.py:70`, `:85` (ARPAbet 39 + silence, `phoneme.arpabet-39-sil`) | English phoneme inventory | A T15-style decoder for another language needs another inventory (IPA subset) | manifest `output.vocab_id` | Medium | ok (a vocabulary id already names it); new inventories go with new decoders |
| C5 | `src/fidetype/lm/llm.py:33`, `:38`, `:186` | LLM prompts say "one English sentence" | The LLM rescoring is biased to English output | `Language.llm_prompt_name` (the language name in the prompt) | Medium (P15-05 results) | proposal (P14-40) |
| C6 | `src/fidetype/trust/grounding.py` (`GroundingCheck`, `label_fn`) | No assumption in the module: the caller gives `label_fn`. Our label functions use CMUdict (C3) | Language enters only through `label_fn` | — | — | ok |

### 3.4 Streams, manifests, trust config, spec and SDKs

| # | Where | Assumes | Impact | Config key | Risk | State |
|---|---|---|---|---|---|---|
| D1 | `src/fidetype/pretrained/__init__.py:390`, `:477` | `language="en"` written by hand in the decoder info | A model for another language would write the wrong tag | manifest `language` (BCP 47) | Low | done: the runtimes write `manifest.language` (default `en`) |
| D2 | `src/fidetype/pretrained/manifest.py:198-226` (`parse_manifest`) | No language key | A user cannot see the language of a model | manifest `language` | Low | done: optional key, checked as a BCP 47 tag; absent = `en` |
| D3 | `src/fidetype/trust/dropin.py:937-945`, `:1033-1062` (guard file) | No language key in the saved guard | A guard calibrated on English could run on Spanish text with no warning | guard `language` | Low (written only if not `en`, so English guard files stay byte-identical) | done |
| D4 | `src/fidetype/writer.py:59`, `src/fidetype/adapters/ctc_logits.py:389`, `:570` | Default `language="en"` | ok: callers can pass any tag | — | — | ok |
| D5 | `src/fidetype/adapters/b2t25.py:376` | Writes `language = "en-US"`; the pretrained runtime writes `en` | Two tags for the same data; both resolve to `en` | — | Low | ok (`fidetype.lang.get("en-US")` gives `en`) |
| D6 | `spec/nts-1.0-rc4.md:325` (meta `language`, BCP 47), `:993-996` (`TR-LANGUAGE`) | ok: the spec already asks for the language of text vocabularies | — | — | — | ok |
| D7 | `spec/nts-1.0-rc4.md:238`, `:290`; `src/fidetype/conformance/checks.py:245`; `sdk/typescript/src/checks.ts:138`; `sdk/rust/src/checks.rs:912`, `sdk/rust/src/constants.rs:62` | The only registered `vocab_id` is `char.b2q-28` | A Spanish vocabulary has no registered id, so `NTS-VOCAB-ID` cannot check it | registry entry per language (for example `char.es-37`) | High (spec registry 12.4; needs a FEP and all three SDKs) | proposal (P14-40) |
| D8 | `src/fidetype/conformance/checks.py:702-708` (`NTS-VT-CHAR`) | A `char` token is one code point | hi: a visible character (grapheme cluster, for example `क्ष`) is 3 code points. A vocabulary of graphemes fails the check. es / ar / zh: ok at code-point level | spec text (code point vs. grapheme) | High (spec rule) | proposal (P14-40) |
| D9 | `spec/nts-1.0-rc4.md:77` (white space = Python `str.isspace`) | ok: Unicode white space | — | — | — | ok |
| D10 | Text fields in the spec (`text`, `intent`, `offered`) | ok: UTF-8 strings (GEN-2). No direction mark rule | ar: a mixed right-to-left / left-to-right text has no rule for Unicode bidi marks. Display is the job of the UI | — | Low | proposal (P14-35 UI) |
| D11 | `src/fidetype/demo/page.py:174`, `src/fidetype/demo/live/web/index.html:2`, `src/fidetype/benchmark/leaderboard.py:370`, `:547` | `<html lang="en">` | The page language is right (English UI). The decoded text in the page needs `lang` and `dir` attributes for ar | — | Low | proposal (P14-35 UI) |

## 4. Phase 2: the per-language config (`fidetype.lang`)

### 4.1 What it is

`src/fidetype/lang.py` holds a `Language` object and a registry. A language has:

| Field | `en` (default) | `es` | `zh` (stub) |
|---|---|---|---|
| `tag` | `en` | `es` | `zh` |
| `letters` | `a`-`z` | `a`-`z` `á é í ó ú ü ñ ¿ ¡` | none (no closed set) |
| `vocab` | `streams.vocab.VOCAB` (28, same object) | blank + 35 symbols + space (37) | none |
| `vocab_id` | `char.b2q-28` | none (not registered, D7) | none |
| `normalize` | `streams.vocab.normalize_text` (same function) | lower case, keep the Spanish letters, fold other accents (`à` → `a`), other characters → space | NFKC, join white space |
| `word_segmentation` | `spaces` | `spaces` | `none` |
| `correction_chars_per_min` | 152.0 | 152.0 (provisional: copied from `en`) | none |
| `gaze_chars_per_min` | 20.0 | 20.0 (provisional: copied from `en`) | none |
| `status` | `reference` | `provisional` | `stub` |

`fidetype.lang.get(tag)` resolves a BCP 47 tag: exact match first, then the primary subtag (`en-US` → `en`, `es-419` → `es`, `zh-Hans-CN` → `zh`). An unknown tag raises `KeyError`. `fidetype.lang.register()` adds a language.

### 4.2 English stays bit-identical

The `en` entry does not copy the English rules. It calls the existing objects (`VOCAB`, `normalize_text`, `str.split`). Tests in `tests/test_lang.py` pin the current outputs:

- the 28-symbol charset and `vocab is VOCAB`;
- `normalize_text` on a committed list of hard strings (`tests/fixtures/lang/normalize_en.json`);
- safe WPM v0.1 on a committed fixture of 40 trials (`tests/fixtures/lang/safe_wpm_en.json`): `point`, `ci95`, `no_bci_wpm` and the word and character counts are equal (`==`, not approximately) to the values that commit `dd4a367` gives;
- the guard file of an English guard has no `language` key, and the packaged manifests load with `language == "en"`.

### 4.3 Words per minute without spaces

`Language.words(text)` and `fidetype.lang.wpm_counts(texts, lang)` give the word and character counts that `safe_wpm()` takes as input (`n_words`, `n_chars`). For a language with `word_segmentation = "none"` (Mandarin):

- `words()` and `wpm_counts(..., on_undefined="raise")` raise `WordsNotDefinedError` with the reason;
- `wpm_counts(..., on_undefined="report")` returns `{"defined": False, "reason": ...}` and no counts.

The reason: a Mandarin sentence has no spaces between words. Splitting at spaces gives about one "word" per sentence. A proper definition needs either a fixed word segmenter (and its version in the score card) or a characters-per-minute metric with a cross-language conversion. This is follow-up P14-39.

### 4.4 Where the config is threaded now (low risk)

| Place | Change | English effect |
|---|---|---|
| `fidetype.pretrained` manifest | optional `language` key (BCP 47, must resolve in the registry); `Manifest.language` (default `en`); both runtimes write it into the stream meta | none: no packaged manifest changed, and `en` is the old hand-written value |
| `fidetype.trust` guard | `calibrate(..., language="en")`, `TrustGuard.language`, `load()` reads it; the file has the key only when it is not `en` | none: English guard files are byte-identical |
| safe-WPM inputs | `fidetype.lang.wpm_counts` computes `n_words`, `n_chars` before `safe_wpm()` | none: same `split()` and `len()` as `load_trials_jsonl` |

## 5. Proposals for files that other work owns now

These files were in active edits by other items during P14-34 (P15-29: `safe_wpm.py`, `docs/safe-wpm.md`, `tests/test_safe_wpm.py`; P11-13: the benchmark scorer and track docs). P14-34 did not change them. Follow-up P14-38 does the changes below after those items commit.

1. **`safe_wpm.py`**: `load_trials_jsonl(path, language="en")` and `prefix_outcome(..., language="en")` call `fidetype.lang.get(language).words()` in place of `str.split()`. `safe_wpm(..., language=None)`: if given and the language has no word segmentation, return a refusal (`status = "not-defined"`, with the reason) in place of a number. The defaults of `DEFAULT_S_PER_CHAR` and `GAZE_CHARS_PER_MIN` stay; the score card reports `language` and `rates_source`. English output stays bit-identical (pin with `tests/fixtures/lang/safe_wpm_en.json`).
2. **`docs/safe-wpm.md`**: one paragraph: "`words(y)` is defined only for languages that separate words with spaces (`word_segmentation = spaces`). For other languages safe WPM is not defined (P14-39)."
3. **Benchmark registry and scorer** (`registry.py`, `scoring.py`, `scorecard.py`): a track normaliser `lang:<tag>` that calls `Language.normalize`; WER and `n_w` through `Language.words()`; the user model takes its rates from the language. The existing tracks keep `char28` / `words` / `keycodes`.
4. **Hallucination protocol**: fluency normalised per word only for `word_segmentation = spaces`; per character otherwise (`Language.fluency_unit`).

## 6. Follow-ups

| Item | Gap | What |
|---|---|---|
| P14-38 | 117 | Language hook in safe WPM, the benchmark scorer, the eWPM simulator and the hallucination fluency unit (section 5). English bit-identical |
| P14-39 | 118 | A words-per-minute definition for scripts without spaces (Mandarin, Japanese, Thai): word segmenter or characters per minute |
| P14-40 | 119 | Per-language models and registries: char LM symbol tables beyond bytes, lexicons and grapheme-to-phoneme, LLM prompts, simulator letter frequencies and layouts, registered `vocab_id`s per language and the `NTS-VT-CHAR` grapheme rule (FEP) |
| P15-30 (existing) | 107 | Spanish trust result on SpanishBCBL with the `es` config |

## 7. Limits

- The `es` rates (152 and 20 chars/min) are copies of the English values. No source gives a Spanish gaze-typing rate here. A Spanish no-BCI reference needs data (P15-30).
- `zh` is a stub: it exists so that a Mandarin tag fails loudly, not silently. It has no vocabulary and no normaliser beyond NFKC.
- `ar` and `hi` are not registered. Section 3 gives their impact.
