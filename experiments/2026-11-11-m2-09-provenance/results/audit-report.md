# Provenance audit report

- Ledger id: `47b88a82-0a00-4e66-b4e8-b0cc5583c9d3`; schema `fidetype.provenance/0.1`; text mode `store`; id mode `hash`.
- Entries: 1723; head seq 1722; head hash `906bb70598ca4767efd04bd134466e1ea747cd4220b9d503f90a6d2ed34624ea`.
- Chain verification: **PASS**.

## Summary per decoder / calibration / policy version

| decoder.name | decoder.version | calibration.id | policy.version | decisions | commits | wrong commits | wrong-commit rate | commit precision | actions |
|---|---|---|---|---|---|---|---|---|---|
| card2024-online-rnn + fidetype PhonemeWordDecoder | t15-copytask-online; words {"edit_penalty": 12.0, "lm_weight": 1.0, "word_bonus": 3.0} | cal-692fb52a73417552 | pol-2eaa4ff51919527a | 816 | 189 | 48 | 0.0588 | 0.7460 | COMMIT 189, OFFER 627 |
| card2024-online-rnn + fidetype PhonemeWordDecoder | t15-copytask-online; words {"edit_penalty": 12.0, "lm_weight": 1.0, "word_bonus": 3.0} | cal-e6a13a7844c815a6 | pol-92a5150a77905417 | 816 | 160 | 39 | 0.0478 | 0.7562 | COMMIT 160, OFFER 656 |

## Wrong commits (87)

The first 15 of 87 are shown.

### `dec-000041-ed60b4bd` (entry 44, hash `8cf2c6c67053b185…`)
- Committed: "who you never expect to when"
- Correction (oracle-ground-truth, entry hash-linked): "who you never expect to win"; char edits 2, word edits 1
- Scores: p_top1 0.5814, set size 3, guard risk 0.2857; reason: p_top1 0.58 >= 0.50
- Input: stream `1b4b60e8e4950710…`, source b2t25-copytask, frames [0, 335], t [0.28, 27.0], attempt 0, item b2t25-test-trial-196
- Decoder: card2024-online-rnn + fidetype PhonemeWordDecoder t15-copytask-online; words {"edit_penalty": 12.0, "lm_weight": 1.0, "word_bonus": 3.0}; weights `None`; LM tatoeba-eng-char-6gram-mkn + tatoeba word unigram + cmudict; adapter fidetype.adapters.b2t25
- Calibration `cal-692fb52a73417552`: T_frame 3.7809, T_sentence 4.5551, risk control none (α None, δ None, threshold None), set b2t25-fit-half-812-trials (per-day first half, file order)
- Policy `pol-2eaa4ff51919527a`: commit_p 0.5, commit_max_risk 0.5, offer_max_k 2

### `dec-000049-ded8e04f` (entry 53, hash `983824d8aeefe751…`)
- Committed: "every major city has a"
- Correction (oracle-ground-truth, entry hash-linked): "every major city has a theater"; char edits 8, word edits 1
- Scores: p_top1 0.6731, set size 2, guard risk 0.3182; reason: p_top1 0.67 >= 0.50
- Input: stream `3f75f179bbd66c6f…`, source b2t25-copytask, frames [0, 314], t [0.28, 25.32], attempt 0, item b2t25-test-trial-204
- Decoder: card2024-online-rnn + fidetype PhonemeWordDecoder t15-copytask-online; words {"edit_penalty": 12.0, "lm_weight": 1.0, "word_bonus": 3.0}; weights `None`; LM tatoeba-eng-char-6gram-mkn + tatoeba word unigram + cmudict; adapter fidetype.adapters.b2t25
- Calibration `cal-692fb52a73417552`: T_frame 3.7809, T_sentence 4.5551, risk control none (α None, δ None, threshold None), set b2t25-fit-half-812-trials (per-day first half, file order)
- Policy `pol-2eaa4ff51919527a`: commit_p 0.5, commit_max_risk 0.5, offer_max_k 2

