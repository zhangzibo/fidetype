/**
 * Conformance profile `fep-0002`: NeuralTextStream over LSL (port of
 * `fidetype.conformance.profiles.fep0002`). Each vector is a JSON scenario
 * (schema `fidetype.conformance.lsl-scenario/1`).
 *
 * `inlet` scenarios run through the scenario player of {@link runInletScenario}.
 * Its decision counts come from a structural model of the reference trust
 * layer (see `lsl.ts`); all other values come from the same binding logic as
 * the Python reference.
 */

import { StreamRejected } from "../checks.js";
import { decodeUtf8, get, isObj, parseJson } from "../json.js";
import { CheckMeta, TargetReport, makeRes } from "./common.js";
import { actedTexts, tdFinalErrors, tdFormatErrors } from "./fep0001.js";
import {
  LSLStreamInfo, MARKERS_TYPE, NTS_STREAM_TYPE, checkBinding, checkNativeFrames, decisionsInfoErrors, infoFromXml, ntsHeader,
  pyIter, runInletScenario,
} from "./lsl.js";

export const FEP = "FEP-0002";
export const SUFFIXES = [".json", ".xml"];
export const SCENARIO_SCHEMA = "fidetype.conformance.lsl-scenario/1";

export const CHECKS: CheckMeta[] = [
  ["FEP2-BINDING", "MUST", "9", "desc/fidetype/binding is a known version; event_clock is lsl or source"],
  ["FEP2-FRAMES", "MUST", "3", "Frames stream: type NTS, float32 or double64, V channels, labels in vocab order, srate = 1 / frame_period"],
  ["FEP2-DESC", "MUST", "4", "desc/fidetype/nts_header is a JSON object with spec_version 0.1; values is a known kind"],
  ["FEP2-MARKERS", "MUST", "5", "Events stream: type Markers, 1 string channel, irregular rate"],
  ["FEP2-DECISIONS", "MUST", "8", "Decisions stream: Markers, 1 string channel, role and event_type keys; samples are valid trust_decision events"],
  ["FEP2-CONSUME", "MUST", "3-7", "The reference consumer accepts the scenario"],
];
const META = Object.fromEntries(CHECKS.map((c) => [c[0], c]));
const res = makeRes(META, FEP);

/** Read a `decisions` scenario. Throws StreamRejected on rejection. */
export function runDecisionsScenario(sc: Record<string, unknown>): Record<string, unknown> {
  const info = infoFromXml(String(sc.info_xml));
  const errs = decisionsInfoErrors(info);
  const events: Record<string, unknown>[] = [];
  const samples = pyIter(Object.prototype.hasOwnProperty.call(sc, "samples") ? sc.samples : []);
  samples.forEach((s, k) => {
    const n = k + 1;
    let ev: unknown;
    try {
      if (typeof s !== "string") throw new TypeError("the JSON object must be str");
      ev = parseJson(s);
    } catch (e) {
      if (e instanceof TypeError) throw e; // Python raises TypeError (not caught there) for a non-string sample
      errs.push(`sample ${n}: not JSON: ${(e as Error).message}`);
      return;
    }
    if (!isObj(ev) || ev.type !== "trust_decision") {
      errs.push(`sample ${n}: not a trust_decision event`);
      return;
    }
    ev._line = n;
    errs.push(...tdFormatErrors(ev));
    events.push(ev);
  });
  errs.push(...tdFinalErrors(events));
  if (errs.length) throw new StreamRejected(errs.slice(0, 5).join("; "), `${FEP} 8`);
  return { decisions: events.length, final: events.filter((e) => e.is_final === true).length, acted: actedTexts(events) };
}

export function loadScenario(bytes: Uint8Array): Record<string, unknown> {
  // Python json.loads (NaN / Infinity tokens are allowed here).
  const sc = parseJson(decodeUtf8(bytes), { allowConstants: true });
  if (!isObj(sc) || sc.schema !== SCENARIO_SCHEMA || (sc.kind !== "inlet" && sc.kind !== "decisions")) {
    throw new StreamRejected(`not a ${SCENARIO_SCHEMA} scenario`, FEP);
  }
  return sc;
}

/** Reference consumer of the profile: return a summary, or throw. */
export function consume(_name: string, bytes: Uint8Array): Record<string, unknown> {
  const sc = loadScenario(bytes);
  return sc.kind === "inlet" ? runInletScenario(sc) : runDecisionsScenario(sc);
}

