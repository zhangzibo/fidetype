# Changelog: `@fidetype/sdk` (TypeScript SDK)

This file lists the changes of the TypeScript SDK (npm package `@fidetype/sdk`). The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Versions follow [Semantic Versioning](https://semver.org/) with the 0.x rules in [docs/RELEASING.md](../../docs/RELEASING.md). Spec changes are in [spec/CHANGELOG.md](../../spec/CHANGELOG.md).

## [Unreleased]

### Added
- **Data licence keys (P5-13, NTS 1.0 RC4 amendment 6, FEP-0010).** `DEFINED_KEYS` has `data.licence` (non-empty string) and `data.research_only` (boolean). Vectors V98 (accept), V99, V100 (reject); 100 v0.1 vectors. Same verdicts as Python and Rust.
- **TD-14 (P14-20, NTS 1.0 RC4 amendment 5).** `StreamValidator.push` refuses a `trust_decision` event in an input stream (`StreamEventError` with `TD_INPUT_MESSAGE`); after `end` it is ignored. Same as Python `StreamingTrustLayer` and Rust; test on `spec/conformance/streaming/td-input.json`.
- **LSL-C7 / LSL-C8 (P3-10, amendment 5).** The `fep-0002` runner counts heartbeats (empty marker samples; result key `heartbeats`, not `ignored_markers`) and orders equal times frame first. Vectors L36, L37 (37 in all).
- **MET-11 advisory check `NTS-MODALITY-MATCH` (P1-16)** and `MODALITY_NAMESPACES`: a modality key that does not fit `device.modality` is a warning, never a reject (same as Python and Rust; vectors V93 … V96).
- **Levels (P7-02).** The v0.1 consumer summary has `warnings` (sorted ids of the advisory checks that warn) and `level` (highest stream level). The vector runner compares them where a manifest pins them. `fidetype-ts consume --level core|trust-ready|provenance` rejects a v0.1 stream below that level, so `nts-conform kit --cmd "... --level {level} ..."` can measure the NTS Trust-ready consumer level. Tests: kit total 36.
- **Conformance kit (P7-01).** `npm run conformance:kit` runs `fidetype-ts conformance --vectors ../../spec/conformance/kit` (31 kit files, part of `npm run ci`); a test checks every kit entry. Same verdicts as Python and Rust (`scripts/cross-check.mjs --vectors ../../spec/conformance/kit`). No SDK code change.
- **NTS 1.0 RC4, optional field types (GEN-11, gap G-12, FEP-0008).** The validators refuse a wrongly typed optional field: `segment_end.reason`; `hypothesis.t_start`, `t_end`, `revision_of`, `nbest[].spans`; `signal_quality.channels`; `pointer.absent`, `score`, `score_semantics` (null refused); `decision.score` and `score_range` for every semantics (DEC-6); header `vocab_id`, `vocab_version` (`NTS-VOCAB-ID`, new title); `trust_decision.reason`; intent `vocab_id`, `pending_cleared` (INT-T8); control `level` without `radius` (CTL-T8). The latency fields (TIM-4) are checked on every event of registry 12.1, frames included (`TIMING_KEYS`, `TIMED_TYPES` in `constants`; `RawStream.timed`). Same behaviour as Python and Rust (vectors V69-V82, F63-F66, D24-D26, I25, C25, E25-E27).
- `PLANNED_NAMESPACES` (`constants`): a custom `meta` key in `emg`, `eeg`, `meg`, `fnirs` or `implant` gets the `NTS-NAMESPACE` warning (MET-3, RC4 SC-2).
- Tests: vector count of `fep-0005` 52.
- **NTS 1.0 RC3, unknown enumeration values (VER-6 … VER-10, FEP-0007).** New helpers `isNewerMinor`, `enumOk`, `isUnknown` (exported from `constants`). In data whose governing version is a newer minor version (`"1.1"` …), every validator accepts an unknown enumeration string (header `vocab_type`, `clock_domain`, `device.modality`; event `score_semantics`, `unit`, `mode`, `outcome`, `source`; decision `action`, `score_semantics`, `profile`, `risk_class`, `role`, `confirmed_via`, `state`; intent and control declarations). 0.1 and 1.0 data still refuse them. Comparison rules skip unknown values. Same behaviour as Python and Rust (vectors V66-V68, F57-F59, I24, D22, D23, C24, E22-E24).
- `DecisionTracker`: new kind `"unknown"` (a valid decision with an unknown `action` or `profile`; never forwarded). `forward` is false for an intent COMMIT with an unknown `risk_class`, `role` or `confirmed_via`, and for a control COMMIT with an unknown `state` (VER-10).
- `isTextDecision` (profile absent or `"text"`) and `fep0003.unknownIntentValues`.
- The validators of `fep0003` / `fep0005` (`validateIntentDeclaration`, `validateIntentEvent`, `validateFeedbackEvent`, `validateControlDeclaration`, `validateControlEvent`, `validateEnableEvent`) take an optional `lenient` argument (default `false`).
- `NtsWriter` accepts `vocab: []` (a hypothesis-only or control-only stream, spec HDR-12). `blank_id` must then be `null` (HDR-6). With an empty vocab the writer refuses every frame: `frame()` and `event({ type: "frame" })` throw `RangeError` (HDR-12). Same behaviour and messages as the Python and Rust writers.
- Tests: the empty-vocab writer stream (same events and key order as Python and Rust) and its refusals. Vectors V62-V65 run in the v0.1 suite (65 vectors).
- Packaging for npm (P2): `repository`, `homepage`, `bugs`, `keywords`, `publishConfig` (public access, npm provenance), `./package.json` export, `LICENSE` in the package.
- `npm run check:version`: `package.json` version = `SDK_VERSION`; `LICENSE` = repository `LICENSE`. `prepack` cleans `dist/`, builds and runs this check.
- `fidetype-ts conformance` gives a clear error when the golden vectors are not present (the npm package does not ship them; pass `--vectors DIR`).

### Changed
- **New core check `NTS-TD-INPUT` (TD-4; NTS 1.0 RC4 amendment 4, roadmap P14-17).** `validate` and `loadStream` read a `trust_decision` line in a JSON Lines input stream as an unknown event type and ignored it. Now they reject the stream (a decision log is a separate file). `RawStream.tdLines` lists the lines. Vector V97; same check as the Python and Rust SDKs.
- **GEN-10 (RC3):** an integer above 2^53 - 1 in magnitude is not an integer (`isIntAt`, `isInt` use `Number.isSafeInteger`). Before, such values were accepted but lost precision. Vectors F60, F61, W44.
- **TD-F2 (RC3):** a `trust_decision` whose `declaration` is not an object is refused (vector F62).
- **PRF-4 (RC3):** the text "acted" lists (`actedTexts`, `fep0003.acted`) and `committedText` / `emptyCommitWarning` use only decisions with `profile` absent or `"text"`. A final COMMIT of an unknown profile is never acted on. `moving_ticks` lists only COMMITs with a known moving state; after a control decision with an unknown state the control counts as not engaged (CTL-S7, vector E24).
- Tests: vector counts 68 / 62 / 35 / 47 / 44 / 48 (304); the hand-written-schema test skips newer-minor (VER-8) vectors.
- `extraHeader` must not hold a key that the writer sets itself (`type`, `spec_version`, `vocab`, `vocab_type`, `blank_id`, `source`, `frame_period`, `latency`, `meta`; exported as `HEADER_KEYS`). Before, it could overwrite them and so skip the checks.
- `segmentEnd(t, unit)` checks `unit` at run time (`utterance`, `word`, `trial`; SEG-5).
- The `files` whitelist ships only `dist/**/*.js`, `dist/**/*.d.ts`, `bin/`, `README.md`, `CHANGELOG.md` and `LICENSE`.
- `private: true` is removed. Publishing is still a maintainer decision (see docs/RELEASING.md).

## [0.1.0] - not published

First development version (M7-06). It was never published to npm. It has:
- Writer, reader, reference consumer (JSON Lines and NPZ), the 59 v0.1 checks, JSON Schema validation and generated types.
- `DecisionTracker` and `trust_decision` helpers for the text, intent and control profiles; NTS 1.0 RC2 header `spec_version` support.
- Conformance runner for v0.1 and fep-0001 … fep-0005 (Node entry `@fidetype/sdk/node`); WebSocket client (FEP-0004).
- CLI `fidetype-ts` (conformance, validate, consume, decisions). ESM only; Node >= 18 and browsers.
