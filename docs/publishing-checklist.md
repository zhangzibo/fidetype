# Publishing checklist (first public release)

> **Status: done 2026-11-21.** Release 0.1.0 is public. PyPI: https://pypi.org/project/fidetype/. npm: https://www.npmjs.com/package/@fidetype/sdk. crates.io: https://crates.io/crates/fidetype (docs: https://docs.rs/fidetype/0.1.0). Site: https://zhangzibo.github.io/fidetype/. GitHub releases: https://github.com/zhangzibo/fidetype/releases/tag/py-v0.1.0, https://github.com/zhangzibo/fidetype/releases/tag/ts-v0.1.0, https://github.com/zhangzibo/fidetype/releases/tag/rs-v0.1.0. The site now deploys by itself on every push to `main` (section G). The steps below are kept as the record and as a model for the next release. For the next npm or crates.io release, see [RELEASING.md](RELEASING.md) section 3.1 (trusted publishers, token expiry 2026-11-28).

This page is for the maintainer. It lists every step to publish Fidetype for the first time: the Python package, the TypeScript SDK, the Rust crate, the GitHub Pages site and the GitHub releases. Do the steps in order. Each step has a time estimate, the exact commands, a check and a rollback.

Prepared on 2026-11-18 (task P2-08). Rechecked on 2026-11-21 (pre-flight). Published on 2026-11-21 (see the status line above). The release rules (semver, SDK and spec versions) are in [RELEASING.md](RELEASING.md).

## Summary
| What | Registry or host | Name | Version now | State on 2026-11-21 |
|---|---|---|---|---|
| Python package | PyPI | `fidetype` | 0.1.0 | Built and checked (`twine check --strict` PASS, wheel 2.7 MB, sdist 2.7 MB). Name free. |
| TypeScript SDK | npm | `@fidetype/sdk` | 0.1.0 | `npm pack --dry-run` and `npm publish --dry-run` PASS (53 files, 130.5 kB). Name free; the npm organization `fidetype` must exist first. |
| Rust crate | crates.io | `fidetype` | 0.1.0 | `cargo publish --dry-run --locked` PASS (31 files, 122 KiB compressed). Name free. |
| Static site | GitHub Pages | `https://zhangzibo.github.io/fidetype/` | n/a | Builds with `node tools/site/build.js` into `_site/` (git-ignored). All local links OK. |
| Release notes | GitHub releases | tags `py-v…`, `ts-v…`, `rs-v…` | n/a | Not created. |

Name checks (read-only, no account, 2026-11-18; again 2026-11-21: all 404): `https://pypi.org/pypi/fidetype/json` 404, `https://test.pypi.org/pypi/fidetype/json` 404, `https://crates.io/api/v1/crates/fidetype` 404, `https://registry.npmjs.org/@fidetype%2fsdk` 404, `https://registry.npmjs.org/fidetype` 404 (unscoped name also free). A name is not reserved until the first publish. Check again on the day.

Package content checks (2026-11-18; again 2026-11-21): no e-mail address except `@example.org` placeholders in test fixtures; no private keys or tokens; no PDFs, recordings, model weights or per-trial texts. The only data files are the synthetic golden vectors (`.npz`, `.jsonl`), the benchmark split files and overlap maps (hashed ids; the research-only splits carry no text), the aggregate benchmark results and the pretrained manifests (no weights).

## Total time
| Part | Minutes |
|---|---|
| A. Decisions (below) | 15 |
| B. Accounts and 2FA | 30 |
| C. Release commit and tags | 15 |
| D. Python to TestPyPI, then PyPI | 25 |
| E. npm | 15 |
| F. crates.io | 15 |
| G. GitHub Pages | 10 |
| H. GitHub releases | 10 |
| I. Final checks | 10 |
| **Total** | **about 2 h 25 min** (1 h 15 min if you publish only Python and the site) |
| J. Pretrained weights (optional, P14-02; not in the total) | 45 |

## A. Decisions you must make (15 min)
Write your answer next to each item. Claude can then make the release commit (step C1) for you.

