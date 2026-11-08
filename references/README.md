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
