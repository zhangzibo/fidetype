# References (raw sources)

This is the **raw layer** of the [LLM wiki](../CLAUDE.md). Files here are immutable source material: Claude reads them and never edits them. Summaries and synthesis live in [`../wiki/`](../wiki/index.md).

```
references/
├── papers/     PDFs + extracted .txt   (git-ignored)
├── repos/      third-party code clones (git-ignored)
├── articles/   web articles as markdown
└── assets/     images used by sources
```

PDFs and cloned repos are git-ignored because this repo is public and they carry their own licences. Use the links below to fetch them.

## Catalogue
| Slug | Kind | Source | Licence | Local path |
|---|---|---|---|---|
| brain2qwerty-v1 | paper | Lévy et al., Nature Neuroscience 29 (2026): https://doi.org/10.1038/s41593-026-02303-2 | CC BY-NC-ND 4.0 | `papers/brain2qwerty_v1_nature_neuroscience_s41593-026-02303-2.pdf` |
| brain2qwerty-v2 | paper | Zhang, Lévy et al., Meta preprint (Jun 2026): https://facebookresearch.github.io/brain2qwerty/assets/brain2qwerty_v2.pdf | unspecified | `papers/brain2qwerty_v2_meta_preprint.pdf` |
| brain2qwerty-code | repo | https://github.com/facebookresearch/brain2qwerty (cloned 2026-11-07) | CC BY-NC 4.0 | `repos/brain2qwerty/` |

## Datasets (not stored here)
| Dataset | Access |
|---|---|
| SpanishBCBL (v1) | https://huggingface.co/datasets/bcbl190626/SpanishBCBL (gated, ~262 GB) |
| EnglishBCBL (v2) | embargoed |

### Survey 2026-11-10 (links only, no files; see [wiki/questions/public-datasets.md](../wiki/questions/public-datasets.md))
| Dataset | Link | Licence |
|---|---|---|
| Brain-to-Text '25 (Card et al.) | https://datadryad.org/dataset/doi:10.5061/dryad.dncjsxm85 | CC0 (Dryad); code repo unlicensed |
| Willett 2021 handwriting | https://datadryad.org/dataset/doi:10.5061/dryad.wh70rxwmv | CC0 (Dryad) |
| Brain-to-Text '24 (Willett 2023) | https://datadryad.org/dataset/doi:10.5061/dryad.x69p8czpq | CC0 (Dryad) |
| KT-sEMG (Nokia) | https://doi.org/10.7910/DVN/AV6XIR | CC BY 4.0 |
| Toronto sEMG typing (Achituve et al. 2025) | https://doi.org/10.5683/SP3/KV65VI | CC BY 4.0 (code CC BY-SA 4.0) |
| emg2qwerty | https://github.com/facebookresearch/emg2qwerty | CC BY-NC 4.0 |
| LibriBrain | https://huggingface.co/datasets/pnpl/LibriBrain | CC BY-NC 4.0 |
| MEG-MASC | https://osf.io/ag3kj/ | CC0 (part 1) |
| Chisco | https://openneuro.org/datasets/ds005170 | CC0 |
| ZuCo 2.0 | https://osf.io/2urht/ | CC BY 4.0 |
