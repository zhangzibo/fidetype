---
title: "Error encoding in human speech motor cortex (Hou et al. 2025)"
type: source
tags: [implant, intracortical, speech, t15, t12, error-signals, feedback, f1, abstract-level]
sources: [hou-error-encoding]
updated: 2026-11-24
---

# Hou et al. 2025: error signals in speech motor cortex

## Citation and links
- X. Hou, C. Iacobacci, N. S. Card, M. Wairagkar, T. Singer-Clark, E. M. Kunz, ..., D. M. Brandman, S. D. Stavisky (14 authors). "Error encoding in human speech motor cortex." bioRxiv, v1 posted 2025-06-09. https://doi.org/10.1101/2025.06.07.658426 . No journal version yet (bioRxiv API, 2026-11-24).
- **Licence:** CC BY-NC-ND (bioRxiv API "cc_by_nc_nd"; Europe PMC "cc by-nc-nd"). We store nothing.
- **Local raw path:** none. We read the abstract (Europe PMC). A partial full-text read gave the participants; other body numbers were not checked and are not quoted here.

## TL;DR
When a speech BCI shows a wrong word, speech motor cortex shows an error signal. A decoder can read that signal, so the BCI can detect its own errors without any action by the user.

## Key facts
| Item | Value | Where |
|---|---|---|
| Main result | "This activity could be decoded to enable the neuroprosthesis to identify its own errors with up to 86% accuracy" | Abstract |
| Error types | "distinct neural patterns associated with specific types of mistakes, such as phonemic or semantic differences between the person's intended and displayed words" | Abstract |
| Participants | T15 and T12 (Methods, partial read) | Methods |

## Limitations
- Two participants. The "up to 86%" is a peak value. We have not read the full paper.

## Why it matters for us
A neural error signal is an **implicit feedback** source for F1. It could catch wrong commits that the user does not report (silent errors), and so lower the gap described in [OCP with corrupted feedback](ocp-corrupted-feedback.md). It is a later route; an explicit rating, as in [Card et al. 2026](card-2026-home-use.md), is the first route.

## Feeds
- [F1 guarantee scope](../questions/f1-guarantee-scope.md)
- [North star F1](../questions/north-star.md#f1-safe-self-improving-bci-e2)