| # | Decision | Options | Recommendation |
|---|---|---|---|
| D1 | Which packages this weekend | all three; Python only; Python + site | All three. They are ready, and the names are free today. |
| D2 | Python version | keep `0.0.1`; use `0.1.0` like the TypeScript and Rust SDKs | `0.1.0` for all three: one number is easier to explain. `0.0.x` signals "not usable yet". |
| D3 | npm name | `@fidetype/sdk` (needs the npm organization `fidetype`); unscoped `fidetype` (also free) | `@fidetype/sdk`: the scope also protects later packages (`@fidetype/…`). Create the organization even if you choose the unscoped name. |
| D4 | Licence of the spec text (roadmap P9-01, open) | Apache-2.0 like the code (today); CC BY 4.0; Open Web Foundation Agreement | Keep Apache-2.0 for this release; the sdist ships `spec/` under the repository licence. A later change to a more open licence is still possible for new versions. |
| D5 | Copyright line in `LICENSE` (appendix) | `Copyright 2026 zhangzibo` (today); `Copyright 2026 Zibo Zhang` | `Zibo Zhang`, the same as the package metadata (`authors`). Same change in `sdk/typescript/LICENSE` and `sdk/rust/LICENSE`. |
| D6 | Progress dashboard on the public site | include (today); leave out | Your choice. It shows task times and agent token counts. To leave it out, set `INCLUDE_PROGRESS = false` in `tools/site/build.js`. |
| D7 | First Python upload | TestPyPI first; PyPI directly | TestPyPI first (10 extra minutes). A PyPI version number can never be used again. |
| D8 | Upload method | trusted publishing from GitHub Actions (no token on disk); API token on your computer | Trusted publishing for PyPI (works for the first upload). npm and crates.io need one manual first upload; then add trusted publishing. |
| D9 | Supported Python | `>=3.12`. CI tests 3.12, 3.13, 3.14 on Linux, 3.12 and 3.13 on Windows, 3.13 on macOS (P2-09) | Keep. Say "tested on 3.12-3.14 (Linux), Windows and macOS" in the release notes. |

## B. Accounts and 2FA (30 min, once)
| Step | Do this | Check |
|---|---|---|
| B1 (10 min) | PyPI: create an account at <https://pypi.org/account/register/>. Turn on 2FA (an authenticator app or a security key). Save the recovery codes. Do the same on <https://test.pypi.org> (a separate account). | You can log in with 2FA on both sites. |
| B2 (5 min) | PyPI trusted publishing: <https://pypi.org/manage/account/publishing/> → "Add a new pending publisher": PyPI project `fidetype`, owner `zhangzibo`, repository `fidetype`, workflow `release.yml`, environment `release-pypi`. Do the same on TestPyPI (<https://test.pypi.org/manage/account/publishing/>). | The pending publisher is in the list. |
| B3 (10 min) | npm: create an account at <https://www.npmjs.com/signup>. Turn on 2FA ("Authorization and writes"). Create the organization `fidetype` (<https://www.npmjs.com/org/create>, free plan for public packages). On your computer: `npm login` (opens the browser). | `npm whoami` prints your npm user name. |
| B4 (5 min) | crates.io: log in at <https://crates.io> with your GitHub account. Verify your e-mail address in Account Settings (crates.io needs it to publish; the address is not shown on the crate page). Create an API token: scope `publish-new` and `publish-update`, crate pattern `fidetype`, expiry 7 days. | The token is shown once. Keep it in a password manager, not in a file in the repository. |
| B5 (5 min) | GitHub: Settings → Environments → create `release-pypi`, `release-npm`, `release-crates`. For each: Required reviewers = you; Deployment branches and tags = Selected → `main`. | Three environments, each with you as reviewer. |

Never put a token, a password or your e-mail address in a file of this repository. The hygiene check (`node tools/hygiene/check.js`) fails on private e-mail addresses and tokens.

## C. Release commit and tags (15 min)
C1. **Release commit.** You can ask Claude: "cut release 0.1.0 for all three SDKs" with your decisions D2, D4, D5. By hand:

