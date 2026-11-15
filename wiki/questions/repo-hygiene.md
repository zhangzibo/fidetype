---
title: Repository hygiene (what to commit, cleanup checklist)
type: question
tags: [repo, hygiene, ci, privacy, licences, maintenance]
sources: []
updated: 2026-11-15
---

# Repository hygiene

**Question (2026-11-15, task R-23):** Do we commit files that we do not need? What must never be in the public repository? How do we check this again later?

**Short answer:** The tracked tree is clean of the dangerous classes: no caches, no build output, no recordings, no weights, no secrets, no third-party PDFs or code, no private e-mail addresses in files. The size is 45 MB in 1,836 files; 26 MB of it is `experiments/`. Nothing had to be removed. The audit added `.gitignore` rules, a check script and a CI job. Nine judgement calls are left for the user (table below).

## 1. Audit result (2026-11-15, commit `957f0fa`)

| Top-level entry | Files | Size | Note |
|---|---|---|---|
| `experiments/` | 836 | 26.2 MB | plan.md, results.md, aggregate JSON, 160 `.log` files (0.5 MB) |
| `papers/` | 109 | 6.3 MB | Our own paper: LaTeX, figures, 8 draft PDFs (2.5 MB), final PDFs, arXiv zip |
| `tools/` | 22 | 4.9 MB | 4.7 MB is the vendored draw.io viewer (Apache-2.0, needed offline) |
| `src/` | 113 | 2.5 MB | Includes benchmark split files (ids and hashes only) |
| `wiki/` | 220 | 1.9 MB | 102 files are progress tracker files (100 archived fragments) |
| `spec/` | 334 | 1.2 MB | Golden vectors (synthetic) |
| `sdk/` | 75 | 0.9 MB | TypeScript and Rust sources |

| Check | Result |
|---|---|
| Caches, build output (`__pycache__`, `.pytest_cache`, `node_modules`, `target/`, `dist/`, `*.egg-info`) | None tracked. All present only in the work tree and ignored |
| Data and model files (`.fif`, `.edf`, `.mat`, `.npy`, `.h5`, `.pt`, `.pkl`, ...) | None tracked. 33 `.npz` files are all synthetic golden vectors in `spec/conformance/` |
| Files over 5 MB | None. Largest: draw.io viewer 4.7 MB, then a 1.4 MB result JSON |
| Secrets (private keys, GitHub / npm / AWS / API tokens) | None found |
| E-mail addresses in tracked files | Only placeholders (`example.com`, `example.org`) and the vendored viewer's licence header |
| Third-party PDFs, third-party code | None. `references/papers/` and `references/repos/` are ignored. The 28 PDFs are our own paper |
| Per-trial participant typed text (`trials.json`) | None at the tip (removed in M5-12; a `.gitignore` rule blocks it) |
| Duplicates | Licence copies in `sdk/*/LICENSE` (needed by the packages); paper sources duplicated in `papers/paper1/final/arxiv/` (the frozen arXiv copy) |

## 2. Changes made in R-23

- `.gitignore`: added tool caches (`.pytest_cache`, `.ruff_cache`, `.mypy_cache`, coverage), `node_modules/`, `*.tgz`, `sdk/rust/target/`, more model and key formats (`*.pkl`, `*.safetensors`, `*.onnx`, `*.pem`), the job sentinel `experiments/**/DONE` and the tracker merge lock.
- [`tools/hygiene/check.js`](../../tools/hygiene/check.js): the repeatable audit (below).
- [`tools/hygiene/links.js`](../../tools/hygiene/links.js): relative-link and anchor check for `README.md`, `docs/`, the SDK READMEs and the project files.
- CI job `hygiene` in [`.github/workflows/tests.yml`](../../.github/workflows/tests.yml) runs both with `--ci`.
- No file was removed: no tracked file was clear junk outside `experiments/` (which this task did not touch, because jobs were running).

## 3. Judgement calls for the user

