---
title: TypeScript SDK
type: concept
tags: [sdk, typescript, browser, neuraltextstream, conformance, trust, schemas, m7]
sources: []
updated: 2026-11-14
---

# TypeScript SDK

Task **M7-06**. The second reference SDK, after the [Python SDK](python-sdk.md). It lives in [`sdk/typescript/`](../../sdk/typescript/README.md) (package `@fidetype/sdk`, ready for npm but not published). It runs in Node (>= 18) and in the browser (ESM). The core has zero runtime dependencies and no Node API.

## What it gives

| Job | API |
|---|---|
| Write a stream | `NtsWriter` (one checked event per line), `toJsonl` |
| Read a stream | `parseNtsText`, `readNtsEvents` (byte or text stream, chunk borders and UTF-8 handled), `validateNtsStream` |
| Accept or reject a file | `loadStream(name, bytes)`: port of the reference consumer `load_stream` (JSON Lines **and** NPZ; own ZIP/DEFLATE/NPY reader) |
| Check a file | `checkStream`: the 60 checks of the [conformance suite](conformance-suite.md), levels core / trust-ready / provenance / advisory |
| Check a live stream | `StreamValidator`: the event checks of the [streaming trust layer](streaming-trust-layer.md) `push` (header first, increasing t, normalised rows, valid n-best) |
| Act on decisions | `DecisionTracker`: per `trust_decision` the kind (commit, offer, ask, abstain, preview), the committed text or intent, `forward`, errors (FEP-0001 rules 5-8) and warnings (rule 9: empty final COMMIT); TD-12: blank candidates in a 1.x OFFER / ASK / OFFER_WORDS); `offered` drops blank texts (TD-12) |
| Conformance | `runVectors`: the golden vectors in `spec/conformance/` for `v0.1`, `fep-0001`, `fep-0002`, [`fep-0003`](intent-events.md), [`fep-0004`](websocket-input.md), [`fep-0005`](control-events.md) |
| WebSocket (M6-11) | `DecisionSubscriber` (browser `/decisions` client: resubscribe with `from_seq` on a gap), `subscribeEvents`, `IngestCore` / `SubscriberCore` (FEP-0004 cores, used by the `fep-0004` profile). Example page: `examples/ws-browser/` |

## Schemas are the source of truth
- New structural JSON schemas (draft 2020-12): `spec/schemas/nts-v0.1/` (7 event kinds) and `spec/schemas/fep-0001/` (segment_end, n-best item, decode_declaration, trust_decision), next to `spec/schemas/fep-0003/`.
- A generator writes the TypeScript types and an embedded copy of the schemas. `npm run check:schemas` fails on drift; the build and CI run it.
- A test validates every event of every accepted JSON Lines vector against its schema, and checks that the structural reject vectors break it.

## Parity with Python

| Profile | Vectors | TypeScript pass | Same verdict as Python |
|---|---|---|---|
| v0.1 (NPZ + JSON Lines) | 61 (52 before RC2) | 61 | 61/61 |
| fep-0001 | 54 (47 before RC2) | 54 | 54/54 |
| fep-0002 (LSL scenarios) | 35 (32 before RC2) | 35 | 35/35 |
| fep-0003 | 44 | 44 | 44/44 |
| fep-0004 (WebSocket scenarios) | 43 (38 before RC2) | 43 | 43/43 (Rust ported in M7-12) |
| fep-0005 ([control events](control-events.md); gap G-1) | 42 | 42 | 42/42 (Rust too) |