1. Python: set `__version__ = "0.1.0"` in `src/fidetype/__init__.py` and `version: 0.1.0` plus `date-released` in `CITATION.cff` (a test checks that the two agree).
2. In each changelog (`CHANGELOG.md`, `sdk/typescript/CHANGELOG.md`, `sdk/rust/CHANGELOG.md`): merge `[Unreleased]` and the old "not published" entry into `## [0.1.0] - 2026-11-21`. List the spec versions and profiles (rule SDK-V1 in RELEASING.md). Add an empty `## [Unreleased]` above it.
3. TypeScript and Rust are already 0.1.0. If you change them: `version` in `sdk/typescript/package.json` and `SDK_VERSION` in `sdk/typescript/src/index.ts` (`npm run check:version`); `version` in `sdk/rust/Cargo.toml`, then `cargo update -p fidetype` in `sdk/rust`.
4. Update the matrix in spec section 11.7 (`spec/nts-1.0-rc4.md`) if a version changed.
4b. Install text in the READMEs and docs. Each registry page keeps the README of its upload, so the text must be true before and after the upload: "From 0.1.0: `pip install fidetype`" (`npm install @fidetype/sdk`, `cargo add fidetype`). Keep the clone path for development. **Done** in the release commit of 2026-11-21 (`README.md`, `sdk/typescript/README.md`, `sdk/rust/README.md`, `docs/sdks.md`, `docs/README.md`, `docs/getting-started.md`, `docs/trust-quickstart.md`).
5. Run the tests: `uv run pytest -q`. Commit, push, wait for CI to be green (all jobs, `packaging` included).

C2. **Local dry run** (optional; CI job `packaging` does the same):
```bash
uvx --from build pyproject-build --installer uv --outdir dist . && uvx twine check --strict dist/*
cd sdk/typescript && npm ci && npm run ci && npm pack --dry-run && cd ../..
cd sdk/rust && cargo test --locked && cargo publish --dry-run --locked && cd ../..
node tools/site/build.js
```

C3. **Tags** (on the green release commit on `main`):
```bash
git pull
git tag -a py-v0.1.0 -m "fidetype 0.1.0 (Python)"
git tag -a ts-v0.1.0 -m "@fidetype/sdk 0.1.0"
git tag -a rs-v0.1.0 -m "fidetype 0.1.0 (Rust crate)"
git push origin py-v0.1.0 ts-v0.1.0 rs-v0.1.0
```
A tag push starts no workflow. Check: `git ls-remote --tags origin` lists the three tags. Rollback (before any upload only): `git push --delete origin py-v0.1.0` and `git tag -d py-v0.1.0`.

## D. Python: TestPyPI, then PyPI (25 min)
The workflow [.github/workflows/release.yml](../.github/workflows/release.yml) never runs by itself. Its only trigger is "Run workflow" in the Actions tab. Each upload waits for your approval in the protected environment.

| Step | Do this | Check |
|---|---|---|
| D-1 (5 min) | Actions → `release` → Run workflow (Use workflow from: `main`): sdk `python`, tag `py-v0.1.0`, target `dry-run`. | The job `python-build` is green; the artifact `python-dist` holds one `.whl` and one `.tar.gz`. |
| D-2 (5 min) | Run again with target `testpypi`. Approve the `release-pypi` deployment. | <https://test.pypi.org/project/fidetype/> shows 0.1.0, the README, the licence `Apache-2.0` and the author `Zibo Zhang`. |
| D-3 (5 min) | Test the install in a new folder: `uv venv t && uv pip install --python t --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ fidetype==0.1.0`, then `t/Scripts/fidetype --help` (Linux/macOS: `t/bin/fidetype`) and `t/Scripts/fidetype conformance --profile fep-0001`. | The help text prints; "66/66 golden vectors" PASS. |
| D-4 (5 min) | Run again with target `pypi`. Approve. | <https://pypi.org/project/fidetype/> shows 0.1.0 with a green "verified" attestation mark. |
| D-5 (5 min) | `uv venv p && uv pip install --python p fidetype==0.1.0` and run the two commands of D-3. | Same output. |