### `dec-000059-12fed7ce` (entry 64, hash `8f9aced9994d4437…`)
- Committed: "i was pretty shocked it that"
- Correction (oracle-ground-truth, entry hash-linked): "i was pretty shocked at that"; char edits 1, word edits 1
- Scores: p_top1 0.5712, set size 1, guard risk 0.3214; reason: p_top1 0.57 >= 0.50
- Input: stream `a64665622454c0a9…`, source b2t25-copytask, frames [0, 320], t [0.28, 25.8], attempt 0, item b2t25-test-trial-214
- Decoder: card2024-online-rnn + fidetype PhonemeWordDecoder t15-copytask-online; words {"edit_penalty": 12.0, "lm_weight": 1.0, "word_bonus": 3.0}; weights `None`; LM tatoeba-eng-char-6gram-mkn + tatoeba word unigram + cmudict; adapter fidetype.adapters.b2t25
- Calibration `cal-692fb52a73417552`: T_frame 3.7809, T_sentence 4.5551, risk control none (α None, δ None, threshold None), set b2t25-fit-half-812-trials (per-day first half, file order)
- Policy `pol-2eaa4ff51919527a`: commit_p 0.5, commit_max_risk 0.5, offer_max_k 2

### `dec-000062-a8d7e08b` (entry 68, hash `4bc989a0e3b41cdb…`)
- Committed: "it's not like him going home"
- Correction (oracle-ground-truth, entry hash-linked): "it's not like i'm going home"; char edits 2, word edits 1
- Scores: p_top1 0.7004, set size 2, guard risk 0.0447; reason: p_top1 0.70 >= 0.50
- Input: stream `b6340389dfca0ce8…`, source b2t25-copytask, frames [0, 283], t [0.28, 22.84], attempt 0, item b2t25-test-trial-217
- Decoder: card2024-online-rnn + fidetype PhonemeWordDecoder t15-copytask-online; words {"edit_penalty": 12.0, "lm_weight": 1.0, "word_bonus": 3.0}; weights `None`; LM tatoeba-eng-char-6gram-mkn + tatoeba word unigram + cmudict; adapter fidetype.adapters.b2t25
- Calibration `cal-692fb52a73417552`: T_frame 3.7809, T_sentence 4.5551, risk control none (α None, δ None, threshold None), set b2t25-fit-half-812-trials (per-day first half, file order)
- Policy `pol-2eaa4ff51919527a`: commit_p 0.5, commit_max_risk 0.5, offer_max_k 2

### `dec-000087-0c5aa0ea` (entry 94, hash `4715cbafc08739e0…`)
- Committed: "we try to do one thing was a year"
- Correction (oracle-ground-truth, entry hash-linked): "we try to do one thing once a year"; char edits 4, word edits 1
- Scores: p_top1 0.6482, set size 2, guard risk 0.1515; reason: p_top1 0.65 >= 0.50
- Input: stream `0c3d6a71267f3e48…`, source b2t25-copytask, frames [0, 235], t [0.28, 19.0], attempt 0, item b2t25-test-trial-291
- Decoder: card2024-online-rnn + fidetype PhonemeWordDecoder t15-copytask-online; words {"edit_penalty": 12.0, "lm_weight": 1.0, "word_bonus": 3.0}; weights `None`; LM tatoeba-eng-char-6gram-mkn + tatoeba word unigram + cmudict; adapter fidetype.adapters.b2t25
- Calibration `cal-692fb52a73417552`: T_frame 3.7809, T_sentence 4.5551, risk control none (α None, δ None, threshold None), set b2t25-fit-half-812-trials (per-day first half, file order)
- Policy `pol-2eaa4ff51919527a`: commit_p 0.5, commit_max_risk 0.5, offer_max_k 2

