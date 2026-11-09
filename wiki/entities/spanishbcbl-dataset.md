---
title: SpanishBCBL dataset (Brain2Qwerty v1)
type: entity
tags: [dataset, meg, eeg, public]
sources: [brain2qwerty-v1, brain2qwerty-code]
updated: 2026-11-08
---

# SpanishBCBL

- **Access**: https://huggingface.co/datasets/bcbl190626/SpanishBCBL. The dataset is **not gated**: a plain download works, with no access request. (The paper itself says data is available "upon request" to academics. The HuggingFace release replaces that.)
- **Size**: the MEG part is about **268 GB** (MEG `.fif`, behavioural `.mat` logs). The full set also has EEG BrainVision files. The loader can download the MEG subtree on its own.
- **Contents**:
  - MEG: 20 participants (19 usable), 21.5 h, 5,100 sentences, 193k characters.
  - EEG: 20 participants, 17.7 h, 4,000 sentences, 146k characters.
  - Each session covers 128 unique Spanish sentences, each typed about twice. Sentence diversity is low.
- **Loader**: `studies/spanishbcbl.py` in the [code repo](../sources/brain2qwerty-code.md) (study class `Pinet2024Meg`). It hard-codes some bad-file lists and naming quirks.
- **Licence / terms**: **CC BY-NC 4.0** (HuggingFace card). Research use only. See the licence rule in the [project plan](../questions/project-plan.md#licence-rule).

> **Our take:** This is the **only public typing-MEG dataset we know of**. Any reproduction or new method has to start here.

## Inspection findings (2026-11-08)

Source: our own inspection of subject S25 (`25_12032`, 2 sessions × 2 typing blocks) in MNE 1.13.2. Full results: [experiments/2026-11-08-inspect-spanishbcbl/results.md](../../experiments/2026-11-08-inspect-spanishbcbl/results.md).

### Files and layout
- The MEG tree has **25 participant IDs**, but only **19 unique MEG participants**. Some people have more than one ID: S1 = S18, S4 = S14, S5 = S10 = S21 (dataset card). S23 is excluded (metal), and S13 has no logs. Evidence and leakage check: [SpanishBCBL repeated participants](../questions/spanishbcbl-repeated-participants.md).
- Some session folders are duplicates (3 found). The download hard-links them, so they use no extra disk space.
- File names are messy (for example `bolck2.fif`). The loader must match them with tolerance, not with a fixed pattern.
- Each typing block is one `.fif` file, 13–16 min long, 1000 Hz, online filter 0.10–330 Hz, line frequency 50 Hz.
- The behavioural log of each block is a `.mat` file in `MEG/logs/` (for example `S25-session1_block1_list1.mat`).

### Channels
| Type | Count | Names |
|---|---|---|
| Magnetometer (mag) | 102 | `MEGxxx1` |
| Planar gradiometer (grad) | 204 | `MEGxxx2`, `MEGxxx3` |
| EOG | 2 | `EOG001`, `EOG002` |
| ECG | 1 | `ECG003` |
| IAS (MaxShield) | 11 | `IAS*` |
| Stim | 1 | `STI101` |
| System | 1 | `SYS201` |
| **Total** | **322** | |

### Head digitisation
- **Present.** Each block has 3 fiducials, 5 HPI coil points and 315 head-shape points (session 2: 218), plus a valid `dev_head_t`.
- The dataset has no MRI. Source-space work must use a template brain (scaled fsaverage), fitted to the head-shape points.
- The head moves by about 7 mm between sessions. Pooling sessions needs one common head position.

### Raw data state
- The data is raw **MaxShield** data (internal active shielding on). No SSS was applied. MNE loads it only with `allow_maxshield=True`.
- The dataset has **no SSS calibration files** (no fine-calibration file, no cross-talk file). SSS runs without them. This is a small quality loss.
- cHPI coils were on (295–328 Hz). This allows head-movement estimation.

### Trigger coding (`STI101`)
| Code | Meaning |
|---|---|
| Windows virtual-key (VK) code | One key press. Letters = upper-case ASCII (65–90), space = 32, backspace = 8, return = 13 |
| 10 | Word onset (RSVP word shown on the screen) |
| 20 | Block marker |
| 30 | Pause marker (the log has no times for it) |
| 1, 2, 3, … 255 | Start-up test ramp, about 20 ms apart. Drop it |

The VK code has no case and no accents. Take the key identity from the log (`kp.CookedKey`), not from the trigger.

### Log (`.mat`) structure
- The useful variable is the struct `pr_trials`. Each block has 66 trials: 2 training trials (with visual feedback) and 64 test trials.
- `sequence{trial}`: the target sentence of each trial, including the training trials. Case varies and trailing spaces occur. Normalise before use.
- `kp{trial}`: the key presses (`Time`, `Keycode`, `CookedKey`, …). `key{trial}` also holds the releases.
- `keyTrig{trial}`: the trigger send time of each key press. `rsvp{trial}.trigTime`: the trigger send time of each word. `blockTrig`: the block markers. All three use one clock.
- `dist` and `errperc` count case and trailing spaces. Do not use them as typing-error rates.
- The typed text (the `CookedKey` sequence) contains typos and backspaces. It can differ from the target.

### Clock drift and alignment
- The log clock and the MEG sample clock **drift by about 0.5 ms per second** (slope 1.0005, the same in all blocks). A constant offset gives about 0.45 s of error at the end of a block.
- Our method: drop the test ramp. Match the log and MEG code sequences (`difflib`). Fit offset and slope per block. Check every pair by time (tolerance 20 ms).
- **Result for S25:** 9366/9367 key presses matched (11972/11973 events of all types). Median residual 0.33 ms, worst block p95 0.97 ms.
- The key trigger comes about 8 ms after the keyboard-queue time. This is less than one sample at 100 Hz.

### Data quality
- A narrow **23.3 Hz peak** on the magnetometers (32 dB prominence). It is inside the 0.5–45 Hz band. Check it again after SSS.
- **50 Hz line noise and harmonics** (100, 150, 200 Hz) are strong on the magnetometers (about 17–20 dB) and weak on the gradiometers.
- No flat channels. The Maxwell bad-channel scan finds no bad channels. Before SSS, 51 channels have high RMS in a few sensor groups. This suggests external interference, not broken sensors.

### Recommended preprocessing
1. Load with `allow_maxshield=True`. Mark bad channels with `find_bad_channels_maxwell`, per block.
2. Apply tSSS (`maxwell_filter`, `st_duration=10`) with one `destination` head position per subject.
3. Notch 50 Hz (and 100 Hz). Band-pass 0.5–45 Hz. Resample to 100 Hz. (Baseline variant: the v1 recipe, 0.1–20 Hz, 50 Hz.)
4. Take keystroke times from the MEG triggers. Join key identity and sentence text from the log with the drift fit.
5. Use the 306 MEG channels as decoder input. Keep EOG/ECG for artefact rejection.
6. Keep the 2 training trials of each block out of test metrics.

> **Our take (what this means for M1):** The data is usable for the M1 baseline decoder. Nothing blocks it.
> - The loader must be our own code. It must handle the messy file names, the duplicate folders and the per-block drift fit. The Brain2Qwerty loader avoids the drift by sequence matching. We use the same idea plus a time check, but we copy no code.
> - Keystroke labels come with sub-millisecond timing. This is more than enough for CTC targets at 100 Hz.
> - tSSS is a required step. Without it, the raw MaxShield data has strong interference.
> - Typed text and target text differ. M1 needs a character alignment step between them to choose the label (typed keys or target sentence).
> - The head digitisation keeps source-space options open (scaled fsaverage) for later work.

Related: [EnglishBCBL](englishbcbl-dataset.md) · [BCBL](bcbl.md) · [Brain2Qwerty v1](../sources/brain2qwerty-v1.md) · [MEG](../concepts/meg.md) · [Compute setup](../questions/compute-setup.md)
