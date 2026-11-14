/**
 * A small JSON Schema (draft 2020-12 subset) validator, and the structural
 * check of NeuralTextStream events against the schemas in `spec/schemas/`
 * (embedded at build time in `schemas.generated.ts`).
 *
 * Supported keywords: type, enum, const, required, properties,
 * additionalProperties, items, minItems, maxItems, minLength, maxLength,
 * pattern, minimum, maximum, exclusiveMinimum, exclusiveMaximum, not,
 * anyOf, oneOf, allOf, if / then / else, $ref (local `#/$defs/...`).
 * Annotations ($schema, $id, title, description, default) are ignored.
 *
 * The schemas are structural. The semantic rules (for example "one final
 * decision per utterance") are in the validators and the conformance
 * profiles, as in the Python reference.
 */

import { isObj } from "./json.js";
import { SCHEMAS, SchemaKey } from "./schemas.generated.js";

export type Schema = boolean | Record<string, unknown>;

export interface SchemaError {
  path: string;
  message: string;
}

const KNOWN = new Set([
  "$schema", "$id", "$defs", "title", "description", "default", "examples", "$comment",
  "type", "enum", "const", "required", "properties", "additionalProperties", "items", "minItems", "maxItems",
  "minLength", "maxLength", "pattern", "minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum",
  "not", "anyOf", "oneOf", "allOf", "if", "then", "else", "$ref",
]);

function typeOk(v: unknown, t: string): boolean {
  switch (t) {
    case "null": return v === null;
    case "boolean": return typeof v === "boolean";
    case "string": return typeof v === "string";
    case "number": return typeof v === "number";
    case "integer": return typeof v === "number" && Number.isInteger(v);
    case "array": return Array.isArray(v);
    case "object": return isObj(v);
    default: throw new RangeError(`unknown JSON Schema type '${t}'`);
  }
}

function jsonEqual(a: unknown, b: unknown): boolean {
  if (a === b) return true;
  if (Array.isArray(a) && Array.isArray(b)) return a.length === b.length && a.every((x, i) => jsonEqual(x, b[i]));
  if (isObj(a) && isObj(b)) {
    const ka = Object.keys(a);
    return ka.length === Object.keys(b).length && ka.every((k) => k in b && jsonEqual(a[k], b[k]));
  }
  return false;
}

/** Validate `value` against `schema`. Returns the errors (empty: valid). Throws on an unsupported keyword. */
export function validateSchema(value: unknown, schema: Schema, root: Schema = schema, path = ""): SchemaError[] {
  if (schema === true) return [];
  if (schema === false) return [{ path, message: "no value is allowed here" }];
  const s = schema;
  const errs: SchemaError[] = [];
  const err = (message: string, p = path): void => {
    errs.push({ path: p || "/", message });
  };
  for (const k of Object.keys(s)) if (!KNOWN.has(k)) throw new RangeError(`unsupported JSON Schema keyword '${k}'`);
  if (typeof s.$ref === "string") {
    const m = /^#\/\$defs\/(.+)$/.exec(s.$ref);
    const defs = isObj(root) ? (root.$defs as Record<string, Schema> | undefined) : undefined;
    if (!m || !defs || !(m[1] in defs)) throw new RangeError(`unsupported $ref '${s.$ref}'`);
    errs.push(...validateSchema(value, defs[m[1]], root, path));
  }
  if (s.type !== undefined) {
    const types = Array.isArray(s.type) ? (s.type as string[]) : [s.type as string];
    if (!types.some((t) => typeOk(value, t))) {
      err(`must be of type ${types.join(" or ")}`);
      return errs; // other keywords would only repeat the problem
    }
  }
  if (s.enum !== undefined && !(s.enum as unknown[]).some((e) => jsonEqual(e, value))) err(`must be one of ${JSON.stringify(s.enum)}`);
  if (s.const !== undefined && !jsonEqual(s.const, value)) err(`must be ${JSON.stringify(s.const)}`);
  if (typeof value === "number") {
    if (typeof s.minimum === "number" && !(value >= s.minimum)) err(`must be >= ${s.minimum}`);
    if (typeof s.maximum === "number" && !(value <= s.maximum)) err(`must be <= ${s.maximum}`);
    if (typeof s.exclusiveMinimum === "number" && !(value > s.exclusiveMinimum)) err(`must be > ${s.exclusiveMinimum}`);
    if (typeof s.exclusiveMaximum === "number" && !(value < s.exclusiveMaximum)) err(`must be < ${s.exclusiveMaximum}`);
  }
  if (typeof value === "string") {
    const n = [...value].length;
    if (typeof s.minLength === "number" && n < s.minLength) err(`must have at least ${s.minLength} character(s)`);
    if (typeof s.maxLength === "number" && n > s.maxLength) err(`must have at most ${s.maxLength} character(s)`);
    if (typeof s.pattern === "string" && !new RegExp(s.pattern, "u").test(value)) err(`must match ${s.pattern}`);
  }
  if (Array.isArray(value)) {
    if (typeof s.minItems === "number" && value.length < s.minItems) err(`must have at least ${s.minItems} item(s)`);
    if (typeof s.maxItems === "number" && value.length > s.maxItems) err(`must have at most ${s.maxItems} item(s)`);
    if (s.items !== undefined) value.forEach((x, i) => errs.push(...validateSchema(x, s.items as Schema, root, `${path}/${i}`)));
  }
  if (isObj(value)) {
    for (const r of (s.required as string[] | undefined) ?? []) if (!Object.prototype.hasOwnProperty.call(value, r)) err(`'${r}' is required`);
    const props = (s.properties as Record<string, Schema> | undefined) ?? {};
    for (const [k, v] of Object.entries(value)) {
      if (Object.prototype.hasOwnProperty.call(props, k)) errs.push(...validateSchema(v, props[k], root, `${path}/${k}`));
      else if (s.additionalProperties !== undefined) errs.push(...validateSchema(v, s.additionalProperties as Schema, root, `${path}/${k}`));
    }
  }
  if (s.allOf) for (const sub of s.allOf as Schema[]) errs.push(...validateSchema(value, sub, root, path));
  if (s.anyOf && !(s.anyOf as Schema[]).some((sub) => !validateSchema(value, sub, root, path).length)) err("must match at least one schema of anyOf");
  if (s.oneOf) {
    const n = (s.oneOf as Schema[]).filter((sub) => !validateSchema(value, sub, root, path).length).length;
    if (n !== 1) err(`must match exactly one schema of oneOf (matches ${n})`);
  }
  if (s.not !== undefined && !validateSchema(value, s.not as Schema, root, path).length) err("must not match the 'not' schema");
  if (s.if !== undefined) {
    const cond = !validateSchema(value, s.if as Schema, root, path).length;
    if (cond && s.then !== undefined) errs.push(...validateSchema(value, s.then as Schema, root, path));
    if (!cond && s.else !== undefined) errs.push(...validateSchema(value, s.else as Schema, root, path));
  }
  return errs;
}

