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
| SpanishBCBL (v1) | https://huggingface.co/datasets/bcbl190626/SpanishBCBL (not gated, 280.4 GB for the whole repo per the HF API on 2026-11-10; an earlier note said "gated, ~262 GB") |
| EnglishBCBL (v2) | embargoed |

### Downloaded datasets (files outside the repo, never committed)
| Slug | File | Source | Licence | Local path | Size (bytes) | SHA-256 |
|---|---|---|---|---|---|---|
| brain-to-text-25 | `t15_copyTask.pkl` | Card et al. 2024, Dryad https://doi.org/10.5061/dryad.dncjsxm85 (version 2025-07-03). Downloaded 2026-11-10 from the HF mirror `Paulownia/Brain-to-text_25_data` (`additional_files/`), because Dryad file downloads need a login. The digest equals the Dryad API digest. | CC0 1.0 (Dryad). Companion code `Neuroprosthetics-Lab/nejm-brain-to-text`: no licence, do not copy | `C:\Users\zhang\bci-data\brain-to-text-25\t15_copyTask.pkl` | 57 786 348 | `7313b9a1102794cfd31455a85d3d16a1aca962aa730a7134d9346fb8f5e165e3` |
| brain-to-text-25 | `README.md` (dataset card) | same | CC0 1.0 | `C:\Users\zhang\bci-data\brain-to-text-25\README.md` | 3 183 | `3516e6c4c20cfc8c66e5b73fe70474208093ce807034f32f1500087622908e70` |
| cmudict | `cmudict.dict` | https://github.com/cmusphinx/cmudict, commit `74790861f652b15e4ac49015a90074ad62a27690` | BSD-2-Clause style (CMU; keep the copyright notice). Commercial use allowed | `C:\Users\zhang\bci-data\lexicon\cmudict\cmudict.dict` (+ `LICENSE`) | 3 618 488 | `81917843c7f44ce2b094ac63873c2c7a4cf802040792c455ba3ca406891c3d22` |

Pickle safety (`t15_copyTask.pkl`): an opcode scan (`pickletools.genops`, no load) found only 4 imports: `numpy.core.multiarray._reconstruct`, `numpy.ndarray`, `numpy.dtype`, `numpy.core.multiarray.scalar`. No `INST`/`OBJ`/`NEWOBJ`/extension/persistent-id opcodes. We load it only with the whitelist Unpickler in `src/fidetype/adapters/b2t25.py`.

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
