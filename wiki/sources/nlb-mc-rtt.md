---
title: "NLB MC_RTT: macaque motor cortex, self-paced random-target reaching (DANDI 000129)"
type: source
tags: [dataset, implant, intracortical, utah-array, monkey, cursor, control, cc-by, licence-clean, p12]
sources: [nlb-mc-rtt]
updated: 2026-11-14
---

# NLB MC_RTT (DANDI 000129)

## Citation and links
- **Data:** O'Doherty, J. (2024). *MC_RTT: macaque motor cortex spiking activity during self-paced reaching* (Version 0.241017.1444). DANDI archive. https://doi.org/10.48324/dandi.000129/0.241017.1444. Contributors: Felix Pei, Joseph O'Doherty.
- **Benchmark:** part of the Neural Latents Benchmark (NLB, Pei et al. 2021), https://neurallatents.github.io. We did not read the NLB paper for this page; facts below come from the DANDI metadata and the file.
- **Licence:** **CC-BY-4.0** (DANDI API `license` field, checked 2026-11-14). Commercial use: yes, with attribution (cite the DOI above and NLB).
- **Local raw path (outside the repo, never committed):** `C:\Users\zhang\bci-data\raw\nlb-mc-rtt\sub-Indy_desc-train_behavior+ecephys.nwb` (49,764,168 bytes; SHA-256 in [`references/README.md`](../../references/README.md)). Derived 20 ms bins: `C:\Users\zhang\bci-data\derived\nlb-mc-rtt\mc_rtt_20ms.npz` (made by `experiments/2026-11-14-p12-03-control/convert_mc_rtt.py`).

## TL;DR
One monkey (Indy) reaches between targets picked at random from an 8 x 8 grid, with no delay period and no trial structure. A Utah array in primary motor cortex gives sorted units. Finger position, finger velocity, cursor position and target position are sampled at 1 kHz. It is a small, clean, licence-clean benchmark for **continuous** velocity decoding, which is what the FEP-0005 control profile needs.

## Key facts (checked on the train file, 2026-11-14)
| Item | Value |
|---|---|
| Files | train (behaviour + spikes, 49.8 MB) and test (spikes only, 1.2 MB). We use the train file only |
| Duration | 649.1 s (649,100 samples at 1 kHz) |
| Units | 130 sorted units (96 electrodes); NLB marks some as held out |
| Behaviour | `cursor_pos` (2D), `finger_pos` (3D), `finger_vel` (2D), `target_pos` (2D); stored in mm with conversion 0.001 to m |
| Targets | 8 x 8 grid, spacing 15 mm (x -52.5 to 52.5, y 7.5 to 112.5 mm); 563 target changes, median 1.1 s apart |
| Speed | median 15.9 mm/s, 90th percentile 178.6, 99th 331.7 mm/s (20 ms bins) |
| Firing | mean 4.0 Hz per unit; total count per 20 ms bin: median 9 spikes over 130 units (some bins have 0) |
| Trials table | 1,080 NLB windows with a `split` column (train / val / test / none) |
| Invalid | 15 bins (20 ms) with NaN behaviour |

## Our use
- P12-03 evaluation of the control trust layer ([results](../../experiments/2026-11-14-p12-03-control/results.md), [control events](../concepts/control-events.md)): causal Wiener filter R² 0.478; conformal coverage 0.905 at 0.90; zero-input drift 13.3 mm/s, stopped by the no-signal gates.

## Limitations
- One animal, one session, about 11 minutes. No human, no closed loop: the monkey moved its real arm; the decoder is offline.
- No click or other discrete event.
- Spike sorting is fixed by the provider. Unsorted threshold crossings (as in BrainGate) behave differently.

> **Our take:** MC_RTT is a good first test because it is small, continuous and CC BY. It cannot show closed-loop behaviour (the user corrects drift). The [BrainGate recalibration dataset](../entities/braingate-recalibration-dataset.md) is the planned human, closed-loop test.

Related: [Intent and control datasets](../questions/intent-datasets-survey.md) · [Control events](../concepts/control-events.md)
