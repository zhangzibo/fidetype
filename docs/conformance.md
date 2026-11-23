# Conformance

How to check that your producer writes valid NTS and that your consumer reads it correctly, and how to join the self-certification list.

**Status:** Release Candidate ([status levels](glossary.md#status-levels))

The conformance suite tells you if a producer writes valid NeuralTextStream (NTS) and if a consumer reads it correctly. Each check cites its spec rule. The rules are in [NTS 1.0 RC4, section 9](../spec/nts-1.0-rc4.md#9-conformance) (draft).

Start with the **conformance kit** and `nts-conform` (below). Use the [golden vectors](glossary.md#golden-vector) (further down) when you want every edge case. The **implementation levels** (NTS Core, NTS Full, NTS Trust-ready) and the **self-certification list** are further down.

## The conformance kit and `nts-conform`

The kit is a short list of realistic example files: 36 files (kit version 0.2.0), one or more for each wire form of the spec. Each file has an expected verdict, the rule ids that it exercises and, for an input stream, its `stream_level` (the highest stream level of spec 9.2 that it reaches). The files live in [`spec/conformance/kit/`](../spec/conformance/kit/). The index is [`kit.json`](../spec/conformance/kit/kit.json).

| Wire form | Spec | Kit entries |
|---|---|---|
| `jsonl-stream`: JSON Lines input stream (header, dense or sparse frames, events, `meta` keys; text, intent and control profiles) | 8.1.1, 3, 4, 7 | K01, K02, K06-K15, K19, K20, K23, K24, K32-K36 |
| `npz`: NPZ frame core | 8.1.2 | K03, K04, K05 |
| `jsonl-decision-log`: `trust_decision` lines (text, intent, control) | 6, 7.3.5, 7.4.5 | K16-K18, K21, K22, K25 |
| `lsl-capture`, `lsl-decisions-capture`: LSL binding `nts-lsl/0.1` | 8.2 | K26-K28 |
| `ws-capture`, `ws-decisions-capture`: WebSocket binding `nts-ws/0.1` | 8.3 | K29-K31 |

Binary protobuf is not a wire form in RC4. The proto files define the data model and the JSON mapping; the binary framing is planned work. The JSON Lines files of the kit are the JSON mapping.

Verdicts: `accept` (no failed check, no advisory warning), `accept-with-warnings` (only the listed advisory checks warn), `reject` (at least the listed checks fail). `nts-conform list` prints the full table.

New in kit 0.2.0: K32 (EMG keys on an EEG stream: the advisory MET-11 warning `NTS-MODALITY-MATCH`), and K33-K36, valid streams that stop below stream level provenance (K33 no `source` and no `meta`: core; K34 no provenance keys: trust-ready; K35 an offline decoder that still writes `latency`: core; K36 `calibration.applied` without `decoder.calibration_method`: core).

### Check your producer's files

`nts-conform` is installed with the Python package (`pip install -e .` in a clone). It finds the wire form and runs every profile that applies.

```sh
nts-conform check my_stream.jsonl                  # input stream, decision log, .npz, LSL / WebSocket capture
nts-conform check out/ --level trust-ready --json report.json
my-decoder --emit-nts | nts-conform check -        # a live capture on stdin (JSON Lines or NPZ)
```

Output: one line per finding, with the outcome, the rule ids, the check id, the location and the message. Example (kit file K20):

```text
spec/conformance/kit/fep-0003/k20-intent-undeclared.jsonl  [jsonl-stream; profiles v0.1, fep-0001, fep-0003; level core; stream level none]
  FAIL  INT-E2                 FEP3-INTENT          line 2         candidates[0] intent 'intent.open-door' is not in the declaration
  => FAIL: 1 failed and 0 warning checks of 51 run (26 not applicable); ...
[nts-conform: FAIL] 0/1 targets pass
[producer level: none; profiles intent]
  not higher: NTS Core: failed checks in spec/conformance/kit/fep-0003/k20-intent-undeclared.jsonl
```

- **FAIL** is a failed check at or below `--level` (default `core`). **WARN** is an advisory check, or a failed check of a higher level than `--level`.
- Each file line shows the **stream level** that the file reaches (core, trust-ready or provenance; spec 9.2). The last line shows the **producer level** of all files together (spec 9.6, below).
- The rule ids come from the traceability table of the spec ([Appendix C.1](../spec/nts-1.0-rc4.md#c1-table)). If the message names a rule of the check, only that rule is listed. Else a table of message patterns names the one or two rules of the finding (for example `FEP2-CONSUME`, which tests 17 rules, reports `LSL-F2` for a wrong channel count). Only a message that no pattern knows lists all rules of the check. The map and the pattern table (`refine`) are in [`rule-map.json`](../spec/conformance/kit/rule-map.json).
- An LSL capture or a WebSocket capture is a scenario JSON file (schemas `fidetype.conformance.lsl-scenario/1`, `fidetype.conformance.ws-scenario/1`): the stream infos and the recorded chunks or messages. See the kit files K26-K31.
- `nts-conform capture` records such a capture from a live producer. See [Record a capture from a live producer](#record-a-capture-from-a-live-producer-lsl-websocket).
- `--json OUT` writes the report (schema `fidetype.nts-conform.report/1`): per target the form, the profiles, the verdict, the outcome per rule id, and every result with rule ids, check, level, location and message.

Exit codes: 0 = every target passes, 1 = a target fails, 2 = an input error (no such file, unknown form).

### Record a capture from a live producer (LSL, WebSocket)

`nts-conform capture` records what a consumer receives from your running producer and writes it as a capture file. Then `nts-conform check` judges it like any other file.

```sh
# LSL (needs pylsl: pip install "fidetype[lsl]"). QUERY = a stream name, or key=value pairs (name, type, source_id).
nts-conform capture --lsl my.nts --out lsl.json --received lsl.received.jsonl
nts-conform capture --lsl type=Markers,name=fidetype.decisions --no-wait-end --seconds 10 --out dec.json
# WebSocket (needs websockets: pip install "fidetype[ws]")
nts-conform capture --ws ws://127.0.0.1:8765/nts --out ws.json --received ws.received.jsonl   # listens; your producer connects
nts-conform capture --ws ws://127.0.0.1:8765/decisions --seconds 10 --out wsd.json             # subscribes to your server
nts-conform check lsl.json lsl.received.jsonl --require-level core
```

| Form | What the tool does | Capture |
|---|---|---|
| `--lsl QUERY`, a frames stream | Opens the frames stream and the events stream that `desc/fidetype/events_source_id` names. Stops after the `end` event (or `--seconds`). | `lsl-scenario/1`, kind `inlet` |
| `--lsl QUERY`, a decisions stream (`role = trust_decisions`) | Records the samples for `--seconds`. | `lsl-scenario/1`, kind `decisions` |
| `--ws ws://HOST:PORT/nts` | Starts a recording server. It answers like the reference server (welcome, acks) and records each open, message and close with its time. Stops after `end` and the close (or `--seconds`). | `ws-scenario/1`, kind `ingest` |
| `--ws ws://HOST:PORT/decisions` | Subscribes with `from_seq` 1 and records every message. Stops after `--seconds` or `--max-decisions`. | `ws-scenario/1`, kind `subscribe` |

- `--received OUT.jsonl` also writes what the reference consumer reads from the capture: the NTS stream (header, frames, events) or the decision log. A producer level needs an input stream (spec 9.6), so binding evidence is the capture **and** its received stream.
- The capture keeps only the LSL stream-info fields that FEP-0002 uses. It removes the host name, uid, creation time and addresses. It never records an `Authorization` header, a token or a client address.
- Use a loopback address for the recording server. The tool warns for any other host.

### Run the kit against your implementation

Your validator or reader gets each kit file. The kit mode compares its verdicts with the expected verdicts.

```sh
nts-conform kit                                                  # the reference (must always pass)
nts-conform kit --cmd "my-validator {path}"                      # exit 0 = accept, other = reject
nts-conform kit --cmd "my-validator --profile {profile} {path}"  # {profile}: v0.1, fep-0001 ... fep-0005
nts-conform kit --impl my_pkg.reader:load                        # Python: returns = accept, raises = reject
nts-conform kit --verdicts my-verdicts.json                      # verdicts you made offline: {"K01": "accept", ...}
nts-conform kit --profile fep-0004 --json kit-report.json
```

The reference run checks two things for each file: the consumer verdict, and the producer check (`nts-conform check`). Both must give the expected verdict. With `--cmd`, `--impl` or `--verdicts`, only your verdicts are compared. The JSON report has the schema `fidetype.nts-conform.kit-report/1`.

The TypeScript and Rust SDKs run the kit with their own consumers. Each kit profile folder has a `manifest.json` in the golden-vector format, so the SDK runners read it as it is:

```sh
node sdk/typescript/bin/fidetype-ts.mjs conformance --vectors spec/conformance/kit   # or: npm run conformance:kit
fidetype-rs conformance --vectors spec/conformance/kit
nts-conform kit --cmd "fidetype-rs consume --profile {profile} {path}"
```

CI checks that Python, TypeScript and Rust give the same verdict on every kit file (`sdk/typescript/scripts/cross-check.mjs --vectors spec/conformance/kit --rust BIN`), and that the generated JSON Schema agrees with them (`tools/proto/parity.py`).

Maintainers: `nts-conform build --out spec/conformance/kit` writes the kit. `nts-conform rules --write` rebuilds `rule-map.json` after a change of Appendix C. `nts-conform levels --write` rebuilds `levels.json`. Tests fail if a copy is stale.

## Implementation levels: NTS Core, NTS Full, NTS Trust-ready

The normative text is [spec 9.6](../spec/nts-1.0-rc4.md#96-implementation-levels-nts-core-nts-full-nts-trust-ready-amendment-3) (RC4 amendment 3). The levels are cumulative. `nts-conform levels` prints them; [`levels.json`](../spec/conformance/levels.json) lists the rule ids and kit entries of each level.

| Level | What it means | Producer (`nts-conform check`) | Consumer (`nts-conform kit`) |
|---|---|---|---|
| **NTS Core** | The frame core: header, `meta`, frames, segment boundaries, `signal_quality`, the v0.1 `decision` and `pointer` events, JSON Lines and NPZ | Every file passes at `--level core`; at least one input stream | The expected verdict on the 19 `v0.1` entries (K01-K14, K32-K36) |
| **NTS Full** | Core + all event kinds of the named output profiles (text, intent, control); no profile named = all three | Core, and per named profile one file that uses its events (text: `hypothesis` or `segment_end`, or a text decision log; intent: `intent_declaration` or an intent decision log; control: `control_declaration` or a control decision log) | Core + the expected verdict on the entries of each named profile (text K15-K18, intent K19-K22, control K23-K25) |
| **NTS Trust-ready** | Full + score semantics, provenance and timing (what a trust layer needs), and the safety rules | Full, and every input stream reaches stream level provenance | Full + the expected `stream_level` of every input-stream entry |

Bindings are added to a claim: `nts-lsl/0.1` needs K26-K28, `nts-ws/0.1` needs K29-K31. Advisory checks never block a level.

```sh
nts-conform check out/*.jsonl                                 # prints the producer level
nts-conform check out/ --claim text --claim intent --require-level full
nts-conform kit --cmd "my-validator --profile {profile} --level {level} {path}" --require-level trust-ready
nts-conform kit --cmd "my-validator {path}" --claim text      # without {level}: NTS Full at most
nts-conform levels                                           # the level table
```

For NTS Trust-ready, the consumer must report stream levels. With `--cmd`, put `{level}` in the command: the kit asks it with `core`, `trust-ready` and `provenance` (profile `v0.1`), and exit 0 means "the file reaches this level". With `--impl`, give the function a `level` parameter. With `--verdicts`, write `{"K33": {"verdict": "accept", "level": "core"}, ...}`. The TypeScript and Rust CLIs support it: `fidetype-ts consume --profile {profile} --level {level} {path}`, `fidetype-rs consume --profile {profile} --level {level} {path}`.

A producer that writes only frames meets NTS Core. The stream level of its files then tells a trust layer what it gets. An NPZ-only producer stops at NTS Core (NPZ has no events).

## Self-certification

[`spec/conformance/certified.json`](../spec/conformance/certified.json) is the public list of implementations that claim a level ([spec 9.7](../spec/nts-1.0-rc4.md#97-self-certification-amendment-3)). Each entry links its evidence: the JSON report of `nts-conform`. `nts-conform certified` prints the list; CI runs `nts-conform certified --check`, which compares every entry with its evidence file.

Current entries (all from this repository; no outside entry yet):

| Entry | Class | Level |
|---|---|---|
| `fidetype-python` (reference reader, validator, `nts-conform`) | consumer | NTS Trust-ready, text + intent + control, nts-lsl/0.1 + nts-ws/0.1 |
| `fidetype-typescript` (`@fidetype/sdk`) | consumer | NTS Trust-ready, same scope |
| `fidetype-rust` (crate `fidetype`) | consumer | NTS Trust-ready, same scope |
| `fidetype-collector` (`fidetype-collector consume`: file, LSL and WebSocket receivers + `validate`, [collector](collector.md#the-collector-as-a-consumer-the-conformance-kit)) | consumer | NTS Trust-ready, text + intent + control, `nts-lsl/0.1` + `nts-ws/0.1` |
| `adapter-text-nbest` | producer | NTS Trust-ready, text |
| `adapter-spanishbcbl`, `-toronto`, `-ctc-logits`, `-kt-semg`, `-emg2qwerty` | producer | NTS Core (frames only); stream level provenance |
| `adapter-b2t25`, `adapter-willett` | producer | NTS Core (frames only); stream level trust-ready (no published weights hash) |
| `binding-lsl` (`replay_to_lsl` frames + events streams, `DecisionOutlet`) | producer | NTS Trust-ready, text, nts-lsl/0.1 |
| `binding-ws` (`WSProducer` / `replay_to_ws`, the `/decisions` channel of `WSServer`) | producer | NTS Trust-ready, text, nts-ws/0.1 |
| `fidetype-live-lsl` (`fidetype live --publish lsl`: `NTSOutlet` frames + events streams, `DecisionOutlet`; [live decode](live-decode.md#8a-publish-over-a-binding---publish)) | producer | NTS Trust-ready, text, nts-lsl/0.1 |
| `fidetype-live-ws` (`fidetype live --publish ws://.../nts` + `ws://.../decisions`: `WSProducer`, `/decisions` of `WSServer`) | producer | NTS Trust-ready, text, nts-ws/0.1 |
| `fidetype-live-file` (`fidetype live --out S.jsonl`: the NTS input stream and the decision log `S.decisions.jsonl`; [live decode](live-decode.md#8-what-the-nts-file-holds)) | producer | NTS Trust-ready, text |

The two `binding-*` entries come from captures of our own outlets. `python -m fidetype.conformance.binding_producers --out DIR` runs them in one process on loopback with synthetic input (WebSocket on 127.0.0.1; LSL with `ResolveScope = machine`), records them with `nts-conform capture` and writes each capture with its received stream. CI (job `live`) runs it and `nts-conform check DIR/lsl` / `DIR/ws --require-level trust-ready`.

The two `fidetype-live-*` entries come from captures of the `fidetype live` command itself. `--target live-lsl --target live-ws` runs `fidetype live --source synthetic --publish ...` in a child process on loopback and records it the same way. CI (job `live`) checks them at `--require-level trust-ready`.

The `fidetype-live-file` entry checks the two files of `fidetype live --out S.jsonl` together: the NTS input stream (no `trust_decision`, rule TD-4) and the decision log `S.decisions.jsonl` (`--decisions-out`). `tools/conformance/certify.py` runs `fidetype live --source synthetic --speed 0 --utterances 4 --out live.nts.jsonl` and `nts-conform check` on both files.

### Add your implementation (pull request)

1. Run the kit with the current kit version and save the JSON report.
   - Consumer (reader, validator, trust layer): `nts-conform kit --cmd "YOUR-PROGRAM --profile {profile} --level {level} {path}" --json kit-report.json` (or `--impl`, or `--verdicts`). Run the full kit: no `--profile`.
   - Producer: write real output of your producer (or the output of the same code on synthetic input) into a folder, then `nts-conform check FOLDER --json report.json`. Add `--claim` for the profiles that you claim.
   - Binding producer (LSL outlet, WebSocket sender): record it with `nts-conform capture ... --received ...` (above), then `nts-conform check FOLDER --json report.json` on the captures and the received streams. The report lists the binding (`bindings`).
2. Check the level in the last line of the output (`[consumer level: ...]` or `[producer level: ...]`).
3. Add the report as `spec/conformance/certified/<id>.kit-report.json` (consumer) or `spec/conformance/certified/<id>.report.json` (producer). It must hold no personal data and no raw recordings.
4. Add one entry to `certified.json`: `id` (lower case, digits, `-`), `implementation`, `language`, `class` (`producer` or `consumer`), `level` (`core`, `full`, `trust-ready`) and `level_title`, `profiles`, `bindings`, `spec` (`NTS 1.0 RC4 (draft)`: a claim names the draft, CNF-1), `kit_version` (from the report), `version` (of your implementation), `evidence` (the path from step 3, relative to `spec/conformance/`), `evidence_command` (the command of step 1), `maintainer`, `repository` (public URL), `licence`, `date` (YYYY-MM-DD). Optional: a link to your passing CI run.
5. Run `nts-conform certified --check` and open the pull request with the label `conformance`. A maintainer checks the evidence file and the command; CI runs the same check.

A listing is self-certification: we check the evidence, not your implementation. It is not a licence to use the Fidetype name or a mark (a trademark policy is planned work). If a later kit version adds entries, your entry stays at its kit version until you send a new report.

## Check a producer (your stream files)

The older `fidetype conformance` commands stay. They run one profile at a time.

```sh
fidetype validate my_stream.jsonl --level trust-ready
fidetype conformance check my_stream.npz --level provenance --verbose
fidetype conformance check my_decisions.jsonl --profile fep-0001
```

These `--level` values are the **stream levels** of spec 9.2 (one stream), not the implementation levels above.

| Stream level | Adds |
|---|---|
| `core` | Every MUST rule that a validator can check |
| `trust-ready` | The SHOULD rules that a trust layer needs (`source`, `device.modality`, `decoder.causal`, `data.derived`, `language`) (CNF-3) |
| `provenance` | Stream id, decoder name and version, weights hash, calibration id, pseudonymous ids (CNF-4) |

Advisory checks warn but never block a level. One of them is `NTS-MODALITY-MATCH` (MET-11): a key of `emg.*`, `meg.*` or `implant.*` on a stream whose `device.modality` does not fit (`emg.*` with `emg`; `meg.*` with `meg` or `opm-meg`; `implant.*` with `intracortical` or `ecog`). The Python, TypeScript and Rust validators give the same warning (vectors V93-V96, kit K32). Another one is `NTS-LICENCE-MATCH` (MET-12, RC4 amendment 7): `data.research_only = false` with a `data.licence` that surely does not allow commercial use, that is, a Creative Commons id with `NC` (`CC-BY-NC-4.0`, `cc-by-nc-sa-4.0`, ...) or `LicenseRef-unknown`. Other ids give no warning. Same warning in the three validators (vectors V101-V104).

`fidetype conformance list` prints every check with its level and spec clause.

## Check a consumer (your reader)

Your reader gets each golden vector as a file. It must exit 0 to accept and non-zero to reject. The suite compares the result with the expected verdict:

```sh
fidetype conformance consumer --cmd "my-reader {path}"
fidetype conformance consumer --profile fep-0001 --cmd "my-reader {path}"
```

Run the reference consumer alone (it must always pass):

```sh
fidetype conformance consumer
fidetype conformance --profile fep-0001
```

## Profiles and golden vectors

| Profile | Covers | Vectors |
|---|---|---|
| `v0.1` | Core: header, frames, segments, files (NPZ, JSON Lines) | [`spec/conformance/v0.1/`](../spec/conformance/v0.1/) |
| `fep-0001` | Text profile: hypotheses, evidence, `trust_decision` | [`spec/conformance/fep-0001/`](../spec/conformance/fep-0001/) |
| `fep-0002` | LSL binding (scenarios) | [`spec/conformance/fep-0002/`](../spec/conformance/fep-0002/) |
| `fep-0003` | Intent profile | [`spec/conformance/fep-0003/`](../spec/conformance/fep-0003/) |
| `fep-0004` | WebSocket binding (scenarios) | [`spec/conformance/fep-0004/`](../spec/conformance/fep-0004/) |
| `fep-0005` | Control profile | [`spec/conformance/fep-0005/`](../spec/conformance/fep-0005/) |

Each folder has a `manifest.json` with the expected verdict of each vector. The vectors are small synthetic files. They hold no participant data. The Python wheel ships them, so the commands above work without a clone.

## The other SDKs

```sh
node sdk/typescript/bin/fidetype-ts.mjs conformance     # after npm ci && npm run build in sdk/typescript
cd sdk/rust && cargo run --bin fidetype-rs -- conformance
```

Both CLIs also have a `consume` command that follows the consumer contract above, so the Python suite can test them directly. CI checks that Python, TypeScript and Rust give the same verdict on every vector and on fuzzed variants.

## Make a conformance claim

A claim names the class (producer, consumer, trust layer, bridge, binding), the level, the profiles, the bindings and the spec version. While NTS 1.0 is a draft, a claim must say so, for example: "Consumer, NTS 1.0 RC4 (draft), NTS Trust-ready, profiles text + intent + control, bindings nts-lsl/0.1 + nts-ws/0.1, kit 0.2.0" ([spec 9.4](../spec/nts-1.0-rc4.md#94-conformance-claims)). The claim about one stream keeps the stream level: "level provenance".

More detail: [wiki/concepts/conformance-suite.md](../wiki/concepts/conformance-suite.md).
