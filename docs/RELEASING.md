# Releasing the Fidetype SDKs

This page tells a maintainer how to version and publish the three reference SDKs. **Publishing is a maintainer decision.** No automation in this repository publishes anything by itself. The weekend step-by-step guide (accounts, commands, checks, rollback, time per step) is [docs/publishing-checklist.md](publishing-checklist.md).

| SDK | Folder | Registry | Package name | Version source of truth | Changelog |
|---|---|---|---|---|---|
| Python | `/` (`src/fidetype/`) | PyPI | `fidetype` | `__version__` in `src/fidetype/__init__.py` (hatch reads it) | [CHANGELOG.md](../CHANGELOG.md) |
| TypeScript | `sdk/typescript/` | npm | `@fidetype/sdk` | `version` in `package.json` (= `SDK_VERSION` in `src/index.ts`; `npm run check:version` compares them) | [sdk/typescript/CHANGELOG.md](../sdk/typescript/CHANGELOG.md) |
| Rust | `sdk/rust/` | crates.io | `fidetype` | `version` in `Cargo.toml` (`SDK_VERSION` = `CARGO_PKG_VERSION`) | [sdk/rust/CHANGELOG.md](../sdk/rust/CHANGELOG.md) |

The spec has its own version and changelog: [spec/CHANGELOG.md](../spec/CHANGELOG.md).

## 1. Versioning policy

