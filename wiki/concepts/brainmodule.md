---
title: BrainModule (subject-aware conv encoder)
type: concept
tags: [architecture, encoder]
sources: [brain2qwerty-v1, brain2qwerty-v2, brain2qwerty-code]
updated: 2026-11-07
---

# BrainModule

The BrainModule is the convolutional front end for MEG/EEG that Meta's Brain & AI team reuses across projects. It originates in Défossez et al. 2023, *Decoding speech perception from non-invasive brain recordings* (Nat. Mach. Intell.), which is not yet ingested. It is implemented in `neuraltrain` (`SimpleConv`, `SimpleConvTimeAgg`).

## Components
1. **Spatial attention / channel merger.** Sensor 2D positions are encoded as Fourier features (dim 2048). A learned attention maps any number of sensors onto **270 virtual channels**. This is what lets one model handle different sensor layouts and channel counts.
2. **Subject layer.** A per-subject linear or affine layer that absorbs individual differences in head shape and sensor geometry.
3. **Dilated residual conv stack.** GELU, BatchNorm, dropout, and skip connections.
   - v1: 8 blocks, kernel 3, hidden 2048
   - v2: 4 blocks, kernel 5, hidden 1500
4. **Output stage.**
   - v1: attention pooling over time, giving one 2048-d vector per keystroke
   - v2: strided downsampling into a Conformer

## Evidence
- In v1, the Conv module *alone* already beats EEGNet on MEG ([v1](../sources/brain2qwerty-v1.md)).
- In v2, replacing the BrainModule with a temporal-patch frontend raises CER from 0.28 to 0.37 ([v2](../sources/brain2qwerty-v2.md), Fig. S5C).
- In a t-SNE of the BrainModule's embeddings, points cluster **by subject**. After the Conformer, they cluster **by key** following the keyboard layout ([v2](../sources/brain2qwerty-v2.md), Fig. S2). In other words, the subject identity is only factored out later in the network.

Related: [MEG](meg.md) · [CTC](ctc.md)