Fallback without the workflow (needs a PyPI API token; 2FA protects the account, the token protects the upload):
```bash
uvx --from build pyproject-build --installer uv --outdir dist .
uvx twine check --strict dist/*
uvx twine upload --repository testpypi dist/*     # then: uvx twine upload dist/*
```

**Rollback:** PyPI → Your projects → fidetype → Manage → Releases → Options → **Yank** (pip no longer picks the version unless it is pinned; you can un-yank). Do not delete: a deleted version number can never be uploaded again. Fix forward with 0.1.1.

## E. npm (15 min)
npm trusted publishing needs a package that already exists, so the first upload is manual.

| Step | Do this | Check |
|---|---|---|
| E-1 (5 min) | `git checkout ts-v0.1.0 && cd sdk/typescript && npm ci && npm run ci && npm pack --dry-run` | 53 files, about 130 kB; no `test/`, no `src/`, no vectors. |
| E-2 (3 min) | `npm publish --access public --provenance=false` (npm asks for your 2FA code). `--provenance=false` is needed because npm makes a provenance statement only in CI. | `npm view @fidetype/sdk version` prints `0.1.0`. |
| E-3 (5 min) | In a new folder: `npm init -y && npm install @fidetype/sdk@0.1.0 && npx fidetype-ts --help`. Go back: `cd ../.. && git checkout main`. | The help text prints. |
| E-4 (2 min) | <https://www.npmjs.com/package/@fidetype/sdk> → Settings → Trusted publisher: GitHub Actions, owner `zhangzibo`, repository `fidetype`, workflow `release.yml`, environment `release-npm`. Later releases then run from the workflow (target `publish`) with provenance and no token. | The trusted publisher is saved. |

**Rollback:** `npm deprecate @fidetype/sdk@0.1.0 "use 0.1.1"` (the normal way). `npm unpublish @fidetype/sdk@0.1.0` works only in the first 72 hours and if nothing depends on it; the version number can never be used again.

## F. crates.io (15 min)
The first upload is manual too.

| Step | Do this | Check |
|---|---|---|
| F-1 (5 min) | `git checkout rs-v0.1.0 && cd sdk/rust && cargo test --locked && cargo publish --dry-run --locked` | "aborting upload due to dry run"; 31 files. |
| F-2 (3 min) | `cargo publish --locked --token <TOKEN>` (paste the token from B4; do not save it in `~/.cargo/credentials.toml` if you do not want it on disk). Then revoke the token on crates.io. Go back: `cd ../.. && git checkout main`. | <https://crates.io/crates/fidetype> shows 0.1.0. |
| F-3 (5 min) | In a new folder: `cargo new t && cd t && cargo add fidetype@0.1.0 && cargo build`. Check <https://docs.rs/fidetype> after about 10 minutes (docs.rs builds the docs). | The build passes; docs.rs shows the API. |
| F-4 (2 min) | crates.io → fidetype → Settings → Trusted Publishing: GitHub, owner `zhangzibo`, repository `fidetype`, workflow `release.yml`, environment `release-crates`. | Saved. |

**Rollback:** `cargo yank --version 0.1.0 fidetype` (new projects can no longer depend on it; `cargo yank --version 0.1.0 --undo fidetype` reverses it). A crate cannot be deleted, except in narrow cases of the crates.io policy.

## G. GitHub Pages (10 min)
The project site (hub decision Q6, built locally on 2026-11-18, rebuilt 2026-11-21: 77 files, includes `docs/device-support.md` and the tutorials; P13-08): a landing page (what Fidetype is, the north star, quick start), the benchmark overview and leaderboard (safe WPM v0.2 marked PROPOSED), the hub dataset registry, the docs and the NTS spec rendered from Markdown, the certified conformance list, the synthetic trust demo, the diagrams and the progress dashboard. `node tools/site/build.js` generates every page from repository files. It has no trackers and no external scripts. A fuller docs site is roadmap P8-05.

