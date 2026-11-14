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
| conformal-risk-control | paper | Angelopoulos, Bates, Fisch, Lei, Schuster, arXiv:2208.02814 (v4, 2025-06-13): https://arxiv.org/abs/2208.02814 | arXiv non-exclusive distribution 1.0 | not downloaded (abstract page read 2026-11-11) |
| learn-then-test | paper | Angelopoulos, Bates, Candès, Jordan, Lei, arXiv:2110.01052 (v5, 2022-09-29): https://arxiv.org/abs/2110.01052 | arXiv non-exclusive distribution 1.0 | not downloaded (abstract page read 2026-11-11) |
| adaptive-conformal-inference | paper | Gibbs, Candès, arXiv:2106.00170 (v3, 2021-10-28): https://arxiv.org/abs/2106.00170 | arXiv non-exclusive distribution 1.0 | not downloaded (abstract page read 2026-11-11) |
| conformal-pid-control | paper | Angelopoulos, Candès, Tibshirani, arXiv:2307.16895 (v1, 2023-07-31): https://arxiv.org/abs/2307.16895 | arXiv non-exclusive distribution 1.0 | not downloaded (abstract page read 2026-11-11) |
| conformal-beyond-exchangeability | paper | Barber, Candès, Ramdas, Tibshirani, arXiv:2202.13415 (v5, 2023-03-17): https://arxiv.org/abs/2202.13415 | arXiv non-exclusive distribution 1.0 | not downloaded (abstract page read 2026-11-11) |
| non-exchangeable-crc | paper | Farinhas, Zerva, Ulmer, Martins, arXiv:2310.01262 (v2, 2024-01-26; ICLR 2024): https://arxiv.org/abs/2310.01262 | arXiv non-exclusive distribution 1.0 | not downloaded (abstract page read 2026-11-11) |
| rolling-risk-control | paper | Feldman, Ringel, Bates, Romano, arXiv:2205.09095 (v7, 2023-01-27): https://arxiv.org/abs/2205.09095 | arXiv non-exclusive distribution 1.0 | not downloaded (abstract page read 2026-11-11) |
| conformal-covariate-shift | paper | Tibshirani, Barber, Candès, Ramdas, arXiv:1904.06019 (v3, 2020-07-06): https://arxiv.org/abs/1904.06019 | arXiv non-exclusive distribution 1.0 | not downloaded (abstract page read 2026-11-11) |

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
| toronto-semg-typing | `EMG typing dataset.zip` | Achituve, Beutel, Eby, Fetaya, Koivisto, Zariffa, Sci Data 12:440 (2025). Borealis https://doi.org/10.5683/SP3/KV65VI (version 1, released 2024-11-04), file id 836662, downloaded 2026-11-11 from `https://borealisdata.ca/api/access/datafile/836662`. MD5 `27d052ee1b5dcdf1e5eb0b875c698f6d` equals the Borealis API digest. Extracted: only `.rhd`, `.txt`, `.csv`, `.pdf`, `.xlsx` (the zip also holds a `.git` folder and Python code; not extracted) | CC BY 4.0 (Borealis API). Attribution needed. Baseline code `ANSLab-UHN/sEMG-TypingDatabase`: CC BY-SA 4.0, do not copy | `C:\Users\zhang\bci-data\raw\toronto-semg\EMG_typing_dataset.zip` (extracted to `...\toronto-semg\extracted\`) | 2 766 730 294 | `73c4f925b81c627643373dc271878a6fda6c0b59c521ae856a5610c8e5de7ef3` |
| brain-to-text-24 | `competitionData.tar.gz` | Willett et al. 2023, Nature, "A high-performance speech neuroprosthesis" (participant T12). Dryad https://doi.org/10.5061/dryad.x69p8czpq. Downloaded 2026-11-12 from the Zenodo deposit of the same DOI, https://zenodo.org/records/8047896 (Dryad file downloads need a login token). MD5 `a7e9d972ac5b65171a37674eb47730b8` equals the Zenodo API digest. The Zenodo copy (3 653 747 969 bytes) is an earlier version than Dryad v9 (3 669 638 707 bytes); same partitions (train / test / competitionHoldOut). Also the readmes (`README.md`, `competitionData_readme.txt`, `sentences_readme.txt`) | CC0 1.0 (Zenodo + Dryad). Companion code `fwillett/speechBCI`: no licence, do not copy | `C:\Users\zhang\bci-data\raw\b2t24\competitionData.tar.gz` (extracted to `...\b2t24\extracted\`) | 3 653 747 969 | `d1e90aabb380eea7d286c723f3ed3b69c71108954bc2e4826ae0a5e2bdd7058e` |
| cmudict | `cmudict.dict` | https://github.com/cmusphinx/cmudict, commit `74790861f652b15e4ac49015a90074ad62a27690` | BSD-2-Clause style (CMU; keep the copyright notice). Commercial use allowed | `C:\Users\zhang\bci-data\lexicon\cmudict\cmudict.dict` (+ `LICENSE`) | 3 618 488 | `81917843c7f44ce2b094ac63873c2c7a4cf802040792c455ba3ca406891c3d22` |
| nlb-mc-rtt | `sub-Indy_desc-train_behavior+ecephys.nwb` | NLB MC_RTT, O'Doherty, Pei et al. DANDI 000129 version 0.241017.1444, https://doi.org/10.48324/dandi.000129/0.241017.1444 (monkey Indy, M1 Utah array, self-paced random-target reaching). Downloaded 2026-11-14 from `https://api.dandiarchive.org/api/assets/2ae6bf3c-788b-4ece-8c01-4b4a5680b25b/download/`. Only the train file (the test file has no behaviour). Binned to 20 ms by `experiments/2026-11-14-p12-03-control/convert_mc_rtt.py` (derived NPZ in `C:\Users\zhang\bci-data\derived\nlb-mc-rtt\`) | CC-BY-4.0 (DANDI API `license`, checked 2026-11-14). Attribution: cite the dandiset DOI and the NLB paper (Pei et al. 2021) | `C:\Users\zhang\bci-data\raw\nlb-mc-rtt\sub-Indy_desc-train_behavior+ecephys.nwb` | 49 764 168 | `2f78db62bd4d68b9bc737444f72bc2dfe475d7390dd7a54848aaf6a6a6ba8da5` |
| braingate-recal | `PRIT_paper_data.tar.gz`, `README.md` (**not downloaded**) | Wilson et al., "Long-term unsupervised recalibration of cursor BCIs", Nat. Biomed. Eng. (2025), doi:10.1038/s41551-025-01536-z. Dryad https://doi.org/10.5061/dryad.1jwstqk6g (version 4, published 2025-05-29; participant T5, closed-loop cursor). Dryad API metadata read 2026-11-14 (file list, sizes, SHA-256 digests). The file download API answered 401 "must have current bearer token" on 2026-11-14: a Dryad API account (or a manual browser download by the user) is needed | CC0 1.0 (Dryad API `license`, checked 2026-11-14). No extra terms in the metadata; the abstract says that personal-use data of T11 (possible PHI) is excluded. We follow the Dryad citation norm and never try to re-identify the participant | planned: `C:\Users\zhang\bci-data\raw\braingate-recal\` | 1 685 533 203 (tar.gz) + 10 938 (README) | Dryad digests: tar.gz `12f60dce551336d6472b7743380b959092f0626184845da35c12377b7dd263f6`, README `54ba9459eee5004927552e18c0715f9335d3596f52e300a25bcbc650bf947182` |

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

