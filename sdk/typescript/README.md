# Fidetype TypeScript SDK (`@fidetype/sdk`)

TypeScript SDK for **NeuralTextStream (NTS) v0.1** and the draft FEP profiles. It works in Node (>= 18) and in the browser (ESM). The core has **zero runtime dependencies** and no Node API.

| Part | What it does |
|---|---|
| Writer | `NtsWriter`, `toJsonl`: write NTS JSON Lines (header, frames, hypotheses, `segment_end`, `end`). Each event is checked before it is written. |
| Reader | `parseNtsText`, `readNtsEvents`, `validateNtsStream`: read a whole text or a live byte stream (`fetch` body, Node file stream). |
| Reference consumer | `loadStream(name, bytes)`: accept or reject a `.jsonl` or `.npz` file with the core rules of the Python reference (`fidetype.conformance.io.load_stream`). |
| Checks | `checkStream`: all v0.1 checks with levels `core`, `trust-ready`, `provenance`, `advisory` (the same 59 checks as `fidetype validate`). `StreamValidator`: event-by-event checks for live streams. |
| Schemas | `validateEventSchema`: structural check against `spec/schemas/`. The TypeScript types (`NtsHeader`, `Fep0001TrustDecision`, ...) are generated from the same schemas. |
| Decisions | `DecisionTracker`, `isFinalCommit`, `committedText`, `emptyCommitWarning`: what a consumer may do with each `trust_decision` (COMMIT / OFFER / ASK / ABSTAIN, text and intent profiles). |
| Conformance | `runVectors`: run the golden vectors in `spec/conformance/` (the same files as the Python suite) for every profile. |

## Where it lives and why

The SDK is in `sdk/typescript/`. The repo root is the Python package (`pyproject.toml`, `src/fidetype/`). A separate top-level `sdk/` folder keeps the Python packaging unchanged and gives one place for the other reference SDKs of roadmap phase P2 (for example `sdk/rust/`, M7-07). The SDK reads the spec files in place (`spec/schemas/`, `spec/conformance/`), so there is one copy of each.

## Quick start

```bash
cd sdk/typescript
npm ci            # dev tools only: typescript, @types/node
npm run build     # schema drift check + compile to dist/
npm test          # unit tests + golden vectors
npm run conformance
```

Not published to npm (see "Open items"). In another local project: `npm install ../path/to/sdk/typescript`.

## Examples

### Write a stream

```ts
import { NtsWriter } from "@fidetype/sdk";

const lines: string[] = [];
const w = new NtsWriter((line) => lines.push(line), {
  source: "acme-decoder",
  frame_period: 0.04,
  meta: { "device.modality": "emg", "decoder.causal": true, "data.derived": true, language: "en" },
});
w.frame(0.0, { probs: rowOf28Probabilities });   // or { logProbs } or { logits }
w.hypothesis([{ text: "hi", score: -1.2, char_confidences: [0.9, 0.7] }], { isFinal: true });
w.segmentEnd(0.5);
w.end();
```

### Read and check a stream

```ts
import { loadStream, checkStream, StreamRejected } from "@fidetype/sdk";

try {
  const s = loadStream("stream.jsonl", bytes);       // Uint8Array; ".npz" also works
  console.log(s.summary.n_frames, s.summary.vocab_type);
} catch (e) {
  if (e instanceof StreamRejected) console.log("rejected:", e.checkId, e.clause);
}
const report = checkStream("stream.jsonl", bytes, "trust-ready");
console.log(report.ok, report.level);                // level reached: core / trust-ready / provenance
```

Live stream in the browser:

```ts
import { validateNtsStream } from "@fidetype/sdk";

const res = await fetch("/live.jsonl");
for await (const { event, result } of validateNtsStream(res.body!)) {
  if (result.kind === "frame") draw(result.t, result.row);   // throws StreamEventError at the first bad event
}
```

### Act on trust decisions

```ts
import { DecisionTracker } from "@fidetype/sdk";

const tracker = new DecisionTracker();
for (const ev of decisionEvents) {
  const d = tracker.push(ev);
  if (d.forward) output.type(d.committed!);            // final COMMIT with a non-empty text only
  else if (d.kind === "offer") ui.showChoices(d.offered);
  for (const w of d.warnings) console.warn(w);           // for example FEP-0001 rule 9
  for (const e of d.errors) console.error(e);            // rules 5-8: order, one final per utterance
}
```

Rules that the tracker applies (FEP-0001 section 3):

| Rule | Tracker behaviour |
|---|---|
| 1. Do not act on `is_final = false` | `kind = "preview"`, `forward = false` |
| 3. Forward only a final COMMIT (or a user selection after OFFER) | `forward = true` only for a final COMMIT |
| 5-7. `seq` increases; one final decision per (session, utterance) or (session, unit); nothing after it | an entry in `errors` |
| 8. A COMMIT with `shown` has at least one text | an entry in `errors` |
| 9 (SHOULD). No final COMMIT with an empty or white-space text | an entry in `warnings`, `forward = false` |

Example program (decision log or NTS input stream):

```bash
node examples/replay-decisions.mjs                     # default: spec/conformance/fep-0001/f25-log-two-sessions.jsonl
node examples/replay-decisions.mjs path/to/decisions.jsonl
```

### Command line

```bash
node bin/fidetype-ts.mjs conformance                   # all profiles in spec/conformance/
node bin/fidetype-ts.mjs validate stream.npz --level provenance
node bin/fidetype-ts.mjs decisions decisions.jsonl
node bin/fidetype-ts.mjs consume --profile fep-0001 file.jsonl   # exit 0 = accept
```

