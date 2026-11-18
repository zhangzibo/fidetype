# Publishing checklist (first public release)

This page is for the maintainer. It lists every step to publish Fidetype for the first time: the Python package, the TypeScript SDK, the Rust crate, the GitHub Pages site and the GitHub releases. Do the steps in order. Each step has a time estimate, the exact commands, a check and a rollback.

Prepared on 2026-11-18 (task P2-08). Nothing is published yet. The release rules (semver, SDK and spec versions) are in [RELEASING.md](RELEASING.md).

## Summary
| What | Registry or host | Name | Version now | State on 2026-11-18 |
|---|---|---|---|---|
| Python package | PyPI | `fidetype` | 0.0.1 | Built and checked (`twine check --strict` PASS, wheel 2.2 MB, sdist 2.4 MB). Name free. |
| TypeScript SDK | npm | `@fidetype/sdk` | 0.1.0 | `npm pack --dry-run` and `npm publish --dry-run` PASS (53 files, 129.5 kB). Name free; the npm organization `fidetype` must exist first. |
| Rust crate | crates.io | `fidetype` | 0.1.0 | `cargo publish --dry-run --locked` PASS (31 files, 121 KiB compressed). Name free. |
| Static site | GitHub Pages | `https://zhangzibo.github.io/fidetype/` | n/a | Builds with `node tools/site/build.js` into `_site/` (git-ignored). All local links OK. |
| Release notes | GitHub releases | tags `py-v…`, `ts-v…`, `rs-v…` | n/a | Not created. |

Name checks (read-only, no account, 2026-11-18): `https://pypi.org/pypi/fidetype/json` 404, `https://test.pypi.org/pypi/fidetype/json` 404, `https://crates.io/api/v1/crates/fidetype` 404, `https://registry.npmjs.org/@fidetype%2fsdk` 404, `https://registry.npmjs.org/fidetype` 404 (unscoped name also free). A name is not reserved until the first publish. Check again on the day.

Package content checks (2026-11-18): no e-mail address except `@example.org` placeholders in test fixtures; no private keys or tokens; no PDFs, recordings, model weights or per-trial texts. The only data files are the synthetic golden vectors (`.npz`, `.jsonl`) and the benchmark split files (hashed ids and public truth words).

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

## A. Decisions you must make (15 min)
Write your answer next to each item. Claude can then make the release commit (step C1) for you.

| # | Decision | Options | Recommendation |
|---|---|---|---|
| D1 | Which packages this weekend | all three; Python only; Python + site | All three. They are ready, and the names are free today. |
| D2 | Python version | keep `0.0.1`; use `0.1.0` like the TypeScript and Rust SDKs | `0.1.0` for all three: one number is easier to explain. `0.0.x` signals "not usable yet". |
| D3 | npm name | `@fidetype/sdk` (needs the npm organization `fidetype`); unscoped `fidetype` (also free) | `@fidetype/sdk`: the scope also protects later packages (`@fidetype/…`). Create the organization even if you choose the unscoped name. |
| D4 | Licence of the spec text (roadmap P9-01, open) | Apache-2.0 like the code (today); CC BY 4.0; Open Web Foundation Agreement | Keep Apache-2.0 for this release; the sdist ships `spec/` under the repository licence. A later change to a more open licence is still possible for new versions. |
| D5 | Copyright line in `LICENSE` (appendix) | `Copyright 2026 zhangzibo` (today); `Copyright 2026 Zibo Zhang` | `Zibo Zhang`, the same as the package metadata (`authors`). Same change in `sdk/typescript/LICENSE` and `sdk/rust/LICENSE`. |
| D6 | Progress dashboard on the public site | include (today); leave out | Your choice. It shows task times and agent token counts. To leave it out, delete the `progress` entry in `SECTIONS` of `tools/site/build.js`. |
| D7 | First Python upload | TestPyPI first; PyPI directly | TestPyPI first (10 extra minutes). A PyPI version number can never be used again. |
| D8 | Upload method | trusted publishing from GitHub Actions (no token on disk); API token on your computer | Trusted publishing for PyPI (works for the first upload). npm and crates.io need one manual first upload; then add trusted publishing. |
| D9 | Supported Python | `>=3.12` (today; CI tests 3.12 on Linux only, gap 60 = P2-09) | Keep. Say "tested on 3.12" in the release notes. |

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
The site is the pages that exist today: a plain landing page, the benchmark leaderboard, the synthetic trust demo, the diagrams and the progress dashboard. Docs and the spec are links to GitHub (Markdown is not rendered on the site yet: roadmap P8-01). The original UI is roadmap P8-05.

| Step | Do this | Check |
|---|---|---|
| G-1 (2 min) | Local preview: `node tools/site/build.js`, then open `_site/index.html` in a browser. | "local links: all OK". |
| G-2 (2 min) | Settings → Pages → Build and deployment → Source: **GitHub Actions**. | The page shows "GitHub Actions" as the source. |
| G-3 (5 min) | Actions → `pages` → Run workflow (branch `main`). The workflow [.github/workflows/pages.yml](../.github/workflows/pages.yml) never runs by itself. | The `deploy` job shows the URL `https://zhangzibo.github.io/fidetype/`. Open it and click each page. |
| G-4 (1 min) | Optional: add the URL to the repository "About" box (Website). | The link shows on the repository page. |

To update the site later, run the `pages` workflow again. **Rollback:** Settings → Pages → "Unpublish site", or run the workflow from an older commit.

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
- [ ] No page shows an e-mail address.
- [ ] Ask Claude to record the release: tracker items P2-07 and M7-09 `done`, `## [Unreleased]` headings back in the changelogs, RELEASING.md section 3.1 (names: taken by us), HANDOFF.md.

## Files that support this checklist
| File | Purpose |
|---|---|
| [RELEASING.md](RELEASING.md) | Release rules: semver, SDK and spec versions, package contents. |
| [.github/workflows/release.yml](../.github/workflows/release.yml) | Manual-only release workflow (PyPI with OIDC and attestations, npm with provenance, crates.io with OIDC). |
| [.github/workflows/pages.yml](../.github/workflows/pages.yml) | Manual-only Pages deploy of `node tools/site/build.js`. |
| `tools/site/build.js` | Assembles the site into `_site/` and checks every local link offline (exit 1 on a broken link). |
| `tests/test_publishing_metadata.py` | Checks the author, URLs, licence, versions, no e-mail, manual-only workflows and the site build. |