- **NTS 1.0 RC1 (2026-11-14):** `tdFormatErrors` / `td_format_errors` read the new optional `trust_decision.spec_version` (`"0.1"` or `"1.<minor>"`; absent = `"0.1"`). For 1.x decisions, a final COMMIT with a blank `shown[0]` is an error (rule TD-9, a MUST NOT); for 0.1 decisions it stays the warning of rule 9. The WebSocket `IngestCore` refuses a header whose `meta` is not an object (close 1007; vector W38; the parity fuzz found it at seed 5). Python = TypeScript = Rust on 213/213 vectors (fep-0001 47, fep-0004 38) and on the fuzz mutants of seeds 1-6 at `--n 30` (about 5,400 per seed). See [NTS specification](nts-spec.md).
- **NTS 1.0 RC2 (2026-11-14, gap G-2):** one function decides which header `spec_version` the SDK reads: `isSupportedSpecVersion`. It accepts `"0.1"`, `"1.0"` and `"1.<minor>"` and refuses every other value (`"2.0"`, `"1.0.0"`, `"01.0"`, `"1.01"`, numbers). `NTS-VERSION`, the streaming validator, the LSL `nts_header` check (`FEP2-DESC`), the WebSocket header check and the decision field (TD-F3) all use it. The writer still writes `"0.1"`. New vectors V53-V61, F48-F54, L33-L35, W39-W43 (21); they also close G-3 (`seq: 1.0`, `ws_seq: 2.0`, `blank_id: 0.0`) and G-4 (TD-F2 types). No other check changed: the SDK already refused the G-3 and G-4 inputs.
- **Gap G-1 (2026-11-14):** profile `fep-0005` (`src/profiles/fep0005.ts`) ports the Python control profile and the validators of `fidetype.trust.control`. For a decision log, `consume` returns `moving_ticks` (the "acted" list of control COMMITs, spec 6.4), `acted_intents` and `acted_texts`. To give the Python verdict, it copies two Python behaviours: a pointer `dims` of `true` equals 1 (Python `True == 1`), and a speed square that overflows (`float(v) ** 2` raises `OverflowError` in Python) is a rejection. The 42 vectors passed on the first run. Python = TypeScript = Rust on 279/279 vectors and on 44,196 mutants (seeds 1-6, `--n 30`; fep-0005 7,560). The parity scripts and CI include `fep-0005` without a change: they take the profile list from `CONSUMERS`.
- **P1-10 (2026-11-14):** `DecisionTracker` now tracks control decisions (`profile = "control"`). It checks CTL-T1 … T5 (format; `seq` over all profiles; ticks do not go back; one move per input tick; a HOLD may repeat a tick) and the log checks CTL-S1 … S7, with the same code as the profile `fep-0005` (`ControlSafety`). A control decision has kind commit (move) or abstain, `tick` set, `committed` null; `forward` is true on a valid control COMMIT, so the forwarded ticks are the "acted" list (6.4). An intent COMMIT while the last control decision of its session shows a control that is not engaged is invalid (CTL-S7). The tracker sees only past decisions. On every `fep-0005` decision-log vector the tracker finds an error exactly on the reject vectors and forwards exactly the expected moving ticks.
- **CTL-S7 (P1-10, 2026-11-14):** the profile `fep-0005` now refuses an intent COMMIT while the control is not engaged: before the first engage (the last control decision has `engagement` 0 or the reason `not_engaged` / `disengaged`) and after a stop until a higher `engagement`. Before, it refused it only after a stop. Python = TypeScript = Rust on 281/281 vectors (new E20 reject, E21 accept) and on 44,556 mutants (seeds 1-6, `--n 30`; fep-0005 7,920).
- **TD-12 (P1-11, 2026-11-14):** new RC2 rule: no blank candidate in `shown` of a 1.x text OFFER, ASK or OFFER_WORDS (SHOULD NOT); a consumer drops blank candidates (MUST NOT offer them). The `fep-0001` profile has the advisory check `FEP1-TD-SHOWN` (a warning, never a reject); profile `failures()` now skips advisory checks. The consumer summary of a decision log adds `offered` and `advisories`. `DecisionTracker` drops blank texts from `offered` (every version) and warns on 1.x decisions (`blankCandidateWarning` / `blank_candidate_warning`). Vectors F55, F56 (fep-0001: 56). Python = TypeScript = Rust on 283/283 vectors and on 44,916 mutants (seeds 1-6, `--n 30`). See [NTS specification](nts-spec.md).
- `npm run cross-check` runs both reference consumers on every vector and compares verdict and "ok".
- `npm run fuzz` mutates the JSON vectors (fixed seed). Two runs, about 4,000 mutants each: identical verdicts. The first fuzz runs found 6 differences (Python iterates strings and dicts; NumPy converts sample strings late). All are fixed. M7-11: seeds 1-6 at `--n 30` (24,396 mutants) give identical verdicts in Python, TypeScript and [Rust](rust-sdk.md). CI runs seeds 1-3. RC2: seeds 1-6 at `--n 30` again PASS in all three languages (36,636 mutants).
- The Python suite can also run the TS consumer: `python -m fidetype.conformance consumer --cmd "node sdk/typescript/bin/fidetype-ts.mjs consume {path}"` (52/52 before RC2; fep-0002 32/32).
- A headless Edge run of all 167 vectors (before L32) (NPZ included) passed. So the core works in a browser.