### 1.1 Semantic versioning per SDK
Each SDK has its own [semver](https://semver.org/) version. One SDK can release without the others.

| Phase | MAJOR | MINOR | PATCH |
|---|---|---|---|
| **0.x** (now) | stays 0 | a breaking API change, or a new spec or profile support | a bug fix, a new check that only adds a warning, docs |
| **1.x and later** | a breaking API change | a new feature, a new spec minor version or profile | a bug fix |

- In 0.x, users must pin the minor version (`fidetype~=0.1.0`, `"@fidetype/sdk": "~0.1.0"`, `fidetype = "0.1"` in Cargo, which Cargo reads as `>=0.1.0, <0.2.0`).
- A change in a verdict on a golden vector is a **breaking** change, unless the spec changed the rule (then it follows section 1.2).
- Pre-releases use the registry form: Python `0.2.0rc1`, npm and Cargo `0.2.0-rc.1`.
- A version number is never reused. To fix a bad release, publish a new patch version. Yank (PyPI, crates.io) or deprecate (npm) the bad one; do not delete it.

### 1.2 SDK versions and spec versions
SDK versions are separate from spec versions (spec section 11.7). The rules:

- **SDK-V1.** Each SDK release lists, in its changelog entry, the spec versions it reads and writes and the profiles it claims. The matrix in spec section 11.7 ([spec/nts-1.0-rc4.md](../spec/nts-1.0-rc4.md#117-sdk-and-spec-compatibility-matrix)) is updated in the same pull request.
- **SDK-V2.** Support for a new spec **minor** version (for example 1.1) is an SDK **minor** release. Readers already accept `"1.<minor>"` (VER-3), so old SDKs keep working on new streams.
- **SDK-V3.** Support for a new spec **major** version (for example 2.0) is an SDK **major** release (or a minor release while the SDK is 0.x).
- **SDK-V4.** A change of the **default written** `spec_version` (today `"0.1"`; later `"1.0"`) is a breaking change: it is a minor release in 0.x and a major release from 1.0.
- **SDK-V5.** An SDK reaches **1.0** only after spec 1.0 is final and the SDK passes 100 % of the conformance kit (roadmap P2 exit criteria).
- **SDK-V6.** An SDK that claims a profile passes all golden vectors of that profile in CI. The parity jobs (Python = TypeScript = Rust) stay green.

### 1.3 What goes into each package
| Package | Contains | Does not contain |
|---|---|---|
| Python wheel | `fidetype` package, `py.typed`, benchmark split files, demo config, golden vectors (`fidetype/_spec/conformance`, about 1.5 MB, synthetic), aggregate benchmark results, pretrained manifests and guard (no weights), hub dataset registry | tests, data, `.pt` files, participant data, research experiments |
| Python sdist | package, tests, examples, `spec/`, README, LICENSE, CHANGELOG, CITATION.cff | `sdk/`, `wiki/`, `experiments/`, `data/` |
| npm tarball | `dist/**/*.js`, `dist/**/*.d.ts`, `bin/`, README, CHANGELOG, LICENSE (about 120 kB) | tests, golden vectors, scripts, sources |
| Rust `.crate` | `src/**/*.rs`, `Cargo.toml`, `Cargo.lock`, README, CHANGELOG, LICENSE (about 110 KiB) | tests, examples, golden vectors |

The npm and Rust packages do not ship the golden vectors. Their conformance CLIs need `--vectors DIR` (`spec/conformance/` of a repository checkout) when they run outside the repository.

## 2. Release checklist (one SDK)
Do these steps for each SDK that you release. `X.Y.Z` is the new version.

1. [ ] CI on `main` is green (job `packaging` included).
2. [ ] Changelog: move the `[Unreleased]` items to `## [X.Y.Z] - YYYY-MM-DD`. List the spec versions and profiles (SDK-V1).
3. [ ] Set the version in its one source of truth (table above). For TypeScript, set `SDK_VERSION` in `src/index.ts` too, then run `npm run check:version`.
4. [ ] Update the matrix in spec section 11.7 if the version or the support changed.
5. [ ] Local dry run:
   - Python: `python -m build` then `twine check --strict dist/*`; install the wheel in a fresh venv; run `fidetype --help` and `fidetype conformance --profile fep-0001`.
   - TypeScript: `cd sdk/typescript && npm ci && npm run ci && npm pack --dry-run`.
   - Rust: `cd sdk/rust && cargo test --locked && cargo package --list && cargo publish --dry-run --locked`.
6. [ ] Commit (`Release <sdk> X.Y.Z`), open a pull request, merge when CI is green.
7. [ ] Tag the merge commit: `py-vX.Y.Z`, `ts-vX.Y.Z` or `rs-vX.Y.Z`. Push the tag.
8. [ ] Run the release workflow (section 4) for that SDK and tag, or publish by hand (section 5).
9. [ ] Check the registry page: README, licence, links, version. Install the package from the registry in a clean folder and run its CLI once.
10. [ ] Create a GitHub release from the tag with the changelog entry.
11. [ ] Add an `[Unreleased]` heading to the changelog again.

## 3. One-time setup (maintainer only)
These steps need registry accounts. Only the maintainer can do them. Use **trusted publishing**: the registry trusts a GitHub Actions run of this repository through OpenID Connect (OIDC), so no long-lived token is stored in GitHub.

### 3.1 Names (state on 2026-11-21, after the first release)
| Registry | Name | State |
|---|---|---|
| PyPI | `fidetype` | taken by us (0.1.0, 2026-11-21): https://pypi.org/project/fidetype/ |
| npm | `@fidetype/sdk` | taken by us (0.1.0, 2026-11-21): https://www.npmjs.com/package/@fidetype/sdk (npm organization `fidetype`) |
| crates.io | `fidetype` | taken by us (0.1.0, 2026-11-21): https://crates.io/crates/fidetype |

Before 2026-11-21 the three names were free (read-only checks: each registry API gave 404). The first publish reserved them.

**Next release (note from 2026-11-21):** PyPI uses trusted publishing (OIDC). The npm and crates.io trusted publishers are not set yet. The first npm and crates.io uploads used one-time tokens in the environments `release-npm` and `release-crates`. These tokens expire on 2026-11-28. So the next npm or crates.io release needs a trusted publisher (sections 3.4, 3.5) or a new token.

### 3.2 GitHub
1. Create three **environments** in the repository settings: `release-pypi`, `release-npm` and `release-crates`. For each, add a **required reviewer** (yourself). Then no publish job runs without your click.
2. Restrict each environment to the branch `main` (Deployment branches and tags → Selected branches and tags → `main`). The workflow is started from `main` and checks out the tag that you type.

### 3.3 PyPI (trusted publishing)
1. Create a PyPI account and turn on 2FA.
2. Go to <https://pypi.org/manage/account/publishing/> and add a **pending publisher**: project `fidetype`, owner `zhangzibo`, repository `fidetype`, workflow `release.yml`, environment `release-pypi`. A pending publisher creates the project at the first upload.
3. Optional: do the same on TestPyPI (<https://test.pypi.org>) and run the workflow with `target: testpypi` first.

### 3.4 npm (provenance)
1. Create an npm account and turn on 2FA. Create the organization `fidetype` (free for public packages).
2. Trusted publishing on npm needs the package to exist. Do the **first** publish by hand: `cd sdk/typescript && npm ci && npm publish --access public --provenance=false` (with 2FA). `publishConfig.provenance` is true, and npm can make a provenance statement only in CI, so a manual publish needs `--provenance=false`.
3. On the package settings page on npmjs.com, add a **trusted publisher**: GitHub Actions, owner `zhangzibo`, repository `fidetype`, workflow `release.yml`, environment `release-npm`. Then later releases from the workflow need no token and get a provenance statement.
4. If you do not use trusted publishing, create a granular **automation token** limited to `@fidetype/sdk` and save it as the secret `NPM_TOKEN` in the `release-npm` environment.

### 3.5 crates.io (trusted publishing)
1. Log in to crates.io with GitHub. Verify your e-mail address.
2. The first publish must be by hand: create an API token (scope `publish-new`, crate `fidetype`, short expiry), then `cd sdk/rust && cargo publish --locked`. Revoke the token after the publish.
3. On the crate settings page, add a **trusted publisher**: GitHub, owner `zhangzibo`, repository `fidetype`, workflow `release.yml`, environment `release-crates`. Later releases from the workflow need no token.

## 4. Release workflow
The workflow is [.github/workflows/release.yml](../.github/workflows/release.yml) (it was `docs/release-workflow.example.yml` until 2026-11-18). Its only trigger is `workflow_dispatch`: GitHub never runs it by itself. Without the setup of section 3, every upload step fails. To use it:

1. Do the one-time setup (section 3).
2. Push the tag (section 2, step 7).
3. Run it by hand from the Actions tab (Use workflow from: `main`): choose the SDK, the tag and the target (`dry-run` builds and checks only; `testpypi` or `pypi` for Python; `publish` for npm and crates.io).

What the workflow does:
- It checks out the tag. It checks that the tag version equals the package version.
- It builds and checks the package (the same steps as the CI job `packaging`).
- The publish job runs in the protected environment, so you must approve it.
- Python: `pypa/gh-action-pypi-publish` with OIDC (`id-token: write`), with attestations. npm: `npm publish --provenance`. crates.io: `rust-lang/crates-io-auth-action` gets a short-lived token through OIDC, then `cargo publish`.

## 5. Manual publish (fallback)
Use this only if the workflow cannot run. Run the checklist (section 2) first.

```bash
# Python (needs a PyPI API token in ~/.pypirc or TWINE_PASSWORD)
python -m build && twine check --strict dist/* && twine upload dist/*
# TypeScript
cd sdk/typescript && npm ci && npm run ci && npm publish --access public --provenance=false
# Rust
cd sdk/rust && cargo publish --locked
```

## 6. CI guard
The job `packaging` in [.github/workflows/tests.yml](../.github/workflows/tests.yml) runs on every push and pull request. It builds the Python sdist and wheel, runs `twine check --strict`, installs the wheel in a clean venv and runs the CLI; runs `npm pack --dry-run` and checks the tarball file list; runs `cargo package --list` and `cargo publish --dry-run --locked`. The job `rust-msrv` builds the crate with its `rust-version`. So packaging cannot break silently. None of these jobs publish anything.