### `dec-000095-4d007147` (entry 103, hash `f384b064228863f8…`)
- Committed: "why are our prisons"
- Correction (oracle-ground-truth, entry hash-linked): "why are our prisons overcrowded"; char edits 12, word edits 1
- Scores: p_top1 0.6323, set size 3, guard risk 0.4211; reason: p_top1 0.63 >= 0.50
- Input: stream `6baf49c2a43c963f…`, source b2t25-copytask, frames [0, 147], t [0.28, 11.96], attempt 0, item b2t25-test-trial-299
- Decoder: card2024-online-rnn + fidetype PhonemeWordDecoder t15-copytask-online; words {"edit_penalty": 12.0, "lm_weight": 1.0, "word_bonus": 3.0}; weights `None`; LM tatoeba-eng-char-6gram-mkn + tatoeba word unigram + cmudict; adapter fidetype.adapters.b2t25
- Calibration `cal-692fb52a73417552`: T_frame 3.7809, T_sentence 4.5551, risk control none (α None, δ None, threshold None), set b2t25-fit-half-812-trials (per-day first half, file order)
- Policy `pol-2eaa4ff51919527a`: commit_p 0.5, commit_max_risk 0.5, offer_max_k 2

### `dec-000118-dbeeb502` (entry 127, hash `bf79bc4f0aacc23a…`)
- Committed: "i saw something the other not about it"
- Correction (oracle-ground-truth, entry hash-linked): "i saw something the other night about it"; char edits 3, word edits 1
- Scores: p_top1 0.5925, set size 2, guard risk 0.1316; reason: p_top1 0.59 >= 0.50
- Input: stream `e2784614f669e457…`, source b2t25-copytask, frames [0, 238], t [0.28, 19.240000000000002], attempt 0, item b2t25-test-trial-379
- Decoder: card2024-online-rnn + fidetype PhonemeWordDecoder t15-copytask-online; words {"edit_penalty": 12.0, "lm_weight": 1.0, "word_bonus": 3.0}; weights `None`; LM tatoeba-eng-char-6gram-mkn + tatoeba word unigram + cmudict; adapter fidetype.adapters.b2t25
- Calibration `cal-692fb52a73417552`: T_frame 3.7809, T_sentence 4.5551, risk control none (α None, δ None, threshold None), set b2t25-fit-half-812-trials (per-day first half, file order)
- Policy `pol-2eaa4ff51919527a`: commit_p 0.5, commit_max_risk 0.5, offer_max_k 2

### `dec-000139-d7a2c523` (entry 149, hash `4ef375bcf1478fc6…`)
- Committed: "i was read around guns"
- Correction (oracle-ground-truth, entry hash-linked): "i was raised around guns"; char edits 4, word edits 1
- Scores: p_top1 0.5057, set size 2, guard risk 0.5000; reason: p_top1 0.51 >= 0.50
- Input: stream `a747d600ad6a54c6…`, source b2t25-copytask, frames [0, 140], t [0.28, 11.4], attempt 0, item b2t25-test-trial-400
- Decoder: card2024-online-rnn + fidetype PhonemeWordDecoder t15-copytask-online; words {"edit_penalty": 12.0, "lm_weight": 1.0, "word_bonus": 3.0}; weights `None`; LM tatoeba-eng-char-6gram-mkn + tatoeba word unigram + cmudict; adapter fidetype.adapters.b2t25
- Calibration `cal-692fb52a73417552`: T_frame 3.7809, T_sentence 4.5551, risk control none (α None, δ None, threshold None), set b2t25-fit-half-812-trials (per-day first half, file order)
- Policy `pol-2eaa4ff51919527a`: commit_p 0.5, commit_max_risk 0.5, offer_max_k 2

### `dec-000144-4aa6c220` (entry 155, hash `0511208039a0689a…`)
- Committed: "is this some sort of a decision"
- Correction (oracle-ground-truth, entry hash-linked): "is this some sort of a disease"; char edits 6, word edits 1
- Scores: p_top1 0.7267, set size 2, guard risk 0.2903; reason: p_top1 0.73 >= 0.50
- Input: stream `18f8e1dc96f28f51…`, source b2t25-copytask, frames [0, 197], t [0.28, 15.96], attempt 0, item b2t25-test-trial-405
- Decoder: card2024-online-rnn + fidetype PhonemeWordDecoder t15-copytask-online; words {"edit_penalty": 12.0, "lm_weight": 1.0, "word_bonus": 3.0}; weights `None`; LM tatoeba-eng-char-6gram-mkn + tatoeba word unigram + cmudict; adapter fidetype.adapters.b2t25
- Calibration `cal-692fb52a73417552`: T_frame 3.7809, T_sentence 4.5551, risk control none (α None, δ None, threshold None), set b2t25-fit-half-812-trials (per-day first half, file order)
- Policy `pol-2eaa4ff51919527a`: commit_p 0.5, commit_max_risk 0.5, offer_max_k 2

