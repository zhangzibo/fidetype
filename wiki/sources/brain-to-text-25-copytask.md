---
title: "Brain-to-Text '25 copy-task logits (Card et al. 2024, t15_copyTask.pkl)"
type: source
tags: [dataset, implant, intracortical, speech, phoneme, ctc, cc0, licence-clean, trust-eval]
sources: [brain-to-text-25-copytask]
updated: 2026-11-10
---

# Brain-to-Text '25 copy-task logits (`t15_copyTask.pkl`)

## Citation and links
- **Paper:** N. S. Card, M. Wairagkar, C. Iacobacci, X. Hou, T. Singer-Clark, F. R. Willett, E. M. Kunz, C. Fan, M. Vahdati Nia, D. R. Deo, A. Srinivasan, E. Y. Choi, M. F. Glasser, L. R. Hochberg, J. M. Henderson, K. Shahlaie, S. D. Stavisky, D. M. Brandman. "An accurate and rapidly calibrating speech neuroprosthesis." *N Engl J Med* (2024).
- **Data:** "Data for: An accurate and rapidly calibrating speech neuroprosthesis", Dryad, https://doi.org/10.5061/dryad.dncjsxm85, version 5 (2025-07-03).
- **Licence:** CC0 1.0 (Dryad API `license` field). Commercial use: yes.
- **Code:** `Neuroprosthetics-Lab/nejm-brain-to-text` has **no licence** (GitHub API: `null`). We read it only for facts (the file list, `rnn_args.yaml` values). **We write our own code and copy nothing.**
- **Local raw path (outside the repo, never committed):** `C:\Users\zhang\bci-data\brain-to-text-25\t15_copyTask.pkl` (57,786,348 bytes, SHA-256 `7313b9a1…5e165e3`) and the dataset card `README.md`. Full digests: [`references/README.md`](../../references/README.md).
- **Download route:** Dryad file downloads need a login token (the API returned "Unauthorized"). We used the Hugging Face mirror `Paulownia/Brain-to-text_25_data`. The SHA-256 of both files equals the Dryad API digest, so the bytes are the Dryad bytes.

## TL;DR
One 58 MB file holds the online output of a real intracortical speech BCI for **1,718 copy-task evaluation trials** of participant T15 (ALS, 256 electrodes in the left precentral gyrus). For each trial it has the cue sentence and its phonemes, the RNN's per-frame **phoneme CTC logits**, the raw decoded phonemes, and the final decoded sentence after the n-gram LM and OPT rescoring. This is enough to test a trust layer on real, licence-clean decoder output without a GPU.

## Key facts (checked on the file, 2026-11-10)
| Item | Value |
|---|---|
| Trials | 1,718 (90 with a 50-word vocabulary, 1,628 with 125,000 words) |
| Sessions | 15 post-implant days: 25, 27, 34, 46, 48, 69, 74, 76, 81, 83, 88, 90, 95, 223, 244 |
| Keys (one list entry per trial) | `post_implant_day`, `vocab_size`, `cue_sentence`, `cue_sentence_phonemes`, `decoded_logits`, `decoded_phonemes_raw`, `decoded_sentence`, `decoded_sentence_phonemes`, `speech_duration_s` |
| Logits | float32, shape (T, 41), unnormalised. T = 71 to 627 (median 188) |
| Vocabulary order | 0 = CTC blank, 1 = `SIL` (word boundary), 2–40 = 39 ARPAbet phonemes in alphabetical order (AA … ZH), no stress |
| Order check | The CTC greedy path equals `decoded_phonemes_raw` in 1,709 of 1,718 trials; the other 9 differ by one phoneme |
| Frame period | 80 ms (inferred: 20 ms bins, patch stride 4 in the challenge `rnn_args.yaml`; `speech_duration_s / T` ≤ 0.076 s) |
| Speech rate (125k trials) | 32.4 words/min, 159.3 characters/min (cue text over `speech_duration_s`) |
| Phoneme error rate (PER), raw greedy vs cue | 0.0954 (all trials); 0.0982 (125k) |
| WER of the published sentence vs cue (our computation) | **0.0434** (all 1,718, pooled); 0.0450 (125k); 0.0025 (50-word) |
| Sentence exactly right (published) | 0.810 (all); 0.800 (125k) |
| Pickle safety | Opcode scan: only `numpy.core.multiarray._reconstruct`, `numpy.ndarray`, `numpy.dtype`, `numpy.core.multiarray.scalar`. No risky opcodes. Loaded with a whitelist Unpickler |

The paper abstract (Dryad page) says: "On the first day of use (25 days after surgery), the neuroprosthesis achieved 99.6% accuracy with a 50-word vocabulary." "On the second day, after 1.4 additional hours of system training, the neuroprosthesis achieved 90.2% accuracy using a 125,000-word vocabulary." "With further training data, the neuroprosthesis sustained 97.5% accuracy over a period of 8.4 months after surgical implantation, and the participant used it to communicate in self-paced conversations at a rate of approximately 32 words per minute".

> **Our take:** Our pooled WER (4.34 %) is a different aggregate from the paper's "97.5% accuracy" (2.5 % WER). The paper figure is probably a mean over sessions or a subset; we did not read the full paper. The per-day WERs are in the [experiment tables](../../experiments/2026-11-10-b2t25-trust/results/tables.md).

## Limitations
- One participant, one implant type. Copy task (cued sentences), not free conversation.
- The logits are the **online** decoder output, already shaped by the decoder's training. We cannot rerun the decoder without the 11 GB neural data.
- The per-frame timing is inferred, not stated in the file.
- The conversation-mode file (`t15_personalUse.pkl`) has no text, so it cannot test commits.
- 64 of the 1,628 125k-vocab cue sentences also occur in Tatoeba English, which trains our character LM (possible small LM leak; see the experiment).

## Feeds
- Entity: [Brain-to-Text '25](../entities/brain-to-text-25.md), [Dryad intracortical datasets](../entities/dryad-intracortical-datasets.md).
- Concepts: [CTC](../concepts/ctc.md), [Error metrics](../concepts/error-metrics.md).
- Results: [B2T '25 trust result](../questions/b2t25-trust-result.md), [Trust core v0 results](../questions/trust-core-v0-results.md#8-cross-device-intracortical-speech-2026-11-10).
- Code: `src/fidetype/adapters/b2t25.py` (adapter), `src/fidetype/lm/phoneme_words.py` (phoneme → words).