### Survey 2026-11-13: intent and control datasets (links only, no files; see [wiki/questions/intent-datasets-survey.md](../wiki/questions/intent-datasets-survey.md))
| Dataset | Link | Licence |
|---|---|---|
| BrainGate multi-gesture drag-and-drop | https://datadryad.org/dataset/doi:10.5061/dryad.98sf7m0v1 | CC0 1.0 (Dryad API) |
| BrainGate long-term unsupervised recalibration | https://datadryad.org/dataset/doi:10.5061/dryad.1jwstqk6g | CC0 1.0 (Dryad API) |
| BrainGate preparatory encoding | https://datadryad.org/dataset/doi:10.5061/dryad.brv15dvr9 | CC0 1.0 (Dryad API) |
| BrainGate MINDFUL | https://datadryad.org/dataset/doi:10.5061/dryad.n2z34tn5s | CC0 1.0 (Dryad API) |
| NoMAD latent alignment | https://datadryad.org/dataset/doi:10.5061/dryad.q83bk3jtp | CC0 1.0 (Dryad API) |
| NLB MC_Maze / MC_RTT / Area2_Bump / MC_Maze_Large | https://dandiarchive.org/dandiset/000128 , /000129 , /000127 , /000138 | CC-BY-4.0 (DANDI) |
| FALCON M1-A / H2 / M2 / H1 | https://dandiarchive.org/dandiset/000941 , /000950 , /000953 , /000954 | CC-BY-4.0 (DANDI; 000953 draft) |
| O'Doherty NHP reaching | https://zenodo.org/records/583331 | CC BY 4.0 (Zenodo) |
| Miller ECoG library | https://purl.stanford.edu/zk881ps0522 | CC BY-SA 4.0 |
| BCI Competition IV (sets 1, 2a, 2b, 4) | https://www.bbci.de/competition/iv/ | no licence (terms checkbox, cite) |
| BCI Competition III (set II P300) | https://www.bbci.de/competition/iii/ | no licence (terms checkbox, cite) |
| BNCI Horizon 2020 database | https://bnci-horizon-2020.eu/database/data-sets | per set: 2014-15 CC BY-NC-ND / CC BY-ND 4.0; 2017+ CC BY 4.0 |
| PhysioNet EEGMMIDB | https://physionet.org/content/eegmmidb/1.0.0/ | ODC-By 1.0 |
| Stieger 2021 SMR cursor EEG | https://figshare.com/articles/dataset/Human_EEG_Dataset_for_Brain-Computer_Interface_and_Meditation/13123148 | CC BY 4.0 (figshare API) |
| OpenBMI / Lee2019 | https://gigadb.org/dataset/100542 | no data licence on GigaDB API |
| Tsinghua SSVEP benchmark + BETA | https://bci.med.tsinghua.edu.cn/download.html | no licence |
| GRABMyo | https://physionet.org/content/grabmyo/1.1.0/ | CC BY 4.0 |
| Hyser HD-sEMG | https://physionet.org/content/hd-semg/2.0.0/ | ODC-By 1.0 |
| Meta generic neuromotor interface | https://github.com/facebookresearch/generic-neuromotor-interface | CC BY-NC 4.0 (data + code) |
| emg2qwerty (re-checked) | https://github.com/facebookresearch/emg2qwerty | README CC-BY-NC-4.0; LICENSE file CC BY-NC-SA 4.0 |
| emg2pose | https://github.com/facebookresearch/emg2pose | CC BY-NC-SA 4.0 |
| Ninapro DB1-DB10 | https://ninapro.hevs.ch/ | no licence (cite) |
| Côté-Allard Myo armband | https://github.com/UlysseCoteAllard/MyoArmbandDataset | GPL-3.0 (repo) |
| CSL-HDEMG | https://www.uni-bremen.de/en/csl/research/motion-recognition | no licence (cite) |
| putEMG (paper) | https://pmc.ncbi.nlm.nih.gov/articles/PMC6720505/ | CC BY-NC 4.0 (paper; host page not read) |