### `dec-000151-2873ec87` (entry 163, hash `49e347b28f2bd3d2…`)
- Committed: "a makes any thousand dollars a year"
- Correction (oracle-ground-truth, entry hash-linked): "he makes eighty thousand dollars a year"; char edits 7, word edits 2
- Scores: p_top1 0.6099, set size 3, guard risk 0.4571; reason: p_top1 0.61 >= 0.50
- Input: stream `75bb4803bb438628…`, source b2t25-copytask, frames [0, 224], t [0.28, 18.12], attempt 0, item b2t25-test-trial-412
- Decoder: card2024-online-rnn + fidetype PhonemeWordDecoder t15-copytask-online; words {"edit_penalty": 12.0, "lm_weight": 1.0, "word_bonus": 3.0}; weights `None`; LM tatoeba-eng-char-6gram-mkn + tatoeba word unigram + cmudict; adapter fidetype.adapters.b2t25
- Calibration `cal-692fb52a73417552`: T_frame 3.7809, T_sentence 4.5551, risk control none (α None, δ None, threshold None), set b2t25-fit-half-812-trials (per-day first half, file order)
- Policy `pol-2eaa4ff51919527a`: commit_p 0.5, commit_max_risk 0.5, offer_max_k 2

### `dec-000154-9117d538` (entry 167, hash `f9a48a9c45be52fa…`)
- Committed: "he's an enjoy get"
- Correction (oracle-ground-truth, entry hash-linked): "he's an indoor cat"; char edits 6, word edits 2
- Scores: p_top1 0.6204, set size 2, guard risk 0.4118; reason: p_top1 0.62 >= 0.50
- Input: stream `e9edff8641af328b…`, source b2t25-copytask, frames [0, 116], t [0.28, 9.48], attempt 0, item b2t25-test-trial-415
- Decoder: card2024-online-rnn + fidetype PhonemeWordDecoder t15-copytask-online; words {"edit_penalty": 12.0, "lm_weight": 1.0, "word_bonus": 3.0}; weights `None`; LM tatoeba-eng-char-6gram-mkn + tatoeba word unigram + cmudict; adapter fidetype.adapters.b2t25
- Calibration `cal-692fb52a73417552`: T_frame 3.7809, T_sentence 4.5551, risk control none (α None, δ None, threshold None), set b2t25-fit-half-812-trials (per-day first half, file order)
- Policy `pol-2eaa4ff51919527a`: commit_p 0.5, commit_max_risk 0.5, offer_max_k 2

### `dec-000238-96d8e348` (entry 252, hash `de28f1ce361edbf4…`)
- Committed: "it's not good for a second watching meticulously"
- Correction (oracle-ground-truth, entry hash-linked): "it's not good for a second watching particularly"; char edits 6, word edits 1
- Scores: p_top1 0.5782, set size 2, guard risk 0.4375; reason: p_top1 0.58 >= 0.50
- Input: stream `ffe494a185089de0…`, source b2t25-copytask, frames [0, 257], t [0.28, 20.76], attempt 0, item b2t25-test-trial-593
- Decoder: card2024-online-rnn + fidetype PhonemeWordDecoder t15-copytask-online; words {"edit_penalty": 12.0, "lm_weight": 1.0, "word_bonus": 3.0}; weights `None`; LM tatoeba-eng-char-6gram-mkn + tatoeba word unigram + cmudict; adapter fidetype.adapters.b2t25
- Calibration `cal-692fb52a73417552`: T_frame 3.7809, T_sentence 4.5551, risk control none (α None, δ None, threshold None), set b2t25-fit-half-812-trials (per-day first half, file order)
- Policy `pol-2eaa4ff51919527a`: commit_p 0.5, commit_max_risk 0.5, offer_max_k 2