| Step | Do this | Check |
|---|---|---|
| G-1 (2 min) | Local preview: `node tools/site/build.js`, then open `_site/index.html` in a browser. Click Home, Benchmark, Hub, Docs, Spec and Conformance. Make the browser narrow (phone width) once. | "local links: all OK". Safe WPM v0.2 shows PROPOSED (or ADOPTED, if you adopt it this weekend and the docs say so). D6: set `INCLUDE_PROGRESS = false` in `tools/site/build.js` if you do not want the dashboard public. |
| G-2 (2 min) | Settings → Pages → Build and deployment → Source: **GitHub Actions**. | The page shows "GitHub Actions" as the source. |
| G-3 (5 min) | Actions → `pages` → Run workflow (branch `main`). Since 2026-11-21 the workflow [.github/workflows/pages.yml](../.github/workflows/pages.yml) also runs by itself on every push to `main` (never from a pull request). | The `deploy` job shows the URL `https://zhangzibo.github.io/fidetype/`. Open it and click each page. |
| G-4 (1 min) | Optional: add the URL to the repository "About" box (Website). | The link shows on the repository page. |

The site updates by itself on every push to `main`. You can also run the `pages` workflow by hand. **Rollback:** Settings → Pages → "Unpublish site", or run the workflow from an older commit.

## H. GitHub releases (10 min)
One release per tag, with the changelog entry as the text:
```bash
gh release create py-v0.1.0 --title "fidetype 0.1.0 (Python)" --notes-file <(sed -n '/^## \[0.1.0\]/,/^## \[/p' CHANGELOG.md | sed '$d')
gh release create ts-v0.1.0 --title "@fidetype/sdk 0.1.0" --notes-file <(sed -n '/^## \[0.1.0\]/,/^## \[/p' sdk/typescript/CHANGELOG.md | sed '$d')
gh release create rs-v0.1.0 --title "fidetype 0.1.0 (Rust crate)" --notes-file <(sed -n '/^## \[0.1.0\]/,/^## \[/p' sdk/rust/CHANGELOG.md | sed '$d')
```
Optional: attach the Python files (`gh release upload py-v0.1.0 dist/*`). Mark the releases as pre-releases (`--prerelease`) if you want to show the pre-alpha status. **Rollback:** `gh release delete py-v0.1.0` (the tag stays).

## I. Final checks (10 min)
- [ ] The README badge and install lines work: `pip install fidetype`, `npm install @fidetype/sdk`, `cargo add fidetype`.
- [ ] The PyPI, npm and crates.io pages show the README with working links (the SDK READMEs use absolute GitHub links since 2026-11-18).
- [ ] No page shows an e-mail address. (The vendored draw.io viewer JS, `diagrams/viewer-static.min.js`, holds the jgraph support address in its code. It is not shown on any page.)
- [ ] Ask Claude to record the release: tracker items P2-07 and M7-09 `done`, `## [Unreleased]` headings back in the changelogs, RELEASING.md section 3.1 (names: taken by us), HANDOFF.md.

## J. Pretrained weights (optional, 45 min; roadmap P14-02)
The package has a registry of pretrained decoders (`fidetype decoders list`, [pretrained-decoders.md](pretrained-decoders.md)). Each model has a manifest with a SHA-256, a size and an empty `url` slot. The weights are **not** in the wheel or the repository, and no file is hosted yet. This section is the hosting step. You can skip it this weekend: the package works without it (users then pass `weights=<folder>`).

| # | Decision | Options | Recommendation |
|---|---|---|---|
| D10 | Host of the weights | GitHub release assets (tag `weights-v1`, 2 GB limit per file); Hugging Face Hub model repositories; both | GitHub release assets for the clean models: no new account, and the files stay next to the code. A model hub later if users ask. |
| D11 | Licence of our clean weights | CC0-1.0 (like the T15 / T12 data); Apache-2.0 (like the code); CC-BY-4.0 where the data needs attribution | CC0-1.0 for `t15-m4-13`, `t12-v2` and `willett-hw`; CC-BY-4.0 for `kt-semg-lda` (keeps the Nokia attribution). Then change rule 1 of [`LICENSES/DATA.md`](../LICENSES/DATA.md) ("no trained weights") to "weights only as separate release assets, never in the repository or the wheel". |
| D12 | Research-only weights (`emg2qwerty-p11-01`, CC BY-NC-SA 4.0) | do not host; host separately behind a licence page | Do not host this weekend. Later, if at all: a separate release (never with the clean weights), the licence text next to the file, and the package keeps the `accept_research_only=True` gate. The weights keep the share-alike terms. |

