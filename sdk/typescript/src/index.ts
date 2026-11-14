/**
 * Fidetype TypeScript SDK: NeuralTextStream (NTS) v0.1 and the FEP-0001 /
 * FEP-0002 / FEP-0003 profiles. Browser safe: no Node API in this entry
 * point (Node file helpers are in `@fidetype/sdk/node`).
 *
 * Produce a stream:  {@link NtsWriter}, {@link toJsonl}
 * Read a stream:     {@link parseNtsText}, {@link readNtsEvents}, {@link validateNtsStream}, {@link loadStream}
 * Check a stream:    {@link checkStream}, {@link StreamValidator}, {@link validateEventSchema}
 * Act on decisions:  {@link DecisionTracker}, {@link isFinalCommit}, {@link emptyCommitWarning}
 * Conformance:       {@link runVectors}, {@link CONSUMERS}
 */

export * from "./constants.js";
export { parseJson, pyLines, isIntAt, isFloatLiteral, JsonParseError, dumpJson } from "./json.js";
export type { JsonValue, JsonObject } from "./json.js";
export { readJsonlRaw, readNpzRaw, readRaw } from "./raw.js";
export type { RawStream, NdArray, Issue } from "./raw.js";
export { readNpz, readNpy, inflateRaw } from "./npz.js";
export type { NpyArray, NpzFile } from "./npz.js";
export {
  LEVELS, blocks, runChecks, checkTable, levelReached, loadStream, consumeRaw, StreamRejected, DEFINED_KEYS,
} from "./checks.js";
export type { CheckResult, ConsumedStream, Level, Status } from "./checks.js";
export { StreamValidator, StreamEventError, parseEvent, frameRow, checkHeader, checkNbest } from "./validate.js";
export type { PushResult } from "./validate.js";
export { NtsWriter, toJsonl } from "./writer.js";
export type { WriterOptions, NbestItem } from "./writer.js";
export { parseNtsText, readLines, readNtsEvents, validateNtsStream } from "./reader.js";
export type { ChunkSource } from "./reader.js";
export { DecisionTracker, handleDecisions, isFinalCommit, committedText, emptyCommitWarning } from "./trust.js";
export type { HandledDecision, DecisionKind } from "./trust.js";
export { validateSchema, validateEventSchema, schemaKeyFor, SCHEMAS } from "./schema.js";
export type { Schema, SchemaError } from "./schema.js";
export type { SchemaKey } from "./schemas.generated.js";
export * from "./types.generated.js";
export { runVectors, reportLine, pyEqual, CONSUMERS, PROFILE_TITLES } from "./conformance.js";
export type { ProfileReport, VectorOutcome, Consumer } from "./conformance.js";
export * as fep0001 from "./profiles/fep0001.js";
export * as fep0002 from "./profiles/fep0002.js";
export * as fep0003 from "./profiles/fep0003.js";
export { sha256Hex } from "./sha256.js";

import { blocks as _blocks, levelReached as _levelReached, runChecks as _runChecks } from "./checks.js";
import { readRaw as _readRaw } from "./raw.js";

export const SDK_VERSION = "0.1.0";

/**
 * Check a stream file (the v0.1 suite): every check result, the level it
 * reaches ("core", "trust-ready", "provenance" or null) and `ok` for the
 * requested level (default "core"). Same checks as `fidetype validate`.
 */
export function checkStream(name: string, bytes: Uint8Array, level: "core" | "trust-ready" | "provenance" = "core") {
  const results = _runChecks(_readRaw(name, bytes));
  const failures = results.filter((r) => r.status === "fail" && _blocks(r.level, level));
  return { results, failures, level: _levelReached(results), ok: failures.length === 0 };
}

import type {
  Fep0001SegmentEnd, Fep0001TrustDecision, Fep0003IntentEvent, Fep0003IntentFeedback, Fep0003IntentTrustDecision,
  NtsDecision, NtsEnd, NtsFrame, NtsHeader, NtsHypothesis, NtsPointer, NtsSignalQuality,
} from "./types.generated.js";

/** Any event that a spec schema defines (v0.1, FEP-0001, FEP-0003). Unknown event types are also allowed in a stream. */
export type NtsEvent =
  | NtsHeader | NtsFrame | NtsDecision | NtsHypothesis | NtsPointer | NtsSignalQuality | NtsEnd
  | Fep0001SegmentEnd | Fep0001TrustDecision | Fep0003IntentEvent | Fep0003IntentFeedback | Fep0003IntentTrustDecision;

/** A trust_decision of the text profile (FEP-0001) or of the intent profile (FEP-0003). */
export type TrustDecision = Fep0001TrustDecision | Fep0003IntentTrustDecision;
