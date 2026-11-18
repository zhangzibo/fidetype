# Lineage of decision `dec-000007-461459b3`

- Ledger `6c187f06-de1b-43d7-ac27-5d22a353b850`: chain verification **PASS** (80 entries, head `ab089109f35b900c…`).
- Licence flags: research_only **False**, commercial_ok True, product_ok project False / commercial True.

## 1. Output

- Entry 16 (`9f1c23f86b9bfdf4…`): action **COMMIT**, reason: p_top1 0.64 >= 0.60.
- Shown text: "they live with us".
- Word 0: 'they'; word choice: none (the word came with the whole text).
- Scores: p_top1 0.6406, set size 3, guard risk 0.1765.
- Input: stream `258ecced538fac9e…`, frames [0, 133], t [0.28, 10.84], item b2t25-test-trial-288, subject h:984a7f441ec319cc.

## 2. Corrections

- None.

## 3. Context (trust configuration)

- Entry 8: `ctx-525c24d0efdbc95ea92554df`; software fidetype 0.0.1.
- Decoder: card2024-online-rnn + fidetype PhonemeWordDecoder t15-copytask-online; words {"edit_penalty": 12.0, "lm_weight": 1.0, "word_bonus": 3.0}; LM tatoeba-eng-char-6gram-mkn + cmudict; adapter fidetype.adapters.b2t25.
- Calibration `cal-a7e6d7bec26ae084`: set b2t25-fit-subset-203-trials (every 4th of the per-day first half).
- Policy `pol-c2be66d727c60fb0`.

## 4. Artifacts (inputs first)

- Entry 6: **lm** tatoeba-eng-char-6gram-mkn + cmudict lexicon (`art-4c766fbc7e56e5648f15b6bd`); sha256 `616a201e4c846490…`; purpose research; from ['src-048884c67c879d0fff8d9923', 'src-f6166571540e8197b32969a8']; licences ['BSD-2-Clause', 'CC-BY-2.0-FR']; research_only False.
- Entry 5: **weights** card2024-online-rnn (published logits) t15-copytask-online (`art-671d796facc8c7708e17efe5`); sha256 `7313b9a1102794cf…`; purpose research; from ['src-9c859da1416b0c60e6ebd761']; licences ['CC0-1.0']; research_only False.
- Entry 7: **calibration** M6-06 plug-in gate fit (`art-fdc7f55a3c7fcf40b1db04e8`); sha256 —; purpose research; from ['art-4c766fbc7e56e5648f15b6bd', 'art-671d796facc8c7708e17efe5', 'src-9c859da1416b0c60e6ebd761']; licences ['BSD-2-Clause', 'CC-BY-2.0-FR', 'CC0-1.0']; research_only False.

## 5. Data sources

- Entry 4: CMUdict (`src-048884c67c879d0fff8d9923`); licence **BSD-2-Clause**; url https://github.com/cmusphinx/cmudict; digest `81917843c7f44ce2…`; research_only False.
- Entry 3: Tatoeba English sentences (`src-f6166571540e8197b32969a8`); licence **CC-BY-2.0-FR**; url https://tatoeba.org; digest `1a2d75ac07aa5d03…`; research_only False.
- Entry 2: Brain-to-Text '25, participant T15 copy task (`src-9c859da1416b0c60e6ebd761`); licence **CC0-1.0**; track b2t25-t15; url https://doi.org/10.5061/dryad.dncjsxm85; digest `7313b9a1102794cf…`; research_only False.

## 6. Entries of this lineage

| seq | kind | hash |
|---|---|---|
| 2 | source | `92373aadc68a92b9…` |
| 3 | source | `e6c67d8c7fd1c0af…` |
| 4 | source | `c20ffc3551206909…` |
| 5 | artifact | `4e26af629674be2e…` |
| 6 | artifact | `20b877f297172b7c…` |
| 7 | artifact | `04f370aa4e4f7dde…` |
| 8 | context | `728b4d2aa8ef4f68…` |
| 16 | decision | `9f1c23f86b9bfdf4…` |