| # | Item | Facts | Recommendation |
|---|---|---|---|
| H-1 | Example decoded texts in experiment results | 9 committed JSON files hold example pairs (stimulus sentence + decoded top-1 text): 30 per file in the MEG beam results, 180 in `experiments/2026-11-08-m2-real-keystroke/results/lm.json` (15 configurations × the same 12 sentences), 36 in the Toronto sEMG `trust.json`. They are model outputs on public datasets, not typed text. [LICENSES/DATA.md](../../LICENSES/DATA.md) already lists this as a judgement call | Keep, but update LICENSES/DATA.md to name these files. From now on, write example texts to `~/bci-data/derived/` and commit only aggregates |
| H-2 | Commit author e-mail | Every commit carries the maintainer's personal e-mail address in its git metadata. GitHub shows it publicly. Files are clean | Set `git config user.email` to the GitHub `noreply` address for future commits. Do not rewrite history |
| H-3 | Windows home paths in files | 198 tracked files (158 in `experiments/`) contain absolute paths with the Windows user name, mostly in logs and run commands | Low risk. New code and docs should use `~`, `%USERPROFILE%` or `FIDETYPE_*` variables. Do not edit old results |
| H-4 | `agent-memory/` mirror | 8 files: Claude's working notes about the user's preferences and project goals. Public, by design (CLAUDE.md) | Keep if the user is fine with these notes being public. Otherwise ignore the folder and keep the mirror local only |
| H-5 | Archived tracker fragments | `wiki/progress/fragments/archive/` has 100 files (77 kB). `tracker.json` already holds the merged result. The build does not read the archive | Keep for now (small, an audit trail). Option: stop committing the archive and add it to `.gitignore` |
| H-6 | Paper drafts | `papers/paper1/draft-v0.pdf` … `draft-v5*.pdf`: 8 PDFs, 2.5 MB, superseded by `final/`. The LaTeX history is in git anyway | Remove the drafts from the tip (`git rm`), or move them to a GitHub release. Keep `final/` |
| H-7 | Experiment logs | 160 `.log` files (0.5 MB), for example `run.log` and `stdout-*.log`. One is empty: `experiments/2026-11-08-m2-real-keystroke/run.err.log` | Keep: they are cheap provenance. Remove the empty file in a later cleanup. Rule for new runs: commit one `run.log`; do not commit duplicate stdout captures |
| H-8 | Large aggregate results | 14 result JSON files are between 0.4 and 1.4 MB | Keep. For new results over 1 MB, commit a `.json.gz` (as the M2-09 ledger does) |
| H-9 | `HANDOFF.md` size | 117 kB and growing; each update prepends history | Move entries older than a week to `wiki/log.md` or a `HANDOFF-archive.md` |

## 4. Cleanup checklist (run "every now and then")

1. `node tools/hygiene/check.js` — read the errors, warnings and the size table. `--top 30` lists more large files.
2. `node tools/hygiene/links.js` — fix broken links in the user pages.
3. `git status --ignored --short` — check that new tool output is ignored, not just untracked.
4. Look for one-off files: `git ls-files | grep -iE 'tmp|scratch|old|copy|backup|\.bak$'`.
5. Check new experiment folders: per-trial texts stay in `~/bci-data/derived/`; only plan.md, results.md and aggregates are committed.
6. Check the README status lines and counts against the code (`fidetype version`, `fidetype conformance consumer`).
7. Untrack clear junk with `git rm --cached <path>` (keeps the local copy) plus a `.gitignore` rule. Never rewrite history and never force-push. Put debatable items in section 3 of this page.
8. Log the pass in [log.md](../log.md).

## 5. What the CI check enforces

| Rule | Level |
|---|---|
| Caches, virtual envs, build output, OS files, `.env` and key files | error |
| Data and model formats (`.fif`, `.edf`, `.mat`, `.npy`, `.h5`, `.pt`, `.pkl`, `.safetensors`, `.onnx`, ...); `.npz` outside `spec/conformance/` | error |
| `references/papers/`, `references/repos/`, `data/`, `experiments/**/results/trials.json` | error |
| Secret patterns (private key, GitHub, npm, AWS, Slack, `sk-` keys) | error |
| E-mail addresses other than `example.*` and `noreply` | error |
| File over 5 MB | error |
| File over 1 MB; PDF outside `papers/` | warning |
| Broken relative link or anchor in README.md, docs/, SDK READMEs | error (`links.js`) |

Related: [LICENSES/DATA.md](../../LICENSES/DATA.md) · [docs site plan](docs-site-plan.md) · [open-source playbook](open-source-playbook.md)