> **Our take:** Identical verdicts need the Python data model, not only the rules. Python keeps `1.0` (float) apart from `1` (int), and the profiles reject `1.0` where an integer is required. The SDK's own JSON parser records float literals for this reason. A plain `JSON.parse` port gives different verdicts on such input. A future spec version should state the rule (for example "an integer is written without a fraction or exponent"), so that every SDK can follow the text.

> **Our take:** The `fep-0002` reference consumer runs the full trust layer, so its expected values include decision counts. The SDK uses a structural model (same event checks, same counts, no decoding, no policy). This is enough to check an LSL producer. A TypeScript trust layer is a separate, larger task.

## Layout decision
`sdk/typescript/` at the top level, not under `src/`: the repo root is the Python package, and the roadmap phase P2 adds more SDKs (the [Rust SDK](rust-sdk.md), M7-07, is in `sdk/rust/`). Each SDK reads `spec/` in place.

## Fixed in M7-11 (2026-11-13)
The three-way fuzz ([Rust SDK](rust-sdk.md)) found 4 mutants where TypeScript differed from Python. All are fixed:

| Mutant | Cause | Fix |
|---|---|---|
| `l10` m22, seed 1 | String-stream samples were iterated before the empty-timestamps check | `pull` iterates them after the check, like `zip(samples, stamps)` |
| `l14` m22, seed 2 | Frames route with `blank_id` null: Python raised IndexError | Python bug, fixed in Python. Spec 3.1 and FEP-0002 section 10 now say what null means. New vector L32 |
| `l05` m12, seed 3 | A truthy non-object `consumer_settings` was read as `{}` | `pyDict` copies Python `dict(x or {})` |
| `l13` m18, seed 5 | Gap length of an infinite timestamp: `Math.round` gave no error | `pyRoundInt` (half to even, error for inf / NaN) |

## Open items
- npm publishing: a user decision. The package is ready (P2-06, 2026-11-14): `@fidetype/sdk` was free (`npm view` 404; the scope needs an npm organization `fidetype`); `private` removed, `publishConfig` public + provenance; ESM-only exports map (`.`, `./node`, `./package.json`); `files` ships only `dist/**/*.{js,d.ts}`, `bin/`, README, CHANGELOG, LICENSE (52 files, 118 kB; no tests or vectors); `prepack` cleans, builds and runs `check:version` (`package.json` = `SDK_VERSION`). A clean install imports both entry points. Outside the repository, `fidetype-ts conformance` needs `--vectors DIR`. Steps: [docs/RELEASING.md](../../docs/RELEASING.md).
- The offline demo (`demo/index.html`) is not wired to the SDK. It runs from `file://`, which cannot load ES modules; it would need a bundle.
- Parity fuzz covers JSON vectors only, not NPZ.

Related: [Python SDK](python-sdk.md), [Rust SDK](rust-sdk.md), [conformance suite](conformance-suite.md), [streaming trust layer](streaming-trust-layer.md), [LSL input](lsl-input.md), [intent events](intent-events.md), [control events](control-events.md).