### `dec-000247-19fafadb` (entry 262, hash `b1bc7bc9b991a097…`)
- Committed: "i've not from minneapolis"
- Correction (oracle-ground-truth, entry hash-linked): "i'm not from minneapolis"; char edits 2, word edits 1
- Scores: p_top1 0.5945, set size 3, guard risk 0.4800; reason: p_top1 0.59 >= 0.50
- Input: stream `7a7529ec2c9c6e5d…`, source b2t25-copytask, frames [0, 134], t [0.28, 10.92], attempt 0, item b2t25-test-trial-602
- Decoder: card2024-online-rnn + fidetype PhonemeWordDecoder t15-copytask-online; words {"edit_penalty": 12.0, "lm_weight": 1.0, "word_bonus": 3.0}; weights `None`; LM tatoeba-eng-char-6gram-mkn + tatoeba word unigram + cmudict; adapter fidetype.adapters.b2t25
- Calibration `cal-692fb52a73417552`: T_frame 3.7809, T_sentence 4.5551, risk control none (α None, δ None, threshold None), set b2t25-fit-half-812-trials (per-day first half, file order)
- Policy `pol-2eaa4ff51919527a`: commit_p 0.5, commit_max_risk 0.5, offer_max_k 2

### `dec-000267-ff51c7af` (entry 283, hash `e709180b5b74f7dd…`)
- Committed: "we don't have couple"
- Correction (oracle-ground-truth, entry hash-linked): "we don't have cable"; char edits 3, word edits 1
- Scores: p_top1 0.5142, set size 2, guard risk 0.3500; reason: p_top1 0.51 >= 0.50
- Input: stream `bf054b1bd9833992…`, source b2t25-copytask, frames [0, 114], t [0.28, 9.32], attempt 0, item b2t25-test-trial-622
- Decoder: card2024-online-rnn + fidetype PhonemeWordDecoder t15-copytask-online; words {"edit_penalty": 12.0, "lm_weight": 1.0, "word_bonus": 3.0}; weights `None`; LM tatoeba-eng-char-6gram-mkn + tatoeba word unigram + cmudict; adapter fidetype.adapters.b2t25
- Calibration `cal-692fb52a73417552`: T_frame 3.7809, T_sentence 4.5551, risk control none (α None, δ None, threshold None), set b2t25-fit-half-812-trials (per-day first half, file order)
- Policy `pol-2eaa4ff51919527a`: commit_p 0.5, commit_max_risk 0.5, offer_max_k 2

### `dec-000272-c460ab02` (entry 289, hash `995282988b0aff8e…`)
- Committed: "the last time he came was in much"
- Correction (oracle-ground-truth, entry hash-linked): "the last time he came was in march"; char edits 2, word edits 1
- Scores: p_top1 0.6963, set size 1, guard risk 0.0268; reason: p_top1 0.70 >= 0.50
- Input: stream `69aae5bac949d1f6…`, source b2t25-copytask, frames [0, 226], t [0.28, 18.28], attempt 0, item b2t25-test-trial-731
- Decoder: card2024-online-rnn + fidetype PhonemeWordDecoder t15-copytask-online; words {"edit_penalty": 12.0, "lm_weight": 1.0, "word_bonus": 3.0}; weights `None`; LM tatoeba-eng-char-6gram-mkn + tatoeba word unigram + cmudict; adapter fidetype.adapters.b2t25
- Calibration `cal-692fb52a73417552`: T_frame 3.7809, T_sentence 4.5551, risk control none (α None, δ None, threshold None), set b2t25-fit-half-812-trials (per-day first half, file order)
- Policy `pol-2eaa4ff51919527a`: commit_p 0.5, commit_max_risk 0.5, offer_max_k 2