`consume` follows the external-consumer contract of the Python suite. So the Python suite can test this SDK directly:

```bash
python -m fidetype.conformance consumer --cmd "node sdk/typescript/bin/fidetype-ts.mjs consume {path}"
python -m fidetype.conformance consumer --profile fep-0002 --cmd "node sdk/typescript/bin/fidetype-ts.mjs consume --profile fep-0002 {path}"
```

## Conformance and parity with Python

| Profile | Vectors | TypeScript | Same verdict as Python |
|---|---|---|---|
| `v0.1` (NPZ + JSON Lines) | 52 | 52/52 pass | 52/52 |
| `fep-0001` streaming trust events | 40 | 40/40 pass | 40/40 |
| `fep-0002` NTS over LSL (scenarios) | 32 | 32/32 pass | 32/32 |
| `fep-0003` intent events | 44 | 44/44 pass | 44/44 |

- `npm run cross-check` runs the Python reference consumer and the TypeScript consumer on every vector and compares the verdict (accept / reject) and the "ok" result (verdict and expected values). It needs a Python with the `fidetype` package (the repo `.venv`, or `FIDETYPE_PYTHON`).
- `npm run fuzz -- --n 30` mutates the JSON and JSON Lines vectors (fixed seed) and compares the verdicts on the mutants. Seeds 1-6 (about 4,070 mutants each, 24,396 in total) give identical verdicts (M7-11). CI runs seeds 1-3.
- Both scripts take `--rust BIN` (or `$FIDETYPE_RUST_BIN`): they then also run the Rust SDK CLI (`sdk/rust`, M7-07) on the same files and require its verdict to match. M7-11 fixed the 4 TypeScript gaps that this three-way fuzz found (the last three FEP-0002 rows of the table below, and the `blank_id` null fix in Python).

Rules that matter for identical verdicts:

| Python behaviour | How the SDK copies it |
|---|---|
| `1.0` is a float, so it is not an integer (`seq`, `unit`, `set_size`, `blank_id`, ...) | The JSON parser records numbers written as float literals (`isIntAt`). |
| `NaN` / `Infinity` tokens are not JSON | Rejected (except where Python uses plain `json.loads`: LSL marker strings and scenarios). |
| Lines split with `str.splitlines()` | `pyLines` splits on the same characters. |
| `char_confidences` counts Unicode code points | Code points, not UTF-16 units. |
| The NumPy stream stores `log_probs` as float32 and checks again | `loadStream` rounds to float32 and checks the rows again. |
| FEP-0002: `zip(samples, stamps)` iterates string-stream samples only after the empty-timestamps check | `pull` iterates the raw samples after that check. |
| FEP-0002: `dict(consumer_settings or {})` | `pyDict`: a falsy value gives `{}`, a list of pairs is mapped, other values are rejected. |
| FEP-0002: `int(round(x))` for the gap length: half to even; an error for inf / NaN | `pyRoundInt`. |

### FEP-0002 note

FEP-0002 vectors are LSL scenarios. The Python reference plays them through its LSL adapter and its trust layer. The SDK ports the LSL binding logic (stream infos, clock correction, order, gaps, reconnect, markers) and uses a **structural model** of the trust layer: the same event checks and the same decision counts (`decisions`, `final_decisions`, `aborted_utterances`). It does not decode and it does not apply a trust policy. So the SDK can check an FEP-0002 producer, but it is not a TypeScript trust layer.

## Schemas are the single source of truth

- The schemas are in `spec/schemas/` (draft 2020-12): `nts-v0.1/` (header, frame, decision, hypothesis, pointer, signal_quality, end), `fep-0001/` (segment_end, n-best item, decode_declaration, trust_decision) and `fep-0003/`.
- `npm run gen:schemas` writes `src/schemas.generated.ts` (the schemas, embedded for the browser) and `src/types.generated.ts` (the types).
- `npm run check:schemas` fails if the generated files differ from the schemas. `npm run build` runs it first, and CI runs it.
- A test checks that every event of every accepted JSON Lines vector is valid under its schema, and that the structural reject vectors break their schema. So a schema cannot drift from the Python verdicts without a test failure.
- The schemas are structural. Rules across fields or events (normalisation, order, one final decision per utterance, safety rules of FEP-0003) are in the validators, as in Python.

## Browser use

- `dist/index.js` and its imports use only standard web APIs (`TextDecoder`, `ReadableStream`, `Uint8Array`). The core is compiled without Node types, and `npm run check:browser` scans the build.
- Load it as an ES module over HTTP (`<script type="module">`). Browsers do not load ES modules from `file://` pages. A headless Edge run of all 167 vectors (NPZ included) passed.
- Node-only helpers (file reading, profile folders) are in `@fidetype/sdk/node` (`dist/node.js`).

## Dependencies and licences

| Package | Kind | Version (pinned) | Licence |
|---|---|---|---|
| (none) | runtime | - | - |
| `typescript` | dev | 5.9.3 | Apache-2.0 |
| `@types/node` (and its dependency `undici-types`) | dev | 18.19.130 | MIT |

The SDK has its own small JSON Schema validator, DEFLATE decoder, NPY reader and SHA-256, so it needs no runtime package. The SDK is Apache-2.0, as the repository.

## Open items

- **npm publishing is a user decision.** The package is `private: true`. Before a release: choose the package name and scope, the versioning policy and trusted publishing (as M7-09 for PyPI).
- Optional: an IIFE bundle for the offline demo (`demo/index.html` works from `file://`, which cannot load ES modules).
- FEP-0002: a full TypeScript trust layer (decoding and policy) is not part of this SDK.
- The parity fuzz mutates JSON vectors only, not NPZ files.