function infoRole(info: LSLStreamInfo): string {
  if (info.fidetype.role === "trust_decisions") return "decisions";
  return info.channel_format === "string" ? "events" : "frames";
}

/** Producer checks of one LSL stream info. */
export function checkInfo(info: LSLStreamInfo) {
  const role = infoRole(info);
  let bErr: string[] = [];
  try {
    checkBinding(info);
  } catch (e) {
    bErr = [(e as Error).message];
  }
  const out = [res("FEP2-BINDING", bErr, info.fidetype.binding ?? "absent (0.1 assumed)")];
  let header: Record<string, unknown> | null = null;
  if (role !== "decisions") {
    const dErr: string[] = [];
    try {
      header = ntsHeader(info);
    } catch (e) {
      dErr.push((e as Error).message);
    }
    if (header === null && !dErr.length) dErr.push("no desc/fidetype/nts_header");
    else if (header !== null && get(header, "spec_version") !== "0.1") dErr.push(`nts_header spec_version ${JSON.stringify(get(header, "spec_version"))} is not '0.1'`);
    const values = info.fidetype.values ?? "log_probs";
    if (!["log_probs", "probs", "logits"].includes(values)) dErr.push(`values '${values}' is not log_probs, probs or logits`);
    out.push(res("FEP2-DESC", dErr));
  } else out.push(res("FEP2-DESC", null, "", "decisions stream"));
  if (role === "frames") {
    const fErr = info.type === NTS_STREAM_TYPE ? [] : [`type '${info.type}' is not '${NTS_STREAM_TYPE}'`];
    if (header !== null) {
      const vocab = (get(header, "vocab") || []) as unknown[];
      if (vocab.length !== info.channel_count) fErr.push(`${info.channel_count} channels but the vocab has ${vocab.length} tokens`);
      try {
        checkNativeFrames(info, header);
      } catch (e) {
        fErr.push((e as Error).message);
      }
    }
    out.push(res("FEP2-FRAMES", fErr));
  } else out.push(res("FEP2-FRAMES", null, "", "not a frames stream"));
  if (role === "events") {
    const mErr = info.type === MARKERS_TYPE ? [] : [`type '${info.type}' is not '${MARKERS_TYPE}'`];
    if (info.channel_count !== 1) mErr.push("an events stream has 1 channel");
    if (info.nominal_srate !== 0) mErr.push("an events stream has an irregular rate (nominal_srate 0)");
    out.push(res("FEP2-MARKERS", mErr));
  } else out.push(res("FEP2-MARKERS", null, "", "not an events stream"));
  out.push(res("FEP2-DECISIONS", role === "decisions" ? decisionsInfoErrors(info) : null, "", role === "decisions" ? null : "not a decisions stream"));
  return out;
}

/** Producer check: a stream info `.xml` file, or a scenario `.json` file. */
export function checkFile(name: string, bytes: Uint8Array): TargetReport {
  if (name.toLowerCase().endsWith(".xml")) {
    const info = infoFromXml(decodeUtf8(bytes));
    return { target: name, checks: checkInfo(info), info: { format: "lsl-info-xml", role: infoRole(info) } };
  }
  let sc: Record<string, unknown>;
  try {
    sc = loadScenario(bytes);
  } catch (e) {
    return { target: name, checks: [res("FEP2-CONSUME", [`${(e as Error).name}: ${(e as Error).message}`])], info: { format: "lsl-scenario" } };
  }
  const cid = sc.kind === "decisions" ? "FEP2-DECISIONS" : "FEP2-CONSUME";
  let r;
  try {
    if (sc.kind === "inlet") runInletScenario(sc);
    else runDecisionsScenario(sc);
    r = res(cid, [], "accepted");
  } catch (e) {
    r = res(cid, [`${(e as Error).name}: ${(e as Error).message}`]);
  }
  return { target: name, checks: [r], info: { format: "lsl-scenario", kind: sc.kind } };
}

/**
 * Keys of the inlet summary that the structural trust model computes from
 * counts only. They match the Python reference on the golden vectors, but
 * they are not a trust-layer implementation.
 */
export const STRUCTURAL_KEYS = ["decisions", "final_decisions", "aborted_utterances"];