Licence check per model (do this before any upload):

| Model | Files (local folder `C:\Users\zhang\bci-data\pretrained\<model>\`) | Training data licence | Weights licence (proposal) | Host now? | Check |
|---|---|---|---|---|---|
| `t15-m4-13` | `t15-m4-13.weights.npz` (182 MB) + 3 text files of the guard (8 MB, in `pretrained\text\`) | CC0 1.0 (Card et al. 2024) | CC0-1.0 | yes (clean) | The text files are not weights: `cmudict.dict` (BSD-2-Clause style: put its licence file next to it), `eng_tatoeba_6gram_mkn.npz` and `eng_tatoeba_word_counts.json` (CC BY 2.0 FR: keep the Tatoeba attribution). |
| `t12-v2` | `t12-v2.weights.npz` (340 MB) | CC0 1.0 (Willett et al. 2023) | CC0-1.0 | yes (clean) | none |
| `kt-semg-lda` | `kt-semg-lda.model.json`, `.weights.json`, `.guard.json` (0.1 MB) | CC BY 4.0 (Nokia) | CC-BY-4.0 | yes (attribution in the release notes and the card) | The card already holds the attribution line. |
| `emg2qwerty-p11-01` | `emg2qwerty-p11-01.weights.npz` (35 MB) | CC BY-NC-SA 4.0 | CC-BY-NC-SA-4.0 (required) | **no** (D12) | Never in the same release as the clean weights. |
| `willett-hw` | `willett-hw.weights.npz` (34 MB) | CC0 1.0 (Willett et al. 2021) | CC0-1.0 (provisional until D11) | yes (clean), if D11 = CC0 | Trained on Willett CC0 data only (P15-08 run R-all-s0, random init). A weak decoder (greedy CER 0.305): the card says so. |
| `toronto-semg-cnn` | none (planned) | CC BY 4.0 | n/a | no | No weights yet. |

| Step | Do this | Check |
|---|---|---|
| J-1 (5 min) | Decide D10-D12. Tell Claude the decisions. Claude records them on the roadmap (P14-02) and changes DATA.md rule 1. | The decisions are in the wiki. |
| J-2 (10 min) | `.venv\Scripts\python.exe -I tools/pretrained/export_weights.py --list` prints the SHA-256 and the size of each local file. Compare them with `fidetype decoders info <model> --json`. | Every file matches its manifest. |
| J-3 (15 min) | GitHub → Releases → Draft a new release: tag `weights-v1`, title "Pretrained decoders v1 (weights only)". Attach the files of the clean models only (table above), plus a `LICENSE-WEIGHTS.md` with the licence and the attribution of each file. Publish. | The release page lists the files with their sizes. No `emg2qwerty` file. |
| J-4 (10 min) | Ask Claude to put the asset URLs into the `url` fields of the manifests (`src/fidetype/pretrained/manifests/*.json`) and to run the download test. | `fidetype decoders verify <model>` passes after a `download=True` load into an empty cache. |
| J-5 (5 min) | Test from a clean folder: `pip install fidetype`, then in Python: `import fidetype.pretrained as p; m = p.load("t15-m4-13", download=True)`. | The SHA-256 check passes; `print(m.card())` prints the card. |

## Files that support this checklist
| File | Purpose |
|---|---|
| [RELEASING.md](RELEASING.md) | Release rules: semver, SDK and spec versions, package contents. |
| [.github/workflows/release.yml](../.github/workflows/release.yml) | Manual-only release workflow (PyPI with OIDC and attestations, npm with provenance, crates.io with OIDC). |
| [.github/workflows/pages.yml](../.github/workflows/pages.yml) | Pages deploy of `node tools/site/build.js`: on every push to `main`, or by hand. |
| `tools/site/build.js` | Assembles the site into `_site/` and checks every local link offline (exit 1 on a broken link). |
| `tests/test_publishing_metadata.py` | Checks the author, URLs, licence, versions, no e-mail, manual-only workflows and the site build. |