/** The schema of an event, by its `type` (and `profile` for trust_decision). null: no schema (an unknown type is allowed). */
export function schemaKeyFor(ev: Record<string, unknown>): SchemaKey | null {
  switch (ev.type) {
    case "header": return "nts-v0.1/header";
    case "frame": return "nts-v0.1/frame";
    case "decision": return "nts-v0.1/decision";
    case "hypothesis": return "nts-v0.1/hypothesis";
    case "pointer": return "nts-v0.1/pointer";
    case "signal_quality": return "nts-v0.1/signal-quality";
    case "end": return "nts-v0.1/end";
    case "segment_end": return "fep-0001/segment-end";
    case "trust_decision":
      if (ev.profile === "intent") return "fep-0003/intent-trust-decision" as SchemaKey;
      if (ev.profile === "control") return "fep-0005/control-trust-decision" as SchemaKey;
      return "fep-0001/trust-decision";
    case "intent": return "fep-0003/intent-event" as SchemaKey;
    case "intent_feedback": return "fep-0003/intent-feedback" as SchemaKey;
    case "control": return "fep-0005/control-event" as SchemaKey;
    case "control_enable": return "fep-0005/control-enable" as SchemaKey;
    default: return null;
  }
}

function sub(key: string, value: unknown, path: string): SchemaError[] {
  const s = (SCHEMAS as Record<string, Schema>)[key];
  return s === undefined ? [] : validateSchema(value, s, s, path);
}

/**
 * Structural check of one event against the spec schemas. It also checks
 * the nested objects that have their own schema: `decode_declaration`,
 * `intent_declaration`, `control_declaration` and the FEP-0001 n-best items. Event-internal
 * `_line` keys are ignored.
 */
export function validateEventSchema(ev: Record<string, unknown>): SchemaError[] {
  const key = schemaKeyFor(ev);
  if (key === null) return [];
  const errs = sub(key, ev, "");
  if ((ev.type === "header" || ev.type === "hypothesis") && "decode_declaration" in ev) {
    errs.push(...sub("fep-0001/decode-declaration", ev.decode_declaration, "/decode_declaration"));
  }
  if (ev.type === "header" && "intent_declaration" in ev) errs.push(...sub("fep-0003/intent-declaration", ev.intent_declaration, "/intent_declaration"));
  if (ev.type === "header" && "control_declaration" in ev) errs.push(...sub("fep-0005/control-declaration", ev.control_declaration, "/control_declaration"));
  if (ev.type === "hypothesis" && Array.isArray(ev.nbest)) {
    ev.nbest.forEach((it, i) => errs.push(...sub("fep-0001/nbest-item", it, `/nbest/${i}`)));
  }
  return errs;
}

export { SCHEMAS };
