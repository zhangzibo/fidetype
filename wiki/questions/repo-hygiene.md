---
title: Repository hygiene (what to commit, cleanup checklist)
type: question
tags: [repo, hygiene, ci, privacy, licences, maintenance]
sources: []
updated: 2026-11-15
---

# Repository hygiene

**Question (2026-11-15, task R-23):** Do we commit files that we do not need? What must never be in the public repository? How do we check this again later?

**Short answer:** The tracked tree is clean of the dangerous classes: no caches, no build output, no recordings, no weights, no secrets, no third-party PDFs or code, no private e-mail addresses in files. The size is 45 MB in 1,836 files; 26 MB of it is `experiments/`. Nothing had to be removed. The audit added `.gitignore` rules, a check script and a CI job. Nine judgement calls followed; R-24 (2026-11-15) decided and applied all nine (section 3).

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

## 3. Judgement calls and decisions

The R-23 audit left nine judgement calls (H-1 … H-9). The user let the orchestrator decide them. Task R-24 applied the decisions on 2026-11-15.

| # | Item | Facts (R-23) | Decision and status (R-24, 2026-11-15) |
|---|---|---|---|
| H-1 | Example decoded texts in experiment results | 9 committed JSON files hold example pairs (stimulus sentence + decoded top-1 text): 30 in each of 6 MEG beam result files, 180 in `experiments/2026-11-08-m2-real-keystroke/results/lm.json`, 96 in `.../run1-uncalibrated-b/lm.json`, 36 in the Toronto sEMG `trust.json`. Model outputs on public datasets, not typed text | **Done.** The files stay. [LICENSES/DATA.md](../../LICENSES/DATA.md) names all 9 with their source licence. New rule (DATA.md, [CONTRIBUTING.md](../../CONTRIBUTING.md), checklist item 5): new experiments do not commit per-trial decoded or stimulus text; aggregates only |
| H-2 | Commit author e-mail | Past commits carry the maintainer's personal e-mail address in their git metadata. Files are clean | **Done.** Switched to the GitHub noreply address on 2026-11-15 (repository-local `git config user.email`); past commits unchanged (no history rewrite). The user can also turn on the GitHub settings "Keep my email addresses private" and "Block command line pushes that expose my email" (Settings → Emails) |
| H-3 | Windows home paths in files | 198 tracked files (158 in `experiments/`) contain absolute paths with the Windows user name, mostly in logs and run commands | **Decided: rule for the future** (checklist item 9). Old results stay unchanged |
| H-4 | `agent-memory/` mirror | 8 files: Claude's working notes about the user's preferences and project goals | **Done.** Untracked (`git rm -r --cached`), added to `.gitignore`. The local mirror stays; `tools/session/snapshot.js` still writes it. CLAUDE.md marks it "local only, not committed". Git history keeps the old copies |
| H-5 | Archived tracker fragments | `wiki/progress/fragments/archive/`: 101 files. `tracker.json` holds the merged result. `build.js` only moves fragments into the archive; it never reads it | **Done.** Untracked (`git rm -r --cached`), added to `.gitignore`. Local copies stay |
| H-6 | Paper drafts | `papers/paper1/draft-v0.pdf` … `draft-v5*.pdf`: 8 PDFs, 2.5 MB, superseded by `final/` (v6) | **Done.** Removed from the tree with `git rm` (8 files, 2,537,048 bytes). `final/` and the LaTeX source stay. Git history keeps the drafts (`git show 59661ca:papers/paper1/draft-v5.pdf`). Paper README, guide and [paper1-plan](paper1-plan.md) updated |
| H-7 | Experiment logs | 160 `.log` files (0.5 MB). One was empty: `experiments/2026-11-08-m2-real-keystroke/run.err.log` | **Done.** The empty log is removed; the other logs stay. Rule for new runs (checklist item 10) |
| H-8 | Large aggregate results | 14 result JSON files are between 0.4 and 1.4 MB | **Decided: rule for the future** (checklist item 11). Existing files stay |
| H-9 | `HANDOFF.md` size | 117 kB and growing | **Done + rule.** Entries before 2026-11-13 moved to [docs/archive/handoff-2026-11-08-to-2026-11-12.md](../../docs/archive/handoff-2026-11-08-to-2026-11-12.md) (text unchanged). HANDOFF.md now holds the current status, running jobs, how to resume and the recent updates (120 kB → 58 kB). Rule (checklist item 12) |

## 4. Cleanup checklist (run "every now and then")

1. `node tools/hygiene/check.js` — read the errors, warnings and the size table. `--top 30` lists more large files.
2. `node tools/hygiene/links.js` — fix broken links in the user pages.
3. `git status --ignored --short` — check that new tool output is ignored, not just untracked.
4. Look for one-off files: `git ls-files | grep -iE 'tmp|scratch|old|copy|backup|\.bak$'`.
5. Check new experiment folders (H-1 rule): per-trial decoded or stimulus texts stay in `~/bci-data/derived/`; only plan.md, results.md and aggregate numbers are committed.
6. Check the README status lines and counts against the code (`fidetype version`, `fidetype conformance consumer`).
7. Untrack clear junk with `git rm --cached <path>` (keeps the local copy) plus a `.gitignore` rule. Never rewrite history and never force-push. Put debatable items in section 3 of this page.
8. Log the pass in [log.md](../log.md).
9. **Home paths (H-3):** new code, docs and run commands use `~`, `%USERPROFILE%` or the `FIDETYPE_*` variables, not `C:Users<name>...`. Do not edit old results.
10. **Logs (H-7):** a new run commits one `run.log`. Do not commit duplicate stdout captures or empty logs.
11. **Large results (H-8):** a new result file over 1 MB is committed as `.json.gz` (as the M2-09 ledger does), or kept outside the repository.
12. **HANDOFF size (H-9):** keep `HANDOFF.md` short: current status, running jobs, how to resume, about one week of recent updates. Move older entries to `docs/archive/handoff-<from>-to-<to>.md` without changing the text. `node tools/session/start.js` must still print a useful summary.

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
