#!/usr/bin/env node
// Example: read a replay file and print the trust decisions.
//
//   node examples/replay-decisions.mjs [FILE]
//
// FILE is a JSON Lines file:
// - a decision log (only trust_decision lines, FEP-0001 section 3 / FEP-0003 section 5): each decision is
//   printed with what a consumer does with it (act only on a final COMMIT);
// - or a NeuralTextStream input stream (header first): it is validated event by event and summarised.
// Default: a decision log from the FEP-0001 golden vectors.
//
// Run `npm run build` first. In your own project: import from "@fidetype/sdk" and "@fidetype/sdk/node".

import { createReadStream } from "node:fs";
import { fileURLToPath } from "node:url";
import { DecisionTracker, StreamValidator, readNtsEvents } from "../dist/index.js";

const file = process.argv[2] ?? fileURLToPath(new URL("../../../spec/conformance/fep-0001/f25-log-two-sessions.jsonl", import.meta.url));

const tracker = new DecisionTracker();
const validator = new StreamValidator();
let kind = null;
const counts = {};
for await (const ev of readNtsEvents(createReadStream(file))) {
  kind ??= ev.type === "trust_decision" ? "decisions" : "input";
  if (kind === "decisions") {
    const d = tracker.push(ev);
    const who = `${ev.session ?? "-"}/${ev.profile === "intent" ? `unit ${ev.unit}` : `utt ${ev.utterance ?? "-"}`}`;
    let line;
    if (d.kind === "commit") line = `COMMIT  ${JSON.stringify(d.committed)}${d.forward ? "  -> send to the output" : ""}`;
    else if (d.kind === "preview") line = `preview ${ev.action} (is_final = false: show only, never act)`;
    else if (d.kind === "invalid") line = "INVALID";
    else line = `${String(ev.action).padEnd(7)} ${d.offered.length ? `offer ${JSON.stringify(d.offered)}` : ""}`;
    console.log(`${who.padEnd(14)} seq ${String(ev.seq ?? "-").padStart(3)}  ${line}`);
    for (const w of d.warnings) console.log(`${"".padEnd(24)}warning: ${w}`);
    for (const e of d.errors) console.log(`${"".padEnd(24)}error: ${e}`);
  } else {
    const r = validator.push(ev); // throws StreamEventError on a bad event
    counts[r.kind] = (counts[r.kind] ?? 0) + 1;
  }
}
if (kind === "input") console.log(`valid NeuralTextStream: ${JSON.stringify(counts)} (vocab size ${validator.vocabSize})`);
